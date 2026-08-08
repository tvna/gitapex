"""Tests for the eval-suite schema drift gate (.github/scripts/gitapex_scan_eval_suite_schema.py).

The gate itself is `test_real_repository_eval_suites_have_no_schema_drift`:
it calls `find_drift()` with no fixture override, so the repository's real
`evals/` tree, real vendored schemas, real flake.nix pin, and real allowlist
consumers are what CI grades. Everything else here unit-tests one detector
against a temp-directory fixture.

Deliberately NOT tested against the network: `find_upstream_drift` is
exercised through an injected opener, because a test that reached
raw.githubusercontent.com would make the pytest gate fail on egress rather
than on drift. Its live behaviour is proven by running the script with
`--verify-upstream` when the pin is bumped, which is what its own `--help`
text tells a bumper to do.
"""

from __future__ import annotations

import http.client
import json
import pathlib
import urllib.error
from typing import Any

import gitapex_scan_eval_suite_schema as drift
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_MINIMAL_TASK: dict[str, Any] = {
    "id": "fixture-task",
    "name": "Fixture Task",
    "inputs": {"prompt": "do the thing"},
    "expected": {"output_contains": ["thing"]},
}

_MINIMAL_EVAL: dict[str, Any] = {
    "name": "fixture-eval",
    "description": "Fixture suite.",
    "skill": "fixture-skill",
    "config": {"trials_per_task": 1, "timeout_seconds": 300, "executor": "copilot-sdk", "model": "claude-sonnet-4.6"},
    "metrics": [{"name": "fixture_metric", "weight": 1.0, "threshold": 0.8}],
    "tasks": ["tasks/*.yaml"],
}


def _write_suite(
    root: pathlib.Path, *, task: dict[str, Any] | None = None, evaluation: dict[str, Any] | None = None
) -> pathlib.Path:
    """Build an `evals/`-shaped tree holding exactly one suite."""
    evals_dir = root / "evals"
    suite = evals_dir / "fixture-suite"
    (suite / "tasks").mkdir(parents=True)
    (suite / "eval.yaml").write_text(yaml.safe_dump(_MINIMAL_EVAL if evaluation is None else evaluation))
    (suite / "tasks" / "t.yaml").write_text(yaml.safe_dump(_MINIMAL_TASK if task is None else task))
    return evals_dir


def _copy_schemas(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Copy the real vendored schemas into `root` so a fixture validates
    against the same bytes the gate does."""
    eval_path = root / "waza-eval.schema.json"
    task_path = root / "waza-task.schema.json"
    eval_path.write_bytes(drift.EVAL_SCHEMA_PATH.read_bytes())
    task_path.write_bytes(drift.TASK_SCHEMA_PATH.read_bytes())
    return eval_path, task_path


# --- the gate ---------------------------------------------------------------


def test_real_repository_eval_suites_have_no_schema_drift() -> None:
    """THE GATE. Every committed suite validates against the vendored waza
    schemas extended by the reviewed allowlist, the vendored pin still
    matches flake.nix, and every allowlist row still names a live consumer."""
    assert drift.find_drift() == []


def test_real_repository_corpus_is_actually_non_empty() -> None:
    """A find_drift() that found nothing because it scanned nothing would
    pass the gate above vacuously."""
    eval_files, task_files = drift.iter_suite_files()
    assert len(eval_files) >= 20
    assert len(task_files) >= 300


def test_real_allowlist_keys_are_rejected_without_the_extension() -> None:
    """Each allowlisted key really is one waza's own schema rejects -- a row
    for a key upstream already permits would be inert."""
    schema = json.loads(drift.TASK_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = drift._validator_for(schema)
    for entry in drift.EXTENSION_KEYS:
        instance = {**_MINIMAL_TASK, "expected": {"output_contains": ["x"], entry.key: []}}
        assert list(validator.iter_errors(instance)), f"{entry.key} is not actually an extension key"


# --- suite validation -------------------------------------------------------


def test_clean_suite_has_no_violations(tmp_path: pathlib.Path) -> None:
    evals_dir = _write_suite(tmp_path)
    eval_path, task_path = _copy_schemas(tmp_path)
    assert drift.find_suite_violations(evals_dir, eval_path, task_path) == []


def test_allowlisted_extension_key_passes(tmp_path: pathlib.Path) -> None:
    task = {**_MINIMAL_TASK, "expected": {"output_contains": ["x"], "output_contains_near": [{"all": ["a", "b"]}]}}
    evals_dir = _write_suite(tmp_path, task=task)
    eval_path, task_path = _copy_schemas(tmp_path)
    assert drift.find_suite_violations(evals_dir, eval_path, task_path) == []


def test_misspelled_extension_key_fails(tmp_path: pathlib.Path) -> None:
    """The point of the gate: a typo in an approved key is a finding, where
    waza itself would ignore it and the local consumer would never see it."""
    task = {**_MINIMAL_TASK, "expected": {"output_contains": ["x"], "output_contains_nea": [{"all": ["a", "b"]}]}}
    evals_dir = _write_suite(tmp_path, task=task)
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_suite_violations(evals_dir, eval_path, task_path)
    assert len(findings) == 1
    assert "output_contains_nea" in findings[0]
    assert "tasks/t.yaml" in findings[0]


def test_task_missing_required_field_fails(tmp_path: pathlib.Path) -> None:
    task = {k: v for k, v in _MINIMAL_TASK.items() if k != "id"}
    evals_dir = _write_suite(tmp_path, task=task)
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_suite_violations(evals_dir, eval_path, task_path)
    assert any("'id' is a required property" in f for f in findings)


def test_eval_file_is_validated_too(tmp_path: pathlib.Path) -> None:
    evals_dir = _write_suite(tmp_path, evaluation={**_MINIMAL_EVAL, "not_a_waza_field": 1})
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_suite_violations(evals_dir, eval_path, task_path)
    assert any("eval.yaml" in f and "not_a_waza_field" in f for f in findings)


def test_suite_directory_without_eval_yaml_is_skipped(tmp_path: pathlib.Path) -> None:
    """evals/scripts/ is such a directory in the real tree: helper code, not
    a suite."""
    evals_dir = _write_suite(tmp_path)
    (evals_dir / "scripts").mkdir()
    (evals_dir / "scripts" / "helper.py").write_text("x = 1\n")
    eval_files, task_files = drift.iter_suite_files(evals_dir)
    assert [p.parent.name for p in eval_files] == ["fixture-suite"]
    assert len(task_files) == 1


def test_empty_evals_tree_fails_closed(tmp_path: pathlib.Path) -> None:
    """Dimension 15: a scan that graded nothing must not report a clean
    corpus. A renamed evals/ or a broken glob would otherwise pass."""
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_suite_violations(evals_dir, eval_path, task_path)
    assert len(findings) == 1
    assert findings[0].startswith("empty-corpus: no */eval.yaml")


def test_suite_with_no_task_files_fails_closed(tmp_path: pathlib.Path) -> None:
    evals_dir = _write_suite(tmp_path)
    (evals_dir / "fixture-suite" / "tasks" / "t.yaml").unlink()
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_suite_violations(evals_dir, eval_path, task_path)
    assert len(findings) == 1
    assert findings[0].startswith("empty-corpus: no */tasks/*.yaml")


def test_unparseable_yaml_raises_read_error(tmp_path: pathlib.Path) -> None:
    evals_dir = _write_suite(tmp_path)
    (evals_dir / "fixture-suite" / "tasks" / "t.yaml").write_text("id: [unterminated\n")
    eval_path, task_path = _copy_schemas(tmp_path)
    with pytest.raises(drift.SuiteReadError, match="is not valid YAML"):
        drift.find_suite_violations(evals_dir, eval_path, task_path)


def test_non_utf8_file_raises_read_error(tmp_path: pathlib.Path) -> None:
    evals_dir = _write_suite(tmp_path)
    (evals_dir / "fixture-suite" / "tasks" / "t.yaml").write_bytes(b"id: \xff\xfe\n")
    eval_path, task_path = _copy_schemas(tmp_path)
    with pytest.raises(drift.SuiteReadError, match="is not valid UTF-8"):
        drift.find_suite_violations(evals_dir, eval_path, task_path)


def test_missing_file_raises_read_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(drift.SuiteReadError, match="cannot be read"):
        drift._read_text_or_raise(tmp_path / "absent.txt")


# --- extend_schema ----------------------------------------------------------


def test_extend_schema_does_not_mutate_its_input() -> None:
    schema: dict[str, Any] = {"$defs": {"expected": {"properties": {}, "additionalProperties": False}}}
    drift.extend_schema(schema)
    assert schema["$defs"]["expected"]["properties"] == {}


def test_extend_schema_adds_every_allowlisted_key() -> None:
    schema: dict[str, Any] = {"$defs": {"expected": {"properties": {}, "additionalProperties": False}}}
    extended = drift.extend_schema(schema)
    assert set(extended["$defs"]["expected"]["properties"]) == {e.key for e in drift.EXTENSION_KEYS}


def test_extend_schema_never_overwrites_a_native_property() -> None:
    """A key upstream has since adopted keeps waza's own value schema; the
    allowlist row is reported by find_allowlist_drift instead."""
    native = {"type": "array"}
    schema: dict[str, Any] = {"$defs": {"expected": {"properties": {"exercises": native}}}}
    extended = drift.extend_schema(schema)
    assert extended["$defs"]["expected"]["properties"]["exercises"] == native


def test_extend_schema_tolerates_a_schema_without_defs() -> None:
    assert drift.extend_schema({"type": "object"}) == {"type": "object"}


def test_extend_schema_skips_a_missing_defs_anchor() -> None:
    schema: dict[str, Any] = {"$defs": {"other": {"properties": {}}}}
    assert drift.extend_schema(schema) == schema


def test_extend_schema_skips_a_non_mapping_properties() -> None:
    schema: dict[str, Any] = {"$defs": {"expected": {"properties": []}}}
    assert drift.extend_schema(schema) == schema


# --- allowlist integrity ----------------------------------------------------


def test_real_allowlist_has_no_drift() -> None:
    assert drift.find_allowlist_drift() == []


def test_allowlist_row_with_missing_consumer_is_reported(tmp_path: pathlib.Path) -> None:
    row = (drift.ExtensionKey("k", "expected", "nope/absent.py", "nothing"),)
    findings = drift.find_allowlist_drift(row, drift.TASK_SCHEMA_PATH, REPO_ROOT)
    assert findings == ["allowlist-drift: k: consumer does not exist: nope/absent.py"]


def test_allowlist_row_whose_consumer_stopped_reading_the_key_is_reported(tmp_path: pathlib.Path) -> None:
    consumer = tmp_path / "consumer.py"
    consumer.write_text("# this file no longer mentions the key\n")
    row = (drift.ExtensionKey("gone_key", "expected", "consumer.py", "nothing"),)
    findings = drift.find_allowlist_drift(row, drift.TASK_SCHEMA_PATH, tmp_path)
    assert len(findings) == 1
    assert "no longer mentions this key" in findings[0]


def test_allowlist_row_with_unknown_defs_anchor_is_reported() -> None:
    row = (drift.ExtensionKey("k", "no_such_def", "flake.nix", "nothing"),)
    findings = drift.find_allowlist_drift(row, drift.TASK_SCHEMA_PATH, REPO_ROOT)
    assert any("no $defs/no_such_def" in f for f in findings)


def test_allowlist_row_shadowing_a_native_property_is_reported() -> None:
    """`output_contains` is waza's own; a row for it would be dead weight."""
    row = (drift.ExtensionKey("output_contains", "expected", "flake.nix", "nothing"),)
    findings = drift.find_allowlist_drift(row, drift.TASK_SCHEMA_PATH, REPO_ROOT)
    assert any("natively" in f for f in findings)


def test_native_properties_returns_empty_set_for_a_defs_without_properties() -> None:
    assert drift._native_properties({"$defs": {"expected": {}}}, "expected") == set()


def test_native_properties_returns_none_for_a_non_mapping_schema() -> None:
    assert drift._native_properties(["not", "a", "mapping"], "expected") is None


# --- pin drift --------------------------------------------------------------


def test_real_flake_pin_matches_the_vendored_tag() -> None:
    assert drift.find_pin_drift() == []


def test_pin_drift_reported_when_flake_pins_another_tag(tmp_path: pathlib.Path) -> None:
    flake = tmp_path / "flake.nix"
    flake.write_text('url = ghRelease "microsoft" "waza" "azd-ext-microsoft-azd-waza_0.99.0" asset;\n')
    findings = drift.find_pin_drift(flake)
    assert len(findings) == 1
    assert "0.99.0" in findings[0]
    assert drift.VENDORED_WAZA_TAG in findings[0]


def test_pin_drift_reported_when_flake_pins_no_waza_tag_at_all(tmp_path: pathlib.Path) -> None:
    flake = tmp_path / "flake.nix"
    flake.write_text('{ description = "no waza here"; }\n')
    assert drift.find_pin_drift(flake) == ["pin-drift: flake.nix pins no recognizable waza release tag"]


def test_pin_drift_ignores_other_class_b_version_literals(tmp_path: pathlib.Path) -> None:
    """flake.nix carries a `version = "0.25.0";` line for apm too; matching a
    bare version assignment would grade the wrong tool's pin."""
    flake = tmp_path / "flake.nix"
    flake.write_text(f'version = "0.25.0";\nurl = ghRelease "microsoft" "waza" "{drift.VENDORED_WAZA_TAG}" a;\n')
    assert drift.find_pin_drift(flake) == []


# --- vendored digests -------------------------------------------------------


def test_real_vendored_digests_match() -> None:
    assert drift.find_vendor_digest_drift() == []


def test_edited_vendored_schema_is_reported(tmp_path: pathlib.Path) -> None:
    """The acceptance criterion's own proof method: deliberately altering a
    vendored file fails the check."""
    eval_path, task_path = _copy_schemas(tmp_path)
    task_path.write_bytes(task_path.read_bytes() + b"\n")
    findings = drift.find_vendor_digest_drift(eval_path, task_path)
    assert len(findings) == 1
    assert "vendor-digest-drift" in findings[0]
    assert "waza-task.schema.json" in findings[0]


def test_unreadable_vendored_schema_raises_read_error(tmp_path: pathlib.Path) -> None:
    eval_path, _task_path = _copy_schemas(tmp_path)
    with pytest.raises(drift.SuiteReadError, match="cannot be read"):
        drift.find_vendor_digest_drift(eval_path, tmp_path / "absent.json")


# --- upstream verification (injected opener, no real egress) ----------------


def test_upstream_drift_clean_when_bytes_match(tmp_path: pathlib.Path) -> None:
    eval_path, task_path = _copy_schemas(tmp_path)
    bodies = {"eval.schema.json": eval_path.read_bytes(), "task.schema.json": task_path.read_bytes()}
    assert drift.find_upstream_drift(eval_path, task_path, lambda url: bodies[url.rsplit("/", 1)[-1]]) == []


def test_upstream_drift_reported_when_bytes_differ(tmp_path: pathlib.Path) -> None:
    eval_path, task_path = _copy_schemas(tmp_path)
    findings = drift.find_upstream_drift(eval_path, task_path, lambda url: b"{}")
    assert len(findings) == 2
    assert all("upstream-drift" in f for f in findings)


def test_truncated_response_is_a_finding_not_a_traceback(tmp_path: pathlib.Path) -> None:
    """http.client.HTTPException is not an OSError subclass, so catching
    OSError alone would let a truncated response escape as a traceback."""
    eval_path, task_path = _copy_schemas(tmp_path)

    def _truncated(url: str) -> bytes:
        raise http.client.IncompleteRead(b"partial")

    findings = drift.find_upstream_drift(eval_path, task_path, _truncated)
    assert len(findings) == 2
    assert all("cannot fetch" in f for f in findings)


def test_upstream_fetch_failure_is_a_finding_not_a_silent_pass(tmp_path: pathlib.Path) -> None:
    eval_path, task_path = _copy_schemas(tmp_path)

    def _boom(url: str) -> bytes:
        raise urllib.error.URLError("no route to host")

    findings = drift.find_upstream_drift(eval_path, task_path, _boom)
    assert len(findings) == 2
    assert all("cannot fetch" in f for f in findings)


def test_upstream_drift_raises_read_error_for_a_missing_local_copy(tmp_path: pathlib.Path) -> None:
    eval_path, _ = _copy_schemas(tmp_path)
    with pytest.raises(drift.SuiteReadError, match="cannot be read"):
        drift.find_upstream_drift(eval_path, tmp_path / "absent.json", lambda url: b"{}")


def test_default_opener_reads_the_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one line of real urllib plumbing, exercised without egress."""

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"body"

    monkeypatch.setattr(drift.urllib.request, "urlopen", lambda url, timeout: _Response())
    assert drift.default_opener("https://example.invalid/x") == b"body"


# --- CLI --------------------------------------------------------------------


def test_main_returns_zero_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert drift.main([]) == 0
    assert "No eval suite schema drift found." in capsys.readouterr().out


def test_main_reports_findings_and_returns_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: ["pin-drift: fixture finding"])
    assert drift.main([]) == 1
    out = capsys.readouterr().out
    assert "eval suite schema drift:" in out
    assert "pin-drift: fixture finding" in out


def test_main_reports_a_read_error_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise() -> list[str]:
        raise drift.SuiteReadError("flake.nix: cannot be read: boom")

    monkeypatch.setattr(drift, "find_drift", _raise)
    assert drift.main([]) == 1
    assert "cannot be read: boom" in capsys.readouterr().out


def test_main_verify_upstream_appends_the_network_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    monkeypatch.setattr(drift, "find_upstream_drift", lambda: ["upstream-drift: fixture finding"])
    assert drift.main(["--verify-upstream"]) == 1
    assert "upstream-drift: fixture finding" in capsys.readouterr().out

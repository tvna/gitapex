"""Tests for the eval-results drift scanner
(`.github/scripts/gitapex_scan_eval_results_schema.py`), issue #926.

Three groups, in the order they carry weight:

1. **The gate itself** -- every real run record under `evals/*/results/` must
   be clean (`test_real_repository_run_records_have_no_drift`).
2. **The regression proof** -- each record as it was actually committed
   before issue #926 must produce at least one finding
   (`test_pre_fix_manifest_shapes_are_each_flagged`). A gate that passes the
   fixed tree proves nothing on its own: it also has to fail the tree that
   motivated it, which is why the seven pre-fix shapes are reconstructed
   here from the real drift issue #926 measured rather than invented.
3. **Per-rule fixtures** -- one construction per rule, each mutating a
   single field of a known-good record so a passing test cannot be passing
   for an unrelated reason.

The fixtures build a whole `evals/<skill>/results/<run>/` tree under
`tmp_path` and call `find_drift` with `min_expected_run_dirs=1`, since the
production default is a fail-closed floor sized for the real repository (see
the floor tests near the end).
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import gitapex_scan_eval_results_schema as scanner
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# A minimal pre-contract record that satisfies every layer-1 rule. Copied and
# mutated one field at a time by the per-rule tests below.
_VALID_PRE_CONTRACT: dict[str, Any] = {
    "date": "2026-08-01",
    "issue": "https://github.com/tvna/gitapex/issues/926",
    "commit": "4e8cda786b8d154fc19ff13fb108a29d7999ea72",
    "record_contract": "pre-contract",
    "fixture_set": "evals/example/tasks/normal.yaml",
    "trials_per_fixture": 1,
    "models": {"default": "claude-sonnet-5"},
    "dispatch_mechanism": "Isolated claude -p subprocess.",
    "scorer": "skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py",
    "artifacts": [],
    "known_gaps": ["record_contract is pre-contract: runner and gate were never captured."],
    "headline_pattern": "Nothing happened, and that is the finding.",
}

# The same record one contract over: a gate run, which layer 2 validates in
# full against the skill-owned schema.
_VALID_GATE_RUN: dict[str, Any] = {
    **{k: v for k, v in _VALID_PRE_CONTRACT.items() if k != "record_contract"},
    "record_contract": "gate-run",
    "runner": {"name": "waza", "version": "0.38.0"},
    "score_files": [{"model_id": "claude-sonnet-5", "file": "claude-sonnet-5.json"}],
    "gate": {
        "verdict": "KEEP",
        "candidate_class": "ordinary",
        "split": "selection",
        "prior_mean": "0.800000",
        "candidate_mean": "0.900000",
    },
    "artifacts": ["claude-sonnet-5.json"],
    "known_gaps": ["none known"],
}

_VALID_SCORE_FILE: dict[str, Any] = {
    "model_id": "claude-sonnet-5",
    "n_fixtures": 1,
    "mean_score": 0.9,
    "scores": [{"fixture_id": "example-normal", "score": 0.9}],
}


def _copy(instance: dict[str, Any]) -> Any:
    """A deep copy typed `Any` -- round-tripped through JSON, mirroring
    `tests/test_gitapex_scan_skill_metadata_schema.py`'s own fixture pattern,
    so `mypy --strict` lets a test delete or retype arbitrary nested keys."""
    return json.loads(json.dumps(instance))


def _build_run(
    tmp_path: pathlib.Path,
    manifest: Any,
    *,
    run_name: str = "2026-08-01-issue-926-example",
    skill: str = "example-skill",
    extra_files: dict[str, str] | None = None,
) -> pathlib.Path:
    """Write one `evals/<skill>/results/<run>/` tree and return the `evals`
    directory to pass as `find_drift`'s `evals_dir`.

    `manifest=None` writes no manifest at all, which is how the
    `manifest-present` rule is exercised -- the one run directory this
    repository actually committed without one
    (`2026-08-01-issue-646-transfer-check`) is the reason that rule exists.
    """
    run_dir = tmp_path / "evals" / skill / "results" / run_name
    run_dir.mkdir(parents=True)
    if manifest is not None:
        (run_dir / scanner.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name, body in (extra_files or {}).items():
        target = run_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return tmp_path / "evals"


# The fixture run label, registered as legacy so a `pre-contract` fixture is
# not flagged for claiming an exemption it is not on the real allowlist for.
# Passed explicitly rather than monkeypatched, the same escape-hatch style
# `min_expected_run_dirs` already uses -- the production default stays the
# frozen eight-record set, and
# `test_the_legacy_allowlist_is_exactly_the_committed_pre_contract_records`
# pins that.
_FIXTURE_LEGACY = frozenset({"example-skill/2026-08-01-issue-926-example"})


def _findings(evals_dir: pathlib.Path, legacy: frozenset[str] = _FIXTURE_LEGACY) -> list[str]:
    return scanner.find_drift(evals_dir, min_expected_run_dirs=1, legacy_pre_contract_runs=legacy)


def _findings_for(tmp_path: pathlib.Path, manifest: Any, **kwargs: Any) -> list[str]:
    return _findings(_build_run(tmp_path, manifest, **kwargs))


# ---- the known-good records pass, so every failure below is attributable ----


def test_valid_pre_contract_record_has_no_findings(tmp_path: pathlib.Path) -> None:
    assert _findings_for(tmp_path, _VALID_PRE_CONTRACT) == []


def test_valid_gate_run_record_has_no_findings(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(
        tmp_path,
        _VALID_GATE_RUN,
        extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)},
    )
    assert _findings(evals_dir) == []


# ---- layer 1: run-dir-naming ----


@pytest.mark.parametrize(
    "run_name",
    [
        "phase1",  # no date, no issue
        "2026-8-1-issue-926-example",  # unpadded date
        "2026-08-01-issue-example",  # no issue number
        "2026-08-01-issue-926-Example",  # uppercase label
        "2026-08-01-issue-926-two__underscores",
    ],
)
def test_run_dir_name_off_pattern_is_flagged(tmp_path: pathlib.Path, run_name: str) -> None:
    findings = _findings_for(tmp_path, _VALID_PRE_CONTRACT, run_name=run_name)
    assert any("run-dir-naming" in f for f in findings)


# ---- layer 1: manifest-present ----


def test_missing_manifest_is_flagged(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(tmp_path, None, extra_files={"artifacts/raw.md": "output"})
    findings = _findings(evals_dir)
    assert any("manifest-present" in f for f in findings)


def test_missing_manifest_skips_the_manifest_rules_without_crashing(tmp_path: pathlib.Path) -> None:
    # `continue`, not a bare exception: a directory with no manifest still
    # gets its root-contents and naming findings, and the scan goes on.
    evals_dir = _build_run(tmp_path, None, extra_files={"stray.md": "output"})
    findings = _findings(evals_dir)
    assert any("run-root-contents" in f for f in findings)
    assert not any("minimum-keys" in f for f in findings)


# ---- layer 1: run-root-contents ----


def test_markdown_in_the_run_root_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["trial-1.md"]
    findings = _findings_for(tmp_path, manifest, extra_files={"trial-1.md": "raw output"})
    assert any("run-root-contents" in f and "trial-1.md" in f for f in findings)


def test_markdown_under_artifacts_is_accepted(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/trial-1.md"]
    assert _findings_for(tmp_path, manifest, extra_files={"artifacts/trial-1.md": "raw output"}) == []


def test_unexpected_subdirectory_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["raw/trial-1.md"]
    findings = _findings_for(tmp_path, manifest, extra_files={"raw/trial-1.md": "raw output"})
    # `unexpected directory`, not a bare `"raw"` substring -- that also
    # appears in the unexpected-*file* message for any filename containing it,
    # so the looser matcher did not distinguish the two branches.
    assert any("run-root-contents" in f and "unexpected directory 'raw'" in f for f in findings)


# ---- layer 1: artifacts-agree, in both directions ----


def test_orphaned_file_is_flagged(tmp_path: pathlib.Path) -> None:
    findings = _findings_for(tmp_path, _VALID_PRE_CONTRACT, extra_files={"artifacts/trial-1.md": "raw"})
    assert any("artifacts-agree" in f and "not listed" in f for f in findings)


def test_dangling_artifact_reference_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/never-written.md"]
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "does not exist" in f for f in findings)


def test_score_file_must_also_be_listed_in_artifacts(tmp_path: pathlib.Path) -> None:
    # One reachability list, not two: a stray .json beside a record is an
    # orphan for the same reason a stray .md is.
    findings = _findings_for(tmp_path, _VALID_PRE_CONTRACT, extra_files={"claude-sonnet-5.json": "{}"})
    assert any("artifacts-agree" in f and "claude-sonnet-5.json" in f for f in findings)


def test_artifacts_not_an_array_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = "artifacts/trial-1.md"
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "must be an array" in f for f in findings)


@pytest.mark.parametrize("entry", ["", 7, None])
def test_non_string_artifact_entry_is_flagged(tmp_path: pathlib.Path, entry: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = [entry]
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "non-empty string" in f for f in findings)


@pytest.mark.parametrize("entry", ["/etc/passwd", "../../../etc/passwd", "artifacts/../../escape.md"])
def test_escaping_artifact_path_is_flagged(tmp_path: pathlib.Path, entry: str) -> None:
    # `(run_dir / entry).is_file()` does not itself guard traversal:
    # pathlib's absolute-operand rule replaces the left side outright, so an
    # absolute path that happens to exist on the host would otherwise read
    # as a resolved reference. Same defense
    # `gitapex_scan_skill_metadata_schema.py`'s `_is_bare_skill_name` states.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = [entry]
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "relative path inside the run directory" in f for f in findings)


@pytest.mark.parametrize("entry", ["./artifacts/a.md", "artifacts//a.md", "artifacts/./a.md"])
def test_equivalent_artifact_path_spellings_are_normalized(tmp_path: pathlib.Path, entry: str) -> None:
    # Unnormalized, each of these reported the listed file as an unlisted
    # orphan. Still fail-closed, but a finding that reads as a false positive
    # teaches a reader to distrust the gate.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = [entry]
    assert _findings_for(tmp_path, manifest, extra_files={"artifacts/a.md": "raw"}) == []


def test_duplicate_artifact_entry_is_flagged(tmp_path: pathlib.Path) -> None:
    # The set-difference silently deduplicated these, so a manifest could
    # promise two attachments and ship one.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/a.md", "artifacts/a.md"]
    findings = _findings_for(tmp_path, manifest, extra_files={"artifacts/a.md": "raw"})
    assert any("artifacts-agree" in f and "more than once" in f for f in findings)


def test_artifacts_listing_the_manifest_itself_is_flagged(tmp_path: pathlib.Path) -> None:
    # `artifacts[]` is defined as every file *except* the manifest; listing it
    # passed silently and made the record an attachment of itself.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = [scanner.MANIFEST_NAME]
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "must not list" in f for f in findings)


def test_unresolvable_artifact_path_is_flagged_rather_than_raising(tmp_path: pathlib.Path) -> None:
    # `Path.is_file()` swallows ENOENT/ENOTDIR/EBADF/ELOOP but not
    # ENAMETOOLONG, so this escaped `find_drift` as an OSError traceback.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/" + "x" * 5000 + ".md"]
    findings = _findings_for(tmp_path, manifest)
    assert any("artifacts-agree" in f and "cannot be resolved" in f for f in findings)


def test_nested_artifact_subdirectory_is_reachable(tmp_path: pathlib.Path) -> None:
    # `_relative_files` walks recursively, so a file nested under artifacts/
    # is still subject to the orphan check.
    findings = _findings_for(tmp_path, _VALID_PRE_CONTRACT, extra_files={"artifacts/nested/raw.md": "x"})
    assert any("artifacts-agree" in f and "nested/raw.md" in f for f in findings)


# ---- layer 1: key-spelling (the drift that actually happened) ----


def test_singular_model_key_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["model"] = "claude-sonnet-5"
    findings = _findings_for(tmp_path, manifest)
    assert any("key-spelling" in f and "'model'" in f for f in findings)


# A literal list, deliberately NOT `sorted(scanner.KEY_SPELLING_DRIFT)`.
# Parametrizing over the constant under test makes deleting a row from it
# invisible: the test case simply disappears and the suite stays green.
_EXPECTED_MISSPELLINGS = {
    "model": "models",
    "artifact": "artifacts",
    "known_gap": "known_gaps",
    "score_file": "score_files",
    "trials_per_task": "trials_per_fixture",
}


def test_the_misspelling_registry_matches_this_test_file_literally() -> None:
    assert scanner.KEY_SPELLING_DRIFT == _EXPECTED_MISSPELLINGS


@pytest.mark.parametrize("wrong", sorted(_EXPECTED_MISSPELLINGS))
def test_every_registered_misspelling_is_flagged(tmp_path: pathlib.Path, wrong: str) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest[wrong] = "anything"
    findings = _findings_for(tmp_path, manifest)
    assert any("key-spelling" in f and repr(wrong) in f for f in findings)


def test_an_unregistered_extra_key_is_tolerated(tmp_path: pathlib.Path) -> None:
    # Both schemas deliberately permit additional keys so a run can carry its
    # own context; `key-spelling` narrows that to known misspellings only,
    # and must not become an accidental allowlist.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["run_shape"] = "Checker-mechanism proof, not a full-corpus re-run."
    assert _findings_for(tmp_path, manifest) == []


# ---- layer 1: minimum-keys ----


# The ten keys, literally. Parametrizing over `scanner.README_MINIMUM_KEYS`
# would have made deleting a key from the tuple undetectable: the parameter
# vanishes, the suite stays green, and (for `commit` specifically) a manifest
# omitting the field entirely then passes layer 1 outright, since
# `find_commit_drift` returns [] when the key is absent. That is the exact
# field issue #926 measured as drifting becoming silently optional.
_EXPECTED_MINIMUM_KEYS = (
    "date",
    "issue",
    "commit",
    "fixture_set",
    "trials_per_fixture",
    "models",
    "dispatch_mechanism",
    "scorer",
    "known_gaps",
    "headline_pattern",
)

_README_PATH = REPO_ROOT / "evals" / "evaluating-skill-quality" / "results" / "README.md"


def test_the_minimum_key_registry_matches_this_test_file_literally() -> None:
    assert scanner.README_MINIMUM_KEYS == _EXPECTED_MINIMUM_KEYS


def test_the_minimum_key_registry_matches_the_readme_it_cites_as_authority() -> None:
    """`README_MINIMUM_KEYS`'s own comment names
    `evals/evaluating-skill-quality/results/README.md` as its source of truth,
    which makes the tuple a hardcoded copy of prose. Nothing tied the two
    together, in either direction -- exactly the drift class issue #926 exists
    to close ("choosing JSON is not what prevents drift, a schema plus a gate
    is"), one level up, between a Markdown sentence and a Python tuple.

    Parses the README's own "Every manifest states, at minimum:" sentence and
    asserts set equality both ways, so adding a key to either side without the
    other fails here."""
    text = _README_PATH.read_text(encoding="utf-8")
    start = text.index("Every manifest states, at minimum:")
    sentence = text[start : text.index("\n\n", start)]
    declared = set(re.findall(r"`([a-z_]+)`", sentence))
    assert declared == set(_EXPECTED_MINIMUM_KEYS)


@pytest.mark.parametrize("key", _EXPECTED_MINIMUM_KEYS)
def test_each_readme_minimum_key_is_required(tmp_path: pathlib.Path, key: str) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    del manifest[key]
    findings = _findings_for(tmp_path, manifest)
    assert any("minimum-keys" in f and repr(key) in f for f in findings)


def test_a_non_object_manifest_is_flagged(tmp_path: pathlib.Path) -> None:
    findings = _findings_for(tmp_path, ["not", "an", "object"])
    assert any("minimum-keys" in f and "not a JSON object" in f for f in findings)


# ---- layer 1: known-gaps-explicit ----


@pytest.mark.parametrize("gaps", [[], "none known"])
def test_empty_or_non_array_known_gaps_is_flagged(tmp_path: pathlib.Path, gaps: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["known_gaps"] = gaps
    findings = _findings_for(tmp_path, manifest)
    assert any("known-gaps-explicit" in f for f in findings)


@pytest.mark.parametrize("entry", ["", "   ", 7, None])
def test_blank_known_gaps_entry_is_flagged(tmp_path: pathlib.Path, entry: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["known_gaps"] = [entry]
    findings = _findings_for(tmp_path, manifest)
    assert any("known-gaps-explicit" in f and "non-empty string" in f for f in findings)


def test_explicit_none_known_is_accepted(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_GATE_RUN)
    manifest["known_gaps"] = ["none known"]
    evals_dir = _build_run(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    assert _findings(evals_dir) == []


# ---- layer 1: commit-recorded-or-disclosed ----


def test_null_commit_without_disclosure_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["commit"] = None
    findings = _findings_for(tmp_path, manifest)
    assert any("commit-recorded-or-disclosed" in f for f in findings)


def test_null_commit_with_disclosure_is_accepted(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["commit"] = None
    manifest["known_gaps"].append("commit is null: this run recorded none and one must not be guessed.")
    assert _findings_for(tmp_path, manifest) == []


@pytest.mark.parametrize("commit", ["4e8cda7", "4e8cda786b8d154fc19ff13fb108a29d7999ea72"])
def test_hex_commit_shapes_are_accepted(tmp_path: pathlib.Path, commit: str) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["commit"] = commit
    assert _findings_for(tmp_path, manifest) == []


@pytest.mark.parametrize(
    "commit",
    [
        "4e8cda",  # shorter than any abbreviation git will resolve
        "4E8CDA7",  # uppercase
        "not-a-hash",
        "4e8cda786b8d154fc19ff13fb108a29d7999ea72f",  # 41 chars
        42,
        ["4e8cda7"],
    ],
)
def test_off_shape_commit_is_flagged(tmp_path: pathlib.Path, commit: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["commit"] = commit
    findings = _findings_for(tmp_path, manifest)
    assert any("commit-recorded-or-disclosed" in f for f in findings)


# ---- layer 1: issue-full-url ----


@pytest.mark.parametrize("issue", [926, "926", "#926", "tvna/gitapex#926", None])
def test_repository_local_issue_reference_is_flagged(tmp_path: pathlib.Path, issue: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["issue"] = issue
    findings = _findings_for(tmp_path, manifest)
    assert any("issue-full-url" in f for f in findings)


# ---- layer 1/2 boundary: record-contract-declared ----


def test_undeclared_record_contract_is_flagged(tmp_path: pathlib.Path) -> None:
    # The fail-closed direction: omitting the key must not buy the layer-2
    # exemption that declaring `pre-contract` buys with a disclosure.
    manifest = _copy(_VALID_PRE_CONTRACT)
    del manifest["record_contract"]
    findings = _findings_for(tmp_path, manifest)
    assert any("record-contract-declared" in f for f in findings)


@pytest.mark.parametrize("contract", ["legacy", "", None, "GATE-RUN", 1])
def test_unknown_record_contract_value_is_flagged(tmp_path: pathlib.Path, contract: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["record_contract"] = contract
    findings = _findings_for(tmp_path, manifest)
    assert any("record-contract-declared" in f for f in findings)


def test_pre_contract_without_disclosure_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["known_gaps"] = ["Single model tier -- cross-model behavior is unmeasured."]
    findings = _findings_for(tmp_path, manifest)
    assert any("record-contract-declared" in f and "known_gaps" in f for f in findings)


def test_gate_run_without_a_gate_key_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_GATE_RUN)
    del manifest["gate"]
    evals_dir = _build_run(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    findings = _findings(evals_dir)
    assert any("record-contract-declared" in f and "gate key" in f for f in findings)


# ---- layer 2: the skill-owned schemas ----


def test_pre_contract_record_is_not_graded_against_the_gate_run_schema(tmp_path: pathlib.Path) -> None:
    # The whole point of the two-layer split: a pre-contract record carries
    # no `runner` and no `gate`, and neither is recoverable for the records
    # this repository committed before issue #932 existed.
    assert "runner" not in _VALID_PRE_CONTRACT
    assert "gate" not in _VALID_PRE_CONTRACT
    assert _findings_for(tmp_path, _VALID_PRE_CONTRACT) == []


@pytest.mark.parametrize("key", ["runner", "score_files"])
def test_gate_run_missing_a_schema_required_key_is_flagged(tmp_path: pathlib.Path, key: str) -> None:
    # `schema:` alone, with no `record-contract-declared` disjunct and no
    # `gate` parameter. Both were load-bearing in the wrong direction: with
    # layer 2 stubbed out entirely, the `gate` case still passed on layer 1's
    # own gate-key check (which the test one above already covers), so this
    # test would have kept a deleted layer 2 green.
    manifest = _copy(_VALID_GATE_RUN)
    del manifest[key]
    evals_dir = _build_run(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    findings = _findings(evals_dir)
    assert any("schema:" in f and key in f for f in findings)


def test_gate_run_with_a_null_commit_is_rejected_by_the_schema(tmp_path: pathlib.Path) -> None:
    # Layer 1 permits a disclosed null; `eval-run.schema.json` does not, and
    # a gate run reaches both. So allowing the null for a pre-contract
    # record widens nothing for a new run.
    manifest = _copy(_VALID_GATE_RUN)
    manifest["commit"] = None
    manifest["known_gaps"] = ["commit is null."]
    evals_dir = _build_run(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    findings = _findings(evals_dir)
    assert any("schema:" in f and "commit" in f for f in findings)


def test_gate_run_score_file_schema_violation_is_flagged(tmp_path: pathlib.Path) -> None:
    broken = _copy(_VALID_SCORE_FILE)
    del broken["mean_score"]
    evals_dir = _build_run(tmp_path, _VALID_GATE_RUN, extra_files={"claude-sonnet-5.json": json.dumps(broken)})
    findings = _findings(evals_dir)
    assert any("score-file claude-sonnet-5.json" in f and "mean_score" in f for f in findings)


def test_gate_run_score_file_that_does_not_exist_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_GATE_RUN)
    manifest["score_files"] = [{"model_id": "claude-sonnet-5", "file": "absent.json"}]
    manifest["artifacts"] = []
    findings = _findings_for(tmp_path, manifest)
    assert any("score-file-resolves" in f for f in findings)


@pytest.mark.parametrize("score_files", ["claude-sonnet-5.json", [None], [{"model_id": "x"}], [{"file": ""}]])
def test_malformed_score_files_rows_do_not_crash_the_scan(tmp_path: pathlib.Path, score_files: Any) -> None:
    # Each of these is `eval-run.schema.json`'s own finding to report; the
    # pointer walk must skip the row rather than raise on it. Asserted as "no
    # score-file finding, and no exception": the earlier `any("schema:")`
    # matcher was satisfied entirely by manifest-level validation, so deleting
    # the whole pointer walk left all four parameters green.
    manifest = _copy(_VALID_GATE_RUN)
    manifest["score_files"] = score_files
    manifest["artifacts"] = ["claude-sonnet-5.json"]
    evals_dir = _build_run(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    findings = _findings(evals_dir)
    assert any("schema:" in f for f in findings)
    assert not any("score-file" in f for f in findings)


@pytest.mark.parametrize(
    "bad_path",
    ["/etc/hostname", "../../../../etc/hostname", "../sibling.json", "artifacts/../../escape.json"],
)
def test_score_file_path_escaping_the_run_directory_is_flagged(tmp_path: pathlib.Path, bad_path: str) -> None:
    # `artifacts[]` had this guard from the start; `score_files[].file` had
    # none, so a committed manifest could name any JSON file on the runner and
    # the scanner would read it AND echo its parsed values into a finding --
    # which on the CI plane means into a public log. Verified against a real
    # readable outside file, so a pass cannot come from the path simply not
    # existing.
    (tmp_path / "sibling.json").write_text('{"secret": "value"}', encoding="utf-8")
    (tmp_path / "escape.json").write_text('{"secret": "value"}', encoding="utf-8")
    manifest = _copy(_VALID_GATE_RUN)
    manifest["score_files"] = [{"model_id": "claude-sonnet-5", "file": bad_path}]
    manifest["artifacts"] = []
    findings = _findings_for(tmp_path, manifest)
    assert any("score-file-resolves" in f and "refusing to read outside it" in f for f in findings)
    assert not any("secret" in f or "value" in f for f in findings)


def test_missing_run_schema_raises_rather_than_silently_passing(tmp_path: pathlib.Path) -> None:
    # Issue #926's own proof method: the scanner must "fail loudly if either
    # is absent". A `{}`-shaped fallback would validate every instance,
    # turning all of layer 2 into a silent pass.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    with pytest.raises(scanner.ResultsReadError, match="layer 2 cannot run"):
        scanner.find_drift(evals_dir, run_schema_path=tmp_path / "absent.json", min_expected_run_dirs=1)


# Absence was only one of three ways the schema dependency can go bad, and
# guarding it alone left the other two fail-open -- the vacuous-pass class the
# scanner's own docstring cites. Each row is the real bad-schema shape, not a
# hypothetical.
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("[]", "not a JSON object"),
        ("null", "not a JSON object"),
        ('"a string"', "not a JSON object"),
        ("7", "not a JSON object"),
        ('{"type": "objekt", "required": ["date"]}', "not a valid JSON Schema"),
        ('{"type": 5, "required": ["date"]}', "not a valid JSON Schema"),
        ("{}", "declares no required properties"),
        ("true", "not a JSON object"),
        ('{"$id": "eval-run.schema.json", "required": []}', "declares no required properties"),
        ('{"$id": "somewhere-else.json", "required": ["date"]}', "does not end in"),
    ],
)
def test_unusable_run_schema_raises_rather_than_validating_vacuously(
    tmp_path: pathlib.Path, body: str, expected: str
) -> None:
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    bad = tmp_path / "bad-schema.json"
    bad.write_text(body, encoding="utf-8")
    with pytest.raises(scanner.ResultsReadError, match=re.escape(expected)):
        scanner.find_drift(evals_dir, run_schema_path=bad, min_expected_run_dirs=1)


def test_the_two_schemas_swapped_for_each_other_is_flagged(tmp_path: pathlib.Path) -> None:
    # Both files name themselves correctly, so a `$id`-matches-its-own-filename
    # check passes this. The `$id` is therefore compared against the caller's
    # declared expectation instead.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    with pytest.raises(scanner.ResultsReadError, match="does not end in"):
        scanner.find_drift(evals_dir, run_schema_path=scanner.SCORES_SCHEMA_PATH, min_expected_run_dirs=1)


def test_missing_scores_schema_raises_rather_than_silently_passing(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    with pytest.raises(scanner.ResultsReadError, match="layer 2 cannot run"):
        scanner.find_drift(evals_dir, scores_schema_path=tmp_path / "absent.json", min_expected_run_dirs=1)


# ---- layer 1: checker-report-declared ----

# `dispatch-trace-check.json`'s own real committed shape: a checker report,
# not a per-model score file -- no `n_fixtures`/`mean_score`/`scores`, so it
# does not validate against `eval-scores.schema.json`.
_CHECKER_SHAPED_PAYLOAD: dict[str, Any] = {
    "model_id": "claude-sonnet-5",
    "n_runs": 2,
    "runs": [{"control": "positive", "dispatch_count": 1}],
}


def test_undeclared_non_score_root_json_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["dispatch-trace-check.json"]
    findings = _findings_for(
        tmp_path, manifest, extra_files={"dispatch-trace-check.json": json.dumps(_CHECKER_SHAPED_PAYLOAD)}
    )
    assert any("checker-report-declared" in f and "does not validate as a per-model score file" in f for f in findings)


def test_declared_checker_report_is_accepted(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["dispatch-trace-check.json"]
    manifest["checker_reports"] = ["dispatch-trace-check.json"]
    findings = _findings_for(
        tmp_path, manifest, extra_files={"dispatch-trace-check.json": json.dumps(_CHECKER_SHAPED_PAYLOAD)}
    )
    assert not any("checker-report-declared" in f for f in findings)


def test_undeclared_valid_score_file_needs_no_declaration(tmp_path: pathlib.Path) -> None:
    # A root .json file that validates against eval-scores.schema.json on its
    # own content is implicitly a legitimate score file -- declaring every
    # one of these in checker_reports[] would defeat the point of checking
    # content instead of name.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["claude-sonnet-5.json"]
    findings = _findings_for(tmp_path, manifest, extra_files={"claude-sonnet-5.json": json.dumps(_VALID_SCORE_FILE)})
    assert not any("checker-report-declared" in f for f in findings)


def test_checker_reports_not_a_list_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["checker_reports"] = "dispatch-trace-check.json"
    findings = _findings_for(tmp_path, manifest)
    assert any("checker-report-declared" in f and "must be an array" in f for f in findings)


@pytest.mark.parametrize("entry", ["", 7, None])
def test_checker_reports_non_string_entry_is_flagged(tmp_path: pathlib.Path, entry: Any) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["checker_reports"] = [entry]
    findings = _findings_for(tmp_path, manifest)
    assert any("checker-report-declared" in f and "non-empty string" in f for f in findings)


@pytest.mark.parametrize("entry", ["artifacts/dispatch-trace-check.json", "../dispatch-trace-check.json"])
def test_checker_reports_entry_with_a_path_separator_is_flagged(tmp_path: pathlib.Path, entry: str) -> None:
    # checker_reports names root-level files only -- a checker report never
    # lives under artifacts/, so a path separator is always wrong.
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["checker_reports"] = [entry]
    findings = _findings_for(tmp_path, manifest)
    assert any("checker-report-declared" in f and "bare filename" in f for f in findings)


def test_dangling_checker_report_reference_is_flagged(tmp_path: pathlib.Path) -> None:
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["checker_reports"] = ["never-written.json"]
    findings = _findings_for(tmp_path, manifest)
    assert any("checker-report-declared" in f and "does not exist" in f for f in findings)


def test_real_repository_checker_reports_are_all_declared() -> None:
    # Pins the three real records this rule found undeclared: two dispatch-
    # trace-check.json instances and #537's own non-standard before/after
    # score file. A future regression (the declaration silently dropped from
    # a manifest) fails the real-tree gate test above; this test names which
    # records the rule is actually protecting.
    declaring = {
        f"{p.parent.parent.name}/{p.name}"
        for p in scanner.discover_run_dirs()
        if isinstance(
            (m := json.loads((p / scanner.MANIFEST_NAME).read_text(encoding="utf-8"))).get("checker_reports"), list
        )
        and m["checker_reports"]
    }
    assert declaring == {
        "battle-testing-a-skill/2026-07-30-issue-584-dispatch-trace",
        "evaluating-skill-quality/2026-07-30-issue-584-dispatch-trace",
        "evaluating-skill-quality/2026-07-29-issue-537-confidentiality-gates",
    }


# ---- layer 1: no-symlinks ----


def test_symlinked_artifact_file_is_flagged(tmp_path: pathlib.Path) -> None:
    # A listed entry can be a well-behaved relative path whose target is
    # anywhere at all, which defeats the containment `_escapes_run_dir`
    # enforces on the string.
    outside = tmp_path / "outside.md"
    outside.write_text("content", encoding="utf-8")
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/link.md"]
    evals_dir = _build_run(tmp_path, manifest)
    run_dir = evals_dir / "example-skill" / "results" / "2026-08-01-issue-926-example"
    (run_dir / "artifacts").mkdir()
    (run_dir / "artifacts" / "link.md").symlink_to(outside)
    assert any("no-symlinks" in f for f in _findings(evals_dir))


def test_broken_symlink_is_flagged_rather_than_invisible(tmp_path: pathlib.Path) -> None:
    # Under an `is_file()`-based walk a dangling symlink was dropped from
    # `present` and, being unlisted, never checked at all -- invisible rather
    # than reported, the opposite of what the walk's docstring claimed.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    run_dir = evals_dir / "example-skill" / "results" / "2026-08-01-issue-926-example"
    (run_dir / "artifacts").mkdir()
    (run_dir / "artifacts" / "dangling.md").symlink_to(tmp_path / "never-created")
    assert any("no-symlinks" in f for f in _findings(evals_dir))


def test_symlinked_artifacts_directory_is_flagged(tmp_path: pathlib.Path) -> None:
    # `rglob` does not descend into a symlinked directory, so the whole
    # artifact tree could live outside the run directory and the orphan half of
    # the bidirectional check saw nothing at all.
    outside = tmp_path / "outside-tree"
    outside.mkdir()
    (outside / "listed.md").write_text("a", encoding="utf-8")
    (outside / "ORPHAN.md").write_text("b", encoding="utf-8")
    manifest = _copy(_VALID_PRE_CONTRACT)
    manifest["artifacts"] = ["artifacts/listed.md"]
    evals_dir = _build_run(tmp_path, manifest)
    run_dir = evals_dir / "example-skill" / "results" / "2026-08-01-issue-926-example"
    (run_dir / "artifacts").symlink_to(outside, target_is_directory=True)
    assert any("no-symlinks" in f for f in _findings(evals_dir))


# ---- results-dir-placement ----


@pytest.mark.parametrize("rel", ["results", "example-skill/sub/results", "example-skill/Results"])
def test_misplaced_results_directory_is_flagged(tmp_path: pathlib.Path, rel: str) -> None:
    # `discover_run_dirs` globs one fixed depth, and the discovery floor counts
    # directories -- so eight correctly-placed records plus one misplaced
    # drifting record cleared the floor and reported clean.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    (evals_dir / rel / "2026-08-01-issue-1-hidden").mkdir(parents=True)
    findings = _findings(evals_dir)
    assert any("results-dir-placement" in f for f in findings)


def test_the_expected_results_directory_is_not_flagged(tmp_path: pathlib.Path) -> None:
    assert _findings_for(tmp_path, _VALID_PRE_CONTRACT) == []


def test_misplaced_results_scan_on_a_missing_directory_is_empty(tmp_path: pathlib.Path) -> None:
    assert scanner.find_misplaced_results_dirs(tmp_path / "does-not-exist") == []


# ---- unparseable input fails loudly, never as a silent skip ----


def test_unparseable_manifest_raises(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    (evals_dir / "example-skill" / "results" / "2026-08-01-issue-926-example" / scanner.MANIFEST_NAME).write_text(
        "{not json", encoding="utf-8"
    )
    with pytest.raises(scanner.ResultsReadError, match="is not valid JSON"):
        _findings(evals_dir)


def test_pathologically_nested_manifest_raises_rather_than_recursing(tmp_path: pathlib.Path) -> None:
    # `RecursionError` is not a `JSONDecodeError` subclass, so the shared
    # loader let it escape as a traceback -- contradicting `ResultsReadError`'s
    # own "exit 1, never a traceback" contract.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    manifest = evals_dir / "example-skill" / "results" / "2026-08-01-issue-926-example" / scanner.MANIFEST_NAME
    manifest.write_text('{"a":' * 100_000, encoding="utf-8")
    with pytest.raises(scanner.ResultsReadError, match="too deeply nested"):
        _findings(evals_dir)


def test_unparseable_score_file_raises(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(tmp_path, _VALID_GATE_RUN, extra_files={"claude-sonnet-5.json": "{not json"})
    with pytest.raises(scanner.ResultsReadError, match="is not valid JSON"):
        _findings(evals_dir)


# ---- discovery ----


def test_discover_run_dirs_finds_a_directory_with_no_manifest(tmp_path: pathlib.Path) -> None:
    # Discovery is positional, not manifest-gated, precisely so
    # `manifest-present` is enforceable. Discovering by manifest would have
    # silently skipped `2026-08-01-issue-646-transfer-check`, which is how it
    # stayed unnoticed through issue #926's own measurement pass.
    evals_dir = _build_run(tmp_path, None)
    assert [p.name for p in scanner.discover_run_dirs(evals_dir)] == ["2026-08-01-issue-926-example"]


def test_discover_run_dirs_ignores_files_directly_under_results(tmp_path: pathlib.Path) -> None:
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    (evals_dir / "example-skill" / "results" / "README.md").write_text("# Results\n", encoding="utf-8")
    assert [p.name for p in scanner.discover_run_dirs(evals_dir)] == ["2026-08-01-issue-926-example"]


def test_discover_run_dirs_on_a_missing_directory_is_empty(tmp_path: pathlib.Path) -> None:
    assert scanner.discover_run_dirs(tmp_path / "does-not-exist") == []


def test_real_repository_discovers_every_committed_run_directory() -> None:
    discovered = {f"{p.parent.parent.name}/{p.name}" for p in scanner.discover_run_dirs()}
    # The eight run directories issue #926 measured -- seven with a manifest
    # and the one committed without. Pinned by name so a silently dropped
    # directory fails here rather than reading as a smaller clean corpus.
    assert discovered == {
        "battle-testing-a-skill/2026-07-30-issue-584-dispatch-trace",
        "evaluating-skill-quality/2026-07-28-issue-500-phase1",
        "evaluating-skill-quality/2026-07-29-issue-537-confidentiality-gates",
        "evaluating-skill-quality/2026-07-30-issue-584-dispatch-trace",
        "untrusted-input-triage/2026-08-01-issue-645-battle-test",
        "untrusted-input-triage/2026-08-01-issue-645-behavioral-eval",
        "untrusted-input-triage/2026-08-01-issue-646-behavioral-gate2",
        "untrusted-input-triage/2026-08-01-issue-646-transfer-check",
    }


# ---- find_drift's discovery floor (fail-closed on incomplete input) ----


def test_floor_catches_a_missing_evals_directory(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(tmp_path / "does-not-exist")
    assert any("run-discovery-floor" in f for f in findings)


def test_floor_catches_a_partially_discovered_tree(tmp_path: pathlib.Path) -> None:
    # Not only total-zero: one valid run directory is still below the real
    # repository's floor, so a checkout that lost most of `evals/` fails too.
    evals_dir = _build_run(tmp_path, _VALID_PRE_CONTRACT)
    findings = scanner.find_drift(evals_dir)
    assert any("run-discovery-floor" in f and "only 1 run directory" in f for f in findings)


def test_floor_does_not_fire_on_the_real_repository() -> None:
    assert not any("run-discovery-floor" in f for f in scanner.find_drift())


# ---- the pre-fix regression proof ----

# Each entry reconstructs one record's own committed shape as issue #926
# measured it at `edd14f4`: the keys it was missing, plus the layout
# violations it carried. A gate that only passes the fixed tree proves
# nothing; these prove it fails the tree that motivated it.
_PRE_FIX_SHAPES: dict[str, dict[str, Any]] = {
    "battle-testing/dispatch-trace (9 of 10 keys, no artifacts[])": {
        "drop": [],
        "expect": "artifacts-agree",
        "root_files": {"dispatch-trace-check.json": "{}"},
    },
    "esq/phase1 (9 of 10 keys, no artifacts[])": {
        "drop": [],
        "expect": "artifacts-agree",
        "root_files": {"claude-sonnet-5.json": "{}"},
    },
    "esq/537-confidentiality-gates (6 of 9, model spelling drift)": {
        "drop": ["commit", "fixture_set", "models"],
        "add": {"model": "inferred claude-sonnet-5"},
        "expect": "key-spelling",
        "root_files": {"claude-sonnet-5.json": "{}"},
    },
    "uit/645-battle-test (6 of 9, three unreferenced .md in the root)": {
        "drop": ["fixture_set", "trials_per_fixture", "scorer"],
        "expect": "run-root-contents",
        "root_files": {"trial-1.md": "raw", "trial-2.md": "raw", "trial-3.md": "raw"},
    },
    "uit/645-behavioral-eval (6 of 9, four unreferenced .md in the root)": {
        "drop": ["fixture_set", "trials_per_fixture", "models"],
        "expect": "minimum-keys",
        "root_files": {
            f"untrusted-input-triage-{n}.md": "raw" for n in ("normal", "guardrail", "edge", "encoded-payload")
        },
    },
    "uit/646-behavioral-gate2 (2 of 9, five unreferenced .md in the root)": {
        "drop": [
            "commit",
            "fixture_set",
            "trials_per_fixture",
            "models",
            "dispatch_mechanism",
            "scorer",
            "known_gaps",
        ],
        # The only pre-fix record that omitted known_gaps entirely, so this
        # is the finding unique to its shape.
        "expect": "minimum-keys: missing 'known_gaps'",
        "root_files": {
            f"untrusted-input-triage-{n}.md": "raw"
            for n in ("normal", "edge", "guardrail", "encoded-payload", "multi-turn-escalation")
        },
    },
    "uit/646-transfer-check (no manifest at all)": {
        "no_manifest": True,
        "expect": "manifest-present",
        "root_files": {"transfer-check-claude-opus-5.md": "raw"},
    },
}


def _build_pre_fix(tmp_path: pathlib.Path, shape: dict[str, Any], skill: str) -> list[str]:
    """One pre-fix shape as its own run directory, and the findings against it."""
    if shape.get("no_manifest"):
        manifest: Any = None
    else:
        manifest = _copy(_VALID_PRE_CONTRACT)
        # None of the pre-fix records declared either key -- both are issue
        # #926's own additions.
        del manifest["record_contract"]
        del manifest["artifacts"]
        for key in shape["drop"]:
            manifest.pop(key, None)
        manifest.update(shape.get("add", {}))
    return _findings(_build_run(tmp_path, manifest, skill=skill, extra_files=shape["root_files"]))


@pytest.mark.parametrize("label", sorted(_PRE_FIX_SHAPES))
def test_pre_fix_manifest_shapes_are_each_flagged(tmp_path: pathlib.Path, label: str) -> None:
    # Asserted against each shape's OWN `expect` rule, not bare truthiness.
    # Every shape also drops `record_contract` and `artifacts` (both are #926
    # additions), so `record-contract-declared` and `artifacts-agree` fire for
    # all seven regardless -- which meant a truthiness assertion survived
    # deleting the very rule the shape is named for.
    shape = _PRE_FIX_SHAPES[label]
    findings = _build_pre_fix(tmp_path, shape, "example-skill")
    assert any(shape["expect"] in f for f in findings), f"{label} must be flagged by {shape['expect']}; got {findings}"


def test_pre_fix_shapes_collectively_exercise_every_layer_1_rule(tmp_path: pathlib.Path) -> None:
    # The reconstructions above are only a proof if they collectively fire
    # every rule issue #926 added, not just the one easiest to trip. Without
    # this, all seven could be passing on `record-contract-declared` alone
    # and the artifacts/spelling/root-layout rules would be unproven against
    # real pre-fix shapes.
    fired: set[str] = set()
    for index, (label, shape) in enumerate(sorted(_PRE_FIX_SHAPES.items())):
        # One run directory per shape, each under its own skill name, so a
        # single tmp_path holds all seven without colliding.
        findings = _build_pre_fix(tmp_path, shape, f"shape-{index}")
        assert findings, f"{label} must produce at least one finding"
        fired |= {f.split(": ", 1)[1].split(":", 1)[0] for f in findings}
    assert {
        "record-contract-declared",
        "artifacts-agree",
        "minimum-keys",
        "key-spelling",
        "run-root-contents",
        "manifest-present",
    } <= fired


# ---- main() ----


def test_main_returns_0_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert scanner.main() == 0
    assert "No eval results schema drift found." in capsys.readouterr().out


def test_main_returns_1_on_drift(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(scanner, "find_drift", lambda: ["fake: finding"])
    assert scanner.main() == 1
    assert "fake: finding" in capsys.readouterr().out


def test_main_returns_1_on_a_read_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def _raise() -> list[str]:
        raise scanner.ResultsReadError("boom")

    monkeypatch.setattr(scanner, "find_drift", _raise)
    assert scanner.main() == 1
    assert "boom" in capsys.readouterr().out


# ---- the gate itself ----


def test_real_repository_run_records_have_no_drift() -> None:
    assert scanner.find_drift() == []


def test_the_two_skill_owned_schemas_are_where_the_registry_says_they_are() -> None:
    """Checked against `.gitapex/ssot.json`'s own `policy_sources` row, not
    re-derived from the same path components the scanner already composes --
    restating the constant would have proved only that the module agrees with
    itself. If the skill moves or its `references/` directory is renamed, this
    fails here with a locatable cause rather than as a `ResultsReadError` from
    every other test at once."""
    registry = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    gate = next(g for g in registry["gates"] if g["id"] == "eval-results-schema-drift")
    source = next(p for p in registry["policy_sources"] if p["id"] in gate["policy_refs"])
    assert REPO_ROOT / source["path"] == scanner.RUN_SCHEMA_PATH
    assert scanner.RUN_SCHEMA_PATH.parent / scanner.SCORES_SCHEMA_NAME == scanner.SCORES_SCHEMA_PATH
    assert scanner.RUN_SCHEMA_PATH.is_file()
    assert scanner.SCORES_SCHEMA_PATH.is_file()


def test_the_legacy_allowlist_is_exactly_the_committed_pre_contract_records() -> None:
    """The frozen exemption set must name every committed `pre-contract`
    record and nothing else. Both directions matter: an entry for a record
    that no longer exists is dead weight that would silently re-admit the
    exemption if that path were ever reused, and a committed `pre-contract`
    record missing from the set fails the real-tree gate."""
    committed = {
        f"{p.parent.parent.name}/{p.name}"
        for p in scanner.discover_run_dirs()
        if json.loads((p / scanner.MANIFEST_NAME).read_text(encoding="utf-8")).get("record_contract")
        == scanner.PRE_CONTRACT
    }
    assert committed == set(scanner.LEGACY_PRE_CONTRACT_RUNS)

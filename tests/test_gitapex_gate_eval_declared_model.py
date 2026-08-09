"""Tests for the declared-model allowlist gate
(.github/scripts/gitapex_gate_eval_declared_model.py).

The gate itself is `test_real_repository_declares_only_approved_models`: it
calls `find_findings()` with no fixture override, so the repository's real
`evals/` tree, real matrix workflow and real allowlist are what CI grades.
Everything else here unit-tests one detector against a temp-directory
fixture, including issue #925's own acceptance check -- a suite edited to
declare the known-retired identifier must fail.

Deliberately NOT tested: whether an approved identifier is actually
dispatchable. No environment without COPILOT_BASE_URL /
COPILOT_PROVIDER_BASE_URL can ask the copilot-sdk executor what it serves,
so a test asserting that would be asserting nothing -- the exact defect
issue #925 reports. The gate's own docstring states the same limit.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_eval_declared_model as gate
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_APPROVED = {"fixture-model-1": "approved for the fixture"}
_RETIRED = {"claude-sonnet-4.6": "FIXTURE-RETIREMENT"}

_MINIMAL_CONFIG: dict[str, object] = {
    "trials_per_task": 1,
    "timeout_seconds": 300,
    "executor": "copilot-sdk",
    "model": "fixture-model-1",
}

_MINIMAL_EVAL: dict[str, object] = {
    "name": "fixture-eval",
    "description": "Fixture suite.",
    "skill": "fixture-skill",
    "config": _MINIMAL_CONFIG,
    "metrics": [{"name": "fixture_metric", "weight": 1.0, "threshold": 0.8}],
    "tasks": ["tasks/*.yaml"],
}

_MINIMAL_WORKFLOW = """
name: fixture
on:
  workflow_dispatch:
    inputs:
      models:
        description: fixture
        required: false
        default: '["fixture-model-1"]'
jobs: {}
"""


def _write_suite(
    root: pathlib.Path, model: object, *, drop_model: bool = False, drop_config: bool = False
) -> pathlib.Path:
    """Build an `evals/`-shaped tree holding exactly one suite."""
    evals_dir = root / "evals"
    suite = evals_dir / "fixture-suite"
    suite.mkdir(parents=True)
    document: dict[str, object] = dict(_MINIMAL_EVAL)
    if drop_config:
        document.pop("config")
    else:
        config = dict(_MINIMAL_CONFIG)
        if drop_model:
            config.pop("model")
        else:
            config["model"] = model
        document["config"] = config
    (suite / "eval.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    return evals_dir


def _write_workflow(root: pathlib.Path, text: str = _MINIMAL_WORKFLOW) -> pathlib.Path:
    path = root / "waza-eval-matrix.yml"
    path.write_text(text, encoding="utf-8")
    return path


# --- the gate ---------------------------------------------------------------


def test_real_repository_declares_only_approved_models() -> None:
    """Issue #925's own acceptance criterion, against the real tree: every
    committed model identifier is one APPROVED_MODELS records evidence for."""
    assert gate.find_findings() == []


def test_real_repository_declares_no_retired_model() -> None:
    """The specific regression issue #925 reports, asserted directly rather
    than only through the allowlist: no committed surface names an identifier
    RETIRED_MODELS knows to be undispatchable."""
    declared = {
        path.relative_to(REPO_ROOT): yaml.safe_load(path.read_text(encoding="utf-8"))["config"]["model"]
        for path in sorted((REPO_ROOT / "evals").glob("*/eval.yaml"))
    }
    offenders = {path: model for path, model in declared.items() if model in gate.RETIRED_MODELS}
    assert offenders == {}, f"retired model identifiers still declared: {offenders}"
    assert set(gate._matrix_default_models(gate.MATRIX_WORKFLOW_PATH)) & set(gate.RETIRED_MODELS) == set()
    env_models = {value for _, value in gate._hardcoded_env_models(gate.MATRIX_WORKFLOW_PATH)}
    assert env_models & set(gate.RETIRED_MODELS) == set()


# --- issue #937 regressions -------------------------------------------------
#
# Each test below fails against dbb0186 (PR #931's merge commit) and passes
# after the fix. They assert the exception *type* and the message *identity*,
# not that some exception or some substring occurred -- that weaker shape is
# what let these five through 100% statement coverage in the first place.


def test_null_workflow_dispatch_raises_the_typed_error(tmp_path: pathlib.Path) -> None:
    """Defect 1. `workflow_dispatch:` with no children parses that key to
    `None`. Before the fix, `.get("inputs", {})` on it raised `AttributeError`
    -- not a `DeclarationReadError`, so it escaped `main()`'s handler and
    surfaced as a raw traceback from a gate whose contract is a typed message.
    `pytest.raises` is deliberately given the exact class, so an
    `AttributeError` fails this test rather than satisfying it."""
    path = _write_workflow(tmp_path, "on:\n  workflow_dispatch:\njobs: {}\n")
    with pytest.raises(gate.DeclarationReadError):
        gate._matrix_default_models(path)


def test_null_workflow_dispatch_exits_one_through_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same defect at the boundary that actually matters: `main()` must
    report and return 1, not propagate. Before the fix this raised."""
    workflow = REPO_ROOT / "tests" / "does-not-exist-null-dispatch.yml"
    monkeypatch.setattr(gate, "MATRIX_WORKFLOW_PATH", workflow)
    workflow.write_text("on:\n  workflow_dispatch:\njobs: {}\n", encoding="utf-8")
    try:
        assert gate.main([]) == 1
        assert "declared model allowlist:" in capsys.readouterr().out
    finally:
        workflow.unlink()


def test_describe_reports_against_the_mappings_it_was_given() -> None:
    """Defect 2. `_describe` must name the caller's allowlist and the caller's
    retirement reason, never this module's globals. Asserted by identity: the
    fixture's own tokens are present and the real ones are absent, so reading
    a global cannot pass."""
    message = gate._describe("fixture-retired", {"fixture-approved": "e"}, {"fixture-retired": "FIXTURE-REASON"})
    assert "FIXTURE-REASON" in message
    assert "fixture-approved" in message
    for real_id in (*gate.APPROVED_MODELS, *gate.RETIRED_MODELS):
        assert real_id not in message


def test_describe_names_no_approved_ids_when_the_given_allowlist_is_empty() -> None:
    """The same defect at its clearest: an empty override must render as an
    empty approved set, not as the module's real one."""
    message = gate._describe("anything", {}, {})
    assert "(none)" in message
    for real_id in gate.APPROVED_MODELS:
        assert real_id not in message


def test_blank_retirement_reason_is_an_integrity_finding() -> None:
    """Defect 3. Before the fix only APPROVED_MODELS rows were checked, so a
    blank retirement reason rendered as `is a known-undispatchable model ().`"""
    findings = gate.find_allowlist_integrity_violations({"a": "evidence"}, {"b": "   "})
    assert findings == ["allowlist integrity: RETIRED_MODELS['b'] carries no evidence"]


def test_judge_model_and_grader_model_are_graded(tmp_path: pathlib.Path) -> None:
    """Defect 4, suite half. Neither field is populated in the committed
    corpus, which is exactly why a hardcoded `config.model` read looked
    complete. Each must be graded the moment it appears."""
    evals_dir = _write_suite(tmp_path, "fixture-model-1")
    document = yaml.safe_load((evals_dir / "fixture-suite" / "eval.yaml").read_text(encoding="utf-8"))
    document["config"]["judge_model"] = "claude-sonnet-4.6"
    document["graders"] = [{"type": "prompt", "name": "g", "model": "some-unapproved-grader-model"}]
    (evals_dir / "fixture-suite" / "eval.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    findings = gate.find_suite_violations(evals_dir, _APPROVED, _RETIRED)
    fields = sorted(finding.split(": ", 1)[1].split(" ", 1)[0] for finding in findings)
    assert fields == ["config.judge_model", "graders[0].model"]
    assert any("FIXTURE-RETIREMENT" in finding for finding in findings)


def test_task_files_are_graded_too(tmp_path: pathlib.Path) -> None:
    """Defect 4, task half. The task schema carries its own model-bearing
    fields, and four committed task files already declare `graders`."""
    evals_dir = _write_suite(tmp_path, "fixture-model-1")
    tasks = evals_dir / "fixture-suite" / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        yaml.safe_dump(
            {"id": "t", "name": "T", "inputs": {"prompt": "x", "responder": {"model": "claude-sonnet-4.6"}}}
        ),
        encoding="utf-8",
    )
    findings = gate.find_suite_violations(evals_dir, _APPROVED, _RETIRED)
    assert len(findings) == 1
    assert "tasks/t.yaml" in findings[0]
    assert "inputs.responder.model" in findings[0]
    assert "FIXTURE-RETIREMENT" in findings[0]


def test_a_task_file_declaring_no_model_is_not_an_error(tmp_path: pathlib.Path) -> None:
    """Only `eval.yaml` must pin a model; the task-level fields are optional
    overrides, so their absence must not raise."""
    evals_dir = _write_suite(tmp_path, "fixture-model-1")
    tasks = evals_dir / "fixture-suite" / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(yaml.safe_dump({"id": "t", "name": "T", "inputs": {"prompt": "x"}}), encoding="utf-8")
    assert gate.find_suite_violations(evals_dir, _APPROVED, _RETIRED) == []


def test_hardcoded_env_model_is_graded(tmp_path: pathlib.Path) -> None:
    """Defect 4, workflow half. A hardcoded `*_MODEL` env value is dispatched
    and is not operator-supplied, so the live-probe exemption the `models`
    input carries does not extend to it."""
    path = _write_workflow(
        tmp_path,
        _MINIMAL_WORKFLOW.replace(
            "jobs: {}", "jobs:\n  j:\n    steps:\n      - env:\n          HF_X_MODEL: claude-sonnet-4.6\n"
        ),
    )
    findings = gate.find_matrix_default_violations(path, _APPROVED, _RETIRED)
    assert len(findings) == 1
    assert "hardcoded env HF_X_MODEL" in findings[0]
    assert "FIXTURE-RETIREMENT" in findings[0]


def test_unreadable_workflow_raises_from_the_env_walk_too(tmp_path: pathlib.Path) -> None:
    """The env walk parses the workflow independently of the default-input
    parse, so it needs its own read guard -- an unhandled decode error there
    would escape `main()` exactly the way defect 1 did."""
    path = tmp_path / "waza-eval-matrix.yml"
    path.write_bytes(b"on:\n  workflow_dispatch: \xff\xfe\n")
    with pytest.raises(gate.DeclarationReadError, match="cannot be read as UTF-8 YAML"):
        gate._hardcoded_env_models(path)


def test_expression_valued_env_model_is_not_graded(tmp_path: pathlib.Path) -> None:
    """An env value resolved from a dispatch input or secret at run time is
    operator-supplied and carries the same live-probe exemption."""
    path = _write_workflow(
        tmp_path,
        _MINIMAL_WORKFLOW.replace(
            "jobs: {}", "jobs:\n  j:\n    steps:\n      - env:\n          HF_X_MODEL: ${{ matrix.model }}\n"
        ),
    )
    assert gate._hardcoded_env_models(path) == []


# --- suite declarations -----------------------------------------------------


def test_approved_suite_model_passes(tmp_path: pathlib.Path) -> None:
    assert gate.find_suite_violations(_write_suite(tmp_path, "fixture-model-1"), _APPROVED) == []


def test_unapproved_suite_model_is_reported(tmp_path: pathlib.Path) -> None:
    findings = gate.find_suite_violations(_write_suite(tmp_path, "fixture-model-unknown"), _APPROVED)
    assert len(findings) == 1
    assert "fixture-model-unknown" in findings[0]
    assert "not on the reviewed allowlist" in findings[0]


def test_retired_suite_model_reports_its_retirement(tmp_path: pathlib.Path) -> None:
    """A suite edited to declare the known-retired identifier fails, and the
    message names the retirement instead of a generic allowlist miss --
    issue #925's third acceptance row."""
    findings = gate.find_suite_violations(_write_suite(tmp_path, "claude-sonnet-4.6"), _APPROVED)
    assert len(findings) == 1
    assert "retired 2026-06-15" in findings[0]


def test_missing_model_raises_rather_than_passing(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.DeclarationReadError, match="declares no 'model'"):
        gate.find_suite_violations(_write_suite(tmp_path, None, drop_model=True), _APPROVED)


def test_missing_config_raises_rather_than_passing(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.DeclarationReadError, match="no 'config' mapping"):
        gate.find_suite_violations(_write_suite(tmp_path, None, drop_config=True), _APPROVED)


def test_non_string_model_raises_rather_than_passing(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.DeclarationReadError, match=r"config\.model is int"):
        gate.find_suite_violations(_write_suite(tmp_path, 46), _APPROVED)


def test_unparseable_suite_raises(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals" / "fixture-suite"
    evals_dir.mkdir(parents=True)
    (evals_dir / "eval.yaml").write_text("config: [unclosed\n", encoding="utf-8")
    with pytest.raises(gate.DeclarationReadError, match="cannot be read as UTF-8 YAML"):
        gate.find_suite_violations(tmp_path / "evals", _APPROVED)


def test_non_utf8_suite_raises(tmp_path: pathlib.Path) -> None:
    """A suite that is not valid UTF-8 is a suite this gate cannot grade.
    `read_text` raises `UnicodeDecodeError`, which is a `ValueError` and not
    an `OSError`, so it needs its own handler or it escapes as an
    unhandled traceback instead of this module's typed error."""
    evals_dir = tmp_path / "evals" / "fixture-suite"
    evals_dir.mkdir(parents=True)
    (evals_dir / "eval.yaml").write_bytes(b"config:\n  model: \xff\xfe\n")
    with pytest.raises(gate.DeclarationReadError, match="cannot be read as UTF-8 YAML"):
        gate.find_suite_violations(tmp_path / "evals", _APPROVED)


def test_zero_discovered_suites_raises_rather_than_passing(tmp_path: pathlib.Path) -> None:
    """A gate that grades nothing must not report a clean tree. Confirmed
    live against an earlier revision of this module, which returned `[]` for
    both an empty and a nonexistent `evals/` directory."""
    empty = tmp_path / "evals"
    empty.mkdir()
    with pytest.raises(gate.DeclarationReadError, match=r"no \*/eval\.yaml found"):
        gate.find_suite_violations(empty, _APPROVED)
    with pytest.raises(gate.DeclarationReadError, match=r"no \*/eval\.yaml found"):
        gate.find_suite_violations(tmp_path / "does-not-exist", _APPROVED)


def test_non_utf8_workflow_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "waza-eval-matrix.yml"
    path.write_bytes(b"on:\n  workflow_dispatch: \xff\xfe\n")
    with pytest.raises(gate.DeclarationReadError, match="cannot be read as UTF-8 YAML"):
        gate._matrix_default_models(path)


# --- matrix workflow default ------------------------------------------------


def test_non_mapping_suite_raises(tmp_path: pathlib.Path) -> None:
    """A suite whose top level parses to something other than a mapping (an
    empty file yields `None`) has no `config` to reach -- it must raise, not
    be skipped past."""
    evals_dir = tmp_path / "evals" / "fixture-suite"
    evals_dir.mkdir(parents=True)
    (evals_dir / "eval.yaml").write_text("", encoding="utf-8")
    with pytest.raises(gate.DeclarationReadError, match="top level is NoneType"):
        gate.find_suite_violations(tmp_path / "evals", _APPROVED)


def test_approved_matrix_default_passes(tmp_path: pathlib.Path) -> None:
    assert gate.find_matrix_default_violations(_write_workflow(tmp_path), _APPROVED) == []


def test_non_mapping_workflow_raises(tmp_path: pathlib.Path) -> None:
    path = _write_workflow(tmp_path, "- not\n- a mapping\n")
    with pytest.raises(gate.DeclarationReadError, match="top level is not a mapping"):
        gate._matrix_default_models(path)


def test_matrix_default_that_is_not_a_string_raises(tmp_path: pathlib.Path) -> None:
    """`default:` written as a YAML sequence rather than the quoted JSON
    string `fromJSON()` expects."""
    path = _write_workflow(
        tmp_path, _MINIMAL_WORKFLOW.replace("default: '[\"fixture-model-1\"]'", "default:\n          - a")
    )
    with pytest.raises(gate.DeclarationReadError, match="declares no string default"):
        gate._matrix_default_models(path)


def test_matrix_default_that_is_valid_json_but_not_a_string_array_raises(tmp_path: pathlib.Path) -> None:
    """Valid JSON, wrong shape -- `fromJSON()` would hand the matrix a
    non-string element. Distinct from the unparseable-JSON case above."""
    path = _write_workflow(tmp_path, _MINIMAL_WORKFLOW.replace("'[\"fixture-model-1\"]'", "'[1, 2]'"))
    with pytest.raises(gate.DeclarationReadError, match="not a JSON array of strings"):
        gate._matrix_default_models(path)


def test_unapproved_matrix_default_is_reported(tmp_path: pathlib.Path) -> None:
    path = _write_workflow(tmp_path, _MINIMAL_WORKFLOW.replace("fixture-model-1", "claude-sonnet-4.6"))
    findings = gate.find_matrix_default_violations(path, _APPROVED)
    assert len(findings) == 1
    assert "retired 2026-06-15" in findings[0]


def test_every_entry_of_a_multi_model_default_is_graded(tmp_path: pathlib.Path) -> None:
    path = _write_workflow(
        tmp_path, _MINIMAL_WORKFLOW.replace('["fixture-model-1"]', '["fixture-model-1","nope-a","nope-b"]')
    )
    findings = gate.find_matrix_default_violations(path, _APPROVED)
    assert len(findings) == 2


def test_yaml_boolean_on_key_is_still_found(tmp_path: pathlib.Path) -> None:
    """`on:` resolves to the boolean True under YAML 1.1, so the lookup must
    accept both spellings or the whole surface silently goes ungraded."""
    assert yaml.safe_load(_MINIMAL_WORKFLOW).get("on") is None
    assert gate._matrix_default_models(_write_workflow(tmp_path)) == ["fixture-model-1"]


def test_non_json_matrix_default_raises(tmp_path: pathlib.Path) -> None:
    path = _write_workflow(tmp_path, _MINIMAL_WORKFLOW.replace("'[\"fixture-model-1\"]'", "fixture-model-1"))
    with pytest.raises(gate.DeclarationReadError, match="not the JSON array"):
        gate._matrix_default_models(path)


def test_missing_models_input_raises(tmp_path: pathlib.Path) -> None:
    path = _write_workflow(tmp_path, "name: fixture\non:\n  workflow_dispatch: {}\njobs: {}\n")
    with pytest.raises(gate.DeclarationReadError, match="no workflow_dispatch input named 'models'"):
        gate._matrix_default_models(path)


# --- allowlist integrity ----------------------------------------------------


def test_clean_allowlist_has_no_integrity_findings() -> None:
    assert gate.find_allowlist_integrity_violations() == []


def test_model_in_both_mappings_is_reported() -> None:
    findings = gate.find_allowlist_integrity_violations({"x": "evidence"}, {"x": "retired"})
    assert len(findings) == 1
    assert "both APPROVED_MODELS and RETIRED_MODELS" in findings[0]


def test_evidence_free_approval_is_reported() -> None:
    findings = gate.find_allowlist_integrity_violations({"x": "   "}, {})
    assert len(findings) == 1
    assert "carries no evidence" in findings[0]


# --- CLI --------------------------------------------------------------------


def test_main_reports_clean_tree(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "No unapproved declared model identifiers found." in capsys.readouterr().out


def test_main_exits_nonzero_on_a_finding(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate, "APPROVED_MODELS", {})
    assert gate.main([]) == 1
    assert "declared model allowlist:" in capsys.readouterr().out


def test_main_exits_nonzero_on_an_unreadable_declaration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "EVALS_DIR", REPO_ROOT / "does-not-exist")
    monkeypatch.setattr(gate, "MATRIX_WORKFLOW_PATH", REPO_ROOT / "does-not-exist.yml")
    assert gate.main([]) == 1
    assert "declared model allowlist:" in capsys.readouterr().out

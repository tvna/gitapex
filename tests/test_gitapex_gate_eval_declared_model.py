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


def test_approved_matrix_default_passes(tmp_path: pathlib.Path) -> None:
    assert gate.find_matrix_default_violations(_write_workflow(tmp_path), _APPROVED) == []


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

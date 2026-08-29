"""Tests for evals/scripts/gitapex_validate_eval_yaml.py (issue #527, derived
from retrospective issue #473).

Covers ``find_yaml_files`` (discovery), ``find_invalid_yaml_files`` (the
actual parse-or-not check, including the real #473 defeat shape -- an
unquoted scalar containing a colon), ``main()``'s CLI wrapper, and a final
real-repository sweep with no fixture override -- the same
"unit-test-the-layers, then self-validate against the real tree" pattern
``tests/test_gitapex_gate_skill_eval_yaml_parity.py`` already established
for its own sibling gate.
"""

from __future__ import annotations

import pathlib

import gitapex_validate_eval_yaml as validate_eval_yaml
import pytest


def _write_eval_yaml(evals_dir: pathlib.Path, skill: str, content: str = "name: x\n") -> pathlib.Path:
    skill_dir = evals_dir / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "eval.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _write_task_yaml(evals_dir: pathlib.Path, skill: str, name: str, content: str = "id: x\n") -> pathlib.Path:
    tasks_dir = evals_dir / skill / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / name
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# find_yaml_files
# ---------------------------------------------------------------------------


def test_find_yaml_files_discovers_eval_yaml_and_task_yaml(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    eval_yaml = _write_eval_yaml(evals_dir, "foo")
    task_yaml = _write_task_yaml(evals_dir, "foo", "normal.yaml")
    assert set(validate_eval_yaml.find_yaml_files(tmp_path)) == {eval_yaml, task_yaml}


def test_find_yaml_files_ignores_scripts_directory(tmp_path: pathlib.Path) -> None:
    # evals/scripts/ holds shared .py helpers, never its own eval.yaml or
    # tasks/ directory -- confirmed here rather than assumed, since a
    # future evals/scripts/*.py addition must never be mistaken for a
    # suite's own YAML.
    evals_dir = tmp_path / "evals"
    scripts_dir = evals_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "helper.py").write_text("", encoding="utf-8")
    assert validate_eval_yaml.find_yaml_files(tmp_path) == []


def test_find_yaml_files_missing_evals_dir_returns_empty_list(tmp_path: pathlib.Path) -> None:
    assert validate_eval_yaml.find_yaml_files(tmp_path / "nonexistent") == []


def test_find_yaml_files_is_sorted_and_deduped(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    _write_eval_yaml(evals_dir, "zeta")
    _write_eval_yaml(evals_dir, "alpha")
    found = validate_eval_yaml.find_yaml_files(tmp_path)
    assert found == sorted(found)
    assert len(found) == len(set(found))


# ---------------------------------------------------------------------------
# find_invalid_yaml_files
# ---------------------------------------------------------------------------


def test_all_valid_files_report_no_failures(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    _write_eval_yaml(evals_dir, "foo", "name: foo-eval\nmetrics:\n  - threshold: 0.8\n")
    _write_task_yaml(evals_dir, "foo", "normal.yaml", "id: normal\ninputs:\n  prompt: hi\n")
    assert validate_eval_yaml.find_invalid_yaml_files(tmp_path) == []


def test_unquoted_colon_scalar_is_reported_invalid(tmp_path: pathlib.Path) -> None:
    # The real issue #473 defeat shape: a plain (unquoted) scalar
    # containing "<text>: <text>" makes YAML read the colon as its own
    # mapping-value delimiter, breaking the whole file's parse --
    # "mapping values are not allowed in this context".
    evals_dir = tmp_path / "evals"
    broken = _write_eval_yaml(
        evals_dir,
        "vetting-attack-surface",
        "metrics:\n  - name: m\n    description: attack surface: OK\n",
    )
    failures = validate_eval_yaml.find_invalid_yaml_files(tmp_path)
    assert len(failures) == 1
    path, message = failures[0]
    assert path == broken
    assert "invalid YAML" in message
    assert str(broken) in message


def test_fixing_the_unquoted_scalar_makes_it_pass(tmp_path: pathlib.Path) -> None:
    # Same file, single-quoted this time (issue #473's own actual fix,
    # commit 82c127f) -- the other half of the issue's proof method:
    # "fix it and confirm it passes."
    evals_dir = tmp_path / "evals"
    _write_eval_yaml(
        evals_dir,
        "vetting-attack-surface",
        "metrics:\n  - name: m\n    description: 'attack surface: OK'\n",
    )
    assert validate_eval_yaml.find_invalid_yaml_files(tmp_path) == []


def test_non_mapping_yaml_is_not_flagged_syntax_only_scope(tmp_path: pathlib.Path) -> None:
    # This gate is syntax-only, never schema validation (issue #527's own
    # stated non-goal/residual risk) -- a file that parses cleanly to a
    # YAML list or scalar, rather than the expected mapping, is not this
    # check's concern.
    evals_dir = tmp_path / "evals"
    _write_eval_yaml(evals_dir, "foo", "- just\n- a\n- list\n")
    assert validate_eval_yaml.find_invalid_yaml_files(tmp_path) == []


def test_multiple_broken_files_are_all_reported_not_just_the_first(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    first = _write_eval_yaml(evals_dir, "foo", "description: broken: one\n")
    second = _write_task_yaml(evals_dir, "foo", "bad.yaml", "description: broken: two\n")
    failures = validate_eval_yaml.find_invalid_yaml_files(tmp_path)
    assert {path for path, _ in failures} == {first, second}


def test_non_utf8_file_is_reported_as_unreadable(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    skill_dir = evals_dir / "foo"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "eval.yaml"
    path.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    failures = validate_eval_yaml.find_invalid_yaml_files(tmp_path)
    assert len(failures) == 1
    found_path, message = failures[0]
    assert found_path == path
    assert "cannot read" in message


def test_unreadable_path_from_a_stale_listing_is_reported_not_raised(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Defeat case: find_yaml_files() and the actual read in
    # find_invalid_yaml_files() are two separate filesystem operations, so
    # a file deleted in between (or any other read failure) must surface
    # as a reported failure, never an uncaught OSError escaping this
    # function.
    missing = tmp_path / "evals" / "foo" / "eval.yaml"

    def fake_find_yaml_files(root: pathlib.Path) -> list[pathlib.Path]:
        return [missing]

    monkeypatch.setattr(validate_eval_yaml, "find_yaml_files", fake_find_yaml_files)
    failures = validate_eval_yaml.find_invalid_yaml_files(tmp_path)
    assert len(failures) == 1
    found_path, message = failures[0]
    assert found_path == missing
    assert "cannot read" in message


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_exits_0_when_nothing_invalid(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(validate_eval_yaml, "find_invalid_yaml_files", lambda: [])
    assert validate_eval_yaml.main(["prog"]) == 0
    assert capsys.readouterr().err == ""


def test_main_exits_1_and_reports_every_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failures = [
        (pathlib.Path("evals/foo/eval.yaml"), "invalid YAML in evals/foo/eval.yaml: boom"),
        (pathlib.Path("evals/foo/tasks/bad.yaml"), "invalid YAML in evals/foo/tasks/bad.yaml: boom2"),
    ]
    monkeypatch.setattr(validate_eval_yaml, "find_invalid_yaml_files", lambda: failures)
    rc = validate_eval_yaml.main(["prog"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "evals/foo/eval.yaml" in err
    assert "evals/foo/tasks/bad.yaml" in err
    assert "2 eval YAML file(s) failed to parse" in err


def test_main_exits_2_on_unexpected_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    rc = validate_eval_yaml.main(["prog", "unexpected-arg"])
    assert rc == 2
    assert "usage:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Real-repository self-validation (the gate itself)
# ---------------------------------------------------------------------------


def test_real_repository_eval_yaml_files_parse_cleanly() -> None:
    failures = validate_eval_yaml.find_invalid_yaml_files()
    assert failures == [], failures


def test_real_repository_sweep_finds_at_least_one_file() -> None:
    # Fail-closed guard (matches gitapex_gate_skill_eval_yaml_parity.py's
    # own min_expected_skill_names discovery-floor pattern): an empty
    # discovery result must never read as "everything passed" -- if the
    # glob ever silently stops matching anything (a moved evals/
    # directory, a typo'd pattern), this test catches it instead of the
    # sweep above vacuously passing on zero files.
    assert len(validate_eval_yaml.find_yaml_files()) > 0

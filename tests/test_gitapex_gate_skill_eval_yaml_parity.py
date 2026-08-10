"""Tests for the skill<->eval.yaml parity gate
(.github/scripts/gitapex_gate_skill_eval_yaml_parity.py).

Issue #928. The final test is the gate itself: every real skills/*/
directory in this repository must have a matching evals/*/eval.yaml, and
vice versa, discovered via directory listing rather than a hardcoded
skill list. The rest unit-test each layer with fixtures: discovery
(discover_skill_names, discover_eval_yaml_skill_names -- including that
evals/scripts/ never counts), the set-comparison itself
(find_parity_drift), the discovery-floor guard, and the CLI (main()) --
including the two adversarial defeat cases the branch plan's own T12
checklist requires: a case-sensitivity mismatch and a trailing-slash
input, both proving naive set-equality on raw, unnormalized names or
paths would silently pass where this gate must fail.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterable

import gitapex_gate_skill_eval_yaml_parity as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _make_skill(skills_dir: pathlib.Path, name: str) -> None:
    (skills_dir / name).mkdir(parents=True)


def _make_eval_yaml(evals_dir: pathlib.Path, name: str, content: str = "trials_per_task: 1\n") -> None:
    skill_evals_dir = evals_dir / name
    skill_evals_dir.mkdir(parents=True)
    (skill_evals_dir / "eval.yaml").write_text(content, encoding="utf-8")


def _populated_dirs(
    tmp_path: pathlib.Path, skill_names: Iterable[str], eval_yaml_names: Iterable[str]
) -> tuple[pathlib.Path, pathlib.Path]:
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    for name in skill_names:
        _make_skill(skills_dir, name)
    for name in eval_yaml_names:
        _make_eval_yaml(evals_dir, name)
    return skills_dir, evals_dir


# ---------------------------------------------------------------------------
# discover_skill_names / discover_eval_yaml_skill_names
# ---------------------------------------------------------------------------


def test_discover_skill_names_lists_immediate_subdirectories(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    _make_skill(skills_dir, "foo")
    _make_skill(skills_dir, "bar")
    (skills_dir / "not-a-dir.txt").write_text("stray file", encoding="utf-8")
    assert gate.discover_skill_names(skills_dir) == {"foo", "bar"}


def test_discover_skill_names_missing_dir_returns_empty_set() -> None:
    assert gate.discover_skill_names(pathlib.Path("/nonexistent/skills")) == set()


def test_discover_eval_yaml_skill_names_requires_eval_yaml_file(tmp_path: pathlib.Path) -> None:
    evals_dir = tmp_path / "evals"
    _make_eval_yaml(evals_dir, "foo")
    # A directory with no eval.yaml at all -- mirrors evals/scripts/, and
    # must never be counted as a skill's own eval suite.
    (evals_dir / "scripts").mkdir(parents=True)
    (evals_dir / "scripts" / "some_helper.py").write_text("", encoding="utf-8")
    assert gate.discover_eval_yaml_skill_names(evals_dir) == {"foo"}


def test_discover_eval_yaml_skill_names_missing_dir_returns_empty_set() -> None:
    assert gate.discover_eval_yaml_skill_names(pathlib.Path("/nonexistent/evals")) == set()


# ---------------------------------------------------------------------------
# find_parity_drift
# ---------------------------------------------------------------------------


def test_matching_sets_have_no_drift(tmp_path: pathlib.Path) -> None:
    names = [f"skill-{i}" for i in range(16)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, names, names)
    assert gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15) == []


def test_skill_missing_eval_yaml_is_reported(tmp_path: pathlib.Path) -> None:
    names = [f"skill-{i}" for i in range(15)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, [*names, "orphan-skill"], names)
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 1
    assert "orphan-skill" in findings[0]
    assert "has no matching" in findings[0]


def test_orphaned_eval_yaml_is_reported(tmp_path: pathlib.Path) -> None:
    names = [f"skill-{i}" for i in range(15)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, names, [*names, "orphan-eval"])
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 1
    assert "orphan-eval" in findings[0]
    assert "has no matching" in findings[0]


def test_both_directions_reported_together(tmp_path: pathlib.Path) -> None:
    names = [f"skill-{i}" for i in range(15)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, [*names, "skill-only"], [*names, "eval-only"])
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 2
    joined = "\n".join(findings)
    assert "skill-only" in joined
    assert "eval-only" in joined


def test_case_sensitivity_mismatch_is_real_drift(tmp_path: pathlib.Path) -> None:
    # Adversarial defeat case (branch plan T12 checklist): a naive
    # case-insensitive or case-folded comparison would treat 'Foo' and
    # 'foo' as the same skill and silently pass. This gate must not.
    names = [f"skill-{i}" for i in range(14)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, [*names, "Foo"], [*names, "foo"])
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 2
    joined = "\n".join(findings)
    assert "Foo" in joined
    assert "foo" in joined


def test_trailing_slash_in_input_paths_does_not_cause_a_false_mismatch(tmp_path: pathlib.Path) -> None:
    # Adversarial defeat case (branch plan T12 checklist): a naive
    # raw-path comparison could be fooled by (or falsely flag) a trailing
    # slash on one side. Both discovery functions key off pathlib
    # directory names, never a raw path string with or without a trailing
    # slash, so passing either directory path with or without a trailing
    # slash must produce identical results.
    names = [f"skill-{i}" for i in range(15)]
    skills_dir, evals_dir = _populated_dirs(tmp_path, names, names)
    without_slash = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    with_slash = gate.find_parity_drift(
        pathlib.Path(str(skills_dir) + "/"), pathlib.Path(str(evals_dir) + "/"), min_expected_skill_names=15
    )
    assert without_slash == with_slash == []


def test_below_min_expected_floor_fails_closed_not_vacuously(tmp_path: pathlib.Path) -> None:
    # issue #928 adversarial review pattern (same fail-closed rationale as
    # the split-fixture-coverage/transfer-check-disclosure gates' own
    # findings): a near-empty skills/ set trivially equals a near-empty
    # evals/ set, which must not read as "in parity."
    skills_dir, evals_dir = _populated_dirs(tmp_path, ["only-skill"], ["only-skill"])
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 1
    assert "discovery failure" in findings[0]


def test_completely_empty_dirs_fail_closed(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    evals_dir = tmp_path / "evals"
    skills_dir.mkdir()
    evals_dir.mkdir()
    findings = gate.find_parity_drift(skills_dir, evals_dir, min_expected_skill_names=15)
    assert len(findings) == 1
    assert "discovery failure" in findings[0]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_passes_when_in_parity(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_find_parity_drift() -> list[str]:
        return []

    monkeypatch.setattr(gate, "find_parity_drift", fake_find_parity_drift)
    assert gate.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_when_drift_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_find_parity_drift() -> list[str]:
        return ["skills/orphan has no matching evals/orphan/eval.yaml"]

    monkeypatch.setattr(gate, "find_parity_drift", fake_find_parity_drift)
    assert gate.main() == 1
    err = capsys.readouterr().out
    assert "orphan" in err


# ---------------------------------------------------------------------------
# Real-repository self-validation (the gate itself)
# ---------------------------------------------------------------------------


def test_real_repository_skills_and_eval_yaml_are_in_parity() -> None:
    findings = gate.find_parity_drift()
    assert findings == [], findings

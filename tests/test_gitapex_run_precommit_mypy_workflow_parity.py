"""Drift-check: gitapex_run_precommit_mypy.MYPY_GROUPS matches
.github/workflows/test.yml's own `mypy` job steps.

Issue #1013 row 5. `MYPY_GROUPS` (the local pre-commit hook's own group
list) and `test.yml`'s `mypy` job steps are two hardcoded copies of the
same directory-group list, kept in sync only "by convention" (module
docstring comment), with nothing catching a future edit to one that
forgets the other. Full workflow-step generation was considered and
rejected (see `gitapex_run_precommit_mypy.py`'s own docstring on why the
grouping -- 5 of 12 groups bundled together due to bare-import
collisions -- is not derivable from directory listing alone); this test
is the minimal fallback the issue's own Acceptance Criteria Map names:
"a drift-check gate comparing the two lists rather than full
unification."

Comparing tuples-of-tuples directly (not converting to sets at any point)
is deliberate: a plain `==` on ordered sequences already distinguishes a
missing group, an extra group, a reordered group, AND a duplicated group
(`("a", "a", "b") != ("a", "b")`), unlike a bare set comparison, which a
prior draft of this test used and which a duplicate would have silently
passed.
"""

from __future__ import annotations

import pathlib
import re

import gitapex_run_precommit_mypy
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_YML = REPO_ROOT / ".github" / "workflows" / "test.yml"

_MYPY_INVOCATION_RE = re.compile(r"mypy\s+--config-file\s+pyproject\.toml\s+(.*)", re.DOTALL)


def _extract_path_group(run: str) -> tuple[str, ...]:
    """The whitespace-separated trailing path arguments of one `mypy (...)`
    step's own `run:` block, with shell line-continuation backslashes
    resolved first (the first, combined-group step spans several `\\`-
    continued lines; every other step is a single line)."""
    normalized = run.replace("\\\n", " ")
    match = _MYPY_INVOCATION_RE.search(normalized)
    if match is None:
        raise AssertionError(f"no 'mypy --config-file pyproject.toml <paths>' invocation found in: {run!r}")
    return tuple(match.group(1).split())


def _mypy_step_groups_from_workflow_text(workflow_text: str) -> tuple[tuple[str, ...], ...]:
    """Every `mypy (...)`-named step's own path group, in document order,
    from a `test.yml`-shaped workflow YAML string."""
    workflow = yaml.safe_load(workflow_text)
    steps = workflow["jobs"]["mypy"]["steps"]
    mypy_steps = [step for step in steps if str(step.get("name", "")).startswith("mypy (")]
    return tuple(_extract_path_group(step["run"]) for step in mypy_steps)


def _declared_groups() -> tuple[tuple[str, ...], ...]:
    return tuple(dirs for _label, dirs in gitapex_run_precommit_mypy.MYPY_GROUPS)


# ---------------------------------------------------------------------------
# Positive: the real, committed files stay in sync
# ---------------------------------------------------------------------------


def test_test_yml_mypy_steps_match_mypy_groups() -> None:
    workflow_groups = _mypy_step_groups_from_workflow_text(TEST_YML.read_text(encoding="utf-8"))
    declared_groups = _declared_groups()
    assert workflow_groups == declared_groups, (
        f"test.yml's mypy job steps {workflow_groups!r} have drifted from "
        f"gitapex_run_precommit_mypy.MYPY_GROUPS {declared_groups!r} -- update both together"
    )


# ---------------------------------------------------------------------------
# Negative: prove the comparison actually detects drift, not just passes
# trivially on the already-in-sync real files above
# ---------------------------------------------------------------------------

_SYNTHETIC_WORKFLOW_TEMPLATE = """\
jobs:
  mypy:
    steps:
      - name: mypy (a)
        run: uv run --frozen mypy --config-file pyproject.toml a
      - name: mypy (b)
        run: uv run --frozen mypy --config-file pyproject.toml b
      - name: mypy (c)
        run: uv run --frozen mypy --config-file pyproject.toml c
"""


def test_missing_step_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gitapex_run_precommit_mypy, "MYPY_GROUPS", (("a", ("a",)), ("b", ("b",)), ("c", ("c",)), ("d", ("d",)))
    )
    workflow_groups = _mypy_step_groups_from_workflow_text(_SYNTHETIC_WORKFLOW_TEMPLATE)
    assert workflow_groups != _declared_groups()


def test_extra_step_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gitapex_run_precommit_mypy, "MYPY_GROUPS", (("a", ("a",)), ("b", ("b",))))
    workflow_groups = _mypy_step_groups_from_workflow_text(_SYNTHETIC_WORKFLOW_TEMPLATE)
    assert workflow_groups != _declared_groups()


def test_duplicated_step_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    # The case a bare set comparison would miss: two occurrences of the same
    # group collapse to one element in a set, so {"a", "b", "c"} ==
    # {"a", "a", "b", "c"} would wrongly report no drift. The tuple
    # comparison this test file uses throughout does not have that gap.
    monkeypatch.setattr(
        gitapex_run_precommit_mypy, "MYPY_GROUPS", (("a", ("a",)), ("a", ("a",)), ("b", ("b",)), ("c", ("c",)))
    )
    workflow_groups = _mypy_step_groups_from_workflow_text(_SYNTHETIC_WORKFLOW_TEMPLATE)
    assert workflow_groups != _declared_groups()


def test_reordered_step_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gitapex_run_precommit_mypy, "MYPY_GROUPS", (("c", ("c",)), ("b", ("b",)), ("a", ("a",))))
    workflow_groups = _mypy_step_groups_from_workflow_text(_SYNTHETIC_WORKFLOW_TEMPLATE)
    assert workflow_groups != _declared_groups()


def test_in_sync_case_reports_no_drift() -> None:
    # Confirms the synthetic fixture and the extraction/comparison logic
    # itself are sound -- when MYPY_GROUPS genuinely matches, the check
    # passes, not just when it happens to fail.
    matching_groups = (("a", ("a",)), ("b", ("b",)), ("c", ("c",)))
    workflow_groups = _mypy_step_groups_from_workflow_text(_SYNTHETIC_WORKFLOW_TEMPLATE)
    assert workflow_groups == tuple(dirs for _label, dirs in matching_groups)


# ---------------------------------------------------------------------------
# _extract_path_group's own multi-line/backslash-continuation handling
# ---------------------------------------------------------------------------


def test_extract_path_group_handles_backslash_continued_lines() -> None:
    run = "uv run --frozen mypy --config-file pyproject.toml \\\n  tests hooks \\\n  evals/scripts\n"
    assert _extract_path_group(run) == ("tests", "hooks", "evals/scripts")


def test_extract_path_group_handles_a_single_line() -> None:
    run = "uv run --frozen mypy --config-file pyproject.toml skills/foo/scripts"
    assert _extract_path_group(run) == ("skills/foo/scripts",)


def test_extract_path_group_raises_when_no_mypy_invocation_found() -> None:
    with pytest.raises(AssertionError, match=r"no 'mypy --config-file pyproject\.toml"):
        _extract_path_group("echo hello")

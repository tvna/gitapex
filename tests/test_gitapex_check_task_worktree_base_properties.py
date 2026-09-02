"""Hypothesis property-based layer for
``skills/executing-a-branch-plan/scripts/gitapex_check_task_worktree_base.py``'s
detection-logic call site (issue #1178's
``detection-logic-property-coverage`` gate; issue #1508 added this module
with zero property coverage of its own regex call site).

Resolves via ``import gitapex_check_task_worktree_base`` against
``skills/executing-a-branch-plan/scripts`` specifically (this repository's
own ``pyproject.toml`` ``pythonpath`` entry). The regular, thorough
example-based coverage for this module (every deny/allow/warn fixture,
including the real-git worktree-staleness repro) lives COLOCATED at
``skills/executing-a-branch-plan/scripts/test_gitapex_check_task_worktree_base.py``,
matching this skill's own established convention (see
``test_gitapex_check_task_bash_safety.py``'s identical colocated pairing
with its own source module). This file exists ONLY because
``gitapex_gate_detection_logic_property_coverage.py``'s own trigger scope
(``skills/*/scripts/gitapex_check_*.py``) requires a Hypothesis
``@given`` test specifically, and its own "is this covered" check
(``.gitapex/ssot.json``'s own ``detection-logic-property-coverage`` gate
entry) requires that test to live in this repository-wide top-level
``tests/test_<stem>_properties.py`` location, not colocated with the
source -- so the SAME module ends up with two test files, each covering a
genuinely different concern (behavioral correctness vs. this repo's own
regex-fuzzing discipline), not a duplicate of the other.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import gitapex_check_task_worktree_base as checker
import pytest
from conftest import FakeStdin as _FakeStdin
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=100, deadline=None)

CLASSIFIER = (
    pathlib.Path(__file__).parent.parent
    / "skills"
    / "executing-a-branch-plan"
    / "scripts"
    / "gitapex_check_task_worktree_base.py"
)

# A single-line, non-empty string -- ``_reflog_created_from``'s own regex
# is matched against one reflog line at a time (``line.strip()`` inside a
# ``splitlines()`` loop), so an embedded newline would change which LINE
# carries the "Created from" marker rather than exercising the capture
# group itself.
_SINGLE_LINE_TEXT = st.text(min_size=1, max_size=40).filter(
    lambda s: "\n" not in s and "\r" not in s and s.strip() != ""
)


@_PROPERTIES
@given(name=_SINGLE_LINE_TEXT)
def test_reflog_created_from_extracts_the_startpoint_name(name: str) -> None:
    """``_CREATED_FROM_RE``'s own capture group recovers exactly the
    startpoint text git wrote after ``"branch: Created from "``, for ANY
    single-line text -- the exact signal this module's whole shared-plan-
    branch-name resolution mechanism depends on (see
    ``gitapex_check_task_worktree_base.py``'s own module docstring). Runs
    against ``_reflog_created_from`` directly (with ``_run_git`` swapped
    for a plain lambda returning canned reflog text, restored in a
    ``finally``) rather than a real git repo per example: the STATELESS
    swap-and-restore below is safe to combine with ``@given`` even though
    a genuine pytest fixture object is not (Hypothesis's own
    ``function_scoped_fixture`` health check exists for exactly the
    stateful-fixture-per-example case this sidesteps)."""
    original_run_git = checker._run_git
    try:
        checker._run_git = lambda args, cwd: (0, f"branch: Created from {name}\n")
        result = checker._reflog_created_from("any-branch", pathlib.Path())
    finally:
        checker._run_git = original_run_git
    assert result == name.strip()


@pytest.fixture(scope="module")
def _fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """A minimal, real git repo with exactly one branch (``main``) and one
    commit -- built ONCE and reused READ-ONLY across every property
    example below. Module-scoped deliberately: Hypothesis's own documented
    fix for the ``function_scoped_fixture`` health check is a fixture with
    a wider scope, which is sound here specifically because nothing below
    ever mutates this repo -- every call is a read-only git plumbing
    command (``rev-parse``, ``symbolic-ref``) against fixed, already-
    committed state."""
    root = tmp_path_factory.mktemp("worktree-base-properties-fixture")
    subprocess.run(["git", "init", "-q", "--initial-branch", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "a.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "c1"], cwd=root, check=True)
    return root


@_PROPERTIES
@given(
    name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/", min_size=1, max_size=20).filter(
        lambda s: s != "main"
    )
)
def test_verify_local_branch_returns_none_for_an_unresolvable_name(name: str, _fixture_repo: pathlib.Path) -> None:
    """For ANY candidate name that does not name a real local branch in
    this fixture repo (only ``main`` exists), ``_verify_local_branch``
    returns None rather than resolving it as though it were a genuine
    branch -- the exact guard that keeps a foreign worktree's own reflog
    (naming a remote-tracking ref or a raw SHA) from being mistaken for
    the shared plan branch (see ``gitapex_check_task_worktree_base.py``'s
    own module docstring, "Why this resolution is deliberately narrow")."""
    assert checker._verify_local_branch(name, _fixture_repo) is None


def test_verify_local_branch_resolves_a_real_local_branch(_fixture_repo: pathlib.Path) -> None:
    sha = checker._verify_local_branch("main", _fixture_repo)
    assert sha is not None
    assert len(sha) == 40


def test_run_git_returns_stdout_and_zero_on_a_real_command(_fixture_repo: pathlib.Path) -> None:
    code, out = checker._run_git(["rev-parse", "HEAD"], _fixture_repo)
    assert code == 0
    assert len(out.strip()) == 40


def test_run_git_folds_a_missing_executable_into_a_nonzero_exit(tmp_path: pathlib.Path) -> None:
    code, out = checker._run_git(["--this-flag-does-not-exist-anywhere"], tmp_path)
    assert code != 0
    assert out == ""


def test_current_branch_returns_the_checked_out_branch_name(_fixture_repo: pathlib.Path) -> None:
    assert checker._current_branch(_fixture_repo) == "main"


def test_current_branch_returns_none_outside_any_git_repo(tmp_path: pathlib.Path) -> None:
    assert checker._current_branch(tmp_path) is None


def test_check_worktree_base_warns_when_not_a_linked_worktree(_fixture_repo: pathlib.Path) -> None:
    """``_fixture_repo`` is a plain, non-worktree repo -- its own branch
    has no ``"branch: Created from ..."`` reflog entry at all, so this
    must fail open (warn), never deny, matching the sequential-fallback
    contract ``check_worktree_base``'s own module docstring requires."""
    result = checker.check_worktree_base(_fixture_repo)
    assert result["decision"] == "warn"


def test_resolve_cwd_falls_back_to_process_cwd_when_payload_cwd_is_missing() -> None:
    assert checker._resolve_cwd({}) == pathlib.Path.cwd()


def _run_classifier(payload: dict[str, object], cwd: pathlib.Path) -> dict[str, object]:
    result = subprocess.run(
        ["python3", str(CLASSIFIER)],
        input=json.dumps(payload),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_main_allows_a_non_bash_tool_call(tmp_path: pathlib.Path) -> None:
    payload: dict[str, object] = {"tool_name": "Read", "tool_input": {}}
    assert _run_classifier(payload, tmp_path)["decision"] == "allow"


def test_main_reads_stdin_and_prints_a_decision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Calls ``main`` directly (in-process, via a monkeypatched
    ``sys.stdin``) rather than only through the subprocess-level
    ``_run_classifier`` above -- the same stdin-JSON entrypoint contract
    ``main``'s own module docstring describes."""
    payload = json.dumps({"tool_name": "Read"}).encode()
    monkeypatch.setattr(checker.sys, "stdin", _FakeStdin(payload))
    assert checker.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "allow"

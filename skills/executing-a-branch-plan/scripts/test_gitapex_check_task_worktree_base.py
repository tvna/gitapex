"""Regression suite for gitapex_check_task_worktree_base.py (issue #1508,
consolidated into issue #1566's own gate-preconditions-mechanism umbrella).

Two layers, mirroring test_gitapex_check_task_full_verification.py's own
split:

- **Fixture-step tests** call `check_worktree_base` directly against real
  git fixture repos built with `git init`/`git worktree add` under
  `tmp_path` (never a mocked git) -- exercising the actual deny/allow/warn
  decision logic, including the exact #1508 defect shape (a worktree
  forked from a now-stale base) and the false-positive class this
  module's own docstring discloses finding live during authoring (a
  worktree created from a remote-tracking ref, never mistaken for a
  genuine shared plan branch).
- **Wrapper-level tests** invoke the shipped
  `gitapex_check_task_worktree_base.py` itself via subprocess with the
  real PreToolUse JSON shape, for the JSON-contract-level paths (tool_name
  gating, malformed stdin, the `cwd` field) -- mirroring
  test_gitapex_check_task_bash_safety.py's own subprocess-invocation
  style for its sibling hook.

This file deliberately does NOT re-test check_task_bash_safety.sh's own
chaining of this classifier as a sibling call (that shell wrapper's own
pre-existing test_gitapex_check_task_bash_safety.py suite, unedited, is
what this task's own proof method re-runs to confirm no regression there
-- see this task's own dispatch prompt).
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import gitapex_check_task_worktree_base as under_test
import pytest

CLASSIFIER = pathlib.Path(__file__).parent / "gitapex_check_task_worktree_base.py"


def _run(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: pathlib.Path, *, branch: str = "shared-plan") -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "--initial-branch", branch], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    return root


def _commit(root: pathlib.Path, name: str, message: str) -> str:
    (root / name).write_text(f"{name}\n", encoding="utf-8")
    _run(["git", "add", "--", name], root)
    _run(["git", "commit", "-q", "-m", message], root)
    return _run(["git", "rev-parse", "HEAD"], root).stdout.strip()


def _worktree_add(
    main_root: pathlib.Path, worktree_path: pathlib.Path, *, new_branch: str, startpoint: str
) -> pathlib.Path:
    _run(["git", "worktree", "add", "-q", "-b", new_branch, str(worktree_path), startpoint], main_root)
    return worktree_path


# --------------------------------------------------------------------------
# check_worktree_base: fixture-step decision logic
# --------------------------------------------------------------------------


def test_deny_when_shared_branch_advanced_past_worktree_fork_point(tmp_path: pathlib.Path) -> None:
    """Direct regression pin for issue #1508's own defect shape: a task's
    worktree keeps working from a base the shared plan branch has since
    advanced past."""
    main_root = _init_repo(tmp_path / "main")
    fork_sha = _commit(main_root, "a.txt", "c1")
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="shared-plan")
    advanced_sha = _commit(main_root, "b.txt", "c2 advances shared-plan past wt's own fork point")

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "deny"
    reason = result["reason"]
    assert isinstance(reason, str)
    assert fork_sha in reason
    assert advanced_sha in reason
    assert "shared-plan" in reason


def test_allow_when_worktree_fork_point_matches_shared_tip(tmp_path: pathlib.Path) -> None:
    main_root = _init_repo(tmp_path / "main")
    tip_sha = _commit(main_root, "a.txt", "c1")
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="shared-plan")

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "allow"
    reason = result["reason"]
    assert isinstance(reason, str)
    assert tip_sha in reason


def test_allow_after_worktree_makes_its_own_commits(tmp_path: pathlib.Path) -> None:
    """A task's own ordinary Red-Green commits inside its worktree must
    never themselves trip this check -- only the SHARED branch advancing
    past the fork point should."""
    main_root = _init_repo(tmp_path / "main")
    tip_sha = _commit(main_root, "a.txt", "c1")
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="shared-plan")
    _commit(worktree, "task-work.txt", "task's own commit")

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "allow"
    reason = result["reason"]
    assert isinstance(reason, str)
    assert tip_sha in reason


def test_warn_when_not_a_linked_worktree(tmp_path: pathlib.Path) -> None:
    """The sequential-fallback case (no worktree, no wave) -- this backstop
    must never block it."""
    main_root = _init_repo(tmp_path / "main")
    _commit(main_root, "a.txt", "c1")

    result = under_test.check_worktree_base(main_root)

    assert result["decision"] == "warn"


def test_warn_when_worktree_head_is_detached(tmp_path: pathlib.Path) -> None:
    main_root = _init_repo(tmp_path / "main")
    _commit(main_root, "a.txt", "c1")
    worktree_path = tmp_path / "wt"
    _run(["git", "worktree", "add", "-q", "--detach", str(worktree_path), "shared-plan"], main_root)

    result = under_test.check_worktree_base(worktree_path)

    assert result["decision"] == "warn"


def test_warn_when_reflog_names_a_raw_sha_not_a_local_branch(tmp_path: pathlib.Path) -> None:
    main_root = _init_repo(tmp_path / "main")
    sha = _commit(main_root, "a.txt", "c1")
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint=sha)

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "warn"


def test_warn_when_worktree_created_from_a_remote_tracking_ref(tmp_path: pathlib.Path) -> None:
    """Regression pin for the exact false-positive class found live during
    this module's own authoring pass (see its module docstring): a
    worktree whose branch was created from a REMOTE-TRACKING ref (e.g.
    'origin/main') must never be mistaken for a genuine shared plan
    branch, since `refs/heads/origin/main` does not exist as a local
    branch."""
    origin = _init_repo(tmp_path / "origin", branch="main")
    _commit(origin, "a.txt", "c1")
    main_root = tmp_path / "main"
    _run(["git", "clone", "-q", str(origin), str(main_root)], tmp_path)
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="origin/main")

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "warn"


def test_stale_base_is_NOT_detected_when_the_worktree_was_created_from_a_remote_tracking_ref(
    tmp_path: pathlib.Path,
) -> None:
    """**Defeat case (step-8 adversarial review, issue #1566) -- pins a
    DISCLOSED STRUCTURAL LIMITATION, not a desired behavior.**

    This is issue #1508's own defect condition -- a task worktree forked
    from a base the shared plan branch has since advanced far past --
    reshaped to fall just outside this module's own reflog heuristic: the
    worktree's branch was created from `origin/main` (a remote-tracking
    ref) rather than from the shared plan branch by name. `_verify_local_branch`
    correctly refuses to resolve `refs/heads/origin/main`, so the whole
    resolution chain returns "cannot resolve" and this backstop fails
    OPEN -- while the stale base it exists to catch is genuinely,
    severely present.

    **This is not hypothetical.** It is the observed shape of a real
    `branch-plan-task` worktree in this repository: the step-8 review
    dispatch that wrote this test was itself handed a worktree whose own
    reflog read exactly `branch: Created from origin/main`, sitting at the
    branch's merge-base with every one of the plan branch's commits
    missing. The check did not fire, and the agent had to notice and
    `git reset --hard` by hand.

    The module's own docstring previously reasoned that a startpoint which
    is not a local branch signals an *unrelated* worktree ("essentially
    never a name that also happens to resolve to an existing local branch
    by coincidence"). The first half of that inference is sound; the
    conclusion drawn from it was not, because this skill's own dispatcher
    produces exactly that shape. Resolving it correctly needs the shared
    plan branch's name threaded in from the dispatching thread -- a
    design change this module explicitly does not make (see its own
    "Disclosed, unverified assumption" section) -- so it is disclosed
    there, in references/execution-and-dispatch.md, and in
    references/threat-model-and-authorization.md rather than papered over.

    Comparing against `origin/main` instead would NOT be a fix: `main` is
    not the shared plan branch, so it would deny every legitimately-based
    task worktree the moment `main` advanced -- precisely the "false,
    actively-blast-radius-widening DENY" this module's own docstring
    rejects that alternative for.

    If a future change makes this case DENY, that is a real improvement
    and this test should be rewritten to assert the deny -- it is pinned
    as `warn` so the limitation cannot be quietly *widened* or forgotten,
    not because `warn` is the good outcome.
    """
    origin = _init_repo(tmp_path / "origin", branch="main")
    _commit(origin, "a.txt", "c1")
    main_root = tmp_path / "main"
    _run(["git", "clone", "-q", str(origin), str(main_root)], tmp_path)
    # `git clone` does not carry over `origin`'s own local `user.*` config
    # (`_init_repo` sets it per-repo, not globally) -- this clone needs its
    # own identity before it can commit. Live-confirmed: this test passed
    # locally (an ambient global git identity papered over the gap) but
    # failed in CI with `git commit` exit 128 ("unable to auto-detect
    # email address") on a runner with no global identity configured.
    _run(["git", "config", "user.email", "test@example.com"], main_root)
    _run(["git", "config", "user.name", "Test"], main_root)

    # The shared plan branch, forked from main and then advanced -- the
    # real wave-dispatch shape this backstop is built for.
    _run(["git", "checkout", "-q", "-b", "shared-plan"], main_root)
    plan_tip = _commit(main_root, "plan-work.txt", "the plan branch advances")

    # The task worktree, created the way this repository's own dispatcher
    # actually creates one: from origin/main, NOT from shared-plan.
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="origin/main")

    # The stale base is genuinely present: shared-plan's tip is not an
    # ancestor of the worktree's HEAD, so a correctly-targeted check would
    # deny here.
    merge_base = _run(["git", "merge-base", "HEAD", "refs/heads/shared-plan"], worktree).stdout.strip()
    assert merge_base != plan_tip, "fixture no longer reproduces a stale base"

    result = under_test.check_worktree_base(worktree)

    assert result["decision"] == "warn", (
        "this defeat case is disclosed as a structural limitation; if it now "
        "resolves the shared plan branch and denies, update this test to assert deny"
    )
    reason = result["reason"]
    assert isinstance(reason, str)
    assert "origin/main" in reason
    assert "failing open" in reason


def test_warn_when_worktree_root_does_not_exist(tmp_path: pathlib.Path) -> None:
    """Every git call in this module fails the same way (non-zero exit) on
    a nonexistent cwd -- confirms the whole chain folds that into a single
    fail-open warn rather than raising."""
    result = under_test.check_worktree_base(tmp_path / "does-not-exist")

    assert result["decision"] == "warn"


# --------------------------------------------------------------------------
# main(): JSON-contract-level paths, via subprocess
# --------------------------------------------------------------------------


def _run_classifier(payload_text: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(CLASSIFIER)],
        input=payload_text,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_allow_when_tool_name_is_not_bash(tmp_path: pathlib.Path) -> None:
    result = _run_classifier(json.dumps({"tool_name": "Read", "tool_input": {}}), tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "allow"


def test_warn_on_malformed_json_stdin(tmp_path: pathlib.Path) -> None:
    result = _run_classifier("not valid json {{{", tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "warn"


def test_warn_on_non_object_json_stdin(tmp_path: pathlib.Path) -> None:
    result = _run_classifier(json.dumps([1, 2, 3]), tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "warn"


def test_allow_on_empty_stdin(tmp_path: pathlib.Path) -> None:
    result = _run_classifier("", tmp_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    # Empty stdin parses as `{}` -- `tool_name` is absent (None), which
    # fails the `== "Bash"` gate the same way an explicitly non-Bash
    # tool_name does, so this never even reaches the worktree-base check
    # itself. Matches gitapex_check_task_bash_safety.py's own identical
    # "no tool_name at all" -> allow behavior for its sibling hook.
    assert payload["decision"] == "allow"


def test_cwd_field_in_payload_is_honored_over_process_cwd(tmp_path: pathlib.Path) -> None:
    """The classifier is invoked with its OWN process cwd set to `tmp_path`
    (an unrelated, non-worktree directory) but the payload's own `cwd`
    field names the real fixture worktree -- confirms `_resolve_cwd`
    prefers the payload field, exactly matching
    gitapex_check_task_full_verification.py's own identical contract for
    the sibling SubagentStop hook."""
    main_root = _init_repo(tmp_path / "main")
    tip_sha = _commit(main_root, "a.txt", "c1")
    worktree = _worktree_add(main_root, tmp_path / "wt", new_branch="task1", startpoint="shared-plan")

    unrelated_cwd = tmp_path / "unrelated"
    unrelated_cwd.mkdir()
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}, "cwd": str(worktree)})

    result = _run_classifier(payload, unrelated_cwd)

    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "allow"
    assert tip_sha in decision["reason"]


@pytest.mark.parametrize("bad_cwd", ["", "/does/not/exist", 42])
def test_resolve_cwd_falls_back_on_a_bad_cwd_field(bad_cwd: object, tmp_path: pathlib.Path) -> None:
    assert under_test._resolve_cwd({"cwd": bad_cwd}) == pathlib.Path.cwd()

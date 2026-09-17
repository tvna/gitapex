"""Integration gate: issue #1987's own "index drift gate" (row 3).

`skills/evaluating-context-channel-maturity/scripts/test_gitapex_check_channel_shape.py`
proves the checks against synthetic fixtures; this runs the same
`gitapex_check_channel_shape.check_shape` over the repository's real
`AGENTS.md`, every real `agents/*.md`, and every real `.claude/agents/*.md`
file, so the checks -- including the three tool-boundary checks --
gate actual channel content in CI (the `test.yml` pytest run), not only
hand-built cases. Mirrors `tests/test_gitapex_repository_skill_shape.py`'s
own shape exactly, one checker module over one file-set instead of another.

Proof method (Branch Plan Task 4, inherited from row 3 and row 1's own
tool-boundary half): the real tree -- after Tasks 1-3 land -- passes every
check here, including all three tool-boundary checks, which FAIL against
`origin/main`'s pre-Task-1 state and PASS on this branch, proven both
directions below (`test_tool_boundary_checks_fail_before_task1_fix_and_pass_after`).
"""

from pathlib import Path

import gitapex_check_channel_shape as ccs
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_TARGETS = [
    REPO_ROOT / "AGENTS.md",
    *sorted((REPO_ROOT / "agents").glob("*.md")),
    *sorted((REPO_ROOT / ".claude" / "agents").glob("*.md")),
]


@pytest.mark.parametrize("target", _TARGETS, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_committed_channel_file_passes_shape(target: Path) -> None:
    failures = [r for r in ccs.check_shape(target) if not r.passed]
    assert not failures, "; ".join(f"{r.name}: {r.evidence}" for r in failures)


def test_tool_boundary_checks_fail_before_task1_fix_and_pass_after() -> None:
    """Issue #1987 row 1's own proof method: "FAIL against the current tree
    before the fix and PASS after, both directions demonstrated."

    The "before" state is no longer reachable on this branch's own working
    tree -- Task 1 already landed the fix -- so this reconstructs it rather
    than checking it out. `hooks/gitapex_sync_opencode.py`'s own git
    history on this checkout (`git log --oneline -- hooks/gitapex_sync_opencode.py`)
    shows commit `f7978454` ("fix(opencode-sync): close tool-boundary gap
    for branch-plan-task.md", Refs #1987) as Task 1's own fix commit; its
    parent, `b5336810`, is the pre-fix state. `git show
    b5336810:hooks/gitapex_sync_opencode.py` carries
    `("branch-plan-task.md", None)` in AGENT_SPECS at that commit -- no
    permission mapping at all, the exact gap Task 1's own commit message
    describes. `pre_fix_agent_specs` below is a frozen, hand-copied
    reconstruction of that one entry (not a live git read at test time --
    this test's own pass/fail must never depend on git history staying
    reachable), verified against that commit before being written here,
    per this task's own "reconstructing pre-fix history, not live
    repository content" instruction.

    The frontmatter side needs no reconstruction: `diff`-ing
    `.claude/agents/branch-plan-task.md` at commit `b5336810` (Task 3's
    own rewrite, already landed by the time Task 1's commit was made)
    against this checkout's own current copy of the same file is empty --
    Task 1 touched only `hooks/gitapex_sync_opencode.py`, never this
    file's own `disallowedTools: mcp__github` declaration. So the real,
    live file already carries the exact frontmatter the pre-fix state saw;
    only `AGENT_SPECS` needs reconstructing.

    This is a real regression-test shape, not merely re-testing Task 2's
    own already-existing synthetic-fixture unit tests: Task 2's own suite
    never reads this repository's real `.claude/agents/branch-plan-task.md`
    file, and never exercises the reconstructed pre-fix AGENT_SPECS
    against it.
    """
    target = REPO_ROOT / ".claude" / "agents" / "branch-plan-task.md"
    assert target.is_file(), target

    # Reconstruction of hooks/gitapex_sync_opencode.py's own AGENT_SPECS
    # entry for "branch-plan-task.md" as it read at commit b5336810 (the
    # parent of f7978454, Task 1's own fix commit) -- NOT live repository
    # content, and not re-derived by reading git history at test time.
    pre_fix_agent_specs = (("branch-plan-task.md", None),)

    pre_fix = {r.name: r for r in ccs.check_shape(target, agent_specs=pre_fix_agent_specs)}
    assert pre_fix["tool-boundary-declared"].passed, (
        "the Claude-side boundary (disallowedTools: mcp__github) was always declared in "
        f"{target} -- Task 1's own gap was the OpenCode-side mapping being None, never this "
        f"check: {pre_fix['tool-boundary-declared'].evidence}"
    )
    assert not pre_fix["tool-boundary-mapping-present"].passed, (
        f"expected the reconstructed pre-Task-1 AGENT_SPECS (None mapping) to fail "
        f"tool-boundary-mapping-present, got: {pre_fix['tool-boundary-mapping-present'].evidence}"
    )
    assert not pre_fix["tool-boundary-mapping-equivalent"].passed, (
        f"expected the reconstructed pre-Task-1 AGENT_SPECS (None mapping) to fail "
        f"tool-boundary-mapping-equivalent, got: {pre_fix['tool-boundary-mapping-equivalent'].evidence}"
    )

    # PASS direction: the real, current AGENT_SPECS -- loaded live from
    # this checkout's own hooks/gitapex_sync_opencode.py, not injected --
    # closes both gaps Task 1 fixed.
    post_fix = {r.name: r for r in ccs.check_shape(target)}
    for name in ("tool-boundary-declared", "tool-boundary-mapping-present", "tool-boundary-mapping-equivalent"):
        assert post_fix[name].passed, f"{name}: {post_fix[name].evidence}"

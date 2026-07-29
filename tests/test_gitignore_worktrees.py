"""Drift gate for the `.claude/worktrees/` gitignore invariant.

Agent-tool `isolation: worktree` dispatches create real git worktrees under
this path; they must never become stageable. If a future `.gitignore` edit
removes or weakens the pattern, this test fails instead of the invariant
silently decaying (see PR #322 review comment).
"""

from __future__ import annotations

from conftest import REPO_ROOT, assert_path_is_gitignored


def test_worktrees_path_is_gitignored() -> None:
    representative = REPO_ROOT / ".claude" / "worktrees" / "agent-driftgate-check"
    assert_path_is_gitignored(representative, "'.claude/worktrees/'")

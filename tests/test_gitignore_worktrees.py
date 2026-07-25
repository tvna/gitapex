"""Drift gate for the `.claude/worktrees/` gitignore invariant.

Agent-tool `isolation: worktree` dispatches create real git worktrees under
this path; they must never become stageable. If a future `.gitignore` edit
removes or weakens the pattern, this test fails instead of the invariant
silently decaying (see PR #322 review comment).
"""

from __future__ import annotations

import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_worktrees_path_is_gitignored() -> None:
    representative = REPO_ROOT / ".claude" / "worktrees" / "agent-driftgate-check"
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(representative)],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, (
        "'.claude/worktrees/' is no longer covered by .gitignore -- "
        "agent worktrees would become stageable content."
    )

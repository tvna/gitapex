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
        ["git", "check-ignore", "-v", str(representative)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "'.claude/worktrees/' is no longer covered by .gitignore -- "
        "agent worktrees would become stageable content."
    )
    # `-v` prefixes the match with its source file (e.g.
    # "<path>/.gitignore:20:/.claude/worktrees/\t..."). An ambient exclude
    # source outside this repository -- a global core.excludesFile, or
    # $GIT_DIR/info/exclude on a machine that happens to carry a matching
    # rule -- would also make the plain exit-code check above pass even
    # after this repository's own .gitignore rule was removed, silently
    # defeating the gate. Require the match to actually come from this
    # repository's own tracked .gitignore file.
    source = result.stdout.split(":", 1)[0]
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"'.claude/worktrees/' is ignored, but by {source!r} instead of "
        f"this repository's own {repo_gitignore} -- an ambient exclude "
        "source (global core.excludesFile, $GIT_DIR/info/exclude) is "
        "masking a possibly-removed repository rule."
    )

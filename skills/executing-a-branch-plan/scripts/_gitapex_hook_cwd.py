"""Shared hook-payload cwd resolution for this directory's checker scripts.

Both `gitapex_check_task_full_verification.py` (the SubagentStop hook) and
`gitapex_check_task_worktree_base.py` (the PreToolUse hook chained into
check_task_bash_safety.sh) need the exact same answer to "which directory
is this dispatched task's own worktree root": the hook payload's own `cwd`
field when it names a real directory (per Claude Code's documented hook
input schema for both hook events), this process's own working directory
otherwise -- matching the empirically-verified fallback
check_task_bash_safety.sh's own `${CLAUDE_PROJECT_DIR:-$(pwd)}` uses for
the PreToolUse hook (see references/threat-model-and-authorization.md).

Leading underscore, same convention as this directory's other
single-underscore "not a public entry point" names (`_gitapex_path_normalize.py`):
this module is a sibling import for the two checker scripts above, not
something invoked directly.
"""

from __future__ import annotations

from pathlib import Path


def resolve_cwd(payload: dict[str, object]) -> Path:
    """The hook payload's own `cwd` field when it names a real directory;
    this process's own working directory otherwise."""
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw:
        candidate = Path(raw)
        if candidate.is_dir():
            return candidate
    return Path.cwd()

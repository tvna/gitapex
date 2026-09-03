"""Drift gate for the `.claude/settings.local.json` gitignore invariant.

A per-session, per-user override (e.g. a `PATH`/`env` tweak needed to work
around a PATH-dependent PreToolUse hook, tracked as issue #1697) must
never become stageable -- it is personal to the machine/session that
created it, unlike the committed `.claude/settings.json`. If a future
`.gitignore` edit removes or weakens the pattern, this test fails instead
of the invariant silently decaying (see
tests/test_gitapex_gitignore_worktrees.py for the identical shape this
test follows).
"""

from __future__ import annotations

from conftest import REPO_ROOT, assert_path_is_gitignored


def test_settings_local_json_is_gitignored() -> None:
    representative = REPO_ROOT / ".claude" / "settings.local.json"
    assert_path_is_gitignored(representative, "'.claude/settings.local.json'")

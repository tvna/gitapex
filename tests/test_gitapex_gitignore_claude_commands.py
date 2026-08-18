"""Drift gate for the `/.claude/commands/` gitignore invariant (issue #1158).

`apm install` deploys vendored plugin commands under this path -- e.g.
cathrynlavery/diagram-design's export-diagram / import-drawio /
import-mermaid commands. Like `.claude/skills/`, they are reproducible from
apm.lock.yaml and must never become stageable. If a future `.gitignore`
edit removes or weakens the pattern, this test fails instead of the
invariant silently decaying.

It also satisfies
`.github/scripts/gitapex_gate_gitignore_pattern_coverage.py`'s requirement
that every pattern added to `.gitignore` in a diff be referenced,
literally, by some test under `tests/` (that gate's own module docstring,
issue #330). `_COMMANDS_PATTERN` below is the literal core-token anchor
that gate's search needs to find.
"""

from __future__ import annotations

from conftest import REPO_ROOT, assert_path_is_gitignored

# The exact pattern this test proves works -- also the literal anchor
# gitapex_gate_gitignore_pattern_coverage.py's core-token search needs so
# the pattern is not reported as untested when added to .gitignore.
_COMMANDS_PATTERN = "/.claude/commands/"


def test_apm_vendored_commands_are_gitignored() -> None:
    # Representative path under the apm-deployed commands subtree. The file
    # need not exist on disk: `git check-ignore` matches a path string
    # against `.gitignore` rules regardless of whether the file is present
    # (real in a dev checkout after `apm install`, absent in a fresh CI
    # checkout).
    assert_path_is_gitignored(
        REPO_ROOT / ".claude" / "commands" / "import-mermaid.md",
        f"{_COMMANDS_PATTERN!r} (apm-vendored diagram-design command)",
    )

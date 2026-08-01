#!/usr/bin/env python3
"""CI gate: hook commands must brace the plugin-root variable.

Issue #650. `hooks/hooks.json` shipped every command as
`"$CLAUDE_PLUGIN_ROOT/hooks/<script>"` -- the *unbraced* form. Verified live
against apm 0.25.0: apm's path substitution rewrites only the braced
`${CLAUDE_PLUGIN_ROOT}` form, so gitapex's commands were copied into a
consumer's `.claude/settings.json` verbatim, resolved to `/hooks/<script>`
(the variable is unset outside a plugin-installed session), and the hook
scripts were never deployed under `.claude/hooks/` at all. The install log
still reported `1 hook(s) integrated`, so every apm-installed consumer lost
all seven PreToolUse gates silently. The two third-party packages installed
alongside gitapex (`obra/superpowers`, `tvna/clairvoyance`) both author the
braced form and both deployed correctly, which is what isolated the cause.

The braced form is also the only form Claude Code's own plugin reference
uses in its examples, so this gate encodes the documented convention rather
than an apm-specific workaround: it stays correct even if apm later widens
its substitution.

Scope is deliberately narrow (CLAUDE.md section 4): only *hook command*
surfaces are read -- `hooks.json` manifests and the YAML frontmatter of
agent definitions, the two places this repository actually carries hook
commands. Prose that merely names the variable (for example
`skills/executing-a-branch-plan/references/threat-model-and-authorization.md`
discussing when it is unset) is not a violation and is never read.

Two misses are deliberate, both found by adversarially probing this gate
before it shipped rather than left to be discovered later:

- A hook command written into `.claude/settings.json` is not read. That
  file is gitignored here and is written by `apm install`, so scanning it
  would grade a third party's notation, not this repository's.
- A `"command"` whose value is a list rather than a string is not read. That
  is not a shape Claude Code documents, so such a hook would already be
  inert; the gate exists to protect hooks that would otherwise work.

A future hook mechanism carrying commands in some third shape would likewise
not be covered; that limit is stated in issue #650's Acceptance Criteria Map
rather than left implicit.

Standard library only, so the calling workflow needs no dependency install.

Run standalone (exit 1 on violation) or via the pytest gate in
`tests/test_gate_plugin_root_brace_notation.py`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections.abc import Iterator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_VARIABLE = "CLAUDE_PLUGIN_ROOT"

# Matches the unbraced `$CLAUDE_PLUGIN_ROOT` only: `${CLAUDE_PLUGIN_ROOT}`
# has `{` where this pattern requires `C`, so the braced form never matches.
# The trailing `\b` keeps a longer, unrelated variable name that merely
# starts with the same characters (`$CLAUDE_PLUGIN_ROOT_BACKUP`) from being
# reported as this variable used wrongly -- `_` is a word character, so the
# boundary does not fire there.
_UNBRACED_RE = re.compile(r"\$" + _VARIABLE + r"\b")

# Path segments that are not this repository's own source. `apm_modules/` is
# apm's package cache and `.claude/skills`, `.claude/hooks` are the trees
# `apm install` deploys into; all three can hold third-party `hooks.json`
# files whose notation this repository neither owns nor can fix. They are
# gitignored, so they only exist in a working tree where `apm install` has
# been run -- CI never sees them, but a contributor running this script
# locally would, and a third party's notation must not fail this repo's PR.
_EXCLUDED_PARTS = frozenset({".git", ".venv", "apm_modules", "node_modules"})
_EXCLUDED_PREFIXES = ((".claude", "skills"), (".claude", "hooks"))

# Agent definitions carry hook commands in YAML frontmatter rather than in a
# `hooks.json`; both locations are scanned because Claude Code loads agents
# from a plugin's `agents/` and a project's `.claude/agents/`. Recursive
# (`**`) rather than a flat `*`: an adversarial probe of an earlier revision
# of this gate showed a violating command in `agents/<sub>/a.md` slipping
# through a flat glob, and nothing stops an author from grouping agent
# definitions in subdirectories.
_AGENT_GLOBS = ("agents/**/*.md", ".claude/agents/**/*.md")


def commands_in_hook_manifest(data: object) -> Iterator[str]:
    """Yield every ``command`` string value anywhere in a parsed manifest.

    Walks the whole structure rather than a fixed path, so a command nested
    under any event name or matcher shape is read without this gate needing
    to track Claude Code's hook-event vocabulary.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                yield from commands_in_hook_manifest(value)
    elif isinstance(data, list):
        for item in data:
            yield from commands_in_hook_manifest(item)


def frontmatter(text: str) -> str:
    """Return the YAML frontmatter block of ``text``, or ``""`` when absent.

    Line-based rather than a substring search for ``\\n---`` so a horizontal
    rule of four or more dashes inside the block does not end it early. A
    leading BOM is stripped the same way this repository's other frontmatter
    readers do.
    """
    lines = text.lstrip("\ufeff").split("\n")
    if not lines or lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    return ""


def offending_lines(path: pathlib.Path) -> list[str]:
    """Return the offending command strings (or frontmatter lines) in ``path``.

    A `hooks.json` is parsed and only its ``command`` values are graded; any
    other file is treated as an agent definition and only its frontmatter is
    graded, so prose in the body is never read.
    """
    text = path.read_text(encoding="utf-8")
    if path.name == "hooks.json":
        try:
            manifest = json.loads(text)
        except json.JSONDecodeError as error:
            # A malformed manifest is a real failure, not something to pass
            # over: nothing downstream can tell whether it hides a violation.
            # Re-raised with the offending path attached so CI shows an
            # actionable message instead of a bare decoder traceback.
            raise ValueError(f"{path}: not valid JSON: {error}") from error
        candidates = commands_in_hook_manifest(manifest)
    else:
        candidates = (line.strip() for line in frontmatter(text).split("\n"))
    return [candidate for candidate in candidates if _UNBRACED_RE.search(candidate)]


def _is_excluded(path: pathlib.Path, root: pathlib.Path) -> bool:
    parts = path.relative_to(root).parts
    if _EXCLUDED_PARTS.intersection(parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in _EXCLUDED_PREFIXES)


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    """Return every hook-command surface under ``root``, sorted and deduped."""
    found = {p for p in root.rglob("hooks.json") if not _is_excluded(p, root)}
    for pattern in _AGENT_GLOBS:
        found.update(p for p in root.glob(pattern) if not _is_excluded(p, root))
    return sorted(found)


def find_violations(root: pathlib.Path) -> list[tuple[str, str]]:
    """Return ``(relative path, offending text)`` for every violation."""
    violations = []
    for path in discover(root):
        for offender in offending_lines(path):
            violations.append((str(path.relative_to(root)), offender))
    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 1 if any hook command uses the unbraced variable form."""
    parser = argparse.ArgumentParser(
        description="Check that hook commands reference the plugin root as "
        "${CLAUDE_PLUGIN_ROOT}, not $CLAUDE_PLUGIN_ROOT."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        violations = find_violations(args.root)
    except ValueError as error:
        print(f"{error}", file=sys.stderr)
        return 1
    if violations:
        for path, offender in violations:
            print(
                f"{path}: hook command uses ${_VARIABLE} (unbraced): {offender}",
                file=sys.stderr,
            )
        print(
            f"\n{len(violations)} hook command(s) use the unbraced "
            f"${_VARIABLE}. apm substitutes only the braced "
            f"${{{_VARIABLE}}} form, so an apm-installed consumer would "
            "receive a command that cannot resolve, with no error at "
            "install time. Use the braced form (refs #650).",
            file=sys.stderr,
        )
        return 1

    surfaces = len(discover(args.root))
    print(f"OK: {surfaces} hook-command surface(s) brace ${_VARIABLE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

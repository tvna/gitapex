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
values are graded -- `command` entries in a `hooks.json` manifest and
`command:` keys in an agent definition's YAML frontmatter, the two places
this repository carries hook commands. Prose naming the variable is never
graded, in a body or in a frontmatter `description:` alike.

Discovery asks git for tracked files rather than walking the filesystem
behind a denylist. That is not a style preference: a filesystem walk made
every gitignored path a false-positive candidate, and an earlier revision's
denylist demonstrably missed two of them -- `.claude/worktrees/<task>/`
(a full checkout of another commit, which still carries the unbraced form
this gate was written to remove) and any `.claude/hooks|skills` apm deploy
tree nested below the scan root. The tracked-file set is exactly "this
repository's own source," so both classes, and any future ignored
directory, are excluded by construction. `tests/conftest.py` already shells
out to git for this same class of question.

One shape is still deliberately not graded: a `command` whose value is a
list rather than a string. Claude Code documents `command` as a string, so
such a hook would already be inert, and this gate exists to protect hooks
that would otherwise work.

Standard library only, so the calling workflow needs no dependency install.

Exit codes: 0 clean, 1 violation found, 2 the scan could not be trusted
(no surfaces discovered, an unreadable or malformed file). The 2 case
mirrors `gate_evals_scripts_coverage.py`'s own rule that an empty match set
is an error, never a silent pass -- otherwise a renamed `hooks.json` turns
this gate into a permanent green no-op nobody notices.

Run standalone or via the pytest gate in
`tests/test_gate_plugin_root_brace_notation.py`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Iterator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_VARIABLE = "CLAUDE_PLUGIN_ROOT"
_BRACED = "${" + _VARIABLE + "}"

# Matches the unbraced `$CLAUDE_PLUGIN_ROOT` only: `${CLAUDE_PLUGIN_ROOT}`
# has `{` where this pattern requires `C`, so the braced form never matches.
# The trailing `\b` keeps a longer, unrelated variable name that merely
# starts with the same characters (`$CLAUDE_PLUGIN_ROOT_BACKUP`) from being
# reported as this variable used wrongly -- `_` is a word character, so the
# boundary does not fire there.
_UNBRACED_RE = re.compile(r"\$" + _VARIABLE + r"\b")

# A frontmatter hook command, as `command: <value>` or `- command: <value>`.
# Anything else in the block (`description:`, `name:`, prose) is not a
# command and is never graded.
_FRONTMATTER_COMMAND_RE = re.compile(r"^[ \t]*(?:-[ \t]*)?command[ \t]*:[ \t]*(\S.*)$")

# git pathspec `*` crosses `/` (verified against this repository: a
# `skills/*.md` pathspec matches `skills/<skill>/references/<file>.md`), so
# these four patterns cover a manifest or agent definition at any depth.
_PATHSPECS = ("hooks.json", "*/hooks.json", "agents/*.md", ".claude/agents/*.md")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


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


def frontmatter(text: str) -> str | None:
    """Return the YAML frontmatter block, ``""`` when there is none, or
    ``None`` when a block opens but never closes.

    The three-way return is what lets the caller fail closed on a malformed
    block while still accepting a plain Markdown file that legitimately has
    no frontmatter -- the same distinction
    `.github/scripts/skill_security_relevance.py` draws for the same reason.
    Line-based rather than a substring search for ``\\n---`` so a horizontal
    rule of four or more dashes inside the block does not end it early.
    """
    lines = text.lstrip("\ufeff").split("\n")
    if lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    return None


def hook_commands(path: pathlib.Path) -> list[str]:
    """Return every hook command declared in ``path``.

    Raises ``ScanError`` rather than returning an empty list when the file
    cannot be read or parsed: nothing downstream can tell whether an
    unreadable file hides a violation.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error

    if path.name == "hooks.json":
        try:
            manifest = json.loads(text)
        except json.JSONDecodeError as error:
            raise ScanError(f"{path}: not valid JSON: {error}") from error
        return list(commands_in_hook_manifest(manifest))

    block = frontmatter(text)
    if block is None:
        raise ScanError(f"{path}: frontmatter block opens but never closes")
    return [
        match.group(1).strip()
        for match in (_FRONTMATTER_COMMAND_RE.match(line) for line in block.split("\n"))
        if match
    ]


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    """Return every repository-tracked hook-command surface under ``root``."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git`
        # is intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine).
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "ls-files", "-z", "--", *_PATHSPECS],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:  # git missing entirely
        raise ScanError(f"cannot run git to list tracked files: {error}") from error
    if result.returncode != 0:
        raise ScanError(f"{root}: git ls-files failed: {result.stderr.strip()}")
    return sorted(root / name for name in result.stdout.split("\0") if name)


def find_violations(root: pathlib.Path) -> list[tuple[str, str]]:
    """Return ``(relative path, offending command)`` for every violation."""
    return violations_in(discover(root), root)


def violations_in(paths: list[pathlib.Path], root: pathlib.Path) -> list[tuple[str, str]]:
    """Grade already-discovered ``paths``, so a caller that also needs the
    path list does not walk for it twice."""
    violations = []
    for path in paths:
        for command in hook_commands(path):
            if _UNBRACED_RE.search(command):
                violations.append((str(path.relative_to(root)), command))
    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation found, 2 the scan could not be trusted."""
    parser = argparse.ArgumentParser(
        description=f"Check that hook commands reference the plugin root as "
        f"{_BRACED}, not ${_VARIABLE}."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        paths = discover(args.root)
        if not paths:
            raise ScanError(
                f"{args.root}: no tracked hook-command surface matched "
                f"{list(_PATHSPECS)}. An empty match set most plausibly means "
                "the scan ran against the wrong root, or a manifest was "
                "renamed -- either way this gate would otherwise pass while "
                "checking nothing."
            )
        violations = violations_in(paths, args.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    if violations:
        for path, command in violations:
            print(
                f"{path}: hook command uses ${_VARIABLE} (unbraced): {command}",
                file=sys.stderr,
            )
        print(
            f"\n{len(violations)} hook command(s) use the unbraced "
            f"${_VARIABLE}. apm substitutes only the braced {_BRACED} form, "
            "so an apm-installed consumer would receive a command that "
            "cannot resolve, with no error at install time. Use the braced "
            "form (refs #650).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(paths)} hook-command surface(s) brace {_BRACED}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

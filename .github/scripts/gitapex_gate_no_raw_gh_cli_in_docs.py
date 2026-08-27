#!/usr/bin/env python3
"""CI gate: no fenced code block in docs/**/*.md may carry a literal raw
`gh <subcommand>` CLI invocation, unless an explicit exception marker
immediately precedes the fence.

Issue #529 (refs #205 Repairs 5 & 8): PR #204's own implementation plan
instructed a raw `gh pr view` CLI invocation, contradicting CLAUDE.md's
"Do not invoke command-line GitHub tools directly." The violation was
caught only by two rounds of manual self-review -- a follow-up carve-out
reintroducing the same violation was caught only on the second pass. No
lint checked documentation/plan files for this pattern before now.

Scope: every tracked `*.md` file under `docs/` (this repo's tracked
plan/spec/report corpus), discovered via `git ls-files -- docs` -- matching
gitapex_gate_hidden_characters.py's own tracked-file rationale (an untracked
scratch file or an ignored worktree checkout is out of scope by
construction). Stated as `docs/**/*.md` elsewhere in this module for
readability, but that is loose shorthand, not the literal git pathspec used:
git's own pathspec matching requires `**` to span at least one directory
segment, so a literal `docs/**/*.md` pathspec would NOT match a file
directly under `docs/` (e.g. `docs/glossary.md`) -- the same pitfall
`provenance-disclosure-gate.yml` and `retro-title-convention-citation-gate.yml`
both name and avoid by listing `docs/*.md` and `docs/**/*.md` explicitly.
This gate's own `discover()` avoids it a different way, by passing the bare
directory `docs` as the pathspec rather than a glob, so both a top-level and
a nested `docs/*.md` file are included; `.gitapex/ssot.json`'s own
`target[].ref` for this gate is `docs/**/*.md`, which is this same loose
shorthand, not a literal pathspec any code evaluates.

Detection is fence-scoped and subcommand-scoped, not a bare "gh " string
match, per this issue's own stated residual risk: a plain substring match
on "gh " would false-flag ordinary prose ("through") and a single-backtick
inline code span that merely *discusses* the CLI without instructing its
use (four such spans exist in this repository's own docs today, none
inside a fenced block -- verified directly, not assumed, at authoring
time). So:

  1. Only text inside a fenced code block (``` or ~~~) is scanned at all --
     a fence-scoped line scan run in the opposite direction from
     `hooks/gitapex_check_acm_present_or_waiver.py`'s own (that check
     strips fences to find text *outside* them; this one keeps only text
     *inside* them), but with stricter pairing than that sibling's plain
     `startswith` fence toggle, which this gate's own audit found wrong.
     Fence pairing follows CommonMark's own run-length rule: a fence closes
     only on a line that is nothing but a run of the SAME marker character
     at least as long as the opening run. A plain `startswith("```")`
     toggle instead closed a four-backtick fence on the first three-backtick
     line inside it, so every line of a nested ```` ```markdown ```` example
     block -- a shape this repository's own
     docs/superpowers/plans/2026-07-13-evaluating-skill-quality-shape-script.md
     already carries -- fell outside every computed range and was never
     scanned (audit of issue #529's own gate, confirmed live against that
     file). An unclosed fence extends to end-of-file, matching how GitHub's
     own renderer treats it.
  2. Within a fenced block, only a `gh` token in command-start position --
     `gh` not preceded by a word character or a hyphen -- followed by one
     of gh CLI's real top-level subcommands counts as an invocation. The
     negative lookbehind rejects a word-internal match ("through pr")
     while still accepting every real command-start position, including
     ones an enumerated opener character class silently missed: a quoted
     invocation (`bash -lc "gh pr merge 1"`, a JSON `"command": "gh issue
     close 42"`) and a path-prefixed one (`/usr/bin/gh pr merge 1`).
     Quote-splitting is the same bypass class
     `hooks/gitapex_check_bash_safety.py` was already live-confirmed
     vulnerable to (issue #1326) before it moved off raw-text matching.
     The subcommand vocabulary is fixed and explicit (`_GH_SUBCOMMANDS`),
     the same never-grow-it-ad-hoc discipline `_HIDDEN_CHARACTERS` uses in
     the hidden-characters gate -- this closes the false positive a bare
     `gh\\s+\\S` match would produce on `for t in uv gh actionlint bun
     lychee` (a real line in this repository's own
     docs/superpowers/plans/2026-07-14-toolchain-foundation.md): `actionlint`
     is not a gh subcommand, so `gh actionlint` here is correctly not an
     invocation.

Known gaps, disclosed rather than claimed closed: an indented (four-space)
code block is not a fenced block and is not scanned; an invocation split
across a shell line continuation (`gh \\` then `pr create` on the next
line) is not matched, since detection is per-line; only the first
invocation on a given line is reported (the line still fails the gate);
CommonMark's own <=3-space cap on fence-marker indentation is not
modelled, because a flat line scanner cannot see the container
indentation a fence nested in a list item legitimately carries -- a
marker line is treated as a fence marker at any indentation, on both the
opening and the closing side; and a fence inside a blockquote (a `>`
prefix on the marker line, e.g. a blockquoted fenced code block) is not
recognized as a fence marker at all, since `_FENCE_OPEN_RE`/
`_FENCE_CLOSE_RE` match only a bare run of the marker character after
stripping whitespace, not a blockquote's own leading `>`.

Exception marker: an explicit `<!-- gitapex-allow-raw-gh-cli: <reason> -->`
line directly on the line immediately preceding the fence's opening
marker (no blank line in between) exempts that one fenced block -- the
same strict, regex-anchored, non-empty-reason-required inline marker
style `hooks/gitapex_check_acm_present_or_waiver.py`'s ACM waiver already
uses in this repository, not a bare `noqa`-style flag.

Historical grandfathering: docs/superpowers/plans/2026-07-14-toolchain-foundation.md
(predates this gate, and CLAUDE.md's rule pre-existed it too) carries 3 real
fenced blocks with 4 real `gh run`/`gh pr create` invocations between them,
each block given the exception marker in the same change that adds this
gate -- not silently exempted by path.

Exit codes: 0 clean, 1 violation(s) found, 2 the scan could not be trusted
(no docs/**/*.md files discovered, or a file could not be read/decoded as
UTF-8) -- the same 0/1/2 split gitapex_gate_hidden_characters.py uses.

Run via `uv run` (needed for the pydantic import) or via the pytest gate in
tests/test_gitapex_gate_no_raw_gh_cli_in_docs.py.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# A fence opens on a run of >= 3 of the same marker character (an info
# string may follow) and closes only on a line that is nothing but a run of
# that same character, at least as long -- CommonMark's own rule. Anything
# looser closes a four-backtick fence on the three-backtick fence nested
# inside it and silently stops scanning the nested block; see this module's
# own docstring.
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^(`{3,}|~{3,})$")

# gh CLI's real top-level commands, fixed and explicit -- never grown ad
# hoc, the same discipline `_HIDDEN_CHARACTERS` uses in
# gitapex_gate_hidden_characters.py. Re-sourced from gh's own published
# manual (https://cli.github.com/manual/, fetched during the audit of this
# gate) rather than from memory: that pass found `agent-task`, `copilot`,
# `discussion`, `licenses`, `skill` and `help` already shipping and absent
# here, so a documented `gh discussion create` in a fenced block passed the
# gate silently. The two documented single-word aliases (`gh cs` for
# codespace, `gh skills` for skill) are included for the same reason. A gh
# CLI command added after this list was last re-sourced remains a
# documented residual risk, not a silently claimed completeness.
_GH_SUBCOMMANDS = frozenset(
    {
        "agent-task",
        "browse",
        "codespace",
        "copilot",
        "cs",
        "discussion",
        "gist",
        "issue",
        "org",
        "pr",
        "project",
        "release",
        "repo",
        "ruleset",
        "cache",
        "run",
        "workflow",
        "alias",
        "api",
        "attestation",
        "auth",
        "completion",
        "config",
        "extension",
        "gpg-key",
        "help",
        "label",
        "licenses",
        "preview",
        "search",
        "secret",
        "skill",
        "skills",
        "ssh-key",
        "status",
        "variable",
    }
)

# The command-start position is asserted by a zero-width negative
# lookbehind rather than an enumerated opener character class, so
# `match.group(1)` is the invocation itself (`gh run`) and no real opener
# has to be remembered: a quote (`bash -lc "gh pr merge 1"`), a path
# separator (`/usr/bin/gh pr merge 1`) and a command-substitution `(` all
# qualify, while a word-internal "gh" ("through pr", "high pr") does not.
_RAW_GH_INVOCATION_RE = re.compile(
    r"(?<![\w-])(gh\s+(?:" + "|".join(re.escape(s) for s in sorted(_GH_SUBCOMMANDS)) + r"))\b"
)

_ALLOW_MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*gitapex-allow-raw-gh-cli[ \t]*:[ \t]*\S.*-->[ \t]*$")


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    matched: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: raw gh CLI invocation `{self.matched}` inside a fenced code block"


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    """Return every repository-tracked `docs/**/*.md` file under `root`."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- same rationale as
        # gitapex_gate_hidden_characters.py's own discover().
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "ls-files", "-z", "--", "docs"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:  # git missing entirely
        raise ScanError(f"cannot run git to list tracked files: {error}") from error
    if result.returncode != 0:
        raise ScanError(f"{root}: git ls-files failed: {result.stderr.strip()}")
    return sorted(root / name for name in result.stdout.split("\0") if name and name.endswith(".md"))


def _fenced_line_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Return `(open_marker_line, scan_end_line)` pairs, 1-indexed, for each
    fenced block in `lines`. `scan_end_line` is an *exclusive* scan
    boundary -- the caller scans `open_marker_line + 1` through
    `scan_end_line - 1` -- not necessarily a marker line itself: for a
    closed fence it is the closing marker's own line (correctly excluded
    from the scan), but for an unclosed fence it is `len(lines) + 1`, one
    past the last real line, so that last line -- content, not a marker --
    is still scanned. Using `len(lines)` there instead was a real bug: it
    silently dropped a file's final line from every scan whenever that
    line closed an unclosed fence and the file had no trailing newline
    (`text.split("\\n")` only pads a synthetic empty final element when the
    text *does* end in one). Found by adversarial review of this gate,
    confirmed by execution, not merely reasoned about, before this fix
    landed.

    A fence closes only on a bare run of the same marker character at
    least as long as the opening run (CommonMark's rule), so a
    three-backtick fence nested inside a four-backtick one does not end
    the outer block. An unclosed fence's scan boundary extends to
    end-of-file, matching how GitHub's own renderer treats it.
    """
    ranges: list[tuple[int, int]] = []
    open_run: str | None = None
    open_line = 0  # only meaningful while open_run is not None
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if open_run is None:
            opening = _FENCE_OPEN_RE.match(stripped)
            if opening:
                open_run = opening.group(1)
                open_line = i
            continue
        closing = _FENCE_CLOSE_RE.match(stripped)
        if closing and closing.group(1)[0] == open_run[0] and len(closing.group(1)) >= len(open_run):
            ranges.append((open_line, i))
            open_run = None
    if open_run is not None:
        ranges.append((open_line, len(lines) + 1))
    return ranges


def _has_allow_marker(lines: list[str], open_line: int) -> bool:
    """True iff the line directly preceding the fence's opening marker
    (1-indexed `open_line`, no blank line in between) is a valid exception
    marker."""
    if open_line < 2:
        return False
    return bool(_ALLOW_MARKER_RE.match(lines[open_line - 2]))


def violations_in_text(text: str) -> list[tuple[int, str]]:
    """Return `(line, matched_invocation)` for every raw gh CLI invocation
    found inside a fenced code block in `text`, 1-indexed, skipping any
    fence whose opening marker is directly preceded by a valid exception
    marker line."""
    lines = text.split("\n")
    found: list[tuple[int, str]] = []
    for open_line, close_line in _fenced_line_ranges(lines):
        if _has_allow_marker(lines, open_line):
            continue
        for lineno in range(open_line + 1, close_line):
            match = _RAW_GH_INVOCATION_RE.search(lines[lineno - 1])
            if match:
                found.append((lineno, match.group(1)))
    return found


def violations_in_file(path: pathlib.Path, root: pathlib.Path) -> list[Violation]:
    """Return every raw-gh-CLI-invocation violation in `path`.

    Raises `ScanError` rather than skipping the file when it cannot be read
    or decoded as UTF-8: nothing downstream can tell whether an unreadable
    file hides a violation.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
    relative = str(path.relative_to(root))
    return [Violation(path=relative, line=line, matched=matched) for line, matched in violations_in_text(text)]


def find_violations(root: pathlib.Path) -> list[Violation]:
    """Scan every tracked `docs/**/*.md` file under `root` and return all
    violations."""
    return violations_in(discover(root), root)


def violations_in(paths: list[pathlib.Path], root: pathlib.Path) -> list[Violation]:
    """Grade already-discovered `paths`, so a caller that also needs the
    path list does not walk for it twice."""
    violations: list[Violation] = []
    for path in paths:
        violations.extend(violations_in_file(path, root))
    return violations


class GateNoRawGhCliInDocsArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. `root` must be an
    existing directory -- every existing caller already passes one, so this
    only gives a --root pointing nowhere a clear, early error instead of
    the deeper "git ls-files failed" ScanError it would otherwise surface."""

    root: pathlib.Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 clean, 1 violation(s) found, 2 the scan could not be trusted."""
    parser = argparse.ArgumentParser(
        description="Check that no fenced code block in docs/**/*.md carries a "
        "literal raw `gh <subcommand>` CLI invocation."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateNoRawGhCliInDocsArgs(root=args.root)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    try:
        paths = discover(validated.root)
        if not paths:
            raise ScanError(
                f"{validated.root}: no tracked docs/**/*.md files found. An empty "
                "match set most plausibly means the scan ran against the wrong "
                "root -- either way this gate would otherwise pass while "
                "checking nothing."
            )
        violations = violations_in(paths, validated.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    if violations:
        for violation in violations:
            print(violation.describe(), file=sys.stderr)
        print(
            f"\n{len(violations)} raw gh CLI invocation(s) found in fenced doc code "
            "blocks. Use a platform-integrated tool call instead (CLAUDE.md: "
            '"Do not invoke command-line GitHub tools directly."), or if the '
            "invocation is illustrative prose rather than an instruction to run, "
            "add `<!-- gitapex-allow-raw-gh-cli: <reason> -->` on the line "
            "directly above the fence (issue #529, refs #205 Repairs 5 & 8).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(paths)} tracked docs/**/*.md file(s) carry no raw gh CLI invocations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

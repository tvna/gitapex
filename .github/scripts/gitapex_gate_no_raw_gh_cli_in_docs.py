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

Scope: docs/**/*.md only (this repo's tracked plan/spec/report corpus),
discovered via `git ls-files` -- matching gitapex_gate_hidden_characters.py's
own tracked-file rationale (an untracked scratch file or an ignored
worktree checkout is out of scope by construction).

Detection is fence-scoped and subcommand-scoped, not a bare "gh " string
match, per this issue's own stated residual risk: a plain substring match
on "gh " would false-flag ordinary prose ("through") and a single-backtick
inline code span that merely *discusses* the CLI without instructing its
use (four such spans exist in this repository's own docs today, none
inside a fenced block -- verified directly, not assumed, at authoring
time). So:

  1. Only text inside a fenced code block (``` or ~~~) is scanned at all --
     the same fence-toggle line-scan `hooks/gitapex_check_acm_present_or_waiver.py`
     already uses, run in the opposite direction (that check strips fences
     to find text *outside* them; this one keeps only text *inside* them).
     An unclosed fence extends to end-of-file, matching how GitHub's own
     renderer treats it.
  2. Within a fenced block, only a `gh` token in command-start position
     (line start, or immediately after a shell separator/opener: whitespace,
     `;`, `&`, `|`, `(`, a backtick) followed by one of gh CLI's real
     top-level subcommands counts as an invocation. The subcommand
     vocabulary is fixed and explicit (`_GH_SUBCOMMANDS`), the same
     never-grow-it-ad-hoc discipline `_HIDDEN_CHARACTERS` uses in the
     hidden-characters gate -- this closes the false positive a bare
     `gh\\s+\\S` match would produce on `for t in uv gh actionlint bun
     lychee` (a real line in this repository's own
     docs/superpowers/plans/2026-07-14-toolchain-foundation.md): `actionlint`
     is not a gh subcommand, so `gh actionlint` here is correctly not an
     invocation.

Exception marker: an explicit `<!-- gitapex-allow-raw-gh-cli: <reason> -->`
line directly on the line immediately preceding the fence's opening
marker (no blank line in between) exempts that one fenced block -- the
same strict, regex-anchored, non-empty-reason-required inline marker
style `hooks/gitapex_check_acm_present_or_waiver.py`'s ACM waiver already
uses in this repository, not a bare `noqa`-style flag.

Historical grandfathering: docs/superpowers/plans/2026-07-14-toolchain-foundation.md
(predates this gate, and CLAUDE.md's rule pre-existed it too) carries 3 real
fenced `gh run`/`gh pr create` invocations, each given the exception marker
in the same change that adds this gate -- not silently exempted by path.

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

_FENCE_MARKERS = ("```", "~~~")

# gh CLI's real top-level subcommands (core + actions + additional), fixed
# and explicit -- never grown ad hoc, the same discipline `_HIDDEN_CHARACTERS`
# uses in gitapex_gate_hidden_characters.py. Sourced from `gh help` at
# authoring time; a future gh CLI subcommand not yet in this list is a
# documented residual risk (see this module's own docstring), not silently
# claimed complete.
_GH_SUBCOMMANDS = frozenset(
    {
        "browse",
        "codespace",
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
        "label",
        "preview",
        "search",
        "secret",
        "ssh-key",
        "status",
        "variable",
    }
)

# The leading separator/opener is matched but not captured, so
# `match.group(1)` below is the invocation itself (`gh run`), never the
# separator character that preceded it (e.g. a command-substitution `(`).
_RAW_GH_INVOCATION_RE = re.compile(
    r"(?:^|[\s;&|(`])(gh\s+(?:" + "|".join(re.escape(s) for s in sorted(_GH_SUBCOMMANDS)) + r"))\b"
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
    """Return `(open_marker_line, close_marker_line)`, both 1-indexed
    marker-line positions, for each fenced block in `lines`. An unclosed
    fence's close is `len(lines)` -- extends to end-of-file, matching how
    GitHub's own renderer treats it."""
    ranges: list[tuple[int, int]] = []
    fence_marker: str | None = None
    open_line = 0  # only meaningful while fence_marker is not None
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if fence_marker is None:
            if stripped.startswith(_FENCE_MARKERS):
                fence_marker = stripped[:3]
                open_line = i
            continue
        if stripped.startswith(fence_marker):
            ranges.append((open_line, i))
            fence_marker = None
    if fence_marker is not None:
        ranges.append((open_line, len(lines)))
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

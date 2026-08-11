#!/usr/bin/env python3
"""CI gate: no tracked text file may carry a literal hidden/invisible
Unicode character -- a BOM, a zero-width character, or a bidi control.

Issue #702 (refs #665 repair 6, refs #651): both new files PR #651 added were first
authored with a literal U+FEFF inside a string literal instead of the
six-character escape sequence (backslash, u, f, e, f, f), and both were
caught and corrected only because the author happened to notice before
committing. That is not hypothetical drift: apm's own supply-chain scan
already flags this repository with "1 file(s) contain hidden characters"
(no filename, `--verbose` included), and a full scan of tracked `main`
found five files carrying a literal U+FEFF -- all inside BOM-stripping
logic or its tests/fixtures, where the escape form is exactly behaviorally
equivalent and, unlike the literal, visible to a reviewer. Author attention
is demonstrably not the right substrate for this: the same class recurred
three times in one retrospective's own telling (twice in PR #651's own new
files, once when the retrospective's own PR body silently dropped a
literal U+FEFF on post).

Scope is repository-wide by design -- unlike a narrowly-scoped gate such as
`gitapex_gate_plugin_root_brace_notation.py`, this one has no natural pathspec
restriction, since a hidden character can be authored into any tracked
text file. Discovery therefore asks `git ls-files` for the full tracked
set rather than a pathspec subset or a filesystem walk behind a denylist,
matching that gate's own rationale: the tracked-file set is exactly "this
repository's own source", so every ignored path (apm's package cache and
deploy trees, worktree checkouts) is out of scope by construction.

The character set graded is fixed and explicit (`_HIDDEN_CHARACTERS`), not
grown ad hoc: U+FEFF, the zero-width family (U+200B-U+200D), the bidi
control characters (U+200E/U+200F, U+202A-U+202E, U+2066-U+2069), and word
joiner (U+2060). The escape-sequence spelling of any of these (the literal
six/seven ASCII characters `\\ufeff`, `\\u200b`, etc.) is deliberately never
graded -- that is the fix this gate exists to steer authors toward, not a
second violation.

Diagnostic output never reproduces the offending character itself: a
hidden character echoed into a CI log is exactly as invisible there as it
was in the source, so every reported violation names the Unicode codepoint
(`U+FEFF`), its formal Unicode name (`ZERO WIDTH NO-BREAK SPACE`), and the
1-indexed line/column position instead.

Exit codes: 0 clean, 1 violation(s) found, 2 the scan could not be trusted
(no tracked files discovered, or a file could not be read/decoded as
UTF-8). The 2 case mirrors `gitapex_gate_evals_scripts_coverage.py`'s own rule that
an empty match set is an error, never a silent pass, and
`gitapex_gate_plugin_root_brace_notation.py`'s rule that an unreadable or
undecodable file fails closed, naming the file, rather than being silently
skipped or crashing with a bare traceback. Every currently tracked file in
this repository decodes as UTF-8 (verified directly), so this is not
presently a live restriction -- it is a deliberate choice not to let a
future binary or non-UTF-8 addition silently narrow this gate's coverage.

This gate's own production invocation (`hidden-characters-gate.yml`) runs
under `uv run`, so a real `pydantic` import is safe here (issue #1040,
refs #1035's `uv run` standardization that made this class of dependency
safe repo-wide).

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs) or via the pytest gate in
`tests/test_gitapex_gate_hidden_characters.py`.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# The fixed, explicit set of hidden/invisible characters this gate grades.
# Documented in this gate's own docstring above; extend deliberately, never
# ad hoc, if a new class of invisible character needs covering.
_HIDDEN_CHARACTERS = frozenset(
    {
        0xFEFF,  # BOM / ZERO WIDTH NO-BREAK SPACE
        0x200B,  # ZERO WIDTH SPACE
        0x200C,  # ZERO WIDTH NON-JOINER
        0x200D,  # ZERO WIDTH JOINER
        0x200E,  # LEFT-TO-RIGHT MARK
        0x200F,  # RIGHT-TO-LEFT MARK
        0x202A,  # LEFT-TO-RIGHT EMBEDDING
        0x202B,  # RIGHT-TO-LEFT EMBEDDING
        0x202C,  # POP DIRECTIONAL FORMATTING
        0x202D,  # LEFT-TO-RIGHT OVERRIDE
        0x202E,  # RIGHT-TO-LEFT OVERRIDE
        0x2060,  # WORD JOINER
        0x2066,  # LEFT-TO-RIGHT ISOLATE
        0x2067,  # RIGHT-TO-LEFT ISOLATE
        0x2068,  # FIRST STRONG ISOLATE
        0x2069,  # POP DIRECTIONAL ISOLATE
    }
)


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    column: int
    codepoint: int

    def codepoint_label(self) -> str:
        return f"U+{self.codepoint:04X}"

    def codepoint_name(self) -> str:
        # No try/except: every codepoint in _HIDDEN_CHARACTERS -- the only
        # source of a Violation's codepoint -- has a real Unicode name
        # (verified directly), so a fallback branch here would be an
        # unreachable guard a 100% line-coverage floor cannot see, the
        # exact defect class issue #665 repair 4 flagged in a sibling gate.
        return unicodedata.name(chr(self.codepoint))

    def describe(self) -> str:
        return (
            f"{self.path}:{self.line}:{self.column}: hidden character "
            f"{self.codepoint_label()} ({self.codepoint_name()})"
        )


def discover(root: pathlib.Path) -> list[pathlib.Path]:
    """Return every repository-tracked file under ``root``."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine).
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "ls-files", "-z"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:  # git missing entirely
        raise ScanError(f"cannot run git to list tracked files: {error}") from error
    if result.returncode != 0:
        raise ScanError(f"{root}: git ls-files failed: {result.stderr.strip()}")
    return sorted(root / name for name in result.stdout.split("\0") if name)


def violations_in_text(text: str) -> list[tuple[int, int, int]]:
    """Return ``(line, column, codepoint)`` for every hidden character in
    ``text``, both 1-indexed."""
    found = []
    line = 1
    column = 1
    for char in text:
        codepoint = ord(char)
        if codepoint in _HIDDEN_CHARACTERS:
            found.append((line, column, codepoint))
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return found


def violations_in_file(path: pathlib.Path, root: pathlib.Path) -> list[Violation]:
    """Return every hidden-character violation in ``path``.

    Raises ``ScanError`` rather than skipping the file when it cannot be
    read or decoded as UTF-8: nothing downstream can tell whether an
    unreadable file hides a violation.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error
    relative = str(path.relative_to(root))
    return [
        Violation(path=relative, line=line, column=column, codepoint=codepoint)
        for line, column, codepoint in violations_in_text(text)
    ]


def find_violations(root: pathlib.Path) -> list[Violation]:
    """Scan every tracked file under ``root`` and return all violations."""
    return violations_in(discover(root), root)


def violations_in(paths: list[pathlib.Path], root: pathlib.Path) -> list[Violation]:
    """Grade already-discovered ``paths``, so a caller that also needs the
    path list does not walk for it twice."""
    violations: list[Violation] = []
    for path in paths:
        violations.extend(violations_in_file(path, root))
    return violations


class GateHiddenCharactersArgs(BaseModel):
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
        description="Check that no repository-tracked file carries a literal "
        "hidden/invisible Unicode character (BOM, zero-width, bidi control)."
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = GateHiddenCharactersArgs(root=args.root)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    try:
        paths = discover(validated.root)
        if not paths:
            raise ScanError(
                f"{validated.root}: no tracked files found. An empty match "
                "set most plausibly means the scan ran against the wrong "
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
            f"\n{len(violations)} hidden character(s) found in tracked source. "
            "Replace each with its escape-sequence spelling (e.g. \\ufeff for "
            "U+FEFF) inside a normal string literal -- behaviorally "
            "equivalent and visible to a reviewer, instead of an invisible "
            "literal character (issue #702, refs #665 repair 6).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(paths)} tracked file(s) carry no hidden characters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

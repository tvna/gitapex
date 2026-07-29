#!/usr/bin/env python3
"""CI gate: a `.gitignore` pattern added in this PR must be referenced by
some test under `tests/`.

Issue #330 (cited by #519's retrospective triage): a new `.gitignore` entry
can ship with no test verifying the pattern actually works, so a later edit
can silently weaken or remove it. `tests/test_gitignore_worktrees.py` is a
hand-written example of the shape a test needs (`git check-ignore -v`,
asserting the match resolves to this repo's own `.gitignore` -- already
fixed per #347), but nothing required *every* new pattern to get one. This
gate closes that gap, mirroring `gate_skill_rename_lifecycle.py`'s shape:
the calling workflow computes the diff, this script only grades it.

Detecting "a test asserts this pattern" mechanically requires the test to
reference the pattern's literal text -- this could miss an indirectly
constructed test (e.g. one that builds the path via `pathlib.Path(...) /
"a" / "b"` joins instead of a literal string). That is a known, accepted
limitation (see issue #519's Acceptance Criteria Map), not an oversight.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Strips a leading negation marker and surrounding slashes so
# "/.claude/worktrees/" and ".claude/worktrees" compare equal -- gitignore
# patterns are commonly anchored/trailing-slashed for directory-only
# matches, but a test asserting the same path rarely repeats that exact
# punctuation.
_NEGATION_PREFIX = "!"


def _core(pattern: str) -> str:
    """Return the comparable core of a `.gitignore` pattern: no leading
    negation marker, no leading/trailing slash, no surrounding whitespace."""
    value = pattern.strip()
    if value.startswith(_NEGATION_PREFIX):
        value = value[len(_NEGATION_PREFIX):]
    return value.strip("/")


def parse_patterns(text: str) -> list[str]:
    """Parse one `.gitignore` pattern per line, ignoring blank lines and
    `#`-comment lines, deduplicated while preserving first-seen order."""
    seen: dict[str, None] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        seen.setdefault(stripped, None)
    return list(seen)


def _discover_test_files(repo_root: Path) -> list[Path]:
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []
    return sorted(tests_dir.glob("**/*.py"))


def find_offenders(added_patterns: list[str], repo_root: Path) -> list[str]:
    """Return one human-readable offender string per added pattern whose
    core text is not referenced, literally, by any test under `tests/`."""
    test_files = _discover_test_files(repo_root)
    sources = []
    for path in test_files:
        try:
            sources.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue

    offenders = []
    for pattern in added_patterns:
        core = _core(pattern)
        if core and any(core in source for source in sources):
            continue
        offenders.append(
            f"{pattern}: added to .gitignore in this diff, but no test "
            f"under tests/ references it"
        )
    return offenders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every .gitignore pattern added in this PR "
        "is referenced by some test under tests/.")
    parser.add_argument(
        "--added",
        help="Path to a file of newly-added .gitignore lines, one per "
        "line; reads standard input when omitted.")
    args = parser.parse_args(argv)

    try:
        text = (
            open(args.added, encoding="utf-8").read() if args.added else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: added-lines file not found: {args.added}", file=sys.stderr)
        return 1

    added_patterns = parse_patterns(text)
    if not added_patterns:
        print("PASS: no .gitignore patterns added in this diff")
        return 0

    offenders = find_offenders(added_patterns, Path("."))
    if not offenders:
        print(f"PASS: test coverage found for all {len(added_patterns)} added pattern(s)")
        return 0

    print("FAIL: the following added .gitignore pattern(s) have no test:", file=sys.stderr)
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    print(
        "Add a test under tests/ that references the pattern (e.g. via "
        "'git check-ignore -v' asserting the match resolves to this "
        "repo's own .gitignore, following tests/test_gitignore_worktrees.py).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

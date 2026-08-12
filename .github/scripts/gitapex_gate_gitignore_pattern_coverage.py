#!/usr/bin/env python3
"""CI gate: a `.gitignore` pattern added in this PR must be referenced by
some test under `tests/`.

Issue #330 (cited by #519's retrospective triage): a new `.gitignore` entry
can ship with no test verifying the pattern actually works, so a later edit
can silently weaken or remove it. `tests/test_gitapex_gitignore_worktrees.py` is a
hand-written example of the shape a test needs (`git check-ignore -v`,
asserting the match resolves to this repo's own `.gitignore` -- already
fixed per #347), but nothing required *every* new pattern to get one. This
gate closes that gap, mirroring `gitapex_gate_skill_rename_lifecycle.py`'s shape:
the calling workflow computes the diff, this script only grades it.

Detecting "a test asserts this pattern" mechanically requires the test to
reference the pattern's literal text -- this could miss an indirectly
constructed test (e.g. one that builds the path via `pathlib.Path(...) /
"a" / "b"` joins instead of a literal string). That is a known, accepted
limitation (see issue #519's Acceptance Criteria Map), not an oversight.

Issue #1062 (wave 3 of #1040's batch pydantic CLI-arg validation rollout):
`main`'s parsed namespace is now passed through `GitignorePatternCoverageArgs`
immediately after `parser.parse_args(argv)`, matching the wrap
`gitapex_gate_hidden_characters.py`/`gitapex_gate_behind_base.py` already apply.
`--added` (`str | None`, defaults to `None`) has no constraint beyond that
already-guaranteed shape -- deliberately no path-existence check here: a
nonexistent `--added` path is already handled gracefully downstream (the
`OSError`/`UnicodeDecodeError` catch around the file read, tested by
`test_main_reports_error_for_missing_added_file`), and duplicating that as
a pydantic field validator would only add a second, differently-worded
error path for the same input. So construction can currently never raise
`ValidationError` for a real CLI invocation; the model exists for
consistency with #1040's repo-wide convention (a typed seam between
`parse_args` and business logic). This gate's own production invocation
(`gitignore-pattern-coverage-gate.yml`) already runs under `uv run`
(issue #1035), so the added `pydantic` import is safe here.

Exit codes:
    0  No patterns added, or every added pattern has test coverage.
    1  An added pattern has no test coverage, or the `--added`/stdin input
       could not be read.
    2  CLI arguments failed validation (unreachable via this script's own
       argparse-guaranteed shape today; see GitignorePatternCoverageArgs).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError


class GitignorePatternCoverageArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1062). See the
    module docstring's own issue #1062 section for why `added` carries no
    additional field validator."""

    added: str | None = None


# Strips a leading negation marker and surrounding slashes so
# "/.claude/worktrees/" and ".claude/worktrees" compare equal -- gitignore
# patterns are commonly anchored/trailing-slashed for directory-only
# matches, but a test asserting the same path rarely repeats that exact
# punctuation.
_NEGATION_PREFIX = "!"

# A plain `core in source` substring check (the first version of this gate)
# was matched by an unrelated word merely containing the core as a
# substring -- e.g. core "build" is a substring of "rebuild" and
# "build_id" -- which would report a completely uncovered pattern as
# covered. Bounding both sides with a not-alnum-or-underscore lookaround
# (rather than plain `\b`, which does not reliably bound a core containing
# glob metacharacters like `*`) keeps the match to the pattern appearing as
# its own token, not a fragment of a longer identifier.
_NOT_BEFORE = r"(?<![A-Za-z0-9_])"
_NOT_AFTER = r"(?![A-Za-z0-9_])"


def _core_regex(core: str) -> re.Pattern[str]:
    return re.compile(f"{_NOT_BEFORE}{re.escape(core)}{_NOT_AFTER}")


def _core(pattern: str) -> str:
    """Return the comparable core of a `.gitignore` pattern: no leading
    negation marker, no leading/trailing slash, no surrounding whitespace."""
    value = pattern.strip()
    if value.startswith(_NEGATION_PREFIX):
        value = value[len(_NEGATION_PREFIX) :]
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
        if core and any(_core_regex(core).search(source) for source in sources):
            continue
        offenders.append(f"{pattern}: added to .gitignore in this diff, but no test under tests/ references it")
    return offenders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every .gitignore pattern added in this PR is referenced by some test under tests/."
    )
    parser.add_argument(
        "--added",
        help="Path to a file of newly-added .gitignore lines, one per line; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)

    try:
        validated = GitignorePatternCoverageArgs(added=args.added)
    except ValidationError:
        print("error: invalid CLI arguments", file=sys.stderr)
        return 2

    try:
        if validated.added:
            with Path(validated.added).open(encoding="utf-8") as handle:
                text = handle.read()
        else:
            text = sys.stdin.buffer.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # OSError (not just FileNotFoundError) -- a directory path
        # (IsADirectoryError) or a permission-denied file (PermissionError)
        # -- and UnicodeDecodeError (a non-UTF-8 added-lines file, or non-
        # UTF-8 stdin) must also fail with this message, not an unhandled
        # traceback or (for stdin under a surrogateescape locale) silently
        # corrupted text.
        source = validated.added if validated.added else "standard input"
        print(f"error: could not read {source!r}: {exc}", file=sys.stderr)
        return 1

    added_patterns = parse_patterns(text)
    if not added_patterns:
        print("PASS: no .gitignore patterns added in this diff")
        return 0

    offenders = find_offenders(added_patterns, Path())
    if not offenders:
        print(f"PASS: test coverage found for all {len(added_patterns)} added pattern(s)")
        return 0

    print("FAIL: the following added .gitignore pattern(s) have no test:", file=sys.stderr)
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    print(
        "Add a test under tests/ that references the pattern (e.g. via "
        "'git check-ignore -v' asserting the match resolves to this "
        "repo's own .gitignore, following tests/test_gitapex_gitignore_worktrees.py).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

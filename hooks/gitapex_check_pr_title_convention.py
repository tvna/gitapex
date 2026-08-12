"""Check a candidate PR title for Conventional Commits format.

hooks/check-pr-title-convention.sh needs this check bundled *with the
hook itself*. Per docs/repository-layout.md, only skills/ and hooks/ are
deployed runtime primitives when this repository is installed as a
plugin -- .github/ is dev-only CI tooling and is never installed into a
consumer repository. .github/scripts/gitapex_gate_pr_title_convention.py
is the CI-side backstop for the same rule (issue #1058), and carries an
independent copy of the same regex rather than importing this file, so
each layer is verifiable on its own -- the same split this repository
already uses for hooks/gitapex_check_acm_present_or_waiver.py vs.
.github/scripts/gitapex_gate_acm_issue_disclosure.py.

Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys

#: Conventional Commits v1.0.0 type list, plus an optional `(scope)` and an
#: optional breaking-change `!`, plus a non-empty description. Mirrored
#: byte-for-byte in .github/scripts/gitapex_gate_pr_title_convention.py's own
#: CONVENTIONAL_COMMIT_RE -- kept in sync by
#: tests/test_gitapex_pr_title_convention_regex_sync.py.
#: `\Z`, not `$`: Python's `$` also matches just before a trailing newline
#: at the end of the string, which would silently accept a title carrying
#: one. `[^\r\n]`, not `.`: `.` matches any character except `\n` by
#: default, which would still accept a title ending in a bare `\r` (a
#: line terminator on its own) -- caught by review on PR #1059.
CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w./-]+\))?!?: [^\r\n]{1,72}\Z"
)


def is_conventional_commit_title(title: str | None) -> bool:
    """Return True iff `title` matches Conventional Commits format."""
    return bool(CONVENTIONAL_COMMIT_RE.match(title or ""))


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff the given title matches Conventional Commits format, else 1."""
    parser = argparse.ArgumentParser(description="Check that a candidate PR title matches Conventional Commits format.")
    parser.add_argument(
        "--title",
        help="The candidate PR title; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        title = args.title if args.title is not None else sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as error:
        print(f"error: standard input is not valid UTF-8: {error}", file=sys.stderr)
        return 1
    if is_conventional_commit_title(title):
        print("PASS: PR title matches Conventional Commits format")
        return 0
    print(
        "FAIL: PR title does not match Conventional Commits format -- expected "
        "'type(scope)!: description' with type in feat|fix|docs|style|refactor|"
        "perf|test|build|ci|chore|revert, a non-empty description of at most 72 "
        "characters, and an optional scope/breaking-change marker",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

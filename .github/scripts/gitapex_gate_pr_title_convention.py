#!/usr/bin/env python3
"""CI gate: a pull request's title must match Conventional Commits format.

Issue #1058: hooks/check-pr-title-convention.sh already guards the
agent-mediated path (mcp__github__create_pull_request /
mcp__github__update_pull_request), but a PR opened or retitled through the
GitHub web UI, the `gh` CLI, or another bot never goes through that hook at
all -- this gate is the CI-side backstop that closes that gap, wired as a
required status check (.gitapex/ssot.json's `pr-title-convention` gate,
cluster `github-operations`) via .github/workflows/pr-title-convention-gate.yml
on `pull_request: [opened, edited, synchronize]`.

Deliberately no `paths:` filter on the calling workflow, and no scoping
here either -- following lint.yml's and hidden-characters-gate.yml's own
stated reasoning (see those files' own header comments and
gitapex_gate_ruleset_required_checks.py's module docstring): a required
status check backed by a workflow that never fires for a given pull request
leaves that check `Pending` forever, with no in-repository fix.

The title text is read from PR_TITLE on standard input (not a CLI
argument), matching gitapex_gate_acm_issue_disclosure.py's own handling of
ISSUE_BODY -- both carry untrusted, tool/attacker-controlled text (anyone
who can open or edit a pull request controls the PR title), and piping it
through stdin avoids ever interpolating it into a shell command line or
into an argv element subject to the OS's ARG_MAX.

Carries an independent copy of the same regex as
hooks/gitapex_check_pr_title_convention.py rather than importing it --
`.github/` is never installed when this repository ships as a plugin (per
docs/repository-layout.md, only skills/ and hooks/ are deployed), so the
hook-side checker cannot depend on this file, and this file stays
standalone for the same reason in the other direction. The two copies are
kept in sync by tests/test_gitapex_pr_title_convention_regex_sync.py.

Standard library only: unlike several sibling `.github/scripts/*.py`
gates, this one validates no CLI arguments beyond the fixed `--title`
escape hatch below, so it carries no `pydantic` import.

Usage::

    printf '%s' "$PR_TITLE" | uv run --frozen python3 \\
        .github/scripts/gitapex_gate_pr_title_convention.py

Exit codes: 0 the title matches; 1 it does not.
"""

from __future__ import annotations

import argparse
import re
import sys

#: Conventional Commits v1.0.0 type list, plus an optional `(scope)` and an
#: optional breaking-change `!`, plus a non-empty description. Mirrored
#: byte-for-byte in hooks/gitapex_check_pr_title_convention.py's own
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
    parser = argparse.ArgumentParser(
        description="Check that a pull request's title matches Conventional Commits format."
    )
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
        # The title itself is never echoed here: it is externally supplied,
        # unauthenticated text (anyone who can open or edit a pull request
        # controls it) that could carry pasted credentials or PII -- caught
        # by review on PR #1059.
        "FAIL: PR title does not match Conventional Commits format -- expected "
        "'type(scope)!: description' with type in feat|fix|docs|style|refactor|"
        "perf|test|build|ci|chore|revert, a non-empty description of at most 72 "
        "characters, and an optional scope/breaking-change marker",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

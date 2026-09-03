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
kept in sync by tests/test_gitapex_pr_title_convention_regex_sync.py --
that test compares `CONVENTIONAL_COMMIT_RE.pattern`/`.flags` directly, so
this module keeps that compiled pattern as a plain module-level constant
rather than folding it invisibly into `PrTitle` below.

Domain validation via a real `pydantic` import (unlike this file's earlier
revision, which validated no CLI arguments beyond the fixed `--title`
escape hatch and so carried none): `PrTitle.title` uses
`CONVENTIONAL_COMMIT_RE` directly as a `Field(pattern=...)` constraint, so
pydantic -- not a hand-rolled `if`/regex branch -- is what decides
PASS/FAIL. `hooks/gitapex_check_pr_title_convention.py` stays
stdlib-only and does NOT get this same treatment: per
docs/repository-layout.md, only skills/ and hooks/ ship with the plugin,
and that hook must run via a bare `python3` invocation with no virtualenv
guaranteed (no `uv run`), so a real third-party import there would break
in an installed-plugin consumer checkout. This file's own production
invocation always goes through `uv run` (see Usage below and this
repository's `uv run` standardization, issue #1035), so the import is
safe here.

Usage::

    printf '%s' "$PR_TITLE" | uv run --frozen python3 \\
        .github/scripts/gitapex_gate_pr_title_convention.py

A bare pipe here masks `printf`'s own exit status in a non-`pipefail` shell
(issue #1531) -- harmless for a literal `printf` producer, which cannot
itself fail in ordinary use, but add `set -o pipefail` first if this
recipe's producer is ever swapped for a command that can.

Exit codes: 0 the title matches; 1 it does not.
"""

from __future__ import annotations

import argparse
import re
import sys

from pydantic import BaseModel, Field, ValidationError

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


class PrTitle(BaseModel):
    """A candidate PR title, validated against Conventional Commits format.

    `Field(pattern=CONVENTIONAL_COMMIT_RE)` -- a compiled `re.Pattern`, not
    a second pattern string -- is the actual PASS/FAIL decision: pydantic
    applies `CONVENTIONAL_COMMIT_RE.match` against `title` during
    construction and raises `ValidationError` on a non-match, verified
    directly (a bare `str` field accepts `None`-coerced-to-string or an
    unanchored partial match under pydantic's own lax-mode defaults; this
    does neither -- confirmed empirically before relying on it here).
    """

    title: str = Field(pattern=CONVENTIONAL_COMMIT_RE)


def is_conventional_commit_title(title: str | None) -> bool:
    """Return True iff `title` matches Conventional Commits format."""
    try:
        PrTitle(title=title)  # type: ignore[arg-type]
    except ValidationError:
        return False
    return True


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
    try:
        PrTitle(title=title)
    except ValidationError:
        print(
            # The title itself is never echoed here: it is externally
            # supplied, unauthenticated text (anyone who can open or edit
            # a pull request controls it) that could carry pasted
            # credentials or PII -- caught by review on PR #1059.
            "FAIL: PR title does not match Conventional Commits format -- expected "
            "'type(scope)!: description' with type in feat|fix|docs|style|refactor|"
            "perf|test|build|ci|chore|revert, a non-empty description of at most 72 "
            "characters, and an optional scope/breaking-change marker",
            file=sys.stderr,
        )
        return 1
    print("PASS: PR title matches Conventional Commits format")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Close never-enriched post-merge-auto-retro stub issues after 48h.

Issue #694 (completing #314/#140's post-merge-auto-retro gate cluster):
`gitapex_post_merge_retro.py` opens a bare stub retrospective issue on every PR
merge; `skills/merge-retrospective/SKILL.md` Step 4 enriches it with real
repair content when an interactive session invokes it (either directly,
per `skills/drafting-a-pr-to-merge/SKILL.md` Step 10's own merge branch,
or later). A PR merged after its driving session's subscription already
ended has no session left to ever enrich its stub -- by this issue's own
accepted premise, a real retrospective requires session memory that a
fresh, memory-less CI dispatch cannot substitute for. Left alone, that
stub simply stays open, empty, forever.

This script finds `retrospective`-labelled, still-open issues whose body
still contains `gitapex_post_merge_retro.py`'s own unenriched-stub marker text
(never enriched -- see `_STUB_MARKER` below) and whose `created_at` is
older than `--stale-hours` (default 48, the upper end of the "24-48h
rescan" figure #140/#314 already named for this later slice), and closes
each with an explanatory comment naming the expiry and how to manually
reopen (and re-run `merge-retrospective`) if a real retrospective is
still wanted. Never touches an issue whose body no longer carries the
marker -- that means it was already enriched, and closing it would
silently discard real retrospective content instead of an empty stub.

`_STUB_MARKER` is a literal copy of the phrase `gitapex_post_merge_retro.py`'s own
`open_retro_issue` embeds in every stub body, not an import from that
module -- this repository keeps `.github/scripts/*.py` files independent
of one another (see that module's own docstring for the same rationale).
`tests/test_gitapex_stale_retro_stub_autoclose.py` carries a drift test asserting
the literal marker text still appears in `gitapex_post_merge_retro.py`'s source,
so the two cannot silently re-diverge the way the title/query pair did
before issue #341's fix.

Issue #729: the retry/backoff-with-`GitHubApiError` HTTP calls this script
needs (previously two hand-copied local implementations, `_call` and
`_fetch_issues_page`, near-identical to `gitapex_gate_acm_issue_disclosure.py`
and `gitapex_post_merge_retro.py`'s own former copies) now delegate to
`_gitapex_github_http.call_json` and `_gitapex_github_http.fetch_json_page`
respectively. That module is the one deliberate, generic exception to this
repository's `.github/scripts/*.py` independence convention (see its own
docstring, and `gitapex_scan_retrospective_gate_drift.py`'s docstring for the
convention itself) -- this script otherwise stays dependency-light (stdlib
plus `pydantic`, this repository's own pinned CLI-arg validation dependency)
and does not import any other carrier script.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_stale_retro_stub_autoclose.py \\
        --owner tvna --repo gitapex --stale-hours 48

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs), matching stale-retro-stub-autoclose.yml's own
invocation.

Environment variables:
    GITHUB_TOKEN  GitHub token with issues:write (the default Actions
                  token's ``issues: write`` permission suffices).

Exit codes:
    0  Ran to completion (whether or not any stale stub was found/closed).
    1  Missing token or a GitHub API error prevented completion (never
       silently treated as success).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from _gitapex_github_http import GitHubApiError, call_json, default_opener, fetch_json_page
from pydantic import BaseModel, Field, ValidationError, field_validator

_API_ROOT = "https://api.github.com"
_PER_PAGE = 100
_RETRO_LABEL = "retrospective"
_DEFAULT_STALE_HOURS = 48

# Literal copy of the phrase `gitapex_post_merge_retro.py`'s own `open_retro_issue`
# embeds in every stub body it creates -- see this module's own docstring
# for why this is a copy, not an import, and how drift is caught.
_STUB_MARKER = "Automated stub opened by the post-merge-auto-retro gate"

# The leading phrase of this module's own `format_close_comment` output --
# used by `close_stub_issue` to detect a close comment already posted on a
# prior run (see that function's own docstring for why this check exists).
_CLOSE_COMMENT_MARKER = "Closing this retrospective stub:"


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def is_unenriched_stub(body: str | None) -> bool:
    """True iff `body` still carries the CI opener's own stub marker --
    i.e. no session has replaced the placeholder with real content yet."""
    return _STUB_MARKER in (body or "")


def is_stale(created_at_iso: str, now: datetime, stale_hours: int) -> bool:
    """True iff `created_at_iso` (a GitHub API UTC timestamp, e.g.
    `2026-08-01T12:00:00Z`) is at least `stale_hours` old relative to
    `now`."""
    created = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    return (now - created) >= timedelta(hours=stale_hours)


def find_stale_stub_issues(issues: list[dict[str, Any]], now: datetime, stale_hours: int) -> list[dict[str, Any]]:
    """Return the subset of `issues` (each a GitHub issue-list item) that
    are still unenriched stubs *and* old enough to close. Order is
    preserved from the input."""
    return [
        issue
        for issue in issues
        if is_unenriched_stub(issue.get("body")) and is_stale(issue["created_at"], now, stale_hours)
    ]


def format_close_comment(stale_hours: int) -> str:
    """The explanatory comment posted on every auto-close -- acceptance
    criterion 'auto-close never happens silently' from issue #694: every
    close carries this comment naming the expiry and the manual-reopen
    path, never a bare state-change with no explanation."""
    return (
        f"Closing this retrospective stub: it has stayed unenriched (its body "
        f"still carries the automated stub marker from the post-merge-auto-retro "
        f"gate) for at least {stale_hours} hours, past this repository's "
        f"auto-close threshold (issue #694). No session enriched it with a real "
        f"merge retrospective before that window elapsed -- by design, per #694's "
        f"own accepted premise that a real retrospective requires session memory "
        f"a fresh, memory-less dispatch cannot substitute for.\n\n"
        f"If a real retrospective for this PR is still wanted, reopen this issue "
        f"and re-run the `merge-retrospective` skill "
        f"(skills/merge-retrospective/SKILL.md) against it, or file a new "
        f"retrospective issue manually."
    )


def format_report(closed_issue_numbers: list[int]) -> str:
    """Human-readable report, printed to stdout and captured in the CI
    step summary."""
    if not closed_issue_numbers:
        return "No stale unenriched retrospective stubs found; nothing closed."
    lines = [f"Closed {len(closed_issue_numbers)} stale unenriched retrospective stub(s):"]
    lines.extend(f"  #{n}" for n in sorted(closed_issue_numbers))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


def list_open_retro_issues(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    """Return every open `retrospective`-labelled issue (not PR), paginated.
    Deliberately state=open only -- a closed issue is never a candidate for
    this script, whether it was closed by a human, this script itself on a
    prior run, or `merge-retrospective`'s own confirmed fast-close."""
    sleeper = sleeper if sleeper is not None else time.sleep
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"labels": _RETRO_LABEL, "state": "open", "per_page": _PER_PAGE, "page": page})
        url = f"{_API_ROOT}/repos/{owner}/{repo}/issues?{query}"
        page_items = fetch_json_page(url, token, opener, sleeper)
        if not page_items:
            break
        # The issues-list endpoint also returns pull requests carrying the
        # label; a retrospective issue is never a PR, so this is a
        # defensive exclusion rather than an expected real-world hit.
        issues.extend(item for item in page_items if "pull_request" not in item)
        if len(page_items) < _PER_PAGE:
            break
        page += 1
    return issues


def _has_close_comment(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> bool:
    """True iff `issue_number` already carries a close comment this
    function's own marker identifies -- i.e. a prior run already posted
    it, most likely because that prior run's own PATCH close then failed.
    A single page (up to 100 comments) is more than sufficient for a stub
    issue, which only ever accumulates a handful of bot comments."""
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page={_PER_PAGE}"
    comments = fetch_json_page(url, token, opener, sleeper)
    return any(_CLOSE_COMMENT_MARKER in (comment.get("body") or "") for comment in comments)


def close_stub_issue(
    owner: str,
    repo: str,
    issue_number: int,
    stale_hours: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Post the explanatory comment (unless a prior run already posted
    one -- see `_has_close_comment`), then close the issue. Comment
    first: if the close call itself then fails (network, permissions),
    the explanation is still on the issue rather than silently lost.

    A later run retries safely because of the `_has_close_comment` check
    above, not merely because the explanation is already there: without
    it, a later run would re-run this function from the top and post a
    second, duplicate comment before retrying the close -- exactly the
    outcome `max_attempts=1` below exists to prevent within a single
    call, reopened across calls if nothing here checked for one already
    posted.

    max_attempts=1 on the comment POST: comment creation is not
    idempotent -- mirrors gitapex_post_merge_retro.py's own open_retro_issue
    call, whose docstring explains why (a lost/truncated response after
    GitHub already created the resource must never be retried into a
    duplicate). The PATCH close below is naturally idempotent (setting
    state=closed twice has no further effect) and keeps the default
    retry count."""
    sleeper = sleeper if sleeper is not None else time.sleep
    comment_url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    if not _has_close_comment(owner, repo, issue_number, token, opener, sleeper):
        call_json(
            "POST",
            comment_url,
            token,
            opener,
            sleeper,
            body={"body": format_close_comment(stale_hours)},
            max_attempts=1,
        )
    issue_url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}"
    call_json("PATCH", issue_url, token, opener, sleeper, body={"state": "closed", "state_reason": "not_planned"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# This CLI's own wording for each constraint the model below imposes, keyed
# by pydantic's own error type. pydantic's message text is deliberately not
# echoed -- it is not part of this CLI's contract, so a version bump must
# not change what an operator reads -- but naming only the offending flag
# and nothing else would leave a rejected `--stale-hours 0` unactionable.
# An unmapped type falls back to a generic label rather than raising, so a
# future constraint kind can never turn a rejected argument into a
# traceback.
_CONSTRAINT_HINTS = {
    "string_too_short": "must not be blank",
    "greater_than": "must be a positive integer",
    # Issue #1087: min_length=1 alone accepts a whitespace-only string; the
    # validator below closes that with a plain ValueError, which pydantic
    # reports as this generic type. Reuses "must not be blank" since an
    # operator would never need to distinguish it from a truly empty value.
    # Keyed on pydantic's error *type* alone, not on which validator raised
    # it: a future field_validator added to this model that raises a plain
    # ValueError for an unrelated reason would also render here as "must
    # not be blank" -- give it a distinct error type or extend this dict
    # deliberately rather than letting it fall through this entry.
    "value_error": "must not be blank",
}


def _is_blank(value: str) -> bool:
    """True iff every character in `value` is ordinary whitespace or a
    Unicode Format-category (Cf) mark -- invisible either way. Cf covers
    U+200B ZERO WIDTH SPACE, U+FEFF ZERO WIDTH NO-BREAK SPACE, and U+180E
    MONGOLIAN VOWEL SEPARATOR, none of which str.strip() removes -- so a
    value made solely of Cf marks passed the old `.strip()`-only check
    unrejected (issue #1094)."""
    return all(char.isspace() or unicodedata.category(char) == "Cf" for char in value)


class StaleRetroStubAutocloseArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. ``owner``/``repo``
    reject blank (argparse's own ``required=True`` only guarantees the flag
    was passed, not that its value is non-empty) and ``stale_hours`` must
    be positive -- a zero or negative age window would close every open
    stub the moment it was opened."""

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    stale_hours: int = Field(gt=0)

    @field_validator("owner", "repo")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        # Checked via _is_blank() without storing a stripped result -- this
        # validates, it does not trim (issue #1087). _is_blank() also
        # rejects a value made solely of Unicode Format-category (Cf)
        # characters, which plain .strip() leaves in place (issue #1094).
        if _is_blank(value):
            raise ValueError("must not be blank")
        return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Close never-enriched post-merge-auto-retro stub issues older than --stale-hours."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=_DEFAULT_STALE_HOURS,
        help=f"Close a stub only once it is at least this many hours old (default: {_DEFAULT_STALE_HOURS})",
    )
    args = parser.parse_args(argv)
    try:
        StaleRetroStubAutocloseArgs(owner=args.owner, repo=args.repo, stale_hours=args.stale_hours)
    except ValidationError as error:
        # Only the offending flag names and this CLI's own constraint
        # wording are echoed -- never pydantic's own message text, and
        # never the rejected value itself.
        invalid = ", ".join(
            f"--{str(item['loc'][0]).replace('_', '-')} ({_CONSTRAINT_HINTS.get(item['type'], 'invalid value')})"
            for item in error.errors()
        )
        print(f"error: invalid arguments: {invalid}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        issues = list_open_retro_issues(args.owner, args.repo, token)
        now = datetime.now(UTC)
        stale_issues = find_stale_stub_issues(issues, now, args.stale_hours)
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    # Each issue is closed independently: one issue's failure (e.g. a
    # transient API error on its PATCH) must not discard the successful
    # closes already made this run, or skip the otherwise-healthy issues
    # still queued behind it -- see the marker-based retry-safety
    # `close_stub_issue`/`_has_close_comment` now provide across runs for
    # whichever issue actually failed.
    closed: list[int] = []
    failed: list[int] = []
    for issue in stale_issues:
        number = int(issue["number"])
        try:
            close_stub_issue(args.owner, args.repo, number, args.stale_hours, token)
            closed.append(number)
        except GitHubApiError as error:
            print(f"error: closing issue #{number} failed: {error}", file=sys.stderr)
            failed.append(number)

    print(format_report(closed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

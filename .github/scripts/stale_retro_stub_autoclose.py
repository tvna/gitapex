#!/usr/bin/env python3
"""Close never-enriched post-merge-auto-retro stub issues after 48h.

Issue #694 (completing #314/#140's post-merge-auto-retro gate cluster):
`post_merge_retro.py` opens a bare stub retrospective issue on every PR
merge; `skills/merge-retrospective/SKILL.md` Step 4 enriches it with real
repair content when an interactive session invokes it (either directly,
per `skills/drafting-a-pr-to-merge/SKILL.md` Step 10's own merge branch,
or later). A PR merged after its driving session's subscription already
ended has no session left to ever enrich its stub -- by this issue's own
accepted premise, a real retrospective requires session memory that a
fresh, memory-less CI dispatch cannot substitute for. Left alone, that
stub simply stays open, empty, forever.

This script finds `retrospective`-labelled, still-open issues whose body
still contains `post_merge_retro.py`'s own unenriched-stub marker text
(never enriched -- see `_STUB_MARKER` below) and whose `created_at` is
older than `--stale-hours` (default 48, the upper end of the "24-48h
rescan" figure #140/#314 already named for this later slice), and closes
each with an explanatory comment naming the expiry and how to manually
reopen (and re-run `merge-retrospective`) if a real retrospective is
still wanted. Never touches an issue whose body no longer carries the
marker -- that means it was already enriched, and closing it would
silently discard real retrospective content instead of an empty stub.

`_STUB_MARKER` is a literal copy of the phrase `post_merge_retro.py`'s own
`open_retro_issue` embeds in every stub body, not an import from that
module -- this repository keeps `.github/scripts/*.py` files independent
of one another (see that module's own docstring for the same rationale).
`tests/test_stale_retro_stub_autoclose.py` carries a drift test asserting
the literal marker text still appears in `post_merge_retro.py`'s source,
so the two cannot silently re-diverge the way the title/query pair did
before issue #341's fix.

Deliberately stdlib-only, mirroring `post_merge_retro.py` and
`scan_retrospective_gate_drift.py`'s own shape and retry-with-backoff
logic.

Usage::

    python3 .github/scripts/stale_retro_stub_autoclose.py \\
        --owner tvna --repo gitapex --stale-hours 48

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
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30
_PER_PAGE = 100
_RETRO_LABEL = "retrospective"
_DEFAULT_STALE_HOURS = 48

# Literal copy of the phrase `post_merge_retro.py`'s own `open_retro_issue`
# embeds in every stub body it creates -- see this module's own docstring
# for why this is a copy, not an import, and how drift is caught.
_STUB_MARKER = "Automated stub opened by the post-merge-auto-retro gate"

# The leading phrase of this module's own `format_close_comment` output --
# used by `close_stub_issue` to detect a close comment already posted on a
# prior run (see that function's own docstring for why this check exists).
_CLOSE_COMMENT_MARKER = "Closing this retrospective stub:"


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


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


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted env-var-derived segments --
    # no attacker-influenced value ever reaches this function.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def _format_code(code: int) -> str:
    return str(code) if code else "network error"


def _call(
    method: str,
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    body: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Call the GitHub API, retrying transient (network / 5xx) failures up
    to `max_attempts` attempts -- mirrors `post_merge_retro.py`'s own
    `_call` shape."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    last_code = 0
    last_body = ""
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 -- fixed https://api.github.com URL
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with opener(request) as response:
                last_code = int(response.status)
                last_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_code = int(error.code)
            last_body = error.read().decode("utf-8", errors="replace")
        except (OSError, http.client.IncompleteRead) as error:
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            return json.loads(last_body) if last_body else {}
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for {method} {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < max_attempts:
            sleeper(attempt * 5)

    raise GitHubApiError(f"{method} {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def _fetch_issues_page(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    max_attempts: int = 3,
) -> list[dict[str, Any]]:
    """GET one page of a list endpoint (issues or comments), retrying
    transient failures -- mirrors `scan_retrospective_gate_drift.py`'s own
    function of the same name (a list response, not the single-object
    shape `_call` above assumes, so it cannot reuse `_call` directly). GET
    is naturally idempotent, so `max_attempts` defaults to 3 like `_call`'s
    own default; the parameter exists so the two functions' retry shape
    stays structurally consistent, not because a GET here ever needs 1."""
    last_code = 0
    last_body = ""
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, method="GET")  # noqa: S310 -- fixed https://api.github.com URL
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", _API_VERSION)
        try:
            with opener(request) as response:
                last_code = int(response.status)
                last_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_code = int(error.code)
            last_body = error.read().decode("utf-8", errors="replace")
        except (OSError, http.client.IncompleteRead) as error:
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            page: list[dict[str, Any]] = json.loads(last_body) if last_body else []
            return page
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for GET {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < max_attempts:
            sleeper(attempt * 5)

    raise GitHubApiError(f"GET {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def list_open_retro_issues(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
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
        page_items = _fetch_issues_page(url, token, opener, sleeper)
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
    comments = _fetch_issues_page(url, token, opener, sleeper)
    return any(_CLOSE_COMMENT_MARKER in (comment.get("body") or "") for comment in comments)


def close_stub_issue(
    owner: str,
    repo: str,
    issue_number: int,
    stale_hours: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
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
    idempotent -- mirrors post_merge_retro.py's own open_retro_issue
    call, whose docstring explains why (a lost/truncated response after
    GitHub already created the resource must never be retried into a
    duplicate). The PATCH close below is naturally idempotent (setting
    state=closed twice has no further effect) and keeps the default
    retry count."""
    sleeper = sleeper if sleeper is not None else time.sleep
    comment_url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    if not _has_close_comment(owner, repo, issue_number, token, opener, sleeper):
        _call(
            "POST",
            comment_url,
            token,
            opener,
            sleeper,
            body={"body": format_close_comment(stale_hours)},
            max_attempts=1,
        )
    issue_url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}"
    _call("PATCH", issue_url, token, opener, sleeper, body={"state": "closed", "state_reason": "not_planned"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _validate_cli_args(owner: str, repo: str, stale_hours: int) -> str | None:
    """Return a pydantic-``ValidationError``-style detail string (one
    ``<field>: <message>`` clause per violated constraint, joined with
    ``"; "``, in field-declaration order) if ``owner``/``repo`` are blank
    or ``stale_hours`` is not positive, else None. Message text matches
    the sibling scripts' own pydantic-equivalent wording."""
    errors: list[str] = []
    if not owner:
        errors.append("owner: String should have at least 1 character")
    if not repo:
        errors.append("repo: String should have at least 1 character")
    if stale_hours <= 0:
        errors.append("stale_hours: Input should be greater than 0")
    return "; ".join(errors) if errors else None


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
    detail = _validate_cli_args(args.owner, args.repo, args.stale_hours)
    if detail is not None:
        print(f"error: invalid arguments: {detail}", file=sys.stderr)
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

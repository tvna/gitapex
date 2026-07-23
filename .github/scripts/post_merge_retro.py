#!/usr/bin/env python3
"""Open (with dedup) a merge-retrospective issue for a just-merged PR.

Issue #314 (sub-issue of #140): the minimal, GITHUB_TOKEN-only slice of
#140's post-merge-auto-retro gate cluster. On a PR closing with
``merged == true``, this script:

1. Searches for an existing retrospective issue for that PR, using the
   exact query shape #140 documents (imported, never re-derived):
   ``repo:{owner}/{repo} type:issue in:title "PR #{n}" "retro"``,
   unfiltered by state (open+closed) -- an interactive agent session may
   already have filed one via skills/merge-retrospective/SKILL.md.
2. If none is found, opens one titled ``Merge retrospective: PR #{n}``
   labeled ``retrospective`` -- reusing merge-retrospective's own
   title/label identity convention exactly (#140 calls this predicate
   ``retro-identity``).

Explicitly out of scope for this slice (see #314's own "Explicitly
deferred" section): the trusted-bot allowlist, the false-positive-prior
skip, the ledger, the 24-48h rescan, and any ``.gitapex/ssot.json``
registry wiring. The opened issue is a stub -- it does not enumerate
repairs; a human or a later interactive agent session fills that in per
skills/merge-retrospective/SKILL.md.

Deliberately stdlib-only and self-contained -- this repository keeps
``.github/scripts/*.py`` files independent of one another rather than
importing across them (see scan_retrospective_gate_drift.py's own
docstring for the same rationale), even though the retry-with-backoff
shape below mirrors that script's own ``_fetch_issues_page``.

Untrusted input note: ``--pr-title`` carries attacker-influenced text (a
PR title, from a possibly-untrusted fork). It never touches a shell
command in this script or its caller workflow -- the workflow passes it
through an intermediate ``env:`` var (never spliced into a ``run:``
string), and this script only ever places it inside a JSON request body,
never a shell invocation -- so no command-injection surface exists.

Usage::

    python3 .github/scripts/post_merge_retro.py \\
        --owner tvna --repo gitapex --pr-number 314 \\
        --pr-title "feat: add foo" --pr-url https://github.com/tvna/gitapex/pull/314

Environment variables:
    GITHUB_TOKEN  GitHub token with issues:write (the default Actions
                  token's ``issues: write`` permission suffices).

Exit codes:
    0  A retrospective issue already existed, or one was opened.
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
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30
_RETRO_LABEL = "retrospective"


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST/Search API returns a non-recoverable error."""


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted env-var-derived segments; the
    # one attacker-influenced value (pr_title) travels only in the JSON
    # body of a POST, never in the URL itself.
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
) -> dict[str, Any]:
    """Call the GitHub API, retrying transient (network / 5xx) failures up
    to three attempts -- mirrors scan_retrospective_gate_drift.py's own
    `_fetch_issues_page` retry shape."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    last_code = 0
    last_body = ""
    for attempt in range(1, 4):
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
            # Covers urllib.error.URLError (an OSError subclass, e.g. DNS/
            # connection failures) and TimeoutError/ConnectionError, plus a
            # body read that starts (headers arrive, `last_code` gets set)
            # but stalls or is cut short.
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            return json.loads(last_body) if last_body else {}
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for {method} {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < 3:
            sleeper(attempt * 5)

    raise GitHubApiError(f"{method} {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def dedup_query(owner: str, repo: str, pr_number: int) -> str:
    """The exact search-query shape #140 documents (imported, not
    re-derived): ``repo:{repo} type:issue in:title "PR #{n}" "retro"``."""
    return f'repo:{owner}/{repo} type:issue in:title "PR #{pr_number}" "retro"'


def find_existing_retro_issue(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> int | None:
    """Return the number of an existing retro issue for `pr_number`, or
    None if the dedup search finds none. Unfiltered by state (open+closed)
    -- an interactive agent session may already have filed one."""
    sleeper = sleeper if sleeper is not None else time.sleep
    query = dedup_query(owner, repo, pr_number)
    url = f"{_API_ROOT}/search/issues?{urllib.parse.urlencode({'q': query})}"
    result = _call("GET", url, token, opener, sleeper)
    items = result.get("items", [])
    return int(items[0]["number"]) if items else None


def open_retro_issue(
    owner: str,
    repo: str,
    pr_number: int,
    pr_title: str,
    pr_url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    """Open a retrospective issue for `pr_number`, titled and labeled per
    merge-retrospective's own identity convention (imported verbatim, never
    re-derived): title ``Merge retrospective: PR #N``, label
    ``retrospective``. The body is an unfilled stub -- enumerating repairs
    is explicitly out of scope for this slice (see #314's own deferrals)."""
    sleeper = sleeper if sleeper is not None else time.sleep
    title = f"Merge retrospective: PR #{pr_number}"
    body = (
        f'Retrospective for PR #{pr_number} ("{pr_title}").\n\n'
        f"Refs #{pr_number}\n"
        f"PR: {pr_url}\n\n"
        "Automated stub opened by the post-merge-auto-retro gate "
        "(issue #314, minimal slice of #140). This slice only opens and "
        "dedups the issue -- it does not enumerate repairs, classify them, "
        "or propose gates. Fill in the Repairs section per "
        "skills/merge-retrospective/SKILL.md before closing this issue.\n"
    )
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues"
    payload = {"title": title, "body": body, "labels": [_RETRO_LABEL]}
    result = _call("POST", url, token, opener, sleeper, body=payload)
    return int(result["number"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open (with dedup) a merge-retrospective issue for a merged PR."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument("--pr-number", required=True, type=int, help="The merged PR's number")
    parser.add_argument("--pr-title", default="", help="The merged PR's title (untrusted; JSON body only)")
    parser.add_argument("--pr-url", default="", help="The merged PR's HTML URL")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        existing = find_existing_retro_issue(args.owner, args.repo, args.pr_number, token)
        if existing is not None:
            print(
                f"Retrospective issue already exists for PR #{args.pr_number}: "
                f"#{existing} -- skipping create."
            )
            return 0
        issue_number = open_retro_issue(
            args.owner, args.repo, args.pr_number, args.pr_title, args.pr_url, token
        )
        print(f"Opened retrospective issue #{issue_number} for PR #{args.pr_number}.")
        return 0
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

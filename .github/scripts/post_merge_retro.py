#!/usr/bin/env python3
"""Open (with dedup) a merge-retrospective issue for a just-merged PR.

Issue #314 (sub-issue of #140): the minimal, GITHUB_TOKEN-only slice of
#140's post-merge-auto-retro gate cluster. On a PR closing with
``merged == true``, this script:

1. Searches for an existing retrospective issue for that PR, matching the
   same title/label identity predicate used at creation time (this
   module's own ``open_retro_issue``, via the shared ``_retro_title``):
   exact-phrase title ``chore(retrospective): merge retrospective for PR
   #{n}`` plus the ``retrospective`` label -- unfiltered by state
   (open+closed) -- an interactive agent session may already have filed
   one via skills/merge-retrospective/SKILL.md.
2. If none is found, opens one titled the same way, labeled
   ``retrospective``.

Issue #341: the title used here previously was the literal
``Merge retrospective: PR #{n}`` shape, on the mistaken belief (inherited
from #140's own text) that this was "gitapex's own existing retro
convention." ``skills/merge-retrospective/SKILL.md`` itself says that
exact shape is only its generic *fallback* title, for repos with neither
an issue template nor their own convention -- and this repo has had its
own convention since issue #118 (2026-07-16, predating #140/#314):
``chore(retrospective): merge retrospective for PR #{n}``. Both the
title and the dedup search phrase are derived from the single
``_retro_title`` function below so they cannot re-diverge silently the
way they did before (the title and the query phrase, and their
docstrings, are the two `see also #341` regression is guarding against).

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
string) -- so no command-injection surface exists. It is also never
placed in the opened issue's body: republishing a fork-controlled title
verbatim into a bot-authored issue would let an ``@user``/``@org``
mention or Markdown in the title inject formatting or trigger unwanted
notifications, so ``open_retro_issue`` accepts and discards it rather
than embedding it.

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

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Call the GitHub API, retrying transient (network / 5xx) failures up
    to `max_attempts` attempts -- mirrors scan_retrospective_gate_drift.py's
    own `_fetch_issues_page` retry shape.

    `max_attempts` defaults to 3 for idempotent (GET/search) calls. The
    issue-creation POST is not idempotent -- a lost or truncated response
    after GitHub has already created the issue would otherwise retry into
    a duplicate -- so its caller passes `max_attempts=1` to disable retry
    for that specific call (RFC 9110 SS9.2.2)."""
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
        if attempt < max_attempts:
            sleeper(attempt * 5)

    raise GitHubApiError(f"{method} {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def _retro_title(pr_number: int) -> str:
    """The single source of truth for this repository's actual
    retrospective title convention (established since issue #118,
    2026-07-16): ``chore(retrospective): merge retrospective for PR #N``.

    Both `dedup_query` and `open_retro_issue` call this function rather
    than each formatting their own title literal, so the search phrase and
    the created title can never re-diverge the way they did before issue
    #341's fix (both previously hardcoded the wrong, SKILL.md-fallback-only
    shape ``Merge retrospective: PR #N`` independently)."""
    return f"chore(retrospective): merge retrospective for PR #{pr_number}"


def dedup_query(owner: str, repo: str, pr_number: int) -> str:
    """Match the same title/label identity predicate used at creation
    time (this module's own `open_retro_issue`, via `_retro_title`): the
    standalone token "retro" does not prefix-match "retrospective" under
    GitHub's exact-match query syntax, so search the real title phrase
    combined with ``label:retrospective``."""
    title = _retro_title(pr_number)
    return f'repo:{owner}/{repo} type:issue in:title "{title}" label:{_RETRO_LABEL}'


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
    """Open a retrospective issue for `pr_number`, titled per
    `_retro_title` (this repository's actual established convention, not
    skills/merge-retrospective/SKILL.md's generic fallback shape) and
    labeled ``retrospective``. The body is an unfilled stub -- enumerating
    repairs is explicitly out of scope for this slice (see #314's own
    deferrals).

    `pr_title` is accepted (kept in the CLI/API surface for callers that
    already pass it) but deliberately never placed in the issue body: it
    is untrusted, fork-controlled text, and republishing it verbatim would
    let an `@user`/`@org` mention or Markdown in a PR title inject
    formatting or trigger unwanted notifications in this bot-authored
    issue. `pr_url` is safe to include as-is -- a GitHub PR URL is not
    free text."""
    del pr_title  # untrusted; deliberately not embedded in the issue body
    sleeper = sleeper if sleeper is not None else time.sleep
    title = _retro_title(pr_number)
    body = (
        f"Retrospective for PR #{pr_number}.\n\n"
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
    # max_attempts=1: issue creation is not idempotent -- see _call's
    # docstring -- so a lost/truncated response is never retried into a
    # duplicate issue.
    result = _call("POST", url, token, opener, sleeper, body=payload, max_attempts=1)
    return int(result["number"])


class _CliArgs(BaseModel):
    """Parsed-and-validated view of this script's own argparse namespace.
    ``owner``/``repo`` reject blank (argparse's own ``required=True`` only
    guarantees the flag was passed, not that its value is non-empty); ``pr_number``
    must be positive (GitHub issue/PR numbers are always >= 1). ``pr_title``/
    ``pr_url`` stay unconstrained -- ``pr_title`` in particular carries
    untrusted, fork-controlled text (see module docstring) that this script
    already never embeds anywhere, so no shape is imposed on it here either."""

    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    pr_number: int = Field(gt=0)
    pr_title: str = ""
    pr_url: str = ""


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
    try:
        cli_args = _CliArgs(
            owner=args.owner, repo=args.repo, pr_number=args.pr_number,
            pr_title=args.pr_title, pr_url=args.pr_url,
        )
    except ValidationError as exc:
        detail = "; ".join(
            f"{e['loc'][0] if e['loc'] else 'args'}: {e['msg'].removeprefix('Value error, ')}" for e in exc.errors()
        )
        print(f"error: invalid arguments: {detail}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        existing = find_existing_retro_issue(cli_args.owner, cli_args.repo, cli_args.pr_number, token)
        if existing is not None:
            print(
                f"Retrospective issue already exists for PR #{cli_args.pr_number}: "
                f"#{existing} -- skipping create."
            )
            return 0
        issue_number = open_retro_issue(
            cli_args.owner, cli_args.repo, cli_args.pr_number, cli_args.pr_title, cli_args.pr_url, token
        )
        print(f"Opened retrospective issue #{issue_number} for PR #{cli_args.pr_number}.")
        return 0
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

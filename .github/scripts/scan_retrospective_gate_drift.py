#!/usr/bin/env python3
"""Report (and fail CI on) retrospective issues with no citing commit.

Issue #297 (refs #187, #242, #246): `merge-retrospective`'s Step 0
requires, every cycle, a manual search of every `retrospective`-labelled
issue for a commit on `main` citing it. Issue #187 proposed automating
this as a meta-gate; #242 and #246 each ran that search by hand again and
confirmed the meta-gate itself was never built. This script mechanizes
Step 0's own method (list `retrospective`-labelled issues, unfiltered by
state; search `main`'s commit history for a citing `#N`) and fails when
the count of issues with zero citing commits exceeds a threshold.

Design: docs/superpowers/specs/2026-07-22-retrospective-gate-drift-design.md

Split into pure logic (fixture-testable, no I/O) and I/O glue (GitHub REST
API over `urllib`, plus a local `git log`). Deliberately stdlib-only and
does not import `sync_pr_publish.py` -- this repository keeps
`.github/scripts/*.py` files independently self-contained (see
`gate_skill_rename_lifecycle.py`'s own docstring for the same rationale)
even though the retry-with-backoff shape below mirrors
`sync_pr_publish.apply_call`.

Usage::

    python3 .github/scripts/scan_retrospective_gate_drift.py \\
        --owner tvna --repo gitapex --ref HEAD --threshold 20

Environment variables:
    GITHUB_TOKEN  GitHub token with read access to issues (the default
                  Actions token's `issues: read` permission suffices).

Exit codes:
    0  No-citation count does not exceed the threshold.
    1  No-citation count exceeds the threshold, or a GitHub API / git
       error prevented the check from completing (never silently
       reported as "zero issues found").
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_THRESHOLD = 20
DEFAULT_LABEL = "retrospective"

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30
_PER_PAGE = 100

# Record separator (0x1e) / unit separator (0x1f): neither appears in real
# commit messages, so they safely delimit `git log` entries and fields
# without a risk of an attacker-controlled commit message forging a fake
# boundary the way a printable delimiter (comma, pipe, newline) could.
_LOG_FORMAT = "%x1e%H%x1f%B"


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


class GitLogError(RuntimeError):
    """Raised when the local `git log` invocation fails."""


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def _citation_pattern(issue_number: int) -> re.Pattern[str]:
    # Digit-boundary-aware: "#187" matches, but neither "#1870" nor "#2187"
    # does -- a plain substring or `\b`-based match would treat "7" and "0"
    # (both word characters) as a boundary and false-positive on unrelated
    # larger issue/PR numbers that happen to contain the target as a prefix
    # or suffix.
    return re.compile(rf"(?<!\d)#{issue_number}(?!\d)")


def citation_count(commit_messages: list[str], issue_number: int) -> int:
    """Count how many of `commit_messages` cite `issue_number`."""
    pattern = _citation_pattern(issue_number)
    return sum(1 for message in commit_messages if pattern.search(message))


def find_no_citation_issues(issue_numbers: list[int], commit_messages: list[str]) -> list[int]:
    """Return the subset of `issue_numbers` with zero citing commits."""
    return [n for n in issue_numbers if citation_count(commit_messages, n) == 0]


def evaluate(no_citation_count: int, threshold: int) -> bool:
    """Return True iff `no_citation_count` exceeds `threshold`."""
    return no_citation_count > threshold


def format_report(no_citation_issues: list[int], total_issues: int, threshold: int) -> str:
    """Human-readable report, printed to stdout and captured in the CI step summary."""
    no_citation_count = len(no_citation_issues)
    lines = [
        f"Retrospective gate-drift report: {no_citation_count} of {total_issues} "
        f"'{DEFAULT_LABEL}'-labelled issues have no citing commit on main "
        f"(threshold: {threshold}).",
    ]
    if no_citation_issues:
        lines.append("Issues with no citing commit:")
        lines.extend(f"  #{n}" for n in sorted(no_citation_issues))
    else:
        lines.append(f"Every '{DEFAULT_LABEL}'-labelled issue has at least one citing commit.")
    if evaluate(no_citation_count, threshold):
        lines.append(f"FAIL: {no_citation_count} exceeds threshold {threshold}.")
    else:
        lines.append(f"PASS: {no_citation_count} does not exceed threshold {threshold}.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted env-var-derived segments.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def _fetch_issues_page(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> list[dict[str, Any]]:
    """GET one page of the issues-list endpoint, retrying transient failures."""
    last_code = 0
    last_body = ""
    for attempt in range(1, 4):
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
            # Covers urllib.error.URLError (an OSError subclass, e.g. DNS/
            # connection failures) and TimeoutError/ConnectionError, plus a
            # body read that starts (headers arrive, `last_code` gets set)
            # but stalls or is cut short -- IncompleteRead is not an OSError
            # subclass, so it needs its own arm. Without this, a body-read
            # failure escapes retry entirely and crashes the whole scan
            # instead of getting the three attempts promised below.
            last_code = 0
            last_body = str(error)

        if 200 <= last_code < 300:
            page: list[dict[str, Any]] = json.loads(last_body)
            return page
        print(f"Attempt {attempt}: HTTP {_format_code(last_code)} for GET {url}", file=sys.stderr)
        if last_code != 0 and last_code < 500:
            break
        if attempt < 3:
            sleeper(attempt * 5)

    raise GitHubApiError(f"GET {url} failed: HTTP {_format_code(last_code)}: {last_body}")


def _format_code(code: int) -> str:
    return str(code) if code else "network error"


def list_labelled_issues(
    owner: str,
    repo: str,
    label: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> list[int]:
    """Return issue numbers carrying `label`, unfiltered by state (matches
    merge-retrospective's own Step 0 method, which deliberately does not
    limit the search to open issues)."""
    sleeper = sleeper if sleeper is not None else time.sleep
    issue_numbers: list[int] = []
    page = 1
    while True:
        url = (
            f"{_API_ROOT}/repos/{owner}/{repo}/issues"
            f"?labels={label}&state=all&per_page={_PER_PAGE}&page={page}"
        )
        items = _fetch_issues_page(url, token, opener, sleeper)
        if not items:
            break
        for item in items:
            # The issues-list endpoint also returns pull requests; a
            # retrospective issue is never a PR, so this is a defensive
            # exclusion rather than an expected real-world hit.
            if "pull_request" in item:
                continue
            issue_numbers.append(item["number"])
        if len(items) < _PER_PAGE:
            break
        page += 1
    return issue_numbers


def git_commit_messages(
    ref: str,
    cwd: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Return the full message (subject + body) of every commit reachable
    from `ref`, via a local `git log` in `cwd`."""
    result = runner(
        ["git", "log", ref, f"--pretty=format:{_LOG_FORMAT}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitLogError(f"git log {ref} failed: {result.stderr.strip()}")

    messages: list[str] = []
    for entry in result.stdout.split("\x1e"):
        if not entry:
            continue
        _sha, _, message = entry.partition("\x1f")
        messages.append(message.rstrip("\n"))
    return messages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _CliArgs(BaseModel):
    """Parsed-and-validated view of this script's own argparse namespace.
    ``owner``/``repo`` reject blank (argparse's own ``required=True`` only
    guarantees the flag was passed, not that its value is non-empty);
    ``ref``/``cwd``/``label`` likewise, since each is used as a real path/ref/
    query fragment downstream and an empty value there was never a
    meaningful input. ``threshold`` keeps its bare ``int`` type -- unlike the
    other fields it has no natural non-negative floor (a caller intentionally
    passing a negative threshold to force a hard fail is not a malformed
    input, just an unusual one), so no extra constraint is added."""

    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    ref: str = Field(default="HEAD", min_length=1)
    cwd: str = Field(default=".", min_length=1)
    label: str = Field(default=DEFAULT_LABEL, min_length=1)
    threshold: int = DEFAULT_THRESHOLD


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report and fail on retrospective-labelled issues with no citing commit."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument("--ref", default="HEAD", help="Git ref to search for citing commits (default: HEAD)")
    parser.add_argument("--cwd", default=".", help="Repository working directory for git log (default: .)")
    parser.add_argument("--label", default=DEFAULT_LABEL, help=f"Issue label to search (default: {DEFAULT_LABEL})")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Fail if the no-citation count exceeds this value (default: {DEFAULT_THRESHOLD})",
    )
    args = parser.parse_args(argv)
    try:
        cli_args = _CliArgs(
            owner=args.owner, repo=args.repo, ref=args.ref, cwd=args.cwd,
            label=args.label, threshold=args.threshold,
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
        issue_numbers = list_labelled_issues(cli_args.owner, cli_args.repo, cli_args.label, token)
        commit_messages = git_commit_messages(cli_args.ref, cli_args.cwd)
    except (GitHubApiError, GitLogError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    no_citation_issues = find_no_citation_issues(issue_numbers, commit_messages)
    print(format_report(no_citation_issues, len(issue_numbers), cli_args.threshold))
    return 1 if evaluate(len(no_citation_issues), cli_args.threshold) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deny mcp__github__issue_write (method create) when a `gate-proposal`
filing carries no fresh backlog-sweep proof (issue #1806).

Issue #1806's own Facts: issues #1724/#1784 duplicated earlier proposals
(#1568, and a row inside #1571) because `merge-retrospective`'s Step 1
treats the pre-existing backlog as out of scope and Step 5's exact-title
dedup can only match a re-run of the same retro. The new Step 4b sweeps
the backlog before filing; this hook is the deterministic proof that
sweep ran against the *current* backlog: the body must carry one line of
fixed shape

    Dedup-sweep: <N> open gate-proposal issues at <ISO-8601>; verdict NEW

generated only by
`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`'s own
`build_dedup_sweep_line` (never hand-typed), and `<N>` must equal a live
re-fetch of the open `gate-proposal` population. Denies when the line is
absent, ambiguous (two or more), malformed, or stale.

Accepted verdicts are `NEW` and `DUPLICATE-OF #<N>`: a deliberate,
narrow superset of the issue's literal `verdict NEW` shape. Row 3 of that
same issue requires a `DUPLICATE-OF` repair to still create its
standalone issue through the Step 5 flow -- a flow whose body this hook
already grades -- so a hook accepting only `verdict NEW` would deny
exactly the concurrent-safe duplicate path the issue mandates. The
count-match (not the verdict word) is the freshness proof either way;
which `#<N>` a duplicate names is verified by the calling skill
(re-fetching #N, per row 2), never by this hook.

Scope notes, named rather than left implicit:

- Agent-path only: hooks mediate `mcp__github__issue_write` calls. A
  human filing from the GitHub web UI (as the owner did for #1806
  itself) never passes through here -- direct owner filings stay
  possible, which is why no waiver line exists: every agent-side caller
  (Step 5) already holds the generator, so there is no legitimate
  agent-side filing that cannot carry the line.
- The timestamp is validated for shape only (real calendar instant, UTC
  `YYYY-MM-DDTHH:MM:SSZ`); no freshness window is enforced -- the issue
  specifies count-match, not recency, and a window would be a speculative
  addition beyond what was asked.
- Fail-closed, matching `gitapex_check_pr_duplicate_issue.py`'s own
  posture: missing token or unfetchable count denies. A hook-runner
  timeout fails open per the runner contract (same disclosed limit as
  `gitapex_gate_independent_review_pending.py`).

Reuses that sibling's REST/pagination/fail-closed shape (adapted from
pulls to the issues endpoint) and carries its own copies of the
fence-stripping patterns (an underscore-prefixed helper is not a shared
reuse surface, per that module's own documented convention).

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"owner":"tvna","repo":"gitapex","method":"create","labels":["gate-proposal"],"body":"..."}' \\
        | python3 hooks/gitapex_check_gate_proposal_dedup_sweep.py

Exit codes:
    0  Allow -- not a gate-proposal creation, or a single well-formed
       sweep line whose count matches the live population.
    1  Deny -- with a "FAIL: ..." reason on stderr. Also 1, with an
       "error: ..." reason instead, when the payload itself could not be
       read at all -- never an uncaught traceback.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
# Per-request budget mirrors gitapex_check_pr_duplicate_issue.py's own
# (10s timeout, one 5s-spaced retry). Its worst case over _MAX_PAGES --
# roughly 25s per page, ~250s total -- does NOT fit hooks.json's own
# 130s timeout for this entry, so this module additionally bounds its own
# total fetch time to _TIME_BUDGET_SECONDS and denies fail-closed before
# the runner can kill the process (which would fail open per the runner
# contract). Realistic backlogs are one page; the bound only bites under
# sustained degradation, exactly when failing open would be wrong.
_HTTP_TIMEOUT_SECONDS = 10
_MAX_ATTEMPTS = 2
_PER_PAGE = 100
_MAX_PAGES = 10
_TIME_BUDGET_SECONDS = 100.0

_GATE_PROPOSAL_LABEL = "gate-proposal"

# Ported copies (not imports) of gitapex_check_pr_duplicate_issue.py's own
# fence-stripping patterns -- see that module's docstring for the
# CommonMark rationale each carries. An illustrative sweep line inside a
# fenced example must never count as proof, the same false-positive class
# the waiver hooks already close.
_CONTAINER_PREFIX = r"[ \t\r]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+|>[ \t]?)*"
_FENCE_RE = re.compile(rf"^{_CONTAINER_PREFIX}(```|~~~).*?^{_CONTAINER_PREFIX}\1", re.DOTALL | re.MULTILINE)
_UNTERMINATED_FENCE_RE = re.compile(rf"^{_CONTAINER_PREFIX}(?:```|~~~).*\Z", re.DOTALL | re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# An indented code block (4 spaces or a tab) is code per CommonMark even
# without fences -- an illustrative sweep line shown that way must not
# count as proof either. Stripped after fences (a fence may itself be
# indented) and before inline code. Generator-emitted lines always start
# at column 0, so stripping indented lines can only deny, never allow.
_INDENTED_CODE_RE = re.compile(r"^(?:[ ]{4}|\t).*$", re.MULTILINE)

_SWEEP_RE = re.compile(
    r"^[ \t]*Dedup-sweep:[ \t]*(\d+)[ \t]+open[ \t]+gate-proposal[ \t]+issues[ \t]+at[ \t]+(\S+)"
    r"[ \t]*;[ \t]*verdict[ \t]+(NEW|DUPLICATE-OF[ \t]+#\d+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def _strip_fences(text: str | None) -> str:
    without_fences = _FENCE_RE.sub("", text or "")
    without_fences = _UNTERMINATED_FENCE_RE.sub("", without_fences)
    without_indented = _INDENTED_CODE_RE.sub("", without_fences)
    return _INLINE_CODE_RE.sub("", without_indented)


def find_sweep_lines(body_text: str | None) -> list[tuple[int, str, str]]:
    """Return [(count, timestamp, verdict), ...] for every sweep-shaped
    line outside fenced/inline code. Empty when the body carries no proof
    line at all."""
    return [
        (int(count), timestamp, verdict) for count, timestamp, verdict in _SWEEP_RE.findall(_strip_fences(body_text))
    ]


def _default_opener(request: urllib.request.Request) -> Any:
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def _call(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    max_attempts: int = _MAX_ATTEMPTS,
) -> Any:
    """GET the GitHub API, retrying transient (network/5xx) failures up to
    `max_attempts` times. Mirrors gitapex_check_pr_duplicate_issue.py's own
    `_call` shape. Returns unvalidated parsed JSON; callers shape-check it."""
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
            return json.loads(last_body) if last_body else {}
        if last_code != 0 and last_code < 500:
            break
        if attempt < max_attempts:
            sleeper(attempt * 5)

    code_display = str(last_code) if last_code else "network error"
    raise GitHubApiError(f"fetch-failed: HTTP {code_display}")


def fetch_open_gate_proposal_count(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
    max_pages: int = _MAX_PAGES,
) -> int:
    """Return the live count of open `gate-proposal`-labelled issues via
    the deterministic REST List Issues endpoint, paginated up to
    `max_pages`. Raises GitHubApiError on a non-recoverable fetch
    failure, a non-array response, or -- fail-closed -- when `max_pages`
    full pages still leave completeness unconfirmed (mirrors
    gitapex_check_pr_duplicate_issue.py's own pagination-bound rule).

    The population intentionally includes pull requests carrying the
    label (the endpoint returns both): Step 4b's own sweep reads the same
    population through `list_issues`, so both sides count identically.
    """
    sleeper = sleeper if sleeper is not None else time.sleep
    started = time.monotonic()
    total = 0
    for page in range(1, max_pages + 1):
        if time.monotonic() - started > _TIME_BUDGET_SECONDS:
            raise GitHubApiError(
                f"time-budget-exhausted: {_TIME_BUDGET_SECONDS:.0f}s elapsed before the open-issue "
                "listing completed -- denying fail-closed rather than trusting a partial count"
            )
        url = (
            f"{_API_ROOT}/repos/{owner}/{repo}/issues?state=open"
            f"&labels={urllib.parse.quote(_GATE_PROPOSAL_LABEL)}"
            f"&per_page={_PER_PAGE}&page={page}"
        )
        data = _call(url, token, opener, sleeper)
        if not isinstance(data, list):
            raise GitHubApiError(f"GET {url} returned {type(data).__name__}, expected a JSON array")
        if not data:
            break
        total += len(data)
        if len(data) < _PER_PAGE:
            break
    else:
        raise GitHubApiError(
            f"pagination-bound-reached: fetched {max_pages} page(s) "
            f"(up to {max_pages * _PER_PAGE} open gate-proposal issues) and the last page was still full -- "
            "cannot confirm every issue was counted"
        )
    return total


def _is_gate_proposal_filing(labels: Any) -> bool:
    # `None` (absent labels) means the filing cannot carry the label --
    # correctly out of scope. Any other non-list shape is malformed input
    # and denies fail-closed rather than silently downgrading to allow.
    if labels is None:
        return False
    if isinstance(labels, str):
        labels = [labels]
    if not isinstance(labels, list):
        raise ValueError(f"labels must be a string array, got {type(labels).__name__}")
    return any(isinstance(label, str) and label.lower() == _GATE_PROPOSAL_LABEL for label in labels)


def evaluate(
    owner: str,
    repo: str,
    method: str | None,
    labels: Any,
    body: str,
    token: str | None,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[bool, str]:
    """Return (passed, message) for the Dedup-sweep proof check."""
    if (method or "") != "create":
        return True, "not an issue creation -- nothing to sweep-check"
    try:
        gate_proposal = _is_gate_proposal_filing(labels)
    except ValueError as error:
        return False, f"malformed issue labels ({error}) -- failing closed"
    if not gate_proposal:
        return True, "not a gate-proposal filing -- nothing to sweep-check"

    sweeps = find_sweep_lines(body)
    if not sweeps:
        return False, (
            "this gate-proposal filing carries no 'Dedup-sweep: <N> open gate-proposal issues at "
            "<ISO-8601>; verdict NEW' proof line -- run the Step 4b backlog sweep and generate the "
            "line via skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py, never hand-typed"
        )
    if len(sweeps) > 1:
        return False, f"ambiguous filing: {len(sweeps)} Dedup-sweep lines found, exactly one is required"

    count, timestamp, _verdict = sweeps[0]
    try:
        _datetime.datetime.strptime(timestamp, _TIMESTAMP_FORMAT)
    except (ValueError, TypeError):
        return False, f"malformed Dedup-sweep timestamp: {timestamp!r} (expected UTC YYYY-MM-DDTHH:MM:SSZ)"

    if not token:
        return False, (
            "cannot verify the Dedup-sweep count against the live backlog: no GH_TOKEN/GITHUB_TOKEN "
            "in the environment (failing closed)"
        )

    try:
        live = fetch_open_gate_proposal_count(owner, repo, token, opener=opener, sleeper=sleeper)
    except GitHubApiError as error:
        return False, f"could not fetch the open gate-proposal count to verify the sweep ({error}) -- failing closed"

    if count != live:
        return False, (
            f"stale Dedup-sweep: the line claims {count} open gate-proposal issues but the live "
            f"backlog holds {live} -- re-run the Step 4b sweep against the current backlog"
        )
    return True, f"Dedup-sweep verified: {count} open gate-proposal issues at {timestamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a candidate gate-proposal issue body: deny when no fresh "
        "Dedup-sweep proof line is present or its count is stale."
    )
    parser.add_argument(
        "--payload",
        help="Path to a JSON file with owner/repo/method/labels/body; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    payload_source = args.payload or "stdin"
    try:
        raw = Path(args.payload).read_text(encoding="utf-8") if args.payload else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: payload file not found: {args.payload}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        print(f"error: payload ({payload_source}) is not valid UTF-8: {error}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        print(f"error: payload is not valid JSON: {error}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print(
            f"error: payload ({payload_source}) must be a JSON object, got {type(payload).__name__}",
            file=sys.stderr,
        )
        return 1

    for field_name in ("owner", "repo", "method", "body"):
        field_value = payload.get(field_name)
        if field_value is not None and not isinstance(field_value, str):
            print(
                f"error: payload ({payload_source}) field '{field_name}' must be a string, "
                f"got {type(field_value).__name__}",
                file=sys.stderr,
            )
            return 1

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    passed, message = evaluate(
        payload.get("owner") or "",
        payload.get("repo") or "",
        payload.get("method") or "",
        payload.get("labels"),
        payload.get("body") or "",
        token,
    )
    if passed:
        print(f"PASS: {message}")
        return 0
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

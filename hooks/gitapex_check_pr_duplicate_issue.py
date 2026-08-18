#!/usr/bin/env python3
"""Deny mcp__github__create_pull_request when another currently-open PR
already cites the same issue this new PR would resolve (issue #1197).

Issue #1197's own Facts: issues #1069/#1070 (two retrospective issues for
the same PR #1066, ~6 minutes apart) and, cited inside #1069's own repair
1, two independent sessions producing duplicate PRs #1066/#1067 for the
same source issue #1064 -- neither session detecting the other in flight.
`planning-a-branch-from-an-issue/SKILL.md` never checked for an existing open PR
targeting the same issue before creating a new one; this hook closes that
gap at PR-creation time.

Reuses `gitapex_check_pr_issue_acm_disclosure.extract_citations` directly (same
directory, plain Python import, matching this repository's own established
reuse convention: a *public* function is a genuine shared reuse surface,
an underscore-prefixed helper is not -- this module accordingly does not
import that module's own private `_call`/`_strip_fences`/etc., and instead
carries its own copies of those, matching every other hook in this family).

Citation semantics for "does another PR already cite this issue": the new
PR's own *resolving* set (Closes/Fixes/Resolves -- the issue(s) it would
actually close) is checked against every other open PR's own resolving
*and* context set (Closes/Fixes/Resolves/Refs/bare #N) -- issue #1197's own
Criterion text: "another currently-open PR already cites (via
`Closes`/`Fixes`/`Refs #N`) the same issue number the new PR would close."
A bare mention on the *other* PR (e.g. a parent tracking issue referenced
for context) still counts as "cites" under that literal text, even though
it would not itself auto-close anything.

Open PRs are fetched via the deterministic REST List Pull Requests
endpoint (`GET /repos/{owner}/{repo}/pulls?state=open`), paginated --
never the semantic Search API. Same reasoning issue #1197's own row 2
applies to `list_issues` vs. `search_issues`: an exact, deterministic
listing is the correct primitive for "does X exist," not a
natural-language-ranked search. Paginated up to `_MAX_PAGES` pages (1000
PRs at 100/page) as a named, disclosed bound -- fail-closed at the bound,
not a silent truncation: an empty or short final page is the only proof
pagination is actually complete, so `fetch_open_pull_requests` raises
(denying the PR, per the fail-closed posture below) when `_MAX_PAGES` is
exhausted and the last page fetched was still full, rather than silently
returning a possibly-incomplete list a duplicate on the next page could
slip past. A repository with more than `_MAX_PAGES * _PER_PAGE` open PRs
at once is expected to use the `Duplicate-PR-waiver` escape hatch below
to get a PR past this hook until that count drops.

Escape hatch (issue #1197's own Constraint: "must include an escape
hatch, not an unconditional hard block"): a `Duplicate-PR-waiver: <reason>`
line anywhere in the new PR's own body, checked the same way
`gitapex_check_acm_present_or_waiver.py`'s own `_ACM_WAIVER_RE` is -- a non-empty
reason required, fenced/inline-code spans stripped first so an
illustrative example of the waiver's own syntax (in this hook's own PR
body, for instance) is never misdetected as a real waiver.

Fail-closed, explicitly, matching `gitapex_check_pr_issue_acm_disclosure.py`'s own
named posture: no GH_TOKEN/GITHUB_TOKEN, or a persistent fetch failure,
denies rather than silently allowing a duplicate through. A missing token
is a single global short-circuit (checked once a resolving citation exists
at all, before any fetch is attempted).

Every deny message names only issue numbers and PR numbers -- never
another PR's own title or body text, which is attacker-influenced text on
a public repository (mirrors gitapex_check_pr_issue_acm_disclosure.py's own
identical rule and rationale).

Residual risk, named rather than left implicit (deterministic-gate-quality
audit, PR #1215): this only guards `create_pull_request`, so editing an
existing PR's body afterward to add a resolving citation is not re-checked
by this hook, and any PR opened outside this agent-mediated path at all
(the GitHub web UI, `gh`, or a direct API call) is never checked -- no
CI-side backstop exists for this gate yet. A hook-runner timeout also does
not block the tool call under Claude Code's own hook contract, so an API
outage severe enough to exceed hooks.json's own timeout for this entry
still fails this gate open despite the fail-closed design below; see
`hooks/check-pr-duplicate-issue.sh`'s own comment for the worst-case
latency arithmetic that timeout is sized against.

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"owner":"tvna","repo":"gitapex","title":"...","body":"Closes #1"}' \\
        | python3 hooks/gitapex_check_pr_duplicate_issue.py

Exit codes:
    0  Allow -- no resolving citation on the new PR, a waiver is present,
       or no other open PR cites the same issue(s).
    1  Deny -- at least one resolving-cited issue is already cited by
       another open PR, with a "FAIL: ..." reason on stderr. Also 1, with
       an "error: ..." reason instead, when the payload itself could not
       be read at all -- never an uncaught traceback.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gitapex_check_pr_issue_acm_disclosure as citation_extractor

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
# 10s, not gitapex_check_pr_issue_acm_disclosure.py's 20s: that sibling fetches
# one issue; this module can fetch up to _MAX_PAGES pages in the same run, so
# its own per-request budget must be smaller for the worst case below to fit
# hooks.json's own timeout for this entry (deterministic-gate-quality audit,
# PR #1215 -- the prior 20s value made the worst case below exceed even a
# since-widened hooks.json timeout, and Claude Code's own hook contract does
# not block the tool call on a timed-out hook, so that overrun was a silent
# fail-OPEN on the exact GitHub-API-degraded case this fail-closed design
# exists for).
_HTTP_TIMEOUT_SECONDS = 10
_MAX_ATTEMPTS = 2
_PER_PAGE = 100
# Named, disclosed bound (module docstring) -- not a silent truncation.
# Worst-case latency this implies, with _HTTP_TIMEOUT_SECONDS=10 and the
# attempt*5 retry backoff below: (_MAX_PAGES - 1) successful pages at 10s
# each, plus one final page exhausting both attempts (2*10 + 5), so
# 9*10 + 25 = 115s -- hooks.json's own timeout for this hook's entry must
# stay comfortably above that figure, or this bound degrades from "fails
# closed" to "fails open on hook-runner cancellation" again.
_MAX_PAGES = 10

_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
# An *unterminated* fence opener (no matching close anywhere in the rest of
# the body) is not covered by `_FENCE_RE` above, which requires a matching
# close to match at all -- deterministic-gate-quality audit, PR #1215,
# live-verified: GitHub renders an unterminated ``` to the end of the
# rendered body as code, but this checker previously left that text
# completely unstripped, so a `Duplicate-PR-waiver:` line a human reader
# sees as an illustrative code example was matched as a real waiver. Runs
# after `_FENCE_RE` (so a well-paired fence is stripped as such, not
# double-counted here) and before `_INLINE_CODE_RE` below (a bare "```" is
# itself two single backticks; running inline-code stripping first would
# eat into it before this pattern ever saw it).
_UNTERMINATED_FENCE_RE = re.compile(r"```.*\Z|~~~.*\Z", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

_WAIVER_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*Duplicate-PR-waiver[ \t]*:[ \t]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def _strip_fences(text: str | None) -> str:
    without_fences = _FENCE_RE.sub("", text or "")
    without_fences = _UNTERMINATED_FENCE_RE.sub("", without_fences)
    return _INLINE_CODE_RE.sub("", without_fences)


def has_duplicate_waiver(body_text: str | None) -> bool:
    """Return True iff `body_text` carries a `Duplicate-PR-waiver: <reason>` line."""
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = _strip_fences(normalized)
    return bool(_WAIVER_RE.search(normalized))


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
    `max_attempts` times. Mirrors gitapex_check_pr_issue_acm_disclosure.py's own
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


def fetch_open_pull_requests(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
    max_pages: int = _MAX_PAGES,
) -> list[dict[str, Any]]:
    """Return [{'number': int, 'title': str, 'body': str}, ...] for every
    open PR, via the deterministic REST List Pull Requests endpoint,
    paginated up to `max_pages` (see module docstring). Raises
    GitHubApiError on a non-recoverable fetch failure, a non-array
    response body, or -- fail-closed, not a silent truncation -- when
    `max_pages` is exhausted and the last fetched page was still full
    (`_PER_PAGE` items), meaning completeness cannot be confirmed: an
    empty or short page is the only proof there is no further page to
    check, and neither occurred."""
    sleeper = sleeper if sleeper is not None else time.sleep
    results: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = f"{_API_ROOT}/repos/{owner}/{repo}/pulls?state=open&per_page={_PER_PAGE}&page={page}"
        data = _call(url, token, opener, sleeper)
        if not isinstance(data, list):
            raise GitHubApiError(f"GET {url} returned {type(data).__name__}, expected a JSON array")
        if not data:
            break
        for item in data:
            if not isinstance(item, dict):
                continue
            number = item.get("number")
            if not isinstance(number, int):
                continue
            title = item.get("title")
            body = item.get("body")
            results.append(
                {
                    "number": number,
                    "title": title if isinstance(title, str) else "",
                    "body": body if isinstance(body, str) else "",
                }
            )
        if len(data) < _PER_PAGE:
            break
    else:
        # The loop ran to completion (`max_pages` full pages, `range`
        # exhausted) without ever taking either `break` above -- the last
        # page fetched was still full, so a further page may exist.
        # Silently returning `results` here would let a duplicate on page
        # `max_pages + 1` bypass this hook entirely; this repository's own
        # "fail closed, including on INDETERMINATE" posture applies to
        # exactly this case.
        raise GitHubApiError(
            f"pagination-bound-reached: fetched {max_pages} page(s) "
            f"(up to {max_pages * _PER_PAGE} open PRs) and the last page was still full -- "
            "cannot confirm every open PR was checked"
        )
    return results


def evaluate(
    owner: str,
    repo: str,
    title: str,
    body: str,
    token: str | None,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[bool, str]:
    """Return (passed, message) for the duplicate-issue-citing-PR check.

    `token` may be falsy -- a missing token is a single global short-circuit
    fail-closed deny (see module docstring), not attempted per-issue."""
    if has_duplicate_waiver(body):
        return True, "explicit Duplicate-PR-waiver present -- duplicate-work check bypassed"

    resolving, _context = citation_extractor.extract_citations(owner, repo, title, body)
    if not resolving:
        return True, "no resolving (Closes/Fixes/Resolves) citation on this PR -- nothing to duplicate-check"

    if not token:
        cited = ", ".join(f"#{n}" for n in resolving)
        return False, (
            f"cannot verify {cited} against other open PRs: no GH_TOKEN/GITHUB_TOKEN "
            "in the environment (failing closed)"
        )

    try:
        open_prs = fetch_open_pull_requests(owner, repo, token, opener=opener, sleeper=sleeper)
    except GitHubApiError as error:
        return False, f"could not fetch open pull requests to check for duplicates ({error}) -- failing closed"

    conflicts: list[tuple[int, int]] = []
    for pr in open_prs:
        pr_resolving, pr_context = citation_extractor.extract_citations(owner, repo, pr["title"], pr["body"])
        pr_cited = set(pr_resolving) | set(pr_context)
        for issue_number in sorted(set(resolving) & pr_cited):
            conflicts.append((issue_number, pr["number"]))

    if conflicts:
        detail = "; ".join(
            f"#{issue_number} already cited by open PR #{pr_number}" for issue_number, pr_number in conflicts
        )
        return False, (
            f"{detail} -- this looks like duplicate work against an issue another "
            "open PR already targets. If this second PR is genuinely intentional "
            "(e.g. splitting a large fix across two PRs), add a "
            "`Duplicate-PR-waiver: <reason>` line to this PR's body and retry."
        )
    return True, "no other open PR cites the same issue(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a candidate PR's title/body: deny if another currently-open "
        "PR already cites the same issue this PR would resolve."
    )
    parser.add_argument(
        "--payload",
        help="Path to a JSON file with owner/repo/title/body; reads standard input when omitted.",
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

    for field_name in ("owner", "repo", "title", "body"):
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
        payload.get("title") or "",
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

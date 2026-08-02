#!/usr/bin/env python3
"""Deny mcp__github__create_pull_request when a Closes/Fixes-cited issue
lacks ACM/waiver disclosure, carries a 'tracking' waiver, or is closed.

Issue #657: hooks/check-issue-acm-disclosure.sh guards issue *creation*
(mcp__github__issue_write method=="create") but nothing guarded PR
*creation* -- a PR could be opened against an issue that never carried an
ACM/waiver (pre-hook issues, web-UI-created issues, and specifically
fixing-a-reported-issue's bare defect issues, which by design carry
neither until its own new step posts a `defect` waiver). This hook
closes that gap: "an Issue's ACM (or waiver) is the sole authority for
what should be solved; a PR is the act of solving it."

Reuses hooks/check_acm_present_or_waiver.py directly (`has_acm_disclosure`,
`waiver_category`, both built on the one `_ACM_WAIVER_RE` this module does
not duplicate) rather than a fifth copy of that regex logic. Both files
live in hooks/, so a plain `import check_acm_present_or_waiver` resolves
via Python's own sys.path[0]-is-the-script's-own-directory behavior when
this script runs standalone (`python3 hooks/check_pr_issue_acm_disclosure.py`),
and via this repository's own pyproject.toml `pythonpath = [..., "hooks"]`
when imported directly by its test suite.

Citation vocabulary:
- "resolving" (ACM-gated): GitHub's own real closing-keyword set --
  close/closes/closed/fix/fixes/fixed/resolve/resolves/resolved,
  case-insensitive, an optional colon, matched in the PR *body* only
  (GitHub never treats a title keyword as auto-closing -- see
  docs.github.com's own "Linking a pull request to an issue" page).
  Deliberately broader than this repository's own documented
  Closes/Fixes/Refs convention (skills/merge-retrospective/SKILL.md,
  skills/explaining-the-work/SKILL.md) -- a PR body reading "Resolves
  #123" really does auto-close #123 on GitHub, so excluding it here
  would be a real bypass of this hook's whole purpose, not a style
  choice. Not back-porting this wider vocabulary to those other skills'
  docs in this change -- out of scope; a possible small follow-up.
- "context-only" (not ACM-gated): a bare `Refs #N`/`References #N`, or a
  bare `#N` with no keyword at all, in either title or body. Counts
  toward "the PR cites *some* issue" (a bare PR citing nothing at all is
  still denied) but is never itself checked for ACM/waiver -- e.g. a
  parent tracking issue cited for context alongside a Closes-cited child.
- `Closes #12, #34` (a keyword followed by a comma-separated list): only
  `#12` actually resolves on GitHub -- its own docs say to repeat the
  keyword per issue ("resolves #10, resolves #123"), not to list bare
  numbers after one keyword. This module's regex matches that real
  behavior by construction (each match requires its own keyword); `#34`
  falls through to the bare-number context-only bucket instead.
- `owner/repo#N` cross-repo citations: a named non-goal for v1. Excluded
  from every bucket -- the bare-number regex's negative lookbehind
  rejects a `#` directly preceded by a word character, so `repo#N` never
  matches. Fetching a foreign repository's issue is out of scope.

Fenced code blocks (``` and ~~~) are stripped before any scan -- a
materially worse false-positive class here than in the table/waiver
checkers this module reuses: an example or quoted PR-body snippet inside
a fence could otherwise read as a real resolution claim.

Fail-closed, explicitly (issue #657's own named trade-off, matching this
repository's general "fail closed, including on INDETERMINATE" posture):
when this hook cannot determine a resolving-cited issue's ACM/waiver
state -- no GH_TOKEN/GITHUB_TOKEN in the environment, or the GitHub API
call fails after retries -- it denies, at the cost of blocking all PR
creation during a transient GitHub API outage. A missing token is a
single global short-circuit before any fetch is attempted (every fetch
would fail identically and there is no reason to pay N request round
trips to learn that); a genuine per-issue fetch failure (404, persistent
5xx) is reported per issue instead. Named residual risk this module
cannot control from inside itself: a hard hook-runner timeout that kills
this process before it can emit its own deny JSON would functionally
fail *open* regardless of this module's own logic.

Token: `os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")` --
GH_TOKEN first, matching the `gh` CLI's own documented precedence
(cli.github.com/manual/gh_help_environment: "GH_TOKEN, GITHUB_TOKEN (in
order of precedence)"). A fresh decision, not reuse: every existing
.github/scripts/*.py in this repository reads exactly one of the two,
never both with a fallback -- and this hook runs inside an interactive
agent session, not CI, so the Actions-default GITHUB_TOKEN assumption
those scripts make does not apply here.

Every deny message names only issue numbers, issue state, and the
fixed-vocabulary category name this module itself computed -- never the
fetched issue body's own text. Mirrors post_merge_retro.py's own "never
embed untrusted text in a bot-authored artifact" rule: an issue body is
attacker-influenced text on a public repository, and reflecting it
verbatim into a systemMessage could inject Markdown/mentions/formatting.
(docs/security-control-inventory.md's OWASP-ASI mapping is an exact
10-row table that rejects any extra row -- gate_owasp_asi_mapping.py /
gate_owasp_llm_mapping.py -- so this constraint is enforced by this
docstring and code review, not a new inventory row.)

Standard library only. This IS the first hook script in this repository
to make a live network call -- every other ACM-family checker
(check_acm_present_or_waiver.py, check_skill_audit_disclosure_or_waiver.py)
is deliberately network-free, per their own docstrings.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"owner":"tvna","repo":"gitapex","title":"...","body":"Closes #1"}' \\
        | python3 hooks/check_pr_issue_acm_disclosure.py

Exit codes:
    0  Allow -- every resolving-cited issue passed, or none was cited but
       some other citation form (Refs/#N) was.
    1  Deny -- no citation at all, or at least one resolving-cited issue
       failed; a "FAIL: ..." reason on stderr.
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
from typing import Any, Callable

import check_acm_present_or_waiver as acm_checker

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 20
# Lower than gate_acm_issue_disclosure.py's/post_merge_retro.py's 3 -- this
# runs inside a PreToolUse hook's own timeout budget (hooks.json's 45s for
# this entry), and each resolving-cited issue pays its own retry-sleep cost
# sequentially, so a multi-issue PR under a degraded API multiplies it.
_MAX_ATTEMPTS = 2

_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)

_RESOLVING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)\b",
    re.IGNORECASE,
)
_REFS_KEYWORD_RE = re.compile(r"\brefs?\s*:?\s*#(\d+)\b", re.IGNORECASE)
_BARE_NUMBER_RE = re.compile(r"(?<![\w#])#(\d+)\b")


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def _strip_fences(text: str | None) -> str:
    return _FENCE_RE.sub("", text or "")


def extract_citations(title: str | None, body: str | None) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return (resolving, context) -- sorted tuples of distinct issue
    numbers cited by `title`/`body`. `resolving` is the ACM-gated set
    (a GitHub closing keyword in the body); `context` is everything else
    cited (Refs/#N, title or body) that isn't already in `resolving` --
    a number cited both ways stays in `resolving` only."""
    stripped_body = _strip_fences(body)
    stripped_title = _strip_fences(title)
    resolving = {int(n) for n in _RESOLVING_RE.findall(stripped_body)}
    combined = stripped_title + "\n" + stripped_body
    context_candidates = {int(n) for n in _REFS_KEYWORD_RE.findall(combined)}
    context_candidates |= {int(n) for n in _BARE_NUMBER_RE.findall(combined)}
    context = context_candidates - resolving
    return tuple(sorted(resolving)), tuple(sorted(context))


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted owner/repo/issue-number
    # segments -- no untrusted text ever touches the URL itself.
    return urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS)  # noqa: S310


def _call(
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
    max_attempts: int = _MAX_ATTEMPTS,
) -> dict[str, Any]:
    """GET the GitHub API, retrying transient (network/5xx) failures up to
    `max_attempts` times. Mirrors gate_acm_issue_disclosure.py's and
    post_merge_retro.py's own `_call` shape, at a lower max_attempts (see
    module docstring). Raises GitHubApiError("not-found") on a 404
    (single-shot, no retry) so callers can report it distinctly from a
    genuine fetch failure; any other unrecoverable outcome raises
    GitHubApiError("fetch-failed: HTTP <code or 'network error'>")."""
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
        if last_code == 404:
            raise GitHubApiError("not-found")
        if last_code != 0 and last_code < 500:
            break
        if attempt < max_attempts:
            sleeper(attempt * 5)

    code_display = str(last_code) if last_code else "network error"
    raise GitHubApiError(f"fetch-failed: HTTP {code_display}")


def fetch_issue(
    owner: str,
    repo: str,
    number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, str]:
    """Return {'body': str, 'state': str} for issue `number`. Raises
    GitHubApiError -- see `_call`'s docstring for its two message shapes."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{number}"
    data = _call(url, token, opener, sleeper)
    return {"body": data.get("body") or "", "state": data.get("state") or ""}


def classify_issue(
    owner: str,
    repo: str,
    number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> str | None:
    """Return None if issue `number` passes (open, and discloses an ACM
    table or a valid non-'tracking' waiver), else a one-line reason
    string naming why it failed -- never the issue's own body text."""
    try:
        issue = fetch_issue(owner, repo, number, token, opener=opener, sleeper=sleeper)
    except GitHubApiError as error:
        if str(error) == "not-found":
            return f"#{number}: issue not found"
        return f"#{number}: could not fetch issue ({error})"

    if issue["state"] != "open":
        return f"#{number}: issue is already closed"

    category = acm_checker.waiver_category(issue["body"])
    if category == "tracking":
        return (
            f"#{number}: waiver category is 'tracking' -- a tracking/umbrella "
            "issue is resolved by its sub-issues, never its own PR"
        )
    if not acm_checker.has_acm_disclosure(issue["body"]):
        return f"#{number}: no Acceptance Criteria Map table or waiver disclosed"
    return None


def evaluate(
    owner: str,
    repo: str,
    title: str,
    body: str,
    token: str | None,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> tuple[bool, str]:
    """Return (passed, message) for the full PR title/body citation check.

    `token` may be falsy -- a missing token is a single global short-circuit
    fail-closed deny (see module docstring), not a per-issue failure, so
    callers must resolve it (or its absence) before calling this."""
    resolving, context = extract_citations(title, body)

    if not resolving and not context:
        return False, (
            "PR title/body cites no issue at all. Per this repository's own "
            "citation convention, cite one via Closes #N, Fixes #N, Refs #N, "
            "or a bare #N."
        )

    if not resolving:
        return True, "only context-only (Refs/#N) citation(s) -- nothing to ACM-check"

    if not token:
        cited = ", ".join(f"#{n}" for n in resolving)
        return False, (
            f"cannot verify ACM/waiver disclosure for {cited}: no GH_TOKEN/"
            "GITHUB_TOKEN in the environment (failing closed)"
        )

    failures = [
        reason
        for number in resolving
        if (reason := classify_issue(owner, repo, number, token, opener=opener, sleeper=sleeper))
    ]
    if failures:
        return False, "; ".join(failures)
    return True, "every Closes/Fixes-cited issue discloses an ACM table or a valid waiver"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a candidate PR's title/body: every Closes/Fixes-cited "
        "issue must disclose an ACM table or a valid, non-'tracking' waiver, and "
        "must still be open."
    )
    parser.add_argument(
        "--payload",
        help="Path to a JSON file with owner/repo/title/body; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        raw = open(args.payload, encoding="utf-8").read() if args.payload else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: payload file not found: {args.payload}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        print(f"error: payload is not valid JSON: {error}", file=sys.stderr)
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

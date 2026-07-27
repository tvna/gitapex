#!/usr/bin/env python3
"""Flag a GitHub issue whose body carries neither an Acceptance Criteria
Map (ACM) nor an explicit waiver.

Issue #414 (sub-issue of #357): #357's own investigation found that no
workflow in this repository triggers on `issues:` events, so a missing
ACM on an issue body (the shape drafting-an-acm-issue/SKILL.md exists to
prevent) had no universal, environment-independent backstop -- only a
per-session skill-trigger (probabilistic) and a PreToolUse hook (#413,
which only fires where this repo's own hook harness is loaded). This
script is that backstop's check-and-act half; the calling workflow
(.github/workflows/acm-issue-gate.yml) supplies the issue body, owner,
repo, and issue number.

Disclosure vocabulary: an issue body passes when it contains either the
Acceptance Criteria Map table (same header shape as
skills/drafting-an-acm-issue/scripts/check_acm_present.py and
skills/planning-a-branch-from-an-issue/scripts/check_acm_present.py) or an
explicit waiver line of the form ``ACM: not-applicable (chore|docs|tracking):
<reason>`` -- the exact vocabulary named in issue #357's own Acceptance
Criteria Map (the PreToolUse hook row), reused here so this script never
has to classify feature/fix/refactor vs. chore/docs/tracking itself; the
requester makes that call by choosing the waiver line or the table. This
mirrors .github/scripts/gate_skill_audit_disclosure.py's own
disclosure-or-``WAIVED:``-reason shape, applied to a different section
of a different document.

This is *not* a fourth copy of check_acm_present.py: it accepts an
additional waiver form those two copies don't (and isn't discovered by
tests/test_check_acm_present_sync.py, which only globs
skills/*/scripts/check_acm_present.py). If the ACM table's header row
shape ever changes, update this file's _ACM_HEADER_RE alongside both
check_acm_present.py copies -- nothing enforces that beyond this
docstring note.

Decision, named explicitly per issue #414's own Non-goals ("deciding
whether human-authored issues get exempted -- name the decision
explicitly, do not silently default either way"): no carve-out for
human-authored issues. GitHub's `issues` webhook payload carries no
field that reliably distinguishes an issue drafted by an agent from one
typed directly by a human under the same account -- every issue in this
repository, regardless of how it was actually produced, surfaces the
same `user.login`/`author_association` (e.g. issue #414 itself: login
"tvna", author_association "OWNER"). An authorship-based carve-out would
therefore be unenforceable from the webhook payload alone. Since this
gate can only comment/label (GitHub has no required-check equivalent for
issue creation -- it never blocks), applying it uniformly to every
opened/edited issue costs nothing beyond a label on an issue whose
author had no ACM convention in mind.

Deliberately stdlib-only and self-contained, matching this repository's
existing .github/scripts/*.py convention of not importing across files.
The GitHub API retry/error shape (`_call`, `GitHubApiError`) is copied
from post_merge_retro.py rather than shared, for the same reason.

Usage (the check alone, no network calls, no side effects)::

    python3 .github/scripts/gate_acm_issue_disclosure.py --check-only --body <path>
    printf '%s' "$ISSUE_BODY" | python3 .github/scripts/gate_acm_issue_disclosure.py --check-only

Usage (full run: check, then label/comment as needed)::

    python3 .github/scripts/gate_acm_issue_disclosure.py \\
        --owner tvna --repo gitapex --issue-number 123 <<< "$ISSUE_BODY"

Environment variables:
    GITHUB_TOKEN  GitHub token with issues:write (the default Actions
                  token's ``issues: write`` permission suffices). Not
                  read at all in --check-only mode.

Exit codes:
    0  The issue body discloses an ACM (or a valid waiver) -- pass.
    1  No valid disclosure found (the issue is flagged, if not in
       --check-only mode), a required argument/token is missing, or a
       GitHub API call failed.
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
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_HTTP_TIMEOUT_SECONDS = 30

_ACM_LABEL = "needs-acm"
_ACM_LABEL_COLOR = "fbca04"
_ACM_LABEL_DESCRIPTION = "Missing an Acceptance Criteria Map (or an explicit waiver) -- see issue #357"
_MARKER = "<!-- acm-issue-gate:414 -->"

# Same table header shape as skills/drafting-an-acm-issue/scripts/check_acm_present.py
# and skills/planning-a-branch-from-an-issue/scripts/check_acm_present.py. Match loosely
# (any whitespace around pipes) so reasonable Markdown re-formatting still passes.
_ACM_HEADER_RE = re.compile(
    r"\|\s*Criterion\s*\|\s*Interpretation\s*\|\s*Planned ops\s*\|"
    r"\s*Proof method\s*\|\s*Residual risk\s*\|",
    re.IGNORECASE,
)

# Issue #357's own named waiver vocabulary: `ACM: not-applicable (chore|docs|tracking): <reason>`.
# A non-empty trailing reason is required, mirroring gate_skill_audit_disclosure.py's
# own `WAIVED: <reason>` requirement -- a bare "ACM: not-applicable (chore):" with
# nothing after the colon does not satisfy this.
_ACM_WAIVER_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*`?ACM`?[ \t]*:[ \t]*not-applicable[ \t]*"
    r"\((?:chore|docs|tracking)\)[ \t]*:[ \t]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)


class GitHubApiError(RuntimeError):
    """Raised when the GitHub REST API returns a non-recoverable error."""


def has_acm_disclosure(body_text: str | None) -> bool:
    """Return True iff `body_text` carries the ACM table or a valid waiver line."""
    # Normalize CRLF/CR line endings before matching, same rationale as
    # gate_skill_audit_disclosure.py's find_missing_disclosures: GitHub is
    # known to deliver web-UI-authored bodies with CRLF endings.
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    return bool(_ACM_HEADER_RE.search(normalized) or _ACM_WAIVER_RE.search(normalized))


# ---------------------------------------------------------------------------
# GitHub API side effects (label + comment), copied in shape from
# post_merge_retro.py's own _call/_default_opener/_format_code.
# ---------------------------------------------------------------------------


def _default_opener(request: urllib.request.Request) -> Any:
    # S310 justification: every caller builds `request` from a fixed
    # https://api.github.com URL plus trusted owner/repo/issue-number
    # segments; the untrusted issue body never touches a URL, only a JSON
    # request body.
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
) -> Any:
    """Call the GitHub API, retrying transient (network / 5xx) failures up
    to `max_attempts` attempts -- mirrors post_merge_retro.py's own `_call`."""
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


def ensure_label_exists(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Create the `needs-acm` label repo-wide if it does not already exist.

    Idempotent: an HTTP 422 (label name already exists) is treated as
    success, not an error -- the same disclosure-or-waiver run may see
    this label already created by an earlier run."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/labels"
    payload = {"name": _ACM_LABEL, "color": _ACM_LABEL_COLOR, "description": _ACM_LABEL_DESCRIPTION}
    try:
        _call("POST", url, token, opener, sleeper, body=payload, max_attempts=1)
    except GitHubApiError as error:
        if "HTTP 422" not in str(error):
            raise


def add_label(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Add the `needs-acm` label to the issue. Idempotent -- adding a
    label the issue already carries is a no-op per the GitHub API."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/labels"
    _call("POST", url, token, opener, sleeper, body={"labels": [_ACM_LABEL]})


def remove_label(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Remove the `needs-acm` label from the issue, if present. An HTTP
    404 (label was not on the issue) is treated as success, not an
    error -- there is nothing to reconcile."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/labels/{urllib.parse.quote(_ACM_LABEL)}"
    try:
        _call("DELETE", url, token, opener, sleeper, max_attempts=1)
    except GitHubApiError as error:
        if "HTTP 404" not in str(error):
            raise


def has_marker_comment(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> bool:
    """Return True iff this gate has already commented on this issue --
    checked via `_MARKER`, so a repeated `edited` event on a still-failing
    issue does not spam a new comment every time."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=100"
    comments = _call("GET", url, token, opener, sleeper)
    return any(_MARKER in comment.get("body", "") for comment in comments)


def post_comment(
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> None:
    """Post the disclosure-gate comment on the issue, once (guarded by
    `has_marker_comment` in `main`, not here -- kept separate so tests can
    exercise posting without also exercising the marker check)."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    body = (
        f"{_MARKER}\n"
        "This issue's body does not disclose an Acceptance Criteria Map "
        "(ACM) or an explicit waiver. Per `skills/drafting-an-acm-issue/SKILL.md` "
        "(see issue #357), add either:\n\n"
        "- an ACM table (criterion -> interpretation -> planned ops -> proof "
        "method -> residual risk), or\n"
        "- a waiver line: `ACM: not-applicable (chore|docs|tracking): <reason>`\n\n"
        "This is a post-hoc, non-blocking flag (issue #414) -- it does not "
        "prevent this issue from being worked on, and applies regardless of "
        "who or what opened it."
    )
    _call("POST", url, token, opener, sleeper, body={"body": body})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a GitHub issue body for ACM disclosure (or waiver); "
        "label/comment on the issue when missing."
    )
    parser.add_argument("--body", help="Path to the issue body text; reads standard input when omitted.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only run the text check (PASS/FAIL to stdout/stderr); no GitHub API calls.",
    )
    parser.add_argument("--owner", help="Repository owner, e.g. tvna. Required unless --check-only.")
    parser.add_argument("--repo", help="Repository name, e.g. gitapex. Required unless --check-only.")
    parser.add_argument(
        "--issue-number", type=int, help="The issue's number. Required unless --check-only."
    )
    args = parser.parse_args(argv)

    try:
        body_text = open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1

    passed = has_acm_disclosure(body_text)

    if args.check_only:
        if passed:
            print("PASS: Acceptance Criteria Map (or waiver) disclosed")
            return 0
        print("FAIL: no Acceptance Criteria Map table or ACM waiver line found in issue body", file=sys.stderr)
        return 1

    if not args.owner or not args.repo or args.issue_number is None:
        print("error: --owner, --repo, and --issue-number are required outside --check-only", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        if passed:
            print("PASS: Acceptance Criteria Map (or waiver) disclosed -- removing label if present")
            remove_label(args.owner, args.repo, args.issue_number, token)
            return 0

        print(
            "FAIL: no Acceptance Criteria Map table or ACM waiver line found in issue body",
            file=sys.stderr,
        )
        ensure_label_exists(args.owner, args.repo, token)
        add_label(args.owner, args.repo, args.issue_number, token)
        if has_marker_comment(args.owner, args.repo, args.issue_number, token):
            print("Marker comment already present -- not posting again.")
        else:
            post_comment(args.owner, args.repo, args.issue_number, token)
            print(f"Flagged issue #{args.issue_number}: added '{_ACM_LABEL}' label and posted a comment.")
        return 1
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

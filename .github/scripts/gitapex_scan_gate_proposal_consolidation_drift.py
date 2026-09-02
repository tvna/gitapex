#!/usr/bin/env python3
"""Verify a `gate-proposal-umbrella` issue's own `Consolidates: #a, #b, ...`
claim against the referenced source issues' real duplicate-closure state.

Issue #1653: the flat gate-proposal-issues design's own two-signal check
(`gitapex_scan_retrospective_gate_drift.py`) audits every already-CLOSED
`gate-proposal`-labelled issue, but never checks whether an OPEN
`gate-proposal-umbrella` issue's own stated "Consolidates:" claim is
actually true. #1566-#1575 (10 umbrella issues filed in one session,
naming 32 source issues total across them) sat with that claim
unverified for roughly a day -- every referenced source issue was still
OPEN -- before a human caught it and closed them by hand. This script
closes that gap: for every OPEN `gate-proposal`-labelled issue whose
body carries a `Consolidates: #a, #b, ...` line, it verifies each
referenced issue number is CLOSED with `state_reason: duplicate` AND
GraphQL `Issue.duplicateOf.number` pointing back to that same umbrella.

Primary-source grounding for the GraphQL dependency (issue #1653's own
research, not re-derived here): GitHub's REST API documents no read-side
field naming which issue a closed issue is a duplicate of (only
`state_reason`, whose enum includes `duplicate` but names no target);
only the GraphQL `Issue.duplicateOf` field exposes that relationship
(confirmed directly against GitHub's own public GraphQL schema SDL,
https://docs.github.com/public/fpt/schema.docs.graphql, and against a
live example, issue #1547, closed duplicate of #1566).

Sibling script to `gitapex_scan_retrospective_gate_drift.py`, not a third
pass inside it (Branch Plan decision for issue #1653, confirmed via
AskUserQuestion during planning): this check needs a GraphQL POST call
the existing pure-REST script deliberately never made, and folding it in
would also require rewriting that script's own docstring ("Two passes")
and the design doc's Decision 5 text it already implements exactly.
`label_exists` and `list_labelled_issue_records` are imported directly
from that script instead of duplicated -- the identical cross-import
precedent `gitapex_compute_gprr.py` already uses for the same two
functions, both scripts living in the same `.github/scripts/` tree
(never crossing the deployed-vs-never-deployed boundary
`docs/repository-layout.md` documents).

Unlike `gitapex_scan_retrospective_gate_drift.py`'s own zero-tolerance
closed-issue pass, a `gate-proposal`-labelled issue with no
`Consolidates:` line at all (an ordinary, non-umbrella finding) is not a
violation -- it is simply outside this check's own scope, nothing to
verify.

Deliberately dependency-light (stdlib plus `pydantic`, this repository's
own pinned CLI-arg validation dependency) and reuses
`_gitapex_github_http.graphql_call` (already shared, already tested)
rather than hand-rolling a second GraphQL client.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py \\
        --owner tvna --repo gitapex

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs), matching `retrospective-gate-drift.yml`'s own
invocation of the sibling script.

Environment variables:
    GITHUB_TOKEN  GitHub token with read access to issues (the default
                  Actions token's `issues: read` permission suffices --
                  this script never writes, so no elevated scope is ever
                  requested; a GraphQL read against the same repository
                  needs no additional scope beyond what the REST reads
                  already use).

Exit codes:
    0  Every OPEN gate-proposal-labelled issue's own Consolidates: claim
       (where present) is verified: every referenced issue is CLOSED as
       a duplicate pointing back to that umbrella. An issue with no
       Consolidates: line at all is not a violation.
    1  At least one referenced issue is still open, closed for a
       different reason, closed as a duplicate of a different issue, or
       could not be resolved at all, or the `gate-proposal` label itself
       does not exist, or a GitHub API error prevented the check from
       completing (never silently reported as "zero issues found").
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata
import urllib.request
from collections.abc import Callable
from typing import Any

import _gitapex_github_http
import gitapex_scan_retrospective_gate_drift as gate_drift
from _gitapex_github_http import GitHubApiError
from pydantic import BaseModel, Field, ValidationError, field_validator

# Confirmed against #1566's own live body (issue #1653's own primary-source
# research): "Consolidates: #1547, #1546, #1489, #1508" -- comma-separated,
# `#N` form, on its own line. MULTILINE so `^`/`$` anchor per line, not the
# whole body; `[ \t]` rather than `\s` so the match cannot itself cross a
# newline into a following paragraph. `finditer`, not `search`, at the call
# site below: an issue body edited to append a second Consolidates: line
# must not leave that second line's own references silently unchecked
# (found by an adversarial review pass against this script's own diff).
_CONSOLIDATES_LINE_RE = re.compile(r"^Consolidates:[ \t]*(#\d+(?:,[ \t]*#\d+)*)[ \t]*$", re.MULTILINE)
_ISSUE_REF_RE = re.compile(r"#(\d+)")

# GraphQL is the only documented way to read "which issue is this closed
# as a duplicate of" -- see module docstring. `owner`/`repo`/`number` are
# passed as typed GraphQL variables, never interpolated into the query
# string itself, so a malformed or adversarial issue number cannot alter
# the query shape.
_ISSUE_DUPLICATE_STATE_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      number
      state
      stateReason
      duplicateOf {
        number
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def extract_consolidates_issue_numbers(body: str) -> list[int]:
    """Return the issue numbers named across every `Consolidates: #a, #b,
    ...` line in `body`, in first-seen order with duplicates removed, or
    `[]` if no such line exists. `body` carrying no such line is not
    itself a defect -- an ordinary (non-umbrella) gate-proposal issue has
    nothing for this check to verify. Scans every matching line, not just
    the first: an issue body edited to append a second Consolidates: line
    must not leave that line's own references unchecked."""
    numbers: list[int] = []
    seen: set[int] = set()
    for line_match in _CONSOLIDATES_LINE_RE.finditer(body):
        for ref in _ISSUE_REF_RE.findall(line_match.group(1)):
            number = int(ref)
            if number not in seen:
                seen.add(number)
                numbers.append(number)
    return numbers


def find_unverified_consolidation_claims(
    umbrella_number: int,
    referenced_numbers: list[int],
    referenced_states: dict[int, dict[str, Any] | None],
) -> list[int]:
    """Return the subset of `referenced_numbers` NOT confirmed CLOSED as a
    duplicate pointing back to `umbrella_number`.

    `referenced_states[n]` is `None` when issue `n` could not be resolved
    at all (e.g. deleted, or an otherwise-unresolvable GraphQL lookup) --
    treated as a violation, the same as any other unverified claim, never
    silently skipped. Otherwise it carries `state` ("OPEN"/"CLOSED"),
    `state_reason` (GitHub's own `IssueStateReason` GraphQL enum value,
    e.g. `"DUPLICATE"`), and `duplicate_of_number` (an `int`, or `None`
    when the issue was closed for a reason other than duplicate, or as a
    duplicate of nothing)."""
    violations: list[int] = []
    for number in referenced_numbers:
        state = referenced_states.get(number)
        if state is None:
            violations.append(number)
            continue
        if state.get("state") != "CLOSED":
            violations.append(number)
            continue
        if state.get("state_reason") != "DUPLICATE":
            violations.append(number)
            continue
        if state.get("duplicate_of_number") != umbrella_number:
            violations.append(number)
    return violations


def find_consolidation_violations(
    referenced_numbers_by_umbrella: dict[int, list[int]],
    referenced_states: dict[int, dict[str, Any] | None],
) -> dict[int, list[int]]:
    """Return `{umbrella_number: [violating_referenced_numbers]}` for every
    `(umbrella_number, referenced_numbers)` pair in
    `referenced_numbers_by_umbrella` (as already extracted by
    `extract_consolidates_issue_numbers`, once, by the caller -- this
    function does no body parsing of its own so a caller iterating many
    umbrella records never re-parses the same body twice) with at least
    one referenced issue not confirmed CLOSED-as-duplicate pointing back
    to it. An umbrella with no referenced numbers at all contributes no
    entry -- not a violation, nothing to verify."""
    violations_by_umbrella: dict[int, list[int]] = {}
    for umbrella_number, referenced_numbers in referenced_numbers_by_umbrella.items():
        if not referenced_numbers:
            continue
        violating = find_unverified_consolidation_claims(
            umbrella_number,
            referenced_numbers,
            referenced_states,
        )
        if violating:
            violations_by_umbrella[umbrella_number] = violating
    return violations_by_umbrella


def format_consolidation_drift_report(violations_by_umbrella: dict[int, list[int]], label: str) -> str:
    """Human-readable report for this check, printed to stdout and
    captured in the CI step summary."""
    if not violations_by_umbrella:
        return (
            f"Consolidation-claim integrity: every OPEN '{label}'-labelled issue's own "
            "Consolidates: claim (where present) is verified -- each referenced issue is "
            "closed as a duplicate pointing back to its umbrella.\nPASS"
        )
    lines = [
        f"Consolidation-claim integrity: {len(violations_by_umbrella)} OPEN '{label}'-labelled "
        "umbrella issue(s) have an unverified Consolidates: claim (no reopen/edit action taken -- "
        "resolve by hand):",
    ]
    for umbrella_number in sorted(violations_by_umbrella):
        violating = ", ".join(f"#{n}" for n in sorted(violations_by_umbrella[umbrella_number]))
        lines.append(f"  #{umbrella_number} Consolidates claim not verified for: {violating}")
    lines.append(f"FAIL: {len(violations_by_umbrella)} umbrella issue(s) have an unverified Consolidates: claim.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


def fetch_issue_duplicate_state(
    owner: str,
    repo: str,
    number: int,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _gitapex_github_http.default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any] | None:
    """GraphQL-fetch issue `number`'s own `state`/`stateReason`/
    `duplicateOf.number` -- the one live signal REST does not expose (see
    module docstring). Returns `None` when the query cannot resolve the
    issue at all (a `data.repository.issue` that comes back `null`, e.g.
    a deleted or cross-repository number) rather than raising -- an
    unresolvable referenced issue is a violation for the caller to
    report, not a script-level failure. Raises `GitHubApiError` on an
    HTTP-level failure (after `graphql_call`'s own retry budget is
    exhausted) or on a 200 response whose body carries a GraphQL `errors`
    entry (a systemic condition -- e.g. a scope/field error unrelated to
    any one issue number -- that must stop the whole run rather than be
    silently read as "issue unresolvable, one violation," found by an
    adversarial review pass against this script's own diff and matching
    the identical `graphql_call` caller pattern in
    `apm_modules/tvna/clairvoyance/scripts/sync_pr_publish.py`), matching
    every other I/O function in this repository's `.github/scripts/*.py`
    tree."""
    sleeper = sleeper if sleeper is not None else time.sleep
    code, body = _gitapex_github_http.graphql_call(
        query=_ISSUE_DUPLICATE_STATE_QUERY,
        variables={"owner": owner, "repo": repo, "number": number},
        token=token,
        opener=opener,
        sleeper=sleeper,
    )
    if 200 <= code < 300:
        if "errors" in body:
            raise GitHubApiError(f"GraphQL query for issue #{number} returned errors: {body['errors']}")
        data = body.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        issue = repository.get("issue") if isinstance(repository, dict) else None
        if not isinstance(issue, dict):
            return None
        duplicate_of = issue.get("duplicateOf")
        duplicate_of_number = duplicate_of.get("number") if isinstance(duplicate_of, dict) else None
        return {
            "state": issue.get("state"),
            "state_reason": issue.get("stateReason"),
            "duplicate_of_number": duplicate_of_number,
        }
    raise GitHubApiError(f"GraphQL query for issue #{number} failed: HTTP {_gitapex_github_http.format_code(code)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# This CLI's own wording for each constraint the model below imposes, keyed
# by pydantic's own error type -- the identical shape
# `gitapex_scan_retrospective_gate_drift.py` and `gitapex_compute_gprr.py`
# each already carry independently, kept as its own copy here for the same
# reason those two scripts stay independently self-contained (see module
# docstring).
_CONSTRAINT_HINTS = {"string_too_short": "must not be blank", "value_error": "must not be blank"}


def _is_blank(value: str) -> bool:
    """True iff every character in `value` is ordinary whitespace or a
    Unicode Format-category (Cf) mark -- invisible either way (issue
    #1094's own finding, reproduced here as its own copy for the same
    self-containment reason as `_CONSTRAINT_HINTS` above)."""
    return all(char.isspace() or unicodedata.category(char) == "Cf" for char in value)


class ScanConsolidationDriftArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. Each field rejects a
    blank value: argparse's own ``required=True`` only guarantees the
    flag was passed, not that its value is non-empty, and a blank
    owner/repo/label was never a meaningful input to the GitHub queries
    below."""

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    label: str = Field(min_length=1)

    @field_validator("owner", "repo", "label")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        if _is_blank(value):
            raise ValueError("must not be blank")
        return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify every OPEN gate-proposal-labelled issue's own Consolidates: claim "
        "against the referenced source issues' real duplicate-closure state."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument(
        "--label",
        default=gate_drift.GATE_PROPOSAL_LABEL,
        help=f"Issue label to search (default: {gate_drift.GATE_PROPOSAL_LABEL})",
    )
    args = parser.parse_args(argv)
    try:
        ScanConsolidationDriftArgs(owner=args.owner, repo=args.repo, label=args.label)
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
        if not gate_drift.label_exists(args.owner, args.repo, args.label, token):
            print(gate_drift.format_missing_label_error(args.owner, args.repo, args.label), file=sys.stderr)
            return 1
        open_records = gate_drift.list_labelled_issue_records(args.owner, args.repo, args.label, token, state="open")

        referenced_numbers_by_umbrella: dict[int, list[int]] = {}
        all_referenced_numbers: set[int] = set()
        for record in open_records:
            numbers = extract_consolidates_issue_numbers(record.get("body") or "")
            if numbers:
                referenced_numbers_by_umbrella[record["number"]] = numbers
                all_referenced_numbers.update(numbers)

        referenced_states: dict[int, dict[str, Any] | None] = {
            number: fetch_issue_duplicate_state(args.owner, args.repo, number, token)
            for number in sorted(all_referenced_numbers)
        }
    except GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    violations_by_umbrella = find_consolidation_violations(referenced_numbers_by_umbrella, referenced_states)
    print(format_consolidation_drift_report(violations_by_umbrella, args.label))
    return 1 if violations_by_umbrella else 0


if __name__ == "__main__":
    raise SystemExit(main())

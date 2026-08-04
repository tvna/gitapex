#!/usr/bin/env python3
"""Compute the Gate-Preventable Repair Rate (GPRR) from existing
`label:retrospective` issues.

Issue #726 (gitapex bug-inducing-patterns audit, 2026-08-04):
`skills/merge-retrospective/SKILL.md` (lines 54-127) already requires
every retrospective issue to carry a machine-parseable `Status:` tag from
a fixed vocabulary (`missing-deterministic-gate` /
`unclear-agent-instruction` / `external-human-decision` /
`carried-forward`), explicitly so "a future drift-check script can
extract classification and gate status without an LLM." Nobody currently
tallies this -- CLAUDE.md section 3 mandates the classification, but only
as narrative per-issue text, re-read by a human (or an LLM) each cycle to
see any trend.

Design: docs/superpowers/specs/2026-08-04-gprr-design.md

Reuses `_github_http.py`'s generic paginated-fetch-with-retry client for
the merged-pull-request query, and `scan_retrospective_gate_drift.py`'s
`list_labelled_issue_records` for the issue-specific fetch, per the
issue's own constraint, rather than a second hand-rolled GitHub API
client. Stdlib-only, matching those two scripts and this repository's
`.github/scripts/*.py` independence convention (see
`gate_skill_rename_lifecycle.py`'s own docstring rationale, and
`_github_http.py`'s own docstring for why the generic HTTP client is a
third shared module rather than one script importing the other's
low-level plumbing).

Deliberately stateless: every run recomputes the full weekly series from
`label:retrospective` issues' own `created_at` timestamps, all the way
back, rather than persisting/committing a time series to a tracked file.
A run one week from now naturally reports one more week-bucket than
today's run -- the growth the issue's own proof method asks for -- with
no merge/append logic, no new write scope, and no risk of drift between
a committed snapshot and GitHub's own current state.

This script is informational, not a gate: it never exits non-zero based
on the computed GPRR value itself (the issue explicitly frames this as
replacing "only a threshold pass/fail gate" with "an inspectable numeric
time series"). It still exits 1 on a genuine GitHub API error -- never
silently reporting an empty/zero series as if it were a real all-clear.

Usage::

    python3 .github/scripts/compute_gprr.py --owner tvna --repo gitapex

Environment variables:
    GITHUB_TOKEN  GitHub token with read access to issues and pull
                  requests (the default Actions token's `issues: read`
                  and `pull-requests: read` permissions suffice).

Exit codes:
    0  Report computed and printed (regardless of the GPRR value itself).
    1  A GitHub API error prevented the check from completing, or the
       CLI arguments were invalid.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypedDict

import _github_http
import scan_retrospective_gate_drift as gate_drift

_API_ROOT = "https://api.github.com"
_PER_PAGE = 100

# The fixed vocabulary `skills/merge-retrospective/SKILL.md` defines. Only
# the first three classify a *repair*; `carried-forward` re-reports a
# prior cycle's still-unimplemented gate and is tallied separately, never
# folded into the GPRR ratio (SKILL.md lines 85-101). Named individually
# (not indexed by position out of a tuple) so a slug's own field mapping
# can never silently drift if `_REPAIR_SLUGS`'s order ever changes.
_MISSING_DETERMINISTIC_GATE_SLUG = "missing-deterministic-gate"
_UNCLEAR_AGENT_INSTRUCTION_SLUG = "unclear-agent-instruction"
_EXTERNAL_HUMAN_DECISION_SLUG = "external-human-decision"
_CARRIED_FORWARD_SLUG = "carried-forward"
_REPAIR_SLUGS = (_MISSING_DETERMINISTIC_GATE_SLUG, _UNCLEAR_AGENT_INSTRUCTION_SLUG, _EXTERNAL_HUMAN_DECISION_SLUG)
_ALL_SLUGS = (*_REPAIR_SLUGS, _CARRIED_FORWARD_SLUG)

# Anchored to the start (optional leading whitespace, matching the
# indented Carried-forward-gate list-item shape) and end of its own line --
# the exact shape SKILL.md's Repair record format always produces a
# `Status:` line in -- so a slug merely *mentioned* inside a repair's
# free-prose "what happened" clause (which SKILL.md's own
# injection-hardening rule confines untrusted quoted material to) does not
# also count as a real field line. Restricted to the closed four-slug
# vocabulary itself, so a forged fifth slug cannot match at all.
_STATUS_LINE_RE = re.compile(
    r"^[ \t]*Status:[ \t]*`(" + "|".join(re.escape(s) for s in _ALL_SLUGS) + r")`[ \t]*$",
    re.MULTILINE,
)


class WeeklyPoint(TypedDict):
    week: str
    missing_deterministic_gate: int
    unclear_agent_instruction: int
    external_human_decision: int
    carried_forward: int
    total_classified: int
    merged_pr_count: int
    gate_share_of_classified: float | None
    gate_share_of_merged_prs: float | None


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def parse_status_tags(body: str) -> list[str]:
    """Extract every `Status:` field-line's slug from an issue body,
    restricted to merge-retrospective's own fixed four-slug vocabulary."""
    return _STATUS_LINE_RE.findall(body)


def week_key(iso_timestamp: str) -> str:
    """Return the ISO-8601 week (`YYYY-Www`) an RFC 3339 timestamp falls
    in, using the ISO week-numbering year (not the calendar year) so a
    late-December/early-January timestamp buckets correctly across the
    year boundary."""
    parsed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    iso_year, iso_week, _iso_weekday = parsed.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _ratio(numerator: int, denominator: int) -> float | None:
    """`numerator / denominator`, or None when the denominator is zero --
    never a raw ZeroDivisionError, and never silently reported as 0.0
    (which would read as a real, computed zero share)."""
    return None if denominator <= 0 else numerator / denominator


def build_weekly_series(
    issue_records: list[dict[str, Any]],
    merged_pr_timestamps: list[str],
) -> list[WeeklyPoint]:
    """Bucket `issue_records` (full `label:retrospective` issue records,
    each needing at least `body` and `created_at`) and
    `merged_pr_timestamps` (each merged PR's `merged_at`) by ISO week, and
    compute both GPRR ratios per week. Weeks are the union of both inputs'
    week-buckets, sorted ascending, so a week with merged PRs but zero
    retrospective issues (or vice versa) still gets a row."""
    tag_buckets: dict[str, Counter[str]] = {}
    for record in issue_records:
        created_at = record.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            continue
        body = record.get("body")
        tags = parse_status_tags(body if isinstance(body, str) else "")
        week = week_key(created_at)
        tag_buckets.setdefault(week, Counter())
        tag_buckets[week].update(tag for tag in tags if tag in _ALL_SLUGS)

    merged_buckets: Counter[str] = Counter()
    for timestamp in merged_pr_timestamps:
        if not isinstance(timestamp, str) or not timestamp:
            continue
        merged_buckets[week_key(timestamp)] += 1

    weeks = sorted(set(tag_buckets) | set(merged_buckets))
    series: list[WeeklyPoint] = []
    for week in weeks:
        counts = tag_buckets.get(week, Counter())
        gate_count = counts[_MISSING_DETERMINISTIC_GATE_SLUG]
        classified = sum(counts[slug] for slug in _REPAIR_SLUGS)
        merged_count = merged_buckets.get(week, 0)
        series.append(
            {
                "week": week,
                "missing_deterministic_gate": gate_count,
                "unclear_agent_instruction": counts[_UNCLEAR_AGENT_INSTRUCTION_SLUG],
                "external_human_decision": counts[_EXTERNAL_HUMAN_DECISION_SLUG],
                "carried_forward": counts[_CARRIED_FORWARD_SLUG],
                "total_classified": classified,
                "merged_pr_count": merged_count,
                "gate_share_of_classified": _ratio(gate_count, classified),
                "gate_share_of_merged_prs": _ratio(gate_count, merged_count),
            }
        )
    return series


def _format_share(share: float | None) -> str:
    return "n/a" if share is None else f"{share:.1%}"


def format_report(series: list[WeeklyPoint], label: str = gate_drift.DEFAULT_LABEL) -> str:
    """Human-readable report, printed to stdout and captured in the CI
    step summary. Leads with the all-time missing-deterministic-gate
    headline share (CLAUDE.md section 3: "if the gate is missing, build
    it before the operation it guards"), then a per-week breakdown."""
    total_gate = sum(point["missing_deterministic_gate"] for point in series)
    total_classified = sum(point["total_classified"] for point in series)
    total_merged = sum(point["merged_pr_count"] for point in series)
    total_carried = sum(point["carried_forward"] for point in series)

    lines = [
        f"Gate-Preventable Repair Rate (GPRR), all-time: {total_gate} of {total_classified} classified "
        f"'{label}' repairs were missing-deterministic-gate "
        f"({_format_share(_ratio(total_gate, total_classified))} of classified repairs, "
        f"{_format_share(_ratio(total_gate, total_merged))} of {total_merged} merged PRs).",
    ]
    if not series:
        lines.append(f"No '{label}'-labelled issue carries a recognised Status: tag yet.")
        return "\n".join(lines)

    lines.append(f"{total_carried} carried-forward gate mention(s) reported (excluded from the GPRR ratio above).")
    lines.append("")
    lines.append("Weekly breakdown:")
    for point in series:
        lines.append(
            f"  {point['week']}: missing-deterministic-gate={point['missing_deterministic_gate']} "
            f"of {point['total_classified']} classified ({_format_share(point['gate_share_of_classified'])}), "
            f"{point['merged_pr_count']} merged PR(s) ({_format_share(point['gate_share_of_merged_prs'])}), "
            f"carried-forward={point['carried_forward']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


_default_opener = _github_http.default_opener


def list_merged_pull_requests(
    owner: str,
    repo: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> list[str]:
    """Return the `merged_at` timestamp of every merged pull request, via
    paginated `GET /repos/{owner}/{repo}/pulls?state=closed` -- the closed
    state includes both merged and simply-closed PRs; only entries with a
    non-null `merged_at` are returned. Reuses `_github_http.fetch_json_page`
    for the pagination/retry loop (issue #726's own reuse constraint)
    instead of a second hand-rolled client."""
    sleeper = sleeper if sleeper is not None else time.sleep
    merged_at_timestamps: list[str] = []
    page = 1
    while True:
        url = (
            f"{_API_ROOT}/repos/{owner}/{repo}/pulls"
            f"?state=closed&sort=created&direction=asc&per_page={_PER_PAGE}&page={page}"
        )
        items = _github_http.fetch_json_page(url, token, opener, sleeper)
        if not items:
            break
        for item in items:
            merged_at = item.get("merged_at")
            if isinstance(merged_at, str) and merged_at:
                merged_at_timestamps.append(merged_at)
        if len(items) < _PER_PAGE:
            break
        page += 1
    return merged_at_timestamps


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _validate_cli_args(owner: str, repo: str, label: str) -> str | None:
    """Return a pydantic-``ValidationError``-style detail string (one
    ``<field>: <message>`` clause per violated constraint, joined with
    ``"; "``, in field-declaration order) if any of ``owner``/``repo``/
    ``label`` is blank, else None. Mirrors
    `scan_retrospective_gate_drift._validate_cli_args`'s own shape."""
    errors: list[str] = []
    if not owner:
        errors.append("owner: String should have at least 1 character")
    if not repo:
        errors.append("repo: String should have at least 1 character")
    if not label:
        errors.append("label: String should have at least 1 character")
    return "; ".join(errors) if errors else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute the Gate-Preventable Repair Rate (GPRR) from retrospective issues."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument(
        "--label",
        default=gate_drift.DEFAULT_LABEL,
        help=f"Issue label to search (default: {gate_drift.DEFAULT_LABEL})",
    )
    args = parser.parse_args(argv)
    detail = _validate_cli_args(args.owner, args.repo, args.label)
    if detail is not None:
        print(f"error: invalid arguments: {detail}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        issue_records = gate_drift.list_labelled_issue_records(args.owner, args.repo, args.label, token)
        merged_pr_timestamps = list_merged_pull_requests(args.owner, args.repo, token)
    except _github_http.GitHubApiError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    series = build_weekly_series(issue_records, merged_pr_timestamps)
    print(format_report(series, label=args.label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

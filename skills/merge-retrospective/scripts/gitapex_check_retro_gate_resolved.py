#!/usr/bin/env python3
"""Partition retrospective-labelled issue numbers into resolved/unresolved,
using the same two-signal check `.github/scripts/gitapex_scan_retrospective_gate_drift.py`
already implements.

Issue #1176: merge-retrospective's Step 1 ("Carry-forward check")
independently re-derived a weaker, citation-only approximation of the
two-signal check (a citing commit on `main` AND a corroborating
`.gitapex/ssot.json` `gates[].tracking_issue` entry) that
`gitapex_scan_retrospective_gate_drift.py` (issue #297, hardened by issue
#709) already implements. Because Step 1's prose never pointed at that
mechanism, individual sessions re-derived their own weaker check every
cycle, producing observed cross-session divergence (issues #1109, #1108,
and #1061 each disagreed with sibling retrospectives over the same issue
numbers).

This script re-implements (deliberately, not imports or subprocess-invokes)
the small pure-logic slice of that CI-only script -- `citation_count` and
its AND-not-OR partition -- against a local `git log` and a local
`.gitapex/ssot.json` read. It makes no GitHub API call of its own: the
caller (merge-retrospective's own Step 1) is expected to have already
resolved the candidate issue numbers via
`mcp__github__list_issues(labels: ["retrospective"])` and passes them here
as positional arguments.

This repository keeps `.github/scripts/*.py` and `skills/*/scripts/*.py`
files independently self-contained by deliberate convention (see
`gitapex_scan_retrospective_gate_drift.py`'s own docstring, and the
`drafting-an-acm-issue`/`planning-a-branch-from-an-issue` duplicate
`gitapex_check_acm_present.py` pair for the same convention observed
elsewhere across `skills/*/scripts/`) -- this file does not import that
script, or vice versa. Also deliberately not wired into the root
`pyproject.toml` testpaths/pythonpath (see
`skills/drafting-an-adr/scripts/gitapex_check_adr_shape.py` and
`skills/scanning-attack-surfaces/scripts/gitapex_scan_unpinned_actions.py`
for the same standalone convention) -- this skill's checker travels with
the skill and is meant to stand alone; run its tests directly with:

    python3 -m pytest skills/merge-retrospective/scripts/

Standard library only, no network calls, no side effects.

Usage::

    python3 gitapex_check_retro_gate_resolved.py 1109 1107 1108 1114
    # {"unresolved": [1109], "resolved": [1107, 1108, 1114]}

Exit codes:
    0  Partition computed and printed to stdout as one JSON object.
    1  A local `git log` or `.gitapex/ssot.json` read failed -- never
       silently reported as an empty/all-resolved partition.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Callable

# Record separator (0x1e) / unit separator (0x1f): neither appears in real
# commit messages, so they safely delimit `git log` entries and fields
# without a risk of an attacker-controlled commit message forging a fake
# boundary the way a printable delimiter (comma, pipe, newline) could.
# Mirrors gitapex_scan_retrospective_gate_drift.py's own _LOG_FORMAT exactly.
_LOG_FORMAT = "%x1e%H%x1f%B"


class GitLogError(RuntimeError):
    """Raised when the local `git log` invocation fails."""


class SsotLedgerError(RuntimeError):
    """Raised when `.gitapex/ssot.json` cannot be read as a usable gate
    registry. Never caught and silently downgraded to an empty
    corroboration set -- that would fail every issue's tracking-issue
    signal instead of surfacing the read error, misreporting a read
    failure as "nothing implemented yet"."""


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def _citation_pattern(issue_number: int) -> re.Pattern[str]:
    # Digit-boundary-aware: "#187" matches, but neither "#1870" nor "#2187"
    # does -- a plain substring or `\b`-based match would treat "7" and "0"
    # (both word characters) as a boundary and false-positive on unrelated
    # larger issue/PR numbers that happen to contain the target as a prefix
    # or suffix. Mirrors gitapex_scan_retrospective_gate_drift.py's own
    # _citation_pattern exactly.
    return re.compile(rf"(?<!\d)#{issue_number}(?!\d)")


def citation_count(commit_messages: list[str], issue_number: int) -> int:
    """Count how many of `commit_messages` cite `issue_number`."""
    pattern = _citation_pattern(issue_number)
    return sum(1 for message in commit_messages if pattern.search(message))


def partition_by_resolution(
    issue_numbers: list[int],
    commit_messages: list[str],
    tracking_issues: set[int],
) -> tuple[list[int], list[int]]:
    """Partition `issue_numbers` into `(resolved, unresolved)`.

    Issue #709's two-signal rule: an issue number is resolved only when
    both signals agree -- at least one commit cites it AND
    `tracking_issues` contains it. A bare citing commit with no
    corroborating registry entry, or a registered gate with no citing
    commit, both count as unresolved -- this is AND, not OR. Every input
    number appears in exactly one of the two returned lists, in input
    order.
    """
    resolved: list[int] = []
    unresolved: list[int] = []
    for number in issue_numbers:
        if citation_count(commit_messages, number) > 0 and number in tracking_issues:
            resolved.append(number)
        else:
            unresolved.append(number)
    return resolved, unresolved


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


def git_commit_messages(
    ref: str,
    cwd: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Return the full message (subject + body) of every commit reachable
    from `ref`, via a local `git log` in `cwd`. Mirrors
    gitapex_scan_retrospective_gate_drift.py's own git_commit_messages exactly."""
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


def load_gate_tracking_issues(path: str) -> set[int]:
    """Return every `.gitapex/ssot.json` `gates[].tracking_issue` value.

    Raises `SsotLedgerError` rather than returning an empty set on a
    missing/malformed registry -- an empty set here would fail the
    tracking-issue signal for every issue number, which is
    indistinguishable from "no gate was ever registered" unless the read
    failure is surfaced instead. Mirrors
    gitapex_scan_retrospective_gate_drift.py's own load_gate_tracking_issues.
    """
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SsotLedgerError(f"{path}: gate registry cannot be read: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SsotLedgerError(f"{path}: gate registry is not valid JSON: {error}") from error

    # `[]`, `"x"`, and `1` are all valid JSON, so a successful parse does
    # not mean the shape is usable -- without this guard, `data.get` below
    # would raise an uncaught AttributeError instead of the documented
    # SsotLedgerError.
    if not isinstance(data, dict):
        raise SsotLedgerError(f"{path}: gate registry must be a JSON object, got {type(data).__name__}")
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SsotLedgerError(f"{path}: gate registry has no usable 'gates' list")

    tracking_issues: set[int] = set()
    for gate in gates:
        tracking_issue = gate.get("tracking_issue") if isinstance(gate, dict) else None
        # `bool` is an `int` subclass in Python, so `isinstance(True, int)`
        # is True -- without the extra check, a stray `"tracking_issue":
        # true` would silently corroborate issue #1 instead of being
        # skipped as the malformed value it is.
        if isinstance(tracking_issue, int) and not isinstance(tracking_issue, bool):
            tracking_issues.add(tracking_issue)
    return tracking_issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Partition retrospective-labelled issue numbers into resolved/unresolved, "
        "using the same two-signal check gitapex_scan_retrospective_gate_drift.py already "
        "implements: a citing commit on --ref AND a corroborating "
        ".gitapex/ssot.json gates[].tracking_issue entry."
    )
    parser.add_argument(
        "issue_number",
        type=int,
        nargs="+",
        help="One or more retrospective-labelled issue numbers to check, e.g. from "
        "mcp__github__list_issues(labels=['retrospective']).",
    )
    parser.add_argument("--ref", default="HEAD", help="Git ref to search for citing commits (default: HEAD)")
    parser.add_argument("--cwd", default=".", help="Repository working directory for git log (default: .)")
    parser.add_argument(
        "--ssot-path",
        default=".gitapex/ssot.json",
        help="Path (relative to --cwd) to the gate registry used as the corroborating "
        "signal (default: .gitapex/ssot.json)",
    )
    args = parser.parse_args(argv)

    try:
        commit_messages = git_commit_messages(args.ref, args.cwd)
        tracking_issues = load_gate_tracking_issues(str(pathlib.Path(args.cwd) / args.ssot_path))
    except (GitLogError, SsotLedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    resolved, unresolved = partition_by_resolution(args.issue_number, commit_messages, tracking_issues)
    # Written only once both reads succeeded, so a caller can never observe
    # a partially-computed partition on stdout.
    print(json.dumps({"unresolved": unresolved, "resolved": resolved}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

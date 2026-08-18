#!/usr/bin/env python3
"""Partition retrospective-labelled issue numbers into resolved/unresolved.

Issue #1176: `merge-retrospective/SKILL.md`'s Step 1 ("Carry-forward
check") previously re-derived its own weaker, citation-only
approximation of "is this retrospective issue's proposed gate still
open" live, every cycle, via a semantic-search tool plus a bare
commit-citation check -- producing observed, concrete cross-session
divergence (issue #1176's own Facts section cites concrete examples).

`.github/scripts/gitapex_scan_retrospective_gate_drift.py` already
implements a stricter two-signal check (issue #709: a citing commit
alone is not proof a gate was actually built -- it also needs a
corroborating `.gitapex/ssot.json` `gates[].tracking_issue` entry). This
script deliberately re-implements (never imports or subprocess-invokes)
that same two-signal logic against a local `git log` and
`.gitapex/ssot.json`, per this repository's own independent-self-
containment convention (see that script's own docstring, and
`skills/drafting-an-acm-issue/scripts/gitapex_check_acm_present.py` /
`skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`
for the identical, already-established pattern of two independently-
duplicated, non-importing checker scripts). Unlike the CI script, this
one takes candidate issue numbers as CLI arguments rather than querying
the GitHub issues API itself -- `merge-retrospective/SKILL.md`'s own
Step 1 obtains candidates via `mcp__github__list_issues` first.

Usage::

    uv run --frozen python3 \\
        skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py \\
        1109 1107 1108 1114

Prints one JSON object to stdout, partitioning every input issue number
into exactly one of two arrays::

    {"unresolved": [1109], "resolved": [1107, 1108, 1114]}

Exit codes:
    0  The partition was computed and printed.
    1  A local `git log` or `.gitapex/ssot.json` read error prevented the
       check from completing (never silently reported as "nothing
       resolved").
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Callable


class GitLogError(RuntimeError):
    """Raised when the local `git log` invocation fails."""


class SsotLedgerError(RuntimeError):
    """Raised when `.gitapex/ssot.json` cannot be read as a usable gate
    registry. Never caught and silently downgraded to an empty
    corroboration set -- that would reopen the exact bare-citation
    false-negative issue #709 exists to close (mirrors
    gitapex_scan_retrospective_gate_drift.py's own identical rationale)."""


# Record separator (0x1e) / unit separator (0x1f): see
# gitapex_scan_retrospective_gate_drift.py's own identical comment -- these
# delimit `git log` entries/fields without risk of an attacker-controlled
# commit message forging a fake boundary.
_LOG_FORMAT = "%x1e%H%x1f%B"


def _citation_pattern(issue_number: int) -> re.Pattern[str]:
    # Digit-boundary-aware: "#187" matches, but neither "#1870" nor
    # "#2187" does.
    return re.compile(rf"(?<!\d)#{issue_number}(?!\d)")


def citation_count(commit_messages: list[str], issue_number: int) -> int:
    """Count how many of `commit_messages` cite `issue_number`."""
    pattern = _citation_pattern(issue_number)
    return sum(1 for message in commit_messages if pattern.search(message))


def partition_resolved(
    issue_numbers: list[int],
    commit_messages: list[str],
    tracking_issues: set[int],
) -> tuple[list[int], list[int]]:
    """Partition every entry in `issue_numbers` into `(unresolved,
    resolved)`. An issue number resolves only when both signals agree: at
    least one commit cites it AND `tracking_issues` contains it (issue
    #709's corroborating-signal rationale) -- mirrors
    gitapex_scan_retrospective_gate_drift.py's own
    `find_no_citation_issues`, restated as a two-way partition rather
    than a single no-citation list."""
    resolved = [n for n in issue_numbers if citation_count(commit_messages, n) > 0 and n in tracking_issues]
    resolved_set = set(resolved)
    unresolved = [n for n in issue_numbers if n not in resolved_set]
    return unresolved, resolved


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


def load_gate_tracking_issues(path: str) -> set[int]:
    """Return every `.gitapex/ssot.json` `gates[].tracking_issue` value."""
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SsotLedgerError(f"{path}: gate registry cannot be read: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SsotLedgerError(f"{path}: gate registry is not valid JSON: {error}") from error

    if not isinstance(data, dict):
        raise SsotLedgerError(f"{path}: gate registry must be a JSON object, got {type(data).__name__}")
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SsotLedgerError(f"{path}: gate registry has no usable 'gates' list")

    tracking_issues: set[int] = set()
    for gate in gates:
        tracking_issue = gate.get("tracking_issue") if isinstance(gate, dict) else None
        # `bool` is an `int` subclass in Python -- without the extra
        # check, a stray `"tracking_issue": true` would silently
        # corroborate issue #1 instead of being skipped as malformed.
        if isinstance(tracking_issue, int) and not isinstance(tracking_issue, bool):
            tracking_issues.add(tracking_issue)
    return tracking_issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Partition retrospective-labelled issue numbers into resolved/unresolved "
        "via the two-signal gate-resolution check."
    )
    parser.add_argument(
        "issue_numbers",
        type=int,
        nargs="+",
        help="Retrospective-labelled issue numbers to check (e.g. from mcp__github__list_issues)",
    )
    parser.add_argument("--ref", default="HEAD", help="Git ref to search for citing commits (default: HEAD)")
    parser.add_argument("--cwd", default=".", help="Repository working directory for git log (default: .)")
    parser.add_argument(
        "--ssot-path",
        default=".gitapex/ssot.json",
        help="Path (relative to --cwd) to the gate registry (default: .gitapex/ssot.json)",
    )
    args = parser.parse_args(argv)

    try:
        commit_messages = git_commit_messages(args.ref, args.cwd)
        tracking_issues = load_gate_tracking_issues(str(pathlib.Path(args.cwd) / args.ssot_path))
    except (GitLogError, SsotLedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    unresolved, resolved = partition_resolved(args.issue_numbers, commit_messages, tracking_issues)
    print(json.dumps({"unresolved": unresolved, "resolved": resolved}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

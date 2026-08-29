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
`skills/drafting-issues/scripts/gitapex_check_acm_present.py` /
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

    # With issue bodies (issue #1297), to also populate the `gate_less`
    # bucket below -- a JSON object mapping issue number to body text:
    uv run --frozen python3 \\
        skills/merge-retrospective/scripts/gitapex_check_retro_gate_resolved.py \\
        1109 1107 --bodies -  <<< '{"1109": "...", "1107": "..."}'

Prints one JSON object to stdout, partitioning every input issue number
into exactly one of three arrays::

    {"unresolved": [1109], "resolved": [1107, 1108, 1114], "gate_less": []}

Issue #1297: a candidate whose body carries either the CI-opened-stub
marker or the zero-repair fast-close marker (`is_gate_less`) is routed to
`gate_less` by a pre-check that runs *before* the two-signal partition
below -- such an issue never had a gate to cite or register, so it cannot
satisfy that check by construction and must not inflate `unresolved`.
`gate_less` is always empty when `--bodies` is omitted, identical to this
script's behavior before this bucket existed.

Exit codes:
    0  The partition was computed and printed.
    1  A local `git log`, `.gitapex/ssot.json`, or `--bodies` read error
       prevented the check from completing (never silently reported as
       "nothing resolved").

detection-logic-property-coverage waiver (issue #1178 gate, on
`_citation_pattern` and `citation_count`'s own `.search()` call):
digit-boundary correctness -- neither "#1870" nor "#2187" matching
"#187" -- is already covered by explicit example tests in the co-located
`test_gitapex_check_retro_gate_resolved.py`
(`test_citation_count_does_not_match_longer_number_containing_target_as_prefix`/
`_as_suffix`), the same boundary cases a Hypothesis `@given` property
test would probe. Issue #1176 scopes this diff to
`skills/merge-retrospective/` only (no `tests/` addition), and the
identical pattern in
`.github/scripts/gitapex_scan_retrospective_gate_drift.py` this module
deliberately mirrors is itself out of that gate's own scope by
construction (its `gitapex_scan_` prefix, not `gitapex_check_`/
`gitapex_gate_`).

Same waiver, same reason, extended to `_ZERO_REPAIR_MARKER_LINE_RE` and
`is_gate_less`'s own `.search()` call (issue #1297): standalone-line-vs-
mid-sentence-quote boundary correctness is already covered by explicit
example tests in the co-located test module
(`test_is_gate_less_matches_zero_repair_marker_with_bullet_prefix`/
`test_is_gate_less_false_when_zero_repair_marker_only_quoted_mid_sentence`),
the same boundary a Hypothesis `@given` property test would probe. This
skill's own scripts directory is still outside
`[tool.pytest.ini_options]` `pythonpath`/`testpaths` (unlike
`.github/scripts`), so a `tests/test_gitapex_check_retro_gate_resolved_properties.py`
addition cannot import this module without a `pyproject.toml`
pythonpath change -- out of scope for issue #1297, same architectural
constraint issue #1176 already established above.
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


class BodiesInputError(RuntimeError):
    """Raised when `--bodies` points at a file/stdin payload that cannot be
    read as a usable number-to-body mapping (issue #1297). Only the
    file-or-JSON-shape failure raises -- a malformed individual entry
    (non-integer key, non-string value) is skipped instead, mirroring
    `load_gate_tracking_issues`'s own per-entry leniency below."""


# Issue #1297: a `retrospective` issue can legitimately close with no gate
# to ever propose -- a bare CI-opened stub, or a zero-repair fast-close
# (merge-retrospective/SKILL.md Step 5). Neither can ever satisfy the
# two-signal check below by construction, so both are excluded from
# consideration entirely rather than counted as unresolved backlog.
_CI_STUB_MARKER = "Automated stub opened by the post-merge-auto-retro gate"
_ZERO_REPAIR_MARKER = "Retrospective status: zero-repair-fast-close"

# `_ZERO_REPAIR_MARKER` is checked as a standalone line, not a bare
# substring like `_CI_STUB_MARKER` above: this repo's own retrospectives
# routinely re-quote an earlier issue's text verbatim inside a later
# issue's free-prose Repairs/Carried-forward section (issue #1297's own
# investigation cites #1038 re-quoting a "Proposed gate:" line 63 times) --
# a bare substring match would misclassify a later, real retrospective as
# gate-less merely for quoting a fast-closed one. `_CI_STUB_MARKER` stays
# a bare substring on purpose: `gitapex_post_merge_retro.py`'s own stub body
# embeds it mid-paragraph, not on its own line, and
# `gitapex_stale_retro_stub_autoclose.py`'s own `is_unenriched_stub` already
# matches it the same way -- anchoring it here would silently stop
# recognizing the real stub shape.
_ZERO_REPAIR_MARKER_LINE_RE = re.compile(  # detection-logic-property-coverage: WAIVED: see module docstring
    r"^[ \t]*[-*]?[ \t]*" + re.escape(_ZERO_REPAIR_MARKER) + r"[ \t]*$", re.MULTILINE
)


# Record separator (0x1e) / unit separator (0x1f): see
# gitapex_scan_retrospective_gate_drift.py's own identical comment -- these
# delimit `git log` entries/fields without risk of an attacker-controlled
# commit message forging a fake boundary.
_LOG_FORMAT = "%x1e%H%x1f%B"


def _citation_pattern(issue_number: int) -> re.Pattern[str]:
    # Digit-boundary-aware: "#187" matches, but neither "#1870" nor
    # "#2187" does.
    return re.compile(rf"(?<!\d)#{issue_number}(?!\d)")  # detection-logic-property-coverage: WAIVED: see docstring


def citation_count(commit_messages: list[str], issue_number: int) -> int:
    """Count how many of `commit_messages` cite `issue_number`."""
    pattern = _citation_pattern(issue_number)
    return sum(
        1
        for message in commit_messages
        if pattern.search(message)  # detection-logic-property-coverage: WAIVED: see docstring
    )


def is_gate_less(body: str) -> bool:
    """Return `True` iff `body` carries either literal gate-less marker
    (issue #1297): the CI-opened stub marker (bare substring), or the
    zero-repair fast-close marker `merge-retrospective/SKILL.md`'s Step 5
    requires (matched only as its own line -- see
    `_ZERO_REPAIR_MARKER_LINE_RE`'s own comment for why the two markers
    are checked differently). `body` is normalized to bare LF line
    endings first: GitHub is known to deliver an issue body with CRLF
    endings for one authored or edited via the web UI, and
    `_ZERO_REPAIR_MARKER_LINE_RE` assumes bare LF -- the same
    normalization `.github/scripts/gitapex_gate_skill_audit_disclosure.py`'s
    own `_normalize_body` already applies for the identical reason."""
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    return _CI_STUB_MARKER in normalized or bool(
        _ZERO_REPAIR_MARKER_LINE_RE.search(  # detection-logic-property-coverage: WAIVED: see module docstring
            normalized
        )
    )


def partition_gate_less(issue_numbers: list[int], bodies: dict[int, str]) -> tuple[list[int], list[int]]:
    """Partition every distinct entry in `issue_numbers` into `(gate_less,
    remaining)`, run *before* `partition_resolved` below. An issue number
    with no entry in `bodies` is never treated as gate-less -- absence of
    a supplied body is not evidence of gate-less-ness, it just means the
    caller had nothing to check. Deduplicates first, same first-occurrence
    order guarantee as `partition_resolved`."""
    deduped_issue_numbers = list(dict.fromkeys(issue_numbers))
    gate_less = [n for n in deduped_issue_numbers if is_gate_less(bodies.get(n, ""))]
    gate_less_set = set(gate_less)
    remaining = [n for n in deduped_issue_numbers if n not in gate_less_set]
    return gate_less, remaining


def load_issue_bodies(path: str | None) -> dict[int, str]:
    """Return a number-to-body mapping read from `path` (issue #1297).
    `path` of `None` returns an empty mapping -- the gate-less pre-check
    then simply finds nothing to exclude, identical to this script's
    behavior before this mapping existed. A three-way argument, not the
    two-way file-or-stdin-on-omission convention
    `gitapex_check_acm_present.py`'s own `--body` argument already
    established in this repository: omitting `--bodies` here means "skip
    the check" (there was nothing to omit-to-stdin before this mapping
    existed), so a distinct `path == "-"` sentinel is required to opt
    into reading standard input instead of a file.

    A key that does not parse as an integer, or a value that is not a
    string (for example JSON `null` for an issue with an empty body), is
    skipped rather than raised on -- mirrors `load_gate_tracking_issues`'s
    own per-entry leniency. Only a file-or-JSON-shape failure raises
    `BodiesInputError`."""
    if path is None:
        return {}
    try:
        raw = sys.stdin.read() if path == "-" else pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BodiesInputError(f"{path}: bodies mapping cannot be read: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BodiesInputError(f"{path}: bodies mapping is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise BodiesInputError(f"{path}: bodies mapping must be a JSON object, got {type(data).__name__}")

    bodies: dict[int, str] = {}
    for key, value in data.items():
        try:
            number = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, str):
            bodies[number] = value
    return bodies


def partition_resolved(
    issue_numbers: list[int],
    commit_messages: list[str],
    tracking_issues: set[int],
) -> tuple[list[int], list[int]]:
    """Partition every distinct entry in `issue_numbers` into `(unresolved,
    resolved)`. An issue number resolves only when both signals agree: at
    least one commit cites it AND `tracking_issues` contains it (issue
    #709's corroborating-signal rationale) -- mirrors
    gitapex_scan_retrospective_gate_drift.py's own
    `find_no_citation_issues`, restated as a two-way partition rather
    than a single no-citation list.

    Deduplicates `issue_numbers` first (first-occurrence order preserved):
    unlike the CI sibling's own `issue_numbers` (always a single label
    search's worth of distinct numbers), this script's own candidate list
    is CLI-supplied and `merge-retrospective/SKILL.md`'s own Step 1 builds
    it from two separate searches (a label search plus a title-text
    fallback for pre-label issues) concatenated together -- an issue
    matching both would otherwise appear twice in the same output array."""
    deduped_issue_numbers = list(dict.fromkeys(issue_numbers))
    resolved = [n for n in deduped_issue_numbers if citation_count(commit_messages, n) > 0 and n in tracking_issues]
    resolved_set = set(resolved)
    unresolved = [n for n in deduped_issue_numbers if n not in resolved_set]
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
        # corroborate issue #1 instead of being skipped as malformed. A
        # gate legitimately tracked under more than one issue (issue
        # #1425) stores a list; flatten it the same way a bare int is
        # added.
        candidates = tracking_issue if isinstance(tracking_issue, list) else [tracking_issue]
        for candidate in candidates:
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                tracking_issues.add(candidate)
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
    parser.add_argument(
        "--bodies",
        default=None,
        help="Path to a JSON file mapping issue numbers to their body text (e.g. from "
        "mcp__github__list_issues with 'body' in fields), used to pre-check for the "
        "gate-less markers before the two-signal partition runs. Pass '-' to read from "
        "standard input. Omit to skip the gate-less pre-check entirely (default).",
    )
    args = parser.parse_args(argv)

    try:
        commit_messages = git_commit_messages(args.ref, args.cwd)
        tracking_issues = load_gate_tracking_issues(str(pathlib.Path(args.cwd) / args.ssot_path))
        bodies = load_issue_bodies(args.bodies)
    except (GitLogError, SsotLedgerError, BodiesInputError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    gate_less, remaining = partition_gate_less(args.issue_numbers, bodies)
    unresolved, resolved = partition_resolved(remaining, commit_messages, tracking_issues)
    print(json.dumps({"unresolved": unresolved, "resolved": resolved, "gate_less": gate_less}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

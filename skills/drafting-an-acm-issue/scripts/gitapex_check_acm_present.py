"""Check a drafted issue body for an Acceptance Criteria Map table and a
Dedup disclosure line.

Step 7 of the drafting-an-acm-issue skill requires the drafted issue body
to carry the Acceptance Criteria Map (see
../references/acceptance-criteria-map.md) and, per issue #1197's own row 3,
a `Dedup: {query used}, {N results reviewed}` (or explicit `Dedup: none
found`) disclosure line -- before the issue is created. Re-checking "does
this body have the table" / "does this body have the Dedup line" by
re-reading prose each run is exactly the kind of repeated, multi-rule,
error-prone match that should be scripted instead. Standard library only.

The ACM-table check is a self-contained duplicate of a sibling skill's own
ACM-presence check (same header regex) -- no skill in this repository
shares a scripts/ directory with another, so each ships its own copy
rather than importing across skill boundaries. If the ACM table's header
row ever changes shape, update both copies together -- nothing enforces
they stay in sync automatically (see tests/test_gitapex_check_acm_present_sync.py,
which only enforces this file's own `_HEADER_RE`, not the Dedup-line
check below -- that check is unique to this file, disclosure-only, and
has no sibling copy to stay in sync with).

The Dedup check does not strip fenced code blocks the way the hooks/
family's own waiver checkers do -- this script validates the agent's own
just-drafted body immediately before issue creation, not a remotely
fetched, potentially attacker-influenced body (contrast
hooks/gitapex_check_acm_present_or_waiver.py's own fence-stripping, added
specifically because that module grades someone *else's* issue body).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The table header row this skill's template uses. Match loosely (any
# whitespace around pipes) so reasonable Markdown re-formatting still passes.
_HEADER_RE = re.compile(
    r"\|\s*Criterion\s*\|\s*Interpretation\s*\|\s*Planned ops\s*\|"
    r"\s*Proof method\s*\|\s*Residual risk\s*\|",
    re.IGNORECASE,
)

# A `Dedup: <non-empty reason>` line, optionally bulleted -- matches the
# `- `/`* ` optional-bullet, non-empty-reason shape this repository's own
# ACM-waiver line convention already uses (hooks/gitapex_check_acm_present_or_waiver.py's
# `_ACM_WAIVER_RE`), applied here to a distinct field name.
_DEDUP_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*Dedup[ \t]*:[ \t]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_acm_table(body_text: str | None) -> bool:
    """Return ``True`` iff ``body_text`` contains the ACM header row."""
    return bool(_HEADER_RE.search(body_text or ""))


def has_dedup_disclosure(body_text: str | None) -> bool:
    """Return ``True`` iff ``body_text`` carries a non-empty ``Dedup:``
    disclosure line (a search query plus result count, or an explicit
    ``Dedup: none found``)."""
    return bool(_DEDUP_RE.search(body_text or ""))


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff the given draft body contains both the ACM table
    and a Dedup disclosure line, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a drafted issue body contains the Acceptance Criteria Map "
        "table and a Dedup: disclosure line."
    )
    parser.add_argument(
        "--body",
        help="Path to the drafted issue body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.body if args.body else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 1

    table_found = has_acm_table(body_text)
    dedup_found = has_dedup_disclosure(body_text)
    if table_found and dedup_found:
        print("PASS: Acceptance Criteria Map table and Dedup disclosure found")
        return 0

    failures = []
    if not table_found:
        failures.append("no Acceptance Criteria Map table found in draft body")
    if not dedup_found:
        failures.append("no Dedup: disclosure line found in draft body")
    print("FAIL: " + "; ".join(failures), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

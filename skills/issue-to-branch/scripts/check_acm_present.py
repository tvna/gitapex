"""Check a PR body for an Acceptance Criteria Map table.

Step 8 of the issue-to-branch skill requires every PR body to carry the
Acceptance Criteria Map (see ../references/acceptance-criteria-map.md), not
just a description of the diff. Re-checking "does this body have the table"
by re-reading prose each run is exactly the kind of repeated, multi-rule,
error-prone match that should be scripted instead. Standard library only.

drafting-an-acm-issue ships an independent copy of this exact checker
(same table shape, same header regex) rather than importing across skill
boundaries. If the ACM table's header row ever changes shape, update
both copies together -- nothing enforces they stay in sync automatically.
"""

from __future__ import annotations

import argparse
import re
import sys

# The table header row this skill's template uses. Match loosely (any
# whitespace around pipes) so reasonable Markdown re-formatting still passes.
_HEADER_RE = re.compile(
    r"\|\s*Criterion\s*\|\s*Interpretation\s*\|\s*Planned ops\s*\|"
    r"\s*Proof method\s*\|\s*Residual risk\s*\|",
    re.IGNORECASE,
)


def has_acm_table(body_text):
    """Return ``True`` iff ``body_text`` contains the ACM header row."""
    return bool(_HEADER_RE.search(body_text or ""))


def main(argv=None):
    """CLI: exit 0 iff the given PR body contains the ACM table, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a PR body contains the Acceptance Criteria Map table."
    )
    parser.add_argument(
        "--body",
        help="Path to the PR body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    if has_acm_table(body_text):
        print("PASS: Acceptance Criteria Map table found")
        return 0
    print("FAIL: no Acceptance Criteria Map table found in PR body", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Check a candidate GitHub issue body for ACM disclosure (table or waiver).

hooks/check-issue-acm-disclosure.sh needs this check bundled *with the
hook itself*. Per docs/repository-layout.md, only skills/ and hooks/ are
deployed runtime primitives when this repository is installed as a
plugin -- .github/ is dev-only CI tooling and is never installed into a
consumer repository.

This is a copy of the same header-table regex duplicated across
skills/drafting-an-acm-issue/scripts/check_acm_present.py,
skills/planning-a-branch-from-an-issue/scripts/check_acm_present.py, and
.github/scripts/gate_acm_issue_disclosure.py -- kept in sync by
tests/test_check_acm_present_sync.py's explicit extras list. The
waiver-line vocabulary below is a narrower claim: only this file and
.github/scripts/gate_acm_issue_disclosure.py implement it at all (the two
skills/*/scripts/check_acm_present.py copies check table presence only,
by design -- neither skill they belong to accepts a waiver in lieu of the
table), and those two are kept in sync by
tests/test_check_acm_present_sync.py's own dedicated waiver-regex sync
test. Deliberately not imported from any of those three: this file must
work standalone from inside a distributed plugin bundle with no access to
.github/ or a sibling skill's scripts/ directory.

Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys

# Same table header shape as the other three copies -- see this module's
# own docstring and tests/test_check_acm_present_sync.py.
_HEADER_RE = re.compile(
    r"\|\s*Criterion\s*\|\s*Interpretation\s*\|\s*Planned ops\s*\|"
    r"\s*Proof method\s*\|\s*Residual risk\s*\|",
    re.IGNORECASE,
)

# Same waiver vocabulary as .github/scripts/gate_acm_issue_disclosure.py:
# `ACM: not-applicable (chore|docs|tracking|defect): <reason>`, a
# non-empty trailing reason required. `defect` (issue #657) covers
# fixing-a-reported-issue's bare defect-report issues, which by design
# never carry an ACM table. The category group is capturing (not `(?:...)`)
# so callers -- specifically hooks/check_pr_issue_acm_disclosure.py, which
# must distinguish a `tracking` waiver from the other three categories --
# can read which category matched via `waiver_category()` below without a
# second, partially-duplicate regex. gate_acm_issue_disclosure.py's own
# copy of this pattern carries the same capturing group, even though nothing
# there reads it, purely so the two `.pattern` strings stay byte-identical
# -- tests/test_check_acm_present_sync.py asserts that equality directly.
_ACM_WAIVER_RE = re.compile(
    r"^[ \t]*[-*]?[ \t]*`?ACM`?[ \t]*:[ \t]*not-applicable[ \t]*"
    r"\((?P<category>chore|docs|tracking|defect)\)[ \t]*:[ \t]*\S.*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_acm_disclosure(body_text):
    """Return True iff `body_text` carries the ACM table or a valid waiver line."""
    # Normalize CRLF/CR line endings before matching, same rationale as
    # gate_acm_issue_disclosure.py's own has_acm_disclosure.
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    return bool(_HEADER_RE.search(normalized) or _ACM_WAIVER_RE.search(normalized))


def waiver_category(body_text):
    """Return the lowercased waiver category ('chore'/'docs'/'tracking'/
    'defect') if `body_text` carries a valid waiver line, else None.

    Added for issue #657's hooks/check_pr_issue_acm_disclosure.py, which
    must deny a PR citing an issue whose waiver category is specifically
    'tracking' with a message distinct from "no ACM/waiver at all" --
    `has_acm_disclosure`'s boolean alone cannot make that distinction."""
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    match = _ACM_WAIVER_RE.search(normalized)
    return match.group("category").lower() if match else None


def main(argv=None):
    """CLI: exit 0 iff the given body discloses an ACM table or waiver, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a candidate GitHub issue body discloses an "
        "Acceptance Criteria Map table or an explicit waiver line."
    )
    parser.add_argument(
        "--body",
        help="Path to the candidate issue body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1
    if has_acm_disclosure(body_text):
        print("PASS: Acceptance Criteria Map (or waiver) disclosed")
        return 0
    print(
        "FAIL: no Acceptance Criteria Map table or ACM waiver line found in issue body",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

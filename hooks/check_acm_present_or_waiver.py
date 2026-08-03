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
from pathlib import Path

# Fenced code blocks only (```/~~~), not single-backtick inline code
# spans: `_ACM_WAIVER_RE` below optionally wraps the literal word "ACM"
# in a single backtick pair (`` `ACM`: not-applicable... ``), so stripping
# inline code the way hooks/check_pr_issue_acm_disclosure.py does would
# strip that legitimate waiver's own "ACM" token and false-negative it --
# confirmed directly before choosing fence-only stripping here, not
# assumed safe by analogy. Added for issue #657's own adversarial review:
# hooks/check_pr_issue_acm_disclosure.py's classify_issue() now calls
# has_acm_disclosure()/waiver_category() on a *remotely fetched*, different
# issue's body -- unlike this file's original use (an issue checking its
# own body at its own creation time), a fenced illustrative ACM table or
# waiver line quoted inside someone else's issue body could otherwise read
# as a real disclosure.
#
# Stateful line scan (fence-marker lines toggle in/out of a fence), not a
# single `re.sub(r"```.*?```", ...)` pass -- a second round of the same
# adversarial review found the naive matched-pair-only regex has two real
# gaps: (1) an *unclosed* fence (an opening marker with no matching close)
# leaves its content fully exposed, since there is no pair to match at
# all; (2) with an *odd* total marker count, content between the "extra"
# unpaired marker and the next one is not consistently identified either
# way. This scan instead toggles fence state per marker line -- an
# unclosed fence extends to end-of-text (dropped), matching how GitHub's
# own renderer treats it, rather than being silently left unstripped.
_FENCE_MARKERS = ("```", "~~~")


def _strip_fences(text):
    lines = (text or "").split("\n")
    kept = []
    fence_marker = None
    for line in lines:
        stripped_line = line.lstrip()
        if fence_marker is None:
            if stripped_line.startswith(_FENCE_MARKERS):
                fence_marker = stripped_line[:3]
                continue
            kept.append(line)
        elif stripped_line.startswith(fence_marker):
            fence_marker = None
    return "\n".join(kept)


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
    normalized = _strip_fences(normalized)
    return bool(_HEADER_RE.search(normalized) or _ACM_WAIVER_RE.search(normalized))


def waiver_category(body_text):
    """Return the lowercased waiver category ('chore'/'docs'/'tracking'/
    'defect') if `body_text` carries a valid waiver line, else None.

    Added for issue #657's hooks/check_pr_issue_acm_disclosure.py, which
    must deny a PR citing an issue whose waiver category is specifically
    'tracking' with a message distinct from "no ACM/waiver at all" --
    `has_acm_disclosure`'s boolean alone cannot make that distinction."""
    normalized = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = _strip_fences(normalized)
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
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.read()
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

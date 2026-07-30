#!/usr/bin/env python3
"""Check a candidate PR body for skill-audit disclosure evidence (the base
two-audit check only).

A local pre-check catches a missing or malformed disclosure section
before a create/update_pull_request call reaches CI, the same
round-trip-avoidance rationale behind hooks/check_acm_present_or_waiver.py.
Per docs/repository-layout.md, only skills/ and hooks/ are deployed
runtime primitives when this repository is installed as a plugin --
.github/ is dev-only CI tooling and is never installed into a consumer
repository.

This is a *deliberately partial* copy of
.github/scripts/gate_skill_audit_disclosure.py: only the base check that
both battle-testing-a-skill and evaluating-skill-quality are disclosed
(find_missing_disclosures there). It does NOT port that script's
conditional extensions (WAIVED-rejection on a description change,
eval-coverage disclosure, security-relevance, design-doc coverage) --
each needs a git-diff-computed fact (which skill's description changed,
which skill is security-relevant, which design docs changed) that only
the CI workflow computes, not a local hook with no equivalent
applicability-diff step. CI remains the full, authoritative gate; this
hook is a fast, partial, local backstop.

Deliberately not imported from .github/scripts/gate_skill_audit_disclosure.py
or any other copy: this file must work standalone from inside a
distributed plugin bundle with no access to .github/. Kept in sync with
that script's own _SECTION_RE/_VERDICTS/pattern-building logic by
tests/test_check_skill_audit_disclosure_hook_sync.py, the same
sync-test pattern tests/test_check_acm_present_sync.py uses for the
ACM-disclosure family.

Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys

_SECTION_RE = re.compile(r"^##[ \t]*Skill audit evidence[ \t]*$", re.IGNORECASE | re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)

# Same closed vocabulary as gate_skill_audit_disclosure.py's own _VERDICTS.
_VERDICTS = {
    "battle-testing-a-skill": ("PASS", "FAIL", "INDETERMINATE"),
    "evaluating-skill-quality": (
        "WELL-FORMED-AND-MATURE",
        "WELL-FORMED-NOT-MATURE",
        "NOT-WELL-FORMED",
    ),
}

_WAIVED_CLAUSE = r"WAIVED[ \t]*:[ \t]*\S.*"


def _name_prefix(name):
    return r"^[ \t]*[-*]?[ \t]*`?" + re.escape(name) + r"`?[ \t]*:[ \t]*"


def _line_pattern(name, verdicts):
    verdict_alt = "|".join(re.escape(v) for v in verdicts)
    return re.compile(
        _name_prefix(name)
        + r"(?:(?:"
        + verdict_alt
        + r")\b(?:[ \t]+\S.*)?|"
        + _WAIVED_CLAUSE
        + r")[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )


_LINE_PATTERNS = {name: _line_pattern(name, verdicts) for name, verdicts in _VERDICTS.items()}


def _normalize_body(body_text):
    return (body_text or "").replace("\r\n", "\n").replace("\r", "\n")


def _extract_section(body_text):
    """Return the "## Skill audit evidence" section body, or None if absent."""
    match = _SECTION_RE.search(body_text)
    if not match:
        return None
    next_heading = _NEXT_HEADING_RE.search(body_text, match.end())
    end = next_heading.start() if next_heading else len(body_text)
    return body_text[match.end():end]


def find_missing_disclosures(body_text):
    """Return the list of audit names with no valid disclosure line in body_text."""
    section = _extract_section(_normalize_body(body_text))
    if section is None:
        return list(_VERDICTS)
    return [name for name, pattern in _LINE_PATTERNS.items() if not pattern.search(section)]


def main(argv=None):
    """CLI: exit 0 iff the given body discloses both audits, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a candidate PR body discloses battle-testing-a-skill "
        "and evaluating-skill-quality audit evidence."
    )
    parser.add_argument(
        "--body",
        help="Path to the candidate PR body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1

    missing = find_missing_disclosures(body_text)
    if not missing:
        print("PASS: skill audit evidence disclosed for both audits")
        return 0
    print(
        "FAIL: PR body is missing a disclosed verdict (or waiver) for: " + ", ".join(missing),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

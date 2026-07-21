#!/usr/bin/env python3
"""Check a PR body for skill-audit disclosure evidence.

Issue #248 (refs #242, #246): a PR that adds or modifies a skill's
SKILL.md must disclose that battle-testing-a-skill and
evaluating-skill-quality were run against it -- a verdict for each named
audit, or an explicit waiver with a reason -- rather than depending on
someone remembering to ask for either audit by name. This is the
deterministic backstop: it checks that disclosure was made, not that the
audits actually passed, which stays a human/reviewer judgment matching
the two audits' own model-graded nature.

The calling workflow decides applicability (only invoked when the PR's
diff adds or modifies a skills/*/SKILL.md file); this script only grades
the body text handed to it. Deliberately not placed inside either audited
skill's own directory: both declare a portability level whose procedure
must not depend on this repository's specific tooling, and parsing this
repository's PR-body convention is exactly such repository-specific glue.

Mirrors skills/issue-to-branch/scripts/check_acm_present.py's CLI shape
(--body <path> or stdin, PASS/FAIL output, same exit-code convention)
without importing or duplicating it -- different section, different
verdict vocabulary, no shared contract between the two checks.
"""

from __future__ import annotations

import argparse
import re
import sys

_SECTION_RE = re.compile(r"^##[ \t]*Skill audit evidence[ \t]*$", re.IGNORECASE | re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)

# Each audit's closed disclosure-line vocabulary. "WAIVED: <reason>" is
# accepted for either audit and is checked separately, not folded into
# these tuples, since it requires a non-empty trailing reason.
_VERDICTS = {
    "battle-testing-a-skill": ("PASS", "FAIL", "INDETERMINATE"),
    "evaluating-skill-quality": (
        "WELL-FORMED-AND-MATURE",
        "WELL-FORMED-NOT-MATURE",
        "NOT-WELL-FORMED",
    ),
}


def _line_pattern(name, verdicts):
    verdict_alt = "|".join(re.escape(v) for v in verdicts)
    return re.compile(
        r"^[ \t]*[-*]?[ \t]*`?"
        + re.escape(name)
        + r"`?[ \t]*:[ \t]*(?:(?:"
        + verdict_alt
        + r")\b(?:[ \t]+\S.*)?|WAIVED[ \t]*:[ \t]*\S.*)[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )


_LINE_PATTERNS = {name: _line_pattern(name, verdicts) for name, verdicts in _VERDICTS.items()}


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
    # Normalize CRLF/CR line endings before matching: GitHub is known to
    # deliver github.event.pull_request.body with CRLF endings for PRs
    # authored/edited via the web UI, and the heading/line regexes below
    # assume bare LF.
    body_text = (body_text or "").replace("\r\n", "\n").replace("\r", "\n")
    section = _extract_section(body_text)
    if section is None:
        return list(_VERDICTS)
    return [name for name, pattern in _LINE_PATTERNS.items() if not pattern.search(section)]


def main(argv=None):
    """CLI: exit 0 iff the given PR body discloses both audits, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that a PR body discloses battle-testing-a-skill and "
        "evaluating-skill-quality audit evidence for a skill-content change."
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
    missing = find_missing_disclosures(body_text)
    if not missing:
        print("PASS: skill audit evidence disclosed for both audits")
        return 0
    print(
        "FAIL: PR body is missing a disclosed verdict (or waiver) for: "
        + ", ".join(missing),
        file=sys.stderr,
    )
    print(
        "Add a '## Skill audit evidence' section with one line per audit, e.g.:\n"
        "  - battle-testing-a-skill: PASS\n"
        "  - evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
        "or '<audit>: WAIVED: <reason>' if intentionally skipped.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

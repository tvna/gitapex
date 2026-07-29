#!/usr/bin/env python3
"""Determine whether a skills/*/SKILL.md's frontmatter heuristically
matches a security-relevant keyword.

Issue #517 (refs #454): heuristically flag a skill as security-relevant by
keyword match against its own frontmatter block only (name, description,
and any other frontmatter fields) -- not the full SKILL.md body, which in
this meta-repo mentions "gate" constantly in ordinary prose (CI gates,
quality gates, etc.) and would otherwise over-match almost every skill.

The original implementation extracted the frontmatter block with a bash
`sed -n '/^---$/,/^---$/p'` range address. A sed range re-arms itself: once
the closing '---' of the first range is consumed, sed resumes scanning for
the *opening* address again, so any later '---' line in the SKILL.md body
(a markdown horizontal rule is a common one) re-opens the range -- and if
no further '---' follows it, sed prints straight through to EOF. Both
failure modes (leaking unrelated body prose into the frontmatter scan,
confirmed by direct repro during review) defeat the frontmatter-only
scoping this heuristic depends on.

Mirrors skill_description_diff.py's own extract_description: find the
opening '---', then search for the *closing* '---' by an explicit
line-index search (not a re-armable regex range), and treat a missing
closing delimiter as "no parseable frontmatter" -- fail closed, do not
scan the body -- rather than reading to EOF.

Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys

# \b is a prefix/suffix word-boundary, so "gated"/"gateway"/"trusted"/
# "trustworthy" match while "aggregate"/"delegate"/"negotiate" do not.
_SECURITY_KEYWORDS_RE = re.compile(r"\b(security|gate|trust)", re.IGNORECASE)


def extract_frontmatter(text):
    """Return the frontmatter block's raw text (the opening '---' line
    through the closing '---' line, inclusive), or None if there is no
    well-formed '---'-delimited frontmatter (missing opening or closing
    delimiter)."""
    text = (text or "").lstrip("﻿")
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    return "\n".join(lines[: end + 1])


def is_security_relevant(text):
    """True iff `text`'s frontmatter block (not its full body) matches a
    security-relevant keyword."""
    frontmatter = extract_frontmatter(text)
    if frontmatter is None:
        return False
    return bool(_SECURITY_KEYWORDS_RE.search(frontmatter))


def main(argv=None):
    """CLI: read a SKILL.md's content (--path or stdin), print 'relevant'
    or 'not-relevant', exit 0."""
    parser = argparse.ArgumentParser(
        description="Print 'relevant' or 'not-relevant' depending on whether "
        "a SKILL.md's frontmatter block heuristically matches a "
        "security-relevant keyword."
    )
    parser.add_argument(
        "--path",
        help="Path to the SKILL.md content to check; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        text = open(args.path, encoding="utf-8").read() if args.path else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1
    print("relevant" if is_security_relevant(text) else "not-relevant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

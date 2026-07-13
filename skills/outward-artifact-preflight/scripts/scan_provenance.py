"""Scan text for undisclosed provenance markers. See ../SKILL.md check 1.

Flags the mechanical, pattern-matchable part of check 1 (a bare model ID,
a session URL, a known internal-tool fingerprint) so it is not re-reasoned
in prose each run. Whether a flagged hit is actually undisclosed (vs. an
agreed, ASCII-clean disclosure trailer) remains a judgment call for the
model -- this script only surfaces candidates, it does not decide.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys

# Non-exhaustive by design (see SKILL.md's open-invariant rule): these are
# the common instances, not a closed allowlist. Add more patterns as new
# fingerprint shapes are observed.
_PATTERNS = [
    ("model identifier", re.compile(r"\bclaude-[a-z0-9.\-]+\b", re.IGNORECASE)),
    ("session URL", re.compile(r"https?://[^\s]*\bsession[_/][A-Za-z0-9]+", re.IGNORECASE)),
    ("anthropic session domain", re.compile(r"https?://claude\.ai/[^\s]*", re.IGNORECASE)),
    ("generic build/agent tag", re.compile(r"\b(generated|built)[- ](by|with|using)[- ][A-Za-z0-9_.\-]+\b", re.IGNORECASE)),
]


def scan(text):
    """Return a list of ``(line_no, label, matched_text)`` candidate hits.

    A bare "model identifier" match is cheap to trigger on non-leak text
    that merely contains the substring "claude-" -- a repo/org name like
    "claude-md", a filename like "claude-md-base.md", this repo's own
    ".claude-plugin" directory, or a disclosed eval-config model pin such
    as a YAML "model: claude-sonnet-4.6" line. None of those are provenance
    leaks by themselves. A real leak is disclosed *in context*: alongside a
    session URL, a claude.ai link, or explicit "generated/built by"
    phrasing on the same line. So a "model identifier" hit is only kept
    when the same line also carries one of those other markers; the other
    marker types (session URL, claude.ai domain, generic build/agent tag)
    are specific enough to report unconditionally.
    """
    hits = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line_hits = []
        for label, pattern in _PATTERNS:
            for match in pattern.finditer(line):
                line_hits.append((label, match.group(0)))
        has_corroborating_context = any(
            label != "model identifier" for label, _ in line_hits
        )
        for label, matched in line_hits:
            if label == "model identifier" and not has_corroborating_context:
                continue
            hits.append((line_no, label, matched))
    return hits


def main(argv=None):
    """CLI: print candidate provenance markers found in the given text."""
    parser = argparse.ArgumentParser(
        description="Scan an artifact's text for undisclosed provenance markers."
    )
    parser.add_argument(
        "--file",
        help="Path to the artifact text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 1
    hits = scan(text)
    if not hits:
        print("PASS: no candidate provenance markers found")
        return 0
    for line_no, label, matched in hits:
        print(f"line {line_no}: {label}: {matched}")
    print(
        f"FAIL: {len(hits)} candidate marker(s) found -- review each: is it an "
        "agreed, disclosed convention, or must it be removed?",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

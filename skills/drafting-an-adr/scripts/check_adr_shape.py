"""Check a drafted ADR body for the required sections and a valid Status.

Step 9 of the drafting-an-adr skill requires the drafted ADR body to
carry its required sections (see ../references/adr-template.md) before
it is treated as final. Re-checking "does this have the required
sections" by re-reading prose each run is exactly the kind of repeated,
mechanical match that should be scripted instead. Standard library only.

This is a self-contained checker -- no skill in this repository shares a
scripts/ directory with another, so this ships its own copy rather than
importing across skill boundaries.
"""

from __future__ import annotations

import argparse
import re
import sys

_REQUIRED_HEADINGS = (
    "Status",
    "Context and Problem Statement",
    "Decision Outcome",
    "Consequences",
)

_STATUS_VALUES = ("proposed", "accepted", "deprecated", "superseded")

_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def _section_body(body_text, heading):
    """Text between a ``## <heading>`` line (exclusive) and the next
    ``## `` heading or end of file. ``None`` if the heading is absent."""
    match = re.search(r"^##[ \t]+" + re.escape(heading) + r"[ \t]*$", body_text, re.MULTILINE)
    if not match:
        return None
    rest = body_text[match.end():]
    next_heading = _HEADING_RE.search(rest)
    return rest[: next_heading.start()] if next_heading else rest


def missing_headings(body_text):
    """Return the list of required headings absent from ``body_text``."""
    return [h for h in _REQUIRED_HEADINGS if _section_body(body_text, h) is None]


_STATUS_LINE_RE = re.compile(r"^(" + "|".join(_STATUS_VALUES) + r")\b", re.IGNORECASE)


def has_valid_status(body_text):
    """``True`` iff the Status section's first non-blank line starts with
    one of the recognized values -- trailing detail on the same line
    (e.g. "Accepted (approved by @owner, 2026-06-02)") is allowed."""
    section = _section_body(body_text, "Status")
    if section is None:
        return False
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        return bool(_STATUS_LINE_RE.match(stripped))
    return False


def has_nonempty_consequences(body_text):
    """``True`` iff the Consequences section has real (non-comment,
    non-whitespace) content."""
    section = _section_body(body_text, "Consequences")
    if section is None:
        return False
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") or stripped.endswith("-->"):
            continue
        return True
    return False


def check_adr_shape(body_text):
    """Return a list of failure-reason strings; empty means PASS."""
    failures = []
    missing = missing_headings(body_text)
    if missing:
        failures.append(f"missing required heading(s): {', '.join(missing)}")
    if not missing and not has_valid_status(body_text):
        failures.append(
            "Status section's value is not one of "
            + "/".join(_STATUS_VALUES)
        )
    if not missing and not has_nonempty_consequences(body_text):
        failures.append("Consequences section has no real content")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check that a drafted ADR body has the required sections and a valid Status."
    )
    parser.add_argument(
        "--body",
        help="Path to the drafted ADR body text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1

    failures = check_adr_shape(body_text)
    if not failures:
        print("PASS: ADR body has all required sections and a valid Status")
        return 0
    print("FAIL: ADR body is missing required shape:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Check that every axis section in an agent-product-scope-shaped doc
carries its four required fields, non-empty.

SKILL.md Step 6 requires updating "the relevant axis section" when a
candidate's research changes one -- this is a narrow, deterministic
check that the section still has the shape a reader depends on
(Governs / Current scope / an Owning reference / Boundary), rather than
a full cross-file drift gate synchronizing every axis against its
owning file (a Codex review on this repository's PR #447 suggested
that broader gate; this is the appropriately-scoped first step, not
that). Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys

# A "## Axis <letter>: <name>" heading. Case-sensitive "Axis" by design --
# every section in docs/agent-product-scope.md uses this exact casing.
_AXIS_HEADING_RE = re.compile(r"^## Axis ([A-Za-z0-9]+): (.+)$", re.MULTILINE)

# A bolded field label at the start of a line, e.g. "**Governs:**" or
# "**Owning skill:**". Captures the label text (without the surrounding
# ** and trailing :) and the rest of the line as its value.
_FIELD_RE = re.compile(r"^\*\*([A-Za-z][A-Za-z ]*):\*\*\s*(.*)$", re.MULTILINE)

# Required fields, matched case-insensitively against the captured label.
# "Owning" is deliberately a prefix match (Owning doc/issue/issues/skill
# all satisfy it) since different axes cite different kinds of owner.
_REQUIRED_EXACT = ("governs", "current scope", "boundary")
_REQUIRED_PREFIX = "owning"


def _split_sections(body_text: str):
    """Yield (axis_label, axis_name, section_text) for every '## Axis X:'
    heading in ``body_text``, where ``section_text`` runs to the next
    '## ' heading or end of file."""
    matches = list(_AXIS_HEADING_RE.finditer(body_text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        yield m.group(1), m.group(2), body_text[start:end]


def _missing_fields(section_text: str) -> list[str]:
    """Return the required field names absent or empty in ``section_text``."""
    found = {}
    for m in _FIELD_RE.finditer(section_text):
        label = m.group(1).strip().lower()
        value = m.group(2).strip()
        found[label] = value
    missing = []
    for required in _REQUIRED_EXACT:
        if not found.get(required):
            missing.append(required)
    has_owning = any(
        label.startswith(_REQUIRED_PREFIX) and value
        for label, value in found.items()
    )
    if not has_owning:
        missing.append("owning ...")
    return missing


def check_axis_shape(body_text: str) -> list[str]:
    """Return one evidence string per axis section that is missing a
    required field, or an offense for a section that could not be split
    (no '## Axis X:' heading found at all). Empty list means every axis
    section found has all four required fields."""
    sections = list(_split_sections(body_text))
    if not sections:
        return ["no '## Axis <letter>: ...' heading found in the document"]
    offenses = []
    for label, name, section_text in sections:
        missing = _missing_fields(section_text)
        if missing:
            offenses.append(
                f"Axis {label} ({name}): missing {', '.join(missing)}"
            )
    return offenses


def main(argv=None):
    """CLI: exit 0 iff every axis section in the given file has all four
    required fields, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that every '## Axis X:' section in an "
        "agent-product-scope-shaped doc has Governs/Current scope/"
        "Owning .../Boundary, all non-empty."
    )
    parser.add_argument("path", help="Path to the doc to check.")
    args = parser.parse_args(argv)
    try:
        body_text = open(args.path, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1
    offenses = check_axis_shape(body_text)
    if not offenses:
        print("PASS: every axis section has all four required fields")
        return 0
    print("FAIL: incomplete axis section(s):", file=sys.stderr)
    for offense in offenses:
        print(f"  - {offense}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

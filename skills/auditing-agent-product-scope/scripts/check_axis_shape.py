"""Check that every axis section in an agent-product-scope-shaped doc
carries its four required fields, non-empty.

SKILL.md Step 7 requires updating "the relevant axis section" when a
candidate's research changes one -- this is a narrow, deterministic
check that the section still has the shape a reader depends on
(Governs / Current scope / an Owning reference / Boundary), rather
than a full cross-file drift gate synchronizing every axis against
its owning file. Standard library only, no network calls, no side
effects.

Flags any axis label outside the expected set (default A-F, the six
axes this repository has today) as an offense rather than silently
accepting it: a hostile "deciding quote" pasted verbatim into an
evidence file (per SKILL.md Step 6) could forge a spurious "## Axis
G: ..." heading with fabricated fields that would otherwise pass. A
new axis letter is not necessarily an attack -- the scope map has
legitimately grown before -- but it must be a deliberate, visible
decision (passing --expected-labels to include it), not something
this checker accepts by default.

Also verifies every expected label appears exactly once: checking
only for unexpected labels would let a document missing several axes,
or with a duplicated axis heading, pass with no offenses. Each axis
section is bounded by the next '## ' heading of any kind, not only
the next '## Axis' heading, so a missing field in the final axis
section can't be silently "supplied" by a same-named field label in
an unrelated later section (e.g. '## Maintenance').
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

# A "## Axis <letter>: <name>" heading. Case-sensitive "Axis" by design --
# every section in docs/agent-product-scope.md uses this exact casing.
_AXIS_HEADING_RE = re.compile(r"^## Axis ([A-Za-z0-9]+): (.+)$", re.MULTILINE)

# Any level-two heading at all -- marks where an axis section ends, so a
# non-axis section right after the last axis (e.g. '## Maintenance') is
# never scanned as if it were still part of that axis's content.
_ANY_H2_RE = re.compile(r"^## ", re.MULTILINE)

# A bolded field label at the start of a line, e.g. "**Governs:**" or
# "**Owning skill:**". Captures the label text (without the surrounding
# ** and trailing :) and the rest of the line as its value.
_FIELD_RE = re.compile(r"^\*\*([A-Za-z][A-Za-z ]*):\*\*\s*(.*)$", re.MULTILINE)

# Required fields, matched case-insensitively against the captured label.
# "Owning" is deliberately a prefix match (Owning doc/issue/issues/skill
# all satisfy it) since different axes cite different kinds of owner.
_REQUIRED_EXACT = ("governs", "current scope", "boundary")
_REQUIRED_PREFIX = "owning"

# The axis letters this repository's scope map currently defines (A-F).
# Overridable via --expected-labels so a deliberate new axis is a visible
# CLI-argument change, not something this checker accepts silently.
_DEFAULT_EXPECTED_LABELS = frozenset("ABCDEF")


def _split_sections(body_text: str) -> Iterator[tuple[str, str, str]]:
    """Yield (axis_label, axis_name, section_text) for every '## Axis X:'
    heading in ``body_text``, where ``section_text`` runs to the next
    '## ' heading of any kind (axis or not) or end of file."""
    axis_matches = list(_AXIS_HEADING_RE.finditer(body_text))
    h2_starts = [m.start() for m in _ANY_H2_RE.finditer(body_text)]
    for m in axis_matches:
        start = m.end()
        end = next((s for s in h2_starts if s > m.start()), len(body_text))
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
    has_owning = any(label.startswith(_REQUIRED_PREFIX) and value for label, value in found.items())
    if not has_owning:
        missing.append("owning ...")
    return missing


def check_axis_shape(body_text: str, expected_labels: frozenset[str] = _DEFAULT_EXPECTED_LABELS) -> list[str]:
    """Return one evidence string per offense found: a required field
    missing from an axis section, a label outside ``expected_labels``, an
    expected label that never appears, a label appearing more than once,
    or (if no '## Axis X:' heading exists at all) that single top-level
    offense. Empty list means every expected label appears exactly once,
    each with all four required fields."""
    sections = list(_split_sections(body_text))
    if not sections:
        return ["no '## Axis <letter>: ...' heading found in the document"]
    offenses = []
    seen_labels = []
    for label, name, section_text in sections:
        seen_labels.append(label)
        if label not in expected_labels:
            offenses.append(
                f"Axis {label} ({name}): label not in the expected set "
                f"({''.join(sorted(expected_labels))}) -- confirm this is "
                "a deliberate new axis, not injected content, then pass "
                "--expected-labels to include it"
            )
            continue
        missing = _missing_fields(section_text)
        if missing:
            offenses.append(f"Axis {label} ({name}): missing {', '.join(missing)}")
    seen_set = set(seen_labels)
    for expected in sorted(expected_labels):
        if expected not in seen_set:
            offenses.append(f"Axis {expected}: expected but no '## Axis {expected}:' heading found in the document")
    for label in sorted(seen_set):
        count = seen_labels.count(label)
        if count > 1:
            offenses.append(f"Axis {label}: appears {count} times, expected exactly once")
    return offenses


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff every axis section in the given file has all four
    required fields, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that every '## Axis X:' section in an "
        "agent-product-scope-shaped doc has Governs/Current scope/"
        "Owning .../Boundary, all non-empty."
    )
    parser.add_argument("path", help="Path to the doc to check.")
    parser.add_argument(
        "--expected-labels",
        default="".join(sorted(_DEFAULT_EXPECTED_LABELS)),
        help="Concatenated axis letters this doc is expected to contain "
        "(default: %(default)s). Pass a wider set when a deliberate new "
        "axis is added.",
    )
    args = parser.parse_args(argv)
    try:
        body_text = Path(args.path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"error: could not decode {args.path} as UTF-8: {exc}", file=sys.stderr)
        return 1
    expected_labels = frozenset(args.expected_labels)
    offenses = check_axis_shape(body_text, expected_labels)
    if not offenses:
        print("PASS: every axis section has all four required fields")
        return 0
    print("FAIL: incomplete axis section(s):", file=sys.stderr)
    for offense in offenses:
        print(f"  - {offense}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

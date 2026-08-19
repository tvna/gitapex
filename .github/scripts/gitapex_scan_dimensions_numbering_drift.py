#!/usr/bin/env python3
"""Deterministic gate: references/dimensions.md's own numbering and
cross-reference integrity.

Issue #1229. `evaluating-deterministic-gate-quality`'s two-lane numbered
list (deterministic-shape checks 1-6, probabilistic-maturity dimensions
7-N -- one continuous ordinal sequence spanning two `##` sections) had no
drift gate of its own: a renumbering slip (a skipped number, a duplicate,
an out-of-order insert) or a stale "dimension N" / "shape check N"
cross-reference in dimensions.md or SKILL.md could land unnoticed. Issue
#1229's own drafting caught exactly this failure mode by hand: an earlier
draft misnumbered the new dimension as "22", not noticing 22 and 23 were
already taken, until a direct read of dimensions.md caught it.

**Scope, deliberately narrow, same as the two precedents this mirrors**
(`gitapex_scan_contract_axis_vocabulary_drift.py`, issue #949;
`gitapex_scan_skill_quality_rubric_vocabulary_drift.py`, issue #993). This
is a wording/structure lock, not a quality judgment: it cannot tell
whether a dimension's own grading criteria are good, correct, or worth
having -- that stays review's job. It asserts only that the real ordinal
sequence has no gap, duplicate, or out-of-order entry; that the two
declared lane ranges and the schema's own numeric bound track that real
sequence; and that a "dimension N" / "shape check N" cross-reference in
either source file names a number that actually exists in its own lane.

Unlike the two precedents, this lock's numbered items are markdown
ordered-list entries ("N. **Title.**"), not "## N. <Name>" headings, and
they span one continuous sequence across two `##` sections rather than one
closed list starting at 1 -- `references/dimensions.md`'s own intro
explains why: shape checks are "fixed rules" (1-6), dimensions are "need
judgment" (7-N), the same split `SKILL.md`'s Two-lane split names. The
file's own Contents section carries a similarly-numbered "1. [...]" /
"2. [...]" list, but those are links, never bold -- this module's own item
regex requires a bold title immediately after the ordinal, so the Contents
list is never mistaken for a real shape-check/dimension item.

Checks, grouped by the file they read:

  ``references/dimensions.md``
    1. Every ordered-list item under "## Deterministic-shape checks" is
       numbered 1..S with no gap, duplicate, or out-of-order entry, where
       S is that section's own real item count.
    2. Every ordered-list item under "## Probabilistic-maturity
       dimensions" continues that same sequence, numbered (S+1)..(S+D)
       with no gap, duplicate, or out-of-order entry, where D is that
       section's own real item count.
    3. The "**Deterministic-shape checks** (X-Y)" declaration matches the
       real shape-check span (X=1, Y=S).
    4. The "**Probabilistic-maturity dimensions** (X-Y)" declaration
       matches the real dimension span (X=S+1, Y=S+D).
    5. Every "shape check N" cross-reference names a number in [1, S].
    6. Every "dimension N" cross-reference names a number in [S+1, S+D] --
       a citation naming a shape-check's own number as a "dimension" is
       exactly the category confusion this check exists to catch, not
       only a plainly out-of-range one.

  ``SKILL.md``
    7-8. The same "shape check N" / "dimension N" cross-reference checks
       as 5-6 above, applied to the second file that makes these claims.

  ``references/output-schema.json``
    9. ``findings.items.properties.dimensionId.maximum`` equals S+D.
    10. The ``findings`` array's own top-level description states the
       real "dimensions.md, 1-<N>" span.

Fail-closed: a missing or unreadable file, a missing/duplicated/empty
section heading, zero items found in either lane (nothing to compute a
count from), or malformed JSON, each exit 2 rather than degrading to
"nothing to check, pass".

``ScanError`` and ``read_text`` reused from the shared
``_gitapex_vocabulary_lock.py`` module (issue #993) rather than copied a
third time. This module's own section-bounding helper is not the shared
`extract_section` -- that helper bounds a section to the next heading of
the *same or shallower* level; the shape-check lane's own bound here is a
different, specific `##` heading (`Probabilistic-maturity dimensions`),
not merely the next one of any kind.

Usage::

    python3 .github/scripts/gitapex_scan_dimensions_numbering_drift.py
    python3 .github/scripts/gitapex_scan_dimensions_numbering_drift.py \\
        --skill-dir path/to/evaluating-deterministic-gate-quality

Exit codes:
    0  Every locked requirement holds.
    1  At least one requirement drifted (each reported on stderr).
    2  An input could not be read or parsed, so the check could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from _gitapex_vocabulary_lock import ScanError, read_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"

DIMENSIONS_MD = "references/dimensions.md"
SKILL_MD = "SKILL.md"
SCHEMA_JSON = "references/output-schema.json"

SHAPE_HEADING = "## Deterministic-shape checks"
DIMENSION_HEADING = "## Probabilistic-maturity dimensions"

# One numbered ordered-list item: "N. **...". Requires a bold title
# immediately after the ordinal, at the true start of a line, so neither
# the Contents section's own link-list ("1. [Deterministic-shape
# checks](#...)") nor an indented in-body enumeration (e.g. dimension 24's
# own "(1) state a concrete reason...") is mistaken for a real
# shape-check/dimension item.
_ITEM_RE = re.compile(r"^(\d+)\.\s+\*\*", re.MULTILINE)

_SHAPE_RANGE_RE = re.compile(r"\*\*Deterministic-shape checks\*\*\s*\((\d+)-(\d+)\)")
_DIMENSION_RANGE_RE = re.compile(r"\*\*Probabilistic-maturity dimensions\*\*\s*\((\d+)-(\d+)\)")

# "dimension N" / "shape check N" cross-references -- case-insensitive
# since both files capitalize the word sentence-initially ("Dimension
# 23's own answer..."). \b on both sides so "dimension 10" is not matched
# inside a longer run of digits.
_DIMENSION_REF_RE = re.compile(r"\bdimension\s+(\d+)\b", re.IGNORECASE)
_SHAPE_CHECK_REF_RE = re.compile(r"\bshape check\s+(\d+)\b", re.IGNORECASE)

_SCHEMA_MAX_PATH = ("properties", "findings", "items", "properties", "dimensionId", "maximum")
_SCHEMA_FINDINGS_DESC_PATH = ("properties", "findings", "description")
_SCHEMA_RANGE_RE = re.compile(r"dimensions\.md,\s*1-(\d+)")


@dataclass(frozen=True)
class LaneCount:
    """One review's own real lane spans: the highest shape-check number
    and the highest dimension number actually declared in
    ``references/dimensions.md`` right now. Every other check in this
    module compares a declared citation against one of these two, rather
    than against a hardcoded expectation."""

    shape_max: int
    dimension_max: int


def _section_between(text: str, start_heading: str, end_heading: str | None, path_label: str) -> str:
    """Body from ``start_heading`` up to (but excluding) ``end_heading``,
    or to end-of-text when ``end_heading`` is ``None``.

    Raises :class:`ScanError` when either heading is absent or duplicated
    -- each means the structure this module assumes is not there, which is
    a "cannot check" answer, not a passing one.
    """
    starts = [m.start() for m in re.finditer(rf"^{re.escape(start_heading)}[ \t]*$", text, re.MULTILINE)]
    if not starts:
        raise ScanError(f"{path_label}: heading not found: {start_heading!r}")
    if len(starts) > 1:
        raise ScanError(f"{path_label}: heading appears {len(starts)} times, expected exactly once: {start_heading!r}")
    begin = starts[0] + len(start_heading)
    if end_heading is None:
        return text[begin:]

    ends = [m.start() for m in re.finditer(rf"^{re.escape(end_heading)}[ \t]*$", text, re.MULTILINE)]
    if not ends:
        raise ScanError(f"{path_label}: heading not found: {end_heading!r}")
    if len(ends) > 1:
        raise ScanError(f"{path_label}: heading appears {len(ends)} times, expected exactly once: {end_heading!r}")
    return text[begin : ends[0]]


def _check_sequence(numbers: list[int], expected_start: int, label: str, path_label: str) -> list[str]:
    """Problems for any gap, duplicate, or out-of-order entry in
    ``numbers`` against a contiguous run starting at ``expected_start`` --
    shared by the shape-check and dimension sequence checks, which start
    their own contiguous run at a different point (1 for shape checks; the
    shape-check count plus one for dimensions, continuing the same ordinal
    sequence rather than restarting it)."""
    problems: list[str] = []
    seen: set[int] = set()
    for n in numbers:
        if n in seen:
            problems.append(f"{path_label}: {label} '{n}.' appears more than once")
        seen.add(n)

    expected_sequence = list(range(expected_start, expected_start + len(seen)))
    if sorted(seen) != expected_sequence:
        problems.append(
            f"{path_label}: {label} items are numbered {sorted(seen)}, expected a contiguous "
            f"sequence starting at {expected_start} with no gap ({expected_sequence})"
        )
    if numbers != sorted(numbers):
        problems.append(f"{path_label}: {label} items are numbered {numbers} in document order, expected ascending")
    return problems


def compute_lane_counts(dimensions_text: str) -> tuple[LaneCount, list[str]]:
    """The real shape-check/dimension item counts, plus problems for any
    gap, duplicate, or out-of-order numbering in either lane.

    Raises :class:`ScanError` if either lane has zero items -- there is
    then nothing for any other check in this module to compare against.
    """
    shape_section = _section_between(dimensions_text, SHAPE_HEADING, DIMENSION_HEADING, DIMENSIONS_MD)
    dimension_section = _section_between(dimensions_text, DIMENSION_HEADING, None, DIMENSIONS_MD)

    shape_numbers = [int(m.group(1)) for m in _ITEM_RE.finditer(shape_section)]
    dimension_numbers = [int(m.group(1)) for m in _ITEM_RE.finditer(dimension_section)]
    if not shape_numbers:
        raise ScanError(f"{DIMENSIONS_MD}: no numbered items found under {SHAPE_HEADING!r} -- cannot compute a count")
    if not dimension_numbers:
        raise ScanError(
            f"{DIMENSIONS_MD}: no numbered items found under {DIMENSION_HEADING!r} -- cannot compute a count"
        )

    problems = _check_sequence(shape_numbers, 1, "shape-check item", DIMENSIONS_MD)
    shape_max = max(shape_numbers)
    problems += _check_sequence(dimension_numbers, shape_max + 1, "dimension item", DIMENSIONS_MD)
    dimension_max = max(dimension_numbers)

    return LaneCount(shape_max=shape_max, dimension_max=dimension_max), problems


def check_lane_range_declarations(dimensions_text: str, counts: LaneCount) -> list[str]:
    """The two "**<Lane name>** (X-Y)" declarations against the real lane
    spans ``counts`` already computed."""
    problems: list[str] = []

    match = _SHAPE_RANGE_RE.search(dimensions_text)
    if match is None:
        problems.append(
            f"{DIMENSIONS_MD}: no '**Deterministic-shape checks** (X-Y)' declaration found -- "
            "the shape-check range lock cannot run"
        )
    else:
        start, end = int(match.group(1)), int(match.group(2))
        if (start, end) != (1, counts.shape_max):
            problems.append(
                f"{DIMENSIONS_MD}: declares shape checks '({start}-{end})' but {counts.shape_max} "
                f"shape-check item(s) exist, numbered 1-{counts.shape_max} -- update the range in "
                "the same change as the heading"
            )

    expected_start = counts.shape_max + 1
    match = _DIMENSION_RANGE_RE.search(dimensions_text)
    if match is None:
        problems.append(
            f"{DIMENSIONS_MD}: no '**Probabilistic-maturity dimensions** (X-Y)' declaration found -- "
            "the dimension range lock cannot run"
        )
    else:
        start, end = int(match.group(1)), int(match.group(2))
        if (start, end) != (expected_start, counts.dimension_max):
            problems.append(
                f"{DIMENSIONS_MD}: declares dimensions '({start}-{end})' but "
                f"{counts.dimension_max - counts.shape_max} dimension item(s) exist, numbered "
                f"{expected_start}-{counts.dimension_max} -- update the range in the same change as the heading"
            )
    return problems


def check_cross_references(text: str, counts: LaneCount, path_label: str) -> list[str]:
    """Every "shape check N" / "dimension N" cross-reference in ``text``
    against the real lane each phrase names -- absent is silence, not a
    finding, since these are optional cross-references, not a required
    declaration."""
    problems: list[str] = []
    for match in _SHAPE_CHECK_REF_RE.finditer(text):
        n = int(match.group(1))
        if not (1 <= n <= counts.shape_max):
            problems.append(
                f"{path_label}: cites 'shape check {n}' but shape checks are only numbered "
                f"1-{counts.shape_max} -- stale or wrong cross-reference"
            )
    for match in _DIMENSION_REF_RE.finditer(text):
        n = int(match.group(1))
        if not (counts.shape_max + 1 <= n <= counts.dimension_max):
            problems.append(
                f"{path_label}: cites 'dimension {n}' but dimensions are only numbered "
                f"{counts.shape_max + 1}-{counts.dimension_max} -- stale or wrong cross-reference"
            )
    return problems


def _node_at(schema: object, *path: str) -> object:
    """The value at ``path`` inside ``schema``. Raises :class:`ScanError`
    rather than returning ``None`` for a missing or wrongly-shaped node:
    "the field is gone" must not collapse into "the field is empty"."""
    node: object = schema
    walked: list[str] = []
    for key in path:
        walked.append(key)
        if not isinstance(node, dict) or key not in node:
            raise ScanError(f"{SCHEMA_JSON}: no node at {'.'.join(walked)}")
        node = node[key]
    return node


def check_schema(schema_text: str, counts: LaneCount) -> list[str]:
    """``output-schema.json``'s own dimensionId ceiling and its
    findings-array description's "dimensions.md, 1-N" citation, both
    against the real dimension span ``counts`` already computed."""
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as error:
        raise ScanError(f"{SCHEMA_JSON}: is not valid JSON: {error}") from error

    problems: list[str] = []
    maximum = _node_at(schema, *_SCHEMA_MAX_PATH)
    if maximum != counts.dimension_max:
        problems.append(
            f"{SCHEMA_JSON}: findings[].dimensionId.maximum is {maximum!r} but {counts.dimension_max} "
            "is the real highest dimension number -- update the schema bound in the same change as "
            "the heading"
        )

    description = _node_at(schema, *_SCHEMA_FINDINGS_DESC_PATH)
    if not isinstance(description, str):
        raise ScanError(f"{SCHEMA_JSON}: findings.description is not a string")
    match = _SCHEMA_RANGE_RE.search(description)
    if match is None:
        problems.append(
            f"{SCHEMA_JSON}: findings.description has no 'dimensions.md, 1-<N>' span -- "
            "the schema range-citation lock cannot run"
        )
    elif int(match.group(1)) != counts.dimension_max:
        problems.append(
            f"{SCHEMA_JSON}: findings.description cites 'dimensions.md, 1-{match.group(1)}' but "
            f"{counts.dimension_max} is the real highest dimension number -- update the citation in "
            "the same change as the heading"
        )
    return problems


def scan(skill_dir: Path) -> list[str]:
    """Every drift message for ``skill_dir``; empty means every lock holds."""
    dimensions_text = read_text(skill_dir / DIMENSIONS_MD)
    skill_text = read_text(skill_dir / SKILL_MD)
    schema_text = read_text(skill_dir / SCHEMA_JSON)

    counts, problems = compute_lane_counts(dimensions_text)
    problems += check_lane_range_declarations(dimensions_text, counts)
    problems += check_cross_references(dimensions_text, counts, DIMENSIONS_MD)
    problems += check_cross_references(skill_text, counts, SKILL_MD)
    problems += check_schema(schema_text, counts)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=DEFAULT_SKILL_DIR,
        help="evaluating-deterministic-gate-quality skill directory (default: this repository's own).",
    )
    args = parser.parse_args(argv)

    try:
        problems = scan(args.skill_dir)
    except ScanError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("Dimensions-numbering drift lock could not run -- failing closed.", file=sys.stderr)
        return 2

    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr)
        print(
            f"FAIL: {len(problems)} dimensions-numbering lock(s) drifted in {args.skill_dir}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: dimensions-numbering locks hold in {args.skill_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

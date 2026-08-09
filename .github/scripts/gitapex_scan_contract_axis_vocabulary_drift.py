#!/usr/bin/env python3
"""Deterministic gate: the Contract role / input-domain closure axis keeps its
classification vocabulary.

Issue #949. `evaluating-deterministic-gate-quality` grew a fifth cross-cutting
axis whose whole content is a *classification vocabulary*: three
Design-by-Contract roles (precondition / postcondition / invariant), two
input-domain kinds (structural/protocol, which should be closed; threat/safety
classification, which should stay open and non-exhaustive), a warning-only
limit, and a "never both" division of responsibility against dimension 15.
Prose that only names a vocabulary has nothing holding it to the vocabulary:
issue #406 recorded `evaluating-skill-quality`'s own Contract discipline
metadata drifting stale from that skill's actual procedure twice, and issue
#877's own gate exists because a sidecar's line-count claims went stale three
times. This gate locks the fifth axis's terms so a later edit that drops one --
or re-closes the open half of sub-judgment 2 into a finite list -- fails CI
instead of relying on reviewer memory.

Prior art, named rather than re-derived: `tvna/claude-md`'s
`scripts/scan_nonexhaustive_invariant_drift.py` locks a fixed registry of that
repository's own instruction-file safety bullets to the literal marker phrase
``non-exhaustive instances``, for exactly this failure mode. The registry shape
below (a stable anchor per locked requirement, so a wording refresh around the
anchor does not silently drop a row) is that script's shape applied to a skill's
reference prose plus its structured-output schema.

Why a new script rather than extending
``skills/evaluating-deterministic-gate-quality/scripts/gitapex_check_gate_shape.py``,
which issue #949's own Acceptance Criteria Map offered as the first option:
that checker is scoped by its own module docstring to Domain 2 (an
agent-harness hook subprocess) and grades a *target* hook script handed to it.
This gate grades this repository's own skill content, in no domain at all. The
two share no input, no output shape, and no caller.

**Scope, deliberately narrow.** This is a wording/structure lock, not a quality
judgment. It cannot tell whether the axis's prose is *good*, whether a
classification is *correct*, or whether the axis is worth having -- all three
stay review's job. It asserts only that the named terms are still present where
the skill says they are, that the declared axis count still matches the axis
headings, and that the schema's own enums still spell the same vocabulary.

Checks, grouped by the file they read:

  ``SKILL.md``
    1. The ``### Axis: Contract role / input-domain closure`` heading exists.
    2. That section carries the warning-only limit verbatim.
    3. That section links to the reference file's own anchor, so the pointer
       cannot rot into a dangling one while both files still parse.
    4. The declared axis count word matches the number of ``### Axis:``
       headings actually present -- the drift that "Four cross-cutting axes"
       would have become the moment a fifth landed.
    4b. Every "the other N axes" cross-reference elsewhere in the file matches
       that heading count minus one. Added after an audit round caught exactly
       this second count going stale while the declaration in check 4 stayed
       correct.

  ``references/cross-cutting-axes.md``
    5. The ``## Axis: Contract role / input-domain closure`` section exists.
    6-8. That section carries all three DbC role labels, both input-domain
       kind labels, and the ``non-exhaustive`` marker for the open half.
    9. That section carries the warning-only limit verbatim, so the axis
       cannot silently start affecting a verdict from either file's wording.
    10. That section carries the "Never both" rule and cites dimension 15 by
       number, so the division of responsibility survives an edit.

  ``references/output-schema.json``
    11. ``crossCuttingAxes.contractRoleInputDomainClosure`` exists and its
       ``contractRole``/``inputDomainKind`` enums hold exactly the expected
       token sets -- the machine-readable half of the same vocabulary, which
       would otherwise drift from the prose independently.

Fail-closed, per the dimension-15 rule this repository already holds its own
gates to: a missing or unreadable file, a section heading that is present but
whose section is empty, and malformed JSON each exit 2 rather than degrading
to "nothing to check, pass". An anchor that matches more than one heading is
also an error, not a first-match-wins guess.

Usage::

    python3 .github/scripts/gitapex_scan_contract_axis_vocabulary_drift.py
    python3 .github/scripts/gitapex_scan_contract_axis_vocabulary_drift.py \\
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"

SKILL_MD = "SKILL.md"
AXES_MD = "references/cross-cutting-axes.md"
SCHEMA_JSON = "references/output-schema.json"

AXIS_NAME = "Contract role / input-domain closure"
SKILL_AXIS_HEADING = f"### Axis: {AXIS_NAME}"
AXES_AXIS_HEADING = f"## Axis: {AXIS_NAME}"

# The one sentence fragment that makes this axis warning-only. Locked in both
# files: issue #949's own Acceptance Criteria Map requires it stated in each,
# and a limit stated in only one of two places a reader may open is not a
# limit. Quoted from the Compatibility awareness axis, which established the
# precedent, so the two axes cannot drift into two different warning-only
# wordings.
WARNING_ONLY_MARKER = "never change a verdict solely because of this axis"

# The anchor SKILL.md's pointer must resolve to. Derived from the reference
# file's own heading by GitHub's slug rules ("/" dropped, spaces to "-", so the
# " / " separator leaves the doubled hyphen) -- written out literally rather
# than computed, because a computed slug would silently follow the heading
# wherever it drifted, which is the opposite of what a lock is for.
AXES_ANCHOR = "cross-cutting-axes.md#axis-contract-role--input-domain-closure"

_AXIS_HEADING_RE = re.compile(r"^###[ \t]+Axis:[ \t]+\S.*$", re.MULTILINE)
_AXIS_COUNT_RE = re.compile(r"\*\*([A-Za-z]+) cross-cutting axes\*\*")
# Every "the other N axes" phrasing anywhere in SKILL.md, each of which must
# equal the heading count minus the one axis doing the referring. Added after
# an audit round found the fifth axis had landed while one such phrase still
# said "the other three axes": the declaration lock above covers exactly one
# sentence, so a second count restated elsewhere in the same file drifted with
# nothing watching it -- the failure mode this whole module exists to prevent,
# reappearing one sentence away from its own gate.
_OTHER_AXES_RE = re.compile(r"\bthe other ([A-Za-z]+) axes\b")
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

EXPECTED_CONTRACT_ROLES = frozenset({"precondition", "postcondition", "invariant", "mixed", "indeterminate"})
EXPECTED_INPUT_DOMAIN_KINDS = frozenset(
    {"structural-protocol", "threat-classification", "both-readings", "indeterminate"}
)


class ScanError(Exception):
    """An input could not be read or parsed -- exit 2, never a silent pass."""


@dataclass(frozen=True)
class SectionRequirement:
    """One locked substring inside one file's own axis section.

    ``label`` names the requirement in the failure message; ``needle`` is the
    literal text that must survive. Matching is case-sensitive on purpose: the
    bold role labels and the schema tokens are a closed vocabulary, and a
    re-cased ``**precondition**`` is exactly the kind of quiet respelling that
    breaks a downstream consumer keyed on the documented spelling.
    """

    label: str
    needle: str


ROLE_REQUIREMENTS = (
    SectionRequirement("DbC role: precondition", "**Precondition**"),
    SectionRequirement("DbC role: postcondition", "**Postcondition**"),
    SectionRequirement("DbC role: invariant", "**Invariant**"),
)

DOMAIN_REQUIREMENTS = (
    SectionRequirement("input domain: structural/protocol", "**Structural / protocol value**"),
    SectionRequirement(
        "input domain: threat/safety classification",
        "**Threat / safety-classification category**",
    ),
    SectionRequirement("open-domain marker", "non-exhaustive"),
)

DIVISION_REQUIREMENTS = (
    SectionRequirement("never-both rule", "Never both"),
    SectionRequirement("dimension 15 citation", "dimension 15"),
)


def read_text(path: Path) -> str:
    """Read ``path`` as UTF-8, raising :class:`ScanError` on any failure.

    Every read failure is the same outcome here -- the check could not run --
    so an unreadable file must not reach the caller as an empty string that
    every substring check would then report as ordinary drift.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ScanError(f"{path}: not found") from error
    except UnicodeDecodeError as error:
        raise ScanError(f"{path}: could not decode as UTF-8: {error}") from error
    except OSError as error:
        raise ScanError(f"{path}: could not be read: {error}") from error


def extract_section(text: str, heading: str, path_label: str) -> str:
    """The body under ``heading``, up to the next heading of the same or a
    shallower level.

    Raises :class:`ScanError` when the heading is absent, appears more than
    once, or opens an empty section: each means the structure this gate assumes
    is not there, which is a "cannot check" answer, not a passing one.
    """
    level = len(heading) - len(heading.lstrip("#"))
    occurrences = [m.start() for m in re.finditer(rf"^{re.escape(heading)}[ \t]*$", text, re.MULTILINE)]
    if not occurrences:
        raise ScanError(f"{path_label}: heading not found: {heading!r}")
    if len(occurrences) > 1:
        raise ScanError(f"{path_label}: heading appears {len(occurrences)} times, expected exactly once: {heading!r}")

    start = occurrences[0] + len(heading)
    rest = text[start:]
    next_heading = re.search(rf"^#{{1,{level}}}[ \t]+\S", rest, re.MULTILINE)
    body = rest[: next_heading.start()] if next_heading else rest
    if not body.strip():
        raise ScanError(f"{path_label}: section {heading!r} is empty")
    return body


def check_section(section: str, requirements: tuple[SectionRequirement, ...], where: str) -> list[str]:
    """Failure messages for every requirement in ``requirements`` that ``section``
    no longer satisfies."""
    return [
        f"{where}: lost {req.label} -- expected literal text {req.needle!r} in the axis section"
        for req in requirements
        if req.needle not in section
    ]


def check_other_axes_counts(skill_text: str) -> list[str]:
    """Every "the other N axes" cross-reference against the heading count minus
    the one axis doing the referring.

    Unlike the declaration lock, a file with no such phrase is fine -- these are
    optional cross-references, not a required declaration -- so an empty match
    set is silence, not a finding.
    """
    expected = len(_AXIS_HEADING_RE.findall(skill_text)) - 1
    problems: list[str] = []
    for word in _OTHER_AXES_RE.findall(skill_text):
        stated = _NUMBER_WORDS.get(word.lower())
        if stated is None:
            problems.append(
                f"{SKILL_MD}: cross-reference says 'the other {word} axes', which is not a recognized number word"
            )
        elif stated != expected:
            problems.append(
                f"{SKILL_MD}: cross-reference says 'the other {word} axes' but {expected} other "
                "axes exist -- update every such count in the same change as the heading"
            )
    return problems


def check_axis_count(skill_text: str) -> list[str]:
    """The declared "**N cross-cutting axes**" count against the real number of
    ``### Axis:`` headings."""
    headings = _AXIS_HEADING_RE.findall(skill_text)
    match = _AXIS_COUNT_RE.search(skill_text)
    if match is None:
        return [
            f"{SKILL_MD}: no '**<number> cross-cutting axes**' declaration found -- "
            f"the axis-count lock cannot run, and {len(headings)} '### Axis:' heading(s) are present"
        ]
    word = match.group(1).lower()
    declared = _NUMBER_WORDS.get(word)
    if declared is None:
        return [f"{SKILL_MD}: axis count declared as {match.group(1)!r}, which is not a recognized number word"]
    if declared != len(headings):
        return [
            f"{SKILL_MD}: declares {declared} cross-cutting axes but carries "
            f"{len(headings)} '### Axis:' heading(s) -- update the count in the same change as the heading"
        ]
    return []


def _enum_at(schema: object, *path: str) -> frozenset[str]:
    """The ``enum`` list at ``path`` inside ``schema``, as a set of strings.

    Raises :class:`ScanError` rather than returning an empty set for a missing
    or wrongly-shaped node: "the field is gone" and "the field lists nothing"
    must not collapse into the same silent answer.
    """
    node: object = schema
    walked: list[str] = []
    for key in path:
        walked.append(key)
        if not isinstance(node, dict) or key not in node:
            raise ScanError(f"{SCHEMA_JSON}: no node at {'.'.join(walked)}")
        node = node[key]
    if not isinstance(node, dict) or not isinstance(node.get("enum"), list):
        raise ScanError(f"{SCHEMA_JSON}: {'.'.join(path)} has no enum list")
    return frozenset(str(v) for v in node["enum"])


def check_schema_vocabulary(schema_text: str) -> list[str]:
    """The schema's own enum tokens against this module's expected vocabulary."""
    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as error:
        raise ScanError(f"{SCHEMA_JSON}: is not valid JSON: {error}") from error

    base = (
        "properties",
        "crossCuttingAxes",
        "properties",
        "contractRoleInputDomainClosure",
        "properties",
    )
    problems: list[str] = []
    for field, expected in (
        ("contractRole", EXPECTED_CONTRACT_ROLES),
        ("inputDomainKind", EXPECTED_INPUT_DOMAIN_KINDS),
    ):
        actual = _enum_at(schema, *base, field)
        if actual != expected:
            problems.append(
                f"{SCHEMA_JSON}: {field} enum is {sorted(actual)}, expected {sorted(expected)} -- "
                "the schema's vocabulary and this gate's own registry must be changed together"
            )
    return problems


def scan(skill_dir: Path) -> list[str]:
    """Every drift message for ``skill_dir``; empty means every lock holds."""
    skill_text = read_text(skill_dir / SKILL_MD)
    axes_text = read_text(skill_dir / AXES_MD)
    schema_text = read_text(skill_dir / SCHEMA_JSON)

    skill_section = extract_section(skill_text, SKILL_AXIS_HEADING, SKILL_MD)
    axes_section = extract_section(axes_text, AXES_AXIS_HEADING, AXES_MD)

    problems: list[str] = []
    problems += check_section(
        skill_section,
        (
            SectionRequirement("warning-only limit", WARNING_ONLY_MARKER),
            SectionRequirement("pointer to the reference section", AXES_ANCHOR),
        ),
        SKILL_MD,
    )
    problems += check_axis_count(skill_text)
    problems += check_other_axes_counts(skill_text)
    problems += check_section(
        axes_section,
        (
            SectionRequirement("warning-only limit", WARNING_ONLY_MARKER),
            *ROLE_REQUIREMENTS,
            *DOMAIN_REQUIREMENTS,
            *DIVISION_REQUIREMENTS,
        ),
        AXES_MD,
    )
    problems += check_schema_vocabulary(schema_text)
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
        print("Contract-axis vocabulary lock could not run -- failing closed.", file=sys.stderr)
        return 2

    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr)
        print(
            f"FAIL: {len(problems)} contract-axis vocabulary lock(s) drifted in {args.skill_dir}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: contract-axis vocabulary locks hold in {args.skill_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

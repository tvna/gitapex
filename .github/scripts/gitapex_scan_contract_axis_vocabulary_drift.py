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

  ``references/security-level.md``
    12. That file's own "What this axis does not cover" section states, in
       its closing "narrower than all N" sentence, the same total check 4b
       already computes (the other-axes count) plus a fixed offset of three
       non-axis items (dimensions 1/15 lumped as one bullet, mechanism-fit
       lumped as one bullet, dimension 23) that this module's own change
       does not touch. Added after that exact phrase was found to have
       silently drifted through "four" -> "six" -> "seven" across three
       prior axis additions with nothing checking it -- the same failure
       mode check 4b closed for SKILL.md's own cross-references, reappearing
       in a second file check 4b's own scope never reached.

Fail-closed, per the dimension-15 rule this repository already holds its own
gates to: a missing or unreadable file, a section heading that is present but
whose section is empty, and malformed JSON each exit 2 rather than degrading
to "nothing to check, pass". An anchor that matches more than one heading is
also an error, not a first-match-wins guess.

``ScanError``, ``read_text``, and ``extract_section`` moved to the shared
``_gitapex_vocabulary_lock.py`` module (issue #993) once a second gate of
this same shape (`gitapex_scan_skill_quality_rubric_vocabulary_drift.py`)
needed the identical three primitives -- a duplicated copy of exactly the
kind of drift this gate class exists to prevent, reproduced between the
gates themselves. No behavior changed by that move.

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

from _gitapex_vocabulary_lock import ScanError, check_number_word_matches, extract_section, read_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"

SKILL_MD = "SKILL.md"
AXES_MD = "references/cross-cutting-axes.md"
SCHEMA_JSON = "references/output-schema.json"
SECURITY_LEVEL_MD = "references/security-level.md"

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

# security-level.md's own closing sentence, spanning a line break in the
# real file ("...is narrower\nthan all seven:"), hence \s+ rather than a
# literal space between "all" and the number.
_NARROWER_THAN_ALL_RE = re.compile(r"narrower\s+than\s+all\s+([A-Za-z]+)\s*:", re.MULTILINE)

# security-level.md's "What this axis does not cover" section lists one
# bullet per OTHER axis (the same count check_other_axes_counts computes)
# plus three bullets for concerns that are not axes at all: dimensions
# 1/15 (lumped as one bullet), mechanism-fit's two questions (lumped as one
# bullet), and dimension 23. None of those three bullets is added, removed,
# or renumbered by this module's own change, so the offset is a constant,
# not something a future axis addition needs to touch.
_SECURITY_LEVEL_NON_AXIS_BUCKETS = 3

EXPECTED_CONTRACT_ROLES = frozenset({"precondition", "postcondition", "invariant", "mixed", "indeterminate"})
EXPECTED_INPUT_DOMAIN_KINDS = frozenset(
    {"structural-protocol", "threat-classification", "both-readings", "indeterminate"}
)


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
    expected = _other_axes_count(skill_text)
    return check_number_word_matches(
        _OTHER_AXES_RE.findall(skill_text),
        expected,
        lambda word: f"{SKILL_MD}: cross-reference says 'the other {word} axes', which is not a recognized number word",
        lambda word, _stated: (
            f"{SKILL_MD}: cross-reference says 'the other {word} axes' but {expected} other "
            "axes exist -- update every such count in the same change as the heading"
        ),
    )


def _other_axes_count(skill_text: str) -> int:
    """Number of ``### Axis:`` headings in ``skill_text`` minus one -- the
    "other axes" count shared by check_other_axes_counts and
    check_security_level_count, computed once so the two never drift apart
    from each other."""
    return len(_AXIS_HEADING_RE.findall(skill_text)) - 1


def check_axis_count(skill_text: str) -> list[str]:
    """Every declared "**N cross-cutting axes**" count against the real number
    of ``### Axis:`` headings -- every occurrence, not only the first.

    A second declaration sentence added later in the file, restating the
    count, would otherwise drift exactly the way check 4b's own cross-
    references already have (see that check's module-docstring rationale);
    grading only ``re.search``'s first match left that same exposure open
    for this simpler, single-sentence form.
    """
    headings = _AXIS_HEADING_RE.findall(skill_text)
    matches = _AXIS_COUNT_RE.findall(skill_text)
    if not matches:
        return [
            f"{SKILL_MD}: no '**<number> cross-cutting axes**' declaration found -- "
            f"the axis-count lock cannot run, and {len(headings)} '### Axis:' heading(s) are present"
        ]
    return check_number_word_matches(
        matches,
        len(headings),
        lambda word: f"{SKILL_MD}: axis count declared as {word!r}, which is not a recognized number word",
        lambda _word, declared: (
            f"{SKILL_MD}: declares {declared} cross-cutting axes but carries "
            f"{len(headings)} '### Axis:' heading(s) -- update the count in the same change as the heading"
        ),
    )


def check_security_level_count(skill_dir: Path, other_axes_count: int) -> list[str]:
    """security-level.md's own "narrower than all N" count against
    ``other_axes_count`` plus the three fixed non-axis buckets its "What
    this axis does not cover" section also lists."""
    text = read_text(skill_dir / SECURITY_LEVEL_MD)
    match = _NARROWER_THAN_ALL_RE.search(text)
    if match is None:
        return [
            f"{SECURITY_LEVEL_MD}: no 'narrower than all <number>:' sentence found -- "
            "the security-level cross-reference lock cannot run"
        ]
    expected = other_axes_count + _SECURITY_LEVEL_NON_AXIS_BUCKETS
    return check_number_word_matches(
        [match.group(1)],
        expected,
        lambda word: f"{SECURITY_LEVEL_MD}: count declared as {word!r}, which is not a recognized number word",
        lambda word, _stated: (
            f"{SECURITY_LEVEL_MD}: says 'narrower than all {word}' but "
            f'{expected} items are named in its own "What this axis does not cover" list '
            f"({other_axes_count} other axis/axes + {_SECURITY_LEVEL_NON_AXIS_BUCKETS} non-axis items) -- "
            "update the count in the same change as the heading"
        ),
    )


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
    problems += check_security_level_count(skill_dir, _other_axes_count(skill_text))
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

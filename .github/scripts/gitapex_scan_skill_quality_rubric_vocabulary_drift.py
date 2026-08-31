#!/usr/bin/env python3
"""Deterministic gate: evaluating-skill-quality's nine-dimension rubric and
Agentic operation mechanism-fit vocabulary stay internally consistent.

Issue #993. evaluating-deterministic-gate-quality's fifth cross-cutting axis
(Contract role / input-domain closure) already has a vocabulary/structure
drift-lock gate (`.github/scripts/gitapex_scan_contract_axis_vocabulary_drift.py`,
issue #949): a script that asserts a declared count, named headings, and
enumerated vocabulary all stay consistent with the real document, without
ever judging whether the prose content itself is good. evaluating-skill-quality
has never had the same class of lock: its own nine maturity dimensions and its
Agentic operation mechanism-fit section's nine named step-level checks are asserted only in
prose, with nothing keeping a future edit's declared count, range citation,
or heading structure honest.

**Scope, deliberately narrow, same as the precedent this mirrors.** This is
a wording/structure lock, not a quality judgment. It cannot tell whether a
dimension's own grading criteria are *good*, *correct*, or *worth having* --
that stays review's job, and rubric.md's own nine dimensions are explicitly
"deliberately not scripted" (SKILL.md's Two lanes section). It asserts only
that a declared dimension count matches the real number of dimension
headings, that a declared numeric range ("dimensions 1-9") matches that same
count, that the nine numbered headings are present, non-duplicate, non-empty,
and in order, and that the nine named Agentic operation mechanism-fit step labels are still
present verbatim.

No schema-vocabulary check exists in this module, unlike the precedent it
mirrors: evaluating-skill-quality carries no output/verdict-record JSON
Schema today (confirmed: `skills/evaluating-skill-quality/references/`
holds no such file), so there is no schema enum to lock against. Adding one
is tracked separately (issue #993's own "Out of scope" section) rather than
forced into this change.

``ScanError``, ``read_text``, and ``extract_section`` live in the shared
``_gitapex_vocabulary_lock.py`` module (also used by the precedent this
mirrors) rather than being copied here a second time -- a duplicated copy
of exactly the primitives a vocabulary-lock gate is built from is the same
two-copies-drift failure mode this gate class exists to prevent.

Checks, grouped by the file they read:

  ``SKILL.md``
    1. Every bold dimension-count declaration (`**nine dimensions**`,
       `**nine-dimension**`) matches the real number of `## N. <Name>`
       headings in `references/rubric.md`.
    2. Every literal `dimensions 1-N` full-span range citation matches that
       same count.
    3. The `## Agentic operation mechanism-fit` section carries all nine bold step-level
       check labels (Skill vs. subagent, Skill vs. hook, Skill vs.
       CLAUDE.md, Skill vs. multiple skills / cohesion, Skill-step vs.
       bundled script, Model/effort tier fit, Tool-capability
       verification, Subagent delegation scope, Invocation-mode fit).

  ``references/rubric.md``
    4. Every literal `dimensions 1-N` full-span range citation here too
       (same check as SKILL.md's, applied to the second file that makes
       this claim).
    5. The nine `## N. <Name>` dimension headings are present exactly
       once each, numbered 1 through the real count with no gap or
       duplicate, in ascending document order, and each carries a
       non-empty body.

A range like `dimensions 8-9` (the Behavioural-evidence / Cross-model-
robustness exception pair) is a legitimate sub-range with no relationship to
the total count, not a stale full-span claim -- the range check only matches
a span that literally starts at 1, so it is never mistaken for one.

Fail-closed: a missing or unreadable file, zero dimension headings found at
all (nothing to compute a count from), or a missing/duplicate/empty
Agentic operation mechanism-fit section, each exit 2 rather than degrading to "nothing to
check, pass".

Usage::

    python3 .github/scripts/gitapex_scan_skill_quality_rubric_vocabulary_drift.py
    python3 .github/scripts/gitapex_scan_skill_quality_rubric_vocabulary_drift.py \\
        --skill-dir path/to/evaluating-skill-quality

Exit codes:
    0  Every locked requirement holds.
    1  At least one requirement drifted (each reported on stderr).
    2  An input could not be read or parsed, so the check could not run.
"""

from __future__ import annotations

import argparse
import re
import sys
from functools import partial
from pathlib import Path

from _gitapex_vocabulary_lock import ScanError, check_number_word_matches, extract_section, read_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-skill-quality"

SKILL_MD = "SKILL.md"
RUBRIC_MD = "references/rubric.md"

MECHANISM_FIT_HEADING = "## Agentic operation mechanism-fit"

MECHANISM_FIT_STEP_LABELS = (
    "Skill vs. subagent",
    "Skill vs. hook",
    "Skill vs. CLAUDE.md",
    "Skill vs. multiple skills / cohesion",
    "Skill-step vs. bundled script",
    "Model/effort tier fit",
    "Tool-capability verification",
    "Subagent delegation scope",
    "Invocation-mode fit",
)

_DIMENSION_HEADING_RE = re.compile(r"^## (\d+)\.[ \t]+\S.*$", re.MULTILINE)
# A dimension section's real end: the next level-1 or level-2 heading of any
# kind, numbered or not -- same "same level or shallower" rule extract_section
# (in the shared _gitapex_vocabulary_lock module) uses for its own boundary.
_NEXT_LEVEL_1_OR_2_HEADING_RE = re.compile(r"^#{1,2}[ \t]+\S", re.MULTILINE)
# Matches both the plural prose form ("**nine dimensions**") and the
# hyphenated adjectival form ("**nine-dimension**"); "dimensions?" makes the
# trailing "s" optional so the singular hyphenated spelling also matches.
# Case-insensitive: rubric.md already capitalizes sentence-initial
# "Dimensions" (e.g. "Dimensions 8-9's ..."), so a future full-span or
# count citation rephrased to start a sentence must not silently escape
# this lock just because of a capital D.
_DIMENSION_COUNT_RE = re.compile(r"\*\*([A-Za-z]+)[ -]dimensions?\*\*", re.IGNORECASE)
# Only a range that STARTS at 1 is a full-span claim this gate can check --
# "dimensions 8-9" (the Behavioural-evidence/Cross-model-robustness
# exception pair) is a real, legitimate sub-range with no relationship to
# the total count, so the regex anchors the start explicitly rather than
# matching any "N-M" pair. Plural "dimensions" only -- singular "dimension
# 1-7" (the Verdicts section's "every dimension 1-7 clears" exception
# clause, deliberately excluding the tooling-dependent 8-9 pair) is a
# different, legitimate sub-range claim, not a full-span one.
_RANGE_RE = re.compile(r"\bdimensions\s+1-(\d+)\b", re.IGNORECASE)


def check_dimension_headings(rubric_text: str) -> tuple[int, list[str]]:
    """The real dimension count, plus problems for any gap, duplicate,
    out-of-order numbering, or empty section. Raises :class:`ScanError` if
    zero headings are found at all -- there is then nothing for any other
    check in this module to compare against."""
    matches = list(_DIMENSION_HEADING_RE.finditer(rubric_text))
    if not matches:
        raise ScanError(f"{RUBRIC_MD}: no '## N. <Name>' dimension headings found -- cannot compute a count")

    numbers = [int(m.group(1)) for m in matches]
    problems: list[str] = []
    seen: set[int] = set()
    for n in numbers:
        if n in seen:
            problems.append(f"{RUBRIC_MD}: dimension heading '## {n}.' appears more than once")
        seen.add(n)

    expected_sequence = list(range(1, len(seen) + 1))
    if sorted(seen) != expected_sequence:
        problems.append(
            f"{RUBRIC_MD}: dimension headings are numbered {sorted(seen)}, expected a contiguous "
            f"sequence starting at 1 with no gap ({expected_sequence})"
        )
    if numbers != sorted(numbers):
        problems.append(f"{RUBRIC_MD}: dimension headings are numbered {numbers} in document order, expected ascending")

    for index, match in enumerate(matches):
        start = match.end()
        # The next heading at this level or shallower (## or #), not just the
        # next NUMBERED dimension heading -- an intervening non-dimension
        # `##` section (e.g. a stray subsection) would otherwise be read as
        # this dimension's own body, masking a genuinely empty section.
        next_heading = _NEXT_LEVEL_1_OR_2_HEADING_RE.search(rubric_text, start)
        end = next_heading.start() if next_heading else len(rubric_text)
        if not rubric_text[start:end].strip():
            problems.append(f"{RUBRIC_MD}: dimension heading '## {numbers[index]}.' has an empty section")

    return len(numbers), problems


def check_dimension_count(skill_text: str, rubric_text: str, heading_count: int) -> list[str]:
    """Every bold dimension-count declaration, in either file, against the
    real heading count -- every occurrence, not only the first.

    A second declaration sentence added later in a file, restating the
    count, must not silently escape the lock -- grading only the first match
    would leave exactly the exposure `check_other_axes_counts` in the
    precedent this mirrors exists to close.

    SKILL.md must carry at least one declaration -- it is the primary,
    load-bearing site (mirrors the precedent's own SKILL.md-only axis-count
    declaration requirement); rubric.md's own declaration is an additional,
    optional site: validated if present, not required.
    """
    problems: list[str] = []
    skill_matches = _DIMENSION_COUNT_RE.findall(skill_text)
    if not skill_matches:
        problems.append(
            f"{SKILL_MD}: no '**<number> dimensions**' / '**<number>-dimension**' declaration found -- "
            f"the dimension-count lock cannot run, and {heading_count} '## N. <Name>' heading(s) are present"
        )
    for label, matches in ((SKILL_MD, skill_matches), (RUBRIC_MD, _DIMENSION_COUNT_RE.findall(rubric_text))):
        problems.extend(
            check_number_word_matches(
                matches,
                heading_count,
                partial(_format_unrecognized_dimension_count, label),
                partial(_format_dimension_count_mismatch, label, heading_count),
            )
        )
    return problems


def _format_unrecognized_dimension_count(label: str, word: str) -> str:
    return f"{label}: dimension count declared as {word!r}, which is not a recognized number word"


def _format_dimension_count_mismatch(label: str, heading_count: int, _word: str, declared: int) -> str:
    return (
        f"{label}: declares {declared} dimensions but {RUBRIC_MD} carries {heading_count} "
        "'## N. <Name>' heading(s) -- update the count in the same change as the heading"
    )


def check_range_references(skill_text: str, rubric_text: str, heading_count: int) -> list[str]:
    """Every literal 'dimensions 1-N' full-span citation, in either file,
    against the real heading count. Absent is silence, not a finding --
    these are optional cross-references, not a required declaration."""
    problems: list[str] = []
    for label, text in ((SKILL_MD, skill_text), (RUBRIC_MD, rubric_text)):
        for end in _RANGE_RE.findall(text):
            if int(end) != heading_count:
                problems.append(
                    f"{label}: cites 'dimensions 1-{end}' but {heading_count} dimension heading(s) exist -- "
                    "update every such range in the same change as the heading"
                )
    return problems


def check_mechanism_fit_labels(skill_text: str) -> list[str]:
    """The nine bold Agentic operation mechanism-fit step labels against the real section
    content -- each is a step-level check named in SKILL.md's own Two
    lanes/Agentic operation mechanism-fit prose, not a rubric.md heading."""
    section = extract_section(skill_text, MECHANISM_FIT_HEADING, SKILL_MD)
    return [
        f"{SKILL_MD}: lost Agentic operation mechanism-fit step label -- expected literal text {f'**{label}**'!r} "
        "in the Agentic operation mechanism-fit section"
        for label in MECHANISM_FIT_STEP_LABELS
        if f"**{label}**" not in section
    ]


def scan(skill_dir: Path) -> list[str]:
    """Every drift message for ``skill_dir``; empty means every lock holds."""
    skill_text = read_text(skill_dir / SKILL_MD)
    rubric_text = read_text(skill_dir / RUBRIC_MD)

    heading_count, heading_problems = check_dimension_headings(rubric_text)

    problems: list[str] = []
    problems += heading_problems
    problems += check_dimension_count(skill_text, rubric_text, heading_count)
    problems += check_range_references(skill_text, rubric_text, heading_count)
    problems += check_mechanism_fit_labels(skill_text)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=DEFAULT_SKILL_DIR,
        help="evaluating-skill-quality skill directory (default: this repository's own).",
    )
    args = parser.parse_args(argv)

    try:
        problems = scan(args.skill_dir)
    except ScanError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        print("Skill-quality rubric vocabulary lock could not run -- failing closed.", file=sys.stderr)
        return 2

    if problems:
        for problem in problems:
            print(f"::error::{problem}", file=sys.stderr)
        print(
            f"FAIL: {len(problems)} skill-quality rubric vocabulary lock(s) drifted in {args.skill_dir}.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: skill-quality rubric vocabulary locks hold in {args.skill_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

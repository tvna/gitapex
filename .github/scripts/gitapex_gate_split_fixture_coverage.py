#!/usr/bin/env python3
"""CI gate: split.md fixture-table coverage checks.

Issue #526 unifies two gate proposals drawn from two retrospective issues
("Requested outcome: one check catches both gap classes.") into this one
script.

Check A (issue #191, repair 1). A `split.md`'s gate-result table (a
`| Fixture | Before | After |` Markdown table recording a live before/edit
scored run) is supposed to cover every fixture the file's own `##
Assignment` section declares for the `selection` split. PR #190 shipped a
gate table that silently omitted a declared fixture (`heldout-vague-
completion.yaml`) -- the reported gate covered 9 of the declared 10, and
the missing fixture was never actually scored, caught only by external
review (`chatgpt-codex-connector[bot]`), not by anything mechanical. This
check parses the *most recent* (last, by file position) gate-result table
in a `split.md` file and requires its Fixture column to be a superset of
that file's declared `selection` list -- unless the table is explicitly
scoped to a single named fixture, this repository's own established
convention for a narrower recheck ("one fresh dispatch per side against
`<fixture>.yaml`", used repeatedly by
`evals/evaluating-skill-quality/split.md`'s `gitapex#537` follow-up
entries), which by construction never claims full-corpus coverage and is
exempt from the superset rule.

Check B (issue #352, repair 3). A `SKILL.md` documenting a
precedence/branching rule (an "X takes precedence/priority over Y"
sentence) needs a train+held-out equivalence-class fixture pair in its own
`split.md`, per `scorer-gated-skill-edits`' own precondition gate ("every
actual trigger branch" needs both a positive and a negative/non-trigger
fixture). PR #328 shipped `skills/merge-retrospective/SKILL.md`'s Step 4
precedence rule with zero fixture coverage in
`evals/merge-retrospective/split.md` until external review caught it
(closed by class 9: `title-convention-precedence-train.yaml` /
`no-title-convention-fallback-selection.yaml`). This check parses a
`SKILL.md` for that phrasing and, when the skill already has a
corresponding `evals/<skill>/split.md` (a skill with no `split.md` at all
is out of scope for this check -- that gap belongs to
`scorer-gated-skill-edits`' own precondition gate, not this one), requires
that `split.md`'s `## Equivalence classes` table to have a row that both
mentions "precedence"/"priority" and names two fixtures (a train one and a
held-out one).

Check C (issue #631, following issue #629's blocker 2 finding). A proposed
mechanical "out-of-scope" classifier for `scorer-gated-skill-edits`' gate
(issue #629, "Spec B") found that a fixture-side `exercises:` declaration
-- which section(s) of a skill's `SKILL.md` a fixture's prompt is designed
to exercise -- would silently read a missing/empty declaration as "declares
no sections," making an out-of-scope verdict vacuously true for every
future edit. This check closes that half of the gap on its own (the
classifier itself is explicitly NOT built here -- see issue #631): for
every fixture a `split.md`'s `## Assignment` section declares for the
`selection` split, when the sibling `SKILL.md` has at least one `###`-level
section heading (this repository's convention for a routing-style
sub-heading, e.g. `### Commit log -> a terse Why, not the full Why`,
established by `skills/explaining-the-work/SKILL.md`), that fixture's own
YAML must declare a well-formed `expected.exercises` (a non-empty list of
section labels -- not merely truthy, mirroring
`gitapex_lint_fixture_assertions.py`'s `_is_real_dispatch_declaration` shape-
validation pattern), and every declared label must casefold-match a real
current section label (the heading text before ` -> `, when present) in
that `SKILL.md` -- never resolved by staleness (a fixture whose exercises:
label no longer matches any heading fails loudly, the same declare+verify
precedent as Check A/B above, not a stale pointer left unnoticed).
Scoped automatically to skills that both have a `split.md` and use this
`###` sub-heading convention -- not an enumerated allowlist like issue
#584's `DISPATCH_MANDATE_SKILLS`, since the two skills in this repository
that use `###` headings for an unrelated purpose (`evaluating-deterministic-
gate-quality`'s evaluation axes, `scanning-attack-surfaces`'s check
categories) have no `split.md` at all today, so this check never reaches
them; a future skill combining both conventions in an unrelated way would
need this scoping revisited, the same class of residual heuristic-scope
risk Check B's own docstring already discloses for its narrower text scan.

All three checks are heuristic text parsing over Markdown prose, not a
formal grammar -- the issue's own Acceptance Criteria Map names this
residual risk explicitly ("Parsing split.md's prose-based Assignment
section and gate tables reliably needs a defined, stable format
convention" / "Detecting... phrases in free-form SKILL.md prose needs a
heuristic that could miss some phrasings or over-trigger on unrelated
conditional language"). Scope is deliberately narrowed to the exact
conventions this repository's own `split.md` files already use, verified
directly against all of them (`evals/evaluating-skill-quality/split.md`,
`evals/scorer-gated-skill-edits/split.md`,
`evals/battle-testing-a-skill/split.md`,
`evals/merge-retrospective/split.md`,
`evals/explaining-the-work/split.md`) before writing this gate (Check C)
-- not a general-purpose Markdown parser.

Mirrors `gitapex_gate_retro_title_convention_citation.py`'s shape: the calling
workflow computes which `split.md`/`SKILL.md` files this PR actually added
or modified (pre-existing, already-shipped content is out of scope for a
gate whose job is to catch a gap before it ships), this script only grades
those files.

Usage::

    python3 .github/scripts/gitapex_gate_split_fixture_coverage.py \\
        --split-md FILE [FILE ...] --skill-md FILE [FILE ...]

Either flag may be omitted (or given zero files) if this PR did not touch
that file type. Each `--skill-md` file is matched to a sibling `split.md`
by this repository's own established convention,
`skills/<slug>/SKILL.md` <-> `evals/<slug>/split.md`, resolved under
`--repo-root` (default: current directory).

Exit codes:
    0  No offending file.
    1  At least one offending file, or a required file could not be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TypeGuard

import yaml

_YAML_NAME_RE = re.compile(r"`([A-Za-z0-9._-]+\.yaml)`")

_ASSIGNMENT_HEADING_RE = re.compile(r"^##\s+Assignment\s*$", re.MULTILINE)
_EQUIVALENCE_CLASSES_HEADING_RE = re.compile(r"^##\s+Equivalence classes\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)

# "- **train** (...): `a.yaml`, `b.yaml`." style bullets -- the one
# fixture-assignment convention all four of this repository's split.md
# files share (verified directly against all four before writing this
# regex), even though the surrounding prose differs.
_SPLIT_BULLET_RE = re.compile(
    r"-\s+\*\*(train|selection|test)\*\*(.*?)(?=\n-\s+\*\*(?:train|selection|test)\*\*|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# A gate-result table header: three columns literally named Fixture,
# Before, After, in that order, with any column widths/alignment.
_GATE_TABLE_HEADER_RE = re.compile(
    r"^\|[^\n]*\bFixture\b[^\n]*\|[^\n]*\bBefore\b[^\n]*\|[^\n]*\bAfter\b[^\n]*\|\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# This repository's own established phrasing for a table intentionally
# scoped to one fixture, e.g. "one fresh dispatch per side against only
# `confidentiality-awareness-payment-data-selection.yaml`:".
_SCOPED_TABLE_RE = re.compile(r"against\s+(?:only\s+)?`([A-Za-z0-9._-]+\.yaml)`", re.IGNORECASE)

# The concrete phrasing named by issue #352 ("template and title take
# precedence over this skill's own defaults"), generalized to the
# "priority" synonym. Deliberately narrow (verified against every SKILL.md
# in this repository before writing this regex: exactly one hit,
# skills/merge-retrospective/SKILL.md) to avoid over-triggering on
# unrelated conditional language.
_PRECEDENCE_RE = re.compile(r"\btakes?\s+(?:precedence|priority)\s+over\b", re.IGNORECASE)

# A `###`-level heading, this repository's routing-style sub-heading
# convention (issue #631), e.g. `### Commit log -> a terse Why, not the
# full Why`.
_SECTION_HEADING_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def _section(text: str, heading_re: re.Pattern[str]) -> str:
    """Text from `heading_re`'s heading (exclusive) to the next `##`
    heading, or end of file. Empty string if the heading is absent."""
    match = heading_re.search(text)
    if not match:
        return ""
    rest = text[match.end() :]
    next_heading = _NEXT_HEADING_RE.search(rest)
    return rest[: next_heading.start()] if next_heading else rest


def parse_assignment_fixtures(text: str) -> dict[str, list[str]]:
    """Return `{"train": [...], "selection": [...], "test": [...]}` parsed
    from a `split.md` file's `## Assignment` section."""
    section = _section(text, _ASSIGNMENT_HEADING_RE)
    result: dict[str, list[str]] = {"train": [], "selection": [], "test": []}
    for match in _SPLIT_BULLET_RE.finditer(section):
        result[match.group(1).lower()] = _YAML_NAME_RE.findall(match.group(2))
    return result


def find_gate_tables(text: str) -> list[tuple[int, list[str]]]:
    """Every `| Fixture | Before | After |`-shaped table in `text`, as
    `(header_start_offset, fixtures_in_row_order)`, in file order."""
    tables: list[tuple[int, list[str]]] = []
    for header_match in _GATE_TABLE_HEADER_RE.finditer(text):
        # `$` in MULTILINE mode matches before the newline without
        # consuming it, so `header_match.end()` still points at the
        # header's own trailing "\n" -- skip past it explicitly, or
        # splitlines() below sees a spurious leading blank line and the
        # separator-row / data-row indices are all off by one.
        newline_index = text.find("\n", header_match.end())
        body_start = newline_index + 1 if newline_index != -1 else len(text)
        lines = text[body_start:].splitlines(keepends=True)
        idx = 0
        if idx < len(lines) and _TABLE_SEPARATOR_RE.match(lines[idx]):
            idx += 1
        fixtures: list[str] = []
        while idx < len(lines) and lines[idx].lstrip().startswith("|"):
            cell_match = _YAML_NAME_RE.search(lines[idx])
            if cell_match:
                fixtures.append(cell_match.group(1))
            idx += 1
        tables.append((header_match.start(), fixtures))
    return tables


def _preceding_paragraph(text: str, pos: int) -> str:
    """The blank-line-delimited paragraph immediately before `pos`."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text[:pos]) if p.strip()]
    return paragraphs[-1] if paragraphs else ""


def is_single_fixture_scoped(paragraph: str, table_fixtures: list[str]) -> bool:
    """True iff `paragraph` (the text immediately introducing a gate table)
    names exactly one fixture via the "against [only] `<fixture>.yaml`"
    convention, and the table itself covers only that same fixture -- i.e.
    the table never claimed full-corpus coverage in the first place."""
    match = _SCOPED_TABLE_RE.search(paragraph)
    if match is None:
        return False
    return set(table_fixtures) == {match.group(1)}


def check_latest_gate_table_coverage(path: Path, text: str) -> str | None:
    """Return an offender message if `path`'s most recent gate-result table
    omits a fixture declared in its own `selection` split, else None."""
    tables = find_gate_tables(text)
    if not tables:
        return None
    header_start, fixtures = tables[-1]
    paragraph = _preceding_paragraph(text, header_start)
    if is_single_fixture_scoped(paragraph, fixtures):
        return None
    declared_selection = parse_assignment_fixtures(text)["selection"]
    missing = [f for f in declared_selection if f not in fixtures]
    if not missing:
        return None
    return (
        f"{path}: most recent gate-result table covers {len(fixtures)} fixture(s) "
        f"but the declared 'selection' split has {len(declared_selection)}; "
        f"missing from the table: {', '.join(missing)}"
    )


def find_precedence_phrases(text: str) -> list[str]:
    """Every precedence/branching phrase match in `text` (a SKILL.md),
    in file order."""
    return [m.group(0) for m in _PRECEDENCE_RE.finditer(text)]


def has_precedence_equivalence_class_pair(split_text: str) -> bool:
    """True iff `split_text`'s `## Equivalence classes` table has a row
    mentioning precedence/priority with two named fixtures (a train one
    and a held-out one)."""
    section = _section(split_text, _EQUIVALENCE_CLASSES_HEADING_RE)
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        lowered = stripped.lower()
        if "precedence" not in lowered and "priority" not in lowered:
            continue
        if len(_YAML_NAME_RE.findall(stripped)) >= 2:
            return True
    return False


def check_precedence_branch_coverage(skill_md_path: Path, skill_text: str, repo_root: Path) -> str | None:
    """Return an offender message if `skill_md_path` documents a
    precedence/branching rule with no matching train+held-out equivalence
    class in its skill's own `split.md`, else None. A skill with no
    `split.md` at all is out of scope -- see module docstring, Check B."""
    phrases = find_precedence_phrases(skill_text)
    if not phrases:
        return None
    split_md_path = repo_root / "evals" / skill_md_path.parent.name / "split.md"
    if not split_md_path.is_file():
        return None
    try:
        split_text = split_md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return f"{split_md_path}: could not decode as UTF-8 ({error})"
    if has_precedence_equivalence_class_pair(split_text):
        return None
    return (
        f"{skill_md_path}: documents a precedence/branching rule ({phrases[0]!r}) "
        f"with no matching train+held-out equivalence-class pair in {split_md_path}"
    )


_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def _strip_fenced_code_blocks(text: str) -> str:
    """Blank out every line inside a fenced code block (``` or ~~~), so a
    `###`-prefixed line inside a fence illustrating Markdown syntax is
    never mistaken for a real heading (adversarial review, issue #631) --
    mirrors `gitapex_check_skill_shape.py`'s own `_strip_illustrative_spans`
    fence-toggle logic. Line count is preserved (blanked, not removed) so
    this stays a drop-in substitute for callers that care about offsets;
    `parse_section_labels` below does not, but keeping the shape consistent
    with that established precedent costs nothing."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def parse_section_labels(skill_text: str) -> set[str]:
    """Every `###`-level section's canonical label, casefolded, from a
    SKILL.md's routing-style sub-headings (issue #631). The label is the
    heading text before ` -> ` when present (e.g. `### Commit log -> a
    terse Why, not the full Why` -> `commit log`), else the whole heading
    text casefolded. Fenced code blocks are stripped first, so a
    `###`-prefixed line only illustrating Markdown syntax inside a fence
    is never counted as a real section."""
    labels: set[str] = set()
    for match in _SECTION_HEADING_RE.finditer(_strip_fenced_code_blocks(skill_text)):
        heading = match.group(1).strip()
        label = heading.split(" -> ", 1)[0].strip()
        labels.add(label.casefold())
    return labels


def _is_real_exercises_declaration(value: object) -> TypeGuard[list[str]]:
    """True iff `value` (a fixture's `expected.exercises`) is a non-empty
    list of non-blank strings -- not merely truthy (issue #631, mirroring
    `gitapex_lint_fixture_assertions.py`'s `_is_real_dispatch_declaration`, which
    closed the identical bare-truthy-declaration gap for issue #584)."""
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) and item.strip() for item in value)


def check_exercises_declaration_coverage(split_md_path: Path, split_text: str, repo_root: Path) -> str | None:
    """Return an offender message if any fixture `split_md_path`'s
    `selection` split declares either lacks a well-formed
    `expected.exercises` declaration, or names a section label matching no
    real `###`-level section in the sibling SKILL.md, else None (issue
    #631, closing issue #629's blocker 2: a missing/bare-truthy
    declaration must fail loudly, never be silently read as "declares no
    sections"). Out of scope (returns None) when the sibling SKILL.md
    either does not exist or has no `###`-level section at all -- see the
    module docstring for why this is a structural scope gate, not an
    enumerated allowlist.
    """
    declared_selection = parse_assignment_fixtures(split_text)["selection"]
    if not declared_selection:
        return None
    skill_name = split_md_path.parent.name
    skill_md_path = repo_root / "skills" / skill_name / "SKILL.md"
    if not skill_md_path.is_file():
        return None
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return f"{split_md_path}: could not decode sibling {skill_md_path} as UTF-8 ({error})"
    section_labels = parse_section_labels(skill_text)
    if not section_labels:
        return None

    tasks_dir = repo_root / "evals" / skill_name / "tasks"
    problems: list[str] = []
    for fixture_name in declared_selection:
        fixture_path = tasks_dir / fixture_name
        if not fixture_path.is_file():
            problems.append(f"{fixture_name}: file not found under {tasks_dir}")
            continue
        try:
            data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            problems.append(f"{fixture_name}: could not parse YAML ({error})")
            continue
        expected = data.get("expected") if isinstance(data, dict) else None
        exercises = expected.get("exercises") if isinstance(expected, dict) else None
        if not _is_real_exercises_declaration(exercises):
            problems.append(
                f"{fixture_name}: no well-formed expected.exercises declaration (a non-empty list of section labels)"
            )
            continue
        unmatched = [label for label in exercises if label.casefold() not in section_labels]
        if unmatched:
            problems.append(
                f"{fixture_name}: exercises {unmatched!r} match no real ###-level section in {skill_md_path}"
            )
    if not problems:
        return None
    return f"{split_md_path}: selection-split fixture(s) with an exercises-declaration gap -- {'; '.join(problems)}"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"error: could not read {path}: {error}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split-md", nargs="*", default=[], help="split.md files this PR added or modified.")
    parser.add_argument("--skill-md", nargs="*", default=[], help="SKILL.md files this PR added or modified.")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root, for resolving a skill's split.md/SKILL.md/tasks."
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    offenders: list[str] = []
    # Check C (issue #631) is keyed by split.md path, but must fire whether
    # the *split.md* or its *sibling SKILL.md* is the one that changed --
    # a SKILL.md-only diff (e.g. renaming a ###-level section, with no
    # split.md edit in the same PR) is exactly the staleness scenario this
    # check exists to catch, and the calling workflow populates --split-md/
    # --skill-md independently from whichever file type actually changed
    # (see .github/workflows/split-fixture-coverage-gate.yml), so relying
    # on --split-md alone would silently skip it. Tracked so a PR touching
    # both sides of the same pair is not checked (and reported) twice.
    exercises_checked: set[Path] = set()

    for raw_path in args.split_md:
        path = Path(raw_path)
        text = _read(path)
        if text is None:
            return 1
        offender = check_latest_gate_table_coverage(path, text)
        if offender:
            offenders.append(offender)
        exercises_checked.add(path)
        offender = check_exercises_declaration_coverage(path, text, repo_root)
        if offender:
            offenders.append(offender)

    for raw_path in args.skill_md:
        path = Path(raw_path)
        text = _read(path)
        if text is None:
            return 1
        offender = check_precedence_branch_coverage(path, text, repo_root)
        if offender:
            offenders.append(offender)
        sibling_split_md = repo_root / "evals" / path.parent.name / "split.md"
        if sibling_split_md.is_file() and sibling_split_md not in exercises_checked:
            exercises_checked.add(sibling_split_md)
            sibling_text = _read(sibling_split_md)
            if sibling_text is None:
                return 1
            offender = check_exercises_declaration_coverage(sibling_split_md, sibling_text, repo_root)
            if offender:
                offenders.append(offender)

    if not offenders:
        print("PASS: split.md fixture-table coverage checks satisfied")
        return 0
    print("FAIL: split.md fixture-table coverage gap(s) found:", file=sys.stderr)
    for offender in offenders:
        print(f"  - {offender}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CI gate: split.md/split.json fixture coverage checks.

Issue #526 unifies two gate proposals drawn from two retrospective issues
("Requested outcome: one check catches both gap classes.") into this one
script. Issue #928 rewrites Checks A, B, and D to read the structured
`evals/<skill>/split.json` (added by that issue's own migration, validated
against `skills/scorer-gated-skill-edits/references/split.schema.json`)
instead of regex-parsing `split.md`'s prose `## Assignment` / `##
Equivalence classes` sections, which the migration removed. Check C already
compared a fixture's own YAML declaration against `SKILL.md`'s `###`
headings -- a cross-file fact no schema alone can express -- and stays
cross-file, now reading its declared-`selection` fixture list from
`split.json` instead of markdown bullets.

Check A (issue #191, repair 1). A `split.md`'s gate-result table (a
`| Fixture | Before | After |` Markdown table recording a live before/edit
scored run) is supposed to cover every fixture `split.json`'s own
`assignment.selection` array declares. PR #190 shipped a gate table that
silently omitted a declared fixture (`heldout-vague-completion.yaml`) --
the reported gate covered 9 of the declared 10, and the missing fixture
was never actually scored, caught only by external review
(`chatgpt-codex-connector[bot]`), not by anything mechanical. This check
parses the *most recent* (last, by file position) gate-result table in a
`split.md` file and requires its Fixture column to be a superset of that
skill's declared `selection` list -- unless the table is explicitly scoped
to a single named fixture, this repository's own established convention
for a narrower recheck ("one fresh dispatch per side against
`<fixture>.yaml`", used repeatedly by
`evals/evaluating-skill-quality/split.md`'s follow-up entries), which by
construction never claims full-corpus coverage and is exempt from the
superset rule. The gate-result table itself remains narrative Markdown in
`split.md` -- only the declared-`selection` list it is graded against now
comes from `split.json`.

Check B (issue #352, repair 3). A `SKILL.md` documenting a
precedence/branching rule (an "X takes precedence/priority over Y"
sentence) needs a train+held-out equivalence-class fixture pair declared
in its own skill's `split.json`, per `scorer-gated-skill-edits`' own
precondition gate ("every actual trigger branch" needs both a positive and
a negative/non-trigger fixture). PR #328 shipped
`skills/merge-retrospective/SKILL.md`'s Step 4 precedence rule with zero
fixture coverage until external review caught it (closed by class 9:
`title-convention-precedence-train.yaml` /
`no-title-convention-fallback-selection.yaml`). This check parses a
`SKILL.md` for that phrasing and, when the skill already has a
corresponding `evals/<skill>/split.json` (a skill with no `split.json` at
all is out of scope for this check -- that gap belongs to
`scorer-gated-skill-edits`' own precondition gate, not this one), requires
that file's own `equivalence_classes` array to have at least one
well-formed `{train_fixture, held_out_fixture}` pair. `split.schema.json`'s
`equivalenceClass` shape deliberately carries no per-pair topic label (see
its own docstring: that narrative -- which pair covers *which*
precedence/branching rule -- is "not data split.json's schema can hold"),
so unlike the markdown table this replaces, this check can no longer
confirm the specific pair it finds is *about* the precedence rule the
phrase names, only that some train/held-out pairing exists at all for the
skill. This is a disclosed narrowing versus the markdown-era check (which
required the table row itself to mention "precedence"/"priority"), not an
oversight: the finer label lives in `split.md`'s own narrative prose now,
which is not machine-checked.

Check C (issue #631, following issue #629's blocker 2 finding). A proposed
mechanical "out-of-scope" classifier for `scorer-gated-skill-edits`' gate
(issue #629, "Spec B") found that a fixture-side `exercises:` declaration
-- which section(s) of a skill's `SKILL.md` a fixture's prompt is designed
to exercise -- would silently read a missing/empty declaration as "declares
no sections," making an out-of-scope verdict vacuously true for every
future edit. This check closes that half of the gap on its own (the
classifier itself is explicitly NOT built here -- see issue #631): for
every fixture `split.json`'s own `assignment.selection` array declares,
when the sibling `SKILL.md` has at least one `###`-level section heading
(this repository's convention for a routing-style sub-heading, e.g.
`### Commit log -> a terse Why, not the full Why`, established by
`skills/explaining-the-work/SKILL.md`), that fixture must declare a
well-formed `exercises` list (a non-empty list of section labels -- not
merely truthy, mirroring `gitapex_lint_fixture_assertions.py`'s
`_is_real_dispatch_declaration` shape-validation pattern), either inline in
`split.json` itself (the `fixtureWithExpected` shape `split.schema.json`
defines for exactly this purpose) or in the fixture's own task YAML's
`expected.exercises` field (this repository's pre-existing convention,
still how every real fixture today declares it) -- and every declared
label must casefold-match a real current section label (the heading text
before ` -> `, when present) in that `SKILL.md`, never resolved by
staleness (a fixture whose `exercises:` label no longer matches any
heading fails loudly, the same declare+verify precedent as Check A/B
above, not a stale pointer left unnoticed). Scoped automatically to skills
that both have a `split.json` and use this `###` sub-heading convention --
not an enumerated allowlist like issue #584's `DISPATCH_MANDATE_SKILLS`,
since the two skills in this repository that use `###` headings for an
unrelated purpose (`evaluating-deterministic-gate-quality`'s evaluation
axes, `scanning-attack-surfaces`'s check categories) have no `split.json`
at all today, so this check never reaches them; a future skill combining
both conventions in an unrelated way would need this scoping revisited,
the same class of residual heuristic-scope risk Check B's own docstring
already discloses for its narrower text scan.

Check D (issue #907). A `split.json` that declares a `partition` field
(a `"train:selection:test"` string, e.g. `"9:6:3"`) is asserting an
arithmetic contract against its own `assignment` listing, and this check
verifies it: it requires a file that declares a partition to also carry a
`split_arithmetic_exclusions` array (per-schema, required together with
`partition` -- an explicit empty array is a real "nothing is excluded"
statement, distinct from the key being absent), then asserts, per split,
that the unique listed fixture count minus that split's declared
exclusions equals the declared figure. A named exclusion that is not
actually listed in any split's own array is itself an offence, so the
field cannot rot into a silent blanket waiver, and the same fixture
appearing in more than one split is rejected outright (this repository's
splits are disjoint by construction) rather than silently double-counted
or resolved by picking one. Moving this data into JSON removes an entire
class of prose-parsing ambiguity the markdown-era version of this check
had to defend against by construction (two disagreeing partition
declarations, a declaration hiding inside a fenced illustration, a
duplicated `## Assignment` heading, a trailing paragraph inflating a
split's count): a JSON object has exactly one value per key, so those
specific failure shapes cannot recur here. `gitapex_scan_split_schema.py`
(issue #928, T11) is the dedicated schema-shape gate; this check still
defends its own arithmetic defensively against a `partition` or
`split_arithmetic_exclusions` value that does not match the schema's own
shape, in case that gate has not (yet) run over the same file, rather than
assuming upstream validation always precedes this one.

Mirrors `gitapex_gate_retro_title_convention_citation.py`'s shape: the calling
workflow computes which `split.md`/`SKILL.md` files this PR actually added
or modified (pre-existing, already-shipped content is out of scope for a
gate whose job is to catch a gap before it ships), this script only grades
those files (and, for Checks A/B/C/D, each file's sibling `split.json`,
resolved by this repository's own `evals/<skill>/split.json` <->
`evals/<skill>/split.md` <-> `skills/<skill>/SKILL.md` naming convention).

Usage::

    python3 .github/scripts/gitapex_gate_split_fixture_coverage.py \\
        --split-md FILE [FILE ...] --skill-md FILE [FILE ...]

Either flag may be omitted (or given zero files) if this PR did not touch
that file type. Each `--split-md`/`--skill-md` file is matched to its
skill's `split.json` by this repository's own established convention,
`evals/<slug>/split.json`, resolved under `--repo-root` (default: current
directory).

Exit codes:
    0  No offending file.
    1  At least one offending file, or a required file could not be read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TypeGuard

import yaml

_YAML_NAME_RE = re.compile(r"`([A-Za-z0-9._-]+\.yaml)`")

# A gate-result table header: three columns literally named Fixture,
# Before, After, in that order, with any column widths/alignment/extra
# columns between them.
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
# in this repository before writing this regex) to avoid over-triggering
# on unrelated conditional language.
_PRECEDENCE_RE = re.compile(r"\btakes?\s+(?:precedence|priority)\s+over\b", re.IGNORECASE)

# A `###`-level heading, this repository's routing-style sub-heading
# convention (issue #631), e.g. `### Commit log -> a terse Why, not the
# full Why`.
_SECTION_HEADING_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$", re.MULTILINE)

# split.json's own `partition` field shape (split.schema.json's own
# pattern): three non-negative integers, colon-separated, nothing else.
_PARTITION_RE = re.compile(r"^(\d+):(\d+):(\d+)$")

_SPLIT_NAMES = ("train", "selection", "test")


# ---------------------------------------------------------------------------
# split.json loading and shape helpers
# ---------------------------------------------------------------------------


def load_split_json(path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Parse `path` (a skill's `split.json`) into its top-level object.

    Returns `(data, None)` on success, or `(None, <reason>)` when the file
    is missing, unreadable, undecodable, not valid JSON, or not a JSON
    object -- every caller below reads `split.json` through this one
    function, so a malformed file is reported the same way regardless of
    which check found it first.
    """
    if not path.is_file():
        return None, f"{path}: not found"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return None, f"{path}: could not read ({error})"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return None, f"{path}: could not parse as JSON ({error})"
    if not isinstance(data, dict):
        return None, f"{path}: top-level JSON value must be an object"
    return data, None


def _fixture_entry_name(item: object) -> str | None:
    """The bare fixture filename from one `assignment.<split>` array entry
    -- either a plain filename string, or a `{fixture, expected}` object
    (`split.schema.json`'s `fixtureItem` `oneOf`). `None` if `item`
    matches neither shape (schema-shape enforcement is
    `gitapex_scan_split_schema.py`'s own job, not this gate's)."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        fixture = item.get("fixture")
        if isinstance(fixture, str):
            return fixture
    return None


def assignment_fixtures(data: dict[str, object]) -> dict[str, list[str]]:
    """`{"train": [...], "selection": [...], "test": [...]}` bare fixture
    filenames from `split.json`'s own `assignment` object. A split key
    that is absent, or an entry matching neither `fixtureItem` shape,
    contributes nothing to that split's list."""
    result: dict[str, list[str]] = {name: [] for name in _SPLIT_NAMES}
    assignment = data.get("assignment")
    if not isinstance(assignment, dict):
        return result
    for split_name in _SPLIT_NAMES:
        items = assignment.get(split_name)
        if not isinstance(items, list):
            continue
        result[split_name] = [name for item in items if (name := _fixture_entry_name(item)) is not None]
    return result


# ---------------------------------------------------------------------------
# Check A (issue #191): gate-result table coverage
# ---------------------------------------------------------------------------


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


def check_latest_gate_table_coverage(
    path: Path, text: str, declared_selection: list[str], assignment_present: bool
) -> str | None:
    """Return an offender message if `path`'s (a `split.md`) most recent
    gate-result table omits a fixture `declared_selection` (that skill's
    own `split.json` `assignment.selection` list) names, else None.

    `assignment_present` must be False when the sibling `split.json`'s own
    `assignment` field is absent or not an object -- otherwise
    `declared_selection` collapses to `[]` and an empty `missing` list
    reads as "the table covers everything declared," passing vacuously no
    matter how incomplete the real gate table is (the same fail-open
    pattern this check's own docstring names PR #190 for, this time
    triggered by a malformed `split.json` rather than a short table).
    Schema-shape enforcement is `gitapex_scan_split_schema.py`'s own job,
    T11; this check still defends its own arithmetic against a malformed
    value rather than assuming that gate always ran first, matching
    `check_partition_arithmetic`'s identical defense below."""
    if not assignment_present:
        return f"{path}: sibling split.json has no well-formed 'assignment' object -- cannot verify the gate-result table's fixture coverage"
    tables = find_gate_tables(text)
    if not tables:
        return None
    header_start, fixtures = tables[-1]
    paragraph = _preceding_paragraph(text, header_start)
    if is_single_fixture_scoped(paragraph, fixtures):
        return None
    missing = [f for f in declared_selection if f not in fixtures]
    if not missing:
        return None
    return (
        f"{path}: most recent gate-result table covers {len(fixtures)} fixture(s) "
        f"but split.json's declared 'selection' split has {len(declared_selection)}; "
        f"missing from the table: {', '.join(missing)}"
    )


# ---------------------------------------------------------------------------
# Check B (issue #352): precedence/branching equivalence-class coverage
# ---------------------------------------------------------------------------


def find_precedence_phrases(text: str) -> list[str]:
    """Every precedence/branching phrase match in `text` (a SKILL.md),
    in file order."""
    return [m.group(0) for m in _PRECEDENCE_RE.finditer(text)]


def has_equivalence_class_pair(data: dict[str, object]) -> bool:
    """True iff `split.json`'s own `equivalence_classes` array has at
    least one well-formed `train_fixture`/`held_out_fixture` pair."""
    classes = data.get("equivalence_classes")
    if not isinstance(classes, list):
        return False
    return any(
        isinstance(entry, dict)
        and isinstance(entry.get("train_fixture"), str)
        and isinstance(entry.get("held_out_fixture"), str)
        for entry in classes
    )


def check_precedence_branch_coverage(skill_md_path: Path, skill_text: str, repo_root: Path) -> str | None:
    """Return an offender message if `skill_md_path` documents a
    precedence/branching rule with no equivalence-class pair declared in
    its skill's own `split.json`, else None. A skill with no `split.json`
    at all is out of scope -- see module docstring, Check B."""
    phrases = find_precedence_phrases(skill_text)
    if not phrases:
        return None
    split_json_path = repo_root / "evals" / skill_md_path.parent.name / "split.json"
    if not split_json_path.is_file():
        return None
    data, error = load_split_json(split_json_path)
    if error:
        return f"{skill_md_path}: {error}"
    assert data is not None  # noqa: S101 -- error is None, so load_split_json guarantees data
    if has_equivalence_class_pair(data):
        return None
    return (
        f"{skill_md_path}: documents a precedence/branching rule ({phrases[0]!r}) "
        f"with no equivalence-class pair declared in {split_json_path}"
    )


# ---------------------------------------------------------------------------
# Check C (issue #631): exercises-declaration coverage
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def _strip_fenced_code_blocks(text: str) -> str:
    """Blank out every line inside a fenced code block (``` or ~~~), so a
    `###`-prefixed line inside a fence illustrating Markdown syntax is
    never mistaken for a real heading (adversarial review, issue #631) --
    mirrors `gitapex_check_skill_shape.py`'s own `_strip_illustrative_spans`
    fence-toggle logic."""
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
    """True iff `value` (a fixture's `exercises` declaration) is a
    non-empty list of non-blank strings -- not merely truthy (issue #631,
    mirroring `gitapex_lint_fixture_assertions.py`'s
    `_is_real_dispatch_declaration`, which closed the identical
    bare-truthy-declaration gap for issue #584)."""
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) and item.strip() for item in value)


def check_exercises_declaration_coverage(split_json_path: Path, data: dict[str, object], repo_root: Path) -> str | None:
    """Return an offender message if any fixture `split_json_path`'s
    `assignment.selection` array declares either lacks a well-formed
    `exercises` declaration, or names a section label matching no real
    `###`-level section in the sibling SKILL.md, else None (issue #631,
    closing issue #629's blocker 2: a missing/bare-truthy declaration must
    fail loudly, never be silently read as "declares no sections"). Out of
    scope (returns None) when the sibling SKILL.md either does not exist
    or has no `###`-level section at all -- see the module docstring for
    why this is a structural scope gate, not an enumerated allowlist.

    Each selection fixture's `exercises` list is read from `split.json`
    itself when that fixture entry uses the `fixtureWithExpected` object
    form, else from the fixture's own task YAML's `expected.exercises`
    field (this repository's pre-existing, still-dominant convention).
    """
    assignment = data.get("assignment")
    selection_items = assignment.get("selection") if isinstance(assignment, dict) else None
    if not isinstance(selection_items, list) or not selection_items:
        return None
    skill_name = split_json_path.parent.name
    skill_md_path = repo_root / "skills" / skill_name / "SKILL.md"
    if not skill_md_path.is_file():
        return None
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return f"{split_json_path}: could not decode sibling {skill_md_path} as UTF-8 ({error})"
    section_labels = parse_section_labels(skill_text)
    if not section_labels:
        return None

    tasks_dir = repo_root / "evals" / skill_name / "tasks"
    problems: list[str] = []
    for item in selection_items:
        fixture_name = _fixture_entry_name(item)
        if fixture_name is None:
            problems.append(
                f"{item!r}: not a well-formed fixture entry (string filename or {{fixture, expected}} object)"
            )
            continue

        exercises: object = None
        if isinstance(item, dict):
            expected_inline = item.get("expected")
            if isinstance(expected_inline, dict):
                exercises = expected_inline.get("exercises")

        if exercises is None:
            fixture_path = tasks_dir / fixture_name
            if not fixture_path.is_file():
                problems.append(f"{fixture_name}: file not found under {tasks_dir}")
                continue
            try:
                fixture_data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
            except (yaml.YAMLError, UnicodeDecodeError) as error:
                problems.append(f"{fixture_name}: could not parse YAML ({error})")
                continue
            expected = fixture_data.get("expected") if isinstance(fixture_data, dict) else None
            exercises = expected.get("exercises") if isinstance(expected, dict) else None

        if not _is_real_exercises_declaration(exercises):
            problems.append(
                f"{fixture_name}: no well-formed exercises declaration (a non-empty list of section labels)"
            )
            continue
        unmatched = [label for label in exercises if label.casefold() not in section_labels]
        if unmatched:
            problems.append(
                f"{fixture_name}: exercises {unmatched!r} match no real ###-level section in {skill_md_path}"
            )
    if not problems:
        return None
    return f"{split_json_path}: selection-split fixture(s) with an exercises-declaration gap -- {'; '.join(problems)}"


# ---------------------------------------------------------------------------
# Check D (issue #907): declared partition arithmetic
# ---------------------------------------------------------------------------


def parse_declared_partition(data: dict[str, object]) -> tuple[int, int, int] | None:
    """The `train:selection:test` figures `split.json`'s own `partition`
    field declares, or `None` when the key is absent or malformed
    (schema-shape enforcement is `gitapex_scan_split_schema.py`'s own job,
    T11; this check still defends its own arithmetic against a malformed
    value rather than assuming that gate always ran first -- see
    `check_partition_arithmetic`)."""
    partition = data.get("partition")
    if not isinstance(partition, str):
        return None
    match = _PARTITION_RE.match(partition)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def check_partition_arithmetic(path: Path, data: dict[str, object]) -> str | None:
    """Check D (issue #907): a declared `partition` must reconcile with
    `split.json`'s own `assignment` listing, under its own declared
    `split_arithmetic_exclusions`.

    Counts *unique* names per split, since a fixture list could legitimately
    repeat an entry only by author error -- an entry appearing in more than
    one split is reported as its own offence rather than silently
    double-counted: this repository's splits are disjoint by construction,
    and a cross-split mention is otherwise unfixable -- excluding it to
    satisfy the referencing split breaks the split that legitimately owns
    it (the same reasoning the markdown-era version of this check applied).
    """
    if "partition" not in data:
        return None
    declared = parse_declared_partition(data)
    if declared is None:
        return f"{path}: 'partition' field {data.get('partition')!r} is not a well-formed \"N:N:N\" string"

    exclusions_raw = data.get("split_arithmetic_exclusions")
    if exclusions_raw is None:
        return (
            f"{path}: declares a {declared[0]}:{declared[1]}:{declared[2]} partition but carries no "
            "'split_arithmetic_exclusions' field -- add one (an empty array if nothing is excluded)"
        )
    if not isinstance(exclusions_raw, list) or not all(isinstance(item, str) for item in exclusions_raw):
        return f"{path}: 'split_arithmetic_exclusions' must be an array of fixture-filename strings"
    exclusions = set(exclusions_raw)

    listed = {name: set(values) for name, values in assignment_fixtures(data).items()}
    # A file that declares a partition but lists nothing must not pass
    # vacuously -- `0:0:0` against an absent listing otherwise reconciles
    # perfectly.
    if not set().union(*listed.values()):
        return (
            f"{path}: declares a {declared[0]}:{declared[1]}:{declared[2]} partition but 'assignment' "
            "lists no fixture at all; the arithmetic cannot be checked"
        )

    overlaps = sorted(
        f"{name} (in {' and '.join(s for s in _SPLIT_NAMES if name in listed[s])})"
        for name in set().union(*listed.values())
        if sum(name in listed[s] for s in _SPLIT_NAMES) > 1
    )
    if overlaps:
        return (
            f"{path}: 'assignment' lists the same fixture in more than one split: "
            f"{', '.join(overlaps)} -- each fixture belongs to exactly one split, and a "
            "cross-split mention cannot be reconciled by an exclusion"
        )

    stale = sorted(exclusions - set().union(*listed.values()))
    if stale:
        return (
            f"{path}: declares arithmetic exclusion(s) {', '.join(stale)} that 'assignment' does not "
            "list at all -- a stale exclusion silently widens the waiver"
        )

    for index, split_name in enumerate(_SPLIT_NAMES):
        counted = listed[split_name] - exclusions
        if len(counted) != declared[index]:
            excluded_here = sorted(listed[split_name] & exclusions)
            detail = f", excluding {', '.join(excluded_here)}" if excluded_here else ", with no exclusion here"
            return (
                f"{path}: declared {split_name} figure {declared[index]} does not match the "
                f"{len(counted)} unique {split_name} fixture(s) 'assignment' lists{detail}"
            )
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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
        "--repo-root", default=".", help="Repository root, for resolving a skill's split.json/SKILL.md/tasks."
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    offenders: list[str] = []
    # Check C (issue #631) is keyed by split.json path, but must fire
    # whether the *split.md* or its *sibling SKILL.md* is the one that
    # changed -- a SKILL.md-only diff (e.g. renaming a ###-level section,
    # with no split.md/split.json edit in the same PR) is exactly the
    # staleness scenario this check exists to catch, and the calling
    # workflow populates --split-md/--skill-md independently from whichever
    # file type actually changed (see
    # .github/workflows/split-fixture-coverage-gate.yml), so relying on
    # --split-md alone would silently skip it. Tracked so a PR touching
    # both sides of the same pair is not checked (and reported) twice.
    exercises_checked: set[Path] = set()

    for raw_path in args.split_md:
        path = Path(raw_path)
        text = _read(path)
        if text is None:
            return 1
        split_json_path = path.parent / "split.json"
        data, error = load_split_json(split_json_path)
        if error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        assert data is not None  # noqa: S101 -- error is falsy, so load_split_json guarantees data

        declared_selection = assignment_fixtures(data)["selection"]
        offender = check_latest_gate_table_coverage(
            path, text, declared_selection, assignment_present=isinstance(data.get("assignment"), dict)
        )
        if offender:
            offenders.append(offender)

        exercises_checked.add(split_json_path)
        offender = check_exercises_declaration_coverage(split_json_path, data, repo_root)
        if offender:
            offenders.append(offender)

        offender = check_partition_arithmetic(split_json_path, data)
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
        sibling_split_json = repo_root / "evals" / path.parent.name / "split.json"
        if sibling_split_json.is_file() and sibling_split_json not in exercises_checked:
            exercises_checked.add(sibling_split_json)
            sibling_data, sibling_error = load_split_json(sibling_split_json)
            if sibling_error or sibling_data is None:
                offenders.append(f"{sibling_split_json}: {sibling_error}")
            else:
                offender = check_exercises_declaration_coverage(sibling_split_json, sibling_data, repo_root)
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

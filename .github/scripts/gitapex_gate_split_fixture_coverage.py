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

Check E (issue #192 item 6, Refs #49 repair 1, #115 repair 1). Check C's own
`###`-heading declare-and-verify convention requires a `split.json` (both to
scope which skills are checked at all, and to know which fixtures are
"declared" via `assignment.selection`). Issue #115 originally proposed a
"key term" extraction from each numbered Procedure/Checks item, tested
against its own originating incident and found not to work (see the design
doc, `docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-
item-coverage-design.md`, Item 6). This check instead extends the SAME
declare-and-verify shape Check C already established to two more target
kinds, usable by an "ordinary" SKILL.md that needs no `split.json` at all: a
`Step N` ordinal (or a numbered item's own literal text) under a
`## Procedure`/`## Steps` heading, and a `## Stop boundaries`/
`## Stop boundary` bullet's own first-line text -- the latter using the
identical content-keyed `collections.Counter` identity
`gitapex_gate_skill_branch_fixture_coverage.py` (issue #49) already
established, duplicated here (not imported -- see that module's own
docstring on why `.github/scripts/` files stay independently self-
contained) so the two gates agree on what counts as "the same branch." Two
independent rules, the same layering Check C and the `#49` gate already
use: an absolute resolution check with no retrofit (any
`evals/<skill>/tasks/*.yaml` fixture that already declares
`expected.exercises` must have every label resolve against a real target,
`###` heading included, per the file's own shape; a fixture with no
`exercises` field is never required to add one), and a delta-scoped
coverage demand reusing the `#49` gate's own `after_counter -
before_counter` machinery (when a diff introduces a *new* Stop-boundary
bullet or Procedure/Steps item, the skill must carry a fixture whose
`exercises` resolves to it -- the fixture set is read at head, not from
the diff, the same way the `#49` gate counts fixtures via `git ls-tree`;
see `check_new_procedure_stop_boundary_fixture_demand`'s own docstring for
the residual that leaves). Check E's vocabulary is also what Check C
resolves against, per this item's own ACM row ("extend
`check_exercises_declaration_coverage` and its label-resolution logic"):
the two never disagree about which labels are legal.
Deliberately excludes the `#49` gate's OTHER
decision-branch kind, named dispatch branches -- no `expected.exercises`
resolution target is defined for one anywhere in this design, so that kind
stays covered exclusively by that gate's own pre-existing count-based
check, never duplicated here.

Mirrors `gitapex_gate_retro_title_convention_citation.py`'s shape: the calling
workflow computes which `split.md`/`SKILL.md` files this PR actually added
or modified (pre-existing, already-shipped content is out of scope for a
gate whose job is to catch a gap before it ships), this script only grades
those files (and, for Checks A/B/C/D, each file's sibling `split.json`,
resolved by this repository's own `evals/<skill>/split.json` <->
`evals/<skill>/split.md` <-> `skills/<skill>/SKILL.md` naming convention).
Check E runs unconditionally against every `--skill-md` file's own
`evals/<skill>/tasks/` directly, independent of whether that skill has a
`split.json` at all.

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
import re
import sys
from collections import Counter
from pathlib import Path
from typing import TypeGuard

import yaml
from _gitapex_schema_validation import load_json_or_raise

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

#: One `main()` run's worth of already-loaded `split.json` files, keyed by
#: path. Check B (`check_precedence_branch_coverage`) and the `--split-md`
#: loop can both need the same skill's `split.json` in one run (a PR that
#: touches a skill's `split.md` and its `SKILL.md` together) -- routing both
#: through this cache means the second access is a dict lookup, not a
#: second read/parse of the same file.
_SplitJsonCache = dict[Path, tuple[dict[str, object] | None, str | None]]


def _load_split_json_cached(path: Path, cache: _SplitJsonCache) -> tuple[dict[str, object] | None, str | None]:
    if path not in cache:
        cache[path] = load_split_json(path)
    return cache[path]


class _SplitLoadError(Exception):
    """Internal-only: converted back to `(None, message)` immediately below."""


def load_split_json(path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Parse `path` (a skill's `split.json`) into its top-level object.

    Returns `(data, None)` on success, or `(None, <reason>)` when the file
    is missing, unreadable, undecodable, not valid JSON, or not a JSON
    object -- every caller below reads `split.json` through this one
    function, so a malformed file is reported the same way regardless of
    which check found it first. Delegates the read/parse/shape-check to
    `load_json_or_raise`, wrapping its raise-on-error contract back into
    this function's own tuple-return convention -- `OSError` (which
    `load_json_or_raise` already catches) covers a missing file via
    `FileNotFoundError`, one of its subclasses, so no separate
    `path.is_file()` pre-check is needed.
    """
    try:
        data = load_json_or_raise(path, _SplitLoadError)
    except _SplitLoadError as error:
        return None, str(error)
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


def check_precedence_branch_coverage(
    skill_md_path: Path, skill_text: str, repo_root: Path, cache: _SplitJsonCache | None = None
) -> str | None:
    """Return an offender message if `skill_md_path` documents a
    precedence/branching rule with no equivalence-class pair declared in
    its skill's own `split.json`, else None. A skill with no `split.json`
    at all is out of scope -- see module docstring, Check B.

    `cache` is optional and defaults to a fresh, call-local dict when
    omitted (every existing direct caller/test keeps working unchanged);
    `main()` passes its own run-wide cache so this function's own load
    reuses a `split.json` the `--split-md` loop already read this run,
    instead of reading it a second time.
    """
    phrases = find_precedence_phrases(skill_text)
    if not phrases:
        return None
    split_json_path = repo_root / "evals" / skill_md_path.parent.name / "split.json"
    if not split_json_path.is_file():
        return None
    data, error = _load_split_json_cached(split_json_path, cache if cache is not None else {})
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

    Label resolution goes through `resolvable_exercise_labels` (defined in
    the Check E section below -- issue #192 item 6, whose ACM row is
    literally "extend `check_exercises_declaration_coverage` and its
    label-resolution logic"), so this check accepts exactly the vocabulary
    Check E advertises: `###` section label, `Step N` ordinal or literal
    Procedure/Steps item text, or Stop-boundary bullet text. Keeping the
    two vocabularies apart -- as an earlier revision did, resolving here
    against `parse_section_labels` alone -- made a selection fixture
    declaring "Step 2" simultaneously pass Check E and fail Check C, and
    could make Check E's own delta-scoped demand unsatisfiable for a skill
    that has both `###` headings and a `split.json` (the demanded label
    would trip this check). The SCOPE gate below stays `###`-only, so this
    check reaches exactly the skills it reached before; only what it
    ACCEPTS widened. The widening cannot smuggle a stale pointer past
    Check C's own purpose (issue #631): every accepted label still has to
    resolve against a real current target in the sibling SKILL.md.
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
    resolvable_labels = resolvable_exercise_labels(skill_text)

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
        unmatched = [label for label in exercises if label.casefold() not in resolvable_labels]
        if unmatched:
            problems.append(
                f"{fixture_name}: exercises {unmatched!r} match no real ###-level section, Step-N ordinal, "
                f"Procedure/Steps item, or Stop-boundary bullet in {skill_md_path}"
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
    all_listed = set().union(*listed.values())
    # A file that declares a partition but lists nothing must not pass
    # vacuously -- `0:0:0` against an absent listing otherwise reconciles
    # perfectly.
    if not all_listed:
        return (
            f"{path}: declares a {declared[0]}:{declared[1]}:{declared[2]} partition but 'assignment' "
            "lists no fixture at all; the arithmetic cannot be checked"
        )

    overlaps = sorted(
        f"{name} (in {' and '.join(s for s in _SPLIT_NAMES if name in listed[s])})"
        for name in all_listed
        if sum(name in listed[s] for s in _SPLIT_NAMES) > 1
    )
    if overlaps:
        return (
            f"{path}: 'assignment' lists the same fixture in more than one split: "
            f"{', '.join(overlaps)} -- each fixture belongs to exactly one split, and a "
            "cross-split mention cannot be reconciled by an exclusion"
        )

    stale = sorted(exclusions - all_listed)
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
# Check E (issue #192 item 6, Refs #49 repair 1, #115 repair 1):
# Procedure/Steps item + Stop-boundary bullet exercises-label resolution
# ---------------------------------------------------------------------------

_PROC_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_PROC_FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*$")
_ANY_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
# Anchored with `[ \t]*$` (not `\b`) so the heading text is nothing but
# "Procedure"/"Steps" plus trailing whitespace -- `\b` alone let this match
# an unrelated heading merely starting with that word, e.g.
# "## Steps 2-3 -- a secret reachable only through history" in
# skills/scanning-leaked-secrets/references/worked-examples.md:344
# (found live during independent review of this gate).
_PROCEDURE_STEPS_HEADING_RE = re.compile(r"^#{1,6}[ \t]+(?:Procedure|Steps)[ \t]*$", re.IGNORECASE | re.MULTILINE)
_STOP_BOUNDARY_HEADING_RE = re.compile(r"^#{1,6}[ \t]+Stop boundar(?:y|ies)\b", re.IGNORECASE | re.MULTILINE)
_TOP_LEVEL_NUMBERED_ITEM_RE = re.compile(r"^(\d+)\.[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_TOP_LEVEL_DASH_BULLET_RE = re.compile(r"^-[ \t]+")


def _blank_fenced_blocks_length_aware(text: str) -> str:
    """Length/character-aware fence blanking, mirroring
    `gitapex_gate_skill_branch_fixture_coverage.py`'s own
    `_blank_fenced_blocks` (issue #49) so a Stop-boundary bullet's identity
    agrees exactly between the two gates, including CommonMark's own
    nested-fence rule (an inner 3-backtick line never closes an outer
    4+-backtick fence). Duplicated rather than imported -- see this
    section's own module-docstring paragraph on why `.github/scripts/`
    files stay independently self-contained."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in lines:
        if not in_fence:
            match = _PROC_FENCE_OPEN_RE.match(line)
            if match:
                in_fence = True
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                out.append("")
                continue
            out.append(line)
            continue
        match = _PROC_FENCE_CLOSE_RE.match(line)
        if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_len:
            in_fence = False
            fence_char = ""
            fence_len = 0
        out.append("")
    return "\n".join(out)


def _normalize_for_span_scan(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _blank_fenced_blocks_length_aware(text).split("\n")


def _heading_section_span(lines: list[str], heading_index: int) -> tuple[int, int]:
    """(start, end) line-index range (end exclusive) of the content
    strictly after the heading at `heading_index`, up to the next heading
    of any level or EOF -- mirrors the `#49` gate's own
    `_section_content_span`."""
    end = len(lines)
    for i in range(heading_index + 1, len(lines)):
        if _ANY_HEADING_RE.match(lines[i]):
            end = i
            break
    return heading_index + 1, end


def stop_boundary_identity_counter(skill_md_text: str) -> Counter[str]:
    """Content-keyed multiset of top-level (column-0) '- ' bullets directly
    under every '## Stop boundary'/'## Stop boundaries' heading (any
    heading level, case-insensitive) -- the identical identity convention
    `gitapex_gate_skill_branch_fixture_coverage.py`'s own
    `stop_boundary_bullet_counter` already established (issue #49), so the
    two gates agree on what counts as "the same branch"."""
    lines = _normalize_for_span_scan(skill_md_text)
    counter: Counter[str] = Counter()
    for i, line in enumerate(lines):
        if _STOP_BOUNDARY_HEADING_RE.match(line):
            start, end = _heading_section_span(lines, i)
            for j in range(start, end):
                if _TOP_LEVEL_DASH_BULLET_RE.match(lines[j]):
                    counter[f"stop-boundary:{lines[j].strip()}"] += 1
    return counter


def parse_procedure_step_items(skill_md_text: str) -> list[tuple[int, str]]:
    """Ordered (source order) list of ``(source ordinal, item text)`` for
    every top-level (column-0) numbered item under every
    '## Procedure'/'## Steps' heading (any heading level,
    case-insensitive).

    The ordinal is the item's OWN number as written in the Markdown, not a
    running 1..N index over the flattened list. Issue #192 item 6's design
    specifies "the Nth numbered item (1-indexed, *matching the list's own
    source numbering*)", and a running index does not: the adversarial
    review (issue #192 step 8) found three shipped skills in this
    repository -- `reviewing-an-artifact`, `merge-retrospective`,
    `battle-testing-a-skill` -- whose Procedure lists start at `0.`, this
    repository's own convention for a pre-flight step (`reviewing-an-
    artifact`'s own frontmatter says "the eight Step 0 deferral targets").
    Under a running index every one of their ordinals was off by one:
    a fixture correctly declaring "Step 0" resolved against nothing, a
    non-existent "Step 7" resolved successfully, and "Step 3" silently
    resolved to the item actually numbered `2.` -- defeating the very
    resolve-against-a-real-target guarantee this check exists to give.
    Reading the source ordinal also fixes the flattening the same review
    named: two Procedure/Steps sections in one file, or a restarted
    numbered list inside one, no longer inflate later ordinals."""
    lines = _normalize_for_span_scan(skill_md_text)
    items: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if _PROCEDURE_STEPS_HEADING_RE.match(line):
            start, end = _heading_section_span(lines, i)
            for j in range(start, end):
                match = _TOP_LEVEL_NUMBERED_ITEM_RE.match(lines[j])
                if match:
                    items.append((int(match.group(1)), match.group(2).strip()))
    return items


def parse_procedure_steps(skill_md_text: str) -> list[str]:
    """Just the item texts from `parse_procedure_step_items`, in source
    order -- the position-independent view `procedure_step_identity_counter`
    keys its content identity on."""
    return [item_text for _ordinal, item_text in parse_procedure_step_items(skill_md_text)]


def procedure_step_identity_counter(skill_md_text: str) -> Counter[str]:
    """Content-keyed multiset of Procedure/Steps items -- delta-scoping
    identity only, deliberately position-independent (unlike
    `parse_procedure_steps`'s own positional reading, used only for label
    resolution): an unrelated insertion earlier in the list must not make
    every later item register as 'new' just because its ordinal shifted."""
    counter: Counter[str] = Counter()
    for item_text in parse_procedure_steps(skill_md_text):
        counter[f"procedure-step:{item_text}"] += 1
    return counter


def _stop_boundary_bullet_label(counter_key: str) -> str:
    """The casefolded, declarable label form of a `stop_boundary_identity_counter`
    key: the bullet's own text with its leading '- ' marker stripped (a
    fixture author declares the bullet's own wording, not raw Markdown
    syntax). The counter key itself keeps the marker -- see
    `stop_boundary_identity_counter`'s own docstring -- since that identity
    must agree byte-for-byte with `gitapex_gate_skill_branch_fixture_coverage.py`'s
    own convention; this stripping is resolution-only."""
    _, _, bullet_text = counter_key.partition(":")
    return _TOP_LEVEL_DASH_BULLET_RE.sub("", bullet_text, count=1).casefold()


def resolvable_exercise_labels(skill_md_text: str) -> set[str]:
    """Casefolded union of every real `expected.exercises` target this
    SKILL.md exposes: its own '###'-level section labels (Check C's
    existing convention, reused via `parse_section_labels`), a 'Step N'
    ordinal or the literal text of a Procedure/Steps item, and a
    Stop-boundary bullet's own first-line text (marker stripped). Empty
    when the file uses none of the three conventions -- callers treat
    that as out of scope.

    A 'Step N' label resolves against the item's OWN source ordinal -- see
    `parse_procedure_step_items` for why a running 1..N index is wrong
    against this repository's real content."""
    labels: set[str] = set(parse_section_labels(skill_md_text))
    for ordinal, item_text in parse_procedure_step_items(skill_md_text):
        labels.add(f"step {ordinal}")
        labels.add(item_text.casefold())
    for key in stop_boundary_identity_counter(skill_md_text):
        labels.add(_stop_boundary_bullet_label(key))
    return labels


def check_procedure_stop_boundary_exercises_coverage(
    skill_md_path: Path, skill_md_text: str, repo_root: Path
) -> str | None:
    """Issue #192 item 6 (Refs #49 repair 1, #115 repair 1): absolute
    resolution, no retrofit. Any `evals/<skill>/tasks/*.yaml` fixture that
    already declares `expected.exercises` must have every label resolve
    against a real target `resolvable_exercise_labels` exposes for this
    SKILL.md. Unlike Check C's own selection-scoped rule, a fixture with
    no `exercises` field is never required to add one -- passes untouched.
    Runs unconditionally, independent of whether this skill has a
    `split.json` at all: reads every task YAML under
    `evals/<skill>/tasks/` directly rather than a `split.json`-declared
    `selection` subset -- the inline `fixtureWithExpected` declaration
    form Check C also supports is out of scope here (no real `split.json`
    in this repository uses it today; a disclosed, deliberate narrowing).
    Out of scope (returns None) when the SKILL.md uses none of the three
    resolvable conventions, or the skill has no `evals/<skill>/tasks/`
    directory at all."""
    targets = resolvable_exercise_labels(skill_md_text)
    if not targets:
        return None
    skill_name = skill_md_path.parent.name
    tasks_dir = repo_root / "evals" / skill_name / "tasks"
    if not tasks_dir.is_dir():
        return None
    problems: list[str] = []
    for fixture_path in sorted(tasks_dir.glob("*.yaml")):
        if not fixture_path.is_file():
            # A `*.yaml`-named directory under tasks/ would otherwise raise
            # IsADirectoryError out of read_text -- matches the established
            # is_file() pre-check this file already uses above (Check C's
            # own inline-vs-file fixture read).
            continue
        try:
            fixture_data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            problems.append(f"{fixture_path.name}: could not parse YAML ({error})")
            continue
        expected = fixture_data.get("expected") if isinstance(fixture_data, dict) else None
        if not isinstance(expected, dict) or "exercises" not in expected:
            continue
        exercises = expected.get("exercises")
        if not _is_real_exercises_declaration(exercises):
            problems.append(
                f"{fixture_path.name}: no well-formed exercises declaration (a non-empty list of section labels)"
            )
            continue
        unmatched = [label for label in exercises if label.casefold() not in targets]
        if unmatched:
            problems.append(
                f"{fixture_path.name}: exercises {unmatched!r} match no ### section label, Step-N ordinal, "
                f"Procedure/Steps item, or Stop-boundary bullet in {skill_md_path}"
            )
    if not problems:
        return None
    return f"{skill_md_path}: procedure/stop-boundary exercises-declaration gap -- {'; '.join(problems)}"


def new_procedure_stop_boundary_content(before_text: str | None, after_text: str) -> list[str]:
    """Every Stop-boundary-bullet or Procedure/Steps-item content key this
    diff newly introduces -- a Counter key whose after-count exceeds its
    before-count, mirroring `gitapex_gate_skill_branch_fixture_coverage.py`'s
    own `after_counter - before_counter` delta-scoping (issue #49).
    `before_text=None` (a brand-new SKILL.md) counts every item as new."""
    after_counter = stop_boundary_identity_counter(after_text) + procedure_step_identity_counter(after_text)
    if before_text is None:
        return sorted(after_counter.elements())
    before_counter = stop_boundary_identity_counter(before_text) + procedure_step_identity_counter(before_text)
    delta = after_counter - before_counter
    return sorted(delta.elements())


def check_new_procedure_stop_boundary_fixture_demand(
    skill_md_path: Path, before_text: str | None, after_text: str, repo_root: Path
) -> str | None:
    """Issue #192 item 6: delta-scoped coverage demand. When a diff
    introduces a new Stop-boundary bullet or Procedure/Steps item (per
    `new_procedure_stop_boundary_content`), the skill must have at least
    one `evals/<skill>/tasks/*.yaml` fixture whose declared
    `expected.exercises` resolves to it. A pre-existing gap this diff did
    not create is never retroactively flagged -- when nothing is new,
    there is nothing to check. Deliberately scoped to only the two kinds
    this design built a resolution target for; a new named dispatch
    branch stays covered exclusively by the `#49` gate's own pre-existing
    count-based check (see this Check E section's own module-docstring
    paragraph).

    Disclosed structural limit -- the covering fixture is read from the
    skill's CURRENT `tasks/` directory, so this cannot require that the
    fixture was ADDED BY THE SAME DIFF; the workflow hands this gate no
    diff-side fixture information, exactly as the `#49` gate it mirrors
    counts the head-revision fixture set via `git ls-tree` rather than
    diff-added files. An earlier revision of this docstring claimed the
    stronger "must, in that same diff, add ..." rule; the issue #192 step
    8 adversarial review found the code never enforced it, and the claim
    is corrected here rather than left as an unverified behavioural
    assertion. The concrete residual this leaves: inserting a new item
    into the MIDDLE of a Procedure list is satisfied by a pre-existing
    fixture that declared that ordinal for the item previously at that
    position -- a consequence of ordinal labels being positional, which
    the design doc's own author guidance already warns about ("prefer a
    heading or bullet-prefix label over a `Step N` ordinal where
    practical"). Closing it needs diff-side fixture data this gate is not
    given; a literal-text label is unaffected.

    Clarification on that guidance's own wording (issue #192 step 8
    adversarial review): "bullet-prefix label" names WHICH label kind to
    prefer (a Stop-boundary bullet or Procedure/Steps item, as opposed to
    a `Step N` ordinal), not permission to declare only a truncated
    PREFIX of the bullet's own text. Resolution here and in
    `resolvable_exercise_labels` is an exact casefold match against the
    item's own full first-line text (`_stop_boundary_bullet_label`,
    `parse_procedure_step_items`'s `item_text`) -- a fixture author who
    declares a shortened prefix of a long bullet/item will not resolve.
    """
    new_content = new_procedure_stop_boundary_content(before_text, after_text)
    if not new_content:
        return None
    skill_name = skill_md_path.parent.name
    tasks_dir = repo_root / "evals" / skill_name / "tasks"
    covered_labels: set[str] = set()
    if tasks_dir.is_dir():
        for fixture_path in sorted(tasks_dir.glob("*.yaml")):
            if not fixture_path.is_file():
                # Same IsADirectoryError guard as
                # check_procedure_stop_boundary_exercises_coverage above.
                continue
            try:
                fixture_data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
            except (yaml.YAMLError, UnicodeDecodeError):
                continue
            expected = fixture_data.get("expected") if isinstance(fixture_data, dict) else None
            exercises = expected.get("exercises") if isinstance(expected, dict) else None
            if not _is_real_exercises_declaration(exercises):
                continue
            covered_labels.update(label.casefold() for label in exercises)

    after_items = parse_procedure_step_items(after_text)
    uncovered: list[str] = []
    for key in new_content:
        kind, _, text = key.partition(":")
        if kind == "stop-boundary":
            resolved = _stop_boundary_bullet_label(key) in covered_labels
        else:
            resolved = text.casefold() in covered_labels or any(
                f"step {ordinal}" in covered_labels for ordinal, item_text in after_items if item_text == text
            )
        if not resolved:
            uncovered.append(f"{kind}: {text!r}")
    if not uncovered:
        return None
    return (
        f"{skill_md_path}: this diff introduces new Stop-boundary bullet/Procedure-Steps item(s) with no "
        f"evals/{skill_name}/tasks/*.yaml fixture whose exercises resolves to them -- {'; '.join(uncovered)}"
    )


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
    parser.add_argument(
        "--skill-md-before-map",
        help="Optional path to a '<skill-md-after-path><TAB><before-content-path-or-empty>' "
        "entries file (workflow-computed, one line per --skill-md file), enabling Check E's "
        "delta-scoped coverage demand. Omit to skip that demand check entirely -- Check E's "
        "absolute resolution check still runs unconditionally against every --skill-md file.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    before_map: dict[str, str] = {}
    if args.skill_md_before_map:
        try:
            before_map_text = Path(args.skill_md_before_map).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as before_map_error:
            print(f"error: could not read --skill-md-before-map file: {before_map_error}", file=sys.stderr)
            return 1
        for line in before_map_text.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                print(
                    f"error: malformed --skill-md-before-map line (expected 2 tab-separated fields): {line!r}",
                    file=sys.stderr,
                )
                return 1
            before_map[parts[0]] = parts[1]

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
    split_json_cache: _SplitJsonCache = {}

    for raw_path in args.split_md:
        path = Path(raw_path)
        text = _read(path)
        if text is None:
            return 1
        split_json_path = path.parent / "split.json"
        data, error = _load_split_json_cached(split_json_path, split_json_cache)
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
        offender = check_precedence_branch_coverage(path, text, repo_root, cache=split_json_cache)
        if offender:
            offenders.append(offender)
        sibling_split_json = repo_root / "evals" / path.parent.name / "split.json"
        if sibling_split_json.is_file() and sibling_split_json not in exercises_checked:
            exercises_checked.add(sibling_split_json)
            sibling_data, sibling_error = _load_split_json_cached(sibling_split_json, split_json_cache)
            if sibling_error or sibling_data is None:
                offenders.append(f"{sibling_split_json}: {sibling_error}")
            else:
                offender = check_exercises_declaration_coverage(sibling_split_json, sibling_data, repo_root)
                if offender:
                    offenders.append(offender)

        offender = check_procedure_stop_boundary_exercises_coverage(path, text, repo_root)
        if offender:
            offenders.append(offender)

        if args.skill_md_before_map:
            if raw_path not in before_map:
                # Fails CLOSED, not silently skipped: once a before-map file
                # is supplied at all, every --skill-md path is expected to
                # have its own entry (the calling workflow populates one line
                # per --skill-md file). A missing entry here means the
                # workflow's own map-building step is out of sync with its
                # --skill-md list -- exactly the kind of drift Check E exists
                # to catch elsewhere, so this gate must not pass it through
                # silently. Use an empty before-content path (not a missing
                # line) for a genuinely newly-added file.
                print(
                    f"error: --skill-md-before-map was supplied but has no entry for "
                    f"--skill-md path {raw_path!r} -- every --skill-md file must have a "
                    "corresponding before-map entry (use an empty before-content path "
                    "for a newly added file)",
                    file=sys.stderr,
                )
                return 1
            before_raw = before_map[raw_path]
            before_text: str | None = None
            if before_raw:
                try:
                    before_text = Path(before_raw).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as before_read_error:
                    # Fails CLOSED (a None before-text counts every item as
                    # new, i.e. stricter), but must still say so: an
                    # unreadable before-file turns an ordinary edit into a
                    # whole-file coverage demand, and swallowing the reason
                    # leaves that inexplicable in the job log. Same warning
                    # shape as the sibling `#49` gate's own
                    # `_read_entries` before-content fallback.
                    print(
                        f"warning: could not read before-content for {raw_path!r} ({before_raw}): "
                        f"{before_read_error} -- treating as newly added",
                        file=sys.stderr,
                    )
                    before_text = None
            offender = check_new_procedure_stop_boundary_fixture_demand(path, before_text, text, repo_root)
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

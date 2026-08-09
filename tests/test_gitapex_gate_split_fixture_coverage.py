"""Tests for the split.md fixture-table coverage gate
(.github/scripts/gitapex_gate_split_fixture_coverage.py).

Issue #526, unifying two proposed gates from retrospective issues #191
(repair 1: a gate-result table must cover every declared `selection`
fixture) and #352 (repair 3: a SKILL.md precedence/branching rule must
have a train+held-out equivalence-class pair in its split.md). Issue #631
adds a third check: every declared `selection` fixture must declare a
well-formed `expected.exercises` list matching a real `###`-level section
in its sibling SKILL.md.

No test in this file makes a network call. The self-validation tests at
the bottom run the real gate against this repository's own `split.md`
files and SKILL.md files, doubling as a drift check: if a future edit to
any of them silently reintroduces the #191/#352/#631 gap shape, these
tests fail here before the CI gate would even need to run.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_split_fixture_coverage as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_SPLIT_MD_TEMPLATE = """\
# Held-out split for widget-polisher

## Assignment

- **train** (motivates edits; read for evidence, never scored for
  acceptance): `a-train.yaml`, `b-train.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`, `c-selection.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `d-test.yaml`.

## Kept-edit log

**Iteration: issue #1, some edit.**

| Fixture | Before | After |
|---|---|---|
{table_rows}
"""


def _split_md(table_rows: str) -> str:
    return _SPLIT_MD_TEMPLATE.format(table_rows=table_rows)


# ---------------------------------------------------------------------------
# parse_assignment_fixtures
# ---------------------------------------------------------------------------


def test_parse_assignment_fixtures_extracts_all_three_splits():
    result = gate.parse_assignment_fixtures(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n"))
    assert result["train"] == ["a-train.yaml", "b-train.yaml"]
    assert result["selection"] == ["edge.yaml", "c-selection.yaml"]
    assert result["test"] == ["d-test.yaml"]


def test_parse_assignment_fixtures_flat_bullet_style():
    # evals/scorer-gated-skill-edits/split.md's own shape: no parenthetical
    # prose spanning the "test"/"train" words, single terse clause.
    text = (
        "## Assignment\n\n"
        "- **train** (may motivate edits): `normal.yaml`,\n"
        "  `edge.yaml`.\n"
        "- **selection** (held out for candidate acceptance):\n"
        "  `guardrail.yaml`.\n"
        "- **test** (final reporting only): `blind.yaml`.\n\n"
        "## Next section\n"
    )
    result = gate.parse_assignment_fixtures(text)
    assert result == {
        "train": ["normal.yaml", "edge.yaml"],
        "selection": ["guardrail.yaml"],
        "test": ["blind.yaml"],
    }


def test_parse_assignment_fixtures_missing_section_returns_empty_lists():
    result = gate.parse_assignment_fixtures("# No assignment section here\n")
    assert result == {"train": [], "selection": [], "test": []}


# ---------------------------------------------------------------------------
# check_latest_gate_table_coverage (Check A, issue #191)
# ---------------------------------------------------------------------------


def test_full_coverage_table_passes():
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n")
    assert gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text) is None


def test_missing_declared_fixture_from_latest_table_fails():
    # Reproduces the #191 incident shape: the declared selection split has
    # two fixtures, the reported gate table covers only one.
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")
    offender = gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "c-selection.yaml" in offender


def test_scoped_single_fixture_followup_table_is_exempt():
    # This repository's own established convention: "against [only]
    # `<fixture>.yaml`" scopes a table to one fixture on purpose.
    text = (
        "## Assignment\n\n"
        "- **train**: `a-train.yaml`.\n"
        "- **selection**: `edge.yaml`, `c-selection.yaml`.\n"
        "- **test**: `d-test.yaml`.\n\n"
        "## Kept-edit log\n\n"
        "**Gate result, one fresh dispatch per side against only "
        "`c-selection.yaml`:**\n\n"
        "| Fixture | Before | After |\n|---|---|---|\n"
        "| `c-selection.yaml` | 1.0 | 1.0 |\n"
    )
    offender = gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text)
    assert offender is None


def test_scoped_phrase_present_but_table_has_extra_fixture_is_not_exempt():
    # The "against `X.yaml`" phrase alone isn't sufficient if the table
    # itself covers more than that one fixture -- the exemption must match
    # the table's actual contents, not just nearby prose.
    text = (
        "## Assignment\n\n"
        "- **train**: `a-train.yaml`.\n"
        "- **selection**: `edge.yaml`, `c-selection.yaml`.\n"
        "- **test**: `d-test.yaml`.\n\n"
        "## Kept-edit log\n\n"
        "**Gate result, one fresh dispatch per side against only "
        "`c-selection.yaml`:**\n\n"
        "| Fixture | Before | After |\n|---|---|---|\n"
        "| `c-selection.yaml` | 1.0 | 1.0 |\n"
    )
    assert gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text) is None
    # Now widen the table to cover a second fixture while keeping the same
    # scoping phrase naming only the first -- edge.yaml is still missing
    # and the phrase no longer matches the table's actual fixture set.
    widened = text.replace(
        "| `c-selection.yaml` | 1.0 | 1.0 |\n",
        "| `c-selection.yaml` | 1.0 | 1.0 |\n| `other.yaml` | 1.0 | 1.0 |\n",
    )
    offender = gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), widened)
    assert offender is not None
    assert "edge.yaml" in offender


def test_no_gate_table_at_all_passes():
    text = "## Assignment\n\n- **train**: `a.yaml`.\n- **selection**: `b.yaml`.\n- **test**: `c.yaml`.\n"
    assert gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text) is None


def test_only_most_recent_table_is_checked():
    # An older, incomplete table earlier in the file must not fail the
    # gate if a later, complete table already supersedes it.
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")  # missing c-selection.yaml
    text += "\n**Iteration: issue #2, a later edit.**\n\n"
    text += "| Fixture | Before | After |\n|---|---|---|\n"
    text += "| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"
    assert gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text) is None


# ---------------------------------------------------------------------------
# find_precedence_phrases / has_precedence_equivalence_class_pair /
# check_precedence_branch_coverage (Check B, issue #352)
# ---------------------------------------------------------------------------


def test_find_precedence_phrases_matches_takes_precedence_over():
    text = "Template and title take precedence over this skill's own defaults."
    assert len(gate.find_precedence_phrases(text)) == 1


def test_find_precedence_phrases_matches_priority_synonym():
    assert len(gate.find_precedence_phrases("The CLI flag takes priority over the config file.")) == 1


def test_find_precedence_phrases_ignores_unrelated_conditional_prose():
    text = "If the repo has a template, fill it out; otherwise use the fallback shape."
    assert gate.find_precedence_phrases(text) == []


def test_has_precedence_equivalence_class_pair_true_for_matching_row():
    split_text = (
        "## Equivalence classes\n\n"
        "| # | Class | Train | Held-out |\n|---|---|---|---|\n"
        "| 9 | Step 4: repo's own title convention takes precedence over "
        "the skill's fallback shape | `title-convention-precedence-train.yaml` | "
        "`no-title-convention-fallback-selection.yaml` (selection) |\n"
    )
    assert gate.has_precedence_equivalence_class_pair(split_text) is True


def test_has_precedence_equivalence_class_pair_false_when_section_missing():
    assert gate.has_precedence_equivalence_class_pair("## Assignment\n\n- **train**: `a.yaml`.\n") is False


def test_has_precedence_equivalence_class_pair_false_when_row_has_one_fixture():
    split_text = (
        "## Equivalence classes\n\n"
        "| # | Class | Train | Held-out |\n|---|---|---|---|\n"
        "| 1 | some precedence rule | `only-one.yaml` |  |\n"
    )
    assert gate.has_precedence_equivalence_class_pair(split_text) is False


def test_check_precedence_branch_coverage_none_when_no_phrase(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("No precedence talk here.\n", encoding="utf-8")
    assert gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path) is None


def test_check_precedence_branch_coverage_none_when_no_split_md(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    assert gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path) is None


def test_check_precedence_branch_coverage_fails_when_split_md_lacks_pair(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.parent.mkdir(parents=True)
    split_md.write_text("## Assignment\n\n- **train**: `a.yaml`.\n", encoding="utf-8")
    offender = gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path)
    assert offender is not None
    assert "precedence" in offender.lower()


def test_check_precedence_branch_coverage_fails_loudly_on_undecodable_split_md(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.parent.mkdir(parents=True)
    split_md.write_bytes(b"\xff\xfe bad")
    offender = gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path)
    assert offender is not None
    assert "could not decode" in offender


def test_check_precedence_branch_coverage_passes_when_split_md_has_pair(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.parent.mkdir(parents=True)
    split_md.write_text(
        "## Equivalence classes\n\n"
        "| # | Class | Train | Held-out |\n|---|---|---|---|\n"
        "| 1 | precedence rule | `p-train.yaml` | `p-selection.yaml` |\n",
        encoding="utf-8",
    )
    assert gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path) is None


# ---------------------------------------------------------------------------
# parse_section_labels / _is_real_exercises_declaration /
# check_exercises_declaration_coverage (Check C, issue #631)
# ---------------------------------------------------------------------------

_ROUTING_SKILL_MD = (
    "## Routing\n\n"
    "### Code body -> How only\n\n"
    "(naming/structure). Never restate what the code already says.\n\n"
    "### Commit log -> a terse Why, not the full Why\n\n"
    "Per git-community consensus... a permanent record.\n"
)


def test_parse_section_labels_extracts_label_before_arrow():
    assert gate.parse_section_labels(_ROUTING_SKILL_MD) == {"code body", "commit log"}


def test_parse_section_labels_empty_when_no_section_headings():
    assert gate.parse_section_labels("## Routing\n\n- a bullet, not a heading\n") == set()


def test_parse_section_labels_casefolds():
    assert "commit log" in gate.parse_section_labels("### Commit Log -> whatever\n")


@pytest.mark.parametrize(
    "value",
    [
        ["Commit log"],
        ["Commit log", "Code comments"],
    ],
)
def test_is_real_exercises_declaration_accepts_nonempty_string_list(value):
    assert gate._is_real_exercises_declaration(value) is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        "Commit log",
        [],
        [""],
        ["   "],
        [1],
        ["Commit log", 2],
    ],
)
def test_is_real_exercises_declaration_rejects_bare_truthy_and_malformed(value):
    assert gate._is_real_exercises_declaration(value) is False


def _write_skill_and_tasks(tmp_path: pathlib.Path, skill_name: str, skill_md_body: str, fixtures: dict):
    skill_md = tmp_path / "skills" / skill_name / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(skill_md_body, encoding="utf-8")
    tasks_dir = tmp_path / "evals" / skill_name / "tasks"
    tasks_dir.mkdir(parents=True)
    for name, content in fixtures.items():
        (tasks_dir / name).write_text(content, encoding="utf-8")
    return skill_md


def test_exercises_coverage_none_when_skill_has_no_section_headings(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("No section headings here.\n", encoding="utf-8")
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is None


def test_exercises_coverage_none_when_no_selection_fixtures_declared(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    split_text = "## Assignment\n\n- **train**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is None


def test_exercises_coverage_fails_when_selection_fixture_missing_declaration(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  output_contains:\n    - "x"\n'},
    )
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "a.yaml" in offender
    assert "no well-formed expected.exercises" in offender


def test_exercises_coverage_fails_when_label_matches_no_real_section(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Nonexistent Section"\n  output_contains:\n    - "x"\n'},
    )
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "Nonexistent Section" in offender


def test_exercises_coverage_passes_when_declaration_matches_real_section(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Commit log"\n  output_contains:\n    - "x"\n'},
    )
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is None


def test_exercises_coverage_matches_case_insensitively(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "COMMIT LOG"\n  output_contains:\n    - "x"\n'},
    )
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is None


def test_exercises_coverage_fails_loudly_on_undecodable_skill_md(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_bytes(b"\xff\xfe bad")
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "could not decode" in offender


def test_exercises_coverage_fails_when_fixture_file_missing(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    split_text = "## Assignment\n\n- **selection**: `missing.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "file not found" in offender


def test_exercises_coverage_fails_loudly_on_unparseable_yaml(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": "expected:\n  exercises: [unterminated\n"},
    )
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "could not parse YAML" in offender


def test_exercises_coverage_fails_loudly_on_undecodable_fixture_yaml(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    (tmp_path / "evals" / "widget-polisher" / "tasks" / "a.yaml").write_bytes(b"\xff\xfe bad")
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "could not parse YAML" in offender


def test_exercises_coverage_none_when_sibling_skill_md_missing(tmp_path: pathlib.Path):
    (tmp_path / "evals" / "widget-polisher" / "tasks").mkdir(parents=True)
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is None


def test_exercises_coverage_non_dict_fixture_does_not_crash(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {"a.yaml": "- just\n- a\n- list\n"})
    split_text = "## Assignment\n\n- **selection**: `a.yaml`.\n"
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.md", split_text, tmp_path
    )
    assert offender is not None
    assert "no well-formed expected.exercises" in offender


def test_parse_section_labels_ignores_heading_shaped_line_inside_fence():
    # Adversarial review (issue #631): a "### Fake heading" line only
    # illustrating Markdown syntax inside a fenced code block must not be
    # mistaken for a real section.
    text = (
        "### Code body -> How only\n\ntext\n\n"
        "```markdown\n### Fake heading -> not real\n```\n\n"
        "### Test code -> What\n\ntext\n"
    )
    assert gate.parse_section_labels(text) == {"code body", "test code"}


def test_parse_section_labels_still_matches_after_a_closed_fence():
    # Regression guard on the fence-toggle logic itself: a heading after a
    # properly closed fence must still be counted (in_fence must flip back
    # off, not stay stuck on).
    text = "```\nsome code\n```\n\n### Real heading -> text\n"
    assert gate.parse_section_labels(text) == {"real heading"}


def test_explaining_the_work_skill_md_actually_has_section_headings():
    # Sanity check that the self-validation test above (and the repo-wide
    # one below) isn't vacuously true because no real file ever triggers
    # Check C's scope condition at all.
    path = REPO_ROOT / "skills" / "explaining-the-work" / "SKILL.md"
    assert gate.parse_section_labels(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# parse_declared_partition / parse_arithmetic_exclusions /
# check_partition_arithmetic (Check D, issue #907)
# ---------------------------------------------------------------------------

_PARTITION_SPLIT_MD_TEMPLATE = """\
# Held-out split for widget-polisher

## Corpus size

... combines a 1:2:1 base partition with a 1:0:0 addition, {declaration}.

{exclusion_line}

## Assignment

- **train** (motivates edits): `a-train.yaml`, `b-train.yaml`.
- **selection** (gates acceptance): `edge.yaml`, `c-selection.yaml`.
- **test** (read once): `d-test.yaml`.
"""


def _partition_split_md(declaration: str = "for a resulting 2:2:1 partition", exclusion_line: str = "") -> str:
    return _PARTITION_SPLIT_MD_TEMPLATE.format(declaration=declaration, exclusion_line=exclusion_line)


def test_parse_declared_partition_reads_the_prose_figures():
    assert gate.parse_declared_partition(_partition_split_md()) == (2, 2, 1)


def test_parse_declared_partition_none_when_no_declaration():
    assert gate.parse_declared_partition(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n")) is None


def test_parse_declared_partition_matches_a_bolded_non_resulting_phrasing():
    # evals/merge-retrospective/split.md's own wording, which an earlier
    # draft keyed to the literal word "resulting" and silently missed.
    text = _partition_split_md(declaration="this split uses a flatter **9:6:3** partition (train:selection:test)")
    assert gate.parse_declared_partition(text) == (9, 6, 3)


def test_parse_declared_partition_ignores_a_ratio_not_qualifying_partition():
    # "SkillOpt's default split ratio is 2:1:7" is not a declaration.
    assert gate.parse_declared_partition("SkillOpt's default split ratio is 2:1:7. At 18 fixtures ...") is None


def test_parse_declared_partition_none_when_declarations_disagree():
    text = _partition_split_md(declaration="for a resulting 1:1:1 partition, superseded by a 4:5:6 partition")
    assert gate.parse_declared_partition(text) is None
    assert gate.count_declared_partitions(text) == 2


def test_parse_declared_partition_accepts_a_repeated_identical_declaration():
    text = _partition_split_md(declaration="for a resulting 2:2:1 partition, i.e. a 2:2:1 partition")
    assert gate.parse_declared_partition(text) == (2, 2, 1)


def test_check_partition_arithmetic_flags_disagreeing_declarations():
    text = _partition_split_md(
        declaration="for a resulting 1:1:1 partition, superseded by a 4:5:6 partition",
        exclusion_line="Split-arithmetic exclusions: none",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "2 disagreeing" in offender


def test_parse_declared_partition_ignores_a_declaration_below_the_assignment_heading():
    # This repository's split.md files carry append-only edit logs that
    # quote historical ratios; one phrased as a partition must not
    # re-target the check.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    text += "\n## Kept-edit log\n\n**Iteration: issue #999.** ... for a resulting 19:20:11 partition.\n"
    assert gate.parse_declared_partition(text) == (2, 2, 1)
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_parse_declared_partition_ignores_a_fenced_declaration():
    text = "```markdown\nfor a resulting 99:99:99 partition\n```\n\n## Assignment\n\n- **train**: `a.yaml`.\n"
    assert gate.parse_declared_partition(text) is None


def test_parse_arithmetic_exclusions_ignores_a_fenced_line():
    # A fenced example illustrating the convention must not satisfy the
    # must-carry-a-line requirement, which would fail open as an explicit
    # "none".
    text = _partition_split_md(exclusion_line="```markdown\nSplit-arithmetic exclusions: none\n```")
    assert gate.parse_arithmetic_exclusions(text) is None
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "carries no" in offender


def test_parse_arithmetic_exclusions_rejects_an_empty_payload():
    result = gate.parse_arithmetic_exclusions(_partition_split_md(exclusion_line="Split-arithmetic exclusions:   "))
    assert isinstance(result, str)
    assert "empty" in result


def test_parse_arithmetic_exclusions_rejects_unbackticked_names():
    result = gate.parse_arithmetic_exclusions(
        _partition_split_md(exclusion_line="Split-arithmetic exclusions: a-train.yaml")
    )
    assert isinstance(result, str)
    assert "backtick" in result


def test_parse_arithmetic_exclusions_rejects_more_than_one_line():
    text = _partition_split_md(
        exclusion_line="Split-arithmetic exclusions: none\n\nSplit-arithmetic exclusions: `a-train.yaml`"
    )
    result = gate.parse_arithmetic_exclusions(text)
    assert isinstance(result, str)
    assert "2 " in result


def test_check_partition_arithmetic_reports_a_malformed_exclusion_line():
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: a-train.yaml")
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "backtick" in offender


def test_check_partition_arithmetic_flags_a_cross_split_mention():
    # A bullet naming another split's fixture is unfixable by exclusion:
    # waiving it to satisfy this split breaks the split that owns it.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none").replace(
        "`b-train.yaml`.", "`b-train.yaml` (held-out counterpart: `d-test.yaml`)."
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "more than one split" in offender
    assert "d-test.yaml (in train and test)" in offender


def test_parse_assignment_fixtures_stops_at_a_trailing_paragraph():
    # evals/merge-retrospective/split.md's shape: an explanatory paragraph
    # after the last bullet naming pre-existing fixtures. Absorbing it
    # inflated the last split's count.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    text = text.replace(
        "- **test** (read once): `d-test.yaml`.\n",
        "- **test** (read once): `d-test.yaml`.\n\nThe pre-existing fixtures (`a-train.yaml`, `edge.yaml`)\n"
        "predate this split.\n",
    )
    assert gate.parse_assignment_fixtures(text)["test"] == ["d-test.yaml"]
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_check_partition_arithmetic_flags_a_duplicated_assignment_heading():
    # `_section` reads the FIRST heading, so an appended superseding
    # listing would be silently invisible.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    text += "\n## Assignment\n\n- **train** (superseding): `a-train.yaml`, `b-train.yaml`, `x.yaml`.\n"
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "2 '## Assignment' headings" in offender


def test_check_partition_arithmetic_flags_a_declared_partition_with_nothing_listed():
    # `0:0:0` against an absent listing otherwise reconciles perfectly.
    text = "for a resulting 0:0:0 partition.\n\nSplit-arithmetic exclusions: none\n"
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "lists no fixture at all" in offender


def test_check_partition_arithmetic_still_flags_a_stale_exclusion_named_only_in_prose():
    # The self-cancelling leak: a deleted fixture name-dropped in a
    # trailing Assignment paragraph used to count as "listed", so the
    # exclusion never read as stale and the +1/-1 cancelled.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: `deleted-long-ago.yaml`")
    text = text.replace(
        "- **test** (read once): `d-test.yaml`.\n",
        "- **test** (read once): `d-test.yaml`.\n\nHistorical note: `deleted-long-ago.yaml` was deleted.\n",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "stale exclusion" in offender


def test_parse_arithmetic_exclusions_none_when_line_absent():
    assert gate.parse_arithmetic_exclusions(_partition_split_md()) is None


def test_parse_arithmetic_exclusions_empty_set_for_explicit_none():
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    assert gate.parse_arithmetic_exclusions(text) == set()


def test_parse_arithmetic_exclusions_reads_named_fixtures():
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: `a-train.yaml`, `d-test.yaml` -- why")
    assert gate.parse_arithmetic_exclusions(text) == {"a-train.yaml", "d-test.yaml"}


def test_check_partition_arithmetic_passes_when_figures_reconcile():
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_check_partition_arithmetic_skips_a_file_declaring_no_partition():
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_check_partition_arithmetic_flags_a_missing_exclusion_line():
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), _partition_split_md())
    assert offender is not None
    assert "Split-arithmetic exclusions:" in offender


def test_check_partition_arithmetic_flags_the_pre_907_shape():
    # The exact defect this check exists to catch: one more listed fixture
    # than the declared figure, with no exclusion accounting for it.
    text = _partition_split_md(
        declaration="for a resulting 1:2:1 partition",
        exclusion_line="Split-arithmetic exclusions: none",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "declared train figure 1" in offender
    assert "2 unique train fixture(s)" in offender
    assert "with no exclusion here" in offender


def test_check_partition_arithmetic_accepts_a_declared_exclusion():
    text = _partition_split_md(
        declaration="for a resulting 1:2:1 partition",
        exclusion_line="Split-arithmetic exclusions: `b-train.yaml` -- listing consistency only",
    )
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_check_partition_arithmetic_names_the_exclusion_in_a_still_failing_split():
    text = _partition_split_md(
        declaration="for a resulting 2:2:1 partition",
        exclusion_line="Split-arithmetic exclusions: `b-train.yaml` -- listing consistency only",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "excluding b-train.yaml" in offender


def test_check_partition_arithmetic_flags_a_stale_exclusion():
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: `gone.yaml` -- removed long ago")
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "stale exclusion" in offender


def test_check_partition_arithmetic_flags_a_selection_mismatch():
    text = _partition_split_md(
        declaration="for a resulting 2:5:1 partition",
        exclusion_line="Split-arithmetic exclusions: none",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "declared selection figure 5" in offender


def test_check_partition_arithmetic_flags_a_test_mismatch():
    text = _partition_split_md(
        declaration="for a resulting 2:2:9 partition",
        exclusion_line="Split-arithmetic exclusions: none",
    )
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), text)
    assert offender is not None
    assert "declared test figure 9" in offender


def test_check_partition_arithmetic_counts_unique_names_not_mentions():
    # A parenthetical cross-reference repeating a name must not inflate the
    # count -- this repository's real Assignment bullets do exactly that.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none").replace(
        "`b-train.yaml`.", "`b-train.yaml` (see `a-train.yaml` in eval-status.md)."
    )
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


# ---------------------------------------------------------------------------
# Second-review-round regressions (issue #907). Each test below pins a
# defect a /code-review round demonstrated against the first hardening
# pass; every one of them was a real, reproduced fail-open or false
# positive, not a theoretical concern.
# ---------------------------------------------------------------------------

_INTERNAL_BREAK_SPLIT_MD = """\
# Held-out split for widget-polisher

## Assignment

- **selection** (gates acceptance): `edge.yaml`,

  and, after an indented paragraph break, `c-selection.yaml`.

## Kept-edit log

**Iteration: issue #1, some edit.**

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.0 | 1.0 |
"""


def test_bullet_survives_an_indented_internal_paragraph_break():
    # A bare blank-line terminator truncated the bullet here, silently
    # shrinking `selection` from 2 fixtures to 1.
    assert gate.parse_assignment_fixtures(_INTERNAL_BREAK_SPLIT_MD)["selection"] == [
        "edge.yaml",
        "c-selection.yaml",
    ]


def test_check_a_still_flags_a_gap_after_an_internal_paragraph_break():
    # The consequence of the truncation above: Check A passed a gate table
    # that omits a declared selection fixture -- a regression in a
    # pre-existing check, introduced while fixing Check D.
    offender = gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), _INTERNAL_BREAK_SPLIT_MD)
    assert offender is not None
    assert "c-selection.yaml" in offender


def test_bullet_still_ends_at_a_dedented_trailing_paragraph():
    # The boundary must still fire for a paragraph that leaves the list --
    # evals/merge-retrospective/split.md's own shape.
    text = _INTERNAL_BREAK_SPLIT_MD.replace(
        "  and, after an indented paragraph break, `c-selection.yaml`.",
        "Trailing prose naming `c-selection.yaml` at column zero.",
    )
    assert gate.parse_assignment_fixtures(text)["selection"] == ["edge.yaml"]


_FENCED_HEADING_ABOVE = """\
# Held-out split for widget-polisher

```markdown
## Assignment
```

... for a resulting 9:9:9 partition.

Split-arithmetic exclusions: none

## Assignment

- **train** (motivates edits): `a-train.yaml`, `b-train.yaml`.
- **selection** (gates acceptance): `c-selection.yaml`.
- **test** (read once): `d-test.yaml`.
"""


def test_declaration_region_ignores_a_fenced_assignment_heading_above_it():
    # Locating the heading in raw text truncated the region before the real
    # declaration, dropping the partition count to 0 and passing a 9:9:9
    # declaration against a 2/1/1 listing clean.
    assert gate.count_declared_partitions(_FENCED_HEADING_ABOVE) == 1
    assert gate.parse_declared_partition(_FENCED_HEADING_ABOVE) == (9, 9, 9)


def test_section_ignores_a_fenced_assignment_heading_above_the_real_one():
    # Same root cause one level deeper: `_section` returned the fence's own
    # bullet-free body, so every caller read an empty listing.
    listed = gate.parse_assignment_fixtures(_FENCED_HEADING_ABOVE)
    assert listed["train"] == ["a-train.yaml", "b-train.yaml"]
    assert listed["selection"] == ["c-selection.yaml"]
    assert listed["test"] == ["d-test.yaml"]


def test_check_partition_arithmetic_reports_the_real_mismatch_past_a_fenced_heading():
    offender = gate.check_partition_arithmetic(pathlib.Path("split.md"), _FENCED_HEADING_ABOVE)
    assert offender is not None
    assert "declared train figure 9" in offender
    assert "2 unique train fixture(s)" in offender


def test_duplicate_assignment_guard_ignores_a_fenced_heading():
    # Mirror-image false positive: a valid, fully reconciling file that
    # merely illustrates the convention in a fence was failed.
    text = _partition_split_md(exclusion_line="Split-arithmetic exclusions: none")
    text += "\nExample of the heading shape:\n\n```markdown\n## Assignment\n```\n"
    assert gate.check_partition_arithmetic(pathlib.Path("split.md"), text) is None


def test_parse_declared_partition_rejects_a_longer_colon_run():
    # Unanchored, these yielded (2, 1, 9) and (3, 4, 5) -- grading a file
    # against figures it never declared, which is worse than the
    # out-of-scope outcome the module's own docstring claimed.
    assert gate.parse_declared_partition("for a resulting 2:2:1:9 partition.") is None
    assert gate.parse_declared_partition("a 1:2:3:4:5 partition") is None


def test_parse_declared_partition_accepts_a_backticked_triple():
    # This repository's prose routinely backticks these figures.
    assert gate.parse_declared_partition("a `9:6:3` partition (train:selection:test)") == (9, 6, 3)


def test_parse_declared_partition_still_reads_a_bare_and_bolded_triple():
    assert gate.parse_declared_partition("for a resulting 27:30:12 partition") == (27, 30, 12)
    assert gate.parse_declared_partition("a flatter **9:6:3** partition") == (9, 6, 3)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_when_clean(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(
        _split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8"
    )
    assert gate.main(["--split-md", str(split_md)]) == 0


def test_main_returns_one_when_offender_found(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8")
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_one_when_split_md_unreadable(tmp_path: pathlib.Path):
    missing = tmp_path / "does-not-exist.md"
    assert gate.main(["--split-md", str(missing)]) == 1


def test_main_returns_one_when_split_md_undecodable(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_zero_with_no_files():
    assert gate.main([]) == 0


def _write_split_and_skill_md(
    tmp_path: pathlib.Path, skill_name: str, skill_md_body: str, fixtures: dict, selection: list[str]
):
    skill_md = _write_skill_and_tasks(tmp_path, skill_name, skill_md_body, fixtures)
    split_md = tmp_path / "evals" / skill_name / "split.md"
    selection_yaml = ", ".join(f"`{name}`" for name in selection)
    split_md.write_text(f"## Assignment\n\n- **selection**: {selection_yaml}.\n", encoding="utf-8")
    return skill_md, split_md


def test_main_check_c_fires_on_skill_md_only_diff(tmp_path: pathlib.Path):
    # Regression (adversarial review, issue #631): the calling workflow
    # populates --split-md/--skill-md independently based on which file
    # type actually changed in a PR's diff -- a SKILL.md-only diff (e.g.
    # renaming a ###-level section, with no split.md edit in the same PR)
    # must still run Check C via the sibling split.md, not silently skip
    # it because --split-md was never passed.
    skill_md, _split_md = _write_split_and_skill_md(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {}, ["a.yaml"])
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 1


def test_main_check_c_passes_on_skill_md_only_diff_with_valid_declaration(tmp_path: pathlib.Path):
    skill_md, _split_md = _write_split_and_skill_md(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Commit log"\n  output_contains:\n    - "x"\n'},
        ["a.yaml"],
    )
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 0


def test_main_check_c_not_double_reported_when_both_sides_passed(tmp_path: pathlib.Path, capsys):
    # Both --split-md and --skill-md naming the same pair (a PR touching
    # both files) must check Check C once, not report the same offender
    # twice.
    skill_md, split_md = _write_split_and_skill_md(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {}, ["a.yaml"])
    rc = gate.main(
        [
            "--split-md",
            str(split_md),
            "--skill-md",
            str(skill_md),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1
    stderr = capsys.readouterr().err
    assert stderr.count("exercises-declaration gap") == 1


def test_main_check_c_absent_when_sibling_split_md_missing(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(_ROUTING_SKILL_MD, encoding="utf-8")
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 0


# ---------------------------------------------------------------------------
# Self-validation against this repository's real split.md/SKILL.md files.
# These double as a drift check: a future edit that reintroduces the
# #191/#352 gap shape into real, shipped content fails here.
# ---------------------------------------------------------------------------

_REAL_SPLIT_MD_FILES = sorted((REPO_ROOT / "evals").glob("*/split.md"))
_REAL_SKILL_MD_FILES = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))


def test_every_real_split_md_passes_check_a():
    assert _REAL_SPLIT_MD_FILES, "expected at least one real evals/*/split.md file"
    for path in _REAL_SPLIT_MD_FILES:
        offender = gate.check_latest_gate_table_coverage(path, path.read_text(encoding="utf-8"))
        assert offender is None, offender


def test_every_real_skill_md_passes_check_b():
    assert _REAL_SKILL_MD_FILES, "expected at least one real skills/*/SKILL.md file"
    for path in _REAL_SKILL_MD_FILES:
        offender = gate.check_precedence_branch_coverage(path, path.read_text(encoding="utf-8"), REPO_ROOT)
        assert offender is None, offender


def test_merge_retrospective_skill_md_actually_has_a_precedence_phrase():
    # A sanity check that the self-validation test above isn't vacuously
    # true because no real file ever triggers Check B at all.
    path = REPO_ROOT / "skills" / "merge-retrospective" / "SKILL.md"
    assert gate.find_precedence_phrases(path.read_text(encoding="utf-8"))


def test_every_real_split_md_passes_check_c():
    assert _REAL_SPLIT_MD_FILES, "expected at least one real evals/*/split.md file"
    for path in _REAL_SPLIT_MD_FILES:
        offender = gate.check_exercises_declaration_coverage(path, path.read_text(encoding="utf-8"), REPO_ROOT)
        assert offender is None, offender


def test_every_real_split_md_passes_check_d():
    assert _REAL_SPLIT_MD_FILES, "expected at least one real evals/*/split.md file"
    for path in _REAL_SPLIT_MD_FILES:
        offender = gate.check_partition_arithmetic(path, path.read_text(encoding="utf-8"))
        assert offender is None, offender


def test_real_split_md_partition_declarations_are_pinned_exactly():
    # Pins WHICH real files Check D actually grades, so the self-validation
    # test above can never go quietly vacuous. An earlier draft of Check D
    # keyed its regex to the literal word "resulting" and silently skipped
    # merge-retrospective's differently-worded declaration; a bare "every
    # real file passes" test saw nothing, because a skipped file passes.
    # A new declaration (or a reworded existing one) fails here on purpose.
    declared = {
        path.parent.name: gate.parse_declared_partition(path.read_text(encoding="utf-8"))
        for path in _REAL_SPLIT_MD_FILES
    }
    assert declared == {
        "battle-testing-a-skill": None,
        "evaluating-skill-quality": (27, 30, 12),
        "explaining-the-work": None,
        "merge-retrospective": (9, 6, 3),
        "scorer-gated-skill-edits": None,
    }


def test_real_split_md_arithmetic_exclusions_are_pinned_exactly():
    # Same anti-vacuity discipline for the exclusion side: every file Check
    # D grades must carry a well-formed line, and what it waives is pinned
    # rather than left to drift.
    exclusions = {
        path.parent.name: gate.parse_arithmetic_exclusions(path.read_text(encoding="utf-8"))
        for path in _REAL_SPLIT_MD_FILES
        if gate.count_declared_partitions(path.read_text(encoding="utf-8")) == 1
    }
    assert exclusions == {
        "evaluating-skill-quality": {"dispatch-required-negative-control.yaml"},
        "merge-retrospective": set(),
    }


def test_main_reports_a_check_d_partition_offender(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]):
    # Drives Check D through main(), so the offender-collection path there is
    # exercised and not only check_partition_arithmetic in isolation.
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.parent.mkdir(parents=True)
    split_md.write_text(
        _partition_split_md(
            declaration="for a resulting 1:2:1 partition",
            exclusion_line="Split-arithmetic exclusions: none",
        ),
        encoding="utf-8",
    )
    rc = gate.main(["--split-md", str(split_md), "--repo-root", str(tmp_path)])
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "declared train figure 1" in stderr

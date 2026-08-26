"""Tests for the split.md/split.json fixture coverage gate
(.github/scripts/gitapex_gate_split_fixture_coverage.py).

Issue #526, unifying two proposed gates from retrospective issues #191
(repair 1: a gate-result table must cover every declared `selection`
fixture) and #352 (repair 3: a SKILL.md precedence/branching rule must
have a train+held-out equivalence-class pair in its skill's split.json).
Issue #631 adds a third check: every declared `selection` fixture must
declare a well-formed `exercises` list matching a real `###`-level section
in its sibling SKILL.md. Issue #928 moves Checks A, B, and D onto
`split.json` (structured data) instead of regex-parsing `split.md`'s now-
removed `## Assignment` / `## Equivalence classes` prose sections; Check C
stays cross-file against SKILL.md, now sourcing its declared-`selection`
list from `split.json` too.

No test in this file makes a network call. The self-validation tests at
the bottom run the real gate against this repository's own `split.json`,
`split.md`, and `SKILL.md` files, doubling as a drift check: if a future
edit to any of them silently reintroduces the #191/#352/#631/#907 gap
shape, these tests fail here before the CI gate would even need to run.
"""

from __future__ import annotations

import json
import pathlib

import gitapex_gate_split_fixture_coverage as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_SPLIT_JSON_TEMPLATE = {
    "assignment": {
        "train": ["a-train.yaml", "b-train.yaml"],
        "selection": ["edge.yaml", "c-selection.yaml"],
        "test": ["d-test.yaml"],
    }
}


def _split_json_text(**overrides: object) -> str:
    data = {**_SPLIT_JSON_TEMPLATE, **overrides}
    return json.dumps(data)


def _write_split_json(directory: pathlib.Path, **overrides: object) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "split.json"
    path.write_text(_split_json_text(**overrides), encoding="utf-8")
    return path


_SPLIT_MD_TEMPLATE = """\
# Held-out split for widget-polisher

See split.json for the fixture assignment.

## Kept-edit log

**Iteration: issue #1, some edit.**

| Fixture | Before | After |
|---|---|---|
{table_rows}
"""


def _split_md(table_rows: str) -> str:
    return _SPLIT_MD_TEMPLATE.format(table_rows=table_rows)


# ---------------------------------------------------------------------------
# load_split_json / assignment_fixtures
# ---------------------------------------------------------------------------


def test_load_split_json_reads_a_well_formed_file(tmp_path: pathlib.Path):
    path = _write_split_json(tmp_path)
    data, error = gate.load_split_json(path)
    assert error is None
    assert data == _SPLIT_JSON_TEMPLATE


def test_load_split_json_missing_file():
    data, error = gate.load_split_json(pathlib.Path("/nonexistent/split.json"))
    assert data is None
    assert "cannot be read" in error


def test_load_split_json_undecodable(tmp_path: pathlib.Path):
    path = tmp_path / "split.json"
    path.write_bytes(b"\xff\xfe bad")
    data, error = gate.load_split_json(path)
    assert data is None
    assert error is not None
    assert "is not valid UTF-8" in error


def test_load_split_json_malformed_json(tmp_path: pathlib.Path):
    path = tmp_path / "split.json"
    path.write_text("{not valid json", encoding="utf-8")
    data, error = gate.load_split_json(path)
    assert data is None
    assert error is not None
    assert "is not valid JSON" in error


def test_load_split_json_rejects_non_object_top_level(tmp_path: pathlib.Path):
    path = tmp_path / "split.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    data, error = gate.load_split_json(path)
    assert data is None
    assert error is not None
    assert "must be an object" in error


def test_assignment_fixtures_extracts_all_three_splits():
    result = gate.assignment_fixtures(_SPLIT_JSON_TEMPLATE)
    assert result["train"] == ["a-train.yaml", "b-train.yaml"]
    assert result["selection"] == ["edge.yaml", "c-selection.yaml"]
    assert result["test"] == ["d-test.yaml"]


def test_assignment_fixtures_missing_assignment_key_returns_empty_lists():
    assert gate.assignment_fixtures({}) == {"train": [], "selection": [], "test": []}


def test_assignment_fixtures_missing_split_key_defaults_to_empty_list():
    data: dict[str, object] = {"assignment": {"train": ["a.yaml"]}}
    result = gate.assignment_fixtures(data)
    assert result == {"train": ["a.yaml"], "selection": [], "test": []}


def test_assignment_fixtures_reads_fixture_with_expected_object_form():
    data = {
        "assignment": {
            "selection": [
                "plain.yaml",
                {"fixture": "with-expected.yaml", "expected": {"exercises": ["Commit log"]}},
            ]
        }
    }
    assert gate.assignment_fixtures(data)["selection"] == ["plain.yaml", "with-expected.yaml"]


def test_assignment_fixtures_ignores_a_malformed_entry():
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml", 42, {"no_fixture_key": True}]}}
    assert gate.assignment_fixtures(data)["selection"] == ["a.yaml"]


# ---------------------------------------------------------------------------
# check_latest_gate_table_coverage (Check A, issue #191)
# ---------------------------------------------------------------------------


def test_full_coverage_table_passes():
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n")
    assert (
        gate.check_latest_gate_table_coverage(
            pathlib.Path("split.md"), text, ["edge.yaml", "c-selection.yaml"], assignment_present=True
        )
        is None
    )


def test_missing_declared_fixture_from_latest_table_fails():
    # Reproduces the #191 incident shape: split.json's declared selection
    # split has two fixtures, the reported gate table covers only one.
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")
    offender = gate.check_latest_gate_table_coverage(
        pathlib.Path("split.md"), text, ["edge.yaml", "c-selection.yaml"], assignment_present=True
    )
    assert offender is not None
    assert "c-selection.yaml" in offender


def test_missing_assignment_object_fails_closed_not_vacuously():
    # A malformed/absent split.json 'assignment' must not read as "the
    # table covers everything declared" -- the same fail-open shape PR
    # #651's own precedent named for a different gate (issue #928 adversarial
    # review finding 1). declared_selection collapsing to [] because
    # assignment itself is missing is exactly the case assignment_present
    # exists to distinguish from "assignment is present and legitimately
    # declares an empty selection split."
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")
    offender = gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text, [], assignment_present=False)
    assert offender is not None
    assert "assignment" in offender


def test_empty_but_present_assignment_selection_still_passes():
    # Contrast with the above: a legitimately empty 'selection' array (the
    # key exists, assignment is a well-formed object) is not malformed and
    # must not be flagged.
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")
    assert gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text, [], assignment_present=True) is None


def test_scoped_single_fixture_followup_table_is_exempt():
    # This repository's own established convention: "against [only]
    # `<fixture>.yaml`" scopes a table to one fixture on purpose.
    text = (
        "# Held-out split\n\n"
        "**Gate result, one fresh dispatch per side against only "
        "`c-selection.yaml`:**\n\n"
        "| Fixture | Before | After |\n|---|---|---|\n"
        "| `c-selection.yaml` | 1.0 | 1.0 |\n"
    )
    offender = gate.check_latest_gate_table_coverage(
        pathlib.Path("split.md"), text, ["edge.yaml", "c-selection.yaml"], assignment_present=True
    )
    assert offender is None


def test_scoped_phrase_present_but_table_has_extra_fixture_is_not_exempt():
    # The "against `X.yaml`" phrase alone isn't sufficient if the table
    # itself covers more than that one fixture -- the exemption must match
    # the table's actual contents, not just nearby prose.
    text = (
        "# Held-out split\n\n"
        "**Gate result, one fresh dispatch per side against only "
        "`c-selection.yaml`:**\n\n"
        "| Fixture | Before | After |\n|---|---|---|\n"
        "| `c-selection.yaml` | 1.0 | 1.0 |\n"
    )
    assert (
        gate.check_latest_gate_table_coverage(
            pathlib.Path("split.md"), text, ["edge.yaml", "c-selection.yaml"], assignment_present=True
        )
        is None
    )
    # Now widen the table to cover a second fixture while keeping the same
    # scoping phrase naming only the first -- edge.yaml is still missing
    # and the phrase no longer matches the table's actual fixture set.
    widened = text.replace(
        "| `c-selection.yaml` | 1.0 | 1.0 |\n",
        "| `c-selection.yaml` | 1.0 | 1.0 |\n| `other.yaml` | 1.0 | 1.0 |\n",
    )
    offender = gate.check_latest_gate_table_coverage(
        pathlib.Path("split.md"), widened, ["edge.yaml", "c-selection.yaml"], assignment_present=True
    )
    assert offender is not None
    assert "edge.yaml" in offender


def test_no_gate_table_at_all_passes():
    text = "# Held-out split\n\nSee split.json for the fixture listing.\n"
    assert (
        gate.check_latest_gate_table_coverage(pathlib.Path("split.md"), text, ["b.yaml"], assignment_present=True)
        is None
    )


def test_only_most_recent_table_is_checked():
    # An older, incomplete table earlier in the file must not fail the
    # gate if a later, complete table already supersedes it.
    text = _split_md("| `edge.yaml` | 1.0 | 1.0 |\n")  # missing c-selection.yaml
    text += "\n**Iteration: issue #2, a later edit.**\n\n"
    text += "| Fixture | Before | After |\n|---|---|---|\n"
    text += "| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"
    assert (
        gate.check_latest_gate_table_coverage(
            pathlib.Path("split.md"), text, ["edge.yaml", "c-selection.yaml"], assignment_present=True
        )
        is None
    )


# ---------------------------------------------------------------------------
# find_precedence_phrases / has_equivalence_class_pair /
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


def test_has_equivalence_class_pair_true_for_a_well_formed_entry():
    data = {"equivalence_classes": [{"train_fixture": "p-train.yaml", "held_out_fixture": "p-selection.yaml"}]}
    assert gate.has_equivalence_class_pair(data) is True


def test_has_equivalence_class_pair_false_when_key_missing():
    assert gate.has_equivalence_class_pair({}) is False


def test_has_equivalence_class_pair_false_when_array_empty():
    assert gate.has_equivalence_class_pair({"equivalence_classes": []}) is False


def test_has_equivalence_class_pair_false_when_entry_missing_a_side():
    data = {"equivalence_classes": [{"train_fixture": "only-one.yaml"}]}
    assert gate.has_equivalence_class_pair(data) is False


def test_check_precedence_branch_coverage_none_when_no_phrase(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("No precedence talk here.\n", encoding="utf-8")
    assert gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path) is None


def test_check_precedence_branch_coverage_none_when_no_split_json(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    assert gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path) is None


def test_check_precedence_branch_coverage_fails_when_split_json_lacks_pair(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    _write_split_json(tmp_path / "evals" / "widget-polisher", assignment={"train": ["a.yaml"]})
    offender = gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path)
    assert offender is not None
    assert "precedence" in offender.lower()


def test_check_precedence_branch_coverage_fails_loudly_on_malformed_split_json(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    split_json = tmp_path / "evals" / "widget-polisher" / "split.json"
    split_json.parent.mkdir(parents=True)
    split_json.write_bytes(b"\xff\xfe bad")
    offender = gate.check_precedence_branch_coverage(skill_md, skill_md.read_text(), tmp_path)
    assert offender is not None
    assert "is not valid UTF-8" in offender


def test_check_precedence_branch_coverage_passes_when_split_json_has_pair(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    _write_split_json(
        tmp_path / "evals" / "widget-polisher",
        equivalence_classes=[{"train_fixture": "p-train.yaml", "held_out_fixture": "p-selection.yaml"}],
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
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_none_when_no_selection_fixtures_declared(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    data: dict[str, object] = {"assignment": {"train": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_fails_when_selection_fixture_missing_declaration(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  output_contains:\n    - "x"\n'},
    )
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "a.yaml" in offender
    assert "no well-formed exercises" in offender


def test_exercises_coverage_fails_when_label_matches_no_real_section(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Nonexistent Section"\n  output_contains:\n    - "x"\n'},
    )
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
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
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_matches_case_insensitively(tmp_path: pathlib.Path):
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "COMMIT LOG"\n  output_contains:\n    - "x"\n'},
    )
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_reads_inline_declaration_from_split_json(tmp_path: pathlib.Path):
    # split.schema.json's fixtureWithExpected shape: the exercises list is
    # declared inline in split.json itself, no fixture YAML needed.
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    data: dict[str, object] = {
        "assignment": {
            "selection": [{"fixture": "a.yaml", "expected": {"exercises": ["Commit log"]}}],
        }
    }
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_falls_back_to_fixture_yaml_when_inline_expected_not_a_dict(tmp_path: pathlib.Path):
    # A malformed inline `expected` (not itself an object) must not crash --
    # it falls back to the fixture's own task YAML, same as the plain
    # string-filename form.
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _ROUTING_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Commit log"\n  output_contains:\n    - "x"\n'},
    )
    data: dict[str, object] = {"assignment": {"selection": [{"fixture": "a.yaml", "expected": "not-a-dict"}]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_inline_declaration_still_checked_against_real_sections(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    data: dict[str, object] = {
        "assignment": {
            "selection": [{"fixture": "a.yaml", "expected": {"exercises": ["Nonexistent Section"]}}],
        }
    }
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "Nonexistent Section" in offender


def test_exercises_coverage_fails_loudly_on_undecodable_skill_md(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_bytes(b"\xff\xfe bad")
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "could not decode" in offender


def test_exercises_coverage_fails_when_fixture_file_missing(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    data: dict[str, object] = {"assignment": {"selection": ["missing.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
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
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "could not parse YAML" in offender


def test_exercises_coverage_fails_loudly_on_undecodable_fixture_yaml(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    (tmp_path / "evals" / "widget-polisher" / "tasks" / "a.yaml").write_bytes(b"\xff\xfe bad")
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "could not parse YAML" in offender


def test_exercises_coverage_none_when_sibling_skill_md_missing(tmp_path: pathlib.Path):
    (tmp_path / "evals" / "widget-polisher" / "tasks").mkdir(parents=True)
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is None


def test_exercises_coverage_non_dict_fixture_does_not_crash(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {"a.yaml": "- just\n- a\n- list\n"})
    data: dict[str, object] = {"assignment": {"selection": ["a.yaml"]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "no well-formed exercises" in offender


def test_exercises_coverage_reports_a_malformed_selection_entry(tmp_path: pathlib.Path):
    _write_skill_and_tasks(tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {})
    data: dict[str, object] = {"assignment": {"selection": [42]}}
    offender = gate.check_exercises_declaration_coverage(
        tmp_path / "evals" / "widget-polisher" / "split.json", data, tmp_path
    )
    assert offender is not None
    assert "not a well-formed fixture entry" in offender


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
# parse_declared_partition / check_partition_arithmetic (Check D, issue #907)
# ---------------------------------------------------------------------------


def test_parse_declared_partition_reads_the_field():
    assert gate.parse_declared_partition({"partition": "2:2:1"}) == (2, 2, 1)


def test_parse_declared_partition_none_when_key_absent():
    assert gate.parse_declared_partition({}) is None


def test_parse_declared_partition_none_when_not_a_string():
    assert gate.parse_declared_partition({"partition": 221}) is None


def test_parse_declared_partition_none_when_malformed_shape():
    assert gate.parse_declared_partition({"partition": "2:2"}) is None
    assert gate.parse_declared_partition({"partition": "2:2:1:9"}) is None
    assert gate.parse_declared_partition({"partition": "a resulting 2:2:1 partition"}) is None


def test_check_partition_arithmetic_reports_a_malformed_partition_string():
    data = {"partition": "not-a-ratio", "split_arithmetic_exclusions": []}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "not a well-formed" in offender


def test_check_partition_arithmetic_skips_a_file_declaring_no_partition():
    assert gate.check_partition_arithmetic(pathlib.Path("split.json"), _SPLIT_JSON_TEMPLATE) is None


def test_check_partition_arithmetic_flags_a_missing_exclusions_field():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1"}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "split_arithmetic_exclusions" in offender


def test_check_partition_arithmetic_flags_a_non_list_exclusions_field():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1", "split_arithmetic_exclusions": "none"}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "must be an array" in offender


def test_check_partition_arithmetic_flags_a_non_string_exclusions_item():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1", "split_arithmetic_exclusions": [42]}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "must be an array" in offender


def test_check_partition_arithmetic_passes_when_figures_reconcile():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1", "split_arithmetic_exclusions": []}
    assert gate.check_partition_arithmetic(pathlib.Path("split.json"), data) is None


def test_check_partition_arithmetic_flags_the_pre_907_shape():
    # The exact defect this check exists to catch: one more listed fixture
    # than the declared figure, with no exclusion accounting for it.
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "1:2:1", "split_arithmetic_exclusions": []}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "declared train figure 1" in offender
    assert "2 unique train fixture(s)" in offender
    assert "with no exclusion here" in offender


def test_check_partition_arithmetic_accepts_a_declared_exclusion():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "1:2:1", "split_arithmetic_exclusions": ["b-train.yaml"]}
    assert gate.check_partition_arithmetic(pathlib.Path("split.json"), data) is None


def test_check_partition_arithmetic_names_the_exclusion_in_a_still_failing_split():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1", "split_arithmetic_exclusions": ["b-train.yaml"]}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "excluding b-train.yaml" in offender


def test_check_partition_arithmetic_flags_a_stale_exclusion():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:1", "split_arithmetic_exclusions": ["gone.yaml"]}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "does not list at all" in offender


def test_check_partition_arithmetic_flags_a_selection_mismatch():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:5:1", "split_arithmetic_exclusions": []}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "declared selection figure 5" in offender


def test_check_partition_arithmetic_flags_a_test_mismatch():
    data = {**_SPLIT_JSON_TEMPLATE, "partition": "2:2:9", "split_arithmetic_exclusions": []}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "declared test figure 9" in offender


def test_check_partition_arithmetic_flags_a_declared_partition_with_nothing_listed():
    # `0:0:0` against an absent listing otherwise reconciles perfectly.
    data: dict[str, object] = {"assignment": {}, "partition": "0:0:0", "split_arithmetic_exclusions": []}
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "lists no fixture at all" in offender


def test_check_partition_arithmetic_flags_a_cross_split_mention():
    # A fixture named in more than one split is unfixable by exclusion:
    # waiving it to satisfy one split breaks the split that owns it.
    data = {
        "assignment": {
            "train": ["a-train.yaml", "b-train.yaml"],
            "selection": ["edge.yaml", "c-selection.yaml"],
            "test": ["d-test.yaml", "b-train.yaml"],
        },
        "partition": "2:2:1",
        "split_arithmetic_exclusions": [],
    }
    offender = gate.check_partition_arithmetic(pathlib.Path("split.json"), data)
    assert offender is not None
    assert "more than one split" in offender
    assert "b-train.yaml (in train and test)" in offender


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_when_clean(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(
        _split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8"
    )
    _write_split_json(tmp_path)
    assert gate.main(["--split-md", str(split_md)]) == 0


def test_main_returns_one_when_offender_found(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8")
    _write_split_json(tmp_path)
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_one_when_split_md_unreadable(tmp_path: pathlib.Path):
    missing = tmp_path / "does-not-exist.md"
    assert gate.main(["--split-md", str(missing)]) == 1


def test_main_returns_one_when_split_md_undecodable(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_bytes(b"\xff\xfe bad")
    _write_split_json(tmp_path)
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_one_when_sibling_split_json_missing(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(
        _split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8"
    )
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_zero_with_no_files():
    assert gate.main([]) == 0


def test_main_returns_one_when_skill_md_unreadable(tmp_path: pathlib.Path):
    missing = tmp_path / "does-not-exist" / "SKILL.md"
    assert gate.main(["--skill-md", str(missing)]) == 1


def test_main_reports_a_check_b_offender_via_skill_md(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("Step 4 takes precedence over the fallback.\n", encoding="utf-8")
    _write_split_json(tmp_path / "evals" / "widget-polisher", assignment={"train": ["a.yaml"]})
    rc = gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)])
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "precedence" in stderr.lower()


def test_main_reports_sibling_split_json_load_error_via_skill_md_only(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(_ROUTING_SKILL_MD, encoding="utf-8")
    split_json = tmp_path / "evals" / "widget-polisher" / "split.json"
    split_json.parent.mkdir(parents=True)
    split_json.write_text("{not valid json", encoding="utf-8")
    rc = gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)])
    assert rc == 1


def _write_split_json_and_skill_md(
    tmp_path: pathlib.Path, skill_name: str, skill_md_body: str, fixtures: dict, selection: list[str]
):
    skill_md = _write_skill_and_tasks(tmp_path, skill_name, skill_md_body, fixtures)
    _write_split_json(tmp_path / "evals" / skill_name, assignment={"selection": selection})
    split_json = tmp_path / "evals" / skill_name / "split.json"
    return skill_md, split_json


def test_main_check_c_fires_on_skill_md_only_diff(tmp_path: pathlib.Path):
    # Regression (adversarial review, issue #631): the calling workflow
    # populates --split-md/--skill-md independently based on which file
    # type actually changed in a PR's diff -- a SKILL.md-only diff (e.g.
    # renaming a ###-level section, with no split.md/split.json edit in
    # the same PR) must still run Check C via the sibling split.json, not
    # silently skip it because --split-md was never passed.
    skill_md, _split_json = _write_split_json_and_skill_md(
        tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {}, ["a.yaml"]
    )
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 1


def test_main_check_c_passes_on_skill_md_only_diff_with_valid_declaration(tmp_path: pathlib.Path):
    skill_md, _split_json = _write_split_json_and_skill_md(
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
    skill_md, _split_json = _write_split_json_and_skill_md(
        tmp_path, "widget-polisher", _ROUTING_SKILL_MD, {}, ["a.yaml"]
    )
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.write_text("# Held-out split\n\nSee split.json.\n", encoding="utf-8")
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


def test_split_json_read_once_when_split_md_and_skill_md_touch_the_same_skill(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # issue #1013 row 8: check_precedence_branch_coverage (Check B) must not
    # independently re-read a split.json the --split-md loop already read
    # this run. Proven by counting real load_split_json calls, not just by
    # asserting the (already-covered-elsewhere) result is correct.
    skill_md, split_json = _write_split_json_and_skill_md(
        tmp_path, "widget-polisher", "Step 4 takes precedence over the fallback.\n", {}, ["a.yaml"]
    )
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.write_text(_split_md("| a.yaml | 1 | 2 |\n"), encoding="utf-8")

    calls: list[pathlib.Path] = []
    real_load_split_json = gate.load_split_json

    def counting_load_split_json(path: pathlib.Path) -> tuple[dict[str, object] | None, str | None]:
        calls.append(path)
        return real_load_split_json(path)

    monkeypatch.setattr(gate, "load_split_json", counting_load_split_json)
    gate.main(["--split-md", str(split_md), "--skill-md", str(skill_md), "--repo-root", str(tmp_path)])
    assert calls.count(split_json) == 1, calls


def test_main_check_c_absent_when_sibling_split_json_missing(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(_ROUTING_SKILL_MD, encoding="utf-8")
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 0


def test_main_reports_a_check_d_partition_offender(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]):
    # Drives Check D through main(), so the offender-collection path there
    # is exercised and not only check_partition_arithmetic in isolation.
    split_md = tmp_path / "evals" / "widget-polisher" / "split.md"
    split_md.parent.mkdir(parents=True)
    split_md.write_text("# Held-out split\n\nSee split.json.\n", encoding="utf-8")
    _write_split_json(
        tmp_path / "evals" / "widget-polisher",
        partition="1:2:1",
        split_arithmetic_exclusions=[],
    )
    rc = gate.main(["--split-md", str(split_md), "--repo-root", str(tmp_path)])
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "declared train figure 1" in stderr


# ---------------------------------------------------------------------------
# Self-validation against this repository's real split.json/split.md/
# SKILL.md files. These double as a drift check: a future edit that
# reintroduces the #191/#352/#631/#907 gap shape into real, shipped content
# fails here.
# ---------------------------------------------------------------------------

_REAL_SPLIT_JSON_FILES = sorted((REPO_ROOT / "evals").glob("*/split.json"))
_REAL_SPLIT_MD_FILES = sorted((REPO_ROOT / "evals").glob("*/split.md"))
_REAL_SKILL_MD_FILES = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))


def test_every_real_split_md_passes_check_a():
    assert _REAL_SPLIT_MD_FILES, "expected at least one real evals/*/split.md file"
    for path in _REAL_SPLIT_MD_FILES:
        data, error = gate.load_split_json(path.parent / "split.json")
        assert error is None, error
        declared_selection = gate.assignment_fixtures(data)["selection"]
        offender = gate.check_latest_gate_table_coverage(
            path,
            path.read_text(encoding="utf-8"),
            declared_selection,
            assignment_present=isinstance(data.get("assignment"), dict),
        )
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


def test_every_real_split_json_passes_check_c():
    assert _REAL_SPLIT_JSON_FILES, "expected at least one real evals/*/split.json file"
    for path in _REAL_SPLIT_JSON_FILES:
        data, error = gate.load_split_json(path)
        assert error is None, error
        offender = gate.check_exercises_declaration_coverage(path, data, REPO_ROOT)
        assert offender is None, offender


def test_every_real_split_json_passes_check_d():
    assert _REAL_SPLIT_JSON_FILES, "expected at least one real evals/*/split.json file"
    for path in _REAL_SPLIT_JSON_FILES:
        data, error = gate.load_split_json(path)
        assert error is None, error
        offender = gate.check_partition_arithmetic(path, data)
        assert offender is None, offender


def test_real_split_json_partition_declarations_are_pinned_exactly():
    # Pins WHICH real files Check D actually grades, so the self-validation
    # test above can never go quietly vacuous. A new declaration (or a
    # changed existing one) fails here on purpose.
    declared = {}
    for path in _REAL_SPLIT_JSON_FILES:
        data, error = gate.load_split_json(path)
        assert error is None, error
        declared[path.parent.name] = gate.parse_declared_partition(data)
    assert declared == {
        "battle-testing-a-skill": None,
        "evaluating-skill-quality": (31, 36, 14),
        "explaining-the-work": (3, 2, 9),
        "merge-retrospective": (10, 6, 4),
        "scorer-gated-skill-edits": None,
    }


def test_real_split_json_arithmetic_exclusions_are_pinned_exactly():
    # Same anti-vacuity discipline for the exclusion side: every file Check
    # D grades must carry a well-formed field, and what it waives is pinned
    # rather than left to drift.
    exclusions = {}
    for path in _REAL_SPLIT_JSON_FILES:
        data, error = gate.load_split_json(path)
        assert error is None, error
        if gate.parse_declared_partition(data) is None:
            continue
        exclusions[path.parent.name] = set(data.get("split_arithmetic_exclusions") or [])
    assert exclusions == {
        "evaluating-skill-quality": {"dispatch-required-negative-control.yaml"},
        "explaining-the-work": set(),
        "merge-retrospective": set(),
    }


def test_real_split_json_files_all_parse_and_have_an_assignment():
    assert _REAL_SPLIT_JSON_FILES, "expected at least one real evals/*/split.json file"
    for path in _REAL_SPLIT_JSON_FILES:
        data, error = gate.load_split_json(path)
        assert error is None, error
        assert isinstance(data.get("assignment"), dict), path


def test_main_passes_against_every_real_split_md_and_skill_md_file():
    # Drives the full main() CLI against the real repository tree, the
    # same shape the CI workflow invokes it with.
    rc = gate.main(
        [
            "--split-md",
            *[str(p) for p in _REAL_SPLIT_MD_FILES],
            "--skill-md",
            *[str(p) for p in _REAL_SKILL_MD_FILES],
            "--repo-root",
            str(REPO_ROOT),
        ]
    )
    assert rc == 0

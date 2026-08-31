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
# Check E (issue #192 item 6, Refs #49 repair 1, #115 repair 1):
# Procedure/Steps item + Stop-boundary bullet exercises-label resolution
# ---------------------------------------------------------------------------

_PROCEDURE_STOP_BOUNDARY_SKILL_MD = (
    "## Procedure\n\n"
    "1. **Reproduce.** Attempt the reported repro steps.\n"
    "2. **Dedupe.** Search for likely duplicates.\n"
    "3. **Label.** Apply the repo's existing issue-type labels.\n\n"
    "## Stop boundaries\n\n"
    "- Never skip step 2 under time pressure.\n"
    "- Never label content before dedupe completes.\n"
)

_PROCEDURE_ITEMS = [
    "**Reproduce.** Attempt the reported repro steps.",
    "**Dedupe.** Search for likely duplicates.",
    "**Label.** Apply the repo's existing issue-type labels.",
]


def test_parse_procedure_steps_extracts_ordered_items():
    assert gate.parse_procedure_steps(_PROCEDURE_STOP_BOUNDARY_SKILL_MD) == _PROCEDURE_ITEMS


def test_parse_procedure_steps_recognizes_steps_heading_too():
    text = "## Steps\n\n1. First.\n2. Second.\n"
    assert gate.parse_procedure_steps(text) == ["First.", "Second."]


def test_parse_procedure_steps_empty_when_no_heading():
    assert gate.parse_procedure_steps("No procedure heading here.\n1. Not counted.\n") == []


def test_parse_procedure_steps_stops_at_next_heading():
    text = "## Procedure\n\n1. Only this one.\n\n## Notes\n\n2. Not a procedure item.\n"
    assert gate.parse_procedure_steps(text) == ["Only this one."]


def test_stop_boundary_identity_counter_matches_49_gate_convention():
    # Mirrors gitapex_gate_skill_branch_fixture_coverage.py's own
    # stop_boundary_bullet_counter -- same key shape ("stop-boundary:<full
    # bullet line, marker included>"), so the two gates agree on identity.
    counter = gate.stop_boundary_identity_counter(_PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert counter["stop-boundary:- Never skip step 2 under time pressure."] == 1
    assert counter["stop-boundary:- Never label content before dedupe completes."] == 1
    assert sum(counter.values()) == 2


def test_normalize_for_span_scan_splits_lines_and_blanks_fences():
    text = "a\n```\nsecret\n```\nb"
    assert gate._normalize_for_span_scan(text) == ["a", "", "", "", "b"]


def test_normalize_for_span_scan_normalizes_crlf():
    assert gate._normalize_for_span_scan("a\r\nb\r\n") == ["a", "b", ""]


def test_procedure_step_identity_counter_keys_on_content_not_position():
    counter = gate.procedure_step_identity_counter(_PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert counter[f"procedure-step:{_PROCEDURE_ITEMS[0]}"] == 1
    assert sum(counter.values()) == len(_PROCEDURE_ITEMS)


def test_procedure_step_identity_counter_empty_with_no_heading():
    assert gate.procedure_step_identity_counter("No procedure heading here.\n1. Not counted.\n") == {}


def test_stop_boundary_bullet_label_strips_marker_and_casefolds():
    assert gate._stop_boundary_bullet_label("stop-boundary:- Never Skip Step 2.") == "never skip step 2."


def test_resolvable_exercise_labels_step_ordinal():
    labels = gate.resolvable_exercise_labels(_PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert "step 1" in labels
    assert "step 3" in labels
    assert "step 4" not in labels


def test_resolvable_exercise_labels_literal_procedure_item_text():
    labels = gate.resolvable_exercise_labels(_PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert "**dedupe.** search for likely duplicates.".casefold() in labels


def test_resolvable_exercise_labels_stop_boundary_bullet_text_marker_stripped():
    labels = gate.resolvable_exercise_labels(_PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert "never skip step 2 under time pressure." in labels


def test_resolvable_exercise_labels_includes_section_headings_too():
    # explaining-the-work's own real shape: ### headings AND a Stop
    # boundaries heading coexist -- the union must include both kinds.
    text = _ROUTING_SKILL_MD + "\n## Stop boundaries\n\n- A bullet.\n"
    labels = gate.resolvable_exercise_labels(text)
    assert "commit log" in labels
    assert "a bullet." in labels


def test_resolvable_exercise_labels_empty_when_no_convention_used():
    assert gate.resolvable_exercise_labels("No headings or lists here.\n") == set()


def test_procedure_stop_boundary_coverage_none_when_no_convention(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", "Nothing here.\n", {})
    offender = gate.check_procedure_stop_boundary_exercises_coverage(skill_md, "Nothing here.\n", tmp_path)
    assert offender is None


def test_procedure_stop_boundary_coverage_passes_untouched_with_no_exercises_field(tmp_path: pathlib.Path):
    # No-retrofit: a fixture with no exercises field at all is never
    # required to add one.
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  output_contains:\n    - "x"\n'},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_procedure_stop_boundary_coverage_resolves_via_step_ordinal(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Step 2"\n'},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_procedure_stop_boundary_coverage_resolves_via_literal_procedure_item_text(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "**Dedupe.** Search for likely duplicates."\n'},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_procedure_stop_boundary_coverage_resolves_via_stop_boundary_bullet_text(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Never skip step 2 under time pressure."\n'},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_procedure_stop_boundary_coverage_fails_when_label_resolves_to_nothing(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Nonexistent step"\n'},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is not None
    assert "a.yaml" in offender
    assert "Nonexistent step" in offender


def test_procedure_stop_boundary_coverage_fails_on_malformed_declaration(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": "expected:\n  exercises: true\n"},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is not None
    assert "no well-formed exercises declaration" in offender


def test_procedure_stop_boundary_coverage_fails_loudly_on_unparseable_yaml(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": "expected:\n  exercises: [\n"},
    )
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is not None
    assert "could not parse YAML" in offender


def test_procedure_stop_boundary_coverage_skips_directory_named_like_a_fixture(tmp_path: pathlib.Path):
    # Regression (issue #192 step 8 adversarial review, live-reproduced):
    # a directory named `*.yaml` under tasks/ (e.g. a stray checkout
    # artifact) matches the `tasks_dir.glob("*.yaml")` scan but is not a
    # readable fixture file -- read_text on it raises IsADirectoryError.
    # This must be skipped, not crash the gate.
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    (tmp_path / "evals" / "widget-polisher" / "tasks" / "evil.yaml").mkdir()
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_procedure_stop_boundary_coverage_none_when_no_tasks_dir(tmp_path: pathlib.Path):
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, encoding="utf-8")
    offender = gate.check_procedure_stop_boundary_exercises_coverage(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_new_procedure_stop_boundary_content_empty_when_unchanged():
    assert (
        gate.new_procedure_stop_boundary_content(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, _PROCEDURE_STOP_BOUNDARY_SKILL_MD)
        == []
    )


def test_new_procedure_stop_boundary_content_detects_new_stop_boundary_bullet():
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    new_content = gate.new_procedure_stop_boundary_content(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, after)
    assert new_content == ["stop-boundary:- A brand new boundary."]


def test_new_procedure_stop_boundary_content_detects_new_procedure_item():
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD.replace("3. **Label.**", "3. **Triage.** A new item.\n4. **Label.**")
    new_content = gate.new_procedure_stop_boundary_content(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, after)
    assert "procedure-step:**Triage.** A new item." in new_content


def test_new_procedure_stop_boundary_content_brand_new_file_counts_everything():
    new_content = gate.new_procedure_stop_boundary_content(None, _PROCEDURE_STOP_BOUNDARY_SKILL_MD)
    assert len(new_content) == 5  # 3 procedure items + 2 stop-boundary bullets


def test_new_procedure_stop_boundary_content_renumbering_alone_is_not_new():
    # Content-keyed, not positional: reordering the same three items must
    # not register any of them as new.
    after = (
        "## Procedure\n\n"
        "1. **Dedupe.** Search for likely duplicates.\n"
        "2. **Reproduce.** Attempt the reported repro steps.\n"
        "3. **Label.** Apply the repo's existing issue-type labels.\n\n"
        "## Stop boundaries\n\n"
        "- Never skip step 2 under time pressure.\n"
        "- Never label content before dedupe completes.\n"
    )
    assert gate.new_procedure_stop_boundary_content(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, after) == []


def test_fixture_demand_fails_when_new_bullet_has_no_covering_fixture(tmp_path: pathlib.Path):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", after, {})
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is not None
    assert "A brand new boundary." in offender


def test_fixture_demand_passes_when_new_bullet_has_a_covering_fixture(tmp_path: pathlib.Path):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        after,
        {"a.yaml": 'expected:\n  exercises:\n    - "A brand new boundary."\n'},
    )
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is None


def test_fixture_demand_passes_when_new_procedure_item_covered_by_step_ordinal(tmp_path: pathlib.Path):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD.replace("3. **Label.**", "3. **Triage.** A new item.\n4. **Label.**")
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        after,
        {"a.yaml": 'expected:\n  exercises:\n    - "Step 3"\n'},
    )
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is None


def test_fixture_demand_never_retroactively_flags_a_preexisting_gap(tmp_path: pathlib.Path):
    # A skill whose Stop-boundary count already exceeded its fixture
    # coverage before this diff, with no relevant content change in this
    # diff, is never retroactively flagged -- which is also the
    # "nothing new in this diff, so nothing to demand" guard's own case
    # (`new_procedure_stop_boundary_content` returns []).
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is None


def test_fixture_demand_brand_new_skill_md_requires_coverage(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, None, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, tmp_path
    )
    assert offender is not None


def test_fixture_demand_uncovered_when_no_tasks_dir_at_all(tmp_path: pathlib.Path):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = tmp_path / "skills" / "widget-polisher" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(after, encoding="utf-8")
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is not None
    assert "A brand new boundary." in offender


def test_fixture_demand_skips_an_unparseable_fixture_when_scanning_for_coverage(tmp_path: pathlib.Path):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        after,
        {"a.yaml": "expected:\n  exercises: [\n"},
    )
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is not None
    assert "A brand new boundary." in offender


def test_fixture_demand_skips_directory_named_like_a_fixture(tmp_path: pathlib.Path):
    # Regression (issue #192 step 8 adversarial review, live-reproduced):
    # same IsADirectoryError guard as
    # test_procedure_stop_boundary_coverage_skips_directory_named_like_a_fixture,
    # for this function's own separate tasks_dir.glob("*.yaml") scan.
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", after, {})
    (tmp_path / "evals" / "widget-polisher" / "tasks" / "evil.yaml").mkdir()
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is not None
    assert "A brand new boundary." in offender


def test_fixture_demand_skips_a_malformed_exercises_declaration_when_scanning_for_coverage(
    tmp_path: pathlib.Path,
):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        after,
        {"a.yaml": "expected:\n  exercises: true\n"},
    )
    offender = gate.check_new_procedure_stop_boundary_fixture_demand(
        skill_md, _PROCEDURE_STOP_BOUNDARY_SKILL_MD, after, tmp_path
    )
    assert offender is not None
    assert "A brand new boundary." in offender


def test_main_wires_check_e_absolute_resolution(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        _PROCEDURE_STOP_BOUNDARY_SKILL_MD,
        {"a.yaml": 'expected:\n  exercises:\n    - "Nonexistent step"\n'},
    )
    rc = gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)])
    assert rc == 1


def test_main_skips_delta_demand_without_before_map(tmp_path: pathlib.Path):
    # Omitting --skill-md-before-map must skip the delta-scoped demand
    # check entirely (Check E's absolute resolution check still runs).
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", after, {})
    rc = gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)])
    assert rc == 0


def test_main_wires_check_e_delta_demand_via_before_map(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]):
    after = _PROCEDURE_STOP_BOUNDARY_SKILL_MD + "- A brand new boundary.\n"
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", after, {})
    before_file = tmp_path / "before.md"
    before_file.write_text(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, encoding="utf-8")
    before_map_file = tmp_path / "before_map.tsv"
    before_map_file.write_text(f"{skill_md}\t{before_file}\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "A brand new boundary." in stderr


def test_main_before_map_new_file_treated_as_brand_new(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_map_file.write_text(f"{skill_md}\t\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_main_before_map_ignores_a_blank_line(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_map_file.write_text(f"\n{skill_md}\t\n\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_main_processes_a_second_skill_md_after_a_clean_delta_demand(tmp_path: pathlib.Path):
    # Regression: the offender-collection loop must continue to a second
    # --skill-md file after the delta-demand check for the first finds
    # nothing new, not stop short. Both skill_md_1 and skill_md_2's own
    # delta-demand checks see no change (before == after for each) --
    # every --skill-md file carries its own before-map entry, required
    # since the self-revalidation fix that fails closed when a supplied
    # before-map is missing an entry for one of the --skill-md paths.
    # rc == 0 confirms the loop actually reached and finished processing
    # skill_md_2 rather than silently stopping after skill_md_1.
    skill_md_1 = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    skill_md_2 = _write_skill_and_tasks(tmp_path, "second-widget", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_1 = tmp_path / "before_1.md"
    before_1.write_text(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, encoding="utf-8")
    before_2 = tmp_path / "before_2.md"
    before_2.write_text(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, encoding="utf-8")
    before_map_file.write_text(f"{skill_md_1}\t{before_1}\n{skill_md_2}\t{before_2}\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md_1),
            str(skill_md_2),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0


def test_main_before_map_malformed_line_fails_closed(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_map_file.write_text("not-a-well-formed-line\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_main_before_map_missing_file_fails_closed(tmp_path: pathlib.Path):
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(tmp_path / "nonexistent.tsv"),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_main_before_map_missing_entry_for_skill_md_fails_closed(tmp_path: pathlib.Path):
    # Self-revalidation regression (issue #192 step 8 adversarial review):
    # once --skill-md-before-map is supplied at all, every --skill-md path
    # must have its own entry. Silently skipping the delta-demand check for
    # a --skill-md file the map forgot to cover would mask exactly the kind
    # of workflow/gate drift Check E exists to catch elsewhere -- so a
    # missing entry must fail closed (rc == 1) with a clear error, never
    # pass through as though the demand check ran and found nothing.
    skill_md_1 = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    skill_md_2 = _write_skill_and_tasks(tmp_path, "second-widget", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_1 = tmp_path / "before_1.md"
    before_1.write_text(_PROCEDURE_STOP_BOUNDARY_SKILL_MD, encoding="utf-8")
    # Only skill_md_1 gets an entry; skill_md_2 is the missing one.
    before_map_file.write_text(f"{skill_md_1}\t{before_1}\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md_1),
            str(skill_md_2),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_no_real_skill_md_newly_fails_check_e_absolute_resolution():
    # Regression: none of the 467 pre-existing task files across every
    # real skill are retroactively required to add an exercises
    # declaration, and every one that already declares it still resolves.
    for path in _REAL_SKILL_MD_FILES:
        offender = gate.check_procedure_stop_boundary_exercises_coverage(
            path, path.read_text(encoding="utf-8"), REPO_ROOT
        )
        assert offender is None, offender


# ---------------------------------------------------------------------------
# Check E adversarial defeat cases (issue #192 step 8 review)
#
# Each case below was constructed specifically to defeat Check E's own
# detection logic, confirmed to actually do so against the shipped
# revision, and is pinned here asserting the CORRECT outcome so a later
# edit that reintroduces the hole fails loudly instead of silently.
# ---------------------------------------------------------------------------


def test_step_ordinals_follow_the_lists_own_source_numbering():
    # Defeat case (confirmed to defeat the pre-fix revision): "Step N" was
    # resolved by a running 1..N index over the flattened item list, not
    # by the item's own written number. On a list starting at `0.` every
    # ordinal was off by one -- "Step 0" resolved against nothing, a
    # non-existent "Step 4" resolved successfully, and "Step 1" silently
    # pointed at the item numbered `0.`.
    text = "## Procedure\n\n0. Zeroth.\n1. First.\n2. Second.\n3. Third.\n"
    assert gate.parse_procedure_step_items(text) == [
        (0, "Zeroth."),
        (1, "First."),
        (2, "Second."),
        (3, "Third."),
    ]
    labels = gate.resolvable_exercise_labels(text)
    assert "step 0" in labels
    assert "step 3" in labels
    assert "step 4" not in labels


def test_real_skill_md_with_a_step_zero_resolves_step_zero_not_step_seven():
    # The same defeat case against real, shipped content rather than a
    # synthetic fixture: reviewing-an-artifact/SKILL.md numbers its
    # Procedure `0.`..`6.` (its own frontmatter says "the eight Step 0
    # deferral targets"), so "Step 0" must resolve and "Step 7" must not.
    path = REPO_ROOT / "skills" / "reviewing-an-artifact" / "SKILL.md"
    assert path.is_file(), path
    labels = gate.resolvable_exercise_labels(path.read_text(encoding="utf-8"))
    assert "step 0" in labels
    assert "step 6" in labels
    assert "step 7" not in labels


def test_step_ordinals_are_not_flattened_across_two_procedure_headings():
    # Same root cause, second symptom: a running index accumulated across
    # every Procedure/Steps heading in the file, so a 2-item Procedure
    # followed by a 2-item Steps section made "Step 3"/"Step 4" resolve
    # against the second section's own items 1 and 2.
    text = "## Procedure\n\n1. Alpha.\n2. Beta.\n\n## Notes\n\nprose\n\n## Steps\n\n1. Gamma.\n2. Delta.\n"
    labels = gate.resolvable_exercise_labels(text)
    assert "step 1" in labels
    assert "step 2" in labels
    assert "step 3" not in labels
    assert "step 4" not in labels
    # The literal-text targets are unaffected -- both sections contribute.
    assert "gamma." in labels
    assert "delta." in labels


def test_procedure_steps_heading_does_not_over_match_an_unrelated_heading():
    # Regression (issue #192 step 8 adversarial review, live-reproduced):
    # `_PROCEDURE_STEPS_HEADING_RE` used to match any heading merely
    # STARTING with "Procedure"/"Steps" (a `\b`-anchored, not
    # `$`-anchored, pattern) -- e.g. the real heading
    # "## Steps 2-3 -- a secret reachable only through history" in
    # skills/scanning-leaked-secrets/references/worked-examples.md:344.
    # Numbered items under such an unrelated heading must not be read as
    # Procedure/Steps items; a genuine "## Steps" heading elsewhere in
    # the same file still resolves normally.
    text = (
        "## Steps 2-3 -- a secret reachable only through history\n\n"
        "1. Not a real step.\n2. Also not a real step.\n\n"
        "## Steps\n\n1. Alpha.\n2. Beta.\n"
    )
    assert gate.parse_procedure_step_items(text) == [(1, "Alpha."), (2, "Beta.")]
    labels = gate.resolvable_exercise_labels(text)
    assert "step 1" in labels
    assert "step 2" in labels
    assert "not a real step." not in labels
    assert "also not a real step." not in labels


def test_check_c_and_check_e_accept_the_same_exercises_vocabulary(tmp_path: pathlib.Path):
    # Defeat case (confirmed to defeat the pre-fix revision): Check C
    # resolved a selection fixture's labels against `###` headings ALONE
    # while Check E advertised Step-N/Procedure-item/Stop-boundary targets
    # as legal, so one fixture declaring "Step 2" passed Check E and was
    # simultaneously failed by Check C -- and Check E's delta demand could
    # ask for a label Check C would then reject.
    body = _ROUTING_SKILL_MD + _PROCEDURE_STOP_BOUNDARY_SKILL_MD
    skill_md = _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        body,
        {"a.yaml": 'expected:\n  exercises:\n    - "Step 2"\n    - "Never skip step 2 under time pressure."\n'},
    )
    split_json = tmp_path / "evals" / "widget-polisher" / "split.json"
    split_json.write_text(json.dumps({"assignment": {"selection": ["a.yaml"]}}), encoding="utf-8")
    data, error = gate.load_split_json(split_json)
    assert error is None, error
    assert data is not None
    assert gate.check_exercises_declaration_coverage(split_json, data, tmp_path) is None
    assert gate.check_procedure_stop_boundary_exercises_coverage(skill_md, body, tmp_path) is None
    assert gate.main(["--skill-md", str(skill_md), "--repo-root", str(tmp_path)]) == 0


def test_check_c_still_rejects_a_label_resolving_to_nothing_after_the_widening(tmp_path: pathlib.Path):
    # The counterpart guard for the widening above: Check C's own purpose
    # (issue #631 -- a declared label is never resolved by staleness) must
    # survive it. A label matching none of the widened target kinds still
    # fails.
    body = _ROUTING_SKILL_MD + _PROCEDURE_STOP_BOUNDARY_SKILL_MD
    _write_skill_and_tasks(
        tmp_path,
        "widget-polisher",
        body,
        {"a.yaml": 'expected:\n  exercises:\n    - "Step 9"\n'},
    )
    split_json = tmp_path / "evals" / "widget-polisher" / "split.json"
    split_json.write_text(json.dumps({"assignment": {"selection": ["a.yaml"]}}), encoding="utf-8")
    data, error = gate.load_split_json(split_json)
    assert error is None, error
    assert data is not None
    offender = gate.check_exercises_declaration_coverage(split_json, data, tmp_path)
    assert offender is not None
    assert "Step 9" in offender


def test_same_count_stop_boundary_and_procedure_content_swap_registers_as_new():
    # The exact defeat class gitapex_gate_skill_branch_fixture_coverage.py's
    # own module docstring names as the reason it keys Counters on content
    # instead of bare totals: deleting N bullets/items and adding N
    # DIFFERENT ones leaves the totals equal, so a bare-total comparison
    # would see no change at all. Content keying must still report every
    # swapped-in item as new.
    before = "## Stop boundaries\n\n- A.\n- B.\n- C.\n\n## Procedure\n\n1. P1.\n2. P2.\n"
    after = "## Stop boundaries\n\n- X.\n- Y.\n- Z.\n\n## Procedure\n\n1. Q1.\n2. Q2.\n"
    assert gate.new_procedure_stop_boundary_content(before, after) == [
        "procedure-step:Q1.",
        "procedure-step:Q2.",
        "stop-boundary:- X.",
        "stop-boundary:- Y.",
        "stop-boundary:- Z.",
    ]
    # A pure reorder of the same content is NOT new (position-independent
    # identity), and a duplicated bullet is caught by the multiset, not
    # collapsed by a set.
    reordered = "## Stop boundaries\n\n- C.\n- B.\n- A.\n\n## Procedure\n\n1. P2.\n2. P1.\n"
    assert gate.new_procedure_stop_boundary_content(before, reordered) == []
    assert gate.new_procedure_stop_boundary_content(
        "## Stop boundaries\n\n- A.\n", "## Stop boundaries\n\n- A.\n- A.\n"
    ) == ["stop-boundary:- A."]


def test_main_warns_on_unreadable_before_content_instead_of_swallowing_it(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
):
    # An unreadable before-file fails CLOSED (every item counts as new),
    # but silently: the resulting whole-file coverage demand was
    # inexplicable from the job log. Every sibling error path in main()
    # already prints; this one must too.
    skill_md = _write_skill_and_tasks(tmp_path, "widget-polisher", _PROCEDURE_STOP_BOUNDARY_SKILL_MD, {})
    before_map_file = tmp_path / "before_map.tsv"
    before_map_file.write_text(f"{skill_md}\t{tmp_path / 'gone.md'}\n", encoding="utf-8")
    rc = gate.main(
        [
            "--skill-md",
            str(skill_md),
            "--skill-md-before-map",
            str(before_map_file),
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 1
    stderr = capsys.readouterr().err
    assert "warning: could not read before-content" in stderr
    assert "treating as newly added" in stderr


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
        "evaluating-skill-quality": (35, 41, 18),
        "explaining-the-work": (3, 2, 9),
        "merge-retrospective": (11, 7, 5),
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

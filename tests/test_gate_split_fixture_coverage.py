"""Tests for the split.md fixture-table coverage gate
(.github/scripts/gate_split_fixture_coverage.py).

Issue #526, unifying two proposed gates from retrospective issues #191
(repair 1: a gate-result table must cover every declared `selection`
fixture) and #352 (repair 3: a SKILL.md precedence/branching rule must
have a train+held-out equivalence-class pair in its split.md).

No test in this file makes a network call. The self-validation tests at
the bottom run the real gate against this repository's own four
`split.md` files and SKILL.md files, doubling as a drift check: if a
future edit to any of them silently reintroduces the #191/#352 gap shape,
these tests fail here before the CI gate would even need to run.
"""

from __future__ import annotations

import pathlib

import gate_split_fixture_coverage as gate

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
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_when_clean(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n| `c-selection.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8")
    assert gate.main(["--split-md", str(split_md)]) == 0


def test_main_returns_one_when_offender_found(tmp_path: pathlib.Path):
    split_md = tmp_path / "split.md"
    split_md.write_text(_split_md("| `edge.yaml` | 1.0 | 1.0 |\n"), encoding="utf-8")
    assert gate.main(["--split-md", str(split_md)]) == 1


def test_main_returns_one_when_split_md_unreadable(tmp_path: pathlib.Path):
    missing = tmp_path / "does-not-exist.md"
    assert gate.main(["--split-md", str(missing)]) == 1


def test_main_returns_zero_with_no_files():
    assert gate.main([]) == 0


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

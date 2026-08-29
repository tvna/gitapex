"""Tests for gitapex_file_gate_proposal.py (Task B, design doc Component 2:
docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md).

No test in this file makes a network call or a GitHub API call -- the
module under test is pure and network-free by construction, so nothing
here needs to mock one.

The ACM-compatibility test below imports
`hooks/gitapex_check_acm_present_or_waiver.py`'s own `has_acm_disclosure`
directly via `importlib`, loading it by file path rather than adding
`hooks` to this test's own import path: `skills/merge-retrospective/scripts`
is not one of `[tool.pytest.ini_options]`'s `pythonpath` entries in
pyproject.toml (unlike `hooks` itself, which is), so a bare
`import gitapex_check_acm_present_or_waiver` here would depend on pytest's
own config-discovery behavior rather than being guaranteed to resolve --
loading by file path sidesteps that entirely and keeps this test correct
regardless of how pytest is invoked.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

import gitapex_file_gate_proposal as builder
import pytest


def _load_acm_checker() -> types.ModuleType:
    """Load hooks/gitapex_check_acm_present_or_waiver.py by file path (see
    module docstring for why this avoids relying on pytest's pythonpath)."""
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    module_path = repo_root / "hooks" / "gitapex_check_acm_present_or_waiver.py"
    spec = importlib.util.spec_from_file_location("gitapex_check_acm_present_or_waiver", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# GATE_PROPOSAL_LABEL
# ---------------------------------------------------------------------------


def test_gate_proposal_label_is_the_exact_literal() -> None:
    # This exact literal is load-bearing: Task C's own copy in
    # .github/scripts/gitapex_scan_retrospective_gate_drift.py and Task D's
    # sync test both depend on it being precisely "gate-proposal".
    assert builder.GATE_PROPOSAL_LABEL == "gate-proposal"


# ---------------------------------------------------------------------------
# build_gate_proposal_title
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("retro_number", "index", "label", "expected"),
    [
        (1405, 2, "Failed CI rerun", "gate-proposal: retro #1405 repair 2: Failed CI rerun"),
        (42, 1, "Review fix round", "gate-proposal: retro #42 repair 1: Review fix round"),
    ],
)
def test_build_title_concatenates_literal_pieces_in_order(
    retro_number: int, index: int, label: str, expected: str
) -> None:
    title = builder.build_gate_proposal_title(
        retrospective_issue_number=retro_number,
        repair_index=index,
        repair_label=label,
    )
    assert title == expected


# 0 is the off-by-one a 0-based in-memory index pass would produce; a
# negative index is the same contract violation from the other side.
@pytest.mark.parametrize("repair_index", [0, -1])
def test_build_title_rejects_non_positive_index(repair_index: int) -> None:
    with pytest.raises(ValueError, match="1-based"):
        builder.build_gate_proposal_title(retrospective_issue_number=1405, repair_index=repair_index, repair_label="x")


# ---------------------------------------------------------------------------
# Defeat test (design doc Decision 1 / Testing section): same label,
# different index -> distinct titles. This is the specific silent-loss
# collision -- a second repair's search-before-create wrongly matching the
# first repair's own already-filed issue -- this whole indexing mechanism
# exists to prevent.
# ---------------------------------------------------------------------------


def test_defeat_identical_label_different_index_yields_distinct_titles() -> None:
    shared_label = "Failed CI rerun"
    first_title = builder.build_gate_proposal_title(
        retrospective_issue_number=1405, repair_index=1, repair_label=shared_label
    )
    second_title = builder.build_gate_proposal_title(
        retrospective_issue_number=1405, repair_index=2, repair_label=shared_label
    )
    assert first_title != second_title
    # Guard against a degenerate "always different" implementation
    # accidentally satisfying the assertion above for the wrong reason:
    # confirm the label text itself really is identical between the two.
    assert shared_label in first_title
    assert shared_label in second_title


# ---------------------------------------------------------------------------
# build_gate_proposal_acm_body
# ---------------------------------------------------------------------------


def test_build_acm_body_maps_repair_fields_per_decision_4() -> None:
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1405,
        repair_label="Failed CI rerun",
        classification_rationale="No pre-push hook caught the lint failure before push.",
        proposed_gate_text="Add a pre-push hook running the lint suite.",
        residual_risk="Hook can be bypassed with --no-verify.",
    )
    assert "Failed CI rerun" in body
    assert "No pre-push hook caught the lint failure before push." in body
    assert "Add a pre-push hook running the lint suite." in body
    assert (
        "implementing PR adds the check plus a regression test; confirm it "
        "fails against a reintroduced instance of the original defect, then passes" in body
    )
    assert "Hook can be bypassed with --no-verify." in body
    assert "Refs #1405" in body


def test_build_acm_body_puts_each_field_in_its_own_declared_column() -> None:
    # The test above asserts only that each value appears *somewhere* in
    # the body, which a swapped Interpretation/Planned-ops mapping would
    # still satisfy -- and a swap is silent, since both cells are free
    # prose. Decision 4 fixes the column order, so assert it by position.
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1405,
        repair_label="CRITERION",
        classification_rationale="INTERPRETATION",
        proposed_gate_text="PLANNED-OPS",
        residual_risk="RESIDUAL-RISK",
    )
    data_row = body.split("\n")[2]
    cells = [cell.strip() for cell in data_row.strip().strip("|").split("|")]
    assert cells[0] == "CRITERION"
    assert cells[1] == "INTERPRETATION"
    assert cells[2] == "PLANNED-OPS"
    assert cells[3] == builder._PROOF_METHOD
    assert cells[4] == "RESIDUAL-RISK"


def test_build_acm_body_defaults_residual_risk_when_none_named() -> None:
    body_from_none = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text="z",
        residual_risk=None,
    )
    body_from_blank = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text="z",
        residual_risk="   ",
    )
    assert "none identified" in body_from_none
    assert "none identified" in body_from_blank


def test_build_acm_body_refs_line_uses_retrospective_issue_number() -> None:
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=9999,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text="z",
        residual_risk="none",
    )
    assert "Refs #9999" in body


def _delimiter_pipe_count(row: str) -> int:
    """Count the pipes a Markdown renderer would treat as real column
    delimiters in `row`.

    Models Markdown's own escaping rule directly rather than approximating
    it with a `(?<!\\)\\|` lookbehind: a backslash escapes *whatever*
    character follows it, so `\\|` is a literal pipe (not a delimiter)
    while `\\\\|` is an escaped backslash followed by a live delimiter --
    a distinction the lookbehind gets exactly backwards, and precisely the
    case `_sanitize_cell`'s own backslash pass exists to prevent.
    """
    count = 0
    index = 0
    while index < len(row):
        if row[index] == "\\":
            index += 2
            continue
        if row[index] == "|":
            count += 1
        index += 1
    return count


def test_build_acm_body_sanitizes_pipe_and_newline_in_free_text_fields() -> None:
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="line one\nline two | still one cell",
        proposed_gate_text="z",
        residual_risk=None,
    )
    _header, _divider, data_row, _blank, _refs = body.split("\n")
    # The data row must stay exactly one line with exactly 6 real column
    # delimiters -- an embedded "|" left unescaped, or a literal newline,
    # would otherwise misalign the table when rendered.
    assert _delimiter_pipe_count(data_row) == 6
    assert "\\|" in data_row
    assert "\n" not in data_row


def test_build_acm_body_keeps_one_cell_when_free_text_already_contains_an_escaped_pipe() -> None:
    # Defeat case for the pipe-escaping pass: escaping "|" alone turns an
    # input that already reads "\|" -- a proposed gate naming a regex or a
    # `grep 'a\|b'` alternation, the realistic shape for a gate proposal --
    # into "\\|", an escaped backslash plus a live delimiter, silently
    # adding a seventh column and shifting every cell after it. The
    # backslash must be escaped first so the row keeps exactly 6.
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text=r"add a pre-commit grep for 'foo\|bar' in the changed files",
        residual_risk=None,
    )
    data_row = body.split("\n")[2]
    assert _delimiter_pipe_count(data_row) == 6


# ---------------------------------------------------------------------------
# ACM-disclosure hook compatibility (design doc Testing section): the
# produced body, run through hooks/gitapex_check_acm_present_or_waiver.py's
# own has_acm_disclosure, must pass.
# ---------------------------------------------------------------------------


def test_acm_body_satisfies_has_acm_disclosure() -> None:
    acm_checker = _load_acm_checker()
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1405,
        repair_label="Failed CI rerun",
        classification_rationale="No pre-push hook caught the lint failure before push.",
        proposed_gate_text="Add a pre-push hook running the lint suite.",
        residual_risk=None,
    )
    assert acm_checker.has_acm_disclosure(body) is True


def test_acm_body_header_row_matches_hook_header_regex_directly() -> None:
    acm_checker = _load_acm_checker()
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text="z",
        residual_risk="none",
    )
    header_row = body.split("\n", maxsplit=1)[0]
    assert acm_checker._HEADER_RE.search(header_row)

"""Tests for skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py
(design doc Component 2:
docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md, and
the per-family filing, recurrence-record and escalation helpers from issue
#2097).

No test in this file makes a network call or a GitHub API call -- the
module under test is pure and network-free by construction.

Lives under tests/ rather than beside the module (where it used to be)
because `skills/merge-retrospective/scripts` is not one of pyproject.toml's
`testpaths`, so a test there never ran in CI, and the function-body
coverage gate looks for `tests/test_<stem>.py`. Both modules are loaded
by file path, since neither directory is on this suite's `pythonpath`.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(relative: str, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py", "gitapex_file_gate_proposal")


def _load_acm_checker() -> types.ModuleType:
    return _load("hooks/gitapex_check_acm_present_or_waiver.py", "gitapex_check_acm_present_or_waiver")


def _sweep_kwargs(open_count: int = 63, timestamp: str = "2026-09-05T11:00:00Z") -> dict[str, Any]:
    return {"dedup_sweep_open_count": open_count, "dedup_sweep_timestamp": timestamp}


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
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
    )
    body_from_blank = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale="y",
        proposed_gate_text="z",
        residual_risk="   ",
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
    )
    data_row = body.split("\n")[2]
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
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
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
        **_sweep_kwargs(),
    )
    header_row = body.split("\n", maxsplit=1)[0]
    assert acm_checker._HEADER_RE.search(header_row)


# ---------------------------------------------------------------------------
# Dedup-sweep line (issue #1806): the Step 4b backlog-sweep proof line,
# generated only here, never hand-typed. Shape:
#   Dedup-sweep: <N> open gate-proposal issues at <ISO-8601>; verdict NEW
# ---------------------------------------------------------------------------


def test_build_dedup_sweep_line_emits_fixed_shape() -> None:
    line = builder.build_dedup_sweep_line(open_count=63, timestamp="2026-09-05T11:00:00Z")
    assert line == "Dedup-sweep: 63 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict NEW"


@pytest.mark.parametrize("open_count", [-1, True, "63", 6.0, None])
def test_build_dedup_sweep_line_rejects_non_integer_or_negative_count(open_count: object) -> None:
    with pytest.raises(ValueError, match="open_count"):
        builder.build_dedup_sweep_line(open_count=open_count, timestamp="2026-09-05T11:00:00Z")


@pytest.mark.parametrize(
    "timestamp",
    [
        "yesterday",
        "2026-09-05 11:00:00",
        "2026-09-05T11:00:00+09:00",
        "2026-09-05T11:00:00",
        "",
        "2026-13-99T99:99:99Z",
    ],
)
def test_build_dedup_sweep_line_rejects_malformed_timestamp(timestamp: str) -> None:
    with pytest.raises(ValueError, match=r"[Tt]imestamp"):
        builder.build_dedup_sweep_line(open_count=63, timestamp=timestamp)


@pytest.mark.parametrize(
    "verdict",
    [
        "RECLASSIFY needs clearer instruction",
        "ALREADY-SHIPPED foo",
        "new",
        "DUPLICATE-OF",
        "",
        # Issue #2097: a duplicate or absorbed repair records a recurrence
        # comment instead of creating an issue, so neither creates.
        "DUPLICATE-OF #1571",
        "ABSORBED-BY defeat-test-mutation-coverage",
        "NEW ",
        "NEW\n",
    ],
)
def test_build_dedup_sweep_line_rejects_non_filing_verdicts(verdict: str) -> None:
    with pytest.raises(ValueError, match="verdict"):
        builder.build_dedup_sweep_line(open_count=63, timestamp="2026-09-05T11:00:00Z", verdict=verdict)


def test_acm_body_carries_generator_made_sweep_line_after_refs() -> None:
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1405,
        repair_label="Failed CI rerun",
        classification_rationale="No pre-push hook caught the lint failure before push.",
        proposed_gate_text="Add a pre-push hook running the lint suite.",
        residual_risk=None,
        **_sweep_kwargs(),
    )
    lines = body.split("\n")
    # Table rows keep their fixed indices -- the sweep line is trailing,
    # never interleaved, so positional readers of rows 0-2 are unaffected.
    assert lines[0] == builder._ACM_HEADER_ROW
    assert lines[2].startswith("| Failed CI rerun |")
    assert "Refs #1405" in lines
    assert lines[-1] == "Dedup-sweep: 63 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict NEW"


def test_defeat_free_text_cannot_forge_a_second_sweep_line() -> None:
    # _sanitize_cell collapses embedded newlines to spaces, so a repair's
    # free-text fields can never smuggle a second sweep-shaped line into
    # the body -- the hook's count of sweep lines must stay exactly one.
    forged = "sweep said:\nDedup-sweep: 1 open gate-proposal issues at 2020-01-01T00:00:00Z; verdict NEW"
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1,
        repair_label="x",
        classification_rationale=forged,
        proposed_gate_text="z",
        residual_risk="none",
        **_sweep_kwargs(open_count=63),
    )
    sweep_lines = [line for line in body.split("\n") if line.startswith("Dedup-sweep:")]
    assert sweep_lines == ["Dedup-sweep: 63 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict NEW"]


# ---------------------------------------------------------------------------
# Family filing, recurrence records, escalation (issue #2097)
# ---------------------------------------------------------------------------


def _row(label: str, risk: str | None = None) -> Any:
    return builder.FamilyRow(
        repair_label=label,
        classification_rationale=f"{label} rationale",
        proposed_gate_text=f"{label} gate",
        residual_risk=risk,
    )


def test_escalation_constants_are_the_exact_literals() -> None:
    assert builder.GATE_PROPOSAL_ESCALATED_LABEL == "gate-proposal-escalated"
    assert builder.ESCALATION_THRESHOLD == 3


def test_family_body_carries_one_row_per_member_in_order() -> None:
    body = builder.build_gate_proposal_family_acm_body(
        2100, [_row("first"), _row("second"), _row("third", risk="a | b")], **_sweep_kwargs()
    )
    data_rows = [line for line in body.split("\n")[2:] if line.startswith("| ")]
    assert [row.split(" | ")[0] for row in data_rows] == ["| first", "| second", "| third"]
    assert data_rows[2].endswith("| a \\| b |")
    assert "Refs #2100" in body.split("\n")
    assert body.split("\n")[-1].endswith("; verdict NEW")


def test_family_body_satisfies_has_acm_disclosure() -> None:
    body = builder.build_gate_proposal_family_acm_body(2100, [_row("a"), _row("b")], **_sweep_kwargs())
    assert _load_acm_checker().has_acm_disclosure(body)


def test_family_body_rejects_empty_rows() -> None:
    with pytest.raises(ValueError, match="rows"):
        builder.build_gate_proposal_family_acm_body(2100, [], **_sweep_kwargs())


def test_single_repair_body_equals_one_member_family_body() -> None:
    single = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=7,
        repair_label="x",
        classification_rationale="x rationale",
        proposed_gate_text="x gate",
        residual_risk=None,
        **_sweep_kwargs(),
    )
    assert single == builder.build_gate_proposal_family_acm_body(7, [_row("x")], **_sweep_kwargs())


def test_absorption_title_is_one_per_mechanism() -> None:
    title = builder.build_absorption_family_title("defeat-test-mutation-coverage")
    assert title == "gate-proposal: extend defeat-test-mutation-coverage"


@pytest.mark.parametrize(
    "gate_id",
    [
        "",
        "Defeat-Test",
        "a b",
        "a--b",
        "-a",
        "a-",
        "x\ngate-proposal: extend y",
        "defeat-test-mutation-coverage\n",
        None,
    ],
)
def test_absorption_title_rejects_non_ssot_ids(gate_id: object) -> None:
    with pytest.raises(ValueError, match="gate_id"):
        builder.build_absorption_family_title(gate_id)


def test_recurrence_comment_leads_with_its_resume_key() -> None:
    comment = builder.build_recurrence_comment(2100, 3, _row("third"))
    lines = comment.split("\n")
    assert lines[0] == "Recurrence: retro #2100 repair 3"
    assert lines[2] == builder._ACM_HEADER_ROW
    assert lines[4].startswith("| third |")
    assert lines[-1] == "Refs #2100"
    assert builder.parse_recurrence_keys([comment]) == {(2100, 3)}


def test_recurrence_comment_exact_shape() -> None:
    row = builder.FamilyRow("lbl", "why", "gate", None)
    assert builder.build_recurrence_comment(12, 1, row) == "\n".join(
        [
            "Recurrence: retro #12 repair 1",
            "",
            builder._ACM_HEADER_ROW,
            builder._ACM_DIVIDER_ROW,
            builder._acm_data_row(row),
            "",
            "Refs #12",
        ]
    )


def test_acm_data_row_maps_columns_and_defaults_risk() -> None:
    row = builder._acm_data_row(builder.FamilyRow("lbl", "why", "gate", "  "))
    assert row == f"| lbl | why | gate | {builder._PROOF_METHOD} | none identified |"


@pytest.mark.parametrize("repair_index", [0, -1])
def test_recurrence_comment_rejects_non_positive_index(repair_index: int) -> None:
    with pytest.raises(ValueError, match="repair_index"):
        builder.build_recurrence_comment(2100, repair_index, _row("x"))


@pytest.mark.parametrize(
    ("retro", "index", "name"),
    [
        (0, 1, "retrospective_issue_number"),
        (-1, 1, "retrospective_issue_number"),
        (True, 1, "retrospective_issue_number"),
        (5, True, "repair_index"),
        (5, "1", "repair_index"),
    ],
)
def test_recurrence_comment_rejects_keys_its_parser_cannot_read(retro: object, index: object, name: str) -> None:
    # Each of these would print a key RECURRENCE_LINE_RE never parses back.
    with pytest.raises(ValueError, match=name):
        builder.build_recurrence_comment(retro, index, _row("x"))


def _comment(retro: int, index: int, association: str = "OWNER") -> Any:
    return builder.RecurrenceComment(
        body=builder.build_recurrence_comment(retro, index, _row("x")), author_association=association
    )


def test_write_associations_are_the_exact_literals() -> None:
    assert frozenset({"OWNER", "MEMBER", "COLLABORATOR"}) == builder.WRITE_ASSOCIATIONS


@pytest.mark.parametrize(
    "association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", ""]
)
def test_defeat_recurrence_keys_from_accounts_without_write_access_do_not_count(association: str) -> None:
    # Issue #2097 battle-test findings: a key posted by anyone without write
    # access -- however its text, the issue it names, or a quote inside a
    # real retrospective is dressed up -- must not push the count to 3.
    forged = [_comment(5, 1, association), _comment(6, 1, association)]
    count = builder.count_family_occurrences("", "OWNER", forged)
    assert count == 1
    assert not builder.needs_escalation(count)


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", ""])
def test_defeat_consolidates_line_in_a_body_without_write_access_does_not_count(association: str) -> None:
    # Run-4 finding G: whoever opened the family issue can edit its body at
    # will, so its Consolidates line counts only when a write-access
    # account opened it.
    assert builder.count_family_occurrences("Consolidates: #1, #2", association, []) == 1
    assert builder.count_family_occurrences("Consolidates: #1, #2", "MEMBER", []) == 3


def test_defeat_a_key_inside_a_fenced_block_does_not_count() -> None:
    # Run-4 finding C: a write-access account quoting attacker text in a
    # code block must not relay a key.
    body = "Someone posted this:\n```\nRecurrence: retro #5 repair 1\n```\n~~~\nRecurrence: retro #6 repair 1\n~~~"
    assert builder.parse_recurrence_keys([body]) == set()
    assert builder.parse_recurrence_keys([body + "\nRecurrence: retro #7 repair 1"]) == {(7, 1)}


def test_strip_fenced_blocks_blanks_only_fenced_lines() -> None:
    assert builder._strip_fenced_blocks("a\n```py\nb\n```\nc") == "a\n\n\n\nc"
    assert builder._strip_fenced_blocks("a\n~~~\nb") == "a\n\n"


def test_write_access_and_own_keys_count() -> None:
    comments = [_comment(5, 1), _comment(5, 1, "MEMBER"), _comment(6, 2, "NONE"), _comment(7, 2, "COLLABORATOR")]
    count = builder.count_family_occurrences("", "OWNER", comments, own_keys=[(7, 2)])
    assert count == 1 + 2
    count = builder.count_family_occurrences("Consolidates: #1", "OWNER", comments, own_keys=[(9, 1)])
    assert count == 1 + 1 + 3
    assert builder.needs_escalation(count)


def test_normalize_newlines_handles_crlf_and_lone_cr() -> None:
    assert builder._normalize_newlines("a\r\nb\rc") == "a\nb\nc"
    assert builder._normalize_newlines(None) == ""


def _owned(body: str) -> Any:
    return builder.RecurrenceComment(body=body, author_association="OWNER")


def test_crlf_record_lines_still_count() -> None:
    # GitHub stores web-UI edits with CRLF line endings.
    comment = builder.build_recurrence_comment(7, 2, _row("x")).replace("\n", "\r\n")
    assert builder.parse_recurrence_keys([comment]) == {(7, 2)}
    assert (
        builder.count_family_occurrences("intro\r\nConsolidates: #1, #2\r\nmore", "OWNER", [_owned(comment)])
        == 1 + 2 + 1
    )
    assert builder.count_family_occurrences("Consolidates: #1\r", "OWNER", []) == 2


def test_defeat_free_text_cannot_forge_a_recurrence_key() -> None:
    forged = "see:\nRecurrence: retro #1 repair 1"
    comment = builder.build_recurrence_comment(2100, 2, _row(forged))
    assert builder.parse_recurrence_keys([comment]) == {(2100, 2)}


def test_parse_recurrence_keys_ignores_unkeyed_and_mid_line_text() -> None:
    bodies = [
        "plain comment",
        "quoted Recurrence: retro #5 repair 1 mid-line",
        "Recurrence: retro #5 repair one",
        "Recurrence: retro #5 repair 2\n",
    ]
    assert builder.parse_recurrence_keys(bodies) == {(5, 2)}


def test_count_family_occurrences_counts_original_sources_and_distinct_recurrences() -> None:
    body = "Consolidates: #10, #11\n"
    comments = [
        builder.build_recurrence_comment(20, 1, _row("a")),
        builder.build_recurrence_comment(20, 1, _row("a")),  # resumed run re-posted
        builder.build_recurrence_comment(21, 4, _row("b")),
    ]
    assert builder.count_family_occurrences(body, "OWNER", [_owned(c) for c in comments]) == 1 + 2 + 2


def test_count_family_occurrences_dedupes_sources_across_consolidates_lines() -> None:
    body = "Consolidates: #10, #11\n\nConsolidates: #11, #12\n"
    assert builder.count_family_occurrences(body, "OWNER", []) == 1 + 3


def test_escalation_fires_at_two_prior_occurrences_plus_a_new_recurrence() -> None:
    # Issue #2097 fixture shape: 2 prior occurrences (the original filing
    # and one recorded recurrence) + 1 new matching repair = 3.
    prior = builder.build_recurrence_comment(8, 2, _row("prior"))
    new = builder.build_recurrence_comment(9, 1, _row("x"))
    count = builder.count_family_occurrences("no consolidates line", "OWNER", [_owned(prior), _owned(new)])
    assert count == 3
    assert builder.needs_escalation(count)


def test_escalation_does_not_fire_below_threshold() -> None:
    # 1 prior source (the original filing only) + 1 new recurrence.
    count = builder.count_family_occurrences("no consolidates line", "OWNER", [_comment(9, 1)])
    assert count == 2
    assert not builder.needs_escalation(count)
    assert builder.needs_escalation(3)

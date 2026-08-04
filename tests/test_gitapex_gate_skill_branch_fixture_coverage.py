"""Tests for the skill decision-branch/fixture coverage gate
(.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py).

Issue #49 repair 1 (re-escalated across #419, #440, #454, #548): a
SKILL.md's own Stop-boundary bullets and named dispatch branches must not
outgrow its evals/<skill>/tasks/*.yaml fixture count, without this diff
being the one that grew the branch count -- see the gate script's own
module docstring for the full mechanical definition and delta-scoping
rationale.
"""

from __future__ import annotations

import gitapex_gate_skill_branch_fixture_coverage as gate
from conftest import FakeStdin as _FakeStdin

_STOP_BOUNDARY_SKILL = """\
---
name: example
description: An example skill.
---

# Example

## Procedure

1. Do the thing.

## Stop boundary

- Never do X.
- Never do Y.
- Never do Z.

## Notes

Trailing content after the section, not counted.
"""

_STOP_BOUNDARIES_PLURAL_SKILL = """\
## Stop boundaries

- Never do A.
- Never do B.
"""

_DISPATCH_SKILL = """\
## Exact sequence

6. **Dispatch on `state`.**
   - `"clean"` -> proceed.
   - `"unstable"` or `"blocked"` -> wait and re-check.
   - `"dirty"` -> fix it.

## Stop boundaries

- Never skip step 6.
"""

_FENCED_EXAMPLE_SKILL = """\
## Stop boundaries

- Never do X.

## Worked example

```
## Stop boundaries

- Never do fake-A.
- Never do fake-B.
- Never do fake-C.

   - `"fake-state"` -> this is inside a fence, must not count.
```
"""


# --- count_stop_boundary_bullets ---


def test_counts_bullets_under_singular_stop_boundary_heading():
    assert gate.count_stop_boundary_bullets(_STOP_BOUNDARY_SKILL) == 3


def test_counts_bullets_under_plural_stop_boundaries_heading():
    assert gate.count_stop_boundary_bullets(_STOP_BOUNDARIES_PLURAL_SKILL) == 2


def test_heading_match_is_case_insensitive():
    text = "## stop BOUNDARIES\n\n- Never do X.\n- Never do Y.\n"
    assert gate.count_stop_boundary_bullets(text) == 2


def test_no_stop_boundary_heading_returns_zero():
    assert gate.count_stop_boundary_bullets("## Procedure\n\n- Not a stop boundary.\n") == 0


def test_bullets_stop_at_next_heading_of_any_level():
    text = "## Stop boundary\n\n- Never do X.\n\n### Sub-heading\n\n- Not counted, different section.\n"
    assert gate.count_stop_boundary_bullets(text) == 1


def test_fenced_example_of_stop_boundaries_is_not_counted():
    assert gate.count_stop_boundary_bullets(_FENCED_EXAMPLE_SKILL) == 1


def test_indented_sub_bullets_are_not_top_level():
    text = "## Stop boundaries\n\n- Never do X.\n  - a nested clarification, not its own bullet\n"
    assert gate.count_stop_boundary_bullets(text) == 1


# --- count_dispatch_branches ---


def test_counts_single_token_dispatch_bullets():
    text = '- `"clean"` -> proceed.\n- `"dirty"` -> fix it.\n'
    assert gate.count_dispatch_branches(text) == 2


def test_counts_both_tokens_in_an_or_bullet_separately():
    text = '- `"unstable"` or `"blocked"` -> wait and re-check.\n'
    assert gate.count_dispatch_branches(text) == 2


def test_full_dispatch_skill_matches_real_driving_pr_to_merge_shape():
    assert gate.count_dispatch_branches(_DISPATCH_SKILL) == 4  # clean, unstable, blocked, dirty


def test_unnamed_arrow_bullet_is_not_a_dispatch_branch():
    text = "- Clean/approved, no real findings -> continue to step 8.\n"
    assert gate.count_dispatch_branches(text) == 0


def test_dispatch_bullet_inside_stop_boundary_section_is_excluded():
    text = '## Stop boundaries\n\n- `"clean"` -> this reads as a Stop boundary bullet, not a dispatch branch.\n'
    assert gate.count_dispatch_branches(text) == 0
    assert gate.count_stop_boundary_bullets(text) == 1


def test_same_token_on_two_different_bullets_counted_separately():
    # Two textually DIFFERENT bullets that happen to name the same state
    # word are two distinct branches, not one -- an earlier revision of
    # this gate used a document-wide set() of bare tokens and collapsed
    # them, silently under-counting (found by review before this gate
    # ever shipped; see the module docstring's Counter rationale).
    text = '- `"clean"` -> proceed.\n- `"clean"` -> proceed again, but for a different reason.\n'
    assert gate.count_dispatch_branches(text) == 2


def test_two_unrelated_dispatch_blocks_sharing_a_token_both_count():
    doc = (
        "## Exact sequence\n\n"
        "6. Dispatch on mergeable_state.\n"
        '   - `"unknown"` -> GitHub has not finished computing mergeability yet.\n'
        '   - `"clean"` -> proceed.\n'
        "7. Dispatch on ci_status.\n"
        '   - `"unknown"` -> CI has not reported yet.\n'
        '   - `"failed"` -> stop.\n'
    )
    assert gate.count_dispatch_branches(doc) == 4


def test_byte_identical_bullet_lines_share_one_key_but_both_still_count():
    # The accepted, documented edge case: two bullets with byte-identical
    # first-line text (not merely the same token) share one Counter key
    # (no positional bookkeeping distinguishes them), but the Counter
    # itself still tracks both as a multiset occurrence -- the total stays
    # 2, only the distinct-key count collapses to 1. This is a strictly
    # safer direction than silently dropping to 1 total: it still demands
    # two fixtures' worth of coverage for the two real occurrences.
    text = '- `"clean"` -> proceed.\n- `"clean"` -> proceed.\n'
    counter = gate.dispatch_branch_counter(text)
    assert len(counter) == 1
    assert gate.count_dispatch_branches(text) == 2


def test_fenced_dispatch_example_is_not_counted():
    assert gate.count_dispatch_branches(_FENCED_EXAMPLE_SKILL) == 0


def test_plain_quoted_token_without_backticks_also_counts():
    text = '- "clean" -> proceed.\n'
    assert gate.count_dispatch_branches(text) == 1


def test_nested_dispatch_bullet_inside_stop_boundary_section_still_counts():
    # A dispatch-shaped bullet nested (indented) under a Stop-boundary
    # bullet was never counted by count_stop_boundary_bullets (column-0
    # only) -- excluding the whole section span from the dispatch scan
    # too made it vanish from BOTH counters (found by review before this
    # gate ever shipped). Only a column-0 bullet inside the span -- one
    # that WAS already counted as a Stop-boundary bullet -- is excluded.
    text = (
        "## Stop boundaries\n\n"
        "- Never proceed on an ambiguous check status; resolve first.\n"
        '  - `"unstable"` -> wait and re-check.\n'
        '  - `"blocked"` -> escalate.\n'
    )
    assert gate.count_stop_boundary_bullets(text) == 1
    assert gate.count_dispatch_branches(text) == 2
    assert gate.count_decision_branches(text) == 3


def test_column_zero_dispatch_bullet_inside_stop_boundary_still_excluded_once():
    # The narrower exclusion must still avoid double-counting a bullet
    # that genuinely IS one of the section's own top-level bullets.
    text = '## Stop boundaries\n\n- `"clean"` -> this reads as a Stop boundary bullet, not a dispatch branch.\n'
    assert gate.count_stop_boundary_bullets(text) == 1
    assert gate.count_dispatch_branches(text) == 0


def test_outer_fence_longer_than_inner_nested_fence_stays_blanked():
    # CommonMark: a fence only closes on a line whose own run is the SAME
    # character and AT LEAST AS LONG as the opener. Matching only the
    # first 3 characters (an earlier revision did) let an inner 3-backtick
    # line wrongly close a 4+-backtick outer fence, leaking the rest of
    # the still-illustrative block back into real content.
    text = (
        "## Stop boundaries\n\n- Never do X.\n\n"
        "## Worked example\n\n"
        "````\n"
        "```\n"
        "## Stop boundaries\n\n- Never do fake-A.\n- Never do fake-B.\n"
        "```\n"
        "still inside the outer fence\n"
        "````\n"
    )
    assert gate.count_stop_boundary_bullets(text) == 1


# --- count_decision_branches ---


def test_decision_branches_sums_both_metrics():
    assert gate.count_decision_branches(_DISPATCH_SKILL) == 4 + 1  # 4 dispatch + 1 stop boundary


def test_decision_branches_zero_for_a_skill_with_neither_shape():
    text = "## Procedure\n\n1. Step one.\n2. Step two.\n"
    assert gate.count_decision_branches(text) == 0


# --- *_counter (content-keyed multisets) ---


def test_stop_boundary_bullet_counter_keys_by_content():
    counter = gate.stop_boundary_bullet_counter(_STOP_BOUNDARY_SKILL)
    assert sum(counter.values()) == 3
    assert len(counter) == 3  # three distinct keys, since all three bullets differ


def test_dispatch_branch_counter_keys_combine_line_and_token():
    counter = gate.dispatch_branch_counter(_DISPATCH_SKILL)
    assert sum(counter.values()) == 4
    assert len(counter) == 4


def test_decision_branch_counter_is_the_sum_of_both_counters():
    combined = gate.decision_branch_counter(_DISPATCH_SKILL)
    expected = gate.stop_boundary_bullet_counter(_DISPATCH_SKILL) + gate.dispatch_branch_counter(_DISPATCH_SKILL)
    assert combined == expected


# --- evaluate_skill (delta scoping) ---


def test_new_skill_every_branch_counts_as_new():
    result = gate.evaluate_skill("new-skill", None, _STOP_BOUNDARY_SKILL, fixture_count=1)
    assert result.applicable is True
    assert result.before_branches is None
    assert result.after_branches == 3
    assert result.passed is False


def test_new_skill_with_enough_fixtures_passes():
    result = gate.evaluate_skill("new-skill", None, _STOP_BOUNDARY_SKILL, fixture_count=3)
    assert result.applicable is True
    assert result.passed is True


def test_unchanged_branch_count_is_not_applicable_even_when_under_covered():
    # A pre-existing gap this diff did not create must never be retroactively flagged.
    result = gate.evaluate_skill("legacy-skill", _STOP_BOUNDARY_SKILL, _STOP_BOUNDARY_SKILL, fixture_count=0)
    assert result.applicable is False
    assert result.passed is True


def test_decreased_branch_count_is_not_applicable():
    shrunk = "## Stop boundary\n\n- Never do X.\n"
    result = gate.evaluate_skill("shrinking-skill", _STOP_BOUNDARY_SKILL, shrunk, fixture_count=0)
    assert result.applicable is False
    assert result.passed is True


def test_increased_branch_count_without_matching_fixtures_fails():
    grown = _STOP_BOUNDARY_SKILL.replace("- Never do Z.\n", "- Never do Z.\n- Never do W.\n")
    result = gate.evaluate_skill("growing-skill", _STOP_BOUNDARY_SKILL, grown, fixture_count=3)
    assert result.applicable is True
    assert result.before_branches == 3
    assert result.after_branches == 4
    assert result.passed is False


def test_increased_branch_count_with_matching_fixtures_passes():
    grown = _STOP_BOUNDARY_SKILL.replace("- Never do Z.\n", "- Never do Z.\n- Never do W.\n")
    result = gate.evaluate_skill("growing-skill", _STOP_BOUNDARY_SKILL, grown, fixture_count=4)
    assert result.applicable is True
    assert result.passed is True


def test_same_count_content_swap_is_still_detected_as_growth():
    # A same-total content swap (3 bullets removed, 3 DIFFERENT bullets
    # added) must not bypass the delta check just because 3 <= 3 -- an
    # earlier revision of this gate compared bare totals and missed this
    # exact case (found by review before this gate ever shipped).
    before = "## Stop boundaries\n\n- Never do A.\n- Never do B.\n- Never do C.\n"
    after = "## Stop boundaries\n\n- Never do X.\n- Never do Y.\n- Never do Z.\n"
    result = gate.evaluate_skill("swap-skill", before, after, fixture_count=0)
    assert result.applicable is True
    assert result.before_branches == 3
    assert result.after_branches == 3
    assert result.passed is False


def test_reordering_the_same_bullets_is_not_applicable():
    # The inverse of the swap case: identical bullet CONTENT, different
    # order, must not look like growth (Counter subtraction is
    # order-independent, unlike a naive positional diff).
    before = "## Stop boundaries\n\n- Never do A.\n- Never do B.\n- Never do C.\n"
    after = "## Stop boundaries\n\n- Never do C.\n- Never do A.\n- Never do B.\n"
    result = gate.evaluate_skill("reorder-skill", before, after, fixture_count=0)
    assert result.applicable is False
    assert result.passed is True


def test_unreadable_before_content_treated_as_new_skill():
    # None is the sentinel the I/O layer passes when a before-content file
    # could not be read; the pure decision function must treat it exactly
    # like a brand-new skill.
    result = gate.evaluate_skill("skill", None, _STOP_BOUNDARY_SKILL, fixture_count=2)
    assert result.before_branches is None
    assert result.applicable is True


# --- _parse_entries ---


def test_parse_entries_splits_on_tabs():
    text = "skill-a\t\t/tmp/a.md\t2\nskill-b\t/tmp/before.md\t/tmp/after.md\t5\n"
    assert gate._parse_entries(text) == [
        ("skill-a", "", "/tmp/a.md", "2"),
        ("skill-b", "/tmp/before.md", "/tmp/after.md", "5"),
    ]


def test_parse_entries_skips_blank_and_malformed_lines():
    text = "\nnot-enough-fields\t1\nskill-a\t\t/tmp/a.md\t0\n\n"
    assert gate._parse_entries(text) == [("skill-a", "", "/tmp/a.md", "0")]


# --- _read_entries / main() ---


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_main_passes_with_no_entries(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b""))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_passes_for_new_skill_with_enough_fixtures(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t\t{after_path}\t3\n".encode()))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_for_new_skill_with_too_few_fixtures(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t\t{after_path}\t1\n".encode()))
    assert gate.main([]) == 1
    err_or_out = capsys.readouterr()
    assert "FAIL" in err_or_out.out
    assert "example" in err_or_out.out


def test_main_skips_unchanged_branch_count(tmp_path, monkeypatch, capsys):
    before_path = _write(tmp_path, "before.md", _STOP_BOUNDARY_SKILL)
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t{before_path}\t{after_path}\t0\n".encode()))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_missing_after_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t\t{tmp_path / 'missing.md'}\t0\n".encode()))
    assert gate.main([]) == 1
    assert "could not read after-content" in capsys.readouterr().err


def test_main_treats_unreadable_before_file_as_new_skill(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    missing_before = str(tmp_path / "missing-before.md")
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t{missing_before}\t{after_path}\t1\n".encode()))
    assert gate.main([]) == 1
    out = capsys.readouterr()
    assert "warning" in out.err
    assert "new skill" in out.out


def test_main_reports_error_for_non_integer_fixture_count(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(f"example\t\t{after_path}\tnot-a-number\n".encode()))
    assert gate.main([]) == 1
    assert "non-integer fixture count" in capsys.readouterr().err


def test_main_reads_entries_from_file(tmp_path, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    entries_path = tmp_path / "entries.tsv"
    entries_path.write_text(f"example\t\t{after_path}\t3\n", encoding="utf-8")
    assert gate.main(["--entries", str(entries_path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_missing_entries_file(capsys):
    assert gate.main(["--entries", "/no/such/file.tsv"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_reports_error_for_non_utf8_entries_file(tmp_path, capsys):
    path = tmp_path / "entries.tsv"
    path.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--entries", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_hard_fails_on_entirely_malformed_nonblank_input(monkeypatch, capsys):
    # A non-blank entries input that parses to zero well-formed entries
    # (e.g. a workflow bug producing lines with the wrong field count)
    # must never be silently read as "nothing changed" -- an earlier
    # revision of this gate returned a bare PASS here (found by review
    # before this gate ever shipped).
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"not-a-well-formed-line\nanother-bad-line\n"))
    assert gate.main([]) == 1
    assert "refusing to silently treat malformed input" in capsys.readouterr().err


def test_main_reports_multiple_skills_in_one_run(tmp_path, monkeypatch, capsys):
    ok_after = _write(tmp_path, "ok.md", _STOP_BOUNDARY_SKILL)
    bad_after = _write(tmp_path, "bad.md", _STOP_BOUNDARIES_PLURAL_SKILL)
    stdin_text = f"ok-skill\t\t{ok_after}\t3\nbad-skill\t\t{bad_after}\t0\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(stdin_text.encode("utf-8")))
    assert gate.main([]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "bad-skill" in out
    assert "ok-skill" not in out  # only failures are listed by name


# --- format_report ---


def test_format_report_no_applicable_entries():
    result = gate.evaluate_skill("skill", _STOP_BOUNDARY_SKILL, _STOP_BOUNDARY_SKILL, fixture_count=0)
    report = gate.format_report([result])
    assert report.startswith("PASS")
    assert "did not" not in report  # sanity: no stray wording bugs


def test_format_report_all_applicable_pass():
    result = gate.evaluate_skill("skill", None, _STOP_BOUNDARIES_PLURAL_SKILL, fixture_count=2)
    report = gate.format_report([result])
    assert report.startswith("PASS")


def test_format_report_lists_failure_details():
    result = gate.evaluate_skill("skill", None, _STOP_BOUNDARIES_PLURAL_SKILL, fixture_count=0)
    report = gate.format_report([result])
    assert "FAIL" in report
    assert "skill: 2 decision branch(es) (new skill), 0 fixture(s)" in report

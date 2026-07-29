"""Tests for the skill decision-branch/fixture coverage gate
(.github/scripts/gate_skill_branch_fixture_coverage.py).

Issue #49 repair 1 (re-escalated across #419, #440, #454, #548): a
SKILL.md's own Stop-boundary bullets and named dispatch branches must not
outgrow its evals/<skill>/tasks/*.yaml fixture count, without this diff
being the one that grew the branch count -- see the gate script's own
module docstring for the full mechanical definition and delta-scoping
rationale.
"""

from __future__ import annotations

import io

import gate_skill_branch_fixture_coverage as gate

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


def test_duplicate_token_across_bullets_counted_once():
    text = '- `"clean"` -> proceed.\n- `"clean"` -> proceed again elsewhere.\n'
    assert gate.count_dispatch_branches(text) == 1


def test_fenced_dispatch_example_is_not_counted():
    assert gate.count_dispatch_branches(_FENCED_EXAMPLE_SKILL) == 0


def test_plain_quoted_token_without_backticks_also_counts():
    text = '- "clean" -> proceed.\n'
    assert gate.count_dispatch_branches(text) == 1


# --- count_decision_branches ---


def test_decision_branches_sums_both_metrics():
    assert gate.count_decision_branches(_DISPATCH_SKILL) == 4 + 1  # 4 dispatch + 1 stop boundary


def test_decision_branches_zero_for_a_skill_with_neither_shape():
    text = "## Procedure\n\n1. Step one.\n2. Step two.\n"
    assert gate.count_decision_branches(text) == 0


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
    result = gate.evaluate_skill(
        "legacy-skill", _STOP_BOUNDARY_SKILL, _STOP_BOUNDARY_SKILL, fixture_count=0
    )
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
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_passes_for_new_skill_with_enough_fixtures(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t\t{after_path}\t3\n"))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_for_new_skill_with_too_few_fixtures(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t\t{after_path}\t1\n"))
    assert gate.main([]) == 1
    err_or_out = capsys.readouterr()
    assert "FAIL" in err_or_out.out
    assert "example" in err_or_out.out


def test_main_skips_unchanged_branch_count(tmp_path, monkeypatch, capsys):
    before_path = _write(tmp_path, "before.md", _STOP_BOUNDARY_SKILL)
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t{before_path}\t{after_path}\t0\n"))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reports_error_for_missing_after_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t\t{tmp_path / 'missing.md'}\t0\n"))
    assert gate.main([]) == 1
    assert "could not read after-content" in capsys.readouterr().err


def test_main_treats_unreadable_before_file_as_new_skill(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    missing_before = str(tmp_path / "missing-before.md")
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t{missing_before}\t{after_path}\t1\n"))
    assert gate.main([]) == 1
    out = capsys.readouterr()
    assert "warning" in out.err
    assert "new skill" in out.out


def test_main_reports_error_for_non_integer_fixture_count(tmp_path, monkeypatch, capsys):
    after_path = _write(tmp_path, "after.md", _STOP_BOUNDARY_SKILL)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"example\t\t{after_path}\tnot-a-number\n"))
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


def test_main_reports_multiple_skills_in_one_run(tmp_path, monkeypatch, capsys):
    ok_after = _write(tmp_path, "ok.md", _STOP_BOUNDARY_SKILL)
    bad_after = _write(tmp_path, "bad.md", _STOP_BOUNDARIES_PLURAL_SKILL)
    stdin_text = f"ok-skill\t\t{ok_after}\t3\nbad-skill\t\t{bad_after}\t0\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
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

"""Tests for the skill-audit disclosure gate
(.github/scripts/gate_skill_audit_disclosure.py).

Refs #248 (refs #242, #246): this gate blocks a PR that adds or modifies a
skill's SKILL.md unless its body discloses a verdict (or an explicit
waiver) for both battle-testing-a-skill and evaluating-skill-quality.
"""

from __future__ import annotations

import io

import pytest

import gate_skill_audit_disclosure as gate

_VALID_SECTION = """\
## Skill audit evidence

- battle-testing-a-skill: PASS
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""


def test_missing_section_reports_both_audits_missing():
    body = "# My PR\n\nSome description with no evidence section.\n"
    assert sorted(gate.find_missing_disclosures(body)) == [
        "battle-testing-a-skill",
        "evaluating-skill-quality",
    ]


def test_none_body_is_treated_as_empty():
    assert sorted(gate.find_missing_disclosures(None)) == [
        "battle-testing-a-skill",
        "evaluating-skill-quality",
    ]


def test_fully_disclosed_section_passes():
    assert gate.find_missing_disclosures(_VALID_SECTION) == []


@pytest.mark.parametrize(
    "verdict",
    ["PASS", "FAIL", "INDETERMINATE", "pass", "Fail", "indeterminate"],
)
def test_battle_testing_accepts_its_own_verdict_vocabulary_case_insensitively(verdict):
    body = f"""\
## Skill audit evidence

- battle-testing-a-skill: {verdict}
- evaluating-skill-quality: NOT-WELL-FORMED
"""
    assert gate.find_missing_disclosures(body) == []


@pytest.mark.parametrize(
    "verdict",
    [
        "WELL-FORMED-AND-MATURE",
        "WELL-FORMED-NOT-MATURE",
        "NOT-WELL-FORMED",
        "well-formed-and-mature",
    ],
)
def test_evaluating_skill_quality_accepts_its_own_verdict_vocabulary(verdict):
    body = f"""\
## Skill audit evidence

- battle-testing-a-skill: PASS
- evaluating-skill-quality: {verdict}
"""
    assert gate.find_missing_disclosures(body) == []


def test_one_missing_audit_is_reported_alone():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: PASS
"""
    assert gate.find_missing_disclosures(body) == ["evaluating-skill-quality"]


def test_waiver_with_reason_satisfies_either_audit():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording, no behavioral change
- evaluating-skill-quality: WAIVED: same reason
"""
    assert gate.find_missing_disclosures(body) == []


def test_bare_waiver_with_no_reason_does_not_satisfy():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED
- evaluating-skill-quality: WAIVED
"""
    assert sorted(gate.find_missing_disclosures(body)) == [
        "battle-testing-a-skill",
        "evaluating-skill-quality",
    ]


def test_unrecognized_verdict_token_does_not_satisfy():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: LOOKS-GOOD-TO-ME
- evaluating-skill-quality: NOT-WELL-FORMED
"""
    assert gate.find_missing_disclosures(body) == ["battle-testing-a-skill"]


def test_verdict_for_wrong_audit_name_does_not_cross_satisfy():
    body = """\
## Skill audit evidence

- evaluating-skill-quality: NOT-WELL-FORMED
- evaluating-skill-quality: NOT-WELL-FORMED
"""
    assert gate.find_missing_disclosures(body) == ["battle-testing-a-skill"]


def test_section_ends_at_next_heading():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: PASS

## Some other section

- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_missing_disclosures(body) == ["evaluating-skill-quality"]


def test_section_heading_case_insensitive_and_extends_to_end_of_body():
    body = "## skill audit evidence\n\n" + "\n".join(
        f"- {name}: PASS" if name == "battle-testing-a-skill" else f"- {name}: NOT-WELL-FORMED"
        for name in gate._VERDICTS
    )
    assert gate.find_missing_disclosures(body) == []


def test_main_reads_body_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_body_from_file(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_text(_VALID_SECTION, encoding="utf-8")
    assert gate.main(["--body", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_with_missing_disclosure(capsys):
    assert gate.main(["--body", "/dev/null"]) == 1
    err = capsys.readouterr().err
    assert "battle-testing-a-skill" in err
    assert "evaluating-skill-quality" in err


def test_main_reports_error_for_missing_file(capsys):
    assert gate.main(["--body", "/no/such/file.md"]) == 1
    assert "not found" in capsys.readouterr().err


def test_crlf_line_endings_do_not_break_the_heading_match():
    body = _VALID_SECTION.replace("\n", "\r\n")
    assert gate.find_missing_disclosures(body) == []


def test_bare_cr_line_endings_do_not_break_the_heading_match():
    body = _VALID_SECTION.replace("\n", "\r")
    assert gate.find_missing_disclosures(body) == []


def test_verdict_line_accepts_trailing_annotation_text():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: PASS (22/22 dimensions clear, see appendix)
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_missing_disclosures(body) == []


def test_near_miss_verdict_token_does_not_false_match():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: PASSED
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_missing_disclosures(body) == ["battle-testing-a-skill"]

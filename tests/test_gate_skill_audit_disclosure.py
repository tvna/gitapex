"""Tests for the skill-audit disclosure gate
(.github/scripts/gate_skill_audit_disclosure.py).

Refs #248 (refs #242, #246): this gate blocks a PR that adds or modifies a
skill's SKILL.md unless its body discloses a verdict (or an explicit
waiver) for both battle-testing-a-skill and evaluating-skill-quality.

Refs #427 (refs #422): when a changed SKILL.md's frontmatter description
line itself changed, two extra checks apply -- battle-testing-a-skill can
no longer be WAIVED, and the diff must also touch the skill's own
evals/<skill>/tasks/ or evals/<skill>/eval-status.md (issue #499 moved the
latter from a single central docs/skill-eval-status.md), or disclose an
eval-coverage-disclosure waiver.
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
    assert gate.main(["--body", "/dev/null", "--skill-md-changed"]) == 1
    err = capsys.readouterr().err
    assert "battle-testing-a-skill" in err
    assert "evaluating-skill-quality" in err


def test_main_skips_base_check_when_skill_md_not_changed(capsys):
    # Issue #517: skill-audit-gate.yml's applicable path now also fires
    # for a design-doc-only change with no SKILL.md touched -- the base
    # battle-testing-a-skill/evaluating-skill-quality check must not run
    # unconditionally, or every design-doc-only PR would be forced to
    # disclose audits of a skill it never touched.
    assert gate.main(["--body", "/dev/null"]) == 0
    assert "PASS" in capsys.readouterr().out


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


# --- Issue #427 (refs #422): find_disallowed_battle_testing_waiver ---


def test_battle_testing_waiver_rejected_when_description_changed():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording, no behavioral change
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_disallowed_battle_testing_waiver(
        body, ["drafting-an-acm-issue"]
    ) == ["drafting-an-acm-issue"]


def test_battle_testing_waiver_allowed_when_description_unchanged():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording, no behavioral change
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_disallowed_battle_testing_waiver(body, []) == []


def test_battle_testing_real_verdict_accepted_even_when_description_changed():
    assert gate.find_disallowed_battle_testing_waiver(
        _VALID_SECTION, ["drafting-an-acm-issue"]
    ) == []


def test_battle_testing_waiver_check_is_no_op_with_no_evidence_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_disallowed_battle_testing_waiver(body, ["foo"]) == []


# --- Issue #427 (refs #422): find_missing_eval_coverage_disclosure ---


def test_missing_eval_coverage_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_eval_coverage_disclosure(body, ["foo"]) == ["foo"]


def test_missing_eval_coverage_disclosure_reported_with_no_waiver_line():
    assert gate.find_missing_eval_coverage_disclosure(_VALID_SECTION, ["foo"]) == ["foo"]


def test_eval_coverage_waiver_satisfies_check():
    body = _VALID_SECTION + "- eval-coverage-disclosure: WAIVED: no routing surface touched\n"
    assert gate.find_missing_eval_coverage_disclosure(body, ["foo"]) == []


def test_eval_coverage_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- eval-coverage-disclosure: WAIVED\n"
    assert gate.find_missing_eval_coverage_disclosure(body, ["foo"]) == ["foo"]


def test_eval_coverage_not_required_when_skill_list_empty():
    assert gate.find_missing_eval_coverage_disclosure("anything, no section", []) == []


# --- Issue #427 (refs #422): _parse_skill_list ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        (None, []),
        ("foo", ["foo"]),
        ("foo,bar", ["bar", "foo"]),
        (" foo , bar ,foo", ["bar", "foo"]),
        (",,", []),
    ],
)
def test_parse_skill_list(raw, expected):
    assert gate._parse_skill_list(raw) == expected


# --- Issue #427 (refs #422): main() integration ---


def test_main_fails_when_battle_testing_waived_and_description_changed(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: reviewed already
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main(["--description-changed-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "cannot be disclosed as WAIVED" in err
    assert "foo" in err


def test_main_passes_with_real_verdict_and_description_changed(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert gate.main(["--description-changed-skills", "foo"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_still_accepts_waiver_when_description_unchanged(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording
- evaluating-skill-quality: WAIVED: same reason
"""
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main([]) == 0


def test_main_fails_when_eval_coverage_missing(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert gate.main(["--needs-eval-coverage-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "eval-coverage" in err
    assert "foo" in err


def test_main_passes_when_eval_coverage_waived(monkeypatch, capsys):
    body = _VALID_SECTION + "- eval-coverage-disclosure: WAIVED: no routing surface touched\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main(["--needs-eval-coverage-skills", "foo"]) == 0


def test_main_reports_both_new_failures_together(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: reviewed already
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert (
        gate.main(
            [
                "--description-changed-skills",
                "foo",
                "--needs-eval-coverage-skills",
                "foo",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "cannot be disclosed as WAIVED" in err
    assert "eval-coverage" in err


def test_main_notes_waiver_would_be_rejected_when_battle_testing_missing_entirely(
    monkeypatch, capsys
):
    body = """\
## Skill audit evidence

- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main(["--description-changed-skills", "foo", "--skill-md-changed"]) == 1
    err = capsys.readouterr().err
    assert "battle-testing-a-skill" in err
    assert "would not be accepted here either" in err


# --- Issue #517 (refs #454): find_missing_security_coverage_disclosure ---


def test_security_coverage_not_required_when_skill_list_empty():
    assert gate.find_missing_security_coverage_disclosure("anything, no section", []) == []


def test_missing_security_coverage_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_security_coverage_disclosure(body, ["foo"]) == ["foo"]


def test_missing_security_coverage_disclosure_reported_with_no_line():
    assert gate.find_missing_security_coverage_disclosure(_VALID_SECTION, ["foo"]) == ["foo"]


@pytest.mark.parametrize("verdict", ["RAN", "NOT-RUN", "ran", "not-run"])
def test_security_coverage_accepts_its_own_verdict_vocabulary(verdict):
    body = _VALID_SECTION + f"- adversarial-coverage-mapping: {verdict}\n"
    assert gate.find_missing_security_coverage_disclosure(body, ["foo"]) == []


def test_security_coverage_waiver_satisfies_check():
    body = _VALID_SECTION + "- adversarial-coverage-mapping: WAIVED: not security-relevant enough\n"
    assert gate.find_missing_security_coverage_disclosure(body, ["foo"]) == []


def test_security_coverage_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- adversarial-coverage-mapping: WAIVED\n"
    assert gate.find_missing_security_coverage_disclosure(body, ["foo"]) == ["foo"]


def test_security_coverage_unrecognized_verdict_does_not_satisfy():
    body = _VALID_SECTION + "- adversarial-coverage-mapping: MAYBE\n"
    assert gate.find_missing_security_coverage_disclosure(body, ["foo"]) == ["foo"]


# --- Issue #517 (refs #277): find_missing_design_doc_disclosure ---


def test_design_doc_disclosure_not_required_when_doc_list_empty():
    assert gate.find_missing_design_doc_disclosure("anything, no section", []) == []


def test_missing_design_doc_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_design_doc_disclosure(body, ["docs/superpowers/specs/foo.md"]) == [
        "docs/superpowers/specs/foo.md"
    ]


def test_missing_design_doc_disclosure_reported_with_no_line():
    assert gate.find_missing_design_doc_disclosure(_VALID_SECTION, ["foo.md"]) == ["foo.md"]


@pytest.mark.parametrize("verdict", ["RAN", "NOT-RUN", "ran", "not-run"])
def test_design_doc_disclosure_accepts_its_own_verdict_vocabulary(verdict):
    body = _VALID_SECTION + f"- design-doc-adversarial-review: {verdict}\n"
    assert gate.find_missing_design_doc_disclosure(body, ["foo.md"]) == []


def test_design_doc_disclosure_waiver_satisfies_check():
    body = _VALID_SECTION + "- design-doc-adversarial-review: WAIVED: routine bookkeeping doc\n"
    assert gate.find_missing_design_doc_disclosure(body, ["foo.md"]) == []


def test_design_doc_disclosure_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- design-doc-adversarial-review: WAIVED\n"
    assert gate.find_missing_design_doc_disclosure(body, ["foo.md"]) == ["foo.md"]


# --- Issue #517: main() integration for both new checks ---


def test_main_fails_when_security_coverage_missing(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert gate.main(["--security-relevant-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "adversarial-coverage-mapping" in err
    assert "foo" in err


def test_main_passes_when_security_coverage_disclosed(monkeypatch, capsys):
    body = _VALID_SECTION + "- adversarial-coverage-mapping: RAN\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main(["--security-relevant-skills", "foo"]) == 0


def test_main_fails_when_design_doc_disclosure_missing(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert gate.main(["--changed-design-docs", "foo.md"]) == 1
    err = capsys.readouterr().err
    assert "design-doc-adversarial-review" in err
    assert "foo.md" in err


def test_main_passes_when_design_doc_disclosure_present(monkeypatch, capsys):
    body = _VALID_SECTION + "- design-doc-adversarial-review: NOT-RUN\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert gate.main(["--changed-design-docs", "foo.md"]) == 0


def test_main_reports_security_and_design_doc_failures_together(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_VALID_SECTION))
    assert (
        gate.main(
            [
                "--security-relevant-skills",
                "foo",
                "--changed-design-docs",
                "bar.md",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "adversarial-coverage-mapping" in err
    assert "design-doc-adversarial-review" in err

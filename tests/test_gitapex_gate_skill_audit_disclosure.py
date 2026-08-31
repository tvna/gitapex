"""Tests for the skill-audit disclosure gate
(.github/scripts/gitapex_gate_skill_audit_disclosure.py).

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

import builtins
import pathlib
import subprocess

import gitapex_gate_skill_audit_disclosure as gate
import pytest
from conftest import FakeStdin as _FakeStdin

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
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
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


def test_main_reports_error_for_non_utf8_body_file(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--body", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


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
    assert gate.find_disallowed_battle_testing_waiver(body, ["drafting-issues"]) == ["drafting-issues"]


def test_battle_testing_waiver_allowed_when_description_unchanged():
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording, no behavioral change
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    assert gate.find_disallowed_battle_testing_waiver(body, []) == []


def test_battle_testing_real_verdict_accepted_even_when_description_changed():
    assert gate.find_disallowed_battle_testing_waiver(_VALID_SECTION, ["drafting-issues"]) == []


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


# --- Issue #427 (refs #422): _parse_comma_list ---


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
def test_parse_comma_list(raw, expected):
    assert gate._parse_comma_list(raw) == expected


# --- Issue #427 (refs #422): main() integration ---


def test_main_fails_when_battle_testing_waived_and_description_changed(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: reviewed already
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--description-changed-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "cannot be disclosed as WAIVED" in err
    assert "foo" in err


def test_main_passes_with_real_verdict_and_description_changed(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--description-changed-skills", "foo"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_still_accepts_waiver_when_description_unchanged(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: docs-only rewording
- evaluating-skill-quality: WAIVED: same reason
"""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main([]) == 0


def test_main_fails_when_eval_coverage_missing(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--needs-eval-coverage-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "eval-coverage" in err
    assert "foo" in err


def test_main_passes_when_eval_coverage_waived(monkeypatch, capsys):
    body = _VALID_SECTION + "- eval-coverage-disclosure: WAIVED: no routing surface touched\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--needs-eval-coverage-skills", "foo"]) == 0


def test_main_reports_both_new_failures_together(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- battle-testing-a-skill: WAIVED: reviewed already
- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
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


def test_main_notes_waiver_would_be_rejected_when_battle_testing_missing_entirely(monkeypatch, capsys):
    body = """\
## Skill audit evidence

- evaluating-skill-quality: WELL-FORMED-AND-MATURE
"""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
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
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--security-relevant-skills", "foo"]) == 1
    err = capsys.readouterr().err
    assert "adversarial-coverage-mapping" in err
    assert "foo" in err


def test_main_passes_when_security_coverage_disclosed(monkeypatch, capsys):
    body = _VALID_SECTION + "- adversarial-coverage-mapping: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--security-relevant-skills", "foo"]) == 0


def test_main_fails_when_design_doc_disclosure_missing(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--changed-design-docs", "foo.md"]) == 1
    err = capsys.readouterr().err
    assert "design-doc-adversarial-review" in err
    assert "foo.md" in err


def test_main_passes_when_design_doc_disclosure_present(monkeypatch, capsys):
    body = _VALID_SECTION + "- design-doc-adversarial-review: NOT-RUN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-design-docs", "foo.md"]) == 0


def test_main_reports_security_and_design_doc_failures_together(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
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


# --- Issue #565 (refs #560 repair 5): find_missing_checker_script_disclosure ---


def test_checker_script_disclosure_not_required_when_list_empty():
    assert gate.find_missing_checker_script_disclosure("anything, no section", []) == []


def test_missing_checker_script_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_checker_script_disclosure(body, ["skills/foo/scripts/bar.py"]) == [
        "skills/foo/scripts/bar.py"
    ]


def test_missing_checker_script_disclosure_reported_with_no_line():
    assert gate.find_missing_checker_script_disclosure(_VALID_SECTION, ["skills/foo/scripts/bar.py"]) == [
        "skills/foo/scripts/bar.py"
    ]


@pytest.mark.parametrize("verdict", ["RAN", "NOT-RUN", "ran", "not-run"])
def test_checker_script_disclosure_accepts_its_own_verdict_vocabulary(verdict):
    body = _VALID_SECTION + f"- checker-script-adversarial-review: {verdict}\n"
    assert gate.find_missing_checker_script_disclosure(body, ["skills/foo/scripts/bar.py"]) == []


def test_checker_script_disclosure_waiver_satisfies_check():
    body = _VALID_SECTION + "- checker-script-adversarial-review: WAIVED: trivial docstring-only change\n"
    assert gate.find_missing_checker_script_disclosure(body, ["skills/foo/scripts/bar.py"]) == []


def test_checker_script_disclosure_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- checker-script-adversarial-review: WAIVED\n"
    assert gate.find_missing_checker_script_disclosure(body, ["skills/foo/scripts/bar.py"]) == [
        "skills/foo/scripts/bar.py"
    ]


def test_checker_script_disclosure_unrecognized_verdict_does_not_satisfy():
    body = _VALID_SECTION + "- checker-script-adversarial-review: MAYBE\n"
    assert gate.find_missing_checker_script_disclosure(body, ["skills/foo/scripts/bar.py"]) == [
        "skills/foo/scripts/bar.py"
    ]


# --- Issue #565: main() integration for the checker-script check ---


def test_main_fails_when_checker_script_disclosure_missing(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--changed-checker-scripts", "skills/foo/scripts/bar.py"]) == 1
    err = capsys.readouterr().err
    assert "checker-script-adversarial-review" in err
    assert "skills/foo/scripts/bar.py" in err


def test_main_passes_when_checker_script_disclosure_present(monkeypatch, capsys):
    body = _VALID_SECTION + "- checker-script-adversarial-review: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-checker-scripts", "skills/foo/scripts/bar.py"]) == 0


def test_main_reports_checker_script_and_design_doc_failures_together(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert (
        gate.main(
            [
                "--changed-checker-scripts",
                "skills/foo/scripts/bar.py",
                "--changed-design-docs",
                "bar.md",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "checker-script-adversarial-review" in err
    assert "design-doc-adversarial-review" in err


# --- Issue #565 (refs #560 repair 5): regression against PR #558's real body ---
#
# PR #558 ("feat(evaluating-skill-quality): add 4 citation-quality checks to
# gitapex_check_skill_shape.py (#514)") touched only
# skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py and its own
# test file -- no SKILL.md -- and shipped four real correctness bugs
# (retrospective: issue #560) that pytest/ruff/a corpus sweep all missed,
# caught only by a voluntary /code-review pass. This body is the actual,
# unmodified text of that merged PR (fetched via the GitHub API), predating
# this gate: it carries no '## Skill audit evidence' section at all. This
# proves the new check would have caught PR #558 un-waived had it existed
# at the time.
_PR_558_BODY = """\
## Summary

Adds the four deterministic citation-quality checks issue #514 requests to `gitapex_check_skill_shape.py`, each mechanizing a defect a separate retrospective issue previously found by hand: #482 (cross-skill file+heading citation resolution), #487 (unhedged sibling-skill fact-claim), #218 (Agentic operation mechanism-fit subsection citation completeness), #453 (`links-inside-skill` scope extended to `references/*.md`).

## Facts

- `cross-skill-citation-resolves` (#482): a `"SKILL's \\`references/FILE.md\\` HEADING section"` prose citation must resolve to a real sibling skill directory, file, and heading -- reuses `anchor-targets-resolve`'s own GitHub heading-slug logic (`_github_slug`/`_heading_slugs`) verbatim.
- `mechanism-fit-subsections-cite-sources` (#218): every `### ` subsection nested under a `## Agentic operation mechanism-fit` heading (in SKILL.md or any `references/*.md` file) must carry a `[label]`-style citation or the literal phrase "this repository's own reasoned extension". Verified directly: all 5 existing subsections in `evaluating-skill-quality/references/rubric.md` already satisfy this -- no content edits needed there.
- `links-inside-skill:{ref.name}` (#453): extends the existing SKILL.md-only out-of-skill-link check to every `references/*.md` file, resolving a relative link against its own containing file's directory (not the skill root), mirroring `anchor-targets-resolve`'s existing file-relative resolution rule.
- `portable-no-unhedged-skill-fact-claim` (#487): flags an unhedged, possessive (`"\\`NAME\\`'s own X already ..."`) declarative fact-claim about a named, resolving sibling skill inside Portable-declared content.

`#487`'s scope was deliberately narrowed from the issue's literal "any resolving citation, no hedge" wording: a corpus-wide validation scan (run directly against every `skills/*/` directory while designing this check) found that shape fires on **11 of this repository's own already-shipped skills** -- the possessive-citation shape alone (`` `NAME`'s own X``) is extremely common, benign prose here (dozens of legitimate uses). Requiring "already" in the same clause -- grounded in the real incident's own text (`rubric.md`, commit `7ae597d`, fixed in `59b86a5`) and its fix's own diff, which dropped that exact framing rather than adding a hedge phrase -- reduces that to **zero false positives** on the current corpus (the 3 residual hits are all inside `Mixed`-declared skills this check's own Portable gate already excludes). Documented as a deliberate trade-off in the check's own docstring, consistent with this file's own established pattern of narrow, evidence-grounded citation heuristics (e.g. `ISSUE_CITATION_HEDGE_PHRASES`).

Running the extended `#453` check against every shipped skill also found one real, pre-existing out-of-skill link in `auditing-agent-product-scope/references/gitapex-cross-links.md` (`../../../docs/agent-product-scope.md`) -- the exact incident class #453 itself reports as its own root cause. Fixed by dropping the live Markdown link in favor of the plain backtick citation the rest of that file already uses for the same path.

## Assumptions

- `#487`'s narrowed "already"-in-clause trigger will not catch a differently-worded unhedged fact-claim (e.g. one using "always" or no adverb at all). This residual risk was already named in issue #514's own Acceptance Criteria Map ("distinguishing 'unhedged fact-claim' from ordinary prose... needs careful heuristics to avoid false positives") and is documented in the check's own docstring rather than solved.
- `#482`'s heading-text match slugs the citation with a fresh, empty per-citation occurrence table (matching only a heading's first/base occurrence) -- a prose citation names heading *text*, with no way to know which same-slug occurrence (1st, 2nd, ...) the author meant.

## Risk / blast radius

Scoped to `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` (+374 lines) and its test file (+306 lines), plus a 1-line content fix in an unrelated skill's reference file that the extended check surfaced. No SKILL.md files touched. The checker is read-only tooling invoked manually or by other CI gates against a target skill directory; a false positive here would show up as a new check failure on an existing skill, not a runtime behavior change.

## Rollback

`git revert` this commit; no state or schema changes to undo.

## Verification

- `uv run pytest skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py` -- 319 passed (58 new tests across the 4 checks).
- `uv run pytest` (full repo suite) -- 1140 passed, no regressions.
- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py ` run directly against every `skills/*/` directory in this repository -- 0 failures (after the one real `#453`-caught violation was fixed in the same commit).
- `ruff check` on both modified Python files -- clean.

### Acceptance Criteria Map (from issue #514)

| Criterion | Result |
|---|---|
| #482 cross-skill file+heading citation resolves | Implemented (`cross-skill-citation-resolves`); unit tests cover pass, missing-sibling, missing-file, missing-heading, fenced-block exclusion, references/*.md scope |
| #487 unhedged sibling-skill fact-claim flagged | Implemented, narrowed per corpus validation above (`portable-no-unhedged-skill-fact-claim`); unit tests cover unhedged-fails, hedged-passes, non-resolving-name-never-flagged, possessive-without-"already"-never-flagged, non-possessive-never-flagged, Mixed-skips |
| #218 Agentic operation mechanism-fit subsection citation/phrase required | Implemented (`mechanism-fit-subsections-cite-sources`); unit tests cover citation-passes, phrase-passes, neither-fails, no-heading-trivially-passes, section-boundary |
| #453 links-inside-skill scans references/*.md | Implemented (`links-inside-skill:{ref.name}`); unit tests cover out-of-skill-fails, same-directory-passes, skill-root-link-passes, SKILL.md-behavior-unchanged; also found and fixed one real pre-existing violation |

## Checklist

- [x] Tests pass locally
- [x] Docs updated if behavior changed (module docstring's check catalogue extended)
- [x] Issue number cited in every commit
- [ ] Skill audit evidence section -- not applicable, no `skills/*/SKILL.md` touched by this PR
- [ ] Transfer check disclosure -- not applicable, no `evals/*/split.md` Kept-edit-log entry added

## Related Issue

Closes #514
Refs #482, #487, #218, #453
"""


def test_regression_pr_558_body_is_missing_checker_script_disclosure():
    # PR #558 predates this gate and never disclosed any check-script-review
    # evidence -- proving the new check would have caught it un-waived.
    assert gate.find_missing_checker_script_disclosure(
        _PR_558_BODY,
        ["skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py"],
    ) == ["skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py"]


def test_regression_pr_558_main_fails_without_waiver(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_PR_558_BODY.encode("utf-8")))
    assert (
        gate.main(
            [
                "--changed-checker-scripts",
                "skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "checker-script-adversarial-review" in err
    assert "skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py" in err


# --- Issue #673 (refs #665 repair 1): find_missing_gate_quality_disclosure ---
#
# Same shape as the checker-script block above, for the narrower
# .github/scripts/gate_*.py / scan_*.py surface. The two checks are
# deliberately independent: PR #651 satisfied checker-script-adversarial-
# review and still shipped three fail-open defects (see the regression
# fixture at the end of this file).

_GATE_SCRIPT = ".github/scripts/gitapex_gate_plugin_root_brace_notation.py"


def test_gate_quality_disclosure_not_required_when_list_empty():
    assert gate.find_missing_gate_quality_disclosure("anything, no section", []) == []


def test_missing_gate_quality_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_missing_gate_quality_disclosure_reported_with_no_line():
    assert gate.find_missing_gate_quality_disclosure(_VALID_SECTION, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


@pytest.mark.parametrize("verdict", ["RAN", "ran", "Ran"])
def test_gate_quality_disclosure_accepts_its_own_verdict_vocabulary(verdict):
    body = _VALID_SECTION + f"- deterministic-gate-quality: {verdict}\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == []


@pytest.mark.parametrize("verdict", ["NOT-RUN", "not-run"])
def test_gate_quality_disclosure_rejects_not_run(verdict):
    """The one row that narrows the shared RAN/NOT-RUN pair. The
    retrospective's finding was that nobody read a new gate against a
    rubric that already existed, so "I did not read it against the rubric"
    cannot be a passing disclosure -- it is a restatement of the defect.
    WAIVED: <reason> remains the escape hatch, and unlike NOT-RUN it puts a
    reason in front of a reviewer."""
    body = _VALID_SECTION + f"- deterministic-gate-quality: {verdict}\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


@pytest.mark.parametrize(
    "check_name",
    [
        "adversarial-coverage-mapping",
        "design-doc-adversarial-review",
        "checker-script-adversarial-review",
        "defeat-test-disclosure",
    ],
)
def test_the_other_process_checks_still_accept_not_run(check_name):
    """The narrowing above must not leak into the four sibling checks,
    where NOT-RUN is a legitimate answer."""
    body = _VALID_SECTION + f"- {check_name}: NOT-RUN\n"
    pattern = gate._PROCESS_DISCLOSURE_LINE_RES[check_name]
    assert gate._find_missing_disclosure(body, ["item"], pattern) == []


def test_gate_quality_disclosure_waiver_satisfies_check():
    body = _VALID_SECTION + "- deterministic-gate-quality: WAIVED: comment-only change, no logic touched\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == []


def test_gate_quality_disclosure_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- deterministic-gate-quality: WAIVED\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_gate_quality_disclosure_unrecognized_verdict_does_not_satisfy():
    body = _VALID_SECTION + "- deterministic-gate-quality: PASS\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_checker_script_disclosure_does_not_satisfy_gate_quality():
    """The two checks disclose different processes, so one line must never
    stand in for the other -- the exact substitution PR #651 would have made
    (it disclosed checker-script-adversarial-review: RAN and shipped three
    fail-open defects dimension 15 names)."""
    body = _VALID_SECTION + "- checker-script-adversarial-review: RAN\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_gate_quality_disclosure_does_not_satisfy_checker_script():
    """...and the reverse direction, so neither check can be silently
    absorbed into the other later."""
    body = _VALID_SECTION + "- deterministic-gate-quality: RAN\n"
    assert gate.find_missing_checker_script_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


# The three below pin defeat-cases found by probing this check rather than
# trusting it (#665 repair 5's lesson). Each is a fail-open candidate: a
# disclosure that looks present to a reader but must not count.


def test_gate_quality_line_outside_the_evidence_section_does_not_satisfy():
    """A line under a later heading is not a disclosure -- _extract_section
    stops at the next '## ', and this pins that it does."""
    body = _VALID_SECTION + "\n## Verification\n\n- deterministic-gate-quality: RAN\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


@pytest.mark.parametrize(
    "name",
    ["x-deterministic-gate-quality", "deterministic-gate-quality-v2"],
)
def test_a_neighbouring_check_name_does_not_satisfy_this_one(name):
    """A name that merely contains this check's name, as a prefix or a
    suffix, must not be accepted for it."""
    body = _VALID_SECTION + f"- {name}: RAN\n"
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_gate_quality_disclosure_survives_a_crlf_body():
    """GitHub delivers a web-UI-edited body with CRLF endings; the shared
    _normalize_body must cover this check too, not only the older ones."""
    body = (_VALID_SECTION + "- deterministic-gate-quality: RAN\n").replace("\n", "\r\n")
    assert gate.find_missing_gate_quality_disclosure(body, [_GATE_SCRIPT]) == []


# --- Issue #673: main() integration for the gate-quality check ---


def test_main_fails_when_gate_quality_disclosure_missing(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--changed-gate-scripts", _GATE_SCRIPT]) == 1
    err = capsys.readouterr().err
    assert "deterministic-gate-quality" in err
    assert _GATE_SCRIPT in err
    # The FAIL message must point at the rubric the check exists to enforce,
    # not merely name the check -- a reader who has never seen it needs the
    # path (dimensions.md's own dimension 17, discoverability).
    assert "dimensions.md" in err


def test_main_passes_when_gate_quality_disclosure_present(monkeypatch, capsys):
    body = _VALID_SECTION + "- deterministic-gate-quality: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-gate-scripts", _GATE_SCRIPT]) == 0


def test_main_reports_gate_quality_and_checker_script_failures_together(monkeypatch, capsys):
    """A gate script is always also a checker script, so a real PR touching
    one owes both lines; missing both must report both, not just the first."""
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert (
        gate.main(
            [
                "--changed-gate-scripts",
                _GATE_SCRIPT,
                "--changed-checker-scripts",
                _GATE_SCRIPT,
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "deterministic-gate-quality" in err
    assert "checker-script-adversarial-review" in err


def test_gate_quality_check_is_not_required_when_no_gate_script_changed(monkeypatch):
    """An empty --changed-gate-scripts must not make an otherwise-clean body
    fail -- the workflow computes applicability, and a design-doc-only PR
    has no gate script to grade."""
    body = _VALID_SECTION + "- design-doc-adversarial-review: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-design-docs", "foo.md", "--changed-gate-scripts", ""]) == 0


# --- Issue #673 (refs #665 repair 1): regression against PR #651's real body ---
#
# PR #651 ("fix(plugin): brace ${CLAUDE_PLUGIN_ROOT} so apm-deployed hooks
# resolve", merged as ee55c6a) added .github/scripts/gate_plugin_root_brace_
# notation.py, and that new gate shipped three fail-open defects
# (retrospective: issue #665 repair 1) -- zero discovered surfaces exiting 0,
# an unterminated frontmatter block read as "no frontmatter", and an
# unreadable file producing a filenameless message or an uncaught traceback.
# Each contradicts dimension 15 of
# skills/evaluating-deterministic-gate-quality/references/dimensions.md, a
# rubric that already existed. All three passed CI and were found only by an
# operator-run /code-review after the PR opened.
#
# This is a verbatim excerpt of that merged PR's real body (fetched via the
# GitHub API), not the whole text: the full body is ~7000 characters and ends
# with a trailing attribution line carrying a session URL that must not be
# re-committed here. The excerpt spans the two headings around the graded
# region, so the '## Skill audit evidence' section this gate actually reads
# -- and its termination at the next '## ' heading -- are both reproduced
# exactly as they were.
#
# It is a stronger fixture than _PR_558_BODY above, which has no evidence
# section at all: #651 fully satisfied checker-script-adversarial-review and
# still shipped the defects, so this proves the new check catches a PR the
# existing checks already passed.
_PR_651_BODY_EXCERPT = """\
## Checklist

- [x] Tests pass locally (1669 passed; commands and output above)
- [x] Docs updated if behavior changed (the gate's own docstring documents
      the invariant, its scope, and its two deliberate non-covered shapes)
- [x] Issue number cited in every commit (`Refs #650`)
- [x] Skill audit evidence disclosed below (this diff adds a deterministic
      checker script under `.github/scripts/`)
- [ ] N/A: no `evals/*/split.md` Kept-edit-log entry in this diff
- [ ] N/A: no `skills/*/SKILL.md` Stop-boundary or dispatch-branch change in
      this diff

## Skill audit evidence

- battle-testing-a-skill: WAIVED: this diff adds or modifies no `skills/*/SKILL.md`; the two audits grade skill content, and none changed here
- evaluating-skill-quality: WAIVED: same reason -- no `skills/*/SKILL.md` added or modified in this diff
- checker-script-adversarial-review: RAN -- six defeat-case probes against the new gate (nested manifest, `.claude/settings.json` command, agent in a subdirectory, variable buried in a longer shell string, malformed JSON, list-valued command). Two real defects found and fixed in `6d46f90` (subdirectory agents were never read; a malformed manifest raised a bare traceback), two confirmed as deliberate scope boundaries and pinned by new tests, two already handled correctly.

## Related Issue

Closes #650
"""


def test_regression_pr_651_body_already_satisfied_the_checker_script_check():
    """Anchors why a fifth check was needed: #651's real body passes the
    existing check, so that check alone could never have caught it."""
    assert gate.find_missing_checker_script_disclosure(_PR_651_BODY_EXCERPT, [_GATE_SCRIPT]) == []


def test_regression_pr_651_body_is_missing_gate_quality_disclosure():
    assert gate.find_missing_gate_quality_disclosure(_PR_651_BODY_EXCERPT, [_GATE_SCRIPT]) == [_GATE_SCRIPT]


def test_regression_pr_651_main_fails_without_waiver(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_PR_651_BODY_EXCERPT.encode("utf-8")))
    assert gate.main(["--changed-gate-scripts", _GATE_SCRIPT]) == 1
    err = capsys.readouterr().err
    assert "deterministic-gate-quality" in err
    assert _GATE_SCRIPT in err


# --- Issue #998 (refs #982, #997): defeat-test-disclosure ---
#
# Same shared RAN/NOT-RUN/WAIVED shape as the checker-script block above
# (unlike deterministic-gate-quality, which narrows to RAN-only), scoped to
# the union of checker-script and gate paths -- reachable from a path
# neither existing check's own glob covers, e.g. a hooks/check-*.sh gate.

_CHECKER_OR_GATE_PATH = "hooks/check-thing.sh"


def test_defeat_test_disclosure_not_required_when_list_empty():
    assert gate.find_missing_defeat_test_disclosure("anything, no section", []) == []


def test_missing_defeat_test_disclosure_reported_with_no_section():
    body = "# My PR\n\nNo evidence section at all.\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


def test_missing_defeat_test_disclosure_reported_with_no_line():
    assert gate.find_missing_defeat_test_disclosure(_VALID_SECTION, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


@pytest.mark.parametrize("verdict", ["RAN", "NOT-RUN", "ran", "not-run"])
def test_defeat_test_disclosure_accepts_its_own_verdict_vocabulary(verdict):
    body = _VALID_SECTION + f"- defeat-test-disclosure: {verdict}\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == []


def test_defeat_test_disclosure_waiver_satisfies_check():
    body = _VALID_SECTION + "- defeat-test-disclosure: WAIVED: no new detection logic in this docstring-only edit\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == []


def test_defeat_test_disclosure_bare_waiver_with_no_reason_does_not_satisfy():
    body = _VALID_SECTION + "- defeat-test-disclosure: WAIVED\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


def test_defeat_test_disclosure_unrecognized_verdict_does_not_satisfy():
    body = _VALID_SECTION + "- defeat-test-disclosure: MAYBE\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


def test_defeat_test_disclosure_does_not_satisfy_checker_script_or_gate_quality():
    """The three checks are independent claims about the same diff; a
    defeat-test-disclosure line must not silently clear the other two."""
    body = _VALID_SECTION + "- defeat-test-disclosure: RAN\n"
    assert gate.find_missing_checker_script_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]
    assert gate.find_missing_gate_quality_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


def test_checker_script_disclosure_does_not_satisfy_defeat_test():
    """The converse of the check above: #997's own point is that a bare
    checker-script-adversarial-review: RAN is not evidence a defeat test was
    constructed."""
    body = _VALID_SECTION + "- checker-script-adversarial-review: RAN\n"
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


# This check's own defeat test (issue #998's own ask, applied reflexively to
# the check that adds it): a deliberately malformed disclosure line that
# must still FAIL, not just a happy-path line that passes. Each variant
# defeats one structural requirement of `_line_pattern`'s regex.
@pytest.mark.parametrize(
    "malformed_line",
    [
        "- defeat-test-disclosure RAN\n",  # missing colon
        "- defeat-test-disclosure: RANFOO\n",  # verdict word not on a token boundary
        "- defeat-test-disclosure: NOT RUN\n",  # space instead of the required hyphen
        "- defeat-test-disclosure: WAIVED\n",  # WAIVED with no reason text
        "- xdefeat-test-disclosure: RAN\n",  # neighbouring check name, not an exact match
    ],
    ids=["no-colon", "verdict-not-on-boundary", "space-not-hyphen", "waived-no-reason", "neighbouring-name"],
)
def test_defeat_test_disclosure_regex_rejects_malformed_lines(malformed_line):
    body = _VALID_SECTION + malformed_line
    assert gate.find_missing_defeat_test_disclosure(body, [_CHECKER_OR_GATE_PATH]) == [_CHECKER_OR_GATE_PATH]


# --- Issue #998: main() integration for the defeat-test-disclosure check ---


def test_main_fails_when_defeat_test_disclosure_missing(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_VALID_SECTION.encode("utf-8")))
    assert gate.main(["--changed-checker-or-gate-scripts", _CHECKER_OR_GATE_PATH]) == 1
    err = capsys.readouterr().err
    assert "defeat-test-disclosure" in err
    assert _CHECKER_OR_GATE_PATH in err


def test_main_passes_when_defeat_test_disclosure_present(monkeypatch, capsys):
    body = _VALID_SECTION + "- defeat-test-disclosure: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-checker-or-gate-scripts", _CHECKER_OR_GATE_PATH]) == 0


def test_defeat_test_disclosure_check_is_not_required_when_no_path_changed(monkeypatch):
    body = _VALID_SECTION + "- design-doc-adversarial-review: RAN\n"
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(body.encode("utf-8")))
    assert gate.main(["--changed-design-docs", "foo.md", "--changed-checker-or-gate-scripts", ""]) == 0


# --- issue #874: the local --check-diff mode ---
#
# Exercised by direct import rather than only through the subprocess suite
# in tests/test_gitapex_skill_audit_local_wrapper_parity.py: pytest-cov
# cannot see into a subprocess, so the end-to-end suite alone would leave
# this whole branch measured at 0% and silently below the per-file
# coverage floor .github/workflows/test.yml enforces.

_BODY_WITH_GATE_DISCLOSURE = (
    _VALID_SECTION
    + "- checker-script-adversarial-review: RAN\n"
    + "- deterministic-gate-quality: RAN\n"
    + "- defeat-test-disclosure: RAN\n"
)


def _init_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for args in (
        ("config", "user.email", "t@e"),
        ("config", "user.name", "t"),
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    (tmp_path / ".gitapex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gitapex" / "ssot.json").write_text(
        (pathlib.Path(__file__).resolve().parents[1] / ".gitapex" / "ssot.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _commit_all(tmp_path, "base")
    return tmp_path


def _commit_all(repo, message):
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", message], check=True)


def _add_gate_script(repo):
    target = repo / ".github" / "scripts" / "gitapex_gate_new.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n", encoding="utf-8")
    _commit_all(repo, "new gate")


def _body_file(tmp_path, text):
    path = tmp_path / "body.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_check_diff_passes_when_the_diff_triggers_nothing(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _commit_all(repo, "unrelated")
    code = gate.main(
        ["--check-diff", "HEAD~1", "HEAD", "--repo-root", str(repo), "--body-file", _body_file(tmp_path, "nothing")]
    )
    assert code == 0
    assert "triggers no skill-audit disclosure requirement" in capsys.readouterr().out


def test_check_diff_fails_on_an_undisclosed_gate_change(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _VALID_SECTION),
        ]
    )
    assert code == 1
    assert "deterministic-gate-quality" in capsys.readouterr().err


def test_check_diff_passes_once_the_gate_change_is_disclosed(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _BODY_WITH_GATE_DISCLOSURE),
        ]
    )
    assert code == 0, capsys.readouterr().err


def test_check_diff_refuses_explicit_flags_alongside_it(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _VALID_SECTION),
            "--security-relevant-skills",
            "made-up",
        ]
    )
    assert code == 1
    assert "computes the applicability flags itself" in capsys.readouterr().err


def test_check_diff_refuses_an_explicit_skill_md_changed_flag(tmp_path, capsys):
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _VALID_SECTION),
            "--skill-md-changed",
        ]
    )
    assert code == 1
    assert "computes the applicability flags itself" in capsys.readouterr().err


def test_check_diff_fails_closed_when_the_flags_cannot_be_computed(tmp_path, capsys):
    """An uncomputable flag set must never read as 'nothing to disclose'."""
    repo = _init_repo(tmp_path / "repo")
    code = gate.main(
        [
            "--check-diff",
            "no-such-ref",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _VALID_SECTION),
        ]
    )
    assert code == 1
    assert "could not compute this diff's applicability flags" in capsys.readouterr().err


def test_check_diff_reports_a_missing_flag_module(tmp_path, capsys, monkeypatch):
    """The mode is only available inside this repository's own checkout; a
    plugin bundle carries hooks/ but no .github/, and must be told so
    plainly rather than crashing."""
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "gitapex_compute_skill_audit_flags":
            raise ImportError("no module named gitapex_compute_skill_audit_flags")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    code = gate.main(
        ["--check-diff", "A", "B", "--body-file", _body_file(tmp_path, _VALID_SECTION)],
    )
    assert code == 1
    assert "gitapex_compute_skill_audit_flags.py" in capsys.readouterr().err


def test_check_diff_reports_a_dest_with_no_cli_flag(tmp_path, capsys, monkeypatch):
    """Wiring guard one: a dest listed with no argparse flag behind it.

    Reported as a defect in this file, not as a bad operator argument --
    and never as an AttributeError traceback, which is what the earlier
    revision of this guard produced when the conflict check reached the
    unwired dest first.
    """
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    monkeypatch.setattr(gate, "_LIST_FLAG_DESTS", (*gate._LIST_FLAG_DESTS, "invented_flag"))
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _BODY_WITH_GATE_DISCLOSURE),
        ]
    )
    assert code == 1
    assert "registers no flag for: invented_flag" in capsys.readouterr().err


def test_check_diff_reports_a_flag_the_computation_does_not_publish(tmp_path, capsys, monkeypatch):
    """Wiring guard two: a dest this CLI does register but the flag
    computation does not publish, which would leave that check reading
    argparse's own empty default and silently never firing."""
    repo = _init_repo(tmp_path / "repo")
    _add_gate_script(repo)
    # `body` is a real dest on this CLI and deliberately not a
    # SkillAuditFlags field, so it isolates this guard from the one above.
    monkeypatch.setattr(gate, "_LIST_FLAG_DESTS", (*gate._LIST_FLAG_DESTS, "body"))
    code = gate.main(
        [
            "--check-diff",
            "HEAD~1",
            "HEAD",
            "--repo-root",
            str(repo),
            "--body-file",
            _body_file(tmp_path, _BODY_WITH_GATE_DISCLOSURE),
        ]
    )
    assert code == 1
    assert "publishes no flag for: 'body'" in capsys.readouterr().err


def test_body_file_is_an_accepted_alias_for_body(tmp_path, capsys):
    """The spelling issue #874 documents the pre-push command under."""
    code = gate.main(["--body-file", _body_file(tmp_path, _VALID_SECTION), "--skill-md-changed"])
    assert code == 0, capsys.readouterr().err

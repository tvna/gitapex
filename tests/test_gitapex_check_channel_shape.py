"""Tests for gitapex_check_channel_shape.py.

Several cases below are deliberately constructed to DEFEAT this checker's
own detection logic rather than to exercise its happy path: a description
split across lines so a naive first-line read would under-measure it, a
nested `description:` that must not be mistaken for the top-level one, a
`---` inside the body that must not be mistaken for the frontmatter's
closing delimiter, and each threshold's exact boundary on both sides.
"""

from __future__ import annotations

from pathlib import Path

import gitapex_check_channel_shape as ccs
import pytest


def _subagent(description: str, body: str = "body line") -> str:
    return f"---\nname: x\ndescription: {description}\ntools: Read\n---\n\n{body}\n"


# --- split_frontmatter ------------------------------------------------


def test_split_frontmatter_returns_both_halves() -> None:
    frontmatter, body = ccs.split_frontmatter("---\nname: x\n---\n\nhello\n")
    assert "name: x" in frontmatter
    assert "hello" in body


def test_split_frontmatter_fails_closed_without_a_block() -> None:
    with pytest.raises(ccs.ChannelParseError, match="does not open"):
        ccs.split_frontmatter("# no frontmatter\n")


def test_split_frontmatter_fails_closed_when_unterminated() -> None:
    with pytest.raises(ccs.ChannelParseError, match="unterminated"):
        ccs.split_frontmatter("---\nname: x\nstill going\n")


def test_split_frontmatter_stops_at_the_first_closing_delimiter() -> None:
    """DEFEAT CASE: a `---` horizontal rule inside the body must not be
    read as the frontmatter's closing delimiter, and the body must keep
    everything after the real one."""
    frontmatter, body = ccs.split_frontmatter("---\nname: x\n---\n\nintro\n\n---\n\nmore\n")
    assert "name: x" in frontmatter
    assert "intro" in body
    assert "more" in body


# --- frontmatter_values ----------------------------------------------


def test_multi_line_description_is_measured_whole() -> None:
    """DEFEAT CASE: a description continued on following lines would be
    under-measured by a parser that stops at the first newline. Here the
    continuation is what pushes it over the cap, so a truncating parser
    would wrongly PASS."""
    continuation = "\n".join(["x" * 100] * 6)
    text = f"---\nname: x\ndescription: >\n  {continuation}\ntools: Read\n---\n\nbody\n"
    values = ccs.frontmatter_values(ccs.split_frontmatter(text)[0])
    assert len(values["description"]) > ccs.DESCRIPTION_MAX_CHARS
    findings = ccs.check_subagent("p", text)
    assert not next(f for f in findings if f.check == "description-chars").passed


def test_nested_description_is_not_read_as_the_top_level_one() -> None:
    """DEFEAT CASE: an indented `description:` belongs to the mapping above
    it. Treating it as a second top-level key would overwrite, or append
    to, the real description and mis-measure it."""
    text = "---\nname: x\ndescription: real\nhooks:\n  description: nested and much longer than the real one\n---\n\nbody\n"
    values = ccs.frontmatter_values(ccs.split_frontmatter(text)[0])
    assert values["description"] == "real"


def test_keys_without_values_are_still_recorded() -> None:
    values = ccs.frontmatter_values("name:\ndescription: d")
    assert values["name"] == ""
    assert values["description"] == "d"


# --- thresholds -------------------------------------------------------


@pytest.mark.parametrize(
    ("length", "expected_pass"),
    [
        (ccs.DESCRIPTION_MAX_CHARS - 1, True),
        (ccs.DESCRIPTION_MAX_CHARS, True),
        (ccs.DESCRIPTION_MAX_CHARS + 1, False),
    ],
)
def test_description_char_boundary(length: int, expected_pass: bool) -> None:
    findings = ccs.check_subagent("p", _subagent("d" * length))
    assert next(f for f in findings if f.check == "description-chars").passed is expected_pass


@pytest.mark.parametrize(
    ("lines", "expected_pass"),
    [
        (ccs.BODY_MAX_LINES, True),
        (ccs.BODY_MAX_LINES + 1, False),
    ],
)
def test_body_line_boundary(lines: int, expected_pass: bool) -> None:
    findings = ccs.check_subagent("p", _subagent("d", body="\n".join(["x"] * lines)))
    assert next(f for f in findings if f.check == "body-lines").passed is expected_pass


def test_body_token_boundary() -> None:
    over = "x" * ((ccs.BODY_MAX_TOKENS + 1) * ccs.CHARS_PER_TOKEN_ESTIMATE)
    findings = ccs.check_subagent("p", _subagent("d", body=over))
    assert not next(f for f in findings if f.check == "body-tokens").passed


def test_estimated_tokens_divides_by_four() -> None:
    """The literal expected value, not a re-derivation through the same
    constant: this asserts the estimate, where re-deriving it would only
    detect a change to the constant's name."""
    assert ccs.estimated_tokens("x" * 40) == 10
    assert ccs.estimated_tokens("x" * 3) == 0


def test_empty_body_counts_as_zero_lines() -> None:
    findings = ccs.check_subagent("p", "---\nname: x\ndescription: d\n---\n")
    assert next(f for f in findings if f.check == "body-lines").detail.startswith("0 lines")


# --- fail-closed paths -------------------------------------------------


def test_missing_description_fails_closed() -> None:
    findings = ccs.check_subagent("p", "---\nname: x\n---\n\nbody\n")
    assert findings == [ccs.Finding("p", "frontmatter", False, "frontmatter declares no 'description' key")]


def test_malformed_frontmatter_fails_closed() -> None:
    findings = ccs.check_subagent("p", "no frontmatter at all\n")
    assert len(findings) == 1
    assert not findings[0].passed


def test_missing_file_fails_closed(tmp_path: Path) -> None:
    findings = ccs.check_path(tmp_path / "absent.md", ccs._SUBAGENT)
    assert findings == [ccs.Finding(str(tmp_path / "absent.md"), "readable", False, "file not found")]


def test_undecodable_file_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "bad.md"
    target.write_bytes(b"\xff\xfe\x00invalid")
    findings = ccs.check_path(target, ccs._SUBAGENT)
    assert not findings[0].passed
    assert findings[0].check == "readable"


def test_directory_path_fails_closed(tmp_path: Path) -> None:
    """DEFEAT CASE: a directory is readable as a path but not as a file;
    an OSError here must fail closed, not raise out of the checker."""
    findings = ccs.check_path(tmp_path, ccs._SUBAGENT)
    assert not findings[0].passed


# --- project-instruction kind -----------------------------------------


def test_project_instruction_grades_whole_file_length() -> None:
    findings = ccs.check_project_instruction("AGENTS.md", "\n".join(["x"] * ccs.PROJECT_INSTRUCTION_MAX_LINES))
    assert findings[0].passed


def test_project_instruction_over_target_fails() -> None:
    findings = ccs.check_project_instruction("AGENTS.md", "\n".join(["x"] * (ccs.PROJECT_INSTRUCTION_MAX_LINES + 1)))
    assert not findings[0].passed


def test_project_instruction_empty_file_is_zero_lines() -> None:
    assert ccs.check_project_instruction("AGENTS.md", "")[0].detail.startswith("0 lines")


def test_check_path_dispatches_on_kind(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("one line\n", encoding="utf-8")
    assert ccs.check_path(target, ccs._PROJECT_INSTRUCTION)[0].check == "file-lines"


# --- CLI ---------------------------------------------------------------


def test_main_requires_paths(capsys: pytest.CaptureFixture[str]) -> None:
    assert ccs.main(["--kind", ccs._SUBAGENT]) == 2
    assert "no paths given" in capsys.readouterr().err


def test_main_passes_on_a_clean_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "a.md"
    target.write_text(_subagent("short"), encoding="utf-8")
    assert ccs.main(["--kind", ccs._SUBAGENT, str(target)]) == 0
    assert "PASS: all" in capsys.readouterr().out


def test_main_fails_on_an_over_length_description(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "a.md"
    target.write_text(_subagent("d" * (ccs.DESCRIPTION_MAX_CHARS + 1)), encoding="utf-8")
    assert ccs.main(["--kind", ccs._SUBAGENT, str(target)]) == 1
    assert "FAIL" in capsys.readouterr().out


# --- the parse-layer defeats found by adversarial review ----------------


def test_is_delimiter_requires_column_zero() -> None:
    """`_is_delimiter` is the fix for the sharpest defeat found against
    this checker: an indented `---` inside a block scalar is CONTENT, and
    closing the frontmatter there truncates the value being measured."""
    assert ccs._is_delimiter("---")
    assert ccs._is_delimiter("---  ")
    assert not ccs._is_delimiter("  ---")
    assert not ccs._is_delimiter("\t---")


def test_an_indented_delimiter_inside_a_block_scalar_does_not_truncate() -> None:
    """DEFEAT CASE, live-reproduced before the fix: a ~1,000-character
    description measured as ~102 and PASSed the 500-character cap, with
    the overflow absorbed by the far looser body budget."""
    text = "---\nname: x\ndescription: |\n  " + "A" * 100 + "\n  ---\n  " + "B" * 900 + "\ntools: Read\n---\n\nbody\n"
    findings = ccs.check_subagent("p", text)
    assert not next(f for f in findings if f.check == "description-chars").passed


def test_a_yaml_alias_description_fails_closed() -> None:
    """DEFEAT CASE: `description: *d` measures as two characters while the
    loader resolves it to an anchor defined elsewhere in the block. The
    checker does not resolve anchors, so it must not report a size it
    cannot stand behind."""
    text = "---\nname: x\n_d: &d " + "A" * 900 + "\ndescription: *d\ntools: Read\n---\n\nbody\n"
    findings = ccs.check_subagent("p", text)
    assert findings[0].check == "frontmatter"
    assert not findings[0].passed


def test_block_scalar_indentation_is_not_stripped_away() -> None:
    """DEFEAT CASE: with an explicit indentation indicator (`|2`),
    indentation past the declared column is content. Stripping it
    under-measures by an attacker-chosen amount per line."""
    text = "---\ndescription: |2\n" + "\n".join("      " + "X" * 50 for _ in range(3)) + "\n---\n\nbody\n"
    measured = ccs.frontmatter_values(ccs.split_frontmatter(text)[0])["description"]
    assert len(measured) > 3 * 50


def test_an_unknown_kind_never_falls_through_to_project_instruction(tmp_path: Path) -> None:
    """DEFEAT CASE: silently grading an unknown kind under the looser
    project-instruction rules would skip the description cap entirely."""
    target = tmp_path / "a.md"
    target.write_text(_subagent("d" * 900), encoding="utf-8")
    findings = ccs.check_path(target, "not-a-kind")
    assert findings == [ccs.Finding(str(target), "kind", False, "unknown channel kind 'not-a-kind'")]


_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_real_repository_passes() -> None:
    """The live check ACM row 4's proof method names. Both `.github/scripts/`
    gates shipped beside this checker carry a `test_the_real_repository_passes`
    against REPO_ROOT; this one had none, which left "the shape checker FAILs
    against the pre-rewrite tree and PASSes after" as a one-time manual
    observation with no regression guard. The checker is not wired into a
    workflow or the local preflight (it is skill-owned, not
    `.github/scripts/`-owned), so this test is the only thing that re-runs it
    against the real tree at all."""
    for relative, kind in (
        ("agents/review-persona.md", "subagent"),
        ("agents/branch-plan-task.md", "subagent"),
        (".claude/agents/branch-plan-task.md", "subagent"),
        ("AGENTS.md", "project-instruction"),
    ):
        path = _REPO_ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        findings = (
            ccs.check_subagent(relative, text) if kind == "subagent" else ccs.check_project_instruction(relative, text)
        )
        failed = [f"{finding.check}: {finding.detail}" for finding in findings if not finding.passed]
        assert failed == [], f"{relative}: {failed}"

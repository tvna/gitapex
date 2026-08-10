"""CI gate + unit tests for evaluating-skill-quality's nine-dimension rubric
vocabulary lock (issue #993).

Two layers, deliberately, mirroring `test_gitapex_scan_contract_axis_vocabulary_drift.py`
(issue #949): an integration test asserting the lock holds against this
repository's own real skill content, and a battery of deliberately corrupted
copies asserting each lock actually fires. A wording gate that has only ever
been run against correct content proves nothing -- it is indistinguishable
from a gate that returns 0 unconditionally.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import gitapex_scan_skill_quality_rubric_vocabulary_drift as G
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-skill-quality"


def _copy_skill(tmp_path: Path) -> Path:
    target = tmp_path / "evaluating-skill-quality"
    shutil.copytree(REAL_SKILL_DIR, target)
    return target


def _mutate(skill_dir: Path, relative: str, old: str, new: str, *, count: int = 1) -> None:
    path = skill_dir / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture setup: {old!r} not present in {relative}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def _mutate_all_range_1_9(skill_dir: Path, relative: str, new_end: int) -> None:
    """Replace every 'dimensions 1-9' range citation, including one that
    line-wraps between 'dimensions' and '1-9' in the real prose (rubric.md's
    Unknowns framework: 'dimensions\\n  1-9 read this directly.') -- a plain
    string .replace() cannot match that occurrence, the same way this gate's
    own regex uses \\s+ rather than a literal space for the same reason."""
    path = skill_dir / relative
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"dimensions(\s+)1-9\b")
    assert pattern.search(text), f"fixture setup: no 'dimensions ... 1-9' range in {relative}"
    text = pattern.sub(lambda m: f"dimensions{m.group(1)}1-{new_end}", text)
    path.write_text(text, encoding="utf-8")


# --- Integration: the real content passes ------------------------------------


def test_real_skill_content_passes() -> None:
    assert G.scan(REAL_SKILL_DIR) == []


def test_main_on_real_content_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert G.main(["--skill-dir", str(REAL_SKILL_DIR)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_with_no_argv_defaults_to_this_repository() -> None:
    assert G.main([]) == 0


# --- Dimension-count declaration lock ------------------------------------------


def test_stale_dimension_count_in_skill_md_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**nine dimensions**", "**eight dimensions**")
    problems = G.scan(skill_dir)
    assert any("declares 8 dimensions but" in p for p in problems), problems


def test_stale_dimension_count_in_rubric_md_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/rubric.md", "**nine-dimension**", "**ten-dimension**")
    problems = G.scan(skill_dir)
    assert any("declares 10 dimensions but" in p for p in problems), problems


def test_unrecognized_dimension_count_word_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**nine dimensions**", "**several dimensions**")
    assert any("not a recognized number word" in p for p in G.scan(skill_dir))


def test_missing_skill_md_declaration_fails(tmp_path: Path) -> None:
    """SKILL.md is the mandatory declaration site -- unbolding its one
    declaration must not silently escape the lock even though rubric.md
    still carries its own."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**nine dimensions**", "nine dimensions")
    problems = G.scan(skill_dir)
    assert any("dimension-count lock cannot run" in p for p in problems), problems


def test_multiple_dimension_count_declarations_are_all_validated(tmp_path: Path) -> None:
    """check_dimension_count grades every bold declaration it finds, not only
    the first -- a second declaration added later must not silently escape."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "SKILL.md",
        "- **Probabilistic maturity** -- **nine dimensions** of judgment",
        "- **Probabilistic maturity** -- **nine dimensions** of judgment. Restated for emphasis: **nine dimensions**.",
    )
    assert G.scan(skill_dir) == []

    _mutate(
        skill_dir,
        "SKILL.md",
        "Restated for emphasis: **nine dimensions**.",
        "Restated for emphasis: **eight dimensions**.",
    )
    problems = G.scan(skill_dir)
    assert any("declares 8 dimensions but" in p for p in problems), problems


def test_dimension_count_matches_after_a_tenth_dimension_is_declared(tmp_path: Path) -> None:
    """The lock tracks the real heading count, not the literal word "nine" --
    every dependent count (the bold declarations, the 1-9 range citations)
    has to move together for the scan to come back clean."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**nine dimensions**", "**ten dimensions**")
    _mutate(skill_dir, "references/rubric.md", "**nine-dimension**", "**ten-dimension**")
    _mutate_all_range_1_9(skill_dir, "references/rubric.md", 10)
    _mutate(
        skill_dir,
        "references/rubric.md",
        "## 9. Cross-model robustness",
        "## 9. Cross-model robustness\n\nBody.\n\n## 10. Invented tenth\n\nBody.",
    )
    assert G.scan(skill_dir) == []


# --- Range-reference lock -------------------------------------------------------


def test_stale_range_reference_in_rubric_md_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/rubric.md", "dimensions 1-9 below say to check", "dimensions 1-8 below say to check")
    problems = G.scan(skill_dir)
    assert any("cites 'dimensions 1-8' but 9 dimension" in p for p in problems), problems


def test_sub_range_reference_is_not_mistaken_for_a_full_span(tmp_path: Path) -> None:
    """'dimensions 8-9' (the Behavioural-evidence/Cross-model-robustness
    exception pair) must never be graded as a stale 1-N claim."""
    skill_dir = _copy_skill(tmp_path)
    assert G.scan(skill_dir) == []
    # Sanity: the sub-range text is really present and unmutated.
    text = (skill_dir / "references" / "rubric.md").read_text(encoding="utf-8")
    assert "dimensions 8-9" in text


# --- Heading-count / order lock -------------------------------------------------


def test_duplicated_dimension_heading_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/rubric.md", "## 9. Cross-model robustness", "## 8. Cross-model robustness")
    problems = G.scan(skill_dir)
    assert any("'## 8.' appears more than once" in p for p in problems), problems


def test_out_of_order_dimension_headings_fails(tmp_path: Path) -> None:
    """Swapping two headings' document position (numbers 8 and 9, keeping
    the set contiguous 1-9 so the gap check does not also fire) isolates
    the ascending-order check from the gap/duplicate checks above it."""
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references" / "rubric.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("## 8. Behavioural evidence", "## TEMP_EIGHT_MARKER", 1)
    text = text.replace("## 9. Cross-model robustness", "## 8. Behavioural evidence", 1)
    text = text.replace("## TEMP_EIGHT_MARKER", "## 9. Cross-model robustness", 1)
    path.write_text(text, encoding="utf-8")
    problems = G.scan(skill_dir)
    assert any("expected ascending" in p for p in problems), problems


def test_gap_in_dimension_headings_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/rubric.md", "## 8. Behavioural evidence", "## 10. Behavioural evidence")
    _mutate(skill_dir, "references/rubric.md", "## 9. Cross-model robustness", "## 11. Cross-model robustness")
    problems = G.scan(skill_dir)
    assert any("expected a contiguous" in p for p in problems), problems


def test_empty_dimension_section_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references" / "rubric.md"
    text = path.read_text(encoding="utf-8")
    marker = "## 9. Cross-model robustness"
    idx = text.index(marker)
    path.write_text(text[: idx + len(marker)] + "\n", encoding="utf-8")
    problems = G.scan(skill_dir)
    assert any("'## 9.' has an empty section" in p for p in problems), problems


def test_no_dimension_headings_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references" / "rubric.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^## \d+\. ", "## X. ", text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(G.ScanError, match=re.escape("no '## N. <Name>' dimension headings found")):
        G.scan(skill_dir)


# --- Mechanism-fit step-label lock ----------------------------------------------


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("- **Skill vs. subagent**:", "- **Skill vs. subagent-dispatch**:"),
        ("- **Skill vs. hook**:", "- **Skill vs. deterministic hook**:"),
        ("- **Skill vs. CLAUDE.md**:", "- **Skill vs. project instructions**:"),
        ("- **Skill vs. multiple skills / cohesion**:", "- **Skill vs. many skills**:"),
        ("- **Skill-step vs. bundled script**:", "- **Step vs. bundled script**:"),
        ("- **Model/effort tier fit**:", "- **Model tier fit**:"),
        ("- **Tool-capability verification**:", "- **Tool capability check**:"),
        ("- **Subagent delegation scope**:", "- **Delegation scope**:"),
        ("- **Invocation-mode fit**:", "- **Invocation mode**:"),
    ],
)
def test_renamed_mechanism_fit_label_fails(tmp_path: Path, old: str, new: str) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", old, new)
    problems = G.scan(skill_dir)
    assert any("lost Mechanism-fit step label" in p for p in problems), problems


def test_absent_mechanism_fit_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "## Mechanism fit", "## Renamed section")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.scan(skill_dir)


def test_duplicated_mechanism_fit_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "SKILL.md",
        "## Mechanism fit",
        "## Mechanism fit\n\nStub.\n\n## Mechanism fit",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.scan(skill_dir)


def test_empty_mechanism_fit_section_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Mechanism fit"
    idx = text.index(marker)
    tail_marker = "## Subagent dispatch"
    tail_idx = text.index(tail_marker)
    path.write_text(text[: idx + len(marker)] + "\n\n" + text[tail_idx:], encoding="utf-8")
    with pytest.raises(G.ScanError, match="is empty"):
        G.scan(skill_dir)


# --- Fail-closed input handling ---------------------------------------------


def test_missing_skill_md_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "SKILL.md").unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.scan(skill_dir)


def test_missing_rubric_md_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "references" / "rubric.md").unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.scan(skill_dir)


def test_non_utf8_file_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "SKILL.md").write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(G.ScanError, match="could not decode as UTF-8"):
        G.scan(skill_dir)


def test_directory_in_place_of_a_file_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "SKILL.md").unlink()
    (skill_dir / "SKILL.md").mkdir()
    with pytest.raises(G.ScanError, match="could not be read"):
        G.scan(skill_dir)


# --- CLI surface --------------------------------------------------------------


def test_main_reports_drift_on_stderr_and_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**nine dimensions**", "**eight dimensions**")
    assert G.main(["--skill-dir", str(skill_dir)]) == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "FAIL:" in err


def test_main_exits_two_when_the_check_cannot_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "references" / "rubric.md").unlink()
    assert G.main(["--skill-dir", str(skill_dir)]) == 2
    assert "failing closed" in capsys.readouterr().err

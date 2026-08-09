"""CI gate + unit tests for the Contract role / input-domain closure axis's
vocabulary lock (issue #949).

Two layers, deliberately: an integration test asserting the lock holds against
this repository's own real skill content, and a battery of deliberately
corrupted copies asserting each lock actually fires. A wording gate that has
only ever been run against correct content proves nothing -- it is
indistinguishable from a gate that returns 0 unconditionally, which is the
fail-open class `gitapex_gate_skill_audit_disclosure.py`'s own
`deterministic-gate-quality` check exists because of.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import gitapex_scan_contract_axis_vocabulary_drift as G
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"


def _copy_skill(tmp_path: Path) -> Path:
    target = tmp_path / "evaluating-deterministic-gate-quality"
    shutil.copytree(REAL_SKILL_DIR, target)
    return target


def _mutate(skill_dir: Path, relative: str, old: str, new: str) -> None:
    path = skill_dir / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture setup: {old!r} not present in {relative}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _mutate_last(skill_dir: Path, relative: str, old: str, new: str) -> None:
    """Replace the LAST occurrence of ``old``.

    The warning-only marker appears once per warning-only axis, and the
    Compatibility awareness axis -- the precedent this one copies -- comes
    first in both files. Corrupting the first occurrence would test that
    axis, not this one.
    """
    path = skill_dir / relative
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.rpartition(old)
    assert sep, f"fixture setup: {old!r} not present in {relative}"
    path.write_text(f"{head}{new}{tail}", encoding="utf-8")


# --- Integration: the real content passes ------------------------------------


def test_real_skill_content_passes() -> None:
    assert G.scan(REAL_SKILL_DIR) == []


def test_main_on_real_content_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert G.main(["--skill-dir", str(REAL_SKILL_DIR)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_with_no_argv_defaults_to_this_repository() -> None:
    assert G.main([]) == 0


# --- Each lock fires on a deliberately corrupted copy -------------------------


@pytest.mark.parametrize(
    ("relative", "old", "new", "expected_fragment"),
    [
        (
            "references/cross-cutting-axes.md",
            "- **Postcondition**",
            "- **After-check**",
            "DbC role: postcondition",
        ),
        (
            "references/cross-cutting-axes.md",
            "- **Precondition**",
            "- **Entry-check**",
            "DbC role: precondition",
        ),
        (
            "references/cross-cutting-axes.md",
            "- **Invariant**",
            "- **Always-true**",
            "DbC role: invariant",
        ),
        (
            "references/cross-cutting-axes.md",
            "- **Structural / protocol value**",
            "- **Protocol value**",
            "input domain: structural/protocol",
        ),
        (
            "references/cross-cutting-axes.md",
            "- **Threat / safety-classification category**",
            "- **Threat category**",
            "input domain: threat/safety classification",
        ),
        (
            "references/cross-cutting-axes.md",
            "Never both: division of responsibility",
            "Division of responsibility",
            "never-both rule",
        ),
    ],
)
def test_corrupted_axis_section_fails(
    tmp_path: Path, relative: str, old: str, new: str, expected_fragment: str
) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, relative, old, new)
    problems = G.scan(skill_dir)
    assert any(expected_fragment in p for p in problems), problems


def test_reclosing_the_open_domain_fails(tmp_path: Path) -> None:
    """Dropping every "non-exhaustive" marker is the specific regression the
    sibling repository's own drift scan exists to catch."""
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references/cross-cutting-axes.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("non-exhaustive", "complete"), encoding="utf-8")
    assert any("open-domain marker" in p for p in G.scan(skill_dir))


def test_dimension_15_citation_loss_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references/cross-cutting-axes.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("dimension 15", "the malformed-input dimension"), encoding="utf-8")
    assert any("dimension 15 citation" in p for p in G.scan(skill_dir))


@pytest.mark.parametrize("relative", ["SKILL.md", "references/cross-cutting-axes.md"])
def test_warning_only_limit_loss_fails_in_either_file(tmp_path: Path, relative: str) -> None:
    """Losing the limit in one file fails even while the other still carries it
    -- and Compatibility awareness's own copy of the same sentence, earlier in
    both files, does not satisfy this axis's requirement for it."""
    skill_dir = _copy_skill(tmp_path)
    _mutate_last(skill_dir, relative, G.WARNING_ONLY_MARKER, "weigh it against the verdict")
    problems = G.scan(skill_dir)
    assert [p for p in problems if "warning-only limit" in p] == [
        f"{relative}: lost warning-only limit -- expected literal text {G.WARNING_ONLY_MARKER!r} in the axis section"
    ], problems


def test_dangling_pointer_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", G.AXES_ANCHOR, "cross-cutting-axes.md#axis-contract-role")
    assert any("pointer to the reference section" in p for p in G.scan(skill_dir))


# --- Axis-count lock ----------------------------------------------------------


def test_stale_axis_count_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**Five cross-cutting axes**", "**Four cross-cutting axes**")
    assert any("declares 4 cross-cutting axes but carries 5" in p for p in G.scan(skill_dir))


def test_unrecognized_axis_count_word_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**Five cross-cutting axes**", "**Several cross-cutting axes**")
    assert any("not a recognized number word" in p for p in G.scan(skill_dir))


def test_missing_axis_count_declaration_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**Five cross-cutting axes**", "Axes, several of them,")
    assert any("axis-count lock cannot run" in p for p in G.scan(skill_dir))


def test_axis_count_matches_after_a_sixth_axis_is_declared(tmp_path: Path) -> None:
    """The lock tracks the real heading count, not the literal word "Five" --
    and every dependent count (SKILL.md's own cross-reference, and
    security-level.md's own "narrower than all N") has to move together for
    the scan to come back clean."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "**Five cross-cutting axes**", "**Six cross-cutting axes**")
    _mutate(skill_dir, "SKILL.md", "the other four axes", "the other five axes")
    _mutate(
        skill_dir,
        "SKILL.md",
        G.SKILL_AXIS_HEADING,
        f"### Axis: Invented sixth\n\nBody.\n\n{G.SKILL_AXIS_HEADING}",
    )
    _mutate(skill_dir, "references/security-level.md", "than all seven", "than all eight")
    assert G.scan(skill_dir) == []


def test_multiple_axis_count_declarations_are_all_validated(tmp_path: Path) -> None:
    """check_axis_count grades every '**N cross-cutting axes**' sentence, not
    only the first ``re.search`` match -- a second declaration added later in
    the file must not silently escape the lock."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "SKILL.md",
        "**Five cross-cutting axes**",
        "**Five cross-cutting axes**\n\nRestated for emphasis: **Five cross-cutting axes**",
    )
    assert G.scan(skill_dir) == []

    _mutate(
        skill_dir,
        "SKILL.md",
        "Restated for emphasis: **Five cross-cutting axes**",
        "Restated for emphasis: **Four cross-cutting axes**",
    )
    problems = G.scan(skill_dir)
    assert any("declares 4 cross-cutting axes but carries 5" in p for p in problems), problems


# --- Schema vocabulary lock ---------------------------------------------------


def test_schema_enum_token_removal_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/output-schema.json", '"mixed", "indeterminate"', '"indeterminate"')
    assert any("contractRole enum is" in p for p in G.scan(skill_dir))


def test_schema_domain_enum_respelling_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/output-schema.json", '"threat-classification"', '"threat_classification"')
    assert any("inputDomainKind enum is" in p for p in G.scan(skill_dir))


def test_schema_missing_axis_node_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/output-schema.json", '"contractRoleInputDomainClosure"', '"somethingElse"')
    with pytest.raises(G.ScanError, match="no node at"):
        G.scan(skill_dir)


def test_schema_enum_replaced_by_a_non_list_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "references/output-schema.json",
        '"enum": ["precondition", "postcondition", "invariant", "mixed", "indeterminate"]',
        '"pattern": "^p"',
    )
    with pytest.raises(G.ScanError, match="has no enum list"):
        G.scan(skill_dir)


def test_malformed_schema_json_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "references/output-schema.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(G.ScanError, match="not valid JSON"):
        G.scan(skill_dir)


# --- Fail-closed input handling ----------------------------------------------


def test_missing_file_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "SKILL.md").unlink()
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


def test_absent_axis_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/cross-cutting-axes.md", G.AXES_AXIS_HEADING, "## Axis: Renamed")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.scan(skill_dir)


def test_duplicated_axis_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "references/cross-cutting-axes.md",
        G.AXES_AXIS_HEADING,
        f"{G.AXES_AXIS_HEADING}\n\nStub body.\n\n{G.AXES_AXIS_HEADING}",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.scan(skill_dir)


def test_empty_axis_section_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references/cross-cutting-axes.md"
    text = path.read_text(encoding="utf-8")
    head = text[: text.index(G.AXES_AXIS_HEADING)]
    path.write_text(f"{head}{G.AXES_AXIS_HEADING}\n", encoding="utf-8")
    with pytest.raises(G.ScanError, match="is empty"):
        G.scan(skill_dir)


def test_absent_skill_md_axis_heading_is_a_scan_error(tmp_path: Path) -> None:
    """The symmetric failure path for SKILL.md's own level-3 (``###``) heading,
    mirroring test_absent_axis_heading_is_a_scan_error above for
    cross-cutting-axes.md's level-2 (``##``) heading -- both go through the
    same extract_section, but SKILL.md's is extracted first in scan() and a
    level-detection regression scoped to one heading depth would otherwise
    only ever be exercised by the level-2 case."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", G.SKILL_AXIS_HEADING, "### Axis: Renamed")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.scan(skill_dir)


def test_duplicated_skill_md_axis_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "SKILL.md",
        G.SKILL_AXIS_HEADING,
        f"{G.SKILL_AXIS_HEADING}\n\nStub body.\n\n{G.SKILL_AXIS_HEADING}",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.scan(skill_dir)


def test_empty_skill_md_axis_section_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    head = text[: text.index(G.SKILL_AXIS_HEADING)]
    path.write_text(f"{head}{G.SKILL_AXIS_HEADING}\n", encoding="utf-8")
    with pytest.raises(G.ScanError, match="is empty"):
        G.scan(skill_dir)


def test_section_stops_at_the_next_same_level_heading(tmp_path: Path) -> None:
    """A term living *after* the axis section must not count as covering it."""
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / "references/cross-cutting-axes.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("- **Invariant**", "- **Always-true**", 1)
    path.write_text(f"{text}\n## Axis: Decoy\n\n- **Invariant**\n", encoding="utf-8")
    assert any("DbC role: invariant" in p for p in G.scan(skill_dir))


# --- CLI surface --------------------------------------------------------------


def test_main_reports_drift_on_stderr_and_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/cross-cutting-axes.md", "- **Invariant**", "- **Always-true**")
    assert G.main(["--skill-dir", str(skill_dir)]) == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "FAIL:" in err


def test_main_exits_two_when_the_check_cannot_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / "references/cross-cutting-axes.md").unlink()
    assert G.main(["--skill-dir", str(skill_dir)]) == 2
    assert "failing closed" in capsys.readouterr().err


# --- "the other N axes" cross-reference lock ---------------------------------


def test_stale_other_axes_cross_reference_fails(tmp_path: Path) -> None:
    """The exact drift an audit round caught: the declaration stayed correct
    while a second count elsewhere in the same file went stale."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "the other four axes", "the other three axes")
    problems = G.scan(skill_dir)
    assert any("'the other three axes' but 4 other" in p for p in problems), problems
    assert not any("cross-cutting axes but carries" in p for p in problems), (
        "the declaration lock must not also fire -- these are two independent counts"
    )


def test_unrecognized_other_axes_word_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "the other four axes", "the other several axes")
    assert any("not a recognized number word" in p for p in G.scan(skill_dir))


def test_absent_other_axes_cross_reference_is_silence_not_a_finding(tmp_path: Path) -> None:
    """These cross-references are optional, unlike the declaration."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "SKILL.md", "the other four axes", "the sibling axes")
    assert G.scan(skill_dir) == []


# --- security-level.md "narrower than all N" cross-reference lock -------------


def test_stale_security_level_count_fails(tmp_path: Path) -> None:
    """The exact class of drift a real audit already caught three times in this
    repository's own history ("than all four" -> "than all six" -> "than all
    seven"), left unlocked by check 4b's own scope (SKILL.md only) until this
    check closed it."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/security-level.md", "than all seven", "than all six")
    problems = G.scan(skill_dir)
    assert any(
        "says 'narrower than all six' but 7 items" in p and "4 other axis/axes + 3 non-axis items" in p
        for p in problems
    ), problems


def test_unrecognized_security_level_count_word_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, "references/security-level.md", "than all seven", "than all several")
    assert any(
        "references/security-level.md: count declared as 'several', which is not a recognized number word" in p
        for p in G.scan(skill_dir)
    )


def test_missing_security_level_phrase_is_a_finding_not_a_scan_error(tmp_path: Path) -> None:
    """Unlike a missing axis-section heading (a structural precondition this
    gate cannot check anything without), a missing 'narrower than all N:'
    sentence is reported as an ordinary drift finding -- the rest of the
    scan still has useful work to do and should not abort."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "references/security-level.md",
        "This axis's own, distinct question is narrower\nthan all seven:",
        "This axis's own, distinct question is narrower than everything else:",
    )
    problems = G.scan(skill_dir)
    assert any("no 'narrower than all <number>:' sentence found" in p for p in problems), problems


def test_security_level_count_recomputes_with_the_other_axes_count(tmp_path: Path) -> None:
    """A sixth axis growing the "other axes" count from 4 to 5 must also grow
    security-level.md's own expected total from 7 to 8 -- both keyed off the
    same _other_axes_count helper, so they cannot silently diverge from each
    other."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        "SKILL.md",
        G.SKILL_AXIS_HEADING,
        f"### Axis: Invented sixth\n\nBody.\n\n{G.SKILL_AXIS_HEADING}",
    )
    problems = G.scan(skill_dir)
    assert any(
        "says 'narrower than all seven' but 8 items" in p and "5 other axis/axes + 3 non-axis items" in p
        for p in problems
    ), problems

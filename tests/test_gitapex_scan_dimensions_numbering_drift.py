"""CI gate + unit tests for evaluating-deterministic-gate-quality's
dimensions.md numbering/cross-reference lock (issue #1229).

Two layers, deliberately, mirroring `test_gitapex_scan_contract_axis_vocabulary_drift.py`
(issue #949) and `test_gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
(issue #993): an integration test asserting the lock holds against this
repository's own real skill content, and a battery of deliberately corrupted
copies asserting each lock actually fires. A wording gate that has only ever
been run against correct content proves nothing -- it is indistinguishable
from a gate that returns 0 unconditionally.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import gitapex_scan_dimensions_numbering_drift as G
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SKILL_DIR = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"


def _copy_skill(tmp_path: Path) -> Path:
    target = tmp_path / "evaluating-deterministic-gate-quality"
    shutil.copytree(REAL_SKILL_DIR, target)
    return target


def _mutate(skill_dir: Path, relative: str, old: str, new: str, *, count: int = 1) -> None:
    path = skill_dir / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture setup: {old!r} not present in {relative}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")


# --- Integration: the real content passes ------------------------------------


def test_real_skill_content_passes() -> None:
    assert G.scan(REAL_SKILL_DIR) == []


def test_main_on_real_content_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert G.main(["--skill-dir", str(REAL_SKILL_DIR)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_with_no_argv_defaults_to_this_repository() -> None:
    assert G.main([]) == 0


def test_real_content_lane_counts_are_six_and_twenty_four() -> None:
    """Pin the real repository's own current lane spans, so a future
    dimension addition that forgets to update this test file is at least
    forced to look at it -- not itself a drift lock, just a sanity anchor."""
    counts, problems = G.compute_lane_counts(G.read_text(REAL_SKILL_DIR / G.DIMENSIONS_MD))
    assert problems == []
    assert counts == G.LaneCount(shape_max=6, dimension_max=24)


# --- Sequence lock: gap / duplicate / out-of-order ----------------------------


def test_gap_in_shape_check_numbering_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "5. **Untrusted input", "7. **Untrusted input")
    problems = G.scan(skill_dir)
    assert any("expected a contiguous" in p and "shape-check item" in p for p in problems), problems


def test_duplicate_dimension_numbering_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "24. **Deny-path recoverability", "23. **Deny-path recoverability")
    problems = G.scan(skill_dir)
    assert any("dimension item '23.' appears more than once" in p for p in problems), problems


def test_out_of_order_dimension_numbering_fails(tmp_path: Path) -> None:
    """Swap two adjacent dimension numbers' document position (21 and 22),
    keeping the set itself contiguous 7-24 so the gap/duplicate checks stay
    silent -- isolates the ascending-order check on its own."""
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / G.DIMENSIONS_MD
    text = path.read_text(encoding="utf-8")
    text = text.replace("21. **Gate precision", "22. **TEMP_TWENTY_ONE_MARKER", 1)
    text = text.replace("22. **Aggregate-outcome", "21. **Aggregate-outcome", 1)
    text = text.replace("22. **TEMP_TWENTY_ONE_MARKER", "22. **Gate precision", 1)
    path.write_text(text, encoding="utf-8")
    problems = G.scan(skill_dir)
    assert any("expected ascending" in p and "dimension item" in p for p in problems), problems


def test_no_shape_check_items_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / G.DIMENSIONS_MD
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "## Deterministic-shape checks\n",
        "## Deterministic-shape checks\n\nNo items here.\n",
        1,
    )
    # Blank out every "N. **" item between the two headings.
    start = text.index("## Deterministic-shape checks")
    end = text.index("## Probabilistic-maturity dimensions")
    import re as _re

    text = text[:start] + _re.sub(r"^\d+\. \*\*", "X. **", text[start:end], flags=_re.MULTILINE) + text[end:]
    path.write_text(text, encoding="utf-8")
    with pytest.raises(G.ScanError, match="no numbered items found"):
        G.scan(skill_dir)


def test_missing_shape_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "## Deterministic-shape checks", "## Renamed shape section")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.scan(skill_dir)


def test_duplicated_dimension_heading_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.DIMENSIONS_MD,
        "## Probabilistic-maturity dimensions",
        "## Probabilistic-maturity dimensions\n\n## Probabilistic-maturity dimensions",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.scan(skill_dir)


def test_duplicated_shape_heading_is_a_scan_error(tmp_path: Path) -> None:
    """Distinct from the duplicated-END-heading case above: here the
    START heading passed to the shape/dimension boundary lookup is itself
    the one duplicated."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.DIMENSIONS_MD,
        "## Deterministic-shape checks",
        "## Deterministic-shape checks\n\n## Deterministic-shape checks",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.scan(skill_dir)


def test_missing_dimension_heading_entirely_is_a_scan_error(tmp_path: Path) -> None:
    """Renaming the dimension heading away (rather than duplicating it)
    hits the shape-section lookup's own END-heading-not-found branch,
    distinct from `test_missing_shape_heading_is_a_scan_error`'s
    START-heading-not-found branch above."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "## Probabilistic-maturity dimensions", "## Renamed dimension section")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.scan(skill_dir)


def test_no_dimension_items_is_a_scan_error(tmp_path: Path) -> None:
    """Mirrors `test_no_shape_check_items_is_a_scan_error` for the other
    lane: the dimension section's own items all blanked out, while the
    shape-check lane stays intact."""
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / G.DIMENSIONS_MD
    text = path.read_text(encoding="utf-8")
    start = text.index("## Probabilistic-maturity dimensions")
    import re as _re

    text = text[:start] + _re.sub(r"^\d+\. \*\*", "X. **", text[start:], flags=_re.MULTILINE)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(G.ScanError, match="no numbered items found"):
        G.scan(skill_dir)


# --- Lane range-declaration lock -----------------------------------------------


def test_stale_shape_check_range_declaration_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "**Deterministic-shape checks** (1-6)", "**Deterministic-shape checks** (1-5)")
    problems = G.scan(skill_dir)
    assert any("declares shape checks '(1-5)' but 6 shape-check item(s)" in p for p in problems), problems


def test_stale_dimension_range_declaration_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.DIMENSIONS_MD,
        "**Probabilistic-maturity dimensions** (7-24)",
        "**Probabilistic-maturity dimensions** (7-23)",
    )
    problems = G.scan(skill_dir)
    assert any("declares dimensions '(7-23)' but 18 dimension item(s)" in p for p in problems), problems


def test_missing_shape_range_declaration_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "**Deterministic-shape checks** (1-6)", "Deterministic-shape checks (1-6)")
    problems = G.scan(skill_dir)
    assert any("shape-check range lock cannot run" in p for p in problems), problems


def test_missing_dimension_range_declaration_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.DIMENSIONS_MD,
        "**Probabilistic-maturity dimensions** (7-24)",
        "Probabilistic-maturity dimensions (7-24)",
    )
    problems = G.scan(skill_dir)
    assert any("dimension range lock cannot run" in p for p in problems), problems


# --- Cross-reference lock -------------------------------------------------------


def test_dimension_reference_beyond_the_real_max_fails_in_dimensions_md(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "dimension 10 already cite", "dimension 99 already cite")
    problems = G.scan(skill_dir)
    assert any("cites 'dimension 99' but dimensions are only numbered 7-24" in p for p in problems), problems


def test_dimension_reference_naming_a_shape_check_number_fails(tmp_path: Path) -> None:
    """A 'dimension N' citation where N is really a shape-check's own
    number is the category-confusion case this lock exists to catch, not
    only a plainly out-of-range one."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "dimension 10 already cite", "dimension 3 already cite")
    problems = G.scan(skill_dir)
    assert any("cites 'dimension 3' but dimensions are only numbered 7-24" in p for p in problems), problems


def test_shape_check_reference_beyond_the_real_max_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "shape check 6's", "shape check 9's")
    problems = G.scan(skill_dir)
    assert any("cites 'shape check 9' but shape checks are only numbered 1-6" in p for p in problems), problems


def test_stale_dimension_reference_in_skill_md_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.SKILL_MD, "dimension 15's ground", "dimension 97's ground")
    problems = G.scan(skill_dir)
    assert any("SKILL.md: cites 'dimension 97'" in p for p in problems), problems


def test_valid_dimension_reference_to_the_newest_dimension_passes(tmp_path: Path) -> None:
    """A reference to the highest real dimension number is legitimate, not
    a false positive -- the range check is inclusive at both ends."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.SKILL_MD, "dimension 15's ground", "dimension 24's ground")
    assert G.scan(skill_dir) == []


# --- Schema lock -----------------------------------------------------------------


def test_stale_schema_dimension_id_maximum_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.SCHEMA_JSON, '"maximum": 24', '"maximum": 23')
    problems = G.scan(skill_dir)
    assert any("dimensionId.maximum is 23 but 24 is the real highest" in p for p in problems), problems


def test_stale_schema_findings_description_range_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.SCHEMA_JSON, "dimensions.md, 1-24", "dimensions.md, 1-23")
    problems = G.scan(skill_dir)
    assert any("cites 'dimensions.md, 1-23' but 24 is the real highest" in p for p in problems), problems


def test_malformed_schema_json_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.SCHEMA_JSON).write_text("{not json", encoding="utf-8")
    with pytest.raises(G.ScanError, match="is not valid JSON"):
        G.scan(skill_dir)


def test_missing_schema_max_node_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.SCHEMA_JSON,
        '"dimensionId": { "type": "integer", "minimum": 1, "maximum": 24 }',
        '"dimensionId": {}',
    )
    with pytest.raises(G.ScanError, match="no node at"):
        G.scan(skill_dir)


def test_non_string_schema_description_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / G.SCHEMA_JSON
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["findings"]["description"] = 12345
    path.write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(G.ScanError, match="is not a string"):
        G.scan(skill_dir)


def test_schema_description_with_no_range_span_fails(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    path = skill_dir / G.SCHEMA_JSON
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["findings"]["description"] = "One entry per dimension actually assessed."
    path.write_text(json.dumps(schema), encoding="utf-8")
    problems = G.scan(skill_dir)
    assert any("schema range-citation lock cannot run" in p for p in problems), problems


# --- A whole new dimension landing correctly should still pass -----------------


def test_scan_passes_after_a_well_formed_dimension_25_lands(tmp_path: Path) -> None:
    """Every dependent citation moved together for a hypothetical dimension
    25 -- the lock should hold, proving it is not simply hardcoded to 24."""
    skill_dir = _copy_skill(tmp_path)
    _mutate(
        skill_dir,
        G.DIMENSIONS_MD,
        "which artifact is currently under review.\n24. **Deny-path recoverability",
        "which artifact is currently under review.\n25. **Invented follow-on dimension.** Body text.\n24. **Deny-path recoverability",
    )
    # The insert above lands dimension 25 BEFORE 24 in document order but
    # numbered higher -- fix numbering by renumbering in real document
    # order instead: simplest is to append after 24's own body ends.
    text = (skill_dir / G.DIMENSIONS_MD).read_text(encoding="utf-8")
    text = text.replace(
        "which artifact is currently under review.\n25. **Invented follow-on dimension.** Body text.\n24. **Deny-path recoverability",
        "which artifact is currently under review.\n24. **Deny-path recoverability",
    )
    text = text.rstrip("\n") + "\n25. **Invented follow-on dimension.** Body text for a hypothetical dimension.\n"
    text = text.replace("**Probabilistic-maturity dimensions** (7-24)", "**Probabilistic-maturity dimensions** (7-25)")
    (skill_dir / G.DIMENSIONS_MD).write_text(text, encoding="utf-8")
    _mutate(skill_dir, G.SCHEMA_JSON, '"maximum": 24', '"maximum": 25')
    _mutate(skill_dir, G.SCHEMA_JSON, "dimensions.md, 1-24", "dimensions.md, 1-25")
    assert G.scan(skill_dir) == []


# --- Fail-closed input handling ---------------------------------------------


def test_missing_dimensions_md_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.DIMENSIONS_MD).unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.scan(skill_dir)


def test_missing_skill_md_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.SKILL_MD).unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.scan(skill_dir)


def test_missing_schema_json_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.SCHEMA_JSON).unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.scan(skill_dir)


def test_non_utf8_file_is_a_scan_error(tmp_path: Path) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.DIMENSIONS_MD).write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(G.ScanError, match="could not decode as UTF-8"):
        G.scan(skill_dir)


# --- CLI surface --------------------------------------------------------------


def test_main_reports_drift_on_stderr_and_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    _mutate(skill_dir, G.DIMENSIONS_MD, "**Deterministic-shape checks** (1-6)", "**Deterministic-shape checks** (1-5)")
    assert G.main(["--skill-dir", str(skill_dir)]) == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "FAIL:" in err


def test_main_exits_two_when_the_check_cannot_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_dir = _copy_skill(tmp_path)
    (skill_dir / G.DIMENSIONS_MD).unlink()
    assert G.main(["--skill-dir", str(skill_dir)]) == 2
    assert "failing closed" in capsys.readouterr().err

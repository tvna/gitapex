"""Tests for the independent-review-pending heading drift gate
(.github/scripts/gitapex_scan_independent_review_heading_drift.py).

The final test is the gate itself: the repository's real target files must
be drift-free. The rest unit-test the detector with fixtures.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_independent_review_pending as gate
import gitapex_scan_independent_review_heading_drift as drift
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_MARKER = "## " + gate.CANONICAL_HEADING_TEXT
_LEGACY_TEXT = drift._LEGACY_HEADING_TEXTS[0]

# The first target file is a Markdown target (skills/drafting-a-pr-to-merge/
# SKILL.md); the third is not (.gitapex/ssot.json) -- used below to exercise
# the Markdown-only HTML-comment/fence stripping on the right kind of target.
_MARKDOWN_TARGET = drift._TARGET_FILES[0]
_NON_MARKDOWN_TARGET = drift._TARGET_FILES[2]


def _write_clean_fixture(root: pathlib.Path) -> None:
    for relative in drift._TARGET_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"some prose\n\n{_MARKER}\n\nmore prose\n", encoding="utf-8")


def test_clean_fixture_has_no_drift(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    assert drift.find_drift(tmp_path) == []


def test_missing_marker_is_reported(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text("no heading here at all\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert str(_MARKDOWN_TARGET) in findings[0]
    assert _MARKER in findings[0]


def test_every_target_file_is_independently_checked(tmp_path: pathlib.Path) -> None:
    # Empty root -- none of the four target files exist at all.
    findings = drift.find_drift(tmp_path)
    assert len(findings) == len(drift._TARGET_FILES)


def test_missing_target_file_fails_closed(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).unlink()
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "file not found" in findings[0]


def test_undecodable_target_file_fails_closed_not_skipped(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_bytes(b"\xff\xfe bad")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "could not read" in findings[0]


def test_legacy_text_alone_is_reported_as_both_missing_and_stale(tmp_path: pathlib.Path) -> None:
    # Regression (deterministic-gate-quality review, issue #1343): the
    # first drafted version of this gate checked only "is the canonical
    # marker present", so a file carrying the retired heading and nothing
    # else read as clean-ish (one finding: marker missing) instead of
    # flagging the retired text itself. A file with only the legacy text
    # is missing the canonical marker AND still carries the retired one --
    # both must be reported.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(f"## {_LEGACY_TEXT}\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 2
    assert any("does not contain the canonical heading marker" in f for f in findings)
    assert any("still contains the retired heading text" in f for f in findings)


def test_legacy_text_alongside_canonical_marker_is_reported(tmp_path: pathlib.Path) -> None:
    # The one-directional-check gap itself: BOTH the canonical marker and
    # a retired heading text present in the same file (an incomplete
    # migration that left the old text behind) must not read as clean
    # just because the new marker is also there.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(f"{_MARKER}\n\n## {_LEGACY_TEXT}\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "still contains the retired heading text" in findings[0]
    assert str(_MARKDOWN_TARGET) in findings[0]


def test_marker_inside_html_comment_on_markdown_target_does_not_count_as_live(tmp_path: pathlib.Path) -> None:
    # A Markdown-target marker hidden inside an HTML comment renders as
    # nothing at all on GitHub -- dead text, not a live heading -- so it
    # must not satisfy the presence check.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(f"prose\n\n<!--\n{_MARKER}\n-->\n\nmore prose\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "does not contain the canonical heading marker" in findings[0]


def test_marker_inside_fenced_block_on_markdown_target_does_not_count_as_live(tmp_path: pathlib.Path) -> None:
    # Same reasoning as the HTML-comment case, for a fenced code block --
    # an illustrative example, not a live section.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(f"prose\n\n```\n{_MARKER}\n```\n\nmore prose\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "does not contain the canonical heading marker" in findings[0]


def test_marker_inside_html_comment_on_non_markdown_target_still_counts(tmp_path: pathlib.Path) -> None:
    # HTML-comment/fence stripping is Markdown-only (module docstring):
    # a non-Markdown target (e.g. ssot.json) has no such convention, so a
    # literal `<!-- ... -->`-shaped substring in its own text is not
    # special-cased away -- it is searched as plain text, unchanged.
    _write_clean_fixture(tmp_path)
    (tmp_path / _NON_MARKDOWN_TARGET).write_text(f"prose <!-- {_MARKER} --> more\n", encoding="utf-8")
    assert drift.find_drift(tmp_path) == []


def test_repository_target_files_are_drift_free() -> None:
    """The gate: real target files must carry the current canonical heading
    and none of the retired ones."""
    findings = drift.find_drift(REPO_ROOT)
    assert findings == [], f"independent-review-pending heading drift found: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No independent-review-pending heading drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        drift,
        "find_drift",
        lambda: ["skills/drafting-a-pr-to-merge/SKILL.md: does not contain the canonical heading marker"],
    )
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "Independent-review-pending heading drift" in out
    assert "skills/drafting-a-pr-to-merge/SKILL.md" in out

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


def _write_clean_fixture(root: pathlib.Path) -> None:
    for relative in drift._TARGET_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"some prose\n\n{_MARKER}\n\nmore prose\n", encoding="utf-8")


def test_clean_fixture_has_no_drift(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    assert drift.find_drift(tmp_path) == []


def test_one_stale_file_is_reported(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    stale_path = tmp_path / drift._TARGET_FILES[0]
    stale_path.write_text("## Step 8 independent review verdict\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert str(drift._TARGET_FILES[0]) in findings[0]
    assert _MARKER in findings[0]


def test_every_target_file_is_independently_checked(tmp_path: pathlib.Path) -> None:
    # Empty root -- none of the four target files exist at all.
    findings = drift.find_drift(tmp_path)
    assert len(findings) == len(drift._TARGET_FILES)


def test_missing_target_file_fails_closed(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / drift._TARGET_FILES[0]).unlink()
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "file not found" in findings[0]


def test_undecodable_target_file_fails_closed_not_skipped(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / drift._TARGET_FILES[0]).write_bytes(b"\xff\xfe bad")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "could not read" in findings[0]


def test_repository_target_files_are_drift_free() -> None:
    """The gate: real target files must carry the current canonical heading."""
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

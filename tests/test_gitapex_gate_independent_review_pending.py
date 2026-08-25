"""Tests for the independent-review-pending required status check
(.github/scripts/gitapex_gate_independent_review_pending.py).

Issue #1311 (Repair 5 of retrospective #1286): a PR must not be mergeable
between transitioning out of draft and drafting-a-pr-to-merge's own Step 8
independent-review verdict actually being recorded against the PR's
current head commit.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_independent_review_pending as gate
import pytest
from conftest import FakeStdin as _FakeStdin

_SHA = "abc123def456abc123def456abc123def456abc"
_OTHER_SHA = "1111111111111111111111111111111111111111"[:40]

_CLEAN_BODY = f"""## Summary

Some PR body text.

## Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}

## Checklist

- [x] Tests pass locally
"""

_NO_SECTION_BODY = "## Summary\n\nJust a normal PR body, no verdict section at all.\n"

_MISSING_VERDICT_FIELD_BODY = f"""## Step 8 independent review verdict

- Verified commit: {_SHA}
"""

_MISSING_COMMIT_FIELD_BODY = """## Step 8 independent review verdict

- Verdict: CLEAN
"""

_NOT_CLEAN_BODY = f"""## Step 8 independent review verdict

- Verdict: FINDING-PENDING
- Verified commit: {_SHA}
"""

_STALE_BODY = f"""## Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_OTHER_SHA}
"""

_EMPHASIS_BODY = f"""## Step 8 independent review verdict

- Verdict: **CLEAN**
- Verified commit: `{_SHA}`
"""

_TWO_SECTIONS_BODY = f"""## Step 8 independent review verdict

- Verdict: FINDING-PENDING
- Verified commit: {_OTHER_SHA}

## Fixed and re-reviewed

## Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""

_HEADING_DIFFERENT_LEVEL_BODY = f"""### Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}
"""

_SECTION_FOLLOWED_BY_ANOTHER_HEADING_BODY = f"""## Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA}

## Related Issue

Closes #1311
"""


def test_parse_verdict_finds_clean_section() -> None:
    verdict = gate.parse_verdict(_CLEAN_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA
    assert verdict.error is None


def test_parse_verdict_no_section() -> None:
    verdict = gate.parse_verdict(_NO_SECTION_BODY)
    assert verdict.error == "no '## Step 8 independent review verdict' section found"


def test_parse_verdict_missing_verdict_field() -> None:
    verdict = gate.parse_verdict(_MISSING_VERDICT_FIELD_BODY)
    assert verdict.error == "verdict section found but has no 'Verdict:' line"


def test_parse_verdict_missing_commit_field() -> None:
    verdict = gate.parse_verdict(_MISSING_COMMIT_FIELD_BODY)
    assert verdict.error == "verdict section found but has no 'Verified commit:' line"


def test_parse_verdict_missing_both_fields() -> None:
    verdict = gate.parse_verdict("## Step 8 independent review verdict\n\nNothing here.\n")
    assert verdict.error == "verdict section found but has neither a 'Verdict:' nor a 'Verified commit:' line"


def test_parse_verdict_tolerates_emphasis_markup() -> None:
    verdict = gate.parse_verdict(_EMPHASIS_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_uses_last_section_when_multiple_present() -> None:
    verdict = gate.parse_verdict(_TWO_SECTIONS_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_does_not_leak_into_next_heading() -> None:
    # A body where the verdict section is immediately followed by another
    # heading must not accidentally read fields from that next section.
    verdict = gate.parse_verdict(_SECTION_FOLLOWED_BY_ANOTHER_HEADING_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_parse_verdict_matches_any_heading_level() -> None:
    verdict = gate.parse_verdict(_HEADING_DIFFERENT_LEVEL_BODY)
    assert verdict.status == "CLEAN"
    assert verdict.commit == _SHA


def test_check_passes_on_matching_clean_verdict() -> None:
    passed, message = gate.check(_CLEAN_BODY, _SHA)
    assert passed is True
    assert _SHA in message


def test_check_fails_on_no_section() -> None:
    passed, message = gate.check(_NO_SECTION_BODY, _SHA)
    assert passed is False
    assert "no '## Step 8" in message


def test_check_fails_on_non_clean_verdict() -> None:
    passed, message = gate.check(_NOT_CLEAN_BODY, _SHA)
    assert passed is False
    assert "not CLEAN" in message


def test_check_fails_on_stale_commit() -> None:
    passed, message = gate.check(_STALE_BODY, _SHA)
    assert passed is False
    assert "stale verdict" in message


def test_check_fails_on_empty_head_sha() -> None:
    passed, message = gate.check(_CLEAN_BODY, "")
    assert passed is False
    assert "no --head-sha" in message


def test_check_is_case_insensitive_on_verdict_and_commit() -> None:
    body = f"""## Step 8 independent review verdict

- verdict: clean
- verified commit: {_SHA.upper()}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_check_matches_abbreviated_recorded_sha_against_full_head_sha() -> None:
    body = f"""## Step 8 independent review verdict

- Verdict: CLEAN
- Verified commit: {_SHA[:12]}
"""
    passed, _ = gate.check(body, _SHA)
    assert passed is True


def test_main_body_file_pass(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = gate.main(["--body", str(body_file), "--head-sha", _SHA])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_body_file_fail(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text(_NO_SECTION_BODY, encoding="utf-8")
    exit_code = gate.main(["--body", str(body_file), "--head-sha", _SHA])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_missing_body_file_errors(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = gate.main(["--body", "/nonexistent/path.txt", "--head-sha", _SHA])
    assert exit_code == 1
    assert "file not found" in capsys.readouterr().err


def test_main_stdin_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_CLEAN_BODY.encode("utf-8")))
    exit_code = gate.main(["--head-sha", _SHA])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_stdin_undecodable_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    exit_code = gate.main(["--head-sha", _SHA])
    assert exit_code == 1
    assert "not valid UTF-8" in capsys.readouterr().err

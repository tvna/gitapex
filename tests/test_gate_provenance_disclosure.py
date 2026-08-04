"""Tests for the provenance disclosure gate
(.github/scripts/gate_provenance_disclosure.py).

Issue #520 (row 3, refs #350): a review-response draft or doc/PR-body diff
must not name a specific tool's absence/presence as an evidence-limitation
reason without an owner-disclosure marker in the same diff.
"""

from __future__ import annotations

import gate_provenance_disclosure as gate
from conftest import FakeStdin as _FakeStdin

_UNDISCLOSED_NOTE = (
    "The reviewing context had already read the full rubric, so this evaluation "
    "notes the absence of a registered skill invocation and a generic dispatch "
    "tool as the reason a prior run's judgment could not be reused directly.\n"
)

_DISCLOSED_NOTE = (
    _UNDISCLOSED_NOTE
    + "\n"
    + "tool-fingerprint-disclosure: WAIVED: owner approved disclosing this in "
    "review on 2026-07-25\n"
)

_CLEAN_NOTE = (
    "The reviewing context had already read the full rubric and its iteration "
    "history, so reusing it would not meet the skill's own isolation bar.\n"
)

_LIMITATION_WITHOUT_TOOL_CUE = (
    "This section notes the absence of a clear owner decision on rollout timing.\n"
)

_TOOL_CUE_WITHOUT_LIMITATION = (
    "The generic dispatch tool routed the request to the correct subagent.\n"
)


def test_find_offending_paragraphs_flags_undisclosed_note():
    assert len(gate.find_offending_paragraphs(_UNDISCLOSED_NOTE)) == 1


def test_find_offending_paragraphs_ignores_clean_note():
    assert gate.find_offending_paragraphs(_CLEAN_NOTE) == []


def test_find_offending_paragraphs_requires_both_cues():
    assert gate.find_offending_paragraphs(_LIMITATION_WITHOUT_TOOL_CUE) == []
    assert gate.find_offending_paragraphs(_TOOL_CUE_WITHOUT_LIMITATION) == []


def test_has_disclosure_marker():
    assert gate.has_disclosure_marker(_DISCLOSED_NOTE) is True
    assert gate.has_disclosure_marker(_UNDISCLOSED_NOTE) is False


def test_has_disclosure_marker_requires_non_empty_reason():
    text = "tool-fingerprint-disclosure: WAIVED:\n"
    assert gate.has_disclosure_marker(text) is False


def test_main_stdin_pass(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_CLEAN_NOTE.encode("utf-8")))
    exit_code = gate.main([])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_stdin_fail(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_UNDISCLOSED_NOTE.encode("utf-8")))
    exit_code = gate.main([])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_stdin_undecodable_errors(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    exit_code = gate.main([])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_body_file_disclosed_passes(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_DISCLOSED_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_body_file_missing_errors(tmp_path, capsys):
    exit_code = gate.main(["--body", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_body_file_undecodable_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_bytes(b"\xff\xfe bad")
    exit_code = gate.main(["--body", str(body)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(body) in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_diff_added_file_undecodable_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_bytes(b"\xff\xfe bad")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(diff_added) in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_diff_added_missing_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_marker_in_diff_added_covers_offense_in_body(tmp_path, capsys):
    """The disclosure marker can live in either source; the check applies
    to the combined corpus, matching the ACM's own "same diff" framing."""
    body = tmp_path / "body.md"
    body.write_text(_UNDISCLOSED_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_text(
        "tool-fingerprint-disclosure: WAIVED: owner approved\n", encoding="utf-8"
    )
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_offense_in_diff_added_with_no_marker_fails(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_text(_UNDISCLOSED_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "absence of a registered skill invocation" in err.lower()

"""Read-path tests for hooks/check_skill_audit_disclosure_or_waiver.py's
main().

tests/test_check_skill_audit_disclosure_hook_sync.py already covers this
module's regex/verdict parity with the CI gate it partially mirrors; it
does not exercise main()'s own --body/stdin read path. This file pins
that path's documented non-UTF-8 behavior only -- kept separate to keep
the sync test focused on parity, matching this repo's convention of one
concern per test module.
"""

from __future__ import annotations

import pathlib

import check_skill_audit_disclosure_or_waiver as checker
import pytest
from conftest import FakeStdin as _FakeStdin


def test_main_reports_error_for_non_utf8_body_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe bad")
    assert checker.main(["--body", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert checker.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err

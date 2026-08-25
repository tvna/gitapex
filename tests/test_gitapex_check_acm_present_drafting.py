"""Read-path tests for skills/drafting-issues/scripts/gitapex_check_acm_present.py's main().

Colocating this test next to the script (as skills/drafting-issues/
scripts/test_check_acm_present.py) would not be collected by CI: pyproject.toml's
[tool.pytest.ini_options] testpaths does not include that directory, so a bare
`pytest` invocation (exactly what .github/workflows/test.yml runs) never
discovers a test file placed there. tests/ is in testpaths, so this lives here
instead, loaded by file path with a module name unique to this copy -- an
identically-named skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py
exists, and a bare top-level import would collide with it -- the same
technique tests/test_gitapex_check_acm_present_sync.py's own _load_module already
uses for this exact pair of files.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from conftest import FakeStdin as _FakeStdin

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "skills"
    / "drafting-issues"
    / "scripts"
    / "gitapex_check_acm_present.py"
)

_spec = importlib.util.spec_from_file_location("_drafting_issues_check_acm_present", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


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

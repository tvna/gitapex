"""Read-path tests for skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py's
main().

skills/outward-artifact-preflight/scripts/ is not on pyproject.toml's
pythonpath (unlike the handful of skills/*/scripts/ directories that
are), so this loads the module by file path rather than a plain
top-level import -- the same technique
tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py's own _load_module
already uses for hooks/, which is not on pythonpath either.

tests/test_gitapex_gate_provenance_disclosure.py exists but covers a different
script (.github/scripts/gitapex_gate_provenance_disclosure.py); this file is
scoped to gitapex_scan_provenance.py's own main() only.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
from conftest import FakeStdin as _FakeStdin

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SCRIPT_PATH = REPO_ROOT / "skills" / "outward-artifact-preflight" / "scripts" / "gitapex_scan_provenance.py"

_spec = importlib.util.spec_from_file_location("_outward_artifact_preflight_scan_provenance", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
gitapex_scan_provenance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gitapex_scan_provenance)


def test_main_reports_error_for_non_utf8_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "artifact.md"
    path.write_bytes(b"\xff\xfe bad")
    assert gitapex_scan_provenance.main(["--file", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gitapex_scan_provenance.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gitapex_scan_provenance.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err

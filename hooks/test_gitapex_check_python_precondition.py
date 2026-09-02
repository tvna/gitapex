"""Direct-import regression suite for gitapex_check_python_precondition.py's
own is_importable()/find_missing_modules()/main() (issue #1566, closes
#1547(a)).

Named to match the direct-import-suite half of the pattern
hooks/test_gitapex_check_pr_duplicate_issue.py's own docstring describes:
a subprocess-only test cannot easily assert on the in-process
is_importable()/find_missing_modules() helpers or exercise the
argv-vs-stdin branch directly, so this file imports the checker module
in-process instead. hooks/test_gitapex_check_pr_skill_audit_disclosure_shell.py
covers the wrapping shell hook's own end-to-end deny/warn behavior.
"""

from __future__ import annotations

import io
import json
import sys

import gitapex_check_python_precondition as checker
import pytest

_FAKE_MODULE = "this_module_does_not_exist_xyz"


# --- is_importable() ---


def test_is_importable_true_for_a_real_stdlib_module() -> None:
    assert checker.is_importable("json") is True


def test_is_importable_false_for_a_fake_module_name() -> None:
    assert checker.is_importable(_FAKE_MODULE) is False


def test_is_importable_probes_in_a_subprocess_not_this_process() -> None:
    """A missing module must not be able to crash this checker itself --
    the whole reason for the subprocess-probe design. If is_importable()
    ever imported the module directly in this process (rather than
    probing it in a separate `python3` subprocess), this fake module name
    would either raise ModuleNotFoundError right here instead of cleanly
    returning False, or leave a trace behind in this process's own
    sys.modules. Neither happens: the probe runs elsewhere."""
    assert _FAKE_MODULE not in sys.modules
    assert checker.is_importable(_FAKE_MODULE) is False
    assert _FAKE_MODULE not in sys.modules


# --- find_missing_modules() ---


def test_find_missing_modules_reports_each_module_independently() -> None:
    """Multiple module names in one call are each reported independently:
    two importable, one fake, in a mixed order -- only the fake one comes
    back, in input order."""
    result = checker.find_missing_modules(["json", _FAKE_MODULE, "sys"])
    assert result == [_FAKE_MODULE]


def test_find_missing_modules_empty_when_all_importable() -> None:
    assert checker.find_missing_modules(["json", "sys", "os"]) == []


def test_find_missing_modules_all_missing_when_none_importable() -> None:
    result = checker.find_missing_modules([_FAKE_MODULE, "another_fake_module_xyz"])
    assert result == [_FAKE_MODULE, "another_fake_module_xyz"]


# --- main(): argv path ---


def test_main_exits_zero_and_reports_no_missing_modules(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = checker.main(["json", "sys"])
    assert exit_code == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout == {"missing": []}


def test_main_exits_one_and_reports_the_missing_module(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = checker.main(["json", _FAKE_MODULE])
    assert exit_code == 1
    captured = capsys.readouterr()
    stdout = json.loads(captured.out)
    assert stdout == {"missing": [_FAKE_MODULE]}
    assert "FAIL" in captured.err
    assert _FAKE_MODULE in captured.err


def test_main_stdout_is_a_single_json_line_only(capsys: pytest.CaptureFixture[str]) -> None:
    """A caller (the shell hook, via jq) parses stdout directly as JSON;
    it must never carry a second, non-JSON line."""
    checker.main(["json"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    json.loads(lines[0])


# --- main(): stdin fallback path ---


def test_main_reads_module_names_from_stdin_when_argv_is_empty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(f"json\n{_FAKE_MODULE}\nsys\n"))
    exit_code = checker.main([])
    assert exit_code == 1
    stdout = json.loads(capsys.readouterr().out)
    assert stdout == {"missing": [_FAKE_MODULE]}


def test_main_stdin_ignores_blank_lines(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\njson\n\n  \nsys\n"))
    exit_code = checker.main([])
    assert exit_code == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout == {"missing": []}

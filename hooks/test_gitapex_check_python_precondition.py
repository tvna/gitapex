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
import pathlib
import subprocess
import sys
import time

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


def test_is_importable_false_and_warns_when_the_interpreter_cannot_launch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The `python` executable itself may not be launchable at all (not on
    PATH, not executable) -- distinct from the module simply being
    missing. `subprocess.run` raises OSError in that case; this must be
    caught and treated as a fail-closed "cannot confirm importable"
    signal (False), with a warning naming what could not be launched, not
    an uncaught exception escaping this checker."""
    assert checker.is_importable("json", python="/nonexistent/not-a-real-interpreter") is False
    captured = capsys.readouterr()
    assert "could not launch" in captured.err
    assert "/nonexistent/not-a-real-interpreter" in captured.err


def test_is_importable_is_bounded_when_a_modules_import_blocks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Defeat case (step-8 adversarial review, issue #1566).** The exact
    condition this probe exists to catch -- a declared package `python3`
    cannot actually use -- reshaped to fall just outside the probe's own
    `returncode == 0` heuristic: a module that neither imports nor fails,
    because its own import-time code blocks (a network call, a lock, a
    `time.sleep`).

    Before this bound existed, `subprocess.run` was called with no
    `timeout`, so such a module stalled the probe indefinitely. That
    probe runs inside `check-pr-skill-audit-disclosure.sh`, a
    PreToolUse hook firing on every `mcp__github__create_pull_request` /
    `update_pull_request` call in this repository -- so an unbounded probe
    hangs the operation the hook is gating, with no message at all. That
    is strictly worse than the silent tier-2 degrade #1547(a) reports,
    since it produces no verdict whatsoever.

    A blocking import must therefore be bounded and treated exactly like
    the already-handled `OSError` case: fail closed to "cannot confirm
    this is importable" (`False`), with a warning naming what happened."""
    blocker = tmp_path / "gitapex_blocking_import_probe.py"
    blocker.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    started = time.monotonic()
    result = checker.is_importable("gitapex_blocking_import_probe", timeout=1.0)
    elapsed = time.monotonic() - started

    assert result is False
    assert elapsed < 15, f"the probe was not bounded: it took {elapsed:.1f}s for a module that never finishes importing"
    assert "timed out" in capsys.readouterr().err


def test_is_importable_default_timeout_is_pinned() -> None:
    """The default bound is a hang guard, not a budget: a real import
    completes in well under a second. Pinned so a later edit cannot
    silently remove or balloon it back toward "effectively unbounded"."""
    assert checker.PROBE_TIMEOUT_SECONDS == 10.0


def test_find_missing_modules_reports_a_blocking_module_as_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The timeout's fail-closed posture must reach the caller-facing API,
    not stop at `is_importable`: a module whose import blocks is reported
    as missing, so the hook denies with an actionable message rather than
    hanging or silently passing."""
    blocker = tmp_path / "gitapex_blocking_import_probe2.py"
    blocker.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    assert checker.find_missing_modules(["gitapex_blocking_import_probe2"], timeout=1.0) == [
        "gitapex_blocking_import_probe2"
    ]


def test_is_importable_kills_the_probe_process_on_timeout(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`subprocess.run`'s own documented timeout behavior kills the child
    before re-raising, so a timed-out probe leaves no orphaned `python3`
    holding the pipes open. Asserted through the observable consequence:
    the call returns rather than blocking on the child's still-open
    stdout/stderr pipes, which is what `capture_output=True` would
    otherwise wait on."""
    blocker = tmp_path / "gitapex_blocking_import_probe3.py"
    blocker.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    started = time.monotonic()
    assert checker.is_importable("gitapex_blocking_import_probe3", timeout=1.0) is False
    assert time.monotonic() - started < 15


def test_is_importable_false_and_warns_on_a_manufactured_timeout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `TimeoutExpired` branch itself, isolated from real timing --
    matching tests/test__gitapex_preconditions.py's own manufactured-
    timeout style for its sibling git probe."""

    def _hang(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd="python3 -c ...", timeout=10.0)

    monkeypatch.setattr(subprocess, "run", _hang)

    assert checker.is_importable("pydantic") is False
    captured = capsys.readouterr()
    assert "timed out" in captured.err
    assert "pydantic" in captured.err


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

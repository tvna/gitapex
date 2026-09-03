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


def _fake_blocking_interpreter(tmp_path: pathlib.Path) -> str:
    """Write and return the path to a fake `python3`-shaped executable that
    ignores its own argv and sleeps well past any timeout this suite uses --
    standing in for a real interpreter whose probed module blocks at import
    time (a network call, a lock, a `time.sleep`).

    Earlier versions of these tests placed a real blocking `.py` fixture on
    the probe subprocess's own search path via `monkeypatch.setenv(
    "PYTHONPATH", ...)`. That stopped working once `-I` (isolated mode) was
    added to the real probe's own `subprocess.run` argv (the shadow-file
    security fix above): `-I` unconditionally ignores `PYTHONPATH`, so a
    fixture module placed there can no longer reach the probe subprocess at
    all -- it would simply report "not importable" immediately, never
    reaching the blocking code path this suite exists to exercise. The
    behavior under test here -- the probe not returning before `timeout` --
    does not depend on *why* a real interpreter would stall, so substituting
    the whole interpreter with one that unconditionally sleeps is a
    faithful, `-I`-independent reproduction. `exec`'d via a `python3` shebang
    (rather than a shell wrapping a separate `sleep` process) so the process
    `subprocess.run`'s timeout kills is the same process that was sleeping,
    with nothing left orphaned behind it."""
    script = tmp_path / "fake_blocking_python3"
    script.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


# --- is_importable() ---


def test_is_importable_true_for_a_real_stdlib_module() -> None:
    assert checker.is_importable("json") is True


def test_is_importable_false_for_a_fake_module_name() -> None:
    assert checker.is_importable(_FAKE_MODULE) is False


def test_is_importable_default_python_is_this_processs_own_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (issue #1697): the default `python` must be
    `sys.executable`, not a fresh `python3` PATH lookup -- a PreToolUse
    hook's own shell can resolve a bare `python3` from a PATH lacking the
    uv-managed .venv this checker itself was launched from, causing a
    false "cannot import" even though the venv genuinely has the
    package. Asserted by intercepting `subprocess.run`'s own argv rather
    than the return value, so this fails loudly if a future edit
    reintroduces a literal `"python3"` default."""
    captured: list[list[str]] = []

    def _fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.append(argv)
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    checker.is_importable("json")

    assert captured[0][0] == sys.executable


def test_is_importable_default_falls_back_to_python3_when_sys_executable_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sys.executable` can be an empty string for an embedded interpreter
    (documented CPython behavior) -- that must fall back to the literal
    "python3" rather than launching argv[0] == "" (which OSErrors)."""
    captured: list[list[str]] = []

    def _fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.append(argv)
        return subprocess.CompletedProcess(argv, returncode=0)

    monkeypatch.setattr(sys, "executable", "")
    monkeypatch.setattr(subprocess, "run", _fake_run)
    checker.is_importable("json")

    assert captured[0][0] == "python3"


def test_is_importable_explicit_python_overrides_the_default() -> None:
    """An explicitly passed `python` (e.g. a caller that already resolved
    a specific interpreter) must still win over the `sys.executable`
    default."""
    assert checker.is_importable("json", python=sys.executable) is True


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
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Defeat case (step-8 adversarial review, issue #1566).** The exact
    condition this probe exists to catch -- a declared package `python3`
    cannot actually use -- reshaped to fall just outside the probe's own
    `returncode == 0` heuristic: a probe subprocess that neither imports
    nor fails within the ceiling, because the interpreter's own import-time
    code blocks (a network call, a lock, a `time.sleep`). Reproduced via
    `_fake_blocking_interpreter` -- see its own docstring for why this no
    longer uses a `PYTHONPATH`-injected fixture module.

    Before this bound existed, `subprocess.run` was called with no
    `timeout`, so such a probe stalled indefinitely. That probe runs inside
    `check-pr-skill-audit-disclosure.sh`, a PreToolUse hook firing on every
    `mcp__github__create_pull_request` / `update_pull_request` call in this
    repository -- so an unbounded probe hangs the operation the hook is
    gating, with no message at all. That is strictly worse than the silent
    tier-2 degrade #1547(a) reports, since it produces no verdict
    whatsoever.

    A blocking probe must therefore be bounded and treated exactly like the
    already-handled `OSError` case: fail closed to "cannot confirm this is
    importable" (`False`), with a warning naming what happened."""
    python = _fake_blocking_interpreter(tmp_path)

    started = time.monotonic()
    result = checker.is_importable("gitapex_blocking_import_probe", python=python, timeout=1.0)
    elapsed = time.monotonic() - started

    assert result is False
    assert elapsed < 15, f"the probe was not bounded: it took {elapsed:.1f}s for an interpreter that never returns"
    assert "timed out" in capsys.readouterr().err


def test_is_importable_does_not_shadow_via_the_probes_cwd(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Regression (Step 8 security review, issue #1566, HIGH severity).**
    Before `-I` (isolated mode) was added to the probe's own `subprocess.run`
    argv, `python3 -c` implicitly prepended its own process cwd to
    `sys.path[0]` -- so a file shaped like the probed module's own name,
    planted in whatever directory this checker happened to be invoked from
    (this hook's caller never sets `cwd=` on the probe), would shadow the
    real module and have its own top-level code executed inside the probe
    subprocess (CWE-427/CWE-829 -- an attacker with write access to that
    cwd gets arbitrary code execution inside a PreToolUse hook). Reproduced
    directly here: a `shadow_target.py` planted in a cwd this test
    controls, whose own top-level code writes a marker file if it ever
    runs. `-I` must make this probe report the module as NOT importable
    (there is no real `shadow_target` package on the interpreter's own
    controlled search path) rather than importing -- and executing -- the
    shadow file."""
    marker = tmp_path / "executed.marker"
    shadow = tmp_path / "shadow_target.py"
    shadow.write_text(f"open({json.dumps(str(marker))}, 'w').close()\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = checker.is_importable("shadow_target")

    assert result is False
    assert not marker.exists(), "the shadow file planted in the probe's own cwd was imported and executed"


def test_is_importable_default_timeout_is_pinned() -> None:
    """The default bound is a hang guard, not a budget: a real import
    completes in well under a second. Pinned so a later edit cannot
    silently remove or balloon it back toward "effectively unbounded"."""
    assert checker.PROBE_TIMEOUT_SECONDS == 10.0


def test_find_missing_modules_reports_a_blocking_module_as_missing(tmp_path: pathlib.Path) -> None:
    """The timeout's fail-closed posture must reach the caller-facing API,
    not stop at `is_importable`: a probe that blocks past the ceiling is
    reported as missing, so the hook denies with an actionable message
    rather than hanging or silently passing."""
    python = _fake_blocking_interpreter(tmp_path)

    assert checker.find_missing_modules(["gitapex_blocking_import_probe2"], python=python, timeout=1.0) == [
        "gitapex_blocking_import_probe2"
    ]


def test_is_importable_kills_the_probe_process_on_timeout(tmp_path: pathlib.Path) -> None:
    """`subprocess.run`'s own documented timeout behavior kills the child
    before re-raising, so a timed-out probe leaves no orphaned interpreter
    holding the pipes open. Asserted through the observable consequence:
    the call returns rather than blocking on the child's still-open
    stdout/stderr pipes, which is what `capture_output=True` would
    otherwise wait on."""
    python = _fake_blocking_interpreter(tmp_path)

    started = time.monotonic()
    assert checker.is_importable("gitapex_blocking_import_probe3", python=python, timeout=1.0) is False
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

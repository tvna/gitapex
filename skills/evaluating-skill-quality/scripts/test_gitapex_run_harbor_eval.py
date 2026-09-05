"""Tests for the thin Harbor runner
(skills/evaluating-skill-quality/scripts/gitapex_run_harbor_eval.py,
issue #1813). Co-located with the runner itself.

Scope is deliberately narrow: command assembly (including the promise that
no secret value can enter the argv) and the two preflight exits. Live
`harbor run` behavior is proven by real runs per the Branch Plan, not by
these unit tests.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

import gitapex_run_harbor_eval
import pytest


def test_build_command_defaults() -> None:
    """Default args assemble the exact minimal harbor invocation."""
    args = gitapex_run_harbor_eval.parse_args(["--tasks", "evals/d"])
    assert gitapex_run_harbor_eval.build_command(args) == [
        "uv",
        "run",
        "--group",
        "harbor",
        "harbor",
        "run",
        "-p",
        "evals/d",
        "-a",
        "opencode",
        "-m",
        "opencode/muse-spark-1.3-contributor-free",
    ]


def test_build_command_multipliers() -> None:
    """Non-default multipliers append exactly their two flags."""
    args = gitapex_run_harbor_eval.parse_args(
        [
            "--tasks",
            "evals/d",
            "--agent",
            "claude-code",
            "--model",
            "anthropic/m",
            "--setup-timeout-multiplier",
            "3.0",
            "--build-timeout-multiplier",
            "2.0",
        ]
    )
    cmd = gitapex_run_harbor_eval.build_command(args)
    assert cmd[-4:] == [
        "--agent-setup-timeout-multiplier",
        "3.0",
        "--environment-build-timeout-multiplier",
        "2.0",
    ]
    joined = " ".join(cmd)
    for token in ("API_KEY", "SECRET", "TOKEN="):
        assert token not in joined


def test_main_exits_2_without_docker(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing Docker CLI fails closed with guidance, never a traceback."""
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert gitapex_run_harbor_eval.main(["--tasks", "evals/d"]) == 2
    assert "Docker" in capsys.readouterr().err


def test_main_exits_2_without_harbor(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing harbor fails closed only after Docker itself passes."""

    def fake_which(_name: object) -> str:
        return "/usr/bin/docker"

    def fake_run(_cmd: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if isinstance(_cmd, list) and _cmd[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(args=_cmd, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(
            args=_cmd if isinstance(_cmd, list) else [],
            returncode=1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr("subprocess.run", fake_run)
    assert gitapex_run_harbor_eval.main(["--tasks", "evals/d"]) == 2
    assert "harbor" in capsys.readouterr().err.lower()


def test_main_passes_through_agent_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reached harbor run relays its own exit code unchanged."""
    calls: list[list[str]] = []

    def fake_which(_name: object) -> str:
        return "/usr/bin/docker"

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["docker", "ps"] or cmd[-1:] == ["--version"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=3, stdout="", stderr="")

    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = fake_run
    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr("subprocess.run", runner)
    assert gitapex_run_harbor_eval.main(["--tasks", "evals/d"]) == 3
    assert calls[-1][:6] == ["uv", "run", "--group", "harbor", "harbor", "run"]

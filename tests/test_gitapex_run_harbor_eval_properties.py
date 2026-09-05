"""Gate-contract tests for the thin Harbor runner
(skills/evaluating-skill-quality/scripts/gitapex_run_harbor_eval.py,
issue #1813).

The detailed unit tests live next to the runner itself
(skills/.../scripts/test_gitapex_run_harbor_eval.py). This file exists so
the function-body-test-coverage gate (issue #1498) sees every new function
body of that script referenced by name from a test in the same diff; each
test below is a thin contract check, not a duplicate of the unit suite.
"""

from __future__ import annotations

import gitapex_run_harbor_eval
import pytest


def test_parse_args_defaults() -> None:
    """parse_args fills the documented agent/model defaults."""
    args = gitapex_run_harbor_eval.parse_args(["--tasks", "evals/d"])
    assert args.tasks == "evals/d"
    assert args.agent == "opencode"
    assert args.model == "opencode/muse-spark-1.3-contributor-free"


def test_build_command_minimal() -> None:
    """build_command assembles the harbor invocation in order."""
    args = gitapex_run_harbor_eval.parse_args(["--tasks", "evals/d"])
    cmd = gitapex_run_harbor_eval.build_command(args)
    assert cmd[:6] == ["uv", "run", "--group", "harbor", "harbor", "run"]
    assert "evals/d" in cmd


def test_check_docker_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_docker fails closed with guidance when no Docker CLI exists."""
    monkeypatch.setattr("shutil.which", lambda _name: None)
    problem = gitapex_run_harbor_eval.check_docker()
    assert problem is not None and "Docker" in problem


def test_check_harbor_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """check_harbor fails closed with guidance when harbor is missing."""
    import subprocess

    def fake_run(_cmd: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/uv")
    monkeypatch.setattr("subprocess.run", fake_run)
    problem = gitapex_run_harbor_eval.check_harbor()
    assert problem is not None and "harbor" in problem


def test_main_wiring(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """main runs preflight first and exits 2 before any harbor call."""
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert gitapex_run_harbor_eval.main(["--tasks", "evals/d"]) == 2
    assert capsys.readouterr().err != ""

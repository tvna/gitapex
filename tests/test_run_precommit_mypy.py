"""Tests for the pre-commit mypy runner (.github/scripts/run_precommit_mypy.py).

run_group's own subprocess call is mocked throughout -- these tests exercise
main()'s group-iteration/reporting contract, not a real mypy invocation
(that's covered by CI's own `mypy` job running the real thing against this
repository).
"""

from __future__ import annotations

import subprocess

import pytest
import run_precommit_mypy as runner


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["mypy"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_group_invokes_uv_run_frozen_mypy_with_config_file(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return _completed(0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_group(("tests", "hooks"))
    assert captured["cmd"] == [
        "uv",
        "run",
        "--frozen",
        "mypy",
        "--config-file",
        "pyproject.toml",
        "tests",
        "hooks",
    ]


def test_main_returns_zero_when_every_group_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner, "run_group", lambda dirs: _completed(0))
    rc = runner.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "all groups clean" in out


def test_main_returns_one_and_names_failing_group(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run_group(dirs: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if dirs == ("skills/drafting-an-adr/scripts",):
            return _completed(1, stdout="error: bad type\n")
        return _completed(0)

    monkeypatch.setattr(runner, "run_group", fake_run_group)
    rc = runner.main()
    out, err = capsys.readouterr()
    assert rc == 1
    assert "skills/drafting-an-adr/scripts" in out
    assert "error: bad type" in out
    assert "skills/drafting-an-adr/scripts" in err


def test_main_reports_every_failing_group_not_just_the_first(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner, "run_group", lambda dirs: _completed(1, stdout="x"))
    rc = runner.main()
    err = capsys.readouterr().err
    assert rc == 1
    for label, _dirs in runner.MYPY_GROUPS:
        assert label in err


def test_mypy_groups_cover_the_pythonpath_linked_roots_together() -> None:
    # Regression guard: the first group must stay bundled (not split across
    # separate invocations), since those are exactly the directories that
    # bare-import each other per [tool.pytest.ini_options] pythonpath.
    first_label, first_dirs = runner.MYPY_GROUPS[0]
    assert first_label == "tests + pythonpath-linked roots"
    assert "tests" in first_dirs
    assert ".github/scripts" in first_dirs
    assert "evals/scripts" in first_dirs


def test_mypy_groups_check_every_skill_scripts_directory_named_in_ci() -> None:
    labels = {label for label, _dirs in runner.MYPY_GROUPS}
    for expected in (
        "skills/executing-a-branch-plan/scripts",
        "skills/drafting-an-adr/scripts",
        "skills/auditing-git-hosting-surface/scripts",
        "skills/outward-artifact-preflight/scripts",
        "skills/drafting-an-acm-issue/scripts",
        "skills/planning-a-branch-from-an-issue/scripts",
        "skills/setup-gitapex-toolchain/scripts",
    ):
        assert expected in labels

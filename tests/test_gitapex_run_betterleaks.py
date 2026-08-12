"""Tests for the betterleaks hook runner (.github/scripts/gitapex_run_betterleaks.py).

The subprocess call is mocked throughout: these tests pin main()'s
fail-loudly-and-never-fail-open contract and the argv it builds per mode, not a
real betterleaks invocation. The real scan is verified against the actual binary
and this repository's own history (issue #890's ACM), which no unit test can
stand in for.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import gitapex_run_betterleaks as runner
import pytest
from conftest import make_validation_error


def _completed(returncode: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=["betterleaks"], returncode=returncode)


@pytest.fixture
def stub_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a test off `git rev-parse`, which depends on the caller's cwd.

    Deliberately not `autouse`: a blanket stub left `repo_root`'s own body
    unexecuted by every test at once, which dropped this file under the 90%
    per-file floor `.github/scripts/gitapex_gate_evals_scripts_coverage.py`
    enforces. Requested per test instead, so the real function stays covered by
    the slow test below.
    """
    monkeypatch.setattr(runner, "repo_root", lambda: Path("/repo"))


@pytest.mark.slow
def test_repo_root_resolves_the_real_git_toplevel() -> None:
    # Spawns real git, hence `slow` per this repository's own marker
    # definition. Asserted against git's own answer rather than a hard-coded
    # path so it holds in any checkout location.
    expected = subprocess.run(
        ("git", "rev-parse", "--show-toplevel"),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    resolved = runner.repo_root()
    assert resolved == Path(expected)
    # The scan's cwd must be a real checkout, or betterleaks would not find
    # .betterleaks.toml there.
    assert (resolved / ".git").exists()


def test_an_unresolvable_git_toplevel_fails_the_hook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/betterleaks")

    def raise_called_process_error() -> Path:
        raise subprocess.CalledProcessError(returncode=128, cmd=["git", "rev-parse"])

    monkeypatch.setattr(runner, "repo_root", raise_called_process_error)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no scan should run once the repo root is unresolvable")

    monkeypatch.setattr(runner.subprocess, "run", fail_if_called)

    # Fails closed: an unresolvable root means the config -- and so the
    # allowlist -- cannot be located, which must never pass as a clean scan.
    assert runner.main(["--mode", "history"]) == 1
    assert "could not resolve the git top-level directory" in capsys.readouterr().err


def test_staged_mode_matches_the_upstream_published_hook_entry() -> None:
    # betterleaks' own .pre-commit-hooks.yaml uses
    # `betterleaks git --pre-commit --redact --staged --verbose`. Flag order
    # differs here; the set must not.
    command = runner.build_command("/usr/bin/betterleaks", "staged")
    assert command[:2] == ("/usr/bin/betterleaks", "git")
    assert set(command[2:]) == {"--pre-commit", "--staged", "--redact", "--verbose", "--no-banner"}


def test_history_mode_scans_every_commit_rather_than_a_range() -> None:
    command = runner.build_command("/usr/bin/betterleaks", "history")
    # No --log-opts and no --staged: an unrestricted `betterleaks git` is a
    # full-history scan. A range flag appearing here would silently reintroduce
    # the --no-verify gap the pre-push stage exists to close.
    assert command == ("/usr/bin/betterleaks", "git", "--redact", "--verbose", "--no-banner")


@pytest.mark.parametrize("mode", ["staged", "history"])
def test_redact_is_never_optional(mode: str) -> None:
    # CLAUDE.md section 4: a hook that reports a finding must not echo the
    # secret value into the terminal.
    assert "--redact" in runner.build_command("/usr/bin/betterleaks", mode)


@pytest.mark.parametrize("mode", ["staged", "history"])
def test_missing_binary_fails_instead_of_skipping(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no scan should be attempted without a binary")

    monkeypatch.setattr(runner.subprocess, "run", fail_if_called)

    assert runner.main(["--mode", mode]) == 1
    stderr = capsys.readouterr().err
    # The message has to be actionable, not just non-zero.
    assert "nix develop" in stderr
    assert "setup-gitapex-toolchain" in stderr


@pytest.mark.usefixtures("stub_repo_root")
def test_a_timed_out_scan_fails_rather_than_passing_an_unfinished_scan(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/betterleaks")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd="betterleaks", timeout=runner._SCAN_TIMEOUT_SECONDS)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.main(["--mode", "history"]) == 1
    assert "exceeded" in capsys.readouterr().err


@pytest.mark.usefixtures("stub_repo_root")
def test_a_timeout_is_actually_passed_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/betterleaks")

    def fake_run(cmd: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured.update(kwargs)
        return _completed(0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.main(["--mode", "staged"])
    assert captured["timeout"] == runner._SCAN_TIMEOUT_SECONDS
    # The scan must run from the repo root so betterleaks discovers
    # .betterleaks.toml, whose allowlist the eval fixtures depend on.
    assert captured["cwd"] == Path("/repo")


@pytest.mark.parametrize("scanner_exit", [0, 1, 9])
@pytest.mark.usefixtures("stub_repo_root")
def test_the_scanner_exit_code_is_propagated_verbatim(monkeypatch: pytest.MonkeyPatch, scanner_exit: int) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/betterleaks")
    monkeypatch.setattr(runner.subprocess, "run", lambda *_a, **_k: _completed(scanner_exit))
    # A leak-found exit must reach git as a failure, never be swallowed into 0.
    assert runner.main(["--mode", "staged"]) == scanner_exit


def test_mode_is_required_and_constrained() -> None:
    with pytest.raises(SystemExit):
        runner.main([])
    with pytest.raises(SystemExit):
        runner.main(["--mode", "everything"])


def test_args_accepts_both_valid_modes() -> None:
    assert runner.RunBetterleaksArgs(mode="staged").mode == "staged"
    assert runner.RunBetterleaksArgs(mode="history").mode == "history"


def test_args_rejects_an_invalid_mode() -> None:
    with pytest.raises(runner.ValidationError):
        runner.RunBetterleaksArgs(mode="everything")  # type: ignore[arg-type]


def test_main_exits_two_when_args_fail_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise make_validation_error()

    monkeypatch.setattr(runner, "RunBetterleaksArgs", _raise)
    assert runner.main(["--mode", "staged"]) == 2
    assert "invalid CLI arguments" in capsys.readouterr().err

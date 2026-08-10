"""Tests for the behind-base gate
(.github/scripts/gitapex_gate_behind_base.py).

Issue #985. 17 open retrospective issues proposed or carried this check
forward without ever building it; the gap cost real repairs in PR #947's
cycle (issue #948, a red pytest run against a stale base) and PR #961's
cycle (issue #966, a full extra push-and-CI cycle despite every check
passing on the head commit).

Every fixture repo below is real -- built with `git init` and real commits
under `tmp_path` -- rather than a mocked git, so the fetch-then-compare
behavior this gate exists to get right (a stale local ref corrected by its
own fetch) is exercised for real, not asserted about a stub.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_behind_base as gate
import pytest


def _run(args: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: pathlib.Path, *, branch: str = "main") -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "--initial-branch", branch], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    return root


def _commit(root: pathlib.Path, name: str, message: str) -> None:
    (root / name).write_text(f"{name}\n", encoding="utf-8")
    _run(["git", "add", "--", name], root)
    _run(["git", "commit", "-q", "-m", message], root)


def _synced_head(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """An ``origin`` repo with one commit on ``main``, and a ``head`` repo
    whose ``origin`` remote points at it and whose ``HEAD`` is synced to
    ``origin/main`` -- the up-to-date starting point most tests build on."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")

    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    return origin, head


# --- count_behind / fetch_base -----------------------------------------


def test_up_to_date_head_has_zero_behind_and_zero_ahead(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    gate.fetch_base(head)
    result = gate.count_behind(head)
    assert result == gate.BehindBaseCount(behind=0, ahead=0)


def test_head_ahead_of_base_is_not_behind(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    _commit(head, "b.txt", "local work")
    gate.fetch_base(head)
    result = gate.count_behind(head)
    assert result == gate.BehindBaseCount(behind=0, ahead=1)


def test_fetch_picks_up_new_commits_pushed_to_origin(tmp_path: pathlib.Path) -> None:
    """The requester's own recorded decision: fetch_base must read real
    remote state, not whatever `head` last knew, so a base that moved
    since the last fetch is still caught."""
    origin, head = _synced_head(tmp_path)
    _commit(origin, "c.txt", "new base commit")
    gate.fetch_base(head)
    result = gate.count_behind(head)
    assert result == gate.BehindBaseCount(behind=1, ahead=0)


def test_behind_and_ahead_both_nonzero_when_diverged(tmp_path: pathlib.Path) -> None:
    origin, head = _synced_head(tmp_path)
    _commit(origin, "c.txt", "new base commit")
    _commit(head, "b.txt", "local work")
    gate.fetch_base(head)
    result = gate.count_behind(head)
    assert result == gate.BehindBaseCount(behind=1, ahead=1)


def test_fetch_base_fails_closed_on_unreachable_remote(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    with pytest.raises(gate.GateError, match="git fetch"):
        gate.fetch_base(head)


def test_fetch_base_fails_closed_when_git_is_missing(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    with pytest.raises(gate.GateError, match="cannot run git to fetch"):
        gate.fetch_base(tmp_path)


def test_count_behind_fails_closed_when_base_ref_does_not_exist(tmp_path: pathlib.Path) -> None:
    """No fetch happened, so `origin/main` was never created locally --
    the comparison itself must fail closed, distinct from a fetch failure."""
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    with pytest.raises(gate.GateError, match="git rev-list"):
        gate.count_behind(head)


def test_count_behind_fails_closed_when_git_is_missing(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    with pytest.raises(gate.GateError, match="cannot run git to compare"):
        gate.count_behind(tmp_path)


def test_count_behind_fails_closed_on_unparseable_output(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _garbage(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not-a-number\n", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", _garbage)
    with pytest.raises(gate.GateError, match="unexpected 'git rev-list"):
        gate.count_behind(tmp_path)


# --- CLI: main -----------------------------------------------------------


def test_main_returns_zero_when_up_to_date(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _origin, head = _synced_head(tmp_path)
    assert gate.main(["--root", str(head)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_returns_one_and_names_the_behind_count_and_remedy(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    origin, head = _synced_head(tmp_path)
    _commit(origin, "c.txt", "new base commit")
    _commit(origin, "d.txt", "another base commit")
    assert gate.main(["--root", str(head)]) == 1
    stderr = capsys.readouterr().err
    assert "FAIL" in stderr
    assert "2 commit(s) behind origin/main" in stderr
    assert "Merge or rebase" in stderr
    assert "#985" in stderr


def test_main_returns_two_and_names_the_fetch_failure_distinctly(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression for the "failed fetch never becomes a silent pass" ACM
    row: a fetch failure must read as a fetch failure, not silently pass
    and not read as an ordinary behind-base FAIL."""
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    assert gate.main(["--root", str(head)]) == 2
    stderr = capsys.readouterr().err
    assert "error:" in stderr
    assert "git fetch" in stderr
    assert "FAIL" not in stderr
    assert "behind" not in stderr


def test_main_returns_two_on_a_root_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist"
    assert gate.main(["--root", str(missing)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_returns_two_on_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = tmp_path / "not-a-directory"
    a_file.write_text("x", encoding="utf-8")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_default_root_checks_the_real_repository() -> None:
    """The real checkout's own branch is not asserted pass/fail here (that
    depends on this session's live git state), only that main() runs to
    completion against the real repo root without raising."""
    assert gate.main([]) in (0, 1, 2)


# --- GateBehindBaseArgs validation ---------------------------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateBehindBaseArgs(root=tmp_path / "does-not-exist")

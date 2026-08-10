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

import os
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


def test_fetch_base_fails_closed_on_timeout(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _hang(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="git", timeout=gate.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(gate.subprocess, "run", _hang)
    with pytest.raises(gate.GateError, match=f"timed out after {gate.GIT_TIMEOUT_SECONDS}s"):
        gate.fetch_base(tmp_path)


def test_subprocess_output_is_never_strictly_utf8_decoded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a non-UTF-8 byte on git's stdout/stderr must not crash
    this gate with an uncaught UnicodeDecodeError -- which would exit with
    Python's own default code 1, indistinguishable from this gate's
    documented exit-1 "behind base" FAIL. Reproduced with a real fake
    `git` executable emitting invalid UTF-8 on PATH, not a mock of
    subprocess.run, so the actual errors="replace" decoding path in
    _run_git is exercised for real rather than asserted about a stub."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_bytes(b"#!/bin/sh\nprintf '\\xff\\xfe not valid utf-8'\nexit 1\n")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")

    with pytest.raises(gate.GateError, match="git fetch"):
        gate.fetch_base(tmp_path)


def test_count_behind_fails_closed_when_base_ref_does_not_exist(tmp_path: pathlib.Path) -> None:
    """No fetch happened, so `origin/main` was never created locally --
    the comparison itself must fail closed, distinct from a fetch failure.
    Caught by the merge-base check first (no ref means no common
    ancestor either), before `rev-list` is ever invoked."""
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    with pytest.raises(gate.GateError, match="share no common ancestor"):
        gate.count_behind(head)


def test_count_behind_fails_closed_on_unrelated_histories(tmp_path: pathlib.Path) -> None:
    """Regression: a real repro (not a mock) of two repos with no shared
    commit. `git rev-list --left-right --count` does not itself fail on
    this input -- it silently returns a numeric ahead/behind pair for the
    empty merge base -- so without the explicit merge-base check this
    would produce a plausible-looking but meaningless behind-base FAIL
    instead of the honest "cannot be trusted" exit 2."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "origin commit")

    head = _init_repo(tmp_path / "head")
    _commit(head, "b.txt", "unrelated head commit")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)

    with pytest.raises(gate.GateError, match="share no common ancestor"):
        gate.count_behind(head)


def test_count_behind_fails_closed_when_git_is_missing_during_merge_base(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    with pytest.raises(gate.GateError, match="cannot run git to find a common ancestor"):
        gate.count_behind(tmp_path)


def test_count_behind_fails_closed_when_git_is_missing_during_rev_list(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The merge-base check must succeed (real git) so the rev-list call is
    the one that hits a missing git -- exercised with a real fetch/repo
    rather than a fully mocked subprocess, so this is a true second-call
    failure, not an accidental first-call one."""
    _origin, head = _synced_head(tmp_path)
    gate.fetch_base(head)

    real_run = gate.subprocess.run
    calls = {"n": 0}

    def _fail_second_call(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return real_run(*args, **kwargs)  # type: ignore[no-any-return, call-overload]
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _fail_second_call)
    with pytest.raises(gate.GateError, match="cannot run git to compare"):
        gate.count_behind(head)


def test_count_behind_fails_closed_when_rev_list_itself_exits_nonzero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Distinct from every case above: the merge-base check passes for
    real (a common ancestor genuinely exists), but the rev-list call
    itself returns a nonzero exit code -- a real git failure mode
    (corruption, a race deleting an object) rather than a missing
    executable or a no-common-ancestor precondition."""
    _origin, head = _synced_head(tmp_path)
    gate.fetch_base(head)

    real_run = gate.subprocess.run
    calls = {"n": 0}

    def _fail_rev_list(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return real_run(*args, **kwargs)  # type: ignore[no-any-return, call-overload]
        return subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal: bad object HEAD")

    monkeypatch.setattr(gate.subprocess, "run", _fail_rev_list)
    with pytest.raises(gate.GateError, match="git rev-list against origin/main failed"):
        gate.count_behind(head)


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

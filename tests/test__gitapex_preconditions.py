"""Tests for the shallow-clone precondition helpers
(.github/scripts/_gitapex_preconditions.py, issue #1566, consolidating
#1546/#1489).

Builds its own local bare repo, then `git clone --depth 1` from it into a
tmp dir for the shallow-clone fixtures -- the shape this module's own
docstring and the branch plan's Proof method both name -- rather than
cloning this real repository (that heavier, more direct reproduction lives
in tests/test_gitapex_gate_local_preflight.py, alongside the real
harden-checkout-pin-drift-shaped fixture gate). That fixture chain lives in
conftest.py, shared with the runner-level suite that needs the identical
shape.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

import _gitapex_preconditions
import pytest
from conftest import bare_origin_with_two_commits, commit_file, init_git_repo, run_git, shallow_clone


def _full_clone(origin: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    """An ordinary, full-history clone -- the non-shallow counterpart the
    shared fixtures have no other caller for, so it stays local here."""
    run_git(["git", "clone", "-q", f"file://{origin}", str(dest)], dest.parent)
    return dest


# --------------------------------------------------------------------------
# is_shallow_clone
# --------------------------------------------------------------------------


def test_is_shallow_clone_is_true_for_a_depth_one_clone(tmp_path: pathlib.Path) -> None:
    origin = bare_origin_with_two_commits(tmp_path)
    shallow = shallow_clone(origin, tmp_path / "shallow")
    assert _gitapex_preconditions.is_shallow_clone(shallow) is True


def test_is_shallow_clone_is_false_for_an_ordinary_full_clone(tmp_path: pathlib.Path) -> None:
    origin = bare_origin_with_two_commits(tmp_path)
    full = _full_clone(origin, tmp_path / "full")
    assert _gitapex_preconditions.is_shallow_clone(full) is False


def test_is_shallow_clone_is_false_for_a_freshly_initialized_repo(tmp_path: pathlib.Path) -> None:
    """A repo with no remote at all is not shallow -- the ordinary local
    development case this precondition mechanism must leave untouched."""
    repo = init_git_repo(tmp_path / "solo")
    commit_file(repo, "a.txt", "first")
    assert _gitapex_preconditions.is_shallow_clone(repo) is False


def test_is_shallow_clone_raises_rather_than_reporting_not_shallow_outside_a_repo(tmp_path: pathlib.Path) -> None:
    """A directory that is not a git repository at all leaves the shallow
    question genuinely unanswered -- must not be reported as `False`
    (`_gitapex_preconditions.PreconditionsError`'s own reason for
    existing: a caller treating a failed check as "not shallow" would let
    the exact reactive mid-run failure this module exists to prevent
    through unchecked)."""
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="exited"):
        _gitapex_preconditions.is_shallow_clone(not_a_repo)


def test_is_shallow_clone_raises_when_git_cannot_be_run(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(subprocess, "run", _no_git)
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="cannot run git"):
        _gitapex_preconditions.is_shallow_clone(tmp_path)


def test_is_shallow_clone_raises_on_timeout(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _hang(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="git rev-parse --is-shallow-repository", timeout=5)

    monkeypatch.setattr(subprocess, "run", _hang)
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="timed out after 5s"):
        _gitapex_preconditions.is_shallow_clone(tmp_path, timeout=5)


# --------------------------------------------------------------------------
# ensure_full_history
# --------------------------------------------------------------------------


def test_ensure_full_history_makes_a_shallow_clone_report_non_shallow(tmp_path: pathlib.Path) -> None:
    origin = bare_origin_with_two_commits(tmp_path)
    shallow = shallow_clone(origin, tmp_path / "shallow")
    assert _gitapex_preconditions.is_shallow_clone(shallow) is True
    _gitapex_preconditions.ensure_full_history(shallow)
    assert _gitapex_preconditions.is_shallow_clone(shallow) is False


def test_ensure_full_history_raises_naming_the_underlying_git_error_when_origin_is_gone(
    tmp_path: pathlib.Path,
) -> None:
    """The bare origin disappearing before the fetch runs -- the shape the
    branch plan's own Proof method names for reproducing an abort. The
    fetch failure text (git's own, naming the missing path) must reach the
    caller, never be swallowed."""
    origin = bare_origin_with_two_commits(tmp_path)
    shallow = shallow_clone(origin, tmp_path / "shallow")
    shutil.rmtree(origin)
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="git fetch --unshallow failed"):
        _gitapex_preconditions.ensure_full_history(shallow)


def test_ensure_full_history_raises_when_repo_root_is_not_a_git_repo(tmp_path: pathlib.Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="git fetch --unshallow failed"):
        _gitapex_preconditions.ensure_full_history(not_a_repo)


def test_ensure_full_history_raises_when_git_cannot_be_run(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(subprocess, "run", _no_git)
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="cannot run git"):
        _gitapex_preconditions.ensure_full_history(tmp_path)


def test_ensure_full_history_raises_on_timeout(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _hang(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="git fetch --unshallow", timeout=5)

    monkeypatch.setattr(subprocess, "run", _hang)
    with pytest.raises(_gitapex_preconditions.PreconditionsError, match="timed out after 5s"):
        _gitapex_preconditions.ensure_full_history(tmp_path, timeout=5)


def test_git_timeout_seconds_pins_exact_value() -> None:
    assert _gitapex_preconditions.GIT_TIMEOUT_SECONDS == 60

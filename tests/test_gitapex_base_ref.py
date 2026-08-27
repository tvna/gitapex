"""Tests for the shared destination-refspec git-fetch helpers
(.github/scripts/_gitapex_base_ref.py).

Issue #1345: extracted out of gitapex_gate_behind_base.py (issue #985) so
both that gate and the new gitapex_run_base_diff.py share one
destination-refspec fetch implementation instead of two copies that could
drift apart. tests/test_gitapex_gate_behind_base.py and
tests/test_gitapex_run_base_diff.py already exercise these helpers
extensively through their own callers; this file covers the module's own
contract directly, including the error_cls parameterization and the
message-text stability neither sibling test file pins as narrowly as this
one does.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import _gitapex_base_ref
import pytest


class _FakeError(Exception):
    """A stand-in for a caller's own exception type (GateError/
    DiffProducerError) -- proves every function raises the *given*
    error_cls, not a hardcoded one."""


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


def _restricted_refspec_clone(origin: pathlib.Path, dest: pathlib.Path, *, branch: str) -> None:
    """A `git clone --single-branch --branch <branch>` clone -- the shape
    whose configured `remote.origin.fetch` refspec only covers one
    branch, and which a source-only `git fetch origin main` cannot
    populate `refs/remotes/origin/main` in (issue #1345's own repro)."""
    _run(["git", "clone", "-q", "--single-branch", "--branch", branch, str(origin), str(dest)], dest.parent)


# --- destination_refspec / GIT_TIMEOUT_SECONDS ---------------------------


def test_destination_refspec_pins_exact_string() -> None:
    assert _gitapex_base_ref.destination_refspec("origin", "main") == "+refs/heads/main:refs/remotes/origin/main"


def test_git_timeout_seconds_pins_exact_value() -> None:
    assert _gitapex_base_ref.GIT_TIMEOUT_SECONDS == 60


# --- run_git ---------------------------------------------------------------


def test_run_git_raises_given_error_cls_when_git_is_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _no_git)
    with pytest.raises(_FakeError, match="cannot run git to do a thing"):
        _gitapex_base_ref.run_git(tmp_path, ["status"], label="do a thing", timeout=5, error_cls=_FakeError)


def test_run_git_raises_given_error_cls_on_timeout(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _hang(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _hang)
    with pytest.raises(_FakeError, match="do a thing timed out after 5s"):
        _gitapex_base_ref.run_git(tmp_path, ["status"], label="do a thing", timeout=5, error_cls=_FakeError)


@pytest.mark.slow
def test_run_git_uses_errors_replace_on_non_utf8_output(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a non-UTF-8 byte on git's stdout/stderr must not crash
    with an uncaught UnicodeDecodeError. Reproduced with a real fake `git`
    executable emitting invalid UTF-8 on PATH, not a mock of
    subprocess.run."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_bytes(b"#!/bin/sh\nprintf '\\xff\\xfe not valid utf-8'\nexit 0\n")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")

    result = _gitapex_base_ref.run_git(tmp_path, ["status"], label="do a thing", timeout=5, error_cls=_FakeError)
    assert result.returncode == 0


@pytest.mark.slow
def test_run_git_returns_completed_process_for_a_real_command(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    result = _gitapex_base_ref.run_git(tmp_path, ["status"], label="status", timeout=5, error_cls=_FakeError)
    assert result.returncode == 0


# --- remote_url / announce_fetch -------------------------------------------


@pytest.mark.slow
def test_remote_url_returns_configured_url(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", "https://example.invalid/repo.git"], head)
    assert _gitapex_base_ref.remote_url(head, "origin") == "https://example.invalid/repo.git"


@pytest.mark.slow
def test_remote_url_raises_base_ref_error_when_remote_missing(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    with pytest.raises(_gitapex_base_ref.BaseRefError, match="No such remote"):
        _gitapex_base_ref.remote_url(head, "origin")


@pytest.mark.slow
def test_announce_fetch_prints_remote_url_to_stderr(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", "https://example.invalid/repo.git"], head)
    _gitapex_base_ref.announce_fetch(head, "origin", "main")
    stderr = capsys.readouterr().err
    assert "origin" in stderr
    assert "https://example.invalid/repo.git" in stderr
    assert "main" in stderr


@pytest.mark.slow
def test_announce_fetch_degrades_gracefully_when_remote_url_fails(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    head = _init_repo(tmp_path / "head")
    _gitapex_base_ref.announce_fetch(head, "origin", "main")
    stderr = capsys.readouterr().err
    assert "url unresolved" in stderr


# --- fetch_destination_refspec ---------------------------------------------


@pytest.mark.slow
def test_fetch_destination_refspec_materializes_ref_in_restricted_refspec_clone(tmp_path: pathlib.Path) -> None:
    """The defeat test for this issue's own core claim: a source-only
    fetch does NOT do this in a restricted-refspec clone; a
    destination-refspec fetch does."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    _run(["git", "checkout", "-q", "-b", "feature"], origin)
    _commit(origin, "b.txt", "feature work")

    work = tmp_path / "work"
    _restricted_refspec_clone(origin, work, branch="feature")

    assert _gitapex_base_ref.peeled_ref_exists(work, "origin", "main") is False

    _gitapex_base_ref.fetch_destination_refspec(work, "origin", "main", error_cls=_FakeError)

    assert _gitapex_base_ref.peeled_ref_exists(work, "origin", "main") is True


@pytest.mark.slow
def test_fetch_destination_refspec_is_a_noop_safe_replacement_in_wildcard_refspec_clone(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")

    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)

    _gitapex_base_ref.fetch_destination_refspec(head, "origin", "main", error_cls=_FakeError)
    assert _gitapex_base_ref.peeled_ref_exists(head, "origin", "main") is True


@pytest.mark.slow
def test_fetch_destination_refspec_raises_given_error_cls_on_unreachable_remote(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    with pytest.raises(_FakeError, match="git fetch"):
        _gitapex_base_ref.fetch_destination_refspec(head, "origin", "main", error_cls=_FakeError)


@pytest.mark.slow
def test_fetch_destination_refspec_message_matches_pre_1345_label_text(tmp_path: pathlib.Path) -> None:
    """Regression pin: the message text stays 'git fetch {remote} {branch}
    failed: ...', NOT a refspec-bearing form, so
    gitapex_gate_behind_base.py's existing tests keep matching on it
    unmodified."""
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    with pytest.raises(_FakeError, match=r"^git fetch origin main failed:"):
        _gitapex_base_ref.fetch_destination_refspec(head, "origin", "main", error_cls=_FakeError)


def test_fetch_destination_refspec_raises_given_error_cls_when_git_is_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _no_git)
    with pytest.raises(_FakeError, match="cannot run git to fetch"):
        _gitapex_base_ref.fetch_destination_refspec(tmp_path, "origin", "main", error_cls=_FakeError)


# --- peeled_ref_exists -------------------------------------------------------


@pytest.mark.slow
def test_peeled_ref_exists_true_for_real_branch(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    assert _gitapex_base_ref.peeled_ref_exists(head, "origin", "main") is True


@pytest.mark.slow
def test_peeled_ref_exists_false_for_missing_ref(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    assert _gitapex_base_ref.peeled_ref_exists(head, "origin", "main") is False


@pytest.mark.slow
def test_peeled_ref_exists_false_for_dangling_ref(tmp_path: pathlib.Path) -> None:
    """A ref file pointing at an object that does not exist -- a bare
    `git rev-parse --verify --quiet origin/main` would report this
    non-peeled form as "resolves"; the peeled `^{commit}` form must not."""
    head = _init_repo(tmp_path / "head")
    ref_dir = head / ".git" / "refs" / "remotes" / "origin"
    ref_dir.mkdir(parents=True)
    (ref_dir / "main").write_text("deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n", encoding="utf-8")
    assert _gitapex_base_ref.peeled_ref_exists(head, "origin", "main") is False


@pytest.mark.slow
def test_peeled_ref_exists_false_when_only_a_same_named_tag_exists(tmp_path: pathlib.Path) -> None:
    """No refs/remotes/origin/main at all -- only an ordinary tag named
    'main' exists. A bare, unqualified `git rev-parse --verify --quiet
    origin/main` can ambiguously resolve via git's own ref-disambiguation
    rules; querying the fully-qualified refs/remotes/origin/main^{commit}
    path this function actually uses must not."""
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "tag", "main"], head)
    assert _gitapex_base_ref.peeled_ref_exists(head, "origin", "main") is False


def test_peeled_ref_exists_raises_given_error_cls_when_git_is_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _no_git)
    with pytest.raises(_FakeError, match="cannot run git to verify"):
        _gitapex_base_ref.peeled_ref_exists(tmp_path, "origin", "main", error_cls=_FakeError)


# --- require_common_ancestor -------------------------------------------------


@pytest.mark.slow
def test_require_common_ancestor_passes_on_real_common_ancestor(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    _gitapex_base_ref.require_common_ancestor(head, "origin/main", error_cls=_FakeError)  # does not raise


@pytest.mark.slow
def test_require_common_ancestor_raises_on_unrelated_histories(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "origin commit")
    head = _init_repo(tmp_path / "head")
    _commit(head, "b.txt", "unrelated head commit")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    with pytest.raises(_FakeError, match="cannot find a common ancestor"):
        _gitapex_base_ref.require_common_ancestor(head, "origin/main", error_cls=_FakeError)


@pytest.mark.slow
def test_require_common_ancestor_raises_on_shallow_clone_with_no_common_ancestor(tmp_path: pathlib.Path) -> None:
    """Live-verified defeat test: a shallow, restricted-refspec clone can
    fetch `main` correctly and still have no common ancestor with its own
    truncated HEAD history. A bare `git merge-base` prints nothing to
    stderr in this exact case -- this function's own message is the only
    informative signal."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    _commit(origin, "b.txt", "second")
    _run(["git", "checkout", "-q", "-b", "feature"], origin)
    _commit(origin, "c.txt", "feature work")
    _commit(origin, "d.txt", "more feature work")

    work = tmp_path / "work"
    _run(
        ["git", "clone", "-q", "--single-branch", "--branch", "feature", "--depth", "1", f"file://{origin}", str(work)],
        tmp_path,
    )
    _gitapex_base_ref.fetch_destination_refspec(work, "origin", "main", error_cls=_FakeError)
    assert _gitapex_base_ref.peeled_ref_exists(work, "origin", "main") is True

    with pytest.raises(_FakeError, match="cannot find a common ancestor"):
        _gitapex_base_ref.require_common_ancestor(work, "origin/main", error_cls=_FakeError)


def test_require_common_ancestor_raises_given_error_cls_when_git_is_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _no_git)
    with pytest.raises(_FakeError, match="cannot run git to find a common ancestor"):
        _gitapex_base_ref.require_common_ancestor(tmp_path, "origin/main", error_cls=_FakeError)


def test_require_common_ancestor_raises_given_error_cls_on_timeout(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _hang(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(_gitapex_base_ref.subprocess, "run", _hang)
    with pytest.raises(_FakeError, match="timed out after"):
        _gitapex_base_ref.require_common_ancestor(tmp_path, "origin/main", timeout=5, error_cls=_FakeError)

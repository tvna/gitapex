"""Tests for the self-healing local_stdin diff producer
(.github/scripts/gitapex_run_base_diff.py).

Issue #1345: replaces the raw `git diff --merge-base origin/main HEAD`
invocation the three merge-base diff gates (exception-handler-gap,
stdlib-only-claim-drift, detection-logic-property-coverage) used to run
directly, which failed hard in a restricted-refspec clone
(`git clone --single-branch --branch`) because `origin/main` never
resolved locally there.

Every fixture repo below is real -- built with `git init`/`git clone` and
real commits under `tmp_path`, matching tests/test_gitapex_gate_behind_base.py's
own convention -- so the actual self-healing behavior this script exists to
get right is exercised for real, not asserted about a stub.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import gitapex_run_base_diff as producer
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "gitapex_run_base_diff.py"


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


def _run_cli(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[bytes]:
    """Black-box invocation of the real script via subprocess (not
    producer.main() in-process) so the stdout-inheritance byte path is
    exercised end to end, exactly as gitapex_gate_local_preflight.py's own
    runner invokes it."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(cwd), "--", *args],
        capture_output=True,
        check=False,
    )


# --- ensure_base_ref / run_diff (in-process) --------------------------------


@pytest.mark.slow
def test_run_diff_self_heals_in_a_restricted_refspec_clone(tmp_path: pathlib.Path) -> None:
    """The core regression test for issue #1345: the OLD raw
    `git diff --merge-base origin/main HEAD` command fails outright in a
    restricted-refspec clone; this producer must self-heal and succeed."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    _run(["git", "checkout", "-q", "-b", "feature"], origin)
    _commit(origin, "b.txt", "feature work")

    work = tmp_path / "work"
    _run(["git", "clone", "-q", "--single-branch", "--branch", "feature", str(origin), str(work)], tmp_path)

    old_raw_diff = subprocess.run(
        ["git", "-C", str(work), "diff", "--merge-base", "origin/main", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    # Exact wording varies by git version ("bad revision" vs. "ambiguous
    # argument" / "unknown revision") -- exit 128 is the stable signal this
    # test actually needs: origin/main is not a resolvable ref here.
    assert old_raw_diff.returncode == 128

    assert producer.run_diff(work, "origin", "main", ["*.txt"]) == 0


@pytest.mark.slow
def test_run_diff_is_a_noop_safe_replacement_on_a_normal_clone(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    _commit(head, "b.txt", "local work")

    assert producer.run_diff(head, "origin", "main", ["*.txt"]) == 0


@pytest.mark.slow
def test_ensure_base_ref_is_a_noop_when_ref_already_resolves(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("fetch_destination_refspec must not be called when the ref already resolves")

    monkeypatch.setattr(producer._gitapex_base_ref, "fetch_destination_refspec", _fail_if_called)
    producer.ensure_base_ref(head, "origin", "main")  # does not raise


@pytest.mark.slow
def test_ensure_base_ref_raises_distinctly_when_fetch_reports_success_but_ref_still_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 'never trust the fetch's exit code alone' defeat test: simulate a
    fetch that reports success (no exception) but the ref genuinely never
    materializes on re-check."""
    head = _init_repo(tmp_path / "head")

    def _fake_fetch(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(producer._gitapex_base_ref, "fetch_destination_refspec", _fake_fetch)
    with pytest.raises(producer.DiffProducerError, match="reported success but"):
        producer.ensure_base_ref(head, "origin", "main")


@pytest.mark.slow
def test_run_diff_names_the_shallow_clone_case_distinctly(tmp_path: pathlib.Path) -> None:
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

    with pytest.raises(producer.DiffProducerError, match="cannot find a common ancestor"):
        producer.run_diff(work, "origin", "main", ["*.txt"])


@pytest.mark.slow
def test_run_diff_raises_distinctly_on_fetch_failure(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    with pytest.raises(producer.DiffProducerError, match="git fetch"):
        producer.run_diff(head, "origin", "main", ["*.txt"])


@pytest.mark.slow
def test_run_diff_raises_distinctly_when_git_diff_itself_times_out(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real `git diff` subprocess call's own timeout/OSError handling
    (distinct from the fetch/probe/common-ancestor calls, which delegate
    to _gitapex_base_ref) -- exercised in-process, unlike the black-box
    CLI tests below, so this path is actually covered rather than only
    exercised in a child process coverage cannot see."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)

    real_run = producer.subprocess.run

    def _timeout_on_diff(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = args[0]
        assert isinstance(argv, list)
        if "diff" in argv:
            raise subprocess.TimeoutExpired(cmd="git", timeout=5)
        return real_run(*args, **kwargs)  # type: ignore[no-any-return, call-overload]

    monkeypatch.setattr(producer.subprocess, "run", _timeout_on_diff)
    with pytest.raises(producer.DiffProducerError, match="git diff timed out"):
        producer.run_diff(head, "origin", "main", ["*.txt"])


@pytest.mark.slow
def test_run_diff_raises_distinctly_when_git_diff_itself_cannot_run(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)

    real_run = producer.subprocess.run

    def _no_git_for_diff(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        argv = args[0]
        assert isinstance(argv, list)
        if "diff" in argv:
            raise OSError("No such file or directory: 'git'")
        return real_run(*args, **kwargs)  # type: ignore[no-any-return, call-overload]

    monkeypatch.setattr(producer.subprocess, "run", _no_git_for_diff)
    with pytest.raises(producer.DiffProducerError, match="cannot run git diff"):
        producer.run_diff(head, "origin", "main", ["*.txt"])


# --- CLI: main (in-process, exercising the try/except branches coverage
# tooling can't see through the black-box subprocess calls below) ---------


@pytest.mark.slow
def test_main_in_process_returns_two_and_names_the_fetch_failure_distinctly(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)

    assert producer.main(["--root", str(head), "--", "*.txt"]) == 2
    stderr = capsys.readouterr().err
    assert "error:" in stderr
    assert "git fetch" in stderr


# --- CLI: main (black-box, exercising the real stdout-inheritance path) ----


@pytest.mark.slow
def test_main_emits_the_same_bytes_git_diff_would_on_an_unrestricted_clone(tmp_path: pathlib.Path) -> None:
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "initial")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    _commit(head, "b.txt", "local work")

    result = _run_cli(["*.txt"], head)
    assert result.returncode == 0

    expected = subprocess.run(
        [
            "git",
            "-C",
            str(head),
            "-c",
            "core.quotePath=false",
            "diff",
            "-U0",
            "--no-renames",
            "--merge-base",
            "origin/main",
            "HEAD",
            "--",
            "*.txt",
        ],
        capture_output=True,
        check=False,
    )
    assert result.stdout == expected.stdout


@pytest.mark.slow
def test_main_returns_two_and_names_the_fetch_failure_distinctly(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _commit(head, "a.txt", "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)

    result = _run_cli(["*.txt"], head)
    assert result.returncode == 2
    stderr = result.stderr.decode()
    assert "git fetch" in stderr
    assert "common ancestor" not in stderr


@pytest.mark.slow
def test_main_names_the_shallow_clone_case_distinctly_from_an_ordinary_diff_failure(tmp_path: pathlib.Path) -> None:
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

    result = _run_cli(["*.txt"], work)
    assert result.returncode == 2
    stderr = result.stderr.decode()
    assert "cannot find a common ancestor" in stderr


def test_main_rejects_a_root_that_does_not_exist(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "does-not-exist"
    assert producer.main(["--root", str(missing), "--", "*.py"]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_rejects_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = tmp_path / "not-a-directory"
    a_file.write_text("x", encoding="utf-8")
    assert producer.main(["--root", str(a_file), "--", "*.py"]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_rejects_empty_pathspecs(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert producer.main(["--root", str(tmp_path)]) == 2
    assert "at least one pathspec is required" in capsys.readouterr().err


# --- RunBaseDiffArgs validation ----------------------------------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        producer.RunBaseDiffArgs(root=tmp_path / "does-not-exist", pathspecs=["*.py"])


def test_args_reject_empty_pathspecs(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="at least one pathspec is required"):
        producer.RunBaseDiffArgs(root=tmp_path, pathspecs=[])


# --- module constants --------------------------------------------------------


def test_base_remote_and_branch_are_hardcoded_origin_main() -> None:
    assert producer.BASE_REMOTE == "origin"
    assert producer.BASE_BRANCH == "main"


def test_git_timeout_seconds_matches_the_shared_helper() -> None:
    assert producer.GIT_TIMEOUT_SECONDS == producer._gitapex_base_ref.GIT_TIMEOUT_SECONDS

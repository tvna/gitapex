"""Tests for the two-layer commit-citation gate
(.github/scripts/gitapex_gate_commit_citation.py, issue #1212).

Every fixture repo below is real -- built with `git init`/`git commit`/
`git merge` under `tmp_path`, matching tests/test_gitapex_run_base_diff.py's
and tests/test_gitapex_base_ref.py's own convention -- so the `--no-merges`
exclusion this gate depends on is genuinely exercised against a real merge
commit, not only assumed from `git log`'s documented behavior.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_commit_citation as gate
import pytest
from conftest import make_validation_error

# --- real-repo fixture helpers (mirrors tests/test_gitapex_run_base_diff.py) -


def _run(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: pathlib.Path, *, branch: str = "main") -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "--initial-branch", branch], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    return root


def _commit(root: pathlib.Path, name: str, message: str) -> str:
    (root / name).write_text(f"{name}\n", encoding="utf-8")
    _run(["git", "add", "--", name], root)
    _run(["git", "commit", "-q", "-m", message], root)
    return _run(["git", "rev-parse", "HEAD"], root).stdout.strip()


def _checkout_new_branch(root: pathlib.Path, branch: str, start_point: str | None = None) -> None:
    args = ["git", "checkout", "-q", "-b", branch]
    if start_point is not None:
        args.append(start_point)
    _run(args, root)


def _merge_no_ff(root: pathlib.Path, branch: str, message: str) -> str:
    _run(["git", "merge", "-q", "--no-ff", "-m", message, branch], root)
    return _run(["git", "rev-parse", "HEAD"], root).stdout.strip()


def _build_range_repo(tmp_path: pathlib.Path, *, citing_commit: bool) -> tuple[pathlib.Path, str, str]:
    """A repo with a `main` base commit, a `feature` branch carrying two
    ordinary (non-merge) commits with no citation, a real `--no-ff` merge
    of a third `side` branch (also no citation) into `feature`, and --
    only when `citing_commit` -- one final ordinary commit that does carry
    one. Returns (root, base_sha, head_sha)."""
    root = _init_repo(tmp_path / ("repo-cited" if citing_commit else "repo-uncited"))
    base_sha = _commit(root, "a.txt", "chore: init")

    _checkout_new_branch(root, "feature")
    _commit(root, "b.txt", "feat: work on the feature (no citation)")

    _checkout_new_branch(root, "side", base_sha)
    _commit(root, "c.txt", "chore: side work (no citation)")

    _run(["git", "checkout", "-q", "feature"], root)
    _merge_no_ff(root, "side", "Merge branch 'side' into feature")

    head_sha = _run(["git", "rev-parse", "HEAD"], root).stdout.strip()
    if citing_commit:
        head_sha = _commit(root, "d.txt", "fix: correct the bug\n\nCloses #42")

    return root, base_sha, head_sha


# --- check_commit_message / check_pr_text -----------------------------------


@pytest.mark.parametrize("message", ["fix: bug\n\nCloses #123", "chore: work\n\nRefs #123", "chore: work (#123)"])
def test_check_commit_message_accepts_every_citation_form(message: str) -> None:
    assert gate.check_commit_message(message) is True


def test_check_commit_message_rejects_no_citation() -> None:
    assert gate.check_commit_message("chore: tidy up formatting") is False


def test_check_commit_message_a_citation_inside_a_fenced_code_block_does_not_count() -> None:
    # Proves the integration reuses extract_citations' own fence-stripping
    # rather than bypassing it -- the exact false positive issue #657's own
    # adversarial review found live in hooks/gitapex_check_pr_issue_acm_disclosure.py's
    # own PR body.
    message = "docs: explain the citation syntax\n\n```\nCloses #123\n```\n"
    assert gate.check_commit_message(message) is False


def test_check_pr_text_a_citation_inside_inline_code_does_not_count() -> None:
    body = "This hook accepts citations shaped like `Closes #123`."
    assert gate.check_pr_text("tvna", "gitapex", "", body) is False


def test_check_pr_text_finds_a_citation_in_the_title_alone() -> None:
    assert gate.check_pr_text("tvna", "gitapex", "fix: bug (Closes #99)", "") is True


def test_check_pr_text_finds_a_citation_in_the_body_alone() -> None:
    assert gate.check_pr_text("tvna", "gitapex", "", "Closes #99") is True


def test_check_pr_text_normalizes_a_same_repo_qualified_citation() -> None:
    assert gate.check_pr_text("tvna", "gitapex", "", "Fixes tvna/gitapex#7") is True


# --- resolve_base_ref ---------------------------------------------------------


def test_resolve_base_ref_returns_an_explicit_ref_unchanged_with_no_git_call(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no self-heal git call should run when --base-ref is given explicitly")

    monkeypatch.setattr(gate._gitapex_base_ref, "peeled_ref_exists", _fail_if_called)
    monkeypatch.setattr(gate._gitapex_base_ref, "fetch_destination_refspec", _fail_if_called)
    monkeypatch.setattr(gate._gitapex_base_ref, "require_common_ancestor", _fail_if_called)
    assert gate.resolve_base_ref(tmp_path, "deadbeef") == "deadbeef"


@pytest.mark.slow
def test_resolve_base_ref_is_a_noop_probe_when_the_ref_already_resolves(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The common case: an ordinary (non-restricted-refspec) clone where
    `refs/remotes/origin/main` already resolves locally. No fetch should
    run at all -- only the cheap peeled probe."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "chore: init")
    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    _checkout_new_branch(head, "feature")
    _commit(head, "b.txt", "feat: local work")

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no fetch should run once the ref already resolves")

    monkeypatch.setattr(gate._gitapex_base_ref, "fetch_destination_refspec", _fail_if_called)
    assert gate.resolve_base_ref(head, None) == "refs/remotes/origin/main"


@pytest.mark.slow
def test_resolve_base_ref_self_heals_in_a_restricted_refspec_clone(tmp_path: pathlib.Path) -> None:
    """The same regression shape issue #1345 fixed for gitapex_run_base_diff.py:
    a `git clone --single-branch --branch` clone never populates
    `refs/remotes/origin/main` from a source-only fetch, so a bare
    `origin/main` reference fails outright there. resolve_base_ref must
    self-heal it via a destination-refspec fetch when --base-ref is omitted."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "chore: init")
    _checkout_new_branch(origin, "feature")
    _commit(origin, "b.txt", "feat: work")

    work = tmp_path / "work"
    _run(["git", "clone", "-q", "--single-branch", "--branch", "feature", str(origin), str(work)], tmp_path)

    old_raw = subprocess.run(
        ["git", "-C", str(work), "rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert old_raw.returncode != 0  # confirms the ref genuinely does not resolve yet

    resolved = gate.resolve_base_ref(work, None)
    assert resolved == "refs/remotes/origin/main"


def test_resolve_base_ref_raises_distinctly_when_fetch_reports_success_but_ref_still_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 'never trust the fetch's exit code alone' defeat test (issue
    #1345): simulate a fetch that reports success (no exception) but the
    ref genuinely never materializes on re-check."""
    root = _init_repo(tmp_path / "repo")
    _commit(root, "a.txt", "chore: init")

    monkeypatch.setattr(gate._gitapex_base_ref, "fetch_destination_refspec", lambda *_a, **_k: None)
    with pytest.raises(gate.CitationGateError, match="reported success but"):
        gate.resolve_base_ref(root, None)


@pytest.mark.slow
def test_resolve_base_ref_raises_distinctly_on_a_shallow_clone_with_no_common_ancestor(
    tmp_path: pathlib.Path,
) -> None:
    # Mirrors tests/test_gitapex_run_base_diff.py's own
    # test_run_diff_names_the_shallow_clone_case_distinctly: a
    # --single-branch --branch feature --depth 1 clone has only the
    # feature branch's own truncated (depth-1) history locally and no
    # local `main` at all, so even after resolve_base_ref's own
    # destination-refspec fetch of origin/main succeeds, that fetched ref
    # cannot share a common ancestor with the shallow feature history.
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "a.txt", "chore: init")
    _commit(origin, "b.txt", "chore: second")
    _checkout_new_branch(origin, "feature")
    _commit(origin, "c.txt", "feat: work")
    _commit(origin, "d.txt", "feat: more work")

    # `file://{origin}`, not a bare path: a bare local path triggers git's
    # own local-clone hardlink fast path, which can ignore --depth
    # entirely -- the exact same reason
    # tests/test_gitapex_run_base_diff.py's own analogous test uses this
    # form.
    shallow = tmp_path / "shallow"
    _run(
        [
            "git",
            "clone",
            "-q",
            "--single-branch",
            "--branch",
            "feature",
            "--depth",
            "1",
            f"file://{origin}",
            str(shallow),
        ],
        tmp_path,
    )

    with pytest.raises(gate.CitationGateError, match="common ancestor"):
        gate.resolve_base_ref(shallow, None)


# --- commit_range_messages / evaluate_pr_range (real merge-commit fixture) --


@pytest.mark.slow
def test_commit_range_messages_excludes_the_merge_commit_but_keeps_the_ordinary_ones(
    tmp_path: pathlib.Path,
) -> None:
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=False)
    messages = gate.commit_range_messages(root, base_sha, head_sha)
    joined = "\n".join(messages)
    assert "feat: work on the feature" in joined
    assert "chore: side work" in joined
    assert "Merge branch 'side' into feature" not in joined


@pytest.mark.slow
def test_evaluate_pr_range_citation_only_in_one_non_merge_commit_passes(tmp_path: pathlib.Path) -> None:
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=True)
    passed, message = gate.evaluate_pr_range(root, "tvna", "gitapex", "", "", base_sha, head_sha)
    assert passed is True
    assert "non-merge commit" in message


@pytest.mark.slow
def test_evaluate_pr_range_an_uncited_merge_commit_does_not_alone_cause_failure(tmp_path: pathlib.Path) -> None:
    # Same repo shape as the passing case above, minus the citing commit --
    # the merge commit alone (uncited) is present in range and must not
    # itself flip this to a pass; the overall verdict is still a FAIL since
    # nothing anywhere cites an issue, proving --no-merges really excluded it
    # rather than merely never being tested.
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=False)
    passed, message = gate.evaluate_pr_range(root, "tvna", "gitapex", "", "", base_sha, head_sha)
    assert passed is False
    assert "cites no issue" not in message  # message names the range, see below
    assert "neither the PR title/body nor any non-merge commit" in message


@pytest.mark.slow
def test_evaluate_pr_range_citation_only_in_pr_body_passes_without_touching_commits(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail_if_called(*_args: object, **_kwargs: object) -> list[str]:
        raise AssertionError("commit_range_messages must not run once the PR body already cites an issue")

    monkeypatch.setattr(gate, "commit_range_messages", _fail_if_called)
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=False)
    passed, message = gate.evaluate_pr_range(root, "tvna", "gitapex", "", "Closes #7", base_sha, head_sha)
    assert passed is True
    assert "title/body" in message


@pytest.mark.slow
def test_commit_range_messages_raises_on_an_unusable_range(tmp_path: pathlib.Path) -> None:
    root = _init_repo(tmp_path / "repo")
    _commit(root, "a.txt", "chore: init")
    with pytest.raises(gate.CitationGateError, match="git log --no-merges"):
        gate.commit_range_messages(root, "not-a-real-ref", "HEAD")


# --- CommitCitationArgs -------------------------------------------------------


def test_args_requires_a_commit_msg_file_in_commit_msg_mode(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ValidationError, match="commit message file path is required"):
        gate.CommitCitationArgs(
            mode="commit-msg",
            commit_msg_file=None,
            owner="",
            repo="",
            title=None,
            body=None,
            base_ref=None,
            head_ref="HEAD",
            root=tmp_path,
        )


def test_args_does_not_require_a_commit_msg_file_in_pr_range_mode(tmp_path: pathlib.Path) -> None:
    args = gate.CommitCitationArgs(
        mode="pr-range",
        commit_msg_file=None,
        owner="",
        repo="",
        title=None,
        body=None,
        base_ref=None,
        head_ref="HEAD",
        root=tmp_path,
    )
    assert args.commit_msg_file is None


def test_args_rejects_a_root_that_is_not_a_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ValidationError, match="must be an existing directory"):
        gate.CommitCitationArgs(
            mode="pr-range",
            commit_msg_file=None,
            owner="",
            repo="",
            title=None,
            body=None,
            base_ref=None,
            head_ref="HEAD",
            root=tmp_path / "does-not-exist",
        )


def test_args_rejects_an_invalid_mode(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ValidationError):
        gate.CommitCitationArgs(
            mode="everything",  # type: ignore[arg-type]
            commit_msg_file=None,
            owner="",
            repo="",
            title=None,
            body=None,
            base_ref=None,
            head_ref="HEAD",
            root=tmp_path,
        )


# --- main(): --mode commit-msg ------------------------------------------------


def test_main_commit_msg_passes_on_a_cited_message(tmp_path: pathlib.Path) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("fix: correct the bug\n\nCloses #42\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 0


def test_main_commit_msg_fails_on_an_uncited_message(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("chore: tidy up formatting\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_commit_msg_a_fenced_citation_still_fails(tmp_path: pathlib.Path) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("docs: explain it\n\n```\nCloses #123\n```\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 1


def test_main_commit_msg_without_a_file_argument_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--mode", "commit-msg"]) == 2
    assert "invalid CLI arguments" in capsys.readouterr().err


def test_main_commit_msg_missing_file_exits_two(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--mode", "commit-msg", str(tmp_path / "does-not-exist")]) == 2
    assert "not found" in capsys.readouterr().err


def test_main_commit_msg_non_utf8_file_exits_two(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_bytes(b"\xff\xfe not valid utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err


# --- main(): --mode pr-range --------------------------------------------------


def test_main_pr_range_passes_on_a_cited_body(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text("Closes #99", encoding="utf-8")
    assert gate.main(["--mode", "pr-range", "--owner", "tvna", "--repo", "gitapex", "--body", str(body_file)]) == 0


def test_main_pr_range_fails_when_the_body_file_is_missing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gate.main(["--mode", "pr-range", "--body", str(tmp_path / "nope.txt")]) == 2
    assert "not found" in capsys.readouterr().err


def test_main_pr_range_fails_when_the_title_file_is_not_utf8(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    title_file = tmp_path / "title.txt"
    title_file.write_bytes(b"\xff\xfe not valid utf-8")
    assert gate.main(["--mode", "pr-range", "--title", str(title_file)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err


@pytest.mark.slow
def test_main_pr_range_end_to_end_against_a_real_repo_with_no_pr_text(tmp_path: pathlib.Path) -> None:
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=True)
    assert (
        gate.main(
            [
                "--mode",
                "pr-range",
                "--owner",
                "tvna",
                "--repo",
                "gitapex",
                "--base-ref",
                base_sha,
                "--head-ref",
                head_sha,
                "--root",
                str(root),
            ]
        )
        == 0
    )


@pytest.mark.slow
def test_main_pr_range_end_to_end_fails_with_no_citation_anywhere(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=False)
    exit_code = gate.main(
        [
            "--mode",
            "pr-range",
            "--base-ref",
            base_sha,
            "--head-ref",
            head_sha,
            "--root",
            str(root),
        ]
    )
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_pr_range_reports_a_base_ref_resolution_failure_as_exit_two(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> str:
        raise gate.CitationGateError("could not resolve origin/main")

    monkeypatch.setattr(gate, "resolve_base_ref", _raise)
    exit_code = gate.main(["--mode", "pr-range", "--root", str(tmp_path)])
    assert exit_code == 2
    assert "could not resolve origin/main" in capsys.readouterr().err


def test_main_exits_two_when_args_fail_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise make_validation_error()

    monkeypatch.setattr(gate, "CommitCitationArgs", _raise)
    assert gate.main(["--mode", "pr-range"]) == 2
    assert "invalid CLI arguments" in capsys.readouterr().err


def test_main_mode_is_required() -> None:
    with pytest.raises(SystemExit):
        gate.main([])
    with pytest.raises(SystemExit):
        gate.main(["--mode", "everything"])

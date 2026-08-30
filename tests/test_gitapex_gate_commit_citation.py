"""Tests for the two-layer commit-citation gate
(.github/scripts/gitapex_gate_commit_citation.py, issue #1212).

Every fixture repo below is real -- built with `git init`/`git commit`/
`git merge` under `tmp_path`, matching tests/test_gitapex_run_base_diff.py's
and tests/test_gitapex_base_ref.py's own convention -- so the `--no-merges`
exclusion this gate depends on is genuinely exercised against a real merge
commit, not only assumed from `git log`'s documented behavior.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

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


def _raw_hook_commit_editmsg(subject: str, staged_diff_citation: str) -> str:
    """A `COMMIT_EDITMSG` shaped exactly the way git itself writes it at
    `commit-msg`-hook invocation time, under `commit.verbose=true` -- the
    subject the contributor typed, then git's own comment block, then the
    scissors line, then the verbatim staged diff.

    Captured from a real `git commit` against a real repo with a real
    `.git/hooks/commit-msg` (issue #1212's own adversarial review), not
    hand-imagined: git strips the comments and everything from the
    scissors line down *after* the hook returns, so this raw shape is
    genuinely what the hook receives. `test_commit_msg_hook_receives_the_raw_
    uncleaned_file_from_real_git` below re-derives it live from real git
    rather than trusting this constant to stay accurate."""
    return (
        f"{subject}\n"
        "\n"
        "# Please enter the commit message for your changes. Lines starting\n"
        "# with '#' will be ignored, and an empty message aborts the commit.\n"
        "#\n"
        "# On branch main\n"
        "#\n"
        "# Changes to be committed:\n"
        "#\tnew file:   mod.py\n"
        "#\n"
        f"# {gate.SCISSORS_MARKER}\n"
        "# Do not modify or remove the line above.\n"
        "# Everything below it will be ignored.\n"
        "diff --git a/mod.py b/mod.py\n"
        "new file mode 100644\n"
        "index 0000000..52643d8\n"
        "--- /dev/null\n"
        "+++ b/mod.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def f():\n"
        f"+    # {staged_diff_citation}\n"
        "+    return 1\n"
    )


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
def test_commit_range_messages_counts_an_empty_message_commit_as_a_commit(tmp_path: pathlib.Path) -> None:
    """`git commit --allow-empty-message` produces a real, genuinely
    uncited commit whose `%B` is empty. Filtering empty entries out (the
    pre-review form) made a range of two such commits indistinguishable
    from an *empty range*, which `evaluate_pr_range` now passes as
    "nothing to check" -- so an uncited commit would have slipped the gate
    entirely. The list must have one entry per commit, empty or not."""
    root = _init_repo(tmp_path / "empty-messages")
    _commit(root, "a.txt", "chore: base")
    _run(["git", "checkout", "-q", "-b", "feature"], root)
    for name in ("b.txt", "c.txt"):
        (root / name).write_text(f"{name}\n", encoding="utf-8")
        _run(["git", "add", "--", name], root)
        _run(["git", "commit", "-q", "--allow-empty-message", "-m", ""], root)

    assert gate.commit_range_messages(root, "main", "feature") == ["", ""]


@pytest.mark.slow
def test_evaluate_pr_range_uncited_empty_message_commits_still_fail(tmp_path: pathlib.Path) -> None:
    """The end of the same defect: those two commits are uncited, so even
    the lenient `pr_text_supplied=False` local shape must still FAIL --
    "nothing to check" means an empty *range*, never "every commit's
    message happened to be empty"."""
    root = _init_repo(tmp_path / "empty-messages-verdict")
    _commit(root, "a.txt", "chore: base")
    _run(["git", "checkout", "-q", "-b", "feature"], root)
    (root / "b.txt").write_text("b\n", encoding="utf-8")
    _run(["git", "add", "--", "b.txt"], root)
    _run(["git", "commit", "-q", "--allow-empty-message", "-m", ""], root)

    passed, message = gate.evaluate_pr_range(root, "", "", "", "", "main", "feature", pr_text_supplied=False)
    assert passed is False
    assert "nothing to check" not in message


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


def test_root_must_exist_rejects_a_file_path_directly(tmp_path: pathlib.Path) -> None:
    # Calls the pydantic validator directly (not only through CommitCitationArgs
    # construction above), so a not-a-directory root is rejected even when it
    # names an existing file rather than a missing path.
    not_a_dir = tmp_path / "a-file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.CommitCitationArgs._root_must_exist(not_a_dir)


def test_root_must_exist_accepts_a_real_directory(tmp_path: pathlib.Path) -> None:
    assert gate.CommitCitationArgs._root_must_exist(tmp_path) == tmp_path


def test_commit_msg_file_required_in_commit_msg_mode_direct_call(tmp_path: pathlib.Path) -> None:
    # Calls the model_validator directly against an already-constructed
    # instance -- pydantic normally runs it during __init__ (asserted via
    # CommitCitationArgs above), but this exercises the method itself.
    pr_range_args = gate.CommitCitationArgs(
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
    # pydantic wraps a `@model_validator` method in a descriptor proxy mypy's
    # stubs do not model as callable on an instance -- a real runtime call
    # (pydantic's own `__get__` returns the bound method), not a static-typing
    # gap in the call itself.
    assert pr_range_args._commit_msg_file_required_in_commit_msg_mode() is pr_range_args  # type: ignore[operator]


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


# --- issue #1212 adversarial review: the raw-COMMIT_EDITMSG false PASS ------


def test_truncate_at_scissors_cuts_the_line_itself_and_everything_below() -> None:
    text = f"fix: real subject\n\n# {gate.SCISSORS_MARKER}\n# ignored\ndiff --git a/x b/x\n+#42\n"
    assert gate.truncate_at_scissors(text) == "fix: real subject\n\n"


def test_truncate_at_scissors_leaves_an_ordinary_message_untouched() -> None:
    text = "fix: real subject\n\nCloses #42\n"
    assert gate.truncate_at_scissors(text) == text


def test_clean_commit_message_strips_git_comments_and_the_scissors_diff(tmp_path: pathlib.Path) -> None:
    root = _init_repo(tmp_path / "repo")
    cleaned = gate.clean_commit_message(root, _raw_hook_commit_editmsg("chore: tidy up formatting", "See #1212"))
    assert cleaned.strip() == "chore: tidy up formatting"


def test_clean_commit_message_honors_a_custom_core_comment_char(tmp_path: pathlib.Path) -> None:
    """`git stripspace` resolves core.commentChar itself, which is exactly
    why the comment strip is delegated to git rather than hardcoding `#`:
    a repository configuring `;` would defeat a hardcoded strip outright."""
    root = _init_repo(tmp_path / "repo-semicolon")
    _run(["git", "config", "core.commentChar", ";"], root)
    raw = "chore: tidy up formatting\n\n; Please enter the commit message ; Refs #1212\n"
    assert gate.clean_commit_message(root, raw).strip() == "chore: tidy up formatting"


def test_clean_commit_message_raises_rather_than_falling_back_when_stripspace_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `git stripspace` that cannot run must be exit-2 "the check could
    not be trusted", never a silent fallback to the *unstripped* text --
    that fallback would restore the false PASS below, invisibly, on
    exactly the broken-environment path nobody is watching."""

    class _Failed:
        returncode = 1
        stdout = ""
        stderr = "git: 'stripspace' is not a git command"

    monkeypatch.setattr(gate._gitapex_base_ref, "run_git", lambda *_a, **_k: _Failed())
    with pytest.raises(gate.CitationGateError, match="git stripspace --strip-comments failed"):
        gate.clean_commit_message(tmp_path, "chore: tidy\n")


def test_main_commit_msg_a_citation_only_in_the_staged_diff_below_scissors_still_fails(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exact false-PASS issue #1212's own adversarial review
    reproduced live: with `commit.verbose=true`, the file git hands a
    `commit-msg` hook still carries the whole staged diff below the
    scissors line, and a *source file* containing a citation-shaped
    comment (`# See issue #1212 for the rationale.`) made this gate report
    PASS for a commit whose actually-stored message was the uncited
    `chore: tidy up formatting`. Git strips comments and the scissors
    block only *after* the hook returns, so the gate has to do it itself.
    Confirmed to have teeth: reverting `_run_commit_msg` to check the raw
    text makes this test PASS the gate (exit 0) again."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(
        _raw_hook_commit_editmsg("chore: tidy up formatting", "See issue #1212 for the rationale."),
        encoding="utf-8",
    )
    assert gate.main(["--mode", "commit-msg", str(msg_file), "--root", str(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_commit_msg_a_real_citation_survives_the_cleaning(tmp_path: pathlib.Path) -> None:
    """The other half of the same fix: cleaning must not eat a genuine
    citation sitting in the real message, above git's own comment block."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(
        _raw_hook_commit_editmsg("fix: correct the bug\n\nCloses #42", "unrelated prose"), encoding="utf-8"
    )
    assert gate.main(["--mode", "commit-msg", str(msg_file), "--root", str(tmp_path)]) == 0


def test_main_commit_msg_a_citation_only_inside_gits_own_comment_block_still_fails(tmp_path: pathlib.Path) -> None:
    """The no-scissors half of the same class: a `commit.template` (or any
    `#`-prefixed guidance line) documenting the convention as `Refs #123`
    is a comment git will discard, not a citation."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("chore: tidy up formatting\n\n# Cite the issue, e.g. Refs #123\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file), "--root", str(tmp_path)]) == 1


@pytest.mark.slow
def test_commit_msg_hook_receives_the_raw_uncleaned_file_from_real_git(tmp_path: pathlib.Path) -> None:
    """Live end-to-end proof against real git rather than a hand-built
    fixture: a real repo, a real `.git/hooks/commit-msg`, `commit.verbose
    = true`, a staged file whose own content carries a citation-shaped
    line, and an uncited subject. Asserts both halves of the defect --
    that the file the hook receives really does still contain the
    uncleaned comment block, scissors line, and staged diff, and that the
    commit git actually stored cites nothing -- then runs the real gate
    over that captured file and requires a FAIL."""
    root = _init_repo(tmp_path / "live")
    _run(["git", "config", "commit.verbose", "true"], root)
    captured = tmp_path / "captured.txt"
    hook = root / ".git" / "hooks" / "commit-msg"
    hook.write_text(f'#!/bin/sh\ncp "$1" {captured}\nexit 0\n', encoding="utf-8")
    hook.chmod(0o755)

    # A non-interactive stand-in for the contributor's editor: it prepends an
    # uncited subject and leaves everything git itself prepared below it
    # untouched, which is exactly what a real editor session produces.
    editor = tmp_path / "editor.sh"
    editor.write_text(
        '#!/bin/sh\nprintf \'chore: tidy up formatting\\n%s\' "$(cat "$1")" > "$1.new"\nmv "$1.new" "$1"\n',
        encoding="utf-8",
    )
    editor.chmod(0o755)

    (root / "mod.py").write_text("def f():\n    # See issue #1212 for the rationale.\n    return 1\n", encoding="utf-8")
    _run(["git", "add", "--", "mod.py"], root)
    # GIT_EDITOR in the environment, not `git config core.editor`: the env var
    # wins over the config key, and some environments (this repository's own
    # container among them) already export GIT_EDITOR=true, which would
    # silently skip the editor entirely and abort on an empty message.
    subprocess.run(
        ["git", "commit", "-q"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_EDITOR": str(editor)},
    )

    raw = captured.read_text(encoding="utf-8")
    assert gate.SCISSORS_MARKER in raw  # git had NOT yet stripped the scissors block
    assert "See issue #1212" in raw  # the staged diff's own citation-shaped line is present
    stored = _run(["git", "log", "-1", "--format=%B"], root).stdout
    assert "#1212" not in stored  # ...but the commit git really stored cites nothing

    assert gate.main(["--mode", "commit-msg", str(captured), "--root", str(root)]) == 1


# --- issue #1212 adversarial review: the two layers must agree on merges ----


@pytest.mark.slow
def test_merge_in_progress_is_false_on_an_ordinary_checkout(tmp_path: pathlib.Path) -> None:
    root = _init_repo(tmp_path / "ordinary")
    _commit(root, "a.txt", "chore: init")
    assert gate.merge_in_progress(root) is False


@pytest.mark.slow
def test_main_commit_msg_exempts_a_merge_commit_matching_ci_no_merges(tmp_path: pathlib.Path) -> None:
    """`--mode pr-range` exempts merge commits via `git log --no-merges`
    (this issue's own stated non-goal). `--mode commit-msg` must reach the
    same verdict, or the two layers disagree and every ordinary `git
    merge` is rejected locally -- live-reproduced before this fix, with
    git left mid-merge ("Not committing merge; use 'git commit' to
    complete the merge"), which breaks this repository's own documented
    `git pull --no-rebase` shared-branch workflow.

    Left genuinely mid-merge here, with a real `MERGE_HEAD`, rather than
    faking the state: the merge is started with `--no-commit` so the gate
    runs against the same repository state a real `commit-msg` hook sees."""
    root = _init_repo(tmp_path / "merging")
    _commit(root, "a.txt", "chore: base (Refs #1)")
    _checkout_new_branch(root, "side")
    _commit(root, "s.txt", "feat: side (Refs #2)")
    _run(["git", "checkout", "-q", "main"], root)
    _commit(root, "m.txt", "chore: main moves on (Refs #3)")
    _run(["git", "merge", "-q", "--no-ff", "--no-commit", "side"], root)
    assert gate.merge_in_progress(root) is True

    # git's own default merge message, which cites nothing.
    msg_file = tmp_path / "MERGE_MSG"
    msg_file.write_text("Merge branch 'side'\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file), "--root", str(root)]) == 0


@pytest.mark.slow
def test_main_commit_msg_still_gates_an_ordinary_commit_in_the_same_repo(tmp_path: pathlib.Path) -> None:
    """The guard on the exemption above: once the merge is concluded the
    same repo gates an uncited ordinary commit again, so the exemption is
    scoped to a real in-progress merge rather than to the repository."""
    root = _init_repo(tmp_path / "merged-then-ordinary")
    _commit(root, "a.txt", "chore: base (Refs #1)")
    _checkout_new_branch(root, "side")
    _commit(root, "s.txt", "feat: side (Refs #2)")
    _run(["git", "checkout", "-q", "main"], root)
    _commit(root, "m.txt", "chore: main moves on (Refs #3)")
    _merge_no_ff(root, "side", "Merge branch 'side'")
    assert gate.merge_in_progress(root) is False

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("chore: tidy up formatting\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file), "--root", str(root)]) == 1


@pytest.mark.slow
def test_a_real_git_merge_succeeds_with_the_gate_installed_as_a_real_hook(tmp_path: pathlib.Path) -> None:
    """End-to-end against real git with the real script wired in as a real
    `.git/hooks/commit-msg`: the exact command that failed before this fix
    (`git merge --no-ff`, git's own default merge message) must now
    complete, while an uncited ordinary commit in the same repo is still
    rejected by the same installed hook."""
    root = _init_repo(tmp_path / "real-hook")
    hook = root / ".git" / "hooks" / "commit-msg"
    script = pathlib.Path(gate.__file__).resolve()
    hook.write_text(f'#!/bin/sh\nexec {sys.executable} {script} --mode commit-msg "$1" --root {root}\n', "utf-8")
    hook.chmod(0o755)

    _commit(root, "a.txt", "chore: base (Refs #1)")
    _checkout_new_branch(root, "side")
    _commit(root, "s.txt", "feat: side (Refs #2)")
    _run(["git", "checkout", "-q", "main"], root)
    _commit(root, "m.txt", "chore: main moves on (Refs #3)")

    _run(["git", "merge", "--no-ff", "-m", "Merge branch 'side'", "side"], root)
    assert _run(["git", "rev-list", "--count", "--merges", "HEAD"], root).stdout.strip() == "1"

    (root / "z.txt").write_text("z\n", encoding="utf-8")
    _run(["git", "add", "--", "z.txt"], root)
    rejected = subprocess.run(
        ["git", "commit", "-q", "-m", "chore: tidy up formatting"], cwd=root, capture_output=True, text=True
    )
    assert rejected.returncode != 0
    assert "cites no issue" in rejected.stdout + rejected.stderr


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


def test_extract_citations_or_raise_direct_call_passes_through_a_real_citation() -> None:
    resolving, context = gate._extract_citations_or_raise(None, None, None, "Closes #1212")
    assert resolving == (1212,)
    assert context == ()


def test_extract_citations_or_raise_direct_call_converts_value_error() -> None:
    huge_digit_run = "9" * 5000
    with pytest.raises(gate.CitationGateError, match="could not parse a citation number"):
        gate._extract_citations_or_raise(None, None, None, f"Closes #{huge_digit_run}")


def test_check_commit_message_an_implausibly_long_digit_run_raises_not_crashes() -> None:
    """Dimension 15 (`skills/evaluating-deterministic-gate-quality`): before
    this fix, a citation-shaped `#<thousands of digits>` string made
    `extract_citations`' own `int(n)` call raise an uncaught `ValueError`
    (Python's default integer-string-conversion digit limit, 4300) --
    escaping as exit 1, the code this module reserves for a *confirmed*
    no-citation FAIL, not a broken/adversarial input."""
    huge_digit_run = "9" * 5000
    with pytest.raises(gate.CitationGateError, match="could not parse a citation number"):
        gate.check_commit_message(f"Closes #{huge_digit_run}")


def test_main_commit_msg_an_implausibly_long_digit_run_exits_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    huge_digit_run = "9" * 5000
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(f"fix: bug\n\nCloses #{huge_digit_run}\n", encoding="utf-8")
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 2
    assert "could not parse a citation number" in capsys.readouterr().err


def test_main_pr_range_an_implausibly_long_digit_run_in_the_body_exits_two(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    huge_digit_run = "9" * 5000
    body_file = tmp_path / "body.txt"
    body_file.write_text(f"Closes #{huge_digit_run}\n", encoding="utf-8")
    exit_code = gate.main(
        ["--mode", "pr-range", "--root", str(tmp_path), "--body", str(body_file), "--head-ref", "HEAD"]
    )
    assert exit_code == 2
    assert "could not parse a citation number" in capsys.readouterr().err


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


# --- issue #1212 adversarial review: "nothing to check" is not a FAIL -------


def _empty_range_repo(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    """A repo whose `<ref>..HEAD` range is genuinely empty -- the state a
    checkout is in right after a fast-forward, or on a branch whose own
    commits are all already merged into `main`."""
    root = _init_repo(tmp_path / "empty-range")
    head = _commit(root, "a.txt", "chore: init")
    return root, head


@pytest.mark.slow
def test_evaluate_pr_range_an_empty_range_with_no_pr_text_supplied_is_not_a_failure(
    tmp_path: pathlib.Path,
) -> None:
    """`.gitapex/ssot.json`'s own `local_invocation` runs `--mode pr-range`
    with neither `--title` nor `--body`, and feeds the `pre-push` hook's
    `local-preflight` runner, which reads any non-zero exit as a blocked
    push. An empty range there has no commit and no PR text to evaluate at
    all, so there is nothing that *could* carry a citation -- reporting it
    as "you cited nothing" (live-reproduced as exit 1, issue #1212's own
    adversarial review) blocks a push over a non-violation."""
    root, head = _empty_range_repo(tmp_path)
    passed, message = gate.evaluate_pr_range(root, "", "", "", "", head, head, pr_text_supplied=False)
    assert passed is True
    assert "nothing to check" in message


@pytest.mark.slow
def test_evaluate_pr_range_an_empty_range_still_fails_when_pr_text_was_supplied(tmp_path: pathlib.Path) -> None:
    """The guard on the fix above: `pr_text_supplied` tracks whether the
    *flags were passed*, never whether their text is non-empty, so CI --
    which always passes both -- keeps its previous verdict even for an
    empty range. This is the branch that keeps the fix from becoming a
    blanket "empty range always passes"."""
    root, head = _empty_range_repo(tmp_path)
    passed, message = gate.evaluate_pr_range(root, "", "", "", "", head, head, pr_text_supplied=True)
    assert passed is False
    assert "neither the PR title/body nor any non-merge commit" in message


@pytest.mark.slow
def test_evaluate_pr_range_defaults_to_the_strict_pr_text_supplied(tmp_path: pathlib.Path) -> None:
    """Fail-closed default: a caller that omits `pr_text_supplied`
    entirely gets the strict verdict, not the lenient one."""
    root, head = _empty_range_repo(tmp_path)
    passed, _ = gate.evaluate_pr_range(root, "", "", "", "", head, head)
    assert passed is False


@pytest.mark.slow
def test_main_pr_range_empty_range_with_no_title_or_body_exits_zero(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End-to-end through `main`, in the exact `local_invocation` argv
    shape: no `--title`, no `--body`, empty range -> exit 0, with a
    message that names "nothing to check" rather than claiming a citation
    was missing."""
    root, head = _empty_range_repo(tmp_path)
    exit_code = gate.main(["--mode", "pr-range", "--base-ref", head, "--head-ref", head, "--root", str(root)])
    assert exit_code == 0
    assert "nothing to check" in capsys.readouterr().out


@pytest.mark.slow
def test_main_pr_range_empty_range_with_an_uncited_body_file_still_exits_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CI-shaped guard, end to end: the same empty range, but with a
    `--body` file supplied that cites nothing, still FAILs."""
    root, head = _empty_range_repo(tmp_path)
    body_file = tmp_path / "body.txt"
    body_file.write_text("no citation in this body", encoding="utf-8")
    exit_code = gate.main(
        [
            "--mode",
            "pr-range",
            "--base-ref",
            head,
            "--head-ref",
            head,
            "--root",
            str(root),
            "--body",
            str(body_file),
        ]
    )
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


# --- issue #1212 adversarial review: dimension-15 fail-closed input handling -


@pytest.mark.parametrize("mode_argv", [["--mode", "commit-msg"], ["--mode", "pr-range", "--body"]])
def test_main_a_path_argument_naming_a_directory_exits_two(
    mode_argv: list[str], tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dimension 15 (`skills/evaluating-deterministic-gate-quality`):
    before this fix `_read_input_file` caught only `FileNotFoundError` and
    `UnicodeDecodeError`, so pointing any path flag at a *directory*
    raised `IsADirectoryError` straight out of `main` -- an uncaught
    traceback whose Python exit code is 1, the very code this module
    reserves for a *confirmed* no-citation policy FAIL. A broken
    invocation reported itself as a real citation violation."""
    a_directory = tmp_path / "adir"
    a_directory.mkdir()
    assert gate.main([*mode_argv, str(a_directory)]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_main_commit_msg_an_unreadable_file_exits_two(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same dimension-15 arm reached through `PermissionError` rather
    than `IsADirectoryError` -- a file that exists and is valid UTF-8 but
    that this process cannot open at all. Raised through a monkeypatched
    `read_text` rather than a real `chmod(0o000)`: this repository's own
    container runs the suite as uid 0, where the mode bits are bypassed
    and the read simply succeeds, so a chmod-based fixture would assert
    nothing here while passing on a non-root CI runner."""

    def _deny(*_args: object, **_kwargs: object) -> str:
        raise PermissionError(13, "Permission denied")

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("chore: tidy up formatting\n", encoding="utf-8")
    monkeypatch.setattr(pathlib.Path, "read_text", _deny)
    assert gate.main(["--mode", "commit-msg", str(msg_file)]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_read_input_file_direct_call_returns_empty_text_for_none() -> None:
    assert gate._read_input_file(None) == ""


def test_read_input_file_direct_call_reads_a_real_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "body.txt"
    path.write_text("Closes #1212\n", encoding="utf-8")
    assert gate._read_input_file(str(path), label="pr body") == "Closes #1212\n"


def test_read_input_file_direct_call_raises_on_a_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.CitationGateError, match="could not be read"):
        gate._read_input_file(str(tmp_path), label="pr body")


def test_run_commit_msg_direct_call_passes_on_a_cited_message(tmp_path: pathlib.Path) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("fix: correct the bug\n\nCloses #1212\n", encoding="utf-8")
    args = gate.CommitCitationArgs(
        mode="commit-msg",
        commit_msg_file=str(msg_file),
        owner="",
        repo="",
        title=None,
        body=None,
        base_ref=None,
        head_ref="HEAD",
        root=tmp_path,
    )
    assert gate._run_commit_msg(args) == 0


def test_run_commit_msg_direct_call_fails_on_an_uncited_message(tmp_path: pathlib.Path) -> None:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("chore: tidy up formatting\n", encoding="utf-8")
    args = gate.CommitCitationArgs(
        mode="commit-msg",
        commit_msg_file=str(msg_file),
        owner="",
        repo="",
        title=None,
        body=None,
        base_ref=None,
        head_ref="HEAD",
        root=tmp_path,
    )
    assert gate._run_commit_msg(args) == 1


def test_run_pr_range_direct_call_passes_on_a_cited_body(tmp_path: pathlib.Path) -> None:
    body_file = tmp_path / "body.txt"
    body_file.write_text("Closes #1212\n", encoding="utf-8")
    args = gate.CommitCitationArgs(
        mode="pr-range",
        commit_msg_file=None,
        owner="tvna",
        repo="gitapex",
        title=None,
        body=str(body_file),
        base_ref="HEAD",
        head_ref="HEAD",
        root=tmp_path,
    )
    assert gate._run_pr_range(args) == 0


def test_run_pr_range_direct_call_fails_with_no_citation_anywhere(tmp_path: pathlib.Path) -> None:
    root, base_sha, head_sha = _build_range_repo(tmp_path, citing_commit=False)
    args = gate.CommitCitationArgs(
        mode="pr-range",
        commit_msg_file=None,
        owner="",
        repo="",
        title=None,
        body=None,
        base_ref=base_sha,
        head_ref=head_sha,
        root=root,
    )
    # A genuinely non-empty, genuinely uncited commit range: neither
    # --title nor --body was passed (pr_text_supplied defaults to True per
    # evaluate_pr_range's own strict default), so this is the ordinary
    # policy FAIL, not the empty-range "nothing to check" PASS.
    assert gate._run_pr_range(args) == 1


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

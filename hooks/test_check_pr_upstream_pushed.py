"""Regression suite for check-pr-upstream-pushed.sh's own deny/allow matrix.

Issue #187 (via #525): a PreToolUse hook (matcher:
mcp__github__create_pull_request) blocking a PR-open call for a branch
that has no upstream configured, or has local commits not yet pushed to
its upstream -- both reproduce #187's "No commits between main and
<branch>" failure.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_check_issue_acm_disclosure.py.
Each test builds its own throwaway git repo (and, where needed, a bare
"origin") under tmp_path -- this hook's precondition only means anything
against real local git state, unlike the JSON-body-only hooks.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-pr-upstream-pushed.sh"


def _git_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(
        {
            "HOME": str(tmp_path),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _git(*args: str, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), env=env, check=True, capture_output=True)


def _repo_with_commit(tmp_path: Path, env: dict[str, str], branch: str = "feature-x") -> Path:
    work = tmp_path / "work"
    work.mkdir()
    _git("init", cwd=work, env=env)
    _git("checkout", "-b", branch, cwd=work, env=env)
    (work / "file.txt").write_text("hello\n")
    _git("add", "file.txt", cwd=work, env=env)
    _git("commit", "-m", "init", cwd=work, env=env)
    return work


def _pushed_repo(tmp_path: Path, env: dict[str, str], branch: str = "feature-x") -> Path:
    work = _repo_with_commit(tmp_path, env, branch)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], env=env, check=True, capture_output=True)
    _git("remote", "add", "origin", str(origin), cwd=work, env=env)
    _git("push", "-u", "origin", branch, cwd=work, env=env)
    return work


def run(
    *,
    tool_name: str = "mcp__github__create_pull_request",
    head: str = "feature-x",
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {
                "owner": "tvna",
                "repo": "gitapex",
                "title": "x",
                "base": "main",
                "head": head,
            },
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(cwd),
    )


def assert_denied(result: subprocess.CompletedProcess[str], *, message_substring: str) -> None:
    assert result.returncode == 2, f"expected deny, got {result.returncode}: {result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]
    assert message_substring in payload["systemMessage"]


def assert_allowed_silently(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f"expected allow, got {result.returncode}: {result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def assert_allowed_with_warning(result: subprocess.CompletedProcess[str], *, warning_substring: str) -> None:
    assert result.returncode == 0, f"expected fail-open allow, got {result.returncode}: {result.stderr!r}"
    assert result.stdout == ""
    assert warning_substring in result.stderr


def test_allowed_when_branch_is_pushed_and_up_to_date(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    work = _pushed_repo(tmp_path, env)
    assert_allowed_silently(run(cwd=work, env=env))


def test_denied_when_no_upstream_configured(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    work = _repo_with_commit(tmp_path, env)  # no remote, no push at all
    assert_denied(run(cwd=work, env=env), message_substring="has no upstream configured")


def test_denied_when_local_head_has_unpushed_commit_ahead_of_upstream(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    work = _pushed_repo(tmp_path, env)
    (work / "file2.txt").write_text("more\n")
    _git("add", "file2.txt", cwd=work, env=env)
    _git("commit", "-m", "second", cwd=work, env=env)
    assert_denied(run(cwd=work, env=env), message_substring="not yet pushed to its upstream")


def test_fail_open_when_not_a_git_repo(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert_allowed_with_warning(
        run(cwd=not_a_repo, env=env),
        warning_substring="is not running inside a git work tree",
    )


def test_fail_open_when_head_does_not_match_checked_out_branch(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    # No upstream configured either -- would deny if the mismatch check
    # didn't short-circuit first.
    work = _repo_with_commit(tmp_path, env, branch="feature-x")
    assert_allowed_with_warning(
        run(cwd=work, env=env, head="some-other-branch"),
        warning_substring="does not match the currently checked-out branch",
    )


def test_fail_open_when_head_is_detached(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    work = _repo_with_commit(tmp_path, env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()
    _git("checkout", sha, cwd=work, env=env)
    assert_allowed_with_warning(run(cwd=work, env=env), warning_substring="detached HEAD")


def test_non_matching_tool_name_is_ignored(tmp_path: Path) -> None:
    assert_allowed_silently(run(tool_name="Bash", cwd=tmp_path, env=_git_env(tmp_path)))

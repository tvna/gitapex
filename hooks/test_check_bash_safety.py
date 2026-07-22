"""Regression suite for check-bash-safety.sh's own deny/warn/allow matrix.

Refs #280 (retro on PR #279), proposed gate 1: this file is the template
run named there -- the shared hook check_task_bash_safety.sh was adapted
from ("references/threat-model-and-authorization.md" documents that
lineage) had never had one either. Scope is test-only: this file asserts
today's shipped behavior, including gaps this hook does not close (e.g. it
has no `npm ci` / `pnpm install` / bare-`pnpm`/`yarn` / curl-pipe-sh / npx
coverage -- those were added to check_task_bash_safety.sh's own,
stricter, task-agent-scoped copy, not ported back here). No script logic
changes; hooks/check-bash-safety.sh is a shared dependency of multiple
skills and this task's scope is tests only.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, rather than re-deriving the regexes in Python.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-bash-safety.sh"
REPO_ROOT = Path(__file__).parent.parent
SCAN_SCRIPT_RELATIVE = "skills/outward-artifact-preflight/scripts/scan_provenance.py"


def run(
    command: str, tool_name: str = "Bash", extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def assert_denied(command: str) -> None:
    result = run(command)
    assert result.returncode == 2, f"expected deny (exit 2) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(command: str) -> None:
    result = run(command)
    assert result.returncode == 0, f"expected allow (exit 0) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    # warn() also exits 0 while emitting a systemMessage on stdout -- exit
    # code alone can't distinguish a clean allow from a regression that
    # starts warning on one of these commands, so require silence too.
    assert result.stdout == "", f"expected no warn output for {command!r}, got stdout={result.stdout!r}"
    assert result.stderr == ""


# --- Finding 1: package/plugin install verbs -------------------------------
DENIED_INSTALL_COMMANDS = [
    ("pip install requests", "pip-install"),
    ("npm install lodash", "npm-install"),
    ("npm i lodash", "npm-i"),
    ("yarn add lodash", "yarn-add"),
    ("pnpm add lodash", "pnpm-add"),
    ("go install ./...", "go-install"),
    ("brew install wget", "brew-install"),
    ("apt-get install curl", "apt-get-install"),
    ("apt install curl", "apt-install"),
    ("gem install rails", "gem-install"),
    ("cargo install ripgrep", "cargo-install"),
    ("uv pip install requests", "uv-pip-install"),
    ("uv add requests", "uv-add"),
    ("plugin install foo", "plugin-install"),
]

# --- Findings 2 & 3: direct CLI GitHub write commands ----------------------
DENIED_GH_COMMANDS = [
    ("gh issue create --title x", "gh-issue-create"),
    ("gh issue edit 1 --title x", "gh-issue-edit"),
    ("gh issue close 1", "gh-issue-close"),
    ("gh issue comment 1 --body hi", "gh-issue-comment"),
    ("gh issue delete 42", "gh-issue-delete"),
    ("gh issue reopen 1", "gh-issue-reopen"),
    ("gh issue lock 1", "gh-issue-lock"),
    ("gh pr create --title x", "gh-pr-create"),
    ("gh pr edit 1 --title x", "gh-pr-edit"),
    ("gh pr close 1", "gh-pr-close"),
    ("gh pr merge 1", "gh-pr-merge"),
    ("gh pr merge 1 --auto", "gh-pr-merge-auto"),
    ("gh pr review 7 --approve", "gh-pr-review"),
    ("gh pr ready 1", "gh-pr-ready"),
    ("gh api repos/o/r/issues -X POST -f title=x", "gh-api-dash-x-post"),
    ("gh api repos/o/r/issues --method POST", "gh-api-method-post"),
    ("gh api repos/o/r/issues --method=POST", "gh-api-method-eq-post"),
    ("gh api repos/o/r/issues -XPOST", "gh-api-xpost-attached"),
    ("gh api graphql -f query=mutation{createissue}", "gh-api-graphql-mutation"),
    ("gh api repos/o/r/issues -f title=x", "gh-api-field-flag-implicit-write"),
]

ALLOWED_GH_COMMANDS = [
    ("gh issue view 1", "gh-issue-view"),
    ("gh issue list", "gh-issue-list"),
    ("gh pr view 1", "gh-pr-view"),
    ("gh pr list", "gh-pr-list"),
    ("gh pr diff 1", "gh-pr-diff"),
    ("gh pr checks 1", "gh-pr-checks"),
    ("gh api repos/o/r/issues", "gh-api-get-no-method"),
    ("gh api graphql -f query=query{viewer{login}}", "gh-api-graphql-query"),
]

ALLOWED_ORDINARY_COMMANDS = [
    ("git status --short", "git-status"),
    ("git commit -m test", "git-commit"),
    ("npm run build", "npm-run-build"),
    ("npm test", "npm-test"),
    ("yarn test", "yarn-test"),
    ("pytest", "pytest"),
]


@pytest.mark.parametrize("command,case_id", DENIED_INSTALL_COMMANDS, ids=[c[1] for c in DENIED_INSTALL_COMMANDS])
def test_denied_install(command: str, case_id: str) -> None:
    assert_denied(command)


@pytest.mark.parametrize("command,case_id", DENIED_GH_COMMANDS, ids=[c[1] for c in DENIED_GH_COMMANDS])
def test_denied_gh(command: str, case_id: str) -> None:
    assert_denied(command)


@pytest.mark.parametrize("command,case_id", ALLOWED_GH_COMMANDS, ids=[c[1] for c in ALLOWED_GH_COMMANDS])
def test_allowed_gh(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize("command,case_id", ALLOWED_ORDINARY_COMMANDS, ids=[c[1] for c in ALLOWED_ORDINARY_COMMANDS])
def test_allowed_ordinary(command: str, case_id: str) -> None:
    assert_allowed(command)


def test_non_bash_tool_name_is_ignored() -> None:
    result = run("gh pr merge 1", tool_name="Write")
    assert result.returncode == 0


def test_empty_command_is_allowed() -> None:
    assert_allowed("")


# ---------------------------------------------------------------------------
# Finding 4: git push gated (warn, not deny) on scan_provenance.py
# ---------------------------------------------------------------------------


def _init_repo_with_commit(repo_dir: Path, *, second_commit_message: str | None) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=str(repo_dir), check=True, capture_output=True, text=True)

    repo_dir.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("symbolic-ref", "HEAD", "refs/heads/main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo_dir / "a.txt").write_text("base\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "base commit")
    if second_commit_message is not None:
        (repo_dir / "a.txt").write_text("changed\n")
        git("add", "a.txt")
        git("commit", "-q", "-m", second_commit_message)


def test_git_push_denied_when_scan_script_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    result = run("git push origin HEAD", extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "scan_provenance.py" in payload["systemMessage"]


def _fake_session_url() -> str:
    # Assembled at runtime rather than written as one contiguous literal:
    # scan_provenance.py's own "anthropic session domain" pattern would
    # otherwise match this fixture in this very file's diff, making the
    # production pre-push hook warn on this test file itself whenever this
    # commit is part of an outgoing push.
    return "https://" + "claude.ai" + "/x/session_" + "abc123"


def test_git_push_warns_when_scan_flags_a_hit(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "scan_provenance.py").write_text((REPO_ROOT / SCAN_SCRIPT_RELATIVE).read_text())
    _init_repo_with_commit(
        project_dir,
        second_commit_message=f"Add feature\n\nSee {_fake_session_url()} for context.",
    )
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert "flagged the outgoing push for review" in payload["systemMessage"]


def test_git_push_silent_when_scan_finds_nothing(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "scan_provenance.py").write_text((REPO_ROOT / SCAN_SCRIPT_RELATIVE).read_text())
    _init_repo_with_commit(project_dir, second_commit_message="Fix bug in parser")
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

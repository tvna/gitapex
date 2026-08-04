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
SCAN_SCRIPT_RELATIVE = "skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py"


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
    assert result.returncode == 2, (
        f"expected deny (exit 2) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(command: str) -> None:
    result = run(command)
    assert result.returncode == 0, (
        f"expected allow (exit 0) for {command!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
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

# --- Known, disclosed, unresolved regex-gate bypasses ----------------------
# This script shares the same cmd_boundary/whitespace-anchored regex
# construction that skills/executing-a-branch-plan/scripts/
# check_task_bash_safety.sh was adapted from -- its own KNOWN_BYPASS_COMMANDS
# (see the sibling test file) pins these identical 4 cases as unresolved
# there; this script is equally bypassed by them today (verified directly:
# all 4 return exit 0/unblocked against this script too), but neither this
# script's own header comment nor references/threat-model-and-authorization.md
# discloses that ceiling for THIS file specifically -- only for the sibling.
# These tests pin *current* (bypassed) behavior, same as the sibling file's:
# not a "should be fixed" assertion. If one of these ever starts returning
# exit 2, the gap closed -- update this test (and consider whether the
# disclosure convention now needs to name this script too).
KNOWN_BYPASS_COMMANDS = [
    ("git${IFS}push origin HEAD", "ifs-substitution-git-push"),
    ('gi""t push origin HEAD', "empty-quote-split-git"),
    ("pip${IFS}install foo", "ifs-substitution-pip-install"),
    (r"p\ip install foo", "backslash-escape-pip"),
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


@pytest.mark.parametrize("command,case_id", KNOWN_BYPASS_COMMANDS, ids=[c[1] for c in KNOWN_BYPASS_COMMANDS])
def test_known_bypass_still_unblocked(command: str, case_id: str) -> None:
    result = run(command)
    assert result.returncode == 0, (
        f"documented bypass {case_id!r} ({command!r}) is now blocked (exit {result.returncode}); "
        "if this is an intentional fix, update this test and consider whether the disclosure "
        "convention now needs to name this script specifically"
    )


def test_non_bash_tool_name_is_ignored() -> None:
    result = run("gh pr merge 1", tool_name="Write")
    assert result.returncode == 0


def test_empty_command_is_allowed() -> None:
    assert_allowed("")


# ---------------------------------------------------------------------------
# Finding 4: git push gated (warn, not deny) on gitapex_scan_provenance.py
# ---------------------------------------------------------------------------


def _init_diverged_repo(repo_dir: Path, *, feature_commit_messages: list[str]) -> None:
    """Build a repo with a `main` base commit, then check out a `feature`
    branch (left as HEAD) carrying one commit per message.

    Committing onto a *separate* branch -- rather than straight onto
    `main`, as an earlier version of this fixture did -- matters: with no
    upstream set, hooks/check-bash-safety.sh falls back to `merge-base
    <candidate-ref> HEAD` against origin/HEAD, origin/main, origin/master,
    main, master in turn. If HEAD *is* `main` (the earlier fixture), that
    merge-base is HEAD itself, the scan range collapses to empty, and the
    script silently falls through to its tip-commit-only fallback -- the
    exact old behavior the merge-base range scan was added to fix, and a
    regression back to it would pass this fixture undetected. Diverging
    onto `feature` gives `main` a distinct, earlier tip, so the merge-base
    range genuinely spans every `feature_commit_messages` commit, not just
    HEAD's own tip.
    """

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            # Isolate from the host/CI runner's own global or system git
            # config (e.g. commit.gpgsign=true with no reachable signing
            # key) so this fixture can't hang or fail for reasons unrelated
            # to check-bash-safety.sh's own behavior.
            env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
        )

    repo_dir.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("symbolic-ref", "HEAD", "refs/heads/main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo_dir / "a.txt").write_text("base\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "base commit")
    git("checkout", "-q", "-b", "feature")
    for i, message in enumerate(feature_commit_messages):
        (repo_dir / "a.txt").write_text(f"change {i}\n")
        git("add", "a.txt")
        git("commit", "-q", "-m", message)


def test_git_push_denied_when_scan_script_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    result = run("git push origin HEAD", extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_scan_provenance.py" in payload["systemMessage"]


def _fake_session_url() -> str:
    # Assembled at runtime rather than written as one contiguous literal:
    # gitapex_scan_provenance.py's own "anthropic session domain" pattern would
    # otherwise match this fixture in this very file's diff, making the
    # production pre-push hook warn on this test file itself whenever this
    # commit is part of an outgoing push.
    return "https://" + "claude.ai" + "/x/session_" + "abc123"


def _project_with_scan_script(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "gitapex_scan_provenance.py").write_text((REPO_ROOT / SCAN_SCRIPT_RELATIVE).read_text())
    return project_dir


def test_git_push_warns_when_scan_flags_a_hit(tmp_path: Path) -> None:
    project_dir = _project_with_scan_script(tmp_path)
    # The marker sits in the *first* feature commit, with a clean commit on
    # top as HEAD -- so this only passes if the merge-base range scan (both
    # feature commits) runs, not the tip-only fallback (which would see
    # only the clean tip and miss it). See _init_diverged_repo's docstring.
    _init_diverged_repo(
        project_dir,
        feature_commit_messages=[
            f"Add feature\n\nSee {_fake_session_url()} for context.",
            "Fix typo",
        ],
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
    project_dir = _project_with_scan_script(tmp_path)
    _init_diverged_repo(project_dir, feature_commit_messages=["Fix bug in parser"])
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

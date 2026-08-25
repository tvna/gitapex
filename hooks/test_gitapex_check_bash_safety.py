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
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-bash-safety.sh"
REPO_ROOT = Path(__file__).parent.parent
SCAN_SCRIPT_RELATIVE = "skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py"


def run(
    command: str, tool_name: object = "Bash", extra_env: dict[str, str] | None = None
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
    ("uv install requests", "uv-install"),
    ("plugin install foo", "plugin-install"),
]

# --- Issue #1320: declarative package-manager commands allowed -------------
# `uv add`/`uv remove` mutate pyproject.toml/uv.lock, so a dependency change
# made this way shows up in the PR diff for review -- unlike `uv pip
# install`/bare `uv install` (still denied above), which install into the
# venv with no diff trail. `apm install`/`apm uninstall` were never matched
# by install_re at all (no "apm" pattern exists); these two pin that
# already-allowed behavior as a regression test rather than relaxing an
# actual block, so a future widened install_re (e.g. a broader "plugin
# install" pattern) can't silently sweep `apm` back into deny unnoticed.
ALLOWED_DECLARATIVE_PACKAGE_COMMANDS = [
    ("uv add requests", "uv-add"),
    ("uv remove requests", "uv-remove"),
    ("apm install foo", "apm-install"),
    ("apm uninstall foo", "apm-uninstall"),
]

# --- Issue #1320 defeat-test: chaining a newly-allowed uv add/remove ahead
# of a still-denied uv pip install/uv install must NOT smuggle the denied
# verb past this gate. install_re is a substring scan over the whole
# command string (no anchoring to the first token), so a still-denied verb
# appearing anywhere after a shell separator (&&, ;, |) must still be
# caught -- this is the specific way the new carve-out could have been
# exploited had it been implemented as a first-token/early-return check
# instead of a shared substring pattern.
DENIED_CHAINED_AFTER_ALLOWED_COMMANDS = [
    ("uv add safe && uv pip install malicious", "uv-add-then-pip-install-chained"),
    ("uv remove safe; uv install malicious", "uv-remove-then-install-chained"),
    ("uv add safe | uv install malicious", "uv-add-then-install-piped"),
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


@pytest.mark.parametrize(
    "command,case_id",
    ALLOWED_DECLARATIVE_PACKAGE_COMMANDS,
    ids=[c[1] for c in ALLOWED_DECLARATIVE_PACKAGE_COMMANDS],
)
def test_allowed_declarative_package_commands(command: str, case_id: str) -> None:
    assert_allowed(command)


@pytest.mark.parametrize(
    "command,case_id",
    DENIED_CHAINED_AFTER_ALLOWED_COMMANDS,
    ids=[c[1] for c in DENIED_CHAINED_AFTER_ALLOWED_COMMANDS],
)
def test_denied_chained_after_allowed(command: str, case_id: str) -> None:
    assert_denied(command)


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
# Issue #1208: fail closed, not open, when jq is missing or the payload is
# malformed. Ported guard prologue, same one hooks/check-pr-issue-acm-
# disclosure.sh and hooks/check-pr-title-convention.sh already carried.
# ---------------------------------------------------------------------------


def _no_jq_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except jq, so
    `command -v jq` genuinely fails the way it would in an environment
    without jq installed -- rather than mocking that condition."""
    bin_dir = tmp_path / "no-jq-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "tr", "grep", "sed", "git", "python3", "dirname"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def test_denied_when_jq_missing(tmp_path: Path) -> None:
    """Live-reproduced before this fix: with jq absent, the very first jq
    call (extracting tool_name) crashed under `set -e` with exit 127
    ("command not found") -- before deny() was even defined, and non-
    blocking per Claude Code's PreToolUse contract, so an arbitrary Bash
    command (including `gh pr merge`) would have proceeded unchecked. Must
    now deny (exit 2) instead."""
    result = run("gh pr merge 1", extra_env={"PATH": _no_jq_path(tmp_path)})
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in payload["systemMessage"]


def test_denied_on_malformed_json_stdin() -> None:
    """Live-reproduced before this fix: jq's own parse-error exit (5)
    propagated past deny() under `set -e` -- non-blocking per Claude Code's
    PreToolUse contract. Must now deny (exit 2) instead."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_input",
    [["not", "an", "object"], "text", False, True, 0],
    ids=["array", "string", "false", "true", "zero"],
)
def test_denied_when_tool_input_is_not_an_object(tool_input: object) -> None:
    """A well-formed top-level payload whose tool_input is itself a
    non-object would otherwise crash the `.tool_input.command` access with
    jq's own "Cannot index" error. Must deny.

    `false` is the case that actually escaped the original guard: found by
    code review (PR #1213) after the array/string cases above already
    passed -- jq's `//` operator treats JSON `false` the same as `null`
    (both are falsy), so `(.tool_input // {}) | type == "object"` wrongly
    accepted it, and the crash happened one line later, past deny()."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": tool_input})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for tool_input={tool_input!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allowed_when_tool_input_is_absent_or_null() -> None:
    """jq indexes `null`/a missing key as `null`, not a runtime error, so
    these fall through the shape guard to the hook's own downstream logic
    (an empty `command` here, which is itself allowed) rather than being
    wrongly caught by it -- unlike the non-object shapes above."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    for payload in (
        json.dumps({"tool_name": "Bash"}),
        json.dumps({"tool_name": "Bash", "tool_input": None}),
    ):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"payload={payload!r}: expected allow, got {result.returncode}"
        assert result.stdout == ""
        assert result.stderr == ""


@pytest.mark.parametrize("tool_name", [["Bash"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"])
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    """Found by code review (PR #1213): jq -r never errors on a non-string
    `.tool_name` -- it pretty-prints the JSON form across multiple lines
    instead, which then never equals the plain "Bash" string the matcher
    re-check compares against, silently falling through as "not our tool"
    (exit 0) instead of failing closed. Live-confirmed before this guard
    existed: an array-wrapped tool_name let a `gh pr merge` command
    straight through. Must now deny."""
    result = run("gh pr merge 1", tool_name=tool_name)
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [["gh", "pr", "merge", "1"], {"argv": ["gh", "pr", "merge", "1"]}, 5, True],
    ids=["array", "object", "number", "bool"],
)
def test_denied_when_tool_input_command_is_not_a_string(command: object) -> None:
    """Found by code review (PR #1213, round 4): jq -r never errors on a
    non-string `.tool_input.command` -- for an array/object it pretty-
    prints the JSON form across multiple lines, which splits a dangerous
    substring across JSON punctuation (quotes, commas, brackets) and
    breaks every `[[:space:]]`-anchored danger-pattern regex below,
    silently letting a genuinely dangerous command through (exit 0)
    instead of failing closed. Live-confirmed before this guard existed:
    an array-wrapped `["gh","pr","merge","1"]` command let a real merge
    call straight through. Must now deny."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for command={command!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_valid_json_non_object_stdin() -> None:
    """Valid JSON that isn't an object at the top level (e.g. a bare array)
    would otherwise crash the first field-extraction jq call the same way.
    Must deny."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="[]",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


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


def _project_with_huge_warning_scan_script(tmp_path: Path, *, size: int = 3_000_000) -> Path:
    """A project dir whose scan script is a stand-in, not the real
    gitapex_scan_provenance.py: it always exits 1 with `size` bytes of
    output, to exercise warn()'s own robustness against a large message in
    isolation from the real scanner's detection logic (covered by that
    script's own test suite elsewhere)."""
    project_dir = tmp_path / "project"
    scan_dir = project_dir / "skills" / "outward-artifact-preflight" / "scripts"
    scan_dir.mkdir(parents=True)
    (scan_dir / "gitapex_scan_provenance.py").write_text(f"import sys\nsys.stdout.write('A' * {size})\nsys.exit(1)\n")
    return project_dir


def test_git_push_warn_survives_a_huge_scan_message(tmp_path: Path) -> None:
    """Found by code review (PR #1213): warn()'s own pre-fix form (`jq -n
    --arg`) crashed with exit 126 ("Argument list too long") on a
    message this large -- live-confirmed before the fix, via the same
    construction used here. Under `set -euo pipefail` that crash would
    abort the whole script before `exit 0`; the push still proceeds
    either way (any non-2 exit is non-blocking per Claude Code's
    PreToolUse contract), but the warning itself would be silently lost
    instead of reaching the operator. Must now exit 0 with the full
    message intact."""
    project_dir = _project_with_huge_warning_scan_script(tmp_path)
    _init_diverged_repo(project_dir, feature_commit_messages=["Fix bug in parser"])
    result = run(
        "git push origin HEAD",
        extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)},
    )
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr[:500]!r}"
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert "flagged the outgoing push for review" in payload["systemMessage"]
    assert len(payload["systemMessage"]) > 3_000_000


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

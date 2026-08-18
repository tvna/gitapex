"""Regression suite for check-merge-pull-request-block.sh's own deny/allow
matrix.

Issue #637: a PreToolUse hook (matcher: mcp__github__merge_pull_request)
blocking every call to that tool unconditionally -- this repository's
policy (planning-a-branch-from-an-issue/SKILL.md,
drafting-a-pr-to-merge/SKILL.md step 9, the ranking-the-open-queue Routine
specs' "100% human review of any pull request merge") is that no agent tool
call ever merges a PR here, no exceptions. hooks/check-bash-safety.sh
already blocks the equivalent shell form (`gh pr merge`); this hook closes
the identical gap for the platform-integrated MCP tool call.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_gitapex_check_bash_safety.py
and hooks/test_gitapex_check_issue_acm_disclosure.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-merge-pull-request-block.sh"
REPO_ROOT = Path(__file__).parent.parent


def run(
    *,
    tool_name: str = "mcp__github__merge_pull_request",
    tool_input: dict[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": tool_input
            if tool_input is not None
            else {"owner": "tvna", "repo": "gitapex", "pullNumber": 1},
        }
    )
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_denied_unconditionally() -> None:
    result = run()
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "merge_pull_request" in payload["systemMessage"]
    assert "human or CI decision" in payload["systemMessage"]


def test_denied_regardless_of_pull_number_or_repo() -> None:
    result = run(tool_input={"owner": "other-owner", "repo": "other-repo", "pullNumber": 999})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_with_merge_method_specified() -> None:
    # No override phrase or field escapes the block -- an explicit
    # merge_method (squash/rebase/merge) is still denied unconditionally.
    result = run(tool_input={"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "merge_method": "squash"})
    assert result.returncode == 2


def test_non_matching_tool_name_is_ignored() -> None:
    result = run(tool_name="mcp__github__update_pull_request", tool_input={"draft": True})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_bash_gh_pr_merge_is_ignored_by_this_hook() -> None:
    # This hook only matches the MCP tool call; the shell form is
    # check-bash-safety.sh's own responsibility, exercised in
    # test_gitapex_check_bash_safety.py, not duplicated here.
    result = run(tool_name="Bash", tool_input={"command": "gh pr merge 1"})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Issue #1208: fail closed, not open, when jq is missing or the payload is
# malformed -- highest priority in that issue, since this hook backs the
# repository's single most categorical "no override" deny.
# ---------------------------------------------------------------------------


def _no_jq_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except jq, so
    `command -v jq` genuinely fails the way it would in an environment
    without jq installed -- rather than mocking that condition."""
    bin_dir = tmp_path / "no-jq-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def test_denied_when_jq_missing(tmp_path: Path) -> None:
    """Live-reproduced before this fix: with jq absent, the very first jq
    call (extracting tool_name) crashed under `set -e` with exit 127
    ("command not found") -- before deny() was even defined, and non-
    blocking per Claude Code's PreToolUse contract, so
    mcp__github__merge_pull_request would have proceeded unchecked: the
    repository's own "no override" categorical deny did not fire. Must now
    deny (exit 2) instead."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["PATH"] = _no_jq_path(tmp_path)
    payload = json.dumps(
        {
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "pullNumber": 1},
        }
    )
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in parsed["systemMessage"]


def test_denied_on_malformed_json_stdin() -> None:
    """Live-reproduced before this fix: jq's own parse-error exit (5)
    propagated past deny() under `set -e` -- non-blocking per Claude Code's
    PreToolUse contract. This hook cannot then tell whether the malformed
    payload was a disguised merge_pull_request call, so it must deny
    (exit 2) rather than fall through on an indeterminate tool_name."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
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
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_valid_json_non_object_stdin() -> None:
    """Valid JSON that isn't an object at the top level (e.g. a bare array)
    would otherwise crash the `.tool_name` extraction the same way. This
    hook cannot then tell whether it was a disguised merge_pull_request
    call, so it must deny (exit 2) rather than fall through."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
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
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_name", [["mcp__github__merge_pull_request"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"]
)
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    """Found by code review (PR #1213): jq -r never errors on a non-string
    `.tool_name` -- it pretty-prints the JSON form across multiple lines
    instead, which then never equals the plain string this hook's own
    "no override" categorical deny compares against, silently falling
    through as "not our tool" (exit 0) instead of failing closed.
    Live-confirmed before this guard existed: an array-wrapped tool_name
    let a merge_pull_request call straight through this hook -- the exact
    bypass class this file exists to close. Must now deny."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"owner": "tvna", "repo": "gitapex", "pullNumber": 1}})
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"

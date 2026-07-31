"""Regression suite for check-merge-pull-request-block.sh's own deny/allow
matrix.

Issue #637: a PreToolUse hook (matcher: mcp__github__merge_pull_request)
blocking every call to that tool unconditionally -- this repository's
policy (planning-a-branch-from-an-issue/SKILL.md,
drafting-a-pr-to-merge/SKILL.md step 8, the ranking-the-open-queue Routine
specs' "100% human review of any pull request merge") is that no agent tool
call ever merges a PR here, no exceptions. hooks/check-bash-safety.sh
already blocks the equivalent shell form (`gh pr merge`); this hook closes
the identical gap for the platform-integrated MCP tool call.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_check_bash_safety.py
and hooks/test_check_issue_acm_disclosure.py.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

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
    assert result.returncode == 2, (
        f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    )
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
    result = run(
        tool_input={"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "merge_method": "squash"}
    )
    assert result.returncode == 2


def test_non_matching_tool_name_is_ignored() -> None:
    result = run(tool_name="mcp__github__update_pull_request", tool_input={"draft": True})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_bash_gh_pr_merge_is_ignored_by_this_hook() -> None:
    # This hook only matches the MCP tool call; the shell form is
    # check-bash-safety.sh's own responsibility, exercised in
    # test_check_bash_safety.py, not duplicated here.
    result = run(tool_name="Bash", tool_input={"command": "gh pr merge 1"})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

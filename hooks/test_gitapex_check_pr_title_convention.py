"""Regression suite for check-pr-title-convention.sh's own deny/allow matrix.

Issue #1058: a PreToolUse hook (matchers: mcp__github__create_pull_request,
mcp__github__update_pull_request) blocking a PR title that does not match
Conventional Commits format.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as
hooks/test_gitapex_check_issue_acm_disclosure.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-pr-title-convention.sh"
CHECKER = Path(__file__).parent / "gitapex_check_pr_title_convention.py"
REPO_ROOT = Path(__file__).parent.parent

_VALID_TITLE = "feat(gates): add PR title convention gate"
_INVALID_TITLE = "Add PR title convention gate"


def run(
    tool_input: dict[str, object],
    *,
    tool_name: object = "mcp__github__create_pull_request",
    script: Path = SCRIPT,
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        ["bash", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def assert_denied(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_denied_when_create_title_is_not_conventional() -> None:
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "title": _INVALID_TITLE, "body": "x"}))


def test_denied_when_create_title_is_empty() -> None:
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "title": "", "body": "x"}))


def test_denied_when_create_title_field_is_missing() -> None:
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "body": "x"}))


def test_denied_when_create_title_has_trailing_newline() -> None:
    # Regression pin for a live-tested defect found by adversarial review
    # on PR #1059: an earlier version of check-pr-title-convention.sh
    # captured the title via `title=$(...)` command substitution, which
    # unconditionally strips trailing newlines -- silently defeating the
    # exact rejection CONVENTIONAL_COMMIT_RE's `\Z` anchor exists to
    # enforce. The fix pipes jq's output directly into python3 with no
    # intermediate shell-variable capture.
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE + "\n", "body": "x"}))


def test_denied_when_create_title_has_trailing_carriage_return() -> None:
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE + "\r", "body": "x"}))


def test_denied_when_create_title_has_trailing_crlf() -> None:
    assert_denied(run({"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE + "\r\n", "body": "x"}))


def test_allowed_when_create_title_is_conventional() -> None:
    assert_allowed(run({"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE, "body": "x"}))


def test_allowed_when_create_title_has_scope_and_breaking_marker() -> None:
    assert_allowed(run({"owner": "tvna", "repo": "gitapex", "title": "feat(api)!: drop the v1 endpoint", "body": "x"}))


def test_denied_when_update_title_is_not_conventional() -> None:
    assert_denied(
        run(
            {"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "title": _INVALID_TITLE},
            tool_name="mcp__github__update_pull_request",
        )
    )


def test_allowed_when_update_title_is_conventional() -> None:
    assert_allowed(
        run(
            {"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "title": _VALID_TITLE},
            tool_name="mcp__github__update_pull_request",
        )
    )


def test_allowed_when_update_omits_title_entirely() -> None:
    assert_allowed(
        run(
            {"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "body": "x"},
            tool_name="mcp__github__update_pull_request",
        )
    )


def test_non_matching_tool_name_is_ignored() -> None:
    assert_allowed(run({"command": "ls"}, tool_name="Bash"))


@pytest.mark.parametrize(
    "tool_name", [["mcp__github__create_pull_request"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"]
)
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    """Issue #1217: `jq -r '.tool_name // empty'` never errors on a
    non-string `.tool_name` -- a pretty-printed multi-line array/object, or
    a bare number/bool, never equals either target string this hook
    compares against, silently falling through as "not our tool" (exit 0)
    instead of failing closed. Live-confirmed before this guard existed:
    `tool_name: 0` let a non-conventional title straight through. Must now
    deny."""
    result = run({"owner": "tvna", "repo": "gitapex", "title": _INVALID_TITLE, "body": "x"}, tool_name=tool_name)
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_input", [["not", "an", "object"], "text", False, True, 0], ids=["array", "string", "false", "true", "zero"]
)
def test_denied_when_tool_input_is_not_an_object(tool_input: object) -> None:
    """Issue #1216: a well-formed top-level payload whose tool_input is
    itself a non-object would otherwise crash the `has("title")` access
    with jq's own runtime error. Must deny.

    `false` is the case that actually escaped the original guard: jq's `//`
    operator treats JSON `false` the same as `null` (both are falsy), so
    `(.tool_input // {}) | type == "object"` wrongly accepted it, and the
    crash happened one line later, past deny() -- live-confirmed with
    `printf '%s'
    '{"tool_name":"mcp__github__create_pull_request","tool_input":false}'
    | bash hooks/check-pr-title-convention.sh` exiting 5 ("Cannot check
    whether boolean has a string key") instead of 2."""
    # Hand-rolled rather than via run(), matching the established
    # convention for this specific test shape across every sibling that
    # has one (test_gitapex_check_pr_duplicate_issue_shell.py's and
    # test_gitapex_check_pr_skill_audit_disclosure_shell.py's own
    # equivalents): each hook's own run() helper types tool_input as
    # dict[str, object] to match its everyday callers, and a
    # non-dict tool_input is exactly the malformed shape under test here.
    payload = json.dumps({"tool_name": "mcp__github__create_pull_request", "tool_input": tool_input})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
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
    these fall through to the hook's own downstream logic rather than being
    wrongly caught by the shape guard -- unlike the non-object shapes
    above."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    for payload in (
        json.dumps({"tool_name": "mcp__github__create_pull_request"}),
        json.dumps({"tool_name": "mcp__github__create_pull_request", "tool_input": None}),
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
        # Both fall through to the existing "no title field" deny -- a real
        # verdict, not a shape-guard crash.
        assert result.returncode == 2, f"payload={payload!r}: expected deny (exit 2), got {result.returncode}"
        parsed = json.loads(result.stderr)
        assert "carries no title field" in parsed["systemMessage"]


def test_denied_when_payload_is_not_json() -> None:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_when_sibling_checker_missing(tmp_path: Path) -> None:
    # A corrupted/incomplete bundle: the hook script exists but its sibling
    # checker does not. Fails closed rather than silently allowing.
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    result = run({"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE, "body": "x"}, script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_check_pr_title_convention.py" in payload["systemMessage"]


def test_allowed_from_a_copied_bundle_location(tmp_path: Path) -> None:
    # Simulates an installed-plugin consumer: the hook + its sibling checker
    # copied to an arbitrary bundle location. Must still resolve the checker
    # via the hook's own location and correctly allow a valid title.
    bundle = tmp_path / "bundle" / "hooks"
    bundle.mkdir(parents=True)
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    shutil.copy(CHECKER, bundle / CHECKER.name)
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path / "unrelated")
    payload = json.dumps(
        {
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": _VALID_TITLE, "body": "x"},
        }
    )
    result = subprocess.run(
        ["bash", str(copied_script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr!r}"

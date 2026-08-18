"""Regression suite for check-template-overwrite.sh's own deny/allow matrix,
plus issue #1208's jq-missing/malformed-payload fail-closed guard.

No automated coverage existed for this hook before issue #1208 -- the
sibling hooks touched by that issue (check-bash-safety.sh,
check-merge-pull-request-block.sh, check-pr-skill-audit-disclosure.sh) each
already had a suite; this file closes the same gap here rather than leaving
this hook's fix unverified. Same subprocess-driven style as
hooks/test_gitapex_check_bash_safety.py: runs the shipped script with the
PreToolUse JSON shape Claude Code sends on stdin, rather than re-deriving
the shell logic in Python.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-template-overwrite.sh"
REPO_ROOT = Path(__file__).parent.parent


def run(
    file_path: str, tool_name: str = "Write", extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"file_path": file_path}})
    env = dict(os.environ)
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


def assert_denied(file_path: str) -> None:
    result = run(file_path)
    assert result.returncode == 2, (
        f"expected deny (exit 2) for {file_path!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(file_path: str) -> None:
    result = run(file_path)
    assert result.returncode == 0, (
        f"expected allow (exit 0) for {file_path!r}, got {result.returncode}: stderr={result.stderr!r}"
    )
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.fixture
def existing_template_file(tmp_path: Path) -> str:
    """An absolute, on-disk path matching the single-file PR template
    basename rule. A tmp_path fixture rather than a scan over this
    checkout's own template file(s): `[ -f "$file_path" ]` in the hook
    works the same for an absolute path regardless of cwd, so the deny
    path is exercised against a real `-f` hit without the test depending
    on which template file(s) happen to exist in this repository."""
    template = tmp_path / "pull_request_template.md"
    template.write_text("existing template body\n")
    return str(template)


def test_denied_overwriting_an_existing_template_file(existing_template_file: str) -> None:
    assert_denied(existing_template_file)


@pytest.mark.parametrize(
    "file_path",
    [
        ".github/issue_template/not-there-yet.md",
        ".github/pull_request_template/not-there-yet.md",
        ".gitlab/issue_templates/not-there-yet.md",
        ".gitlab/merge_request_templates/not-there-yet.md",
        "pull_request_template.md",
        "PULL_REQUEST_TEMPLATE.MD",
    ],
    ids=[
        "github-issue-template-dir-new-file",
        "github-pr-template-dir-new-file",
        "gitlab-issue-templates-dir-new-file",
        "gitlab-mr-templates-dir-new-file",
        "bare-pr-template-basename-not-present-here",
        "uppercase-pr-template-basename-not-present-here",
    ],
)
def test_allowed_new_template_path_not_yet_on_disk(file_path: str) -> None:
    """A template-shaped path that does not yet exist on disk is a genuinely
    new template, not an overwrite -- allowed regardless of case or which
    template-path rule it matches."""
    assert not (REPO_ROOT / file_path).exists(), f"fixture assumption broken: {file_path} already exists"
    assert_allowed(file_path)


def test_allowed_non_template_path_even_if_it_exists() -> None:
    assert_allowed("hooks/check-template-overwrite.sh")


def test_allowed_when_no_file_path() -> None:
    assert_allowed("")


def test_non_write_tool_name_is_ignored(existing_template_file: str) -> None:
    result = run(existing_template_file, tool_name="Edit")
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Issue #1208: fail closed, not open, when jq is missing or the payload is
# malformed.
# ---------------------------------------------------------------------------


def _no_jq_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except jq, so
    `command -v jq` genuinely fails the way it would in an environment
    without jq installed -- rather than mocking that condition."""
    bin_dir = tmp_path / "no-jq-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "tr", "grep", "sed", "dirname"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def test_denied_when_jq_missing(tmp_path: Path, existing_template_file: str) -> None:
    """Live-reproduced before this fix: with jq absent, every jq call under
    `set -e` crashed with exit 127 ("command not found") -- non-blocking
    per Claude Code's PreToolUse contract, so the overwrite proceeded
    unchecked. Must now deny (exit 2) instead."""
    result = run(existing_template_file, extra_env={"PATH": _no_jq_path(tmp_path)})
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in payload["systemMessage"]


def test_denied_on_malformed_json_stdin() -> None:
    """Live-reproduced before this fix: jq's own parse-error exit (5)
    propagated past deny() under `set -e` -- non-blocking per Claude Code's
    PreToolUse contract. Must now deny (exit 2) instead."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_valid_json_non_object_stdin() -> None:
    """Valid JSON that isn't an object (e.g. a bare array) would otherwise
    crash the first field-extraction jq call the same way. Must deny."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="[]",
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_input", [["not", "an", "object"], False, True, 0], ids=["array", "false", "true", "zero"]
)
def test_denied_when_tool_input_is_not_an_object(tool_input: object) -> None:
    """A well-formed top-level payload whose tool_input is itself a
    non-object would otherwise crash the `.tool_input.file_path` access
    with jq's own "Cannot index" error. Must deny.

    `false` is the case that actually escaped the original guard: found by
    code review (PR #1213) after the array/string cases above already
    passed -- jq's `//` operator treats JSON `false` the same as `null`
    (both are falsy), so `(.tool_input // {}) | type == "object"` wrongly
    accepted it, and the crash happened one line later, past deny()."""
    payload = json.dumps({"tool_name": "Write", "tool_input": tool_input})
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for tool_input={tool_input!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"

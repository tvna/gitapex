"""Regression suite for check-post-write-provenance.sh's own report/allow
matrix (issue #878).

Named `_shell` (not the more obvious
`test_gitapex_check_post_write_provenance.py`) specifically to avoid a
pytest basename collision with
tests/test_gitapex_check_post_write_provenance.py -- both `tests/` and
`hooks/` are on pyproject.toml's `testpaths` with no `__init__.py` in
either, so two files sharing a basename fail collection with "import file
mismatch". Same split, same reason, as the
check-pr-issue-acm-disclosure.sh pair.

Runs the shipped script via subprocess with the same PostToolUse JSON
shape Claude Code sends on stdin (its own hook reference documents
`tool_name`, `tool_input`, and `tool_response` as the fields this event
carries).

Scoped to paths that don't touch the network: a subprocess test spawns a
fresh `python3` process per test, so it cannot inject the fake `fetcher`
tests/test_gitapex_check_post_write_provenance.py's direct-import suite
uses. Covered here: tool_name filtering, malformed-payload reporting,
missing-checker-script reporting, missing-jq reporting, missing-token
reporting (a short-circuit before any fetch), and the structured-output
contract every one of those shares -- exit 0 with a single well-formed
JSON object on stdout and nothing else.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parent / "check-post-write-provenance.sh"
REPO_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.slow


def run(
    *,
    payload: Any = None,
    raw_payload: str | None = None,
    script: Path = SCRIPT,
    path_override: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if raw_payload is None:
        if payload is None:
            payload = {
                "tool_name": "mcp__github__create_pull_request",
                "tool_input": {"owner": "tvna", "repo": "gitapex"},
                "tool_response": {"number": 1},
            }
        raw_payload = json.dumps(payload)
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    # Stripped by default so this suite is hermetic against whatever
    # ambient GH_TOKEN/GITHUB_TOKEN this session's own environment carries:
    # with a real token present, the covered-tool payloads below would make
    # a live GitHub call, which no subprocess test may do.
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    if path_override is not None:
        env["PATH"] = path_override
    return subprocess.run(
        ["bash", str(script)],
        input=raw_payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=str(REPO_ROOT),
        check=False,
    )


def assert_reported(result: subprocess.CompletedProcess[str], fragment: str) -> dict[str, Any]:
    """Assert the run emitted exactly one well-formed report object on
    stdout, on both channels, and still exited 0.

    Exit 0 is the contract, not an oversight: Claude Code's own hook
    reference states that exit 2 makes it "ignore stdout and any JSON in
    it", which would silently drop the systemMessage channel this gate
    depends on.
    """
    assert result.returncode == 0, result.stderr
    parsed: dict[str, Any] = json.loads(result.stdout)
    assert parsed["decision"] == "block"
    assert fragment in parsed["reason"], parsed["reason"]
    assert fragment in parsed["systemMessage"], parsed["systemMessage"]
    return parsed


@pytest.mark.parametrize(
    "tool_name",
    [
        "Bash",
        "Write",
        "mcp__github__merge_pull_request",
        "mcp__github__issue_read",
        "mcp__github__create_pull_request_review",
    ],
)
def test_an_uncovered_tool_is_silent(tool_name: str) -> None:
    result = run(payload={"tool_name": tool_name, "tool_input": {}})
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "tool_name",
    [
        "mcp__github__create_pull_request",
        "mcp__github__update_pull_request",
        "mcp__github__issue_write",
    ],
)
def test_every_covered_tool_reaches_the_checker(tool_name: str) -> None:
    result = run(
        payload={
            "tool_name": tool_name,
            "tool_input": {"owner": "tvna", "repo": "gitapex", "number": 1},
        }
    )
    assert_reported(result, "GH_TOKEN")


@pytest.mark.parametrize("raw", ["not json at all", "[1, 2, 3]", '"a string"', "null", "5", ""])
def test_a_malformed_payload_reports_rather_than_passing_silently(raw: str) -> None:
    result = run(raw_payload=raw)
    assert_reported(result, "not a JSON object")


def test_a_missing_checker_script_reports(tmp_path: Path) -> None:
    relocated = tmp_path / "check-post-write-provenance.sh"
    shutil.copy(SCRIPT, relocated)
    result = run(script=relocated)
    assert_reported(result, "was not found")


def test_a_missing_jq_reports_rather_than_crashing_silently(tmp_path: Path) -> None:
    """jq builds every report payload, including the report path itself, so
    its absence is the one failure that could crash past the emit point
    under `set -e` and read as a clean pass."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for tool in ("bash", "python3", "cat", "printf", "dirname", "cd", "pwd"):
        source = shutil.which(tool)
        if source:
            (stub_bin / tool).symlink_to(source)
    result = run(path_override=str(stub_bin))
    assert_reported(result, "jq is not available on PATH")


def test_a_missing_token_reports_the_artifact_as_unverified() -> None:
    result = run()
    parsed = assert_reported(result, "GH_TOKEN")
    assert "unverified" in parsed["reason"]
    assert "issue #878" in parsed["reason"]


def test_an_unresolvable_number_reports_rather_than_passing_silently() -> None:
    result = run(
        payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex"},
            "tool_response": {},
        }
    )
    assert_reported(result, "could not resolve")


def test_a_failed_write_is_silent() -> None:
    result = run(
        payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex"},
            "tool_response": {"status": "error"},
        }
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_stdout_carries_the_json_and_nothing_else() -> None:
    """Dimension 14 (structured-output hygiene): the checker's own
    diagnostics must be folded into the JSON string, never leaked onto the
    machine-parsed stdout channel beside it."""
    result = run()
    # json.loads rejects trailing content, so parsing the WHOLE stdout is
    # itself the "and nothing else" half of this assertion.
    parsed = json.loads(result.stdout)
    assert set(parsed) == {"decision", "reason", "systemMessage"}


def test_the_report_is_ascii_only() -> None:
    """The report reaches an operator-facing sink; this repository's own
    convention keeps outward text ASCII, and the checker reports a
    non-ASCII finding by codepoint precisely so its own message stays
    clean."""
    result = run()
    assert all(ord(character) < 128 for character in result.stdout)

"""Regression suite for check-pr-duplicate-issue.sh's own deny/allow matrix
(issue #1197).

Named `_shell` (not `test_gitapex_check_pr_duplicate_issue.py`) for the identical
reason test_gitapex_check_pr_issue_acm_disclosure_shell.py's own docstring
states: both `tests/` and `hooks/` are on pyproject.toml's `testpaths` with
no `__init__.py` in either, so two files sharing a basename fail
collection with "import file mismatch".

Scoped to paths that don't touch the network: a subprocess test spawns a
fresh `python3` process per test, so it has no way to inject a fake
opener/sleeper. Pagination, retry-with-backoff, and per-PR overlap
detection are only reachable via hooks/test_gitapex_check_pr_duplicate_issue.py's
own direct-import suite -- this file covers tool_name filtering, the
no-citation-at-all allow, the waiver-present allow, missing-checker-script
fail-closed, missing-token fail-closed, and payload-shape hardening.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parent / "check-pr-duplicate-issue.sh"
CHECKER = Path(__file__).parent / "gitapex_check_pr_duplicate_issue.py"
CITATION_MODULE = Path(__file__).parent / "gitapex_check_pr_issue_acm_disclosure.py"
ACM_CHECKER = Path(__file__).parent / "gitapex_check_acm_present_or_waiver.py"
REPO_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.slow


def run(
    *,
    tool_name: object = "mcp__github__create_pull_request",
    owner: str = "tvna",
    repo: str = "gitapex",
    title: str = "x",
    body: str = "no citation here",
    script: Path = SCRIPT,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"owner": owner, "repo": repo, "title": title, "body": body},
        }
    )
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    # Stripped by default so this suite is hermetic against whatever
    # ambient GH_TOKEN/GITHUB_TOKEN this session's own environment
    # happens to carry -- every test here either never reaches the token
    # check (no resolving citation, waiver present, tool_name mismatch) or
    # specifically wants "no token" (the fail-closed test below).
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(script)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def assert_allowed(**kwargs: Any) -> None:
    result = run(**kwargs)
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_non_matching_tool_name_is_ignored() -> None:
    assert_allowed(tool_name="Bash", body="Closes #1")


@pytest.mark.parametrize(
    "tool_name", [["mcp__github__create_pull_request"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"]
)
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    """Issue #1315: `jq -r '.tool_name // empty'` never errors on a
    non-string `.tool_name` -- it pretty-prints the JSON form across
    multiple lines instead, which then never equals the plain string this
    hook's own re-check compares against, silently falling through as "not
    our tool" (exit 0) instead of failing closed. Live-confirmed before
    this guard existed: an array-wrapped tool_name let a
    create_pull_request call straight through this hook's own
    duplicate-citation check. Must now deny."""
    # body="Refs #1": a context-only citation, so this stays hermetic/
    # network-free the same way test_allowed_when_only_a_context_only_
    # citation_is_present does -- the guard under test fires before any
    # citation parsing would matter anyway.
    result = run(tool_name=tool_name, body="Refs #1")
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool_name" in payload["systemMessage"]


def test_allowed_when_no_resolving_citation_at_all() -> None:
    assert_allowed(body="just a description, no citation")


def test_allowed_when_only_a_context_only_citation_is_present() -> None:
    assert_allowed(body="Refs #1")


def test_allowed_when_waiver_present_even_with_no_token() -> None:
    # The waiver short-circuits before the token check -- no network call,
    # no token needed.
    assert_allowed(body="Closes #1\n\nDuplicate-PR-waiver: intentional second PR, see #1")


def test_denied_when_resolving_citation_but_no_token_in_env() -> None:
    result = run(body="Closes #1")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "GH_TOKEN" in payload["systemMessage"] or "GITHUB_TOKEN" in payload["systemMessage"]


def test_denied_when_sibling_checker_missing(tmp_path: Path) -> None:
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    result = run(body="Closes #1", script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_check_pr_duplicate_issue.py" in payload["systemMessage"]


def test_allowed_from_a_copied_bundle_location(tmp_path: Path) -> None:
    # Same regression class as check-pr-issue-acm-disclosure.sh's own
    # test_allowed_from_a_copied_bundle_location: the hook plus all its
    # sibling scripts (this one imports gitapex_check_pr_issue_acm_disclosure,
    # which itself imports gitapex_check_acm_present_or_waiver) copied to an
    # arbitrary bundle location must still resolve everything relative to
    # its own location and correctly allow a no-network-needed case.
    bundle = tmp_path / "bundle" / "hooks"
    bundle.mkdir(parents=True)
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    shutil.copy(CHECKER, bundle / CHECKER.name)
    shutil.copy(CITATION_MODULE, bundle / CITATION_MODULE.name)
    shutil.copy(ACM_CHECKER, bundle / ACM_CHECKER.name)

    consumer_project_dir = tmp_path / "consumer_project"
    consumer_project_dir.mkdir()

    result = run(
        body="Refs #1",
        script=copied_script,
        extra_env={"CLAUDE_PROJECT_DIR": str(consumer_project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_denied_message_names_the_issue_657_style_reason() -> None:
    result = run(body="Closes #1")
    payload = json.loads(result.stderr)
    assert "issue #1197" in payload["systemMessage"]


def _run_raw(raw_stdin: str, *, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return subprocess.run(
        ["bash", str(script)],
        input=raw_stdin,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_denied_when_stdin_is_not_valid_json() -> None:
    result = _run_raw("not json at all")
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "not exactly one JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_valid_json_but_not_an_object() -> None:
    for raw in ("[1,2,3]", '"just a string"', "null", "5"):
        result = _run_raw(raw)
        assert result.returncode == 2, f"input {raw!r}: expected deny (exit 2), got {result.returncode}"
        payload = json.loads(result.stderr)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "not exactly one JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_empty() -> None:
    result = _run_raw("")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_when_stdin_carries_a_json_stream_rather_than_one_object() -> None:
    # Regression test for a fail-open the deterministic-gate-quality audit
    # (PR #1215) found live: the shape check used to validate a JSON
    # *stream* one value at a time via `jq -e 'if type == "object" ...'`,
    # exiting on the LAST value -- so two concatenated JSON objects on
    # stdin passed it, `tool_name` then became a multi-line string matching
    # no matcher, and the script took its `exit 0` allow path with the
    # duplicate-check never run. Fixed by slurping (`-s`) into a
    # one-element array first, so "exactly one value, and it's an object"
    # is checkable directly. Ordering matters here: the real
    # create_pull_request payload comes FIRST and carries a resolving
    # citation, so an appended second JSON value is all it takes to
    # exercise the old defeat.
    raw = (
        '{"tool_name":"mcp__github__create_pull_request",'
        '"tool_input":{"owner":"tvna","repo":"gitapex","title":"x","body":"Closes #1"}}'
        '{"tool_name":"Bash"}'
    )
    result = _run_raw(raw)
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stdout={result.stdout!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("tool_input", ["[1,2,3]", '"oops"', "5", "true", "false"])
def test_denied_when_tool_input_is_not_an_object(tool_input: str) -> None:
    # "false" is not a redundant case alongside "true": jq's `//` operator
    # treats `false` (like `null`) as falsy, so a naive
    # `(.tool_input // {}) | type == "object"` check silently substitutes
    # `{}` and passes this shape through -- verified live against a real
    # jq invocation before this fix landed, then crashing the downstream
    # payload-extraction jq call with "Cannot index boolean with string"
    # under `set -e`, past deny(). This case is the regression test for
    # that specific defeat.
    raw = '{"tool_name":"mcp__github__create_pull_request","tool_input":' + tool_input + "}"
    result = _run_raw(raw)
    assert result.returncode == 2, f"tool_input={tool_input}: expected deny (exit 2), got {result.returncode}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool_input" in payload["systemMessage"]


def test_allowed_when_tool_input_is_absent_or_null() -> None:
    # jq indexes null/absent as null (not a runtime error); an absent
    # owner/repo/title/body falls through to "no citation" -> allow.
    for raw in (
        '{"tool_name":"mcp__github__create_pull_request"}',
        '{"tool_name":"mcp__github__create_pull_request","tool_input":null}',
    ):
        result = _run_raw(raw)
        assert result.returncode == 0, f"input {raw!r}: expected allow (exit 0), got {result.returncode}"


def test_denied_when_jq_itself_is_missing_from_path(tmp_path: Path) -> None:
    sandbox_bin = tmp_path / "bin"
    sandbox_bin.mkdir()
    for name in ("bash", "cat", "dirname", "sed", "grep", "python3"):
        found = shutil.which(name)
        assert found, f"{name} must be on the real PATH for this test to build a sandbox PATH"
        (sandbox_bin / name).symlink_to(found)

    env = {"HOME": os.environ.get("HOME", "/root"), "PATH": str(sandbox_bin)}
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in payload["systemMessage"]


def test_denied_not_crashed_on_a_title_too_large_for_argv() -> None:
    payload = json.dumps(
        {
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "A" * 3_000_000, "body": "Closes #1"},
        }
    )
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr[:300]!r}"
    payload_json = json.loads(result.stderr)
    assert payload_json["hookSpecificOutput"]["permissionDecision"] == "deny"

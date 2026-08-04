"""Regression suite for check-pr-issue-acm-disclosure.sh's own deny/allow
matrix (issue #657).

Named `_shell` (not the more obvious `test_gitapex_check_pr_issue_acm_disclosure.py`)
specifically to avoid a pytest basename collision with
tests/test_gitapex_check_pr_issue_acm_disclosure.py -- both `tests/` and `hooks/`
are on pyproject.toml's `testpaths` with no `__init__.py` in either, so two
files sharing a basename fail collection with "import file mismatch".

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_gitapex_check_issue_acm_disclosure.py
and hooks/test_gitapex_check_pr_upstream_pushed.py.

Scoped to paths that don't touch the network: a subprocess test spawns a
fresh `python3` process per test, so it has no way to inject a fake
`opener`/`sleeper` the way tests/test_gitapex_check_pr_issue_acm_disclosure.py's
direct-import suite does. The retry-with-backoff logic, per-category
classification against a fetched issue body, and 4xx-vs-5xx handling are
only reachable via that direct-import suite -- this file covers
tool_name filtering, the no-citation-at-all deny (short-circuits before
any fetch is attempted), missing-checker-script fail-closed, and
missing-token fail-closed (also a short-circuit before any fetch).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-pr-issue-acm-disclosure.sh"
CHECKER = Path(__file__).parent / "gitapex_check_pr_issue_acm_disclosure.py"
ACM_CHECKER = Path(__file__).parent / "gitapex_check_acm_present_or_waiver.py"
REPO_ROOT = Path(__file__).parent.parent


def run(
    *,
    tool_name: str = "mcp__github__create_pull_request",
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
    # check (context-only citations, tool_name mismatch) or specifically
    # wants "no token" (the fail-closed test below); none needs a real
    # token, since a subprocess test cannot inject a fake opener to make
    # the ensuing network call safe.
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


def assert_denied(**kwargs) -> None:
    result = run(**kwargs)
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(**kwargs) -> None:
    result = run(**kwargs)
    assert result.returncode == 0, f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr!r}"
    assert result.stdout == ""
    assert result.stderr == ""


def test_non_matching_tool_name_is_ignored() -> None:
    assert_allowed(tool_name="Bash", body="irrelevant")


def test_denied_when_body_and_title_cite_no_issue_at_all() -> None:
    assert_denied(body="just a description, no citation")


def test_allowed_when_only_a_context_only_citation_is_present() -> None:
    # A bare Refs/#N citation needs no ACM check and no network call.
    assert_allowed(body="Refs #1")


def test_denied_when_resolving_citation_but_no_token_in_env() -> None:
    result = run(body="Closes #1")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "GH_TOKEN" in payload["systemMessage"] or "GITHUB_TOKEN" in payload["systemMessage"]


def test_denied_when_sibling_checker_missing(tmp_path: Path) -> None:
    # A corrupted/incomplete bundle: the hook script exists but its sibling
    # checker does not. Fails closed rather than silently allowing.
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    result = run(body="Closes #1", script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_check_pr_issue_acm_disclosure.py" in payload["systemMessage"]


def test_allowed_from_a_copied_bundle_location(tmp_path: Path) -> None:
    # Same regression class as check-issue-acm-disclosure.sh's own
    # test_allowed_from_a_copied_bundle_location (PR #433): the hook plus
    # both its sibling scripts copied to an arbitrary bundle location, with
    # CLAUDE_PROJECT_DIR pointed elsewhere, must still resolve everything
    # relative to its own location and correctly allow a context-only
    # (no-network-needed) citation.
    bundle = tmp_path / "bundle" / "hooks"
    bundle.mkdir(parents=True)
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    shutil.copy(CHECKER, bundle / CHECKER.name)
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


def test_denied_message_names_the_uncited_case_explicitly() -> None:
    result = run(body="nothing here")
    payload = json.loads(result.stderr)
    assert "cites no issue" in payload["systemMessage"]


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
    # Regression for issue #657's own adversarial review: a `set -euo
    # pipefail` script's unprotected jq field-extraction calls crash on
    # malformed JSON before deny() ever runs, exiting with jq's own error
    # code -- which Claude Code's PreToolUse contract treats as a
    # non-blocking error (the tool call proceeds), silently defeating this
    # hook's whole fail-closed guarantee. Live-reproduced originally with
    # `echo "not json at all" | bash check-pr-issue-acm-disclosure.sh`.
    result = _run_raw("not json at all")
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "not a JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_valid_json_but_not_an_object() -> None:
    # A second, distinct crash shape the naive `jq -e .` validity check
    # alone would miss: valid JSON whose top level isn't an object (an
    # array, string, null, or bare number) still crashes the very next
    # `.tool_name` field-access jq call with a runtime "Cannot index ..."
    # error, exiting non-zero past deny() the same way.
    for raw in ("[1,2,3]", '"just a string"', "null", "5"):
        result = _run_raw(raw)
        assert result.returncode == 2, f"input {raw!r}: expected deny (exit 2), got {result.returncode}"
        payload = json.loads(result.stderr)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "not a JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_empty() -> None:
    result = _run_raw("")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("tool_input", ["[1,2,3]", '"oops"', "5", "true"])
def test_denied_when_tool_input_is_not_an_object(tool_input: str) -> None:
    # A second round of issue #657's own adversarial review: the top-level
    # "is this an object" check alone missed that a well-formed object
    # payload with a non-object tool_input (array/string/number/bool)
    # still crashes every `.tool_input.<field>` jq access below it with a
    # "Cannot index X with string" error, past deny(), the same fail-open
    # class as the top-level check guards against.
    raw = '{"tool_name":"mcp__github__create_pull_request","tool_input":' + tool_input + "}"
    result = _run_raw(raw)
    assert result.returncode == 2, f"tool_input={tool_input}: expected deny (exit 2), got {result.returncode}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool_input" in payload["systemMessage"]


def test_allowed_when_tool_input_is_absent_or_null() -> None:
    # jq indexes `null`/a missing key as `null`, not a runtime error, so
    # these fall through to the normal "cites nothing" deny path (a real
    # verdict, not a crash) -- unlike the non-object shapes above.
    for raw in (
        '{"tool_name":"mcp__github__create_pull_request"}',
        '{"tool_name":"mcp__github__create_pull_request","tool_input":null}',
    ):
        result = _run_raw(raw)
        assert result.returncode == 2
        payload = json.loads(result.stderr)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "cites no issue" in payload["systemMessage"]


def test_denied_when_jq_itself_is_missing_from_path(tmp_path: Path) -> None:
    # A third round of issue #657's own adversarial review: deny() itself
    # depends on jq to build its JSON output. If jq is absent from PATH
    # entirely (a broken environment, not a malformed payload), every jq
    # call -- including inside deny() -- crashes with exit 127 ("command
    # not found") past the point where any deny JSON could be emitted.
    # Builds a PATH with everything this script needs except jq, so the
    # system's real PATH/jq installation is untouched.
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
    # Regression for issue #657's own adversarial review: an earlier
    # version rebuilt the JSON payload via `jq -n --arg title "$title"
    # ...`, passing each field as a command-line argument -- a large
    # enough title/body (evaluated by this hook before GitHub's own PR
    # body size limit would ever apply) exceeds the OS's ARG_MAX and
    # crashes the script with exit 126 ("Argument list too long"), past
    # deny(). The current version reshapes the payload via a single jq
    # filter reading $input over stdin, never re-passing large values as
    # argv. 3MB comfortably exceeds this machine's observed ARG_MAX
    # (~2MB) without being implausibly large for a hostile/buggy caller.
    payload = json.dumps(
        {
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "A" * 3_000_000, "body": "no citation"},
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

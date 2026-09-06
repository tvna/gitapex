"""Regression suite for check-gate-proposal-dedup-sweep.sh's own deny/allow
matrix (issue #1806).

Named `_shell` (not `test_gitapex_check_gate_proposal_dedup_sweep.py`) for
the identical reason test_gitapex_check_pr_duplicate_issue_shell.py's own
docstring states: both `tests/` and `hooks/` are on pyproject.toml's
`testpaths` with no `__init__.py` in either, so two files sharing a
basename fail collection with "import file mismatch".

Scoped to paths that don't touch the network: a subprocess test spawns a
fresh `python3` process per test, so it has no way to inject a fake
opener/sleeper. The live-count fetch (pagination, retry-with-backoff) is
only reachable via
tests/test_gitapex_check_gate_proposal_dedup_sweep.py's own direct-import
suite -- this file covers tool_name filtering (including the
plugin-namespaced form), the method/label out-of-scope allows, the
missing-sweep-line deny, missing-checker-script fail-closed, and
payload-shape hardening.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parent / "check-gate-proposal-dedup-sweep.sh"
CHECKER = Path(__file__).parent / "gitapex_check_gate_proposal_dedup_sweep.py"
REPO_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.slow


def run(
    *,
    tool_name: object = "mcp__github__issue_write",
    owner: str = "tvna",
    repo: str = "gitapex",
    method: str = "create",
    labels: object = ("gate-proposal",),
    body: str = "no sweep line here",
    script: Path = SCRIPT,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"owner": owner, "repo": repo, "method": method, "labels": labels, "body": body},
        }
    )
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    # Stripped by default so this suite is hermetic against whatever
    # ambient GH_TOKEN/GITHUB_TOKEN this session's own environment happens
    # to carry -- every test here never reaches the live-count fetch (no
    # gate-proposal label, non-create method, or no sweep line at all --
    # each denies/allows before the token check would matter).
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
    assert_allowed(tool_name="Bash")


def test_plugin_namespaced_tool_name_is_still_gated() -> None:
    """Regression test for the namespace gap a fresh-context convention
    review caught live: the hooks.json matcher
    (mcp__(github|plugin_github_github)__issue_write) covers both forms,
    but an earlier version of this script's own tool_name re-check only
    ever compared against the bare mcp__github__ form -- silently
    exit-0-allowing a gate-proposal filing carrying no sweep line at all
    whenever the plugin-namespaced tool name variant was used instead."""
    result = run(tool_name="mcp__plugin_github_github__issue_write")
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stdout={result.stdout!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Dedup-sweep" in payload["systemMessage"]


@pytest.mark.parametrize(
    "tool_name", [["mcp__github__issue_write"], {"x": 1}, 5, True], ids=["array", "object", "number", "bool"]
)
def test_denied_when_tool_name_is_not_a_string(tool_name: object) -> None:
    result = run(tool_name=tool_name)
    assert result.returncode == 2, f"expected deny (exit 2) for tool_name={tool_name!r}, got {result.returncode}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool_name" in payload["systemMessage"]


def test_allowed_when_method_is_not_create() -> None:
    assert_allowed(method="update")


def test_allowed_when_labels_carry_no_gate_proposal_tag() -> None:
    assert_allowed(labels=["some-other-label"])


def test_denied_when_gate_proposal_filing_carries_no_sweep_line() -> None:
    result = run()
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Dedup-sweep" in payload["systemMessage"]


def test_denied_when_sibling_checker_missing(tmp_path: Path) -> None:
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    result = run(script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gitapex_check_gate_proposal_dedup_sweep.py" in payload["systemMessage"]


def test_allowed_from_a_copied_bundle_location(tmp_path: Path) -> None:
    # Same regression class as check-pr-issue-acm-disclosure.sh's own
    # test_allowed_from_a_copied_bundle_location: the hook plus its sibling
    # checker script, copied to an arbitrary bundle location, must still
    # resolve everything relative to its own location and correctly allow
    # a no-network-needed case.
    bundle = tmp_path / "bundle" / "hooks"
    bundle.mkdir(parents=True)
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    shutil.copy(CHECKER, bundle / CHECKER.name)

    consumer_project_dir = tmp_path / "consumer_project"
    consumer_project_dir.mkdir()

    result = run(
        method="update",
        script=copied_script,
        extra_env={"CLAUDE_PROJECT_DIR": str(consumer_project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


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
    assert "not a single JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_valid_json_but_not_an_object() -> None:
    for raw in ("[1,2,3]", '"just a string"', "null", "5"):
        result = _run_raw(raw)
        assert result.returncode == 2, f"input {raw!r}: expected deny (exit 2), got {result.returncode}"
        payload = json.loads(result.stderr)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "not a single JSON object" in payload["systemMessage"]


def test_denied_when_stdin_is_empty() -> None:
    result = _run_raw("")
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_when_stdin_carries_a_json_stream_rather_than_one_object() -> None:
    # Same concatenated-input class hooks/check-pr-duplicate-issue.sh's own
    # identical regression test covers (deterministic-gate-quality audit,
    # PR #1215): the real gate-proposal-labeled create payload comes FIRST
    # with no sweep line, so an appended second JSON value is all it takes
    # to exercise the old (now-closed) defeat if it ever regressed.
    raw = (
        '{"tool_name":"mcp__github__issue_write",'
        '"tool_input":{"owner":"tvna","repo":"gitapex","method":"create",'
        '"labels":["gate-proposal"],"body":"no sweep line"}}'
        '{"tool_name":"Bash"}'
    )
    result = _run_raw(raw)
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stdout={result.stdout!r}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("tool_input", ["[1,2,3]", '"oops"', "5", "true", "false"])
def test_denied_when_tool_input_is_not_an_object(tool_input: str) -> None:
    # "false" is not redundant alongside "true": jq's `//` operator treats
    # `false` (like `null`) as falsy, so a naive
    # `(.tool_input // {}) | type == "object"` check would silently
    # substitute `{}` and pass this shape through, then crash the
    # downstream payload-extraction jq call under `set -e`, past deny().
    raw = '{"tool_name":"mcp__github__issue_write","tool_input":' + tool_input + "}"
    result = _run_raw(raw)
    assert result.returncode == 2, f"tool_input={tool_input}: expected deny (exit 2), got {result.returncode}"
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "tool_input" in payload["systemMessage"]


def test_allowed_when_tool_input_is_absent_or_null() -> None:
    # jq indexes null/absent as null (not a runtime error); an absent
    # method/labels falls through to "not a gate-proposal create" -> allow.
    for raw in (
        '{"tool_name":"mcp__github__issue_write"}',
        '{"tool_name":"mcp__github__issue_write","tool_input":null}',
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


def test_denied_not_crashed_on_a_body_too_large_for_argv() -> None:
    payload = json.dumps(
        {
            "tool_name": "mcp__github__issue_write",
            "tool_input": {
                "owner": "tvna",
                "repo": "gitapex",
                "method": "create",
                "labels": ["gate-proposal"],
                "body": "A" * 3_000_000,
            },
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


def test_denied_message_names_a_bug_not_a_finding_on_unrecognized_checker_exit(tmp_path: Path) -> None:
    """Regression test for the FAIL:-vs-bug distinction
    hooks/check-pr-duplicate-issue.sh's own identical scheme establishes:
    a check-script exit that carries no `FAIL:`-prefixed line (a crash, a
    non-zero exit with unrelated stderr text) must be reported as looking
    like a bug in the checker itself, never silently folded into an
    ordinary Dedup-sweep deny message."""
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    broken_checker = bundle / CHECKER.name
    broken_checker.write_text("import sys\nprint('boom, not a FAIL: line', file=sys.stderr)\nsys.exit(1)\n")
    result = run(script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "bug in the check script itself" in payload["systemMessage"]
    assert "boom, not a FAIL: line" in payload["systemMessage"]

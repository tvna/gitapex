"""Regression suite for check-issue-acm-disclosure.sh's own deny/allow
matrix.

Issue #413 (sub-issue of #357): a PreToolUse hook (matcher:
mcp__github__issue_write) blocking a new-issue-creation call whose body
carries neither an Acceptance Criteria Map (ACM) table nor an explicit
waiver line. Only fires for method == "create" -- an "update" call is out
of scope for this row.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_check_bash_safety.py.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-issue-acm-disclosure.sh"
REPO_ROOT = Path(__file__).parent.parent
CHECK_SCRIPT_RELATIVE = ".github/scripts/gate_acm_issue_disclosure.py"

_VALID_ACM_TABLE = (
    "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
    "|---|---|---|---|---|\n"
    "| Thing works | It should do X | Add Y | Run Z | None |\n"
)
_VALID_WAIVER = "ACM: not-applicable (chore): docs-only rewording.\n"
_NO_DISCLOSURE = "Just a plain issue body with no table and no waiver.\n"


def run(
    *,
    tool_name: str = "mcp__github__issue_write",
    method: str = "create",
    body: str = _NO_DISCLOSURE,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {
                "method": method,
                "owner": "tvna",
                "repo": "gitapex",
                "title": "x",
                "body": body,
            },
        }
    )
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


def assert_denied(**kwargs) -> None:
    result = run(**kwargs)
    assert result.returncode == 2, (
        f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    )
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert payload["systemMessage"]


def assert_allowed(**kwargs) -> None:
    result = run(**kwargs)
    assert result.returncode == 0, (
        f"expected allow (exit 0), got {result.returncode}: stderr={result.stderr!r}"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_denied_when_body_has_neither_acm_table_nor_waiver() -> None:
    assert_denied(body=_NO_DISCLOSURE)


def test_denied_when_body_is_empty() -> None:
    assert_denied(body="")


def test_allowed_when_body_has_acm_table() -> None:
    assert_allowed(body=_VALID_ACM_TABLE)


def test_allowed_when_body_has_waiver_line() -> None:
    assert_allowed(body=_VALID_WAIVER)


def test_allowed_when_method_is_update_even_without_disclosure() -> None:
    assert_allowed(method="update", body=_NO_DISCLOSURE)


def test_allowed_when_method_is_missing() -> None:
    assert_allowed(method="", body=_NO_DISCLOSURE)


def test_non_matching_tool_name_is_ignored() -> None:
    assert_allowed(tool_name="Bash", body=_NO_DISCLOSURE)


def test_denied_when_check_script_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    result = run(body=_NO_DISCLOSURE, extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)})
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gate_acm_issue_disclosure.py" in payload["systemMessage"]


def test_allowed_when_check_script_present_in_alternate_project_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    check_dir = project_dir / ".github" / "scripts"
    check_dir.mkdir(parents=True)
    (check_dir / "gate_acm_issue_disclosure.py").write_text(
        (REPO_ROOT / CHECK_SCRIPT_RELATIVE).read_text()
    )
    result = run(body=_VALID_ACM_TABLE, extra_env={"CLAUDE_PROJECT_DIR": str(project_dir)})
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

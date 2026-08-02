"""Regression suite for check-issue-acm-disclosure.sh's own deny/allow
matrix.

Issue #413 (sub-issue of #357): a PreToolUse hook (matcher:
mcp__github__issue_write) blocking a new-issue-creation call whose body
carries neither an Acceptance Criteria Map (ACM) table nor an explicit
waiver line. Only fires for method == "create" -- an "update" call is out
of scope for this row.

The checker (hooks/check_acm_present_or_waiver.py) is resolved relative
to the hook script's own location, not CLAUDE_PROJECT_DIR -- a Codex
review on PR #433 caught an earlier version that shelled out to
.github/scripts/gate_acm_issue_disclosure.py relative to
CLAUDE_PROJECT_DIR instead, which does not exist in an installed-plugin
consumer checkout (only skills/ and hooks/ are deployed, per
docs/repository-layout.md) and reproducibly false-denied even a valid
ACM/waiver body there. test_allowed_from_a_copied_bundle_location below
is that exact regression, pinned.

Runs the shipped script via subprocess with the same PreToolUse JSON shape
Claude Code sends on stdin, same style as hooks/test_check_bash_safety.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "check-issue-acm-disclosure.sh"
CHECKER = Path(__file__).parent / "check_acm_present_or_waiver.py"
REPO_ROOT = Path(__file__).parent.parent

_VALID_ACM_TABLE = (
    "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
    "|---|---|---|---|---|\n"
    "| Thing works | It should do X | Add Y | Run Z | None |\n"
)
_VALID_WAIVER = "ACM: not-applicable (chore): docs-only rewording.\n"
_VALID_DEFECT_WAIVER = "ACM: not-applicable (defect): bare defect report, see #142.\n"
_NO_DISCLOSURE = "Just a plain issue body with no table and no waiver.\n"


def run(
    *,
    tool_name: str = "mcp__github__issue_write",
    method: str = "create",
    body: str = _NO_DISCLOSURE,
    script: Path = SCRIPT,
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
    env.pop("CLAUDE_PLUGIN_ROOT", None)
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


def test_allowed_when_body_has_defect_waiver_line() -> None:
    # Issue #657 adds `defect` to the waiver vocabulary for
    # fixing-a-reported-issue's bare defect-report issues. This hook
    # doesn't distinguish waiver categories, so a *new* issue can now be
    # created with a defect waiver too, not only posted via `update` on an
    # existing one -- an accepted, named side effect, not a gap.
    assert_allowed(body=_VALID_DEFECT_WAIVER)


def test_allowed_when_method_is_update_even_without_disclosure() -> None:
    assert_allowed(method="update", body=_NO_DISCLOSURE)


def test_allowed_when_method_is_missing() -> None:
    assert_allowed(method="", body=_NO_DISCLOSURE)


def test_non_matching_tool_name_is_ignored() -> None:
    assert_allowed(tool_name="Bash", body=_NO_DISCLOSURE)


def test_denied_when_sibling_checker_missing(tmp_path: Path) -> None:
    # A corrupted/incomplete bundle: the hook script exists but its sibling
    # checker does not. Fails closed rather than silently allowing.
    bundle = tmp_path / "hooks"
    bundle.mkdir()
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    result = run(body=_VALID_ACM_TABLE, script=copied_script)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "check_acm_present_or_waiver.py" in payload["systemMessage"]


def test_allowed_from_a_copied_bundle_location(tmp_path: Path) -> None:
    # Regression pin for the Codex-reported bug on PR #433: simulates an
    # installed-plugin consumer -- the hook + its sibling checker copied to
    # an arbitrary bundle location, with CLAUDE_PROJECT_DIR pointed at a
    # separate, unrelated directory that carries no .github/ at all (the
    # normal shape of a real consumer checkout). Must still resolve the
    # checker via the hook's own location and correctly allow a valid body.
    bundle = tmp_path / "bundle" / "hooks"
    bundle.mkdir(parents=True)
    copied_script = bundle / SCRIPT.name
    shutil.copy(SCRIPT, copied_script)
    shutil.copy(CHECKER, bundle / CHECKER.name)

    consumer_project_dir = tmp_path / "consumer_project"
    consumer_project_dir.mkdir()

    result = run(
        body=_VALID_ACM_TABLE,
        script=copied_script,
        extra_env={"CLAUDE_PROJECT_DIR": str(consumer_project_dir)},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""

    # Same bundle location, but a body with no disclosure -- still denies.
    result = run(
        body=_NO_DISCLOSURE,
        script=copied_script,
        extra_env={"CLAUDE_PROJECT_DIR": str(consumer_project_dir)},
    )
    assert result.returncode == 2

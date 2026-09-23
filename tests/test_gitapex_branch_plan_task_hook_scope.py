"""Drift gate for the branch-plan-task hook scoping (issue #1996).

The Decision 17 (Bash exclusion) and Decision 20 (full verification) hooks
used to live in `.claude/agents/branch-plan-task.md`'s own frontmatter,
which scoped them to that agent by construction. They now live in the
plugin's `hooks/hooks.json` and scope themselves by the hook payload's
`agent_type`, which Claude Code fills with `<plugin name>:<agent name>` for
a plugin subagent (confirmed live on Claude Code 2.1.280, recorded in issue
#1996). That scope is spelled in five places; if any one drifts, the hook
silently never fires. This test ties them together.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BASH_HOOK = "skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh"
STOP_HOOK = "skills/executing-a-branch-plan/scripts/check_task_full_verification.sh"


def _agent_name() -> str:
    text = (REPO_ROOT / "agents" / "branch-plan-task.md").read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", 2)
    name: str = yaml.safe_load(frontmatter)["name"]
    return name


def _expected_agent_type() -> str:
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return f"{plugin['name']}:{_agent_name()}"


def _hooks() -> dict[str, list[dict[str, Any]]]:
    parsed = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    hooks: dict[str, list[dict[str, Any]]] = parsed["hooks"]
    return hooks


def _entries_running(event: str, script: str) -> list[dict[str, Any]]:
    command = f'"${{CLAUDE_PLUGIN_ROOT}}/{script}"'
    return [entry for entry in _hooks().get(event, []) if any(hook["command"] == command for hook in entry["hooks"])]


def _script_constant(script: str) -> str:
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    found = re.findall(r'^branch_plan_task_agent_name="([^"]+)"$', text, flags=re.MULTILINE)
    assert len(found) == 1, f"{script}: expected one branch_plan_task_agent_name assignment, found {found}"
    value: str = found[0]
    return value


def test_expected_agent_type_is_the_plugin_qualified_name() -> None:
    assert _expected_agent_type() == "gitapex:branch-plan-task"


def test_bash_hook_is_registered_for_bash_and_scopes_to_the_agent_type() -> None:
    entries = _entries_running("PreToolUse", BASH_HOOK)
    assert len(entries) == 1
    assert entries[0]["matcher"] == "Bash"
    assert _script_constant(BASH_HOOK) == _agent_name()


def test_stop_hook_matcher_and_script_scope_agree_with_the_agent_type() -> None:
    entries = _entries_running("SubagentStop", STOP_HOOK)
    assert len(entries) == 1
    matcher = entries[0]["matcher"]
    # Same scope as both scripts' `name | *:name` case pattern.
    assert matcher == f"^(.*:)?{_agent_name()}$"
    # Any plugin prefix, or none, is in scope; a lookalike name is not.
    for in_scope in (_expected_agent_type(), _agent_name(), f"fork:{_agent_name()}", f"a:b:{_agent_name()}"):
        assert re.fullmatch(matcher, in_scope), in_scope
    for out_of_scope in (f"x{_agent_name()}", f"{_expected_agent_type()}-extra", "gitapex:review-persona"):
        assert not re.fullmatch(matcher, out_of_scope), out_of_scope
    assert _script_constant(STOP_HOOK) == _agent_name()


def test_project_local_agent_definition_stays_removed() -> None:
    """A reintroduced project-local copy would register a second
    `branch-plan-task` definition next to the plugin's, two definitions of
    one agent type that could drift apart (both would still be gated, since
    the hooks accept the unqualified name too)."""
    assert not (REPO_ROOT / ".claude" / "agents" / "branch-plan-task.md").exists()


def test_skill_dispatch_sites_use_the_qualified_name() -> None:
    skill_dir = REPO_ROOT / "skills" / "executing-a-branch-plan"
    unqualified = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in [skill_dir / "SKILL.md", *sorted((skill_dir / "references").glob("*.md"))]
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"(agentType|subagent_type): '(?!gitapex:)branch-plan-task'", line)
    ]
    assert unqualified == []

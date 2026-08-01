"""Tests for the plugin-root brace-notation gate
(.github/scripts/gate_plugin_root_brace_notation.py).

Refs #650. The gate exists because `hooks/hooks.json` authored every hook
command with the unbraced `$CLAUDE_PLUGIN_ROOT`, which apm 0.25.0 copies
verbatim instead of rewriting -- so an apm-installed consumer silently
received seven hook commands that could not resolve. These tests pin both
directions: the real repository must stay braced, and an injected unbraced
command must fail rather than pass.

The defeat-cases matter as much as the happy path here: a gate that also
fired on prose naming the variable would be reverted the first time someone
documented this bug, and a gate that read apm's own deployed trees would
fail a gitapex PR over a third party's notation.
"""

from __future__ import annotations

import json
import pathlib

import gate_plugin_root_brace_notation as gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_BRACED = '"${CLAUDE_PLUGIN_ROOT}/hooks/check.sh"'
_UNBRACED = '"$CLAUDE_PLUGIN_ROOT/hooks/check.sh"'


def _write_hooks_json(root: pathlib.Path, command: str) -> pathlib.Path:
    path = root / "hooks" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_repository_hook_commands_all_brace_the_variable():
    """The real checkout passes -- the regression anchor for #650's fix."""
    assert gate.find_violations(REPO_ROOT) == []


def test_repository_scan_reaches_the_real_hook_manifest():
    """discover() must actually find this repo's own surfaces.

    Without this, a discovery bug that silently found nothing would make
    the test above pass for the wrong reason.
    """
    discovered = {p.relative_to(REPO_ROOT).as_posix() for p in gate.discover(REPO_ROOT)}
    assert "hooks/hooks.json" in discovered
    assert "agents/branch-plan-task.md" in discovered


def test_unbraced_command_in_hooks_json_is_a_violation(tmp_path):
    _write_hooks_json(tmp_path, _UNBRACED.strip('"'))
    violations = gate.find_violations(tmp_path)
    assert [path for path, _ in violations] == ["hooks/hooks.json"]


def test_braced_command_in_hooks_json_passes(tmp_path):
    _write_hooks_json(tmp_path, _BRACED.strip('"'))
    assert gate.find_violations(tmp_path) == []


def test_command_nested_under_an_unknown_event_name_is_still_read(tmp_path):
    """The walker must not depend on Claude Code's hook-event vocabulary."""
    path = tmp_path / "hooks" / "hooks.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"hooks": {"SomeFutureEvent": [[{"command": _UNBRACED.strip('"')}]]}}),
        encoding="utf-8",
    )
    assert len(gate.find_violations(tmp_path)) == 1


def test_non_string_command_value_does_not_crash_the_walker(tmp_path):
    path = tmp_path / "hooks" / "hooks.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"hooks": {"X": [{"command": {"nested": 1}}]}}), encoding="utf-8")
    assert gate.find_violations(tmp_path) == []


def test_unbraced_variable_in_agent_frontmatter_is_a_violation(tmp_path):
    path = tmp_path / "agents" / "a.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: a\nhooks:\n  PreToolUse:\n    - command: {_UNBRACED}\n---\n\nBody.\n",
        encoding="utf-8",
    )
    assert [p for p, _ in gate.find_violations(tmp_path)] == ["agents/a.md"]


def test_prose_naming_the_variable_is_not_a_violation(tmp_path):
    """A doc paragraph explaining the bug must never fail this gate."""
    path = tmp_path / "agents" / "a.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: a\n---\n\nThis fires only when $CLAUDE_PLUGIN_ROOT is set.\n",
        encoding="utf-8",
    )
    assert gate.find_violations(tmp_path) == []


def test_a_longer_variable_name_sharing_the_prefix_is_not_flagged(tmp_path):
    _write_hooks_json(tmp_path, "$CLAUDE_PLUGIN_ROOT_BACKUP/hooks/check.sh")
    assert gate.find_violations(tmp_path) == []


def test_apm_cache_and_deploy_trees_are_excluded(tmp_path):
    """A third party's notation must not fail this repository's PR."""
    for relative in (
        "apm_modules/obra/superpowers/hooks/hooks.json",
        ".claude/hooks/superpowers/hooks/hooks.json",
        ".claude/skills/x/hooks/hooks.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"command": _UNBRACED.strip('"')}), encoding="utf-8")
    assert gate.find_violations(tmp_path) == []


def test_project_agents_directory_is_scanned(tmp_path):
    """`.claude/agents/` is in scope even though `.claude/hooks/` is not."""
    path = tmp_path / ".claude" / "agents" / "a.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\ncommand: {_UNBRACED}\n---\n", encoding="utf-8")
    assert [p for p, _ in gate.find_violations(tmp_path)] == [".claude/agents/a.md"]


def test_frontmatter_absent_returns_empty():
    assert gate.frontmatter("no frontmatter here\n") == ""


def test_frontmatter_unterminated_returns_empty():
    assert gate.frontmatter("---\nname: a\nstill going\n") == ""


def test_frontmatter_survives_a_longer_dash_rule_inside_the_block():
    """A four-dash line must not be read as the closing delimiter."""
    assert gate.frontmatter("---\na: 1\n----\nb: 2\n---\nbody\n") == "a: 1\n----\nb: 2"


def test_frontmatter_tolerates_a_leading_bom():
    assert gate.frontmatter("\ufeff---\na: 1\n---\n") == "a: 1"


def test_main_returns_zero_on_the_real_repository(capsys):
    assert gate.main(["--root", str(REPO_ROOT)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(tmp_path, capsys):
    _write_hooks_json(tmp_path, _UNBRACED.strip('"'))
    assert gate.main(["--root", str(tmp_path)]) == 1
    stderr = capsys.readouterr().err
    assert "unbraced" in stderr
    assert "#650" in stderr

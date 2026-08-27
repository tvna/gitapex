"""Tests for the plugin-root brace-notation gate
(.github/scripts/gitapex_gate_plugin_root_brace_notation.py).

Refs #650. The gate exists because `hooks/hooks.json` authored every hook
command with the unbraced `$CLAUDE_PLUGIN_ROOT`, which apm 0.25.0 copies
verbatim instead of rewriting -- so an apm-installed consumer silently
received seven hook commands that could not resolve.

The defeat-cases carry as much weight here as the happy path, and several
of them are regressions for defects a code review found in this gate's own
first revision: a gate that fired on prose in a `description:` would be
reverted the first time someone documented this bug, one that passed on an
unterminated frontmatter block would miss a real command, and one that
reported success having discovered nothing would be a permanent green
no-op. Each is pinned below.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import gitapex_gate_plugin_root_brace_notation as gate
from conftest import assert_workflow_has_no_trigger_path_filter

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_BRACED = "${CLAUDE_PLUGIN_ROOT}/hooks/check.sh"
_UNBRACED = "$CLAUDE_PLUGIN_ROOT/hooks/check.sh"


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Init a git repository -- discovery reads tracked files, not the tree."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _write(root: pathlib.Path, relative: str, content: str, *, track: bool = True):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if track:
        subprocess.run(["git", "-C", str(root), "add", "--", relative], check=True)
    return path


def _manifest(command) -> str:
    return json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": command}]}]}})


# --- the real repository -----------------------------------------------


def test_repository_hook_commands_all_brace_the_variable():
    """The real checkout passes -- the regression anchor for #650's fix."""
    assert gate.find_violations(REPO_ROOT) == []


def test_repository_scan_reaches_the_real_hook_surfaces():
    """Without this, a discovery bug that found nothing would make the test
    above pass for the wrong reason."""
    discovered = {p.relative_to(REPO_ROOT).as_posix() for p in gate.discover(REPO_ROOT)}
    assert "hooks/hooks.json" in discovered
    assert "agents/branch-plan-task.md" in discovered
    assert ".claude/agents/branch-plan-task.md" in discovered


# --- violations ---------------------------------------------------------


def test_unbraced_command_in_hooks_json_is_a_violation(tmp_path):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(_UNBRACED))
    assert [path for path, _ in gate.find_violations(root)] == ["hooks/hooks.json"]


def test_braced_command_in_hooks_json_passes(tmp_path):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(_BRACED))
    assert gate.find_violations(root) == []


def test_command_nested_under_an_unknown_event_name_is_still_read(tmp_path):
    """The walker must not depend on Claude Code's hook-event vocabulary."""
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", json.dumps({"hooks": {"Future": [[{"command": _UNBRACED}]]}}))
    assert len(gate.find_violations(root)) == 1


def test_variable_buried_in_a_longer_shell_command_is_caught(tmp_path):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(f'bash -c "{_UNBRACED} --flag"'))
    assert len(gate.find_violations(root)) == 1


def test_unbraced_command_in_agent_frontmatter_is_a_violation(tmp_path):
    root = _repo(tmp_path)
    _write(root, "agents/a.md", f'---\nname: a\ncommand: "{_UNBRACED}"\n---\n\nBody.\n')
    assert [path for path, _ in gate.find_violations(root)] == ["agents/a.md"]


def test_agent_in_a_subdirectory_is_scanned(tmp_path):
    """A flat glob would miss an author who groups agents into folders."""
    root = _repo(tmp_path)
    _write(root, "agents/sub/a.md", f'---\ncommand: "{_UNBRACED}"\n---\n')
    assert [path for path, _ in gate.find_violations(root)] == ["agents/sub/a.md"]


# --- must not fire ------------------------------------------------------


def test_prose_in_the_body_naming_the_variable_is_not_a_violation(tmp_path):
    root = _repo(tmp_path)
    _write(root, "agents/a.md", f"---\nname: a\n---\n\nFires only when {_UNBRACED} is set.\n")
    assert gate.find_violations(root) == []


def test_prose_in_frontmatter_naming_the_variable_is_not_a_violation(tmp_path):
    """Regression: an earlier revision grepped every frontmatter line, so a
    `description:` discussing the variable failed a file declaring no hook.
    `agents/branch-plan-task.md`'s own description discusses exactly that."""
    root = _repo(tmp_path)
    _write(
        root,
        "agents/a.md",
        f"---\nname: a\ndescription: carries no hook, so {_UNBRACED} never resolves here.\n---\n",
    )
    assert gate.find_violations(root) == []


def test_a_longer_variable_name_sharing_the_prefix_is_not_flagged(tmp_path):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest("$CLAUDE_PLUGIN_ROOT_BACKUP/hooks/check.sh"))
    assert gate.find_violations(root) == []


def test_list_valued_command_is_out_of_scope(tmp_path):
    """Deliberate miss: Claude Code documents `command` as a string only."""
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest([_UNBRACED]))
    assert gate.find_violations(root) == []


def test_untracked_files_are_not_scanned(tmp_path):
    """Regression: a filesystem walk graded apm's deploy trees and the repo's
    own `.claude/worktrees/` checkouts -- content that is not this diff's.
    Reading tracked files excludes every ignored path by construction."""
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(_BRACED))
    for untracked in (
        ".claude/worktrees/task-1/hooks/hooks.json",
        ".claude/hooks/superpowers/hooks/hooks.json",
        "sub/.claude/hooks/superpowers/hooks/hooks.json",
        "apm_modules/obra/superpowers/hooks/hooks.json",
    ):
        _write(root, untracked, _manifest(_UNBRACED), track=False)
    assert gate.find_violations(root) == []


def test_agent_file_without_frontmatter_is_not_an_error(tmp_path):
    """A plain Markdown file under agents/ (a README) is legitimate."""
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(_BRACED))
    _write(root, "agents/README.md", "# Agents\n\nNo frontmatter here.\n")
    assert gate.main(["--root", str(root)]) == 0


# --- fail closed (exit 2) ----------------------------------------------


def test_discovering_nothing_is_an_error_not_a_pass(tmp_path, capsys):
    """Regression: reporting success having checked nothing would make this
    a permanent green no-op after a rename or a wrong scan root."""
    root = _repo(tmp_path)
    assert gate.main(["--root", str(root)]) == 2
    assert "checking nothing" in capsys.readouterr().err


def test_malformed_hooks_json_fails_closed_naming_the_file(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", "{not json")
    assert gate.main(["--root", str(root)]) == 2
    stderr = capsys.readouterr().err
    assert "not valid JSON" in stderr
    assert "hooks.json" in stderr


def test_unterminated_frontmatter_fails_closed(tmp_path, capsys):
    """Regression: an earlier revision returned an empty block here, so a
    real unbraced command inside it was never graded and the gate passed."""
    root = _repo(tmp_path)
    _write(root, "agents/a.md", f'---\nname: a\ncommand: "{_UNBRACED}"\n')
    assert gate.main(["--root", str(root)]) == 2
    assert "never closes" in capsys.readouterr().err


def test_non_utf8_file_fails_closed_naming_the_file(tmp_path, capsys):
    root = _repo(tmp_path)
    path = _write(root, "hooks/hooks.json", _manifest(_BRACED))
    path.write_bytes(b'{"command": "\xff\xfe"}')
    assert gate.main(["--root", str(root)]) == 2
    assert "hooks.json" in capsys.readouterr().err


def test_a_non_repository_root_fails_closed(tmp_path, capsys):
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "git ls-files failed" in capsys.readouterr().err


def test_git_missing_entirely_fails_closed(tmp_path, capsys, monkeypatch):
    """No git on PATH must not surface as a raw traceback."""

    def _no_git(*args, **kwargs):
        raise OSError("No such file or directory: 'git'")

    monkeypatch.setattr(gate.subprocess, "run", _no_git)
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "cannot run git" in capsys.readouterr().err


# --- frontmatter helper -------------------------------------------------


def test_frontmatter_absent_returns_empty_string():
    assert gate.frontmatter("no frontmatter here\n") == ""


def test_frontmatter_unterminated_returns_none():
    assert gate.frontmatter("---\nname: a\nstill going\n") is None


def test_frontmatter_survives_a_longer_dash_rule_inside_the_block():
    """A four-dash line must not be read as the closing delimiter."""
    assert gate.frontmatter("---\na: 1\n----\nb: 2\n---\nbody\n") == "a: 1\n----\nb: 2"


def test_frontmatter_tolerates_a_leading_bom():
    assert gate.frontmatter("\ufeff---\na: 1\n---\n") == "a: 1"


# --- CLI ----------------------------------------------------------------


def test_main_returns_zero_on_the_real_repository(capsys):
    assert gate.main(["--root", str(REPO_ROOT)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_success_message_shows_the_braced_form(capsys):
    """Regression: the OK line rendered the very token the gate forbids."""
    gate.main(["--root", str(REPO_ROOT)])
    out = capsys.readouterr().out
    assert "${CLAUDE_PLUGIN_ROOT}" in out
    assert "brace $CLAUDE_PLUGIN_ROOT." not in out


def test_main_returns_one_and_explains_the_failure(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, "hooks/hooks.json", _manifest(_UNBRACED))
    assert gate.main(["--root", str(root)]) == 1
    stderr = capsys.readouterr().err
    assert "unbraced" in stderr
    assert "#650" in stderr


# --- GatePluginRootBraceNotationArgs validation (new pydantic-model behavior) ---


def test_main_exits_2_on_a_root_that_does_not_exist(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"
    assert gate.main(["--root", str(missing)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_is_a_file(tmp_path, capsys):
    a_file = tmp_path / "not-a-directory"
    a_file.write_text("x", encoding="utf-8")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


# --- the real repository's own CI workflow -------------------------------


def test_the_workflow_has_no_paths_filter() -> None:
    """Drift gate for this workflow's own no-`paths:`-filter invariant, per
    CLAUDE.md section 3 and the same `skill-eval-gate.yml` rationale: a
    filter here would leave a required check stuck `Pending` for any PR
    that doesn't touch one of the three small files this gate scans.
    `conftest.assert_workflow_has_no_trigger_path_filter`'s own docstring
    carries the mechanics.
    """
    assert_workflow_has_no_trigger_path_filter("plugin-root-brace-notation-gate.yml")

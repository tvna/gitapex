"""Regression suite for the review-thread-resolution + mergeable_state-
verification obligation's PostToolUse state-writer half (issue #1209).

See hooks/gitapex_check_post_review_obligation_tracker.py's own module
docstring for the full state-machine design this exercises: a git-push
Bash call (reusing hooks/gitapex_check_bash_safety.py's own
is_git_push classifier) resets the state file; resolve_review_thread and
pull_request_read update it; the Stop hook
(hooks/gitapex_check_stop_review_obligation.py, its own test suite in
hooks/test_gitapex_check_stop_review_obligation.py) reads it back.

Direct-import unit tests exercise `process()` (fast, no subprocess); a
smaller shell-level suite runs the shipped .sh wrapper via subprocess with
the same PostToolUse JSON shape Claude Code sends on stdin, confirming the
wrapper's own jq/shape-guard prologue and its always-exit-0 contract
(PostToolUse cannot block an already-executed call).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import gitapex_check_post_review_obligation_tracker as tracker
import pytest

SCRIPT = Path(__file__).parent / "check-post-review-obligation-tracker.sh"


@pytest.fixture(autouse=True)
def _isolated_tmpdir(tmp_path: Path, monkeypatch: Any) -> None:
    # Every test below shares hooks/gitapex_check_post_review_obligation_tracker.py's
    # own state_path() -- without this, two tests reusing the same
    # session_id (or a stray file left by a manual run) would read each
    # other's state. state_path() reads os.environ["TMPDIR"] fresh on
    # every call (see its own docstring), so this is enough to isolate
    # every test in this module, not just the ones that pass tmp_path
    # explicitly.
    monkeypatch.setenv("TMPDIR", str(tmp_path))


# --- Direct-import unit tests -------------------------------------------


def test_non_matching_tool_is_ignored() -> None:
    assert tracker.process({"session_id": "s1", "tool_name": "Read", "tool_input": {}}) is None


def test_bash_non_push_command_is_ignored() -> None:
    assert tracker.process({"session_id": "s2", "tool_name": "Bash", "tool_input": {"command": "echo hi"}}) is None


def test_bash_git_push_resets_state() -> None:
    result = tracker.process({"session_id": "s3", "tool_name": "Bash", "tool_input": {"command": "git push"}})
    assert result == {
        "push_detected": True,
        "open_review_threads": None,
        "resolve_calls": 0,
        "mergeable_checked": False,
    }


def test_bash_missing_command_is_ignored() -> None:
    assert tracker.process({"session_id": "s4", "tool_name": "Bash", "tool_input": {}}) is None


def test_resolve_review_thread_noop_without_prior_push() -> None:
    assert tracker.process({"session_id": "s5", "tool_name": "mcp__github__resolve_review_thread"}) is None


def test_resolve_review_thread_increments_after_push() -> None:
    session_id = "s6"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    result = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert result is not None
    assert result["resolve_calls"] == 1
    result2 = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert result2 is not None
    assert result2["resolve_calls"] == 2


def test_get_review_comments_records_unresolved_count() -> None:
    session_id = "s7"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    response = {
        "threads": [
            {"isResolved": False, "comments": []},
            {"isResolved": True, "comments": []},
            {"isResolved": False, "comments": []},
        ]
    }
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get_review_comments"},
            "tool_response": response,
        }
    )
    assert result is not None
    assert result["open_review_threads"] == 2


def test_get_review_comments_ignored_without_prior_push() -> None:
    result = tracker.process(
        {
            "session_id": "s8",
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get_review_comments"},
            "tool_response": {"threads": [{"isResolved": False}]},
        }
    )
    assert result is None


def test_get_review_comments_zero_unresolved() -> None:
    session_id = "s9"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get_review_comments"},
            "tool_response": {"threads": [{"isResolved": True}]},
        }
    )
    assert result is not None
    assert result["open_review_threads"] == 0


def test_pull_request_read_get_sets_mergeable_checked() -> None:
    session_id = "s10"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get"},
            "tool_response": {"number": 42, "mergeable_state": "clean"},
        }
    )
    assert result is not None
    assert result["mergeable_checked"] is True


def test_pull_request_read_get_without_mergeable_state_field() -> None:
    session_id = "s11"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get"},
            "tool_response": {"number": 42},
        }
    )
    assert result is None or result["mergeable_checked"] is False


def test_second_push_resets_prior_progress() -> None:
    session_id = "s12"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    result = tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    assert result == {
        "push_detected": True,
        "open_review_threads": None,
        "resolve_calls": 0,
        "mergeable_checked": False,
    }


def test_missing_session_id_is_ignored() -> None:
    assert tracker.process({"tool_name": "Bash", "tool_input": {"command": "git push"}}) is None


def test_state_path_sanitizes_session_id() -> None:
    # tempfile.gettempdir() caches its result on first call, so this does
    # not attempt to redirect it via TMPDIR -- only the basename's own
    # sanitization is under test here.
    path = tracker.state_path("../../etc/passwd")
    assert ".." not in path.name
    assert "/" not in path.name


def test_count_unresolved_threads_handles_bare_list() -> None:
    assert tracker._count_unresolved_threads([{"isResolved": False}, {"isResolved": False}]) == 2


def test_contains_mergeable_state_handles_camel_case() -> None:
    assert tracker._contains_mergeable_state({"mergeableState": "CLEAN"}) is True
    assert tracker._contains_mergeable_state({"other": "field"}) is False


# --- Shell-wrapper integration tests ------------------------------------


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_path)
    return env


def _run(payload: dict[str, object], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_shell_always_exits_zero_on_git_push(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = _run({"session_id": "shell1", "tool_name": "Bash", "tool_input": {"command": "git push"}}, env)
    assert result.returncode == 0
    state_file = tmp_path / "gitapex-review-obligation-shell1.json"
    assert state_file.exists()
    assert json.loads(state_file.read_text())["push_detected"] is True


def test_shell_exits_zero_on_malformed_payload(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not json{{{",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert result.returncode == 0
    assert "systemMessage" in result.stdout


def test_shell_exits_zero_on_non_matching_tool(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = _run({"session_id": "shell2", "tool_name": "Read", "tool_input": {}}, env)
    assert result.returncode == 0
    assert not (tmp_path / "gitapex-review-obligation-shell2.json").exists()

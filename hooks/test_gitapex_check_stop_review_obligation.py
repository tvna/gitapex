"""Regression suite for the review-thread-resolution + mergeable_state-
verification obligation's Stop state-reader half (issue #1209).

See hooks/gitapex_check_stop_review_obligation.py's own module docstring
for the full design: reads only the state file
hooks/gitapex_check_post_review_obligation_tracker.py writes as a
PostToolUse side effect, never the network or the transcript, and treats
a genuinely absent state file as "nothing to verify" while failing closed
on a present-but-corrupt one.

Direct-import unit tests exercise `evaluate()` against hand-built state
dicts (fast, no subprocess, no filesystem). A smaller shell-level suite
runs the shipped .sh wrapper via subprocess with the same Stop JSON shape
Claude Code sends on stdin, confirming the wrapper's own jq/shape-guard
prologue and its exit-2/hookSpecificOutput deny contract.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import gitapex_check_post_review_obligation_tracker as tracker
import gitapex_check_stop_review_obligation as stop_checker

SCRIPT = Path(__file__).parent / "check-stop-review-obligation.sh"


# --- Direct-import unit tests -------------------------------------------


def test_no_push_detected_never_blocks() -> None:
    should_block, _ = stop_checker.evaluate({"push_detected": False})
    assert should_block is False


def test_none_state_never_blocks() -> None:
    should_block, _ = stop_checker.evaluate(None)
    assert should_block is False


def test_push_with_unknown_threads_and_no_mergeable_check_blocks() -> None:
    state = {"push_detected": True, "open_review_threads": None, "resolve_calls": 0, "mergeable_checked": False}
    should_block, reason = stop_checker.evaluate(state)
    assert should_block is True
    assert "mergeable_state" in reason
    assert "resolve_review_thread" not in reason  # threads unknown -- skip that half, per module docstring


def test_push_with_open_threads_and_insufficient_resolves_blocks() -> None:
    state = {"push_detected": True, "open_review_threads": 2, "resolve_calls": 1, "mergeable_checked": True}
    should_block, reason = stop_checker.evaluate(state)
    assert should_block is True
    assert "resolve_review_thread" in reason


def test_push_with_zero_open_threads_and_mergeable_checked_passes() -> None:
    state = {"push_detected": True, "open_review_threads": 0, "resolve_calls": 0, "mergeable_checked": True}
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is False


def test_push_with_sufficient_resolves_and_mergeable_checked_passes() -> None:
    state = {"push_detected": True, "open_review_threads": 2, "resolve_calls": 2, "mergeable_checked": True}
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is False


def test_push_with_more_resolves_than_threads_passes() -> None:
    # resolve_calls counts calls, not a bounded remaining-thread count --
    # more calls than the last-observed count is not itself suspicious.
    state = {"push_detected": True, "open_review_threads": 1, "resolve_calls": 3, "mergeable_checked": True}
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is False


def test_reason_names_both_missing_steps() -> None:
    state = {"push_detected": True, "open_review_threads": 1, "resolve_calls": 0, "mergeable_checked": False}
    should_block, reason = stop_checker.evaluate(state)
    assert should_block is True
    assert "resolve_review_thread" in reason
    assert "mergeable_state" in reason


# --- End-to-end direct-import: writer state feeds the reader -----------


def test_writer_then_reader_end_to_end(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    session_id = "e2e-1"
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    state = json.loads(tracker.state_path(session_id).read_text())
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is True  # mergeable_state never checked

    tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get"},
            "tool_response": {"mergeable_state": "clean"},
        }
    )
    state = json.loads(tracker.state_path(session_id).read_text())
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is False


# --- main()/_load_state error-path tests --------------------------------


def test_load_state_missing_file_returns_none(tmp_path: Path) -> None:
    assert stop_checker._load_state(tmp_path / "does-not-exist.json") is None


def test_load_state_corrupt_json_raises(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not json{{{")
    try:
        stop_checker._load_state(corrupt)
        raised = False
    except stop_checker.StateUnreadable:
        raised = True
    assert raised


def test_load_state_non_object_json_raises(tmp_path: Path) -> None:
    non_object = tmp_path / "list.json"
    non_object.write_text("[1, 2, 3]")
    try:
        stop_checker._load_state(non_object)
        raised = False
    except stop_checker.StateUnreadable:
        raised = True
    assert raised


# --- Shell-wrapper integration tests ------------------------------------


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_path)
    return env


def _run_stop(payload: dict[str, object], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_shell_allows_when_no_state_file(tmp_path: Path) -> None:
    result = _run_stop({"session_id": "shell-none"}, _env(tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_shell_denies_after_push_with_no_followup(tmp_path: Path) -> None:
    env = _env(tmp_path)
    tracker_script = Path(__file__).parent / "check-post-review-obligation-tracker.sh"
    subprocess.run(
        ["bash", str(tracker_script)],
        input=json.dumps({"session_id": "shell-deny", "tool_name": "Bash", "tool_input": {"command": "git push"}}),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    result = _run_stop({"session_id": "shell-deny"}, env)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"
    assert "mergeable_state" in payload["hookSpecificOutput"]["reason"]


def test_shell_allows_and_clears_state_once_satisfied(tmp_path: Path) -> None:
    env = _env(tmp_path)
    tracker_script = Path(__file__).parent / "check-post-review-obligation-tracker.sh"
    session_id = "shell-clear"
    subprocess.run(
        ["bash", str(tracker_script)],
        input=json.dumps({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}}),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    subprocess.run(
        ["bash", str(tracker_script)],
        input=json.dumps(
            {
                "session_id": session_id,
                "tool_name": "mcp__github__pull_request_read",
                "tool_input": {"method": "get"},
                "tool_response": {"mergeable_state": "clean"},
            }
        ),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    state_file = tmp_path / f"gitapex-review-obligation-{session_id}.json"
    assert state_file.exists()

    result = _run_stop({"session_id": session_id}, env)
    assert result.returncode == 0
    assert not state_file.exists()


def test_shell_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input="not json{{{",
        capture_output=True,
        text=True,
        timeout=10,
        env=_env(tmp_path),
    )
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"


def test_shell_fails_closed_on_corrupt_state_file(tmp_path: Path) -> None:
    env = _env(tmp_path)
    session_id = "shell-corrupt"
    state_file = tmp_path / f"gitapex-review-obligation-{session_id}.json"
    state_file.write_text("not json{{{")
    result = _run_stop({"session_id": session_id}, env)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"

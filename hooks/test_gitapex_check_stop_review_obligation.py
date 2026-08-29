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
Claude Code sends on stdin, confirming the wrapper's own missing-python3/
missing-check-script guards and its exit-2/hookSpecificOutput deny
contract. The wrapper carries no jq dependency at all (see its own
header for the deadlock this fixed -- a jq-missing environment used to
deny every turn end unconditionally, together with
hooks/check-bash-safety.sh's own jq-missing fail-closed posture on Bash,
a full deadlock); a dedicated jq-missing test below proves that fix.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import gitapex_check_post_review_obligation_tracker as tracker
import gitapex_check_stop_review_obligation as stop_checker
import pytest

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
    assert "get_review_comments" in reason
    assert "resolve_review_thread" not in reason  # threads unknown -- can't yet know how many to resolve


def test_push_with_unknown_threads_still_blocks_even_when_mergeable_checked() -> None:
    # Independent-review finding, reproduced live against the writer half:
    # a turn that pushed, then only read an unrelated PR's mergeable_state
    # (never called get_review_comments at all), must not satisfy this
    # gate merely because mergeable_checked happens to be True -- the
    # thread state was never actually confirmed.
    state = {"push_detected": True, "open_review_threads": None, "resolve_calls": 0, "mergeable_checked": True}
    should_block, reason = stop_checker.evaluate(state)
    assert should_block is True
    assert "get_review_comments" in reason
    assert "mergeable_state" not in reason  # that half is genuinely satisfied


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
    assert should_block is True  # nothing checked yet at all

    tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"pullNumber": 1209, "method": "get"},
            "tool_response": {"mergeable_state": "clean"},
        }
    )
    state = json.loads(tracker.state_path(session_id).read_text())
    should_block, reason = stop_checker.evaluate(state)
    assert should_block is True  # mergeable_state checked, but review threads never were
    assert "get_review_comments" in reason

    tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"pullNumber": 1209, "method": "get_review_comments"},
            "tool_response": {"threads": []},
        }
    )
    state = json.loads(tracker.state_path(session_id).read_text())
    should_block, _ = stop_checker.evaluate(state)
    assert should_block is False


# --- main()/_load_state error-path tests --------------------------------


def test_load_state_missing_file_returns_none(tmp_path: Path) -> None:
    assert stop_checker._load_state(tmp_path / "does-not-exist.json") is None


def test_load_state_returns_parsed_dict(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"push_detected": True}))
    assert stop_checker._load_state(path) == {"push_detected": True}


def test_load_state_corrupt_json_raises(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not json{{{")
    with pytest.raises(stop_checker.StateUnreadable):
        stop_checker._load_state(corrupt)


def test_load_state_non_object_json_raises(tmp_path: Path) -> None:
    non_object = tmp_path / "list.json"
    non_object.write_text("[1, 2, 3]")
    with pytest.raises(stop_checker.StateUnreadable):
        stop_checker._load_state(non_object)


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


def _stub_bin_without(tmp_path: Path, *, exclude: str) -> Path:
    """A directory on PATH containing every ordinary tool this wrapper (or
    the tracker script it may also invoke in the same test) needs, EXCEPT
    `exclude` -- used to simulate that one tool being entirely absent from
    the environment, rather than merely unconfigured."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir(exist_ok=True)
    for tool in ("bash", "cat", "dirname", "pwd", "python3"):
        if tool == exclude:
            continue
        # cast(), not an `if source:` guard -- these are standard system
        # tools always present wherever this suite itself can run, so a
        # runtime None-check here would be a permanently-untaken branch,
        # not real robustness.
        (stub_bin / tool).symlink_to(cast(str, shutil.which(tool)))
    return stub_bin


def test_shell_stop_hook_does_not_block_unrelated_turn_when_jq_is_missing(tmp_path: Path) -> None:
    # Independent-review finding, reproduced live: this wrapper used to
    # pre-validate payload shape via jq and deny (exit 2) whenever jq
    # itself was missing -- unconditionally, even for a turn that never
    # touched a push or a review thread. Combined with
    # hooks/check-bash-safety.sh's own jq-missing fail-closed posture on
    # Bash, this created a full deadlock (Bash denied, Stop denied, no way
    # to self-heal). This wrapper no longer depends on jq at all -- see its
    # own header -- so an ordinary turn with no state file must still pass
    # cleanly even with jq entirely absent from PATH.
    stub_bin = _stub_bin_without(tmp_path, exclude="jq")
    env = _env(tmp_path)
    env["PATH"] = str(stub_bin)
    result = _run_stop({"session_id": "shell-no-jq-unrelated"}, env)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_shell_stop_hook_still_blocks_when_jq_missing_and_obligation_outstanding(tmp_path: Path) -> None:
    # The other half of the fix above: a jq-missing environment must not
    # become universally permissive either -- a genuinely outstanding
    # obligation still has to deny, jq or no jq, since jq was never what
    # determined push_detected in the first place (that's read entirely
    # in python, from the state file the tracker script -- also jq-free,
    # see its own header -- already wrote).
    stub_bin = _stub_bin_without(tmp_path, exclude="jq")
    env = _env(tmp_path)
    env["PATH"] = str(stub_bin)
    tracker_script = Path(__file__).parent / "check-post-review-obligation-tracker.sh"
    subprocess.run(
        ["bash", str(tracker_script)],
        input=json.dumps(
            {"session_id": "shell-no-jq-deny", "tool_name": "Bash", "tool_input": {"command": "git push"}}
        ),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    result = _run_stop({"session_id": "shell-no-jq-deny"}, env)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"


def test_shell_fails_closed_when_python3_is_missing(tmp_path: Path) -> None:
    stub_bin = _stub_bin_without(tmp_path, exclude="python3")
    env = _env(tmp_path)
    env["PATH"] = str(stub_bin)
    result = _run_stop({"session_id": "shell-no-python3"}, env)
    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["hookSpecificOutput"]["decision"] == "block"
    assert "python3 is not available on PATH" in payload["hookSpecificOutput"]["reason"]


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
                "tool_input": {"pullNumber": 1209, "method": "get"},
                "tool_response": {"mergeable_state": "clean"},
            }
        ),
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
                "tool_input": {"pullNumber": 1209, "method": "get_review_comments"},
                "tool_response": {"threads": []},
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


# --- main() CLI entry point (direct call, not via the .sh wrapper) --------


def test_main_handles_invalid_json_payload(monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(b"not json{{{")})())
    assert stop_checker.main() == 1


def test_main_handles_non_object_payload(monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(b"[1, 2, 3]")})())
    assert stop_checker.main() == 1


def test_main_returns_zero_when_session_id_missing(monkeypatch: Any) -> None:
    import io as _io

    payload = json.dumps({})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert stop_checker.main() == 0


def test_main_returns_zero_when_no_state_file(tmp_path: Path, monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    payload = json.dumps({"session_id": "main-none"})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert stop_checker.main() == 0


def test_main_blocks_and_prints_reason_when_obligation_outstanding(tmp_path: Path, monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    session_id = "main-block"
    tracker.state_path(session_id).write_text(
        json.dumps({"push_detected": True, "target_pr": "#1", "open_review_threads": None, "mergeable_checked": False})
    )
    payload = json.dumps({"session_id": session_id})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert stop_checker.main() == 1


def test_main_returns_one_when_state_unreadable(tmp_path: Path, monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    session_id = "main-corrupt"
    tracker.state_path(session_id).write_text("not json{{{")
    payload = json.dumps({"session_id": session_id})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert stop_checker.main() == 1


def test_main_clears_state_file_when_satisfied(tmp_path: Path, monkeypatch: Any) -> None:
    import io as _io

    monkeypatch.setenv("TMPDIR", str(tmp_path))
    session_id = "main-clear"
    state_file = tracker.state_path(session_id)
    state_file.write_text(
        json.dumps(
            {
                "push_detected": True,
                "target_pr": "#1",
                "open_review_threads": 0,
                "resolve_calls": 0,
                "mergeable_checked": True,
            }
        )
    )
    payload = json.dumps({"session_id": session_id})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert stop_checker.main() == 0
    assert not state_file.exists()

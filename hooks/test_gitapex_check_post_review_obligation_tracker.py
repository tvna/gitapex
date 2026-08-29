"""Regression suite for the review-thread-resolution + mergeable_state-
verification obligation's PostToolUse state-writer half (issue #1209).

See hooks/gitapex_check_post_review_obligation_tracker.py's own module
docstring for the full state-machine design this exercises: a git-push
Bash call (reusing hooks/gitapex_check_bash_safety.py's own
is_git_push classifier) resets the state file; resolve_review_thread and
pull_request_read update it, the latter also establishing `target_pr` --
a call naming a different PR than the one currently tracked switches
`target_pr` to it and resets tracked progress (open_review_threads/
resolve_calls/mergeable_checked), rather than being ignored, so a wrong
first read can never permanently lock out the real target; the Stop hook
(hooks/gitapex_check_stop_review_obligation.py, its own test suite
in hooks/test_gitapex_check_stop_review_obligation.py) reads it back.

Direct-import unit tests exercise `process()` (fast, no subprocess); a
smaller shell-level suite runs the shipped .sh wrapper via subprocess with
the same PostToolUse JSON shape Claude Code sends on stdin, confirming the
wrapper's own missing-script/missing-python3 guards and its always-exit-0
contract (PostToolUse cannot block an already-executed call). The wrapper
carries no jq dependency at all -- see its own header for why -- so there
is no jq-missing case to test here (contrast with the Stop-hook sibling's
own suite, which specifically tests that a jq-missing environment no
longer denies).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import gitapex_check_post_review_obligation_tracker as tracker
import pytest

SCRIPT = Path(__file__).parent / "check-post-review-obligation-tracker.sh"

_PR_INPUT = {"owner": "tvna", "repo": "gitapex", "pullNumber": 1209}


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


def _push(session_id: str) -> None:
    tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})


def _read_pr(session_id: str, *, method: str = "get_review_comments", response: object = None) -> dict[str, Any] | None:
    return tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {**_PR_INPUT, "method": method},
            "tool_response": response if response is not None else {},
        }
    )


# --- Direct-import unit tests -------------------------------------------


def test_non_matching_tool_is_ignored() -> None:
    assert tracker.process({"session_id": "s1", "tool_name": "Read", "tool_input": {}}) is None


def test_bash_non_push_command_is_ignored() -> None:
    assert tracker.process({"session_id": "s2", "tool_name": "Bash", "tool_input": {"command": "echo hi"}}) is None


def test_bash_git_push_resets_state() -> None:
    result = tracker.process({"session_id": "s3", "tool_name": "Bash", "tool_input": {"command": "git push"}})
    assert result == {
        "push_detected": True,
        "target_pr": None,
        "open_review_threads": None,
        "resolve_calls": 0,
        "mergeable_checked": False,
    }


def test_bash_missing_command_is_ignored() -> None:
    assert tracker.process({"session_id": "s4", "tool_name": "Bash", "tool_input": {}}) is None


def test_resolve_review_thread_noop_without_prior_push() -> None:
    assert tracker.process({"session_id": "s5", "tool_name": "mcp__github__resolve_review_thread"}) is None


def test_resolve_review_thread_noop_without_target_pr_established() -> None:
    # Independent review finding: a push alone must not let
    # resolve_review_thread count -- target_pr is only established by a
    # pull_request_read call, per the module's own documented ordering.
    session_id = "s5b"
    _push(session_id)
    assert tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"}) is None


def test_resolve_review_thread_increments_after_push_and_read() -> None:
    session_id = "s6"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    result = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert result is not None
    assert result["resolve_calls"] == 1
    result2 = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert result2 is not None
    assert result2["resolve_calls"] == 2


def test_resolve_review_thread_error_response_not_counted() -> None:
    # Independent review finding: a failed/rejected resolve call was
    # previously counted identically to a successful one.
    session_id = "s6b"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__resolve_review_thread",
            "tool_response": {"isError": True, "content": "invalid thread id"},
        }
    )
    assert result is None


def test_resolve_review_thread_nested_error_response_not_counted() -> None:
    session_id = "s6c"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__resolve_review_thread",
            "tool_response": [{"type": "text", "text": json.dumps({"status": "error", "message": "nope"})}],
        }
    )
    assert result is None


def test_get_review_comments_records_unresolved_count() -> None:
    session_id = "s7"
    _push(session_id)
    response = {
        "threads": [
            {"isResolved": False, "comments": []},
            {"isResolved": True, "comments": []},
            {"isResolved": False, "comments": []},
        ]
    }
    result = _read_pr(session_id, response=response)
    assert result is not None
    assert result["open_review_threads"] == 2
    assert result["target_pr"] == "tvna/gitapex#1209"


def test_get_review_comments_ignored_without_prior_push() -> None:
    result = _read_pr("s8", response={"threads": [{"isResolved": False}]})
    assert result is None


def test_get_review_comments_zero_unresolved() -> None:
    session_id = "s9"
    _push(session_id)
    result = _read_pr(session_id, response={"threads": [{"isResolved": True}]})
    assert result is not None
    assert result["open_review_threads"] == 0


def test_pull_request_read_get_sets_mergeable_checked() -> None:
    session_id = "s10"
    _push(session_id)
    result = _read_pr(session_id, method="get", response={"number": 1209, "mergeable_state": "clean"})
    assert result is not None
    assert result["mergeable_checked"] is True


def test_pull_request_read_get_without_mergeable_state_field() -> None:
    session_id = "s11"
    _push(session_id)
    result = _read_pr(session_id, method="get", response={"number": 1209})
    assert result is None or result["mergeable_checked"] is False


def test_second_push_resets_prior_progress() -> None:
    session_id = "s12"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    result = tracker.process({"session_id": session_id, "tool_name": "Bash", "tool_input": {"command": "git push"}})
    assert result == {
        "push_detected": True,
        "target_pr": None,
        "open_review_threads": None,
        "resolve_calls": 0,
        "mergeable_checked": False,
    }


def test_missing_session_id_is_ignored() -> None:
    assert tracker.process({"tool_name": "Bash", "tool_input": {"command": "git push"}}) is None


def test_write_state_cleans_up_temp_file_on_replace_failure(tmp_path: Path, monkeypatch: Any) -> None:
    # Independent-review finding: the write path must not leave a stray
    # temp file behind (or swallow the failure) when the final atomic
    # rename itself fails.
    path = tmp_path / "state.json"

    def _raise(self: Path, target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", _raise)
    with pytest.raises(OSError):
        tracker._write_state(path, {"push_detected": True})
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


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


# --- Cross-PR scoping (independent-review finding) -----------------------


def test_pull_request_read_against_a_different_pr_switches_target_and_resets_progress() -> None:
    session_id = "s13"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})  # establishes target_pr #1209
    tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    other_pr_input = {"owner": "tvna", "repo": "gitapex", "pullNumber": 999, "method": "get"}
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": other_pr_input,
            "tool_response": {"number": 999, "mergeable_state": "clean"},
        }
    )
    assert result is not None
    assert result["target_pr"] == "tvna/gitapex#999"
    assert result["open_review_threads"] is None  # reset, not carried forward from #1209
    assert result["resolve_calls"] == 0  # reset, not carried forward from #1209
    assert result["mergeable_checked"] is True  # this call's own method=get response sets it


def test_switching_back_to_the_real_target_unblocks_after_a_wrong_pr_was_read_first() -> None:
    # Second independent-review finding: the FIRST pull_request_read call
    # this cycle must not permanently lock target_pr onto whichever PR the
    # agent happened to read first -- a later call against the actual push
    # target must still be able to satisfy the obligation, not be silently
    # ignored forever because an unrelated PR claimed target_pr first.
    session_id = "s13b"
    _push(session_id)
    wrong_pr_input = {"owner": "tvna", "repo": "gitapex", "pullNumber": 1, "method": "get"}
    first = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": wrong_pr_input,
            "tool_response": {"number": 1, "mergeable_state": "clean"},
        }
    )
    assert first is not None
    assert first["target_pr"] == "tvna/gitapex#1"
    assert first["mergeable_checked"] is True

    switched = _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    assert switched is not None
    assert switched["target_pr"] == "tvna/gitapex#1209"
    assert switched["mergeable_checked"] is False  # reset by the switch, not carried over from PR #1
    assert switched["open_review_threads"] == 1

    resolved = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert resolved is not None
    assert resolved["resolve_calls"] == 1


def test_resolve_review_thread_against_established_target_still_counts() -> None:
    # Sanity check that the target-switch handling above does not also
    # disturb the ordinary, same-PR case.
    session_id = "s14"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})
    result = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert result is not None
    assert result["resolve_calls"] == 1


def test_pr_key_requires_a_real_int_pull_number() -> None:
    assert tracker._pr_key({}) is None
    assert tracker._pr_key({"pullNumber": True}) is None  # bool is an int subclass -- must be rejected explicitly
    assert tracker._pr_key({"pullNumber": "1209"}) is None


def test_pr_key_falls_back_to_bare_number_without_owner_repo() -> None:
    assert tracker._pr_key({"pullNumber": 1209}) == "#1209"
    assert tracker._pr_key({"owner": "tvna", "repo": "gitapex", "pullNumber": 1209}) == "tvna/gitapex#1209"


def test_same_pr_matches_bare_and_qualified_keys_for_the_same_number() -> None:
    assert tracker._same_pr("#1209", "tvna/gitapex#1209") is True
    assert tracker._same_pr("tvna/gitapex#1209", "#1209") is True
    assert tracker._same_pr("tvna/gitapex#1209", "tvna/gitapex#1209") is True
    assert tracker._same_pr("#1209", "#1209") is True


def test_same_pr_rejects_different_numbers_regardless_of_qualification() -> None:
    assert tracker._same_pr("#1209", "#999") is False
    assert tracker._same_pr("tvna/gitapex#1209", "tvna/gitapex#999") is False
    assert tracker._same_pr("tvna/gitapex#1209", "#999") is False


def test_same_pr_rejects_same_number_different_owner_repo() -> None:
    # The one case both sides are qualified AND disagree -- a genuinely
    # different repository reusing the same PR number.
    assert tracker._same_pr("tvna/gitapex#1209", "other/repo#1209") is False


def test_pull_request_read_same_pr_with_and_without_owner_repo_preserves_progress() -> None:
    # Independent-review finding (third round): plain string equality
    # treated "tvna/gitapex#1209" and "#1209" -- the SAME real PR, just
    # observed with owner/repo present on one call and absent on
    # another -- as a PR switch, discarding already-confirmed progress.
    session_id = "s18"
    _push(session_id)
    established = _read_pr(session_id, response={"threads": [{"isResolved": False}]})  # target_pr = "tvna/gitapex#1209"
    assert established is not None
    assert established["target_pr"] == "tvna/gitapex#1209"
    resolved = tracker.process({"session_id": session_id, "tool_name": "mcp__github__resolve_review_thread"})
    assert resolved is not None
    assert resolved["resolve_calls"] == 1

    # Same PR, same session, but this call's tool_input omits owner/repo.
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"pullNumber": 1209, "method": "get"},
            "tool_response": {"mergeable_state": "clean"},
        }
    )
    assert result is not None
    assert result["target_pr"] == "tvna/gitapex#1209"
    assert result["open_review_threads"] == 1  # NOT reset -- still the same PR
    assert result["resolve_calls"] == 1  # NOT reset -- still the same PR
    assert result["mergeable_checked"] is True


# --- MCP response-envelope unwrapping -------------------------------------


def test_unwrap_tool_response_bare_text_block_list() -> None:
    wrapped = [{"type": "text", "text": json.dumps({"threads": [{"isResolved": False}]})}]
    assert tracker._unwrap_tool_response(wrapped) == {"threads": [{"isResolved": False}]}


def test_unwrap_tool_response_content_string() -> None:
    wrapped = {"content": json.dumps({"mergeable_state": "clean"})}
    assert tracker._unwrap_tool_response(wrapped) == {"mergeable_state": "clean"}


def test_unwrap_tool_response_content_block_list() -> None:
    wrapped = {"content": [{"type": "text", "text": json.dumps([{"isResolved": False}])}]}
    assert tracker._unwrap_tool_response(wrapped) == [{"isResolved": False}]


def test_unwrap_tool_response_falls_back_unchanged() -> None:
    already_plain = [{"isResolved": False}]
    assert tracker._unwrap_tool_response(already_plain) == already_plain


def test_get_review_comments_through_text_block_envelope() -> None:
    session_id = "s15"
    _push(session_id)
    wrapped = [{"type": "text", "text": json.dumps({"threads": [{"isResolved": False}, {"isResolved": False}]})}]
    result = _read_pr(session_id, response=wrapped)
    assert result is not None
    assert result["open_review_threads"] == 2


def test_reports_error_recognizes_all_three_markers() -> None:
    assert tracker._reports_error({"status": "error"}) is True
    assert tracker._reports_error({"is_error": True}) is True
    assert tracker._reports_error({"isError": True}) is True
    assert tracker._reports_error({"status": "ok"}) is False
    assert tracker._reports_error("not a dict") is False


def test_unwrap_tool_response_skips_unparseable_block_and_tries_next() -> None:
    # Two text blocks, the first not valid JSON -- must fall through to the
    # second rather than stopping at the first candidate's parse failure.
    wrapped = [
        {"type": "text", "text": "not valid json{{{"},
        {"type": "text", "text": json.dumps({"mergeable_state": "clean"})},
    ]
    assert tracker._unwrap_tool_response(wrapped) == {"mergeable_state": "clean"}


def test_read_state_falls_back_to_default_on_non_dict_json() -> None:
    path = tracker.state_path("s17")
    path.write_text(json.dumps([1, 2, 3]))
    assert tracker._read_state(path) == dict(tracker._DEFAULT_STATE)


def test_contains_mergeable_state_handles_bare_list() -> None:
    assert tracker._contains_mergeable_state([{"other": "field"}, {"mergeable_state": "clean"}]) is True
    assert tracker._contains_mergeable_state([{"other": "field"}]) is False


def test_pull_request_read_without_pull_number_and_no_target_established_is_ignored() -> None:
    # Neither this call nor any earlier one can be attributed to a PR --
    # the stricter, fail-toward-more-tracking posture (module docstring)
    # is to not credit an unattributable read rather than optimistically
    # crediting it toward whichever PR turns out to matter later.
    session_id = "s16b"
    _push(session_id)
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get"},  # no owner/repo/pullNumber at all
            "tool_response": {"mergeable_state": "clean"},
        }
    )
    assert result is None
    state = tracker._read_state(tracker.state_path(session_id))
    assert state["target_pr"] is None
    assert state["mergeable_checked"] is False


def test_pull_request_read_without_pull_number_still_updates_established_target() -> None:
    # target_pr is already set from an earlier call; a later call that
    # simply omits pullNumber (call_pr is None, not "a different PR") must
    # not be treated as cross-PR and skipped -- it should still update.
    session_id = "s16"
    _push(session_id)
    _read_pr(session_id, response={"threads": [{"isResolved": False}]})  # establishes target_pr
    result = tracker.process(
        {
            "session_id": session_id,
            "tool_name": "mcp__github__pull_request_read",
            "tool_input": {"method": "get"},  # no owner/repo/pullNumber this time
            "tool_response": {"mergeable_state": "clean"},
        }
    )
    assert result is not None
    assert result["mergeable_checked"] is True


# --- main() CLI entry point -----------------------------------------------


def test_main_processes_valid_payload_and_writes_state(monkeypatch: Any) -> None:
    import io as _io

    payload = json.dumps({"session_id": "main-1", "tool_name": "Bash", "tool_input": {"command": "git push"}})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    exit_code = tracker.main()
    assert exit_code == 0
    state = json.loads(tracker.state_path("main-1").read_text())
    assert state["push_detected"] is True


def test_main_handles_invalid_json_payload(monkeypatch: Any, capsys: Any) -> None:
    import io as _io

    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(b"not json{{{")})())
    assert tracker.main() == 0
    # The .sh wrapper no longer pre-validates payload shape via jq (see its
    # own header) -- this systemMessage is now the only surviving signal.
    assert "systemMessage" in capsys.readouterr().out


def test_main_handles_non_object_payload(monkeypatch: Any, capsys: Any) -> None:
    import io as _io

    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(b"[1, 2, 3]")})())
    assert tracker.main() == 0
    assert "systemMessage" in capsys.readouterr().out


def test_main_suppresses_oserror_from_process(monkeypatch: Any) -> None:
    import io as _io

    def _raise_oserror(payload: dict[str, Any]) -> dict[str, Any] | None:
        raise OSError("disk full")

    monkeypatch.setattr(tracker, "process", _raise_oserror)
    payload = json.dumps({"session_id": "main-2", "tool_name": "Bash", "tool_input": {"command": "git push"}})
    monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": _io.BytesIO(payload.encode())})())
    assert tracker.main() == 0


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


def test_shell_exits_zero_when_python3_is_missing(tmp_path: Path) -> None:
    # New guard added when this wrapper's own jq dependency was removed
    # (see its header): python3 is now the one hard dependency, so its
    # absence must still fail OPEN with a systemMessage, never block.
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for tool in ("bash", "cat", "dirname", "pwd"):
        # cast(), not an `if source:` guard -- these are standard system
        # tools always present wherever this suite itself can run, so a
        # runtime None-check here would be a permanently-untaken branch,
        # not real robustness.
        (stub_bin / tool).symlink_to(cast(str, shutil.which(tool)))
    env = _env(tmp_path)
    env["PATH"] = str(stub_bin)
    result = _run({"session_id": "shell-no-python3", "tool_name": "Bash", "tool_input": {"command": "git push"}}, env)
    assert result.returncode == 0
    assert "python3 is not available on PATH" in result.stdout
    assert not (tmp_path / "gitapex-review-obligation-shell-no-python3.json").exists()

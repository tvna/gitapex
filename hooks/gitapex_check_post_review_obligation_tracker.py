#!/usr/bin/env python3
"""PostToolUse state writer backing the review-thread-resolution +
mergeable_state-verification obligation (issue #1209).

CLAUDE.md section 3 states a turn-terminal obligation: "After a fix push
that addresses a review thread, explicitly call
mcp__github__resolve_review_thread to resolve the thread; then verify
mergeable_state before closing the turn." Nothing backed this
deterministically -- hooks/hooks.json carried zero Stop entries, so the
obligation depended solely on the agent remembering it.

Design (settled on issue #1209, not guessed at implementation time): a
marker-file state machine. This script is the writer half, invoked as a
PostToolUse hook (matcher: Bash|mcp__github__resolve_review_thread|
mcp__github__pull_request_read); hooks/gitapex_check_stop_review_obligation.py
is the reader half, invoked as a Stop hook. Neither half makes its own
GitHub API call -- this script reads only what the already-executed tool
call itself returned (its own tool_response), reusing the pattern
hooks/gitapex_check_post_write_provenance.py already established (issue
#908: a PostToolUse hook's stdin payload does carry the tool's actual
result). The Stop hook in turn reads only this state file, never the
network -- see that module's own docstring for the full split.

State file: ``${TMPDIR:-/tmp}/gitapex-review-obligation-<session_id>.json``,
deliberately outside the git work tree (never pollutes `git status`) and
keyed by session_id (stdin's own `session_id` field) so concurrent
sessions in different repos/worktrees never collide. Session-scoped, not
durable: a restarted session loses in-flight tracking, a disclosed,
deliberately-accepted false-negative (the Stop hook goes silent, never
silently wrong) -- see issue #1209's own Acceptance Criteria Map residual
risk for the full reasoning against a git-tracked alternative.

Fields:
    push_detected: bool -- a git-push Bash call was classified this cycle.
    open_review_threads: int | None -- unresolved-thread count last
        observed from a get_review_comments response; None means "never
        observed this cycle," not "zero."
    resolve_calls: int -- how many times resolve_review_thread fired
        since the last push_detected reset.
    mergeable_checked: bool -- a pull_request_read(method="get") response
        carrying mergeable_state was observed since the last reset.

Three tool shapes update this file:

- Bash: reuses hooks/gitapex_check_bash_safety.py's own `classify()` --
  the same token-based, quote-splitting-resistant classifier
  hooks/check-bash-safety.sh already relies on for its own git-push
  provenance-scan gate -- rather than re-implementing git-push detection.
  `classify(command).is_git_push` true resets the state file to a fresh
  pending cycle (push_detected=true, everything else cleared).
- mcp__github__resolve_review_thread: increments resolve_calls. A no-op
  (never creates a state file) when push_detected has not fired yet this
  cycle -- resolving a thread outside a tracked push cycle is not this
  gate's concern.
- mcp__github__pull_request_read: dispatches on tool_input.method.
  get_review_comments records the unresolved-thread count, read directly
  out of the tool's own tool_response by recursively counting every dict
  carrying `isResolved: false` -- deliberately shape-tolerant (walks the
  whole response tree rather than assuming one fixed envelope), since the
  exact response envelope is the MCP server's own contract, not this
  repository's (the identical fragility issue #908 already named for
  hooks/gitapex_check_post_write_provenance.py's own URL-tail parsing).
  method get sets mergeable_checked when the response tree contains a
  `mergeable_state` key anywhere.

Fails OPEN on every error path (malformed payload, missing jq is handled
by the .sh wrapper, unwritable state dir, unreadable prior state) --
PostToolUse cannot block a tool call that already succeeded (Claude
Code's own hooks reference: "PostToolUse ... cannot block -- the tool
already executed successfully"), so there is nothing to gain by denying
here; the Stop hook's own fail-closed default is where an unverifiable
state gets treated as unresolved, not this half.

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"session_id":"abc","tool_name":"Bash","tool_input":{"command":"git push"}}' \\
        | python3 hooks/gitapex_check_post_review_obligation_tracker.py
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import gitapex_check_bash_safety as bash_safety

_DEFAULT_STATE: dict[str, Any] = {
    "push_detected": False,
    "open_review_threads": None,
    "resolve_calls": 0,
    "mergeable_checked": False,
}


def state_path(session_id: str) -> Path:
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id) or "unknown"
    # os.environ.get("TMPDIR") is read fresh on every call, unlike
    # tempfile.gettempdir(), which caches its result on first use for the
    # life of the process -- a test setting TMPDIR via monkeypatch after
    # some earlier, unrelated call already triggered that cache would
    # otherwise silently keep resolving to the original default dir.
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return Path(base) / f"gitapex-review-obligation-{safe_id}.json"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {**_DEFAULT_STATE, **data}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return dict(_DEFAULT_STATE)


def _write_state(path: Path, state: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(state), encoding="utf-8")
    tmp_path.replace(path)


def _count_unresolved_threads(node: Any) -> int:
    """Recursively count every dict in NODE carrying `isResolved: false`,
    tolerating any surrounding envelope shape (a bare list of threads, a
    `{"threads": [...]}` wrapper, a paginated `{"nodes": [...], "pageInfo":
    ...}` shape, or anything else) -- see module docstring."""
    count = 0
    if isinstance(node, dict):
        if node.get("isResolved") is False:
            count += 1
        for value in node.values():
            count += _count_unresolved_threads(value)
    elif isinstance(node, list):
        for item in node:
            count += _count_unresolved_threads(item)
    return count


def _contains_mergeable_state(node: Any) -> bool:
    if isinstance(node, dict):
        if "mergeable_state" in node or "mergeableState" in node:
            return True
        return any(_contains_mergeable_state(value) for value in node.values())
    if isinstance(node, list):
        return any(_contains_mergeable_state(item) for item in node)
    return False


def handle_bash(state: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return state
    verdict = bash_safety.classify(command)
    if not verdict.is_git_push:
        return state
    return {
        "push_detected": True,
        "open_review_threads": None,
        "resolve_calls": 0,
        "mergeable_checked": False,
    }


def handle_resolve_review_thread(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("push_detected"):
        return state
    return {**state, "resolve_calls": int(state.get("resolve_calls") or 0) + 1}


def handle_pull_request_read(state: dict[str, Any], tool_input: dict[str, Any], tool_response: Any) -> dict[str, Any]:
    if not state.get("push_detected"):
        return state
    method = tool_input.get("method")
    if method == "get_review_comments":
        return {**state, "open_review_threads": _count_unresolved_threads(tool_response)}
    if method == "get" and _contains_mergeable_state(tool_response):
        return {**state, "mergeable_checked": True}
    return state


def process(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the new state to persist, or None to leave the state file
    untouched (an irrelevant tool call, or push_detected not yet set for
    a resolve/read call)."""
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    path = state_path(session_id)
    state = _read_state(path)

    if tool_name == "Bash":
        new_state = handle_bash(state, tool_input)
    elif tool_name == "mcp__github__resolve_review_thread":
        new_state = handle_resolve_review_thread(state)
    elif tool_name == "mcp__github__pull_request_read":
        new_state = handle_pull_request_read(state, tool_input, payload.get("tool_response"))
    else:
        return None

    if new_state == state:
        return None
    _write_state(path, new_state)
    return new_state


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    # Fail open: PostToolUse cannot block an already-executed tool call,
    # and an unwritable state dir is the Stop hook's own fail-closed
    # default's problem to surface, not this half's.
    with contextlib.suppress(OSError):
        process(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

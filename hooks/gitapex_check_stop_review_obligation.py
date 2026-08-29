#!/usr/bin/env python3
"""Stop hook reader backing the review-thread-resolution +
mergeable_state-verification obligation (issue #1209).

See hooks/gitapex_check_post_review_obligation_tracker.py's own module
docstring for the full design (state file shape, why a marker file
instead of a transcript/GitHub-API correlation, the accepted residual
risks). This half only reads the state file that tracker writes as a
PostToolUse side effect -- it never calls the network itself, and it
never inspects the transcript.

Claude Code's Stop event supports no `matcher` (it fires unconditionally
on every turn end -- confirmed by reading code.claude.com/docs/en/hooks
directly rather than assumed), so the "only fire when relevant" filter
has to live in this script's own logic: the very first thing checked is
the state file's own `push_detected` flag, and an absent file or a false
flag exits 0 immediately, before anything PR-specific runs. This is the
mechanism behind issue #1209's own second Acceptance Criteria Map row
("must not regress a turn that never touched a review thread or a
push").

Blocking condition (exit 2 -- Claude Code's own Stop contract: "Prevents
Claude from stopping, continues the conversation"), only once
push_detected is true:

- open_review_threads is a known positive count and resolve_calls is
  still short of it, OR
- mergeable_checked is still false.

Both satisfied (or push_detected was never set) clears the state file and
exits 0.

No stop_hook_active-equivalent infinite-loop guard is implemented here --
deliberate, not an oversight: Claude Code's own hooks reference does not
document one, and issue #1209's own Constraints section says explicitly
not to guess a retry-cap design before live testing shows it is actually
needed. See that issue's Acceptance Criteria Map residual-risk column for
the full accounting of this accepted risk.

Fails CLOSED on an unreadable-but-present state file (malformed JSON,
unreadable permissions) -- matching this repository's general "fail
closed, including on INDETERMINATE" posture (see e.g.
hooks/gitapex_check_pr_issue_acm_disclosure.py's own docstring for the
precedent): a state file that exists but cannot be trusted is treated as
"an obligation might be outstanding," not "nothing to check." A genuinely
ABSENT file (the common case -- most turns never touch a PR at all) is
the one state this module treats as "nothing to verify," since absence
here is `gitapex_check_post_review_obligation_tracker.py`'s own default,
uncorrupted starting condition.

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"session_id":"abc"}' \\
        | python3 hooks/gitapex_check_stop_review_obligation.py
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from gitapex_check_post_review_obligation_tracker import state_path

_MISSING_STEPS_RESOLVE = (
    "call mcp__github__resolve_review_thread for the remaining open review thread(s) on the PR you just pushed to"
)
_MISSING_STEPS_MERGEABLE = (
    'call mcp__github__pull_request_read (method="get") to verify mergeable_state on the PR you just pushed to'
)


class StateUnreadable(Exception):
    """The state file exists but could not be parsed -- fail closed."""


def _load_state(path: Path) -> dict[str, Any] | None:
    """Return None when no obligation is being tracked (file absent),
    the parsed state dict, or raise StateUnreadable for a present-but-
    corrupt file (fail closed, per module docstring)."""
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise StateUnreadable(str(error)) from error
    if not isinstance(data, dict):
        raise StateUnreadable(f"state file is not a JSON object (got {type(data).__name__})")
    return data


def evaluate(state: dict[str, Any] | None) -> tuple[bool, str]:
    """Return (should_block, reason). reason is only meaningful when
    should_block is True."""
    if state is None or not state.get("push_detected"):
        return False, ""

    missing: list[str] = []
    open_threads = state.get("open_review_threads")
    resolve_calls = state.get("resolve_calls") or 0
    if isinstance(open_threads, int) and open_threads > 0 and resolve_calls < open_threads:
        missing.append(_MISSING_STEPS_RESOLVE)
    if not state.get("mergeable_checked"):
        missing.append(_MISSING_STEPS_MERGEABLE)

    if not missing:
        return False, ""
    return True, (
        "A fix push was detected this cycle, but the turn-terminal obligation from CLAUDE.md "
        "section 3 is not yet satisfied. Before closing the turn: " + "; and ".join(missing) + "."
    )


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        print(f"error: payload is not valid JSON ({error}). Failing closed.", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("error: payload is not a JSON object. Failing closed.", file=sys.stderr)
        return 1

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        # No session_id to key a state file by -- nothing was ever
        # trackable for this call, so there is nothing to verify.
        return 0

    path = state_path(session_id)
    try:
        state = _load_state(path)
    except StateUnreadable as error:
        print(f"error: state file at {path} could not be read ({error}). Failing closed.", file=sys.stderr)
        return 1

    should_block, reason = evaluate(state)
    if should_block:
        print(reason, file=sys.stderr)
        return 1

    if state is not None:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/bin/bash
# Stop hook: state-reader half of the marker-file state machine backing
# issue #1209's review-thread-resolution + mergeable_state-verification
# obligation (CLAUDE.md section 3: "After a fix push that addresses a
# review thread, explicitly call mcp__github__resolve_review_thread to
# resolve the thread; then verify mergeable_state before closing the
# turn.").
#
# No matcher: Claude Code's Stop event supports none (confirmed via
# code.claude.com/docs/en/hooks) -- it fires on every turn end
# unconditionally, so hooks/gitapex_check_stop_review_obligation.py's own
# push_detected check is what keeps an ordinary, PR-review-unrelated turn
# from ever being blocked.
#
# Delegates to hooks/gitapex_check_stop_review_obligation.py -- see that
# module's own docstring (and hooks/gitapex_check_post_review_obligation_tracker.py's,
# the writer half) for the full state-machine design and its disclosed
# residual risks (no infinite-loop circuit breaker in v1, session-scoped
# state only).
#
# Denies via the Stop hookSpecificOutput JSON on stdout AND exit 2 /
# stderr text (both conventions, matching this repository's existing
# PreToolUse deny() convention for defense in depth) when the obligation
# is outstanding. Fails closed on jq-missing/malformed-payload, matching
# every other fail-closed gate in this directory.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"hookEventName\": \"Stop\", \"decision\": \"block\", \"reason\": \"hooks/check-stop-review-obligation.sh: jq is not available on PATH -- cannot verify whether a review-thread-resolution/mergeable_state obligation is outstanding. Failing closed.\"}}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  # Piped via stdin (jq -Rs), not --arg -- same ARG_MAX-avoidance
  # rationale as every sibling deny() in this directory.
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": .}}' >&2
  exit 2
}

input=$(cat)

if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-stop-review-obligation.sh: the payload on stdin is not a JSON object. Failing closed."
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_stop_review_obligation.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-stop-review-obligation.sh: gitapex_check_stop_review_obligation.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

# $input is piped on stdin the whole way through, never re-passed as a
# command-line argument -- same ARG_MAX rationale as every sibling hook.
check_exit=0
check_output=$(printf '%s' "$input" | python3 "$check_script" 2>&1) || check_exit=$?

if [ "$check_exit" -eq 0 ]; then
  exit 0
fi

deny "$check_output"

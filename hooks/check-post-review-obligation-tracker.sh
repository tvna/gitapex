#!/bin/bash
# PostToolUse hook (matcher: Bash|mcp__github__resolve_review_thread|
# mcp__github__pull_request_read): state-writer half of the marker-file
# state machine backing issue #1209's review-thread-resolution +
# mergeable_state-verification obligation (CLAUDE.md section 3).
#
# Delegates to hooks/gitapex_check_post_review_obligation_tracker.py --
# see that module's own docstring for the full state-machine design.
# hooks/check-stop-review-obligation.sh (a Stop hook) is the reader half
# that actually blocks; this hook only ever writes state, never blocks.
#
# Always exits 0: PostToolUse cannot block a tool call that already
# executed successfully (Claude Code's own hooks reference), so every
# failure path here (missing jq, malformed payload, missing python3) is
# fail-open with a systemMessage warning -- matching
# hooks/check-post-write-provenance.sh's own convention for the same
# constraint.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"systemMessage\": \"hooks/check-post-review-obligation-tracker.sh could not run: jq is not available on PATH. Review-thread-resolution/mergeable_state tracking for this turn may be incomplete.\"}"
  exit 0
fi

warn() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs '{"systemMessage": .}'
  exit 0
}

input=$(cat)

if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  warn "hooks/check-post-review-obligation-tracker.sh: the tool-call payload on stdin is not a JSON object. Skipping this cycle's obligation tracking."
fi

if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  warn "hooks/check-post-review-obligation-tracker.sh: tool_name in the payload is not a string. Skipping this cycle's obligation tracking."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

case "$tool_name" in
  Bash | mcp__github__resolve_review_thread | mcp__github__pull_request_read) ;;
  *) exit 0 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tracker_script="$script_dir/gitapex_check_post_review_obligation_tracker.py"

if [ ! -f "$tracker_script" ]; then
  warn "hooks/check-post-review-obligation-tracker.sh: gitapex_check_post_review_obligation_tracker.py was not found at $tracker_script (corrupted or incomplete plugin bundle). Skipping this cycle's obligation tracking."
fi

# $input is piped on stdin the whole way through, never re-passed as a
# command-line argument -- same ARG_MAX rationale as every sibling hook
# in this directory.
if ! printf '%s' "$input" | python3 "$tracker_script" 2>/dev/null; then
  warn "hooks/check-post-review-obligation-tracker.sh: gitapex_check_post_review_obligation_tracker.py exited non-zero. Review-thread-resolution/mergeable_state tracking for this turn may be incomplete."
fi

exit 0

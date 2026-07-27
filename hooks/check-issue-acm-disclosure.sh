#!/bin/bash
# PreToolUse hook (matcher: mcp__github__issue_write) backing issue #413
# (sub-issue of #357, covering its first Acceptance Criteria Map row):
# block a new-issue-creation tool call whose body carries neither an
# Acceptance Criteria Map (ACM) table nor an explicit waiver line.
#
# Only fires when tool_input.method == "create" -- an "update" call edits
# an issue that already exists and is out of scope for this row.
#
# Reuses .github/scripts/gate_acm_issue_disclosure.py's own --check-only
# mode (no network calls, no side effects) instead of a fourth copy of the
# ACM-header/waiver regex: that script already carries the exact
# disclosure-or-`ACM: not-applicable (chore|docs|tracking): <reason>`
# vocabulary issue #357 names for this row, and
# tests/test_check_acm_present_sync.py already keeps its header regex in
# sync with the two skills/*/scripts/check_acm_present.py copies.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh).

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__issue_write, but never trust that alone.
if [ "$tool_name" != "mcp__github__issue_write" ]; then
  exit 0
fi

method=$(printf '%s' "$input" | jq -r '.tool_input.method // empty')

if [ "$method" != "create" ]; then
  exit 0
fi

body=$(printf '%s' "$input" | jq -r '.tool_input.body // empty')

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
check_script="$project_dir/.github/scripts/gate_acm_issue_disclosure.py"

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-issue-acm-disclosure.sh: cannot verify ACM disclosure -- gate_acm_issue_disclosure.py was not found at $check_script."
fi

if printf '%s' "$body" | python3 "$check_script" --check-only >/dev/null 2>&1; then
  exit 0
fi

deny "Blocked by hooks/check-issue-acm-disclosure.sh: this issue-creation call's body carries neither an Acceptance Criteria Map table nor an explicit waiver. Per drafting-an-acm-issue/SKILL.md (issue #357), add either the ACM table (skills/drafting-an-acm-issue/references/acceptance-criteria-map.md) or a 'ACM: not-applicable (chore|docs|tracking): <reason>' waiver line."

exit 0

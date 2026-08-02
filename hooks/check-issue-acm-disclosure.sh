#!/bin/bash
# PreToolUse hook (matcher: mcp__github__issue_write): block a
# new-issue-creation tool call whose body carries neither an Acceptance
# Criteria Map (ACM) table nor an explicit waiver line.
#
# Only fires when tool_input.method == "create" -- an "update" call edits
# an issue that already exists and is out of scope.
#
# Checks via hooks/check_acm_present_or_waiver.py, a self-contained sibling
# script bundled beside this hook (not .github/scripts/gate_acm_issue_disclosure.py
# -- per docs/repository-layout.md, only skills/ and hooks/ are deployed
# with the plugin, .github/ never is, so a CLAUDE_PROJECT_DIR-relative
# .github/ lookup always misses in an installed-plugin consumer checkout).
# Resolved relative to this script's own location so it travels with the
# hook regardless of CLAUDE_PROJECT_DIR/CLAUDE_PLUGIN_ROOT.
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

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/check_acm_present_or_waiver.py"

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-issue-acm-disclosure.sh: cannot verify ACM disclosure -- check_acm_present_or_waiver.py was not found at $check_script (corrupted or incomplete plugin bundle)."
fi

if printf '%s' "$body" | python3 "$check_script" >/dev/null 2>&1; then
  exit 0
fi

deny "Blocked by hooks/check-issue-acm-disclosure.sh: this issue-creation call's body carries neither an Acceptance Criteria Map table nor an explicit waiver. Per drafting-an-acm-issue/SKILL.md (issue #357), add either the ACM table (skills/drafting-an-acm-issue/references/acceptance-criteria-map.md) or a 'ACM: not-applicable (chore|docs|tracking|defect): <reason>' waiver line."

exit 0

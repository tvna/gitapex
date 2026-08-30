#!/bin/bash
# SubagentStop hook, scoped to the executing-a-branch-plan skill's
# task-level subagent type (.claude/agents/branch-plan-task.md's embedded
# `hooks.SubagentStop` block) -- backs design doc Decision 20
# (docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md),
# issue #1476 (retro #1475 repair 2): a task-level dispatch must run the
# full repo verification suite (pytest plus every deterministic
# shape/gate checker) inside its own isolated worktree as an exit
# condition before it is allowed to report complete -- not deferred
# solely to the main thread's own merge-back screening step.
#
# Self-contained duplicate, not a shared import: this repository's
# convention (see check_task_bash_safety.sh's own header, and
# skills/drafting-issues/scripts/gitapex_check_acm_present.py's docstring)
# is that no skill shares a scripts/ directory with another. This script
# adapts check_task_bash_safety.sh's own wrapper structure rather than
# re-deriving it -- same jq-based JSON handling, same fail-closed
# defaults -- adapted for the SubagentStop event's own input/output shape
# instead of PreToolUse's.
#
# The actual verification-running logic lives in
# gitapex_check_task_full_verification.py, a thin bash+jq wrapper around
# it -- see that sibling module's own docstring for the full accounting.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"hookEventName\": \"SubagentStop\", \"decision\": \"continue\", \"reason\": \"Blocked by executing-a-branch-plan's task-agent full-verification gate: jq is not available on PATH -- cannot verify the SubagentStop payload. Failing closed.\"}}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"hookEventName": "SubagentStop", "decision": "continue", "reason": .}}' >&2
  exit 2
}

input=$(cat)

if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: the hook payload on stdin is not a JSON object. Failing closed."
fi

if ! printf '%s' "$input" | jq -e '(.hook_event_name == null) or (.hook_event_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: hook_event_name in the payload is not a string. Failing closed."
fi

hook_event_name=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')

# Defense in depth: the subagent frontmatter's own SubagentStop
# registration already restricts this hook to that one event, but never
# trust that alone.
if [ "$hook_event_name" != "SubagentStop" ]; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
classifier="$script_dir/gitapex_check_task_full_verification.py"

if [ ! -f "$classifier" ]; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: gitapex_check_task_full_verification.py was not found at $classifier (corrupted or incomplete plugin bundle). Failing closed."
fi

classifier_exit=0
# python3's own stderr (e.g. a "command not found" launch failure) is
# discarded, not left to leak into this hook's own stderr channel -- see
# hooks/check-bash-safety.sh's identical rationale.
classifier_output=$(printf '%s' "$input" | python3 "$classifier" 2>/dev/null) || classifier_exit=$?
if [ "$classifier_exit" -ne 0 ]; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: gitapex_check_task_full_verification.py exited non-zero ($classifier_exit) instead of returning a decision. Failing closed."
fi

if ! printf '%s' "$classifier_output" | jq -e 'type == "object"' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: gitapex_check_task_full_verification.py did not return a JSON object. Failing closed."
fi

decision=$(printf '%s' "$classifier_output" | jq -r '.decision // empty')
reason=$(printf '%s' "$classifier_output" | jq -r '.reason // empty')

if [ "$decision" = "deny" ]; then
  deny "$reason"
fi

if [ "$decision" != "allow" ]; then
  deny "Blocked by executing-a-branch-plan's task-agent full-verification gate: gitapex_check_task_full_verification.py returned an unrecognized decision '$decision'. Failing closed."
fi

exit 0

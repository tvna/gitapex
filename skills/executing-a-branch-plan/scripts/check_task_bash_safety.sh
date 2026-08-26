#!/bin/bash
# PreToolUse hook, scoped to the executing-a-branch-plan skill's
# task-level subagent type (.claude/agents/branch-plan-task.md's
# embedded `hooks.PreToolUse` block, matcher "Bash") -- backs design doc
# Decision 17 (docs/superpowers/specs/2026-07-22-plan-execution-handoff-
# design.md): the deterministic backstop for Decision 7's exclusion list
# (task agents never run git push, the gh CLI, or a package-manager
# install command), independent of Decision 7's still-open question of
# whether hooks/check-bash-safety.sh binds inside a subagent context.
#
# Self-contained duplicate, not a shared import: this repository's
# convention (see skills/*/scripts/gitapex_check_acm_present.py's docstring) is
# that no skill shares a scripts/ directory with another. This script
# adapts hooks/check-bash-safety.sh's own wrapper structure rather than
# re-deriving it, but is intentionally stricter in the ways
# gitapex_check_task_bash_safety.py's own module docstring states in full
# (gh denied entirely, git push a hard deny, plus additional install-verb
# coverage that script's own predecessor never carried).
#
# Issue #1326 (Stage 1): the actual command-classification logic moved to
# gitapex_check_task_bash_safety.py, a token-based classifier (shlex,
# stdlib-only) adapted from hooks/gitapex_check_bash_safety.py -- see that
# sibling module's own docstring for the full root-cause analysis this
# script's predecessor shared. This script is now a thin bash+jq wrapper.
#
# Known ceiling, disclosed in gitapex_check_task_bash_safety.py's own module
# docstring (dimension 9): verb-token-splitting via string-slice
# reconstruction or array-literal-assignment indirection -- neither of
# which places the tool/verb name as its own literal token anywhere in
# the command -- still evades Stage 1. Obfuscation that hides the verb
# entirely via an external fetch (base64-piped-to-sh where the payload
# itself is fetched, not embedded) remains out of reach of any
# token-based gate for the same reason, tracked as an open follow-up
# (specific to this repository, not portable).

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by executing-a-branch-plan's task-agent Bash gate: jq is not available on PATH -- cannot verify the Bash command. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the subagent frontmatter's matcher already restricts
# this hook to Bash, but never trust that alone.
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
classifier="$script_dir/gitapex_check_task_bash_safety.py"

if [ ! -f "$classifier" ]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: gitapex_check_task_bash_safety.py was not found at $classifier (corrupted or incomplete plugin bundle). Failing closed."
fi

classifier_exit=0
# python3's own stderr (e.g. a "command not found" launch failure) is
# discarded, not left to leak into this hook's own stderr channel -- see
# hooks/check-bash-safety.sh's identical rationale.
classifier_output=$(printf '%s' "$input" | python3 "$classifier" 2>/dev/null) || classifier_exit=$?
if [ "$classifier_exit" -ne 0 ]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: gitapex_check_task_bash_safety.py exited non-zero ($classifier_exit) instead of returning a decision. Failing closed."
fi

if ! printf '%s' "$classifier_output" | jq -e 'type == "object"' >/dev/null 2>&1; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: gitapex_check_task_bash_safety.py did not return a JSON object. Failing closed."
fi

decision=$(printf '%s' "$classifier_output" | jq -r '.decision // empty')
reason=$(printf '%s' "$classifier_output" | jq -r '.reason // empty')

if [ "$decision" = "deny" ]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): $reason."
fi

if [ "$decision" != "allow" ]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate: gitapex_check_task_bash_safety.py returned an unrecognized decision '$decision'. Failing closed."
fi

exit 0

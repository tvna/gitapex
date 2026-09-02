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
#
# Issue #1508 (consolidated into #1566's own gate-preconditions-mechanism
# umbrella): this script also chains gitapex_check_task_worktree_base.py
# as a second sibling classifier call, run once per Bash call alongside
# gitapex_check_task_bash_safety.py above -- a worktree-base precondition
# backstop (does this task's own worktree fork point still match the
# shared plan branch's current tip?), not a Bash-command classifier, but
# wired the identical way since no second hooks.PreToolUse frontmatter
# entry exists in .claude/agents/branch-plan-task.md to hang it off
# instead (confirmed by reading that file directly before adding this --
# it defines exactly one PreToolUse entry, matcher "Bash", one command
# hook; the established convention for a second PreToolUse-scoped check is
# chaining another sibling script call inside THIS shell wrapper, not a
# second frontmatter entry). Deliberately asymmetric from the classifier
# above: that one fails CLOSED (deny) on any malformed input or
# classification uncertainty; the worktree-base check fails OPEN on
# everything except a clean, confirmed mismatch -- see
# gitapex_check_task_worktree_base.py's own module docstring for the full
# fail-open/fail-closed rationale, and
# references/threat-model-and-authorization.md for the disclosed residual
# this asymmetry carries (piggybacks on the task's own first Bash call,
# not a true "before any tool call" gate).

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

# Issue #1508: worktree-base precondition backstop, checked BEFORE the
# Bash-command classification below -- a stale worktree fork point is a
# more foundational problem than whether this one command is itself safe.
# Deliberately fail-open on anything short of a clean, confirmed mismatch
# (see gitapex_check_task_worktree_base.py's own module docstring for the
# full rationale): a missing file, a non-zero exit, malformed/non-object
# output, or a "warn"/"allow" decision are ALL treated identically here --
# silently proceed to the Bash-safety classifier below. This is the ONLY
# path in this script that fails open on a classifier malfunction;
# gitapex_check_task_bash_safety.py's own call further down keeps this
# script's pre-existing fail-CLOSED default for every other outcome, since
# THAT classifier's job (preventing git push/gh/install commands) is
# higher-consequence than this one (a repo-state freshness backstop for
# the wave-dispatch case specifically, per this task's own Planned ops).
worktree_base_classifier="$script_dir/gitapex_check_task_worktree_base.py"
if [ -f "$worktree_base_classifier" ]; then
  worktree_base_exit=0
  worktree_base_output=$(printf '%s' "$input" | python3 "$worktree_base_classifier" 2>/dev/null) || worktree_base_exit=$?
  if [ "$worktree_base_exit" -eq 0 ] && printf '%s' "$worktree_base_output" | jq -e 'type == "object"' >/dev/null 2>&1; then
    worktree_base_decision=$(printf '%s' "$worktree_base_output" | jq -r '.decision // empty')
    if [ "$worktree_base_decision" = "deny" ]; then
      worktree_base_reason=$(printf '%s' "$worktree_base_output" | jq -r '.reason // empty')
      deny "Blocked by executing-a-branch-plan's task-agent worktree-base precondition (issue #1508): $worktree_base_reason."
    fi
  fi
fi

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

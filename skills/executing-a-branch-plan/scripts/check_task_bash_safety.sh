#!/bin/bash
# PreToolUse hook, scoped to the executing-a-branch-plan skill's own
# task-level subagent type (.claude/agents/branch-plan-task.md's own
# embedded `hooks.PreToolUse` block, matcher "Bash") -- backs design doc
# Decision 17 (docs/superpowers/specs/2026-07-22-plan-execution-handoff-
# design.md): the deterministic backstop for Decision 7's exclusion list
# (task agents never run git push, the gh CLI, or a package-manager
# install command), independent of Decision 7's own still-open question
# of whether hooks/check-bash-safety.sh binds inside a subagent context.
#
# Self-contained duplicate, not a shared import: this repository's own
# convention (see skills/*/scripts/check_acm_present.py's own docstring)
# is that no skill shares a scripts/ directory with another. This script
# adapts hooks/check-bash-safety.sh's own command-boundary regex and
# install-verb pattern (Finding 1) rather than re-deriving them, but is
# intentionally stricter in two ways a task-agent context requires:
#   - `gh` is denied entirely (any subcommand, including reads) -- design
#     doc Decision 7 states task agents "never touch mcp__github__* write
#     tools, `gh`, or `git push` directly," not just gh's write
#     subcommands, unlike hooks/check-bash-safety.sh's own narrower
#     write-subcommand-only gh gate (which is correct for its own
#     main-thread scope, where read-only gh use is not itself forbidden).
#   - `git push` is a hard deny here, not hooks/check-bash-safety.sh's own
#     warn-only outward-artifact-preflight gate -- a task agent has no
#     legitimate reason to push at all (design doc Decision 13: worktree
#     merge-back is a main-thread-only step).
#
# If the ACM table's header row or a shared pattern ever changes shape,
# update both copies together -- nothing enforces they stay in sync
# automatically (same caveat check_acm_present.py's own docstring states).

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the subagent frontmatter's own matcher already
# restricts this hook to Bash, but never trust that alone.
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

if [ -z "$command" ]; then
  exit 0
fi

lc_command=$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

# Shared boundary: pre-command anchor that also swallows an absolute or
# relative path prefix, matching hooks/check-bash-safety.sh's own
# cmd_boundary exactly (same rationale: closes the shell-indirection
# bypass class -- `bash -c "pip install x"`, `eval 'gh pr merge 1'` --
# in one negated command-token class rather than chasing each wrapper).
cmd_boundary='(^|[^[:alnum:]_.-])([[:alnum:]_.-]*/)*'

# --- Package/plugin install verbs (adapted from hooks/check-bash-safety.sh
# Finding 1 verbatim) --------------------------------------------------
install_re="${cmd_boundary}(pip3?[[:space:]]+install|npm[[:space:]]+install|npm[[:space:]]+i|yarn[[:space:]]+add|pnpm[[:space:]]+add|go[[:space:]]+install|brew[[:space:]]+install|apt(-get)?[[:space:]]+install|gem[[:space:]]+install|cargo[[:space:]]+install|uv[[:space:]]+pip[[:space:]]+install|uv[[:space:]]+install|uv[[:space:]]+add|plugin[[:space:]]+install)([[:space:]]|\$)"

if [[ "$lc_command" =~ $install_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): package/plugin install commands are not permitted inside a task-level agent. Edit the manifest file's text only; the actual install runs as its own main-thread step, after Decision 6 screening (design doc Decision 7)."
fi

# --- gh CLI: denied entirely, any subcommand ---------------------------
gh_re="${cmd_boundary}gh([[:space:]]|\$)"

if [[ "$lc_command" =~ $gh_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): the gh CLI is not permitted inside a task-level agent, read or write. GitHub reads/writes happen in the orchestrating skill's own main thread (design doc Decision 7)."
fi

# --- git push: hard deny, no warn-only exception ------------------------
push_re="${cmd_boundary}git[[:space:]]+push([[:space:]]|\$)"

if [[ "$lc_command" =~ $push_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): git push is not permitted inside a task-level agent. Worktree merge-back and branch publish are main-thread-only steps (design doc Decision 13)."
fi

exit 0

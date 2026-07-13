#!/bin/bash
# PreToolUse hook (matcher: Bash) backing 3 approved Major findings from
# docs/superpowers/reports/2026-07-13-skill-gap-triage.md:
#
#   1. [evaluating-skill-quality] SKILL.md -- block package/plugin install
#      commands run via Bash.
#   2. [issue-to-branch] SKILL.md -- block enabling auto-merge (a subset of
#      the `gh pr merge` deny rule below; --auto is not special-cased).
#   3. [issue-to-branch] references/github-issue-workflow.md -- block direct
#      CLI GitHub write commands (gh issue/pr create|edit|close|comment|merge,
#      gh api -X POST/PUT/PATCH/DELETE).
#   4. [outward-artifact-preflight] SKILL.md -- before `git push`, run
#      scan_provenance.py against the outgoing commits and block the push if
#      it flags anything.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-bash.sh).

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# Bash, but never trust that alone.
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

# --- Finding 1: package/plugin install verbs -------------------------------
# Case-insensitive, word/space-boundary anchored so `pipx install`, a path
# containing "install", or `cargo install-update` do not false-positive.
# Each alternative ends exactly at the verb/subcommand token (no baked-in
# trailing boundary of its own) so the single outer ([[:space:]]|$) suffix
# applies uniformly -- duplicating it per-alternative previously caused
# `npm i <pkg>` to be missed (the inner match already consumed the boundary
# before the pkg name, leaving nothing for the outer check to see).
install_re='(^|[[:space:];&|]+)(pip3?[[:space:]]+install|npm[[:space:]]+install|npm[[:space:]]+i|yarn[[:space:]]+add|pnpm[[:space:]]+add|go[[:space:]]+install|brew[[:space:]]+install|apt(-get)?[[:space:]]+install|gem[[:space:]]+install|cargo[[:space:]]+install|uv[[:space:]]+pip[[:space:]]+install|uv[[:space:]]+install|uv[[:space:]]+add|plugin[[:space:]]+install)([[:space:]]|$)'

if [[ "$lc_command" =~ $install_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: command matches a package/plugin install pattern. Per evaluating-skill-quality/SKILL.md's stop boundary, installs require the operator's explicit go-ahead -- propose the install instead of running it."
fi

# --- Findings 2 & 3: direct CLI GitHub write commands ----------------------
gh_issue_re='(^|[[:space:];&|]+)gh[[:space:]]+issue[[:space:]]+(create|edit|close|comment)([[:space:]]|$)'
gh_pr_re='(^|[[:space:];&|]+)gh[[:space:]]+pr[[:space:]]+(create|edit|close|comment|merge)([[:space:]]|$)'
gh_api_re='(^|[[:space:];&|]+)gh[[:space:]]+api([[:space:]]|$)'
gh_api_write_method_re='(-x|--method)[[:space:]]+(post|put|patch|delete)([[:space:]]|$)'

if [[ "$lc_command" =~ $gh_issue_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: direct 'gh issue' write command. Per issue-to-branch/references/github-issue-workflow.md, prefer the platform-integrated tool call (connected GitHub app/MCP) instead of shelling out to the gh CLI for writes."
fi

if [[ "$lc_command" =~ $gh_pr_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: direct 'gh pr' write command (create/edit/close/comment/merge, including auto-merge via 'gh pr merge --auto'). Per issue-to-branch/SKILL.md and references/github-issue-workflow.md, merging (including enabling auto-merge) and other PR writes are a separate, explicit human or CI decision -- use the platform-integrated tool call instead of the gh CLI."
fi

if [[ "$lc_command" =~ $gh_api_re ]] && [[ "$lc_command" =~ $gh_api_write_method_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE). Per issue-to-branch/references/github-issue-workflow.md, never shell out to a command-line GitHub tool directly for writes -- use the platform-integrated tool call or an approved read-only wrapper."
fi

# --- Finding 4: git push gated on scan_provenance.py -----------------------
push_re='(^|[[:space:];&|]+)git[[:space:]]+push([[:space:]]|$)'

if [[ "$lc_command" =~ $push_re ]]; then
  project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  scan_script="$project_dir/skills/outward-artifact-preflight/scripts/scan_provenance.py"

  if [ ! -f "$scan_script" ]; then
    deny "Blocked by hooks/check-bash-safety.sh: git push requires the outward-artifact-preflight scan, but scan_provenance.py was not found at $scan_script."
  fi

  content=$(git -C "$project_dir" log --format=%B -p @{u}..HEAD 2>/dev/null || true)
  if [ -z "$content" ]; then
    content=$(git -C "$project_dir" log --format=%B -p -1 HEAD 2>/dev/null || true)
  fi

  scan_exit=0
  scan_output=$(printf '%s' "$content" | python3 "$scan_script" 2>&1) || scan_exit=$?

  if [ "$scan_exit" -ne 0 ]; then
    deny "Blocked by hooks/check-bash-safety.sh: outward-artifact-preflight scan_provenance.py flagged the outgoing push -- $scan_output"
  fi
fi

exit 0

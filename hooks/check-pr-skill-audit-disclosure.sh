#!/bin/bash
# PreToolUse hook (matchers: mcp__github__create_pull_request,
# mcp__github__update_pull_request) backing issue #517 (refs #285, #300):
# block a PR-body-carrying call whose diff adds/modifies a
# skills/*/SKILL.md but whose body does not disclose both
# battle-testing-a-skill and evaluating-skill-quality audit evidence (or
# an explicit waiver for each).
#
# Applicability is computed locally via git, mirroring (a reduced form
# of) .github/workflows/skill-audit-gate.yml's own three-dot diff +
# D/R100 exclusion. Unlike that CI workflow, this hook has no
# github.event.pull_request.base.sha to anchor on -- it resolves the PR's
# base branch from tool_input.base when present (create_pull_request
# always supplies it; update_pull_request only when changing the base),
# falling back to the repo's own default branch (origin/HEAD) otherwise.
# If that resolution, or the git diff itself, fails for any reason (base
# ref not fetched locally, detached HEAD, etc.), this hook fails OPEN
# (exit 0, warning to stderr) rather than blocking on inconclusive local
# git state -- CI's skill-audit-gate.yml remains the deterministic,
# always-correct backstop regardless of what this hook can determine
# locally.
#
# Only checks the base two-audit disclosure via the self-contained
# check_skill_audit_disclosure_or_waiver.py sibling bundled beside this
# hook (not .github/scripts/gate_skill_audit_disclosure.py -- per
# docs/repository-layout.md, only skills/ and hooks/ are deployed with
# the plugin, .github/ never is; see that sibling script's own docstring,
# and hooks/check-issue-acm-disclosure.sh's docstring for the PR #433
# precedent this follows). Does not attempt the issue #427/#454/#277
# conditional extensions (WAIVED-rejection on description change,
# eval-coverage, security-relevance, design-doc coverage) -- those need
# git-diff-computed facts this hook does not compute; CI covers them.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh), same as
# hooks/check-issue-acm-disclosure.sh.

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matchers already restrict this hook to
# these two tools, but never trust that alone.
case "$tool_name" in
  mcp__github__create_pull_request|mcp__github__update_pull_request) ;;
  *) exit 0 ;;
esac

body=$(printf '%s' "$input" | jq -r '.tool_input.body // empty')

# An update_pull_request call that isn't setting a body has nothing new
# to check locally.
if [ -z "$body" ]; then
  exit 0
fi

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/check_skill_audit_disclosure_or_waiver.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: cannot verify skill audit disclosure -- check_skill_audit_disclosure_or_waiver.py was not found at $check_script (corrupted or incomplete plugin bundle)."
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

base_branch=$(printf '%s' "$input" | jq -r '.tool_input.base // empty')
if [ -z "$base_branch" ]; then
  base_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed -E 's#^origin/##') || true
fi

if [ -z "$base_branch" ]; then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not resolve a base branch locally; skipping the local pre-check (CI's skill-audit-gate.yml will still catch this)." >&2
  exit 0
fi

if ! merge_base=$(git merge-base "origin/${base_branch}" HEAD 2>/dev/null); then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not resolve origin/${base_branch} locally (not fetched?); skipping the local pre-check (CI's skill-audit-gate.yml will still catch this)." >&2
  exit 0
fi

if ! diff_output=$(git diff --name-status "${merge_base}...HEAD" -- 'skills/*/SKILL.md' 2>/dev/null); then
  exit 0
fi
changed=$(printf '%s\n' "$diff_output" | grep -vE '^(D|R100)[[:space:]]' || true)

if [ -z "$changed" ]; then
  exit 0
fi

if printf '%s' "$body" | python3 "$check_script" >/dev/null 2>&1; then
  exit 0
fi

deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: this PR's diff adds/modifies a skills/*/SKILL.md but its body does not disclose both battle-testing-a-skill and evaluating-skill-quality audit evidence (a verdict or waiver for each). Add a '## Skill audit evidence' section -- see .github/scripts/gate_skill_audit_disclosure.py for the exact format CI enforces."

exit 0

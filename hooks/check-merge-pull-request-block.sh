#!/bin/bash
# PreToolUse hook (matcher: mcp__github__merge_pull_request): unconditional
# deny. This repository's own policy -- stated in
# planning-a-branch-from-an-issue/SKILL.md ("Do not merge or enable
# auto-merge; that is a separate, explicit human or CI decision, never this
# skill's call to make"), drafting-a-pr-to-merge/SKILL.md step 8, and the
# ranking-the-open-queue Routine specs' "100% human review of any pull
# request merge in this repository is a permanent feature, not a stopgap"
# -- is that no agent tool call ever merges a PR in this repository, with no
# override. hooks/check-bash-safety.sh already blocks the equivalent shell
# form (`gh pr merge`, including `--auto`); this hook closes the identical
# gap for the platform-integrated MCP tool call, which that shell-only hook
# cannot see.
#
# Unlike hooks/check-issue-acm-disclosure.sh or
# hooks/check-pr-skill-audit-disclosure.sh, there is no PR-body field to
# inspect and no legitimate agent-side exception to check for -- merging is
# categorically a human/CI decision, so this hook denies every call
# unconditionally rather than conditioning on tool_input content.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh), same as
# hooks/check-issue-acm-disclosure.sh.

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__merge_pull_request, but never trust that alone.
if [ "$tool_name" != "mcp__github__merge_pull_request" ]; then
  exit 0
fi

deny_msg='Blocked by hooks/check-merge-pull-request-block.sh: mcp__github__merge_pull_request is never a valid agent action in this repository, no override. Per planning-a-branch-from-an-issue/SKILL.md, drafting-a-pr-to-merge/SKILL.md, and the ranking-the-open-queue Routine specs'"'"' "100% human review of any pull request merge" policy, merging a PR is always a separate, explicit human or CI decision. hooks/check-bash-safety.sh already blocks the equivalent "gh pr merge" shell command; this hook blocks the platform-integrated tool-call form the same way.'

jq -n --arg msg "$deny_msg" \
  '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
exit 2

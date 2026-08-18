#!/bin/bash
# PreToolUse hook (matcher: mcp__github__merge_pull_request): unconditional
# deny. This repository's own policy -- stated in
# planning-a-branch-from-an-issue/SKILL.md ("Do not merge or enable
# auto-merge; that is a separate, explicit human or CI decision, never this
# skill's call to make"), drafting-a-pr-to-merge/SKILL.md step 9, and the
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

# Issue #1208: per the audit that found this, "the repository's most
# categorical deny ('no override') does not fire in an environment without
# jq" -- this deny path must not itself depend on jq. If jq is missing from
# PATH entirely, every jq call below would crash under `set -e` with exit
# 127 ("command not found"), an exit code Claude Code's PreToolUse contract
# treats as non-blocking (mcp__github__merge_pull_request would proceed
# unchecked). Checked first, via a fixed, statically-escaped JSON literal
# (no interpolation, so no JSON-escaping risk), same pattern as
# hooks/check-pr-issue-acm-disclosure.sh's own jq-missing guard.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-merge-pull-request-block.sh: jq is not available on PATH -- cannot verify the tool-call payload, and mcp__github__merge_pull_request is never a valid agent action in this repository regardless. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  # Piped via stdin (jq -Rs: raw input, slurped to one string), not
  # `--arg` -- same ARG_MAX-avoidance reason as
  # hooks/check-pr-issue-acm-disclosure.sh's own deny().
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

# Issue #1208: a malformed payload (invalid JSON, or valid JSON that isn't
# an object) would otherwise make the `.tool_name` extraction below exit
# non-zero, crashing past deny() under `set -e` with an exit code Claude
# Code's PreToolUse contract treats as non-blocking -- the same fail-open
# class hooks/check-pr-issue-acm-disclosure.sh's own adversarial review
# found and fixed. This hook's own "no override" categorical deny is the
# highest-priority target in issue #1208, so an unparseable payload here
# fails closed too, rather than falling through on an indeterminate
# tool_name: this hook cannot tell whether an unparseable payload is in
# fact a disguised mcp__github__merge_pull_request call, and the
# repository's fail-closed-on-INDETERMINATE posture answers that
# uncertainty with deny, not allow.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-merge-pull-request-block.sh: the tool-call payload on stdin is not a JSON object, and mcp__github__merge_pull_request is never a valid agent action in this repository regardless. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__merge_pull_request, but never trust that alone.
if [ "$tool_name" != "mcp__github__merge_pull_request" ]; then
  exit 0
fi

deny "Blocked by hooks/check-merge-pull-request-block.sh: mcp__github__merge_pull_request is never a valid agent action in this repository, no override. Per planning-a-branch-from-an-issue/SKILL.md, drafting-a-pr-to-merge/SKILL.md, and the ranking-the-open-queue Routine specs' \"100% human review of any pull request merge\" policy, merging a PR is always a separate, explicit human or CI decision. hooks/check-bash-safety.sh already blocks the equivalent \"gh pr merge\" shell command; this hook blocks the platform-integrated tool-call form the same way."

#!/bin/bash
# PreToolUse hook (matcher: mcp__github__create_pull_request): blocks
# opening a PR whose Closes/Fixes-cited issue(s) lack an Acceptance
# Criteria Map (ACM) table or a valid, non-'tracking' waiver, or are
# already closed -- and blocks a PR that cites no issue at all.
#
# Issue #657: hooks/check-issue-acm-disclosure.sh already guards issue
# *creation*; nothing guarded the PR side, so a PR could be opened
# against an issue that never carried an ACM/waiver at all (pre-hook
# issues, web-UI-created issues, and fixing-a-reported-issue's bare
# defect issues specifically). This hook closes that gap.
#
# Checks via hooks/check_pr_issue_acm_disclosure.py, a self-contained
# sibling script bundled beside this hook (not .github/scripts/ --
# per docs/repository-layout.md, only skills/ and hooks/ are deployed
# with the plugin). That script itself reuses hooks/check_acm_present_or_waiver.py
# directly for the ACM/waiver text check (same directory, plain Python
# import) rather than a fifth duplicate copy of that regex logic.
# Resolved relative to this script's own location so it travels with the
# hook regardless of CLAUDE_PROJECT_DIR/CLAUDE_PLUGIN_ROOT.
#
# This is the first hook in this repository requiring a live GitHub API
# call (every prior ACM-family hook is stdlib-only, no network). It
# fails CLOSED (deny) when it cannot verify a Closes/Fixes-cited issue's
# ACM/waiver state -- no GH_TOKEN/GITHUB_TOKEN in the environment, or the
# GitHub API call fails after retries -- matching this repository's
# general "fail closed, including on INDETERMINATE" posture. Named
# trade-off: this blocks all PR creation during a transient GitHub API
# outage; see hooks/check_pr_issue_acm_disclosure.py's own docstring and
# this PR's own body for the full rationale, not left implicit here.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh), same as
# hooks/check-issue-acm-disclosure.sh and hooks/check-pr-skill-audit-disclosure.sh.

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__create_pull_request, but never trust that alone.
if [ "$tool_name" != "mcp__github__create_pull_request" ]; then
  exit 0
fi

owner=$(printf '%s' "$input" | jq -r '.tool_input.owner // empty')
repo=$(printf '%s' "$input" | jq -r '.tool_input.repo // empty')
title=$(printf '%s' "$input" | jq -r '.tool_input.title // empty')
body=$(printf '%s' "$input" | jq -r '.tool_input.body // empty')

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/check_pr_issue_acm_disclosure.py"

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: cannot verify the cited issue's ACM/waiver disclosure -- check_pr_issue_acm_disclosure.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

payload=$(jq -n --arg owner "$owner" --arg repo "$repo" --arg title "$title" --arg body "$body" \
  '{owner: $owner, repo: $repo, title: $title, body: $body}')

if check_output=$(printf '%s' "$payload" | python3 "$check_script" 2>&1); then
  check_exit=0
else
  check_exit=$?
fi

if [ "$check_exit" -eq 0 ]; then
  exit 0
fi

if printf '%s' "$check_output" | grep -q '^FAIL:'; then
  reason=$(printf '%s' "$check_output" | sed -n 's/^FAIL: //p')
  deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh (issue #657): $reason (see drafting-an-acm-issue/SKILL.md's Issue<->PR ACM contract)."
fi

# check_pr_issue_acm_disclosure.py only ever exits 0 (PASS) or 1 with a
# 'FAIL: ...' stderr message for a genuine disclosure failure -- anything
# else (a different exit code, or exit 1 with no 'FAIL:' line, e.g. an
# uncaught traceback) means the check script itself crashed, not a
# verdict on the PR. Denying either way is still the safe default (an
# unverifiable citation should not silently pass), but the message must
# say so plainly rather than blame the PR for a bug in the check script.
deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: check_pr_issue_acm_disclosure.py exited $check_exit without a recognized FAIL message -- this looks like a bug in the check script itself, not a genuine disclosure failure in the cited issue(s). Failing closed. Output: $check_output"

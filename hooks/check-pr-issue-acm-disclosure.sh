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
# Checks via hooks/gitapex_check_pr_issue_acm_disclosure.py, a self-contained
# sibling script bundled beside this hook (not .github/scripts/ --
# per docs/repository-layout.md, only skills/ and hooks/ are deployed
# with the plugin). That script itself reuses hooks/gitapex_check_acm_present_or_waiver.py
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
# outage; see hooks/gitapex_check_pr_issue_acm_disclosure.py's own docstring and
# this PR's own body for the full rationale, not left implicit here.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh), same as
# hooks/check-issue-acm-disclosure.sh and hooks/check-pr-skill-audit-disclosure.sh.

set -euo pipefail

# A third round of issue #657's own adversarial review found deny() itself
# depends on jq to construct its JSON output -- if jq is missing from
# PATH entirely (a broken environment, not a malformed payload), deny()
# crashes the same way every other jq call in this script would, with
# exit 127 ("command not found") under `set -e`, past the point where
# any deny JSON is emitted. This is the one deny path that must not
# itself depend on jq: a fixed, statically-escaped JSON literal (no
# interpolation, so no JSON-escaping risk), checked before anything else
# in the script runs.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-pr-issue-acm-disclosure.sh: jq is not available on PATH -- cannot verify the cited issue's ACM/waiver disclosure. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  # Piped via stdin (jq -Rs: raw input, slurped to one string), not
  # `--arg` -- an adversarial review of issue #657 found `--arg`-based
  # construction elsewhere in this script hits the OS's ARG_MAX on a
  # large enough value (a giant PR body/title), crashing past this very
  # function with exit 126 ("Argument list too long"). `$reason` is
  # normally a short, hook-authored string, but the one call site that
  # interpolates `$check_output` (below) could in principle be large, so
  # this function is hardened the same way on general principle.
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

# A malformed payload (invalid JSON, or valid JSON that isn't an object --
# an array/string/null/number) makes every field-extraction jq call below
# exit non-zero, which under `set -e` would crash this script past deny()
# with an exit code Claude Code's PreToolUse contract treats as a
# non-blocking error (the tool call proceeds) -- a fail-open path found by
# issue #657's own adversarial review, live-reproduced with `echo "not
# json at all" | bash check-pr-issue-acm-disclosure.sh`. Validate the
# shape up front and fail closed explicitly instead.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__create_pull_request, but never trust that alone.
if [ "$tool_name" != "mcp__github__create_pull_request" ]; then
  exit 0
fi

# The top-level shape check above says nothing about `.tool_input` itself --
# a second round of issue #657's own adversarial review found that a
# well-formed object payload with `tool_input` set to an array/string/
# number/bool still crashes every `.tool_input.<field>` access below with
# jq's own "Cannot index X with string" runtime error, the same fail-open
# class as the top-level check guards against. `null`/absent are fine (the
# `// {}` default below tolerates both) since jq indexes `null` as `null`,
# not an error.
if ! printf '%s' "$input" | jq -e '(.tool_input // {}) | type == "object"' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_pr_issue_acm_disclosure.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: cannot verify the cited issue's ACM/waiver disclosure -- gitapex_check_pr_issue_acm_disclosure.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

# Extracts owner/repo/title/body directly from $input in one jq call and
# re-shapes them into the payload the Python checker expects -- $input is
# read via stdin the whole way through, never re-passed as a `--arg`
# command-line argument. An earlier version extracted each field into a
# shell variable first, then rebuilt the payload via `jq -n --arg title
# "$title" ...`; issue #657's own adversarial review found that a large
# enough title/body (an attacker/tool-controlled field, evaluated before
# this hook, not after GitHub's own PR-body size limit) blows the OS's
# ARG_MAX on that `--arg` expansion, crashing past deny() with exit 126.
payload=$(printf '%s' "$input" | jq -c \
  '{owner: (.tool_input.owner // ""), repo: (.tool_input.repo // ""), title: (.tool_input.title // ""), body: (.tool_input.body // "")}')

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

# gitapex_check_pr_issue_acm_disclosure.py only ever exits 0 (PASS) or 1 with a
# 'FAIL: ...' stderr message for a genuine disclosure failure -- anything
# else (a different exit code, or exit 1 with no 'FAIL:' line, e.g. an
# uncaught traceback) means the check script itself crashed, not a
# verdict on the PR. Denying either way is still the safe default (an
# unverifiable citation should not silently pass), but the message must
# say so plainly rather than blame the PR for a bug in the check script.
deny "Blocked by hooks/check-pr-issue-acm-disclosure.sh: gitapex_check_pr_issue_acm_disclosure.py exited $check_exit without a recognized FAIL message -- this looks like a bug in the check script itself, not a genuine disclosure failure in the cited issue(s). Failing closed. Output: $check_output"

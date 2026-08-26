#!/bin/bash
# PreToolUse hook (matcher: mcp__github__create_pull_request): blocks
# opening a PR whose target issue (the issue it would Close/Fix/Resolve)
# is already cited by another currently-open PR -- unless the new PR's
# own body carries an explicit Duplicate-PR-waiver line.
#
# Issue #1197: issues #1069/#1070 (two retrospective issues for the same
# PR #1066) and, inside #1069's own repair 1, two independent sessions
# producing duplicate PRs #1066/#1067 for the same source issue #1064 --
# neither session detecting the other in flight. Nothing in
# planning-a-branch-from-an-issue/SKILL.md checked for an existing open PR before
# creating a new one. This hook closes that gap.
#
# Checks via hooks/gitapex_check_pr_duplicate_issue.py, a self-contained
# sibling script bundled beside this hook (not .github/scripts/ -- per
# docs/repository-layout.md, only skills/ and hooks/ are deployed with the
# plugin). That script reuses hooks/gitapex_check_pr_issue_acm_disclosure.py's
# own extract_citations directly (same directory, plain Python import)
# rather than a third copy of that regex logic. Resolved relative to this
# script's own location so it travels with the hook regardless of
# CLAUDE_PROJECT_DIR/CLAUDE_PLUGIN_ROOT.
#
# Fails CLOSED (deny) when it cannot verify another open PR's own
# citations -- no GH_TOKEN/GITHUB_TOKEN in the environment, or the GitHub
# API call fails after retries -- matching this repository's general "fail
# closed, including on INDETERMINATE" posture and
# hooks/check-pr-issue-acm-disclosure.sh's own identical, already-accepted
# trade-off (this blocks all PR creation carrying a resolving citation
# during a transient GitHub API outage).
#
# Denies via exit 2 with the hookSpecificOutput JSON on stderr (verified
# live: a deny writes 0 bytes to stdout) -- single-signal, not the
# dual-stdout-and-stderr scheme an earlier version of this comment claimed;
# hooks/check-pr-issue-acm-disclosure.sh's own identical claim is the same
# inaccuracy, inherited when this script was adapted directly from that one.
# See that script's own comments for the rest of the hardening rationale
# this one shares (jq-missing guard, malformed-JSON guard, non-object
# tool_input guard, stdin-only payload construction to avoid ARG_MAX).
#
# Residual risk, named rather than left implicit (deterministic-gate-quality
# audit, PR #1215): (1) wired only on create_pull_request, not
# update_pull_request -- a PR opened with no resolving citation, then
# edited afterward to add one, is not re-checked; (2) a PR opened outside
# this agent-mediated path entirely (GitHub web UI, `gh`, or a direct API
# call) is never checked at all -- no CI-side backstop exists for this gate
# yet, unlike hooks/check-pr-title-convention.sh's
# .github/workflows/pr-title-convention-gate.yml; (3) a hook-runner timeout
# (see the timeout-arithmetic comment on the check-pr-duplicate-issue.sh
# entry in hooks.json) does not block the tool call per Claude Code's own
# hook contract -- an API outage severe enough to exceed even that budget
# fails this gate open, not closed, despite the fail-closed design intent
# below.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-pr-duplicate-issue.sh: jq is not available on PATH -- cannot verify whether another open PR already cites the same issue. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

# Slurped (`-s`) into a one-element array, not `jq -e 'if type == "object"
# ...'` against the bare stream: the bare-stream form validates each
# whitespace-adjacent JSON value independently and exits on the LAST one,
# so two concatenated JSON objects on stdin (a real payload followed by
# anything else) pass this check -- confirmed live (deterministic-gate-
# quality audit, PR #1215) to walk `tool_name` below into a multi-line
# string that matches no matcher, taking the `exit 0` allow path with the
# duplicate-check never run at all. Slurping first collapses the whole
# input to one JSON value (an array of however many top-level values were
# present) so "exactly one, and it's an object" is checkable directly.
if ! printf '%s' "$input" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-duplicate-issue.sh: the tool-call payload on stdin is not exactly one JSON object. Failing closed."
fi

# Found by an independent adversarial code-review agent (issue #1315),
# the same gap PR #1213/#1217 already closed in six sibling hooks: `jq -r`
# never errors on a non-string `.tool_name` (e.g. `["mcp__github__create_
# pull_request"]`) -- it pretty-prints the JSON form across multiple
# lines instead, which then never equals the plain string the check below
# compares against. That silently falls through as "not our tool" (exit
# 0) rather than failing closed on a malformed field this gate
# structurally depends on -- live-confirmed: an array-wrapped tool_name
# let a create_pull_request call straight through this hook's own
# duplicate-citation check. `.tool_name == null` covers both absent and
# explicit null (an absent key indexes as null in jq); only a present
# non-string, non-null value denies.
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-duplicate-issue.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

if [ "$tool_name" != "mcp__github__create_pull_request" ]; then
  exit 0
fi

# NOT `(.tool_input // {}) | type == "object"`: jq's `//` treats `false`
# (like `null`) as falsy and substitutes `{}`, so that shape would pass
# this check for `tool_input: false` -- confirmed live
# (`echo '{"tool_input": false}' | jq -c '(.tool_input // {}) | type == "object"'`
# prints `true`) -- then crash the payload-extraction jq call below with
# "Cannot index boolean with string" under `set -e`, past deny(), the
# exact fail-open class this hook's own comments elsewhere already guard
# against for every other non-object shape. An explicit `== null` check
# treats `false` and `null` as distinct, matching jq's own type() output.
if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-duplicate-issue.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_pr_duplicate_issue.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-duplicate-issue.sh: cannot verify duplicate-PR status -- gitapex_check_pr_duplicate_issue.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

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
  deny "Blocked by hooks/check-pr-duplicate-issue.sh (issue #1197): $reason"
fi

deny "Blocked by hooks/check-pr-duplicate-issue.sh: gitapex_check_pr_duplicate_issue.py exited $check_exit without a recognized FAIL message -- this looks like a bug in the check script itself, not a genuine duplicate-PR finding. Failing closed. Output: $check_output"

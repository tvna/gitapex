#!/bin/bash
# PreToolUse hook (matcher: mcp__(github|plugin_github_github)__issue_write):
# blocks a `gate-proposal` issue-creation call whose body carries no fresh
# `Dedup-sweep:` backlog-sweep proof line (issue #1806).
#
# Only fires when tool_input.method == "create" AND the filing carries the
# `gate-proposal` label -- any other method or label is out of scope and
# allowed without a network call.
#
# Checks via hooks/gitapex_check_gate_proposal_dedup_sweep.py, a
# self-contained sibling script bundled beside this hook (not
# .github/scripts/ -- per docs/repository-layout.md, only skills/ and
# hooks/ are deployed with the plugin). Fails CLOSED (deny) when the
# live open-count cannot be verified -- no GH_TOKEN/GITHUB_TOKEN, or the
# GitHub API call fails after retries -- matching
# hooks/check-pr-duplicate-issue.sh's own posture. A hook-runner timeout
# fails open per the runner contract (disclosed limit, same as
# gitapex_gate_independent_review_pending.py).
#
# Denies via the PreToolUse hookSpecificOutput JSON on stderr and exit 2,
# mirroring hooks/check-pr-duplicate-issue.sh's own single-signal scheme.

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-gate-proposal-dedup-sweep.sh: jq is not available on PATH -- cannot verify the Dedup-sweep proof line. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

# Slurped (`-s`) into a one-element array first: the bare-stream form
# validates each whitespace-adjacent JSON value independently and exits on
# the LAST one, so two concatenated JSON objects on stdin pass a naive
# check -- the same concatenated-input class
# hooks/check-pr-duplicate-issue.sh already closes.
if ! printf '%s' "$input" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: hook payload is not a single JSON object -- cannot verify the Dedup-sweep proof line. Failing closed."
fi

# `.tool_name == null` covers both absent and explicit null; only a present
# non-string, non-null value denies -- same guard
# hooks/check-pr-duplicate-issue.sh's own identical check applies (issue
# #1315).
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: tool_name in the payload is not a string. Failing closed."
fi

# NOT `(.tool_input // {}) | type == "object"`: jq's `//` treats `false`
# (like `null`) as falsy and substitutes `{}`, so that shape would pass
# this check for `tool_input: false` -- same false-clear
# hooks/check-pr-duplicate-issue.sh's own identical comment documents --
# then crash the payload-extraction jq call below with "Cannot index
# boolean with string" under `set -e`, past deny(). An explicit `== null`
# check treats `false` and `null` as distinct, matching jq's own type()
# output.
if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__(github|plugin_github_github)__issue_write, but never trust that
# alone -- both namespaced forms must be listed here too (same case-list
# pattern hooks/check-post-write-provenance.sh already uses), or the
# plugin-namespaced tool name variant silently skips this gate entirely.
case "$tool_name" in
  mcp__github__issue_write | mcp__plugin_github_github__issue_write) ;;
  *) exit 0 ;;
esac

method=$(printf '%s' "$input" | jq -r '.tool_input.method // empty')

if [ "$method" != "create" ]; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_gate_proposal_dedup_sweep.py"

# Issue #1697/#1581: prefer this checkout's own uv-managed toolchain over
# a bare `python3` from ambient PATH; fall back to bare `python3` for a
# consumer plugin install (only skills/ and hooks/ are ever deployed
# there -- docs/repository-layout.md), where no uv toolchain exists --
# $check_script is stdlib-only, so a bare python3 is always correct
# there. Mirrors hooks/check-issue-acm-disclosure.sh's own resolution.
plugin_root="$(dirname "$script_dir")"
python3_cmd=(python3)
if command -v uv >/dev/null 2>&1 && [ -f "$plugin_root/pyproject.toml" ] && [ -f "$plugin_root/uv.lock" ]; then
  python3_cmd=(uv run --frozen --directory "$plugin_root" python3)
fi

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: cannot verify the Dedup-sweep proof line -- gitapex_check_gate_proposal_dedup_sweep.py was not found at $check_script (corrupted or incomplete plugin bundle)."
fi

# Stdin-only payload construction (never argv) to avoid ARG_MAX on large
# bodies -- the same reason hooks/check-pr-duplicate-issue.sh documents.
payload=$(printf '%s' "$input" | jq -c '{owner: (.tool_input.owner // ""), repo: (.tool_input.repo // ""), method: (.tool_input.method // ""), labels: (.tool_input.labels // []), body: (.tool_input.body // "")}')

# `2>&1` (stdout+stderr combined into one captured string) rather than an
# `mktemp`-based stderr-only capture: an unguarded `mktemp` call crashes
# this script under `set -e` on an unwritable/full /tmp (PR #1213's own
# fix for that class in six sibling hooks), and this shape needs no temp
# file at all. Mirrors hooks/check-pr-duplicate-issue.sh's own
# check_output/check_exit scheme exactly, including its FAIL:-vs-bug
# distinction below.
if check_output=$(printf '%s' "$payload" | "${python3_cmd[@]}" "$check_script" 2>&1); then
  check_exit=0
else
  check_exit=$?
fi

if [ "$check_exit" -eq 0 ]; then
  exit 0
fi

if printf '%s' "$check_output" | grep -q '^FAIL:'; then
  reason=$(printf '%s' "$check_output" | sed -n 's/^FAIL: //p')
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: $reason"
fi

deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: gitapex_check_gate_proposal_dedup_sweep.py exited $check_exit without a recognized FAIL message -- this looks like a bug in the check script itself, not a genuine Dedup-sweep finding. Failing closed. Output: $check_output"

#!/bin/bash
# PreToolUse hook (matcher: mcp__github__issue_write): blocks a
# `gate-proposal` issue-creation call whose body carries no fresh
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

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__issue_write, but never trust that alone.
if [ "$tool_name" != "mcp__github__issue_write" ]; then
  exit 0
fi

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

err_file=$(mktemp /tmp/dedup_sweep_err.XXXXXX)
trap 'rm -f "$err_file"' EXIT
if ! printf '%s' "$payload" | "${python3_cmd[@]}" "$check_script" 2>"$err_file"; then
  deny "Blocked by hooks/check-gate-proposal-dedup-sweep.sh: $(cat "$err_file")"
fi

exit 0

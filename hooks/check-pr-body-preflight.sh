#!/bin/bash
# PreToolUse hook (matchers: mcp__github__create_pull_request,
# mcp__github__update_pull_request): runs the consolidated local PR-body
# preflight (.github/scripts/gitapex_gate_pr_body_preflight.py, issue
# #1725) against the exact draft body a PR-write call is about to submit,
# and blocks the call when any sub-check fails.
#
# Issue #1725 consolidates #1707 (skill-audit-disclosure's own regex
# broken by a stray comma) and #1711 (provenance-disclosure's own
# vocabulary collision): both trace to the same root cause -- no single
# local command ran every PR-body-affecting gate together before a
# create_pull_request/update_pull_request call. This hook is that
# consolidated command, wired the same way
# hooks/check-pr-skill-audit-disclosure.sh already wires its own
# individual gate -- fail OPEN (exit 0, warning to stderr) on any
# inconclusive local git state (unresolvable base branch, an unfetched
# origin/<base>, a checkout outside this repository's own .github/
# scripts) rather than block on a check that could not actually run; CI
# remains the deterministic backstop regardless of what this hook can
# determine locally.
#
# Passes --skip skill-audit-disclosure to the CLI: hooks/check-pr-skill-
# audit-disclosure.sh already wraps that same gate as its own PreToolUse
# hook on the identical two matchers, so without this both hooks would
# independently recompute the identical verdict (including a duplicated
# git merge-base resolution) on every single call -- found by an
# independent adversarial review of this issue's own implementation. The
# other three sub-checks (provenance-disclosure, ascii-only, provenance-
# marker-scan) have no other PreToolUse hook, so this hook remains their
# only local coverage.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth), same as
# hooks/check-pr-skill-audit-disclosure.sh.

set -euo pipefail

# Issue #1208's jq-missing guard, same pattern as
# hooks/check-pr-skill-audit-disclosure.sh: checked first, via a fixed,
# statically-escaped JSON literal, so a missing jq cannot crash every
# other jq call below under `set -e` into a non-blocking exit.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-pr-body-preflight.sh: jq is not available on PATH -- cannot verify the consolidated PR-body preflight. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-body-preflight.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-body-preflight.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matchers already restrict this hook to
# these two tools, but never trust that alone.
case "$tool_name" in
  mcp__github__create_pull_request|mcp__github__update_pull_request) ;;
  *) exit 0 ;;
esac

if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-body-preflight.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

body=$(printf '%s' "$input" | jq -r '.tool_input.body // empty')

# Same empty-body bypass as hooks/check-pr-skill-audit-disclosure.sh: an
# update_pull_request call not touching the body has nothing new to
# check locally. create_pull_request's body is optional too, but an
# absent/empty body on a create call is itself the violation every
# sub-check here would flag (no disclosure, trivially non-ASCII-clean),
# so only update_pull_request gets the bypass.
if [ "$tool_name" = "mcp__github__update_pull_request" ] && [ -z "$body" ]; then
  exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=""
preflight_script="${repo_root}/.github/scripts/gitapex_gate_pr_body_preflight.py"

# Per docs/repository-layout.md, only skills/ and hooks/ are deployed
# when this repository ships as a plugin -- .github/ never is, so a
# consumer install simply has no local form of this check (CI is the
# only enforcement there, matching every other .github/scripts/-only
# gate's own posture).
if [ ! -f "$preflight_script" ]; then
  exit 0
fi

# Same base-branch resolution as hooks/check-pr-skill-audit-disclosure.sh:
# tool_input.base when explicitly supplied (create_pull_request always
# sends it; update_pull_request only when changing the base), else the
# repo's own default branch.
base_branch=$(printf '%s' "$input" | jq -r '.tool_input.base // empty')
if [ -z "$base_branch" ]; then
  base_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed -E 's#^origin/##') || true
fi

if [ -z "$base_branch" ]; then
  echo "Warning: hooks/check-pr-body-preflight.sh could not resolve a base branch locally; skipping the local pre-check (CI remains authoritative)." >&2
  exit 0
fi

if ! merge_base=$(git merge-base "origin/${base_branch}" HEAD 2>/dev/null); then
  echo "Warning: hooks/check-pr-body-preflight.sh could not resolve origin/${base_branch} locally (not fetched?); skipping the local pre-check (CI remains authoritative)." >&2
  exit 0
fi

if ! body_file=$(mktemp 2>/dev/null); then
  echo "Warning: hooks/check-pr-body-preflight.sh could not create a temp file for the body check (mktemp failed); skipping the local pre-check (CI remains authoritative)." >&2
  exit 0
fi
printf '%s' "$body" >"$body_file"

# Prefer this checkout's own uv-managed .venv, same rationale as
# hooks/check-pr-skill-audit-disclosure.sh's own tier-2 fallback: a bare
# python3 resolved from the calling shell's own ambient PATH may not see
# this checkout's dependencies (e.g. pydantic, which skill-audit-
# disclosure's own --check-diff mode needs).
python3_cmd=(python3)
if command -v uv >/dev/null 2>&1 && [ -f "${repo_root}/pyproject.toml" ] && [ -f "${repo_root}/uv.lock" ]; then
  python3_cmd=(uv run --frozen --directory "$repo_root" python3)
fi

if preflight_output=$(cd "$repo_root" && "${python3_cmd[@]}" "$preflight_script" \
    --check-diff "$merge_base" HEAD --body-file "$body_file" --skip skill-audit-disclosure 2>&1); then
  preflight_exit=0
else
  preflight_exit=$?
fi
rm -f "$body_file"

if [ "$preflight_exit" -eq 0 ]; then
  exit 0
fi

# `grep -q` closes stdin on first match, which can SIGPIPE a still-writing
# upstream; under `set -o pipefail` (set above) that would silently
# downgrade a real match into "not found" -- same fix
# hooks/check-pr-skill-audit-disclosure.sh already applies for the
# identical reason: `-q` dropped, output redirected instead so grep
# always reads to completion.
if printf '%s' "$preflight_output" | grep '^FAIL ' >/dev/null; then
  deny "Blocked by hooks/check-pr-body-preflight.sh: this PR body fails the consolidated local preflight (provenance-disclosure, ASCII-only, provenance-marker scan -- skill-audit-disclosure is covered separately by hooks/check-pr-skill-audit-disclosure.sh). This is the same coverage CI enforces across its own separate gates, computed locally before the push. Re-check with:

  uv run --frozen python3 .github/scripts/gitapex_gate_pr_body_preflight.py --check-diff ${merge_base} HEAD --body-file <path>

$preflight_output"
fi

# Not a verdict on the body: the preflight script itself could not
# complete (a missing sibling script, an unresolvable diff). Fail open --
# CI remains authoritative regardless.
echo "Warning: hooks/check-pr-body-preflight.sh could not complete the local pre-check (exit $preflight_exit); skipping (CI remains authoritative). Output: $preflight_output" >&2

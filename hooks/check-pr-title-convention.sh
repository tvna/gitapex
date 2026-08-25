#!/bin/bash
# PreToolUse hook (matchers: mcp__github__create_pull_request,
# mcp__github__update_pull_request): blocks a PR title that does not match
# Conventional Commits format.
#
# Issue #1058: no deterministic gate restricted PR titles to Conventional
# Commits (feat/fix/docs/style/refactor/perf/test/build/ci/chore/revert,
# optional scope, optional breaking-change '!'). Checks via
# hooks/gitapex_check_pr_title_convention.py, a self-contained stdlib-only
# sibling script bundled beside this hook (not .github/scripts/ -- per
# docs/repository-layout.md, only skills/ and hooks/ are deployed with the
# plugin). Resolved relative to this script's own location so it travels
# with the hook regardless of CLAUDE_PROJECT_DIR/CLAUDE_PLUGIN_ROOT.
#
# For mcp__github__update_pull_request, `title` is optional -- an update
# that never touches the title is out of scope and passes untouched. For
# mcp__github__create_pull_request, `title` is a required field of the
# tool's own schema, so its absence is treated as a malformed payload and
# denied (fail closed), not silently skipped.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stderr and exit 2,
# same convention as hooks/check-issue-acm-disclosure.sh and
# hooks/check-pr-issue-acm-disclosure.sh. Uses jq -Rs (stdin, not --arg) to
# build the deny JSON, same ARG_MAX-avoidance reason as
# hooks/check-pr-issue-acm-disclosure.sh's own deny().

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-pr-title-convention.sh: jq is not available on PATH -- cannot verify the PR title. Failing closed.\"}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": .}' >&2
  exit 2
}

input=$(cat)

# A malformed payload (invalid JSON, or valid JSON that is not an object)
# would otherwise make every field-extraction jq call below exit non-zero,
# crashing past deny() under `set -e` with an exit code Claude Code's
# PreToolUse contract treats as non-blocking (the tool call proceeds) --
# the same fail-open shape hooks/check-pr-issue-acm-disclosure.sh's own
# adversarial review found and fixed. Validate the shape up front instead.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-title-convention.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

# Found by code review (PR #1213), the same gap independently tracked as
# issue #1217 against this hook specifically: `jq -r` never errors on a
# non-string `.tool_name` (e.g. `["mcp__github__create_pull_request"]`, or
# a bare number/bool) -- it pretty-prints a non-scalar JSON form across
# multiple lines, and a scalar (number/bool) still never equals the plain
# string(s) the check below compares against. Either way this silently
# falls through as "not our tool" (exit 0) rather than failing closed on a
# malformed field this gate structurally depends on -- live-confirmed: a
# `tool_name: 0` payload let a non-conventional PR title straight through
# this hook's own convention check. `.tool_name == null` covers both absent
# and explicit null (an absent key indexes as null in jq); only a present
# non-string, non-null value denies.
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-title-convention.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matchers already restrict this hook to
# these two tools, but never trust that alone.
if [ "$tool_name" != "mcp__github__create_pull_request" ] && [ "$tool_name" != "mcp__github__update_pull_request" ]; then
  exit 0
fi

# tool_input could be a non-object (array/string/number/bool) in an
# otherwise well-formed payload, which would crash the `has("title")`
# access below with jq's own "Cannot check whether X has a string key"
# runtime error -- same fail-open class as the top-level check above.
# `(.tool_input // {})` alone is not enough: jq's `//` treats JSON `false`
# the same as `null` (both are falsy), so a `tool_input: false` payload
# slips past that form and crashes the `has("title")` access below anyway
# -- found by code review (PR #1213), independently tracked as issue #1216
# against this hook specifically, and live-confirmed with
# `jq -e '(.tool_input // {}) | type == "object"' <<< '{"tool_input":false}'`,
# which wrongly reports true. Checking `.tool_input == null` directly (true
# for both absent and explicit null, never for `false`) closes that gap;
# null/absent are fine since jq indexes `null` as `null`, not an error.
if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-title-convention.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

has_title=$(printf '%s' "$input" | jq -r '(.tool_input | has("title"))')

# update_pull_request may legitimately never touch the title; only
# create_pull_request requires one.
if [ "$tool_name" = "mcp__github__update_pull_request" ] && [ "$has_title" != "true" ]; then
  exit 0
fi

if [ "$has_title" != "true" ]; then
  deny "Blocked by hooks/check-pr-title-convention.sh: mcp__github__create_pull_request call carries no title field. Failing closed."
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_pr_title_convention.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-title-convention.sh: cannot verify the PR title's Conventional Commits format -- gitapex_check_pr_title_convention.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

# jq's output is piped straight into python3, never captured into a shell
# variable first: `title=$(...)` command substitution unconditionally
# strips every trailing newline, which silently defeats the very
# trailing-newline rejection CONVENTIONAL_COMMIT_RE exists to enforce (a
# title ending in a literal `\n` would reach the checker already stripped
# and wrongly pass) -- confirmed live by adversarial review on PR #1059.
# `-j` (join), not `-r` (raw): `-r` itself appends a trailing newline
# after every output, which -- once no longer absorbed by the `$(...)`
# capture this replaced -- would reach the checker as an unconditional
# extra `\n` and false-reject every otherwise-valid title. `-j` emits the
# string with no added newline, so only a newline genuinely present in
# the title's own JSON value reaches the checker.
if printf '%s' "$input" | jq -j '.tool_input.title // ""' | python3 "$check_script" >/dev/null 2>&1; then
  exit 0
fi

# The title itself is never echoed here: it is externally supplied,
# unauthenticated text (anyone who can open or edit a pull request
# controls it) that could carry pasted credentials or PII -- caught by
# review on PR #1059.
deny "Blocked by hooks/check-pr-title-convention.sh (issue #1058): PR title does not match Conventional Commits format -- expected 'type(scope)!: description' with type in feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert. See CONVENTIONAL_COMMIT_RE in hooks/gitapex_check_pr_title_convention.py."

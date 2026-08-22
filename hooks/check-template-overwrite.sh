#!/bin/bash
# PreToolUse hook (matcher: Write): blocks Write calls that would overwrite
# an existing issue/PR/MR template file (GitHub or GitLab). A genuinely new
# template (file not yet present) is allowed -- this protects any
# hand-maintained or agent-authored template from accidental clobber by any
# skill or workflow.
#
# Denies via PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (defense in depth -- see plugin-dev's hook-development skill,
# examples/validate-write.sh).

set -euo pipefail

# Issue #1208: this deny path must not itself depend on jq -- if jq is
# missing from PATH entirely, every jq call below would crash under
# `set -e` with exit 127 ("command not found"), an exit code Claude Code's
# PreToolUse contract treats as non-blocking (the tool call proceeds
# unchecked). Checked first, via a fixed, statically-escaped JSON literal
# (no interpolation, so no JSON-escaping risk), same pattern as
# hooks/check-pr-issue-acm-disclosure.sh's own jq-missing guard.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-template-overwrite.sh: jq is not available on PATH -- cannot verify the write target. Failing closed.\"}" >&2
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
# an object) would otherwise make every field-extraction jq call below exit
# non-zero, crashing past deny() under `set -e` with an exit code Claude
# Code's PreToolUse contract treats as non-blocking -- the same fail-open
# class hooks/check-pr-issue-acm-disclosure.sh's own adversarial review
# found and fixed. Validate the shape up front instead.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-template-overwrite.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

# Found by code review (PR #1213): jq -r never errors on a non-string
# `.tool_name` (e.g. `["Write"]`) -- it pretty-prints the JSON form across
# multiple lines instead, which then never equals the plain "Write" string
# the check below compares against. That silently falls through as "not
# our tool" (exit 0) rather than failing closed on a malformed field this
# gate structurally depends on -- live-confirmed: an array-wrapped
# tool_name let an overwrite of the real .github/PULL_REQUEST_TEMPLATE.md
# straight through this hook. `.tool_name == null` covers both absent and
# explicit null (an absent key indexes as null in jq); only a present
# non-string, non-null value denies.
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-template-overwrite.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# Write, but never trust that alone.
if [ "$tool_name" != "Write" ]; then
  exit 0
fi

# Issue #1208: tool_input could be a non-object (array/string/number/bool)
# in an otherwise well-formed payload, which would crash the
# `.tool_input.file_path` access below with jq's own "Cannot index X with
# string" runtime error -- same fail-open class as the top-level check
# above. `(.tool_input // {})` alone is not enough: jq's `//` treats JSON
# `false` the same as `null` (both are falsy), so a `tool_input: false`
# payload slipped past that form and crashed the extraction below anyway
# -- found by code review (PR #1213), live-confirmed with
# `jq -e '(.tool_input // {}) | type == "object"' <<< '{"tool_input":false}'`,
# which wrongly reports true. Checking `.tool_input == null` directly
# (true for both absent and explicit null, never for `false`) closes
# that gap.
if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-template-overwrite.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

# Issue #1208 (round 4): a well-formed, object-shaped tool_input can still
# carry `.tool_input.file_path` as a JSON array (e.g.
# `[".github/PULL_REQUEST_TEMPLATE.md"]`) instead of a string. `jq -r`
# never errors on this -- it pretty-prints the value across multiple
# lines, which breaks both `is_template_path()`'s basename matching and
# `[ -f "$file_path" ]`, silently letting an overwrite of a real,
# existing template file through with exit 0 instead of exit 2 -- found
# by code review (PR #1213), live-confirmed against the actual
# `.github/PULL_REQUEST_TEMPLATE.md` in this repository. Must deny
# before extraction.
if ! printf '%s' "$input" | jq -e '(.tool_input.file_path == null) or (.tool_input.file_path | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-template-overwrite.sh: tool_input.file_path in the payload is not a string. Failing closed."
fi

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

if [ -z "$file_path" ]; then
  exit 0
fi

is_template_path() {
  # Match case-insensitively: GitHub honors these paths regardless of case
  # (e.g. a lowercase `.github/pull_request_template.md` is valid), so a
  # case-sensitive match would let a lowercase overwrite slip through.
  local p base
  p=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')

  # Directory-based template locations (hold multiple templates).
  case "$p" in
    *.github/issue_template/*) return 0 ;;
    *.github/pull_request_template/*) return 0 ;;
    *.gitlab/issue_templates/*) return 0 ;;
    *.gitlab/merge_request_templates/*) return 0 ;;
  esac

  # Single-file PR template. GitHub honors it at the repo root, in `.github/`,
  # or in `docs/`, with a `.md`/`.txt`/no extension -- the same set this
  # plugin's validate_templates.py (find_existing_templates) enumerates.
  # Matching the reserved basename anywhere is a safe over-approximation: a
  # file with this exact name is a PR template in practice, keeping this
  # guard in sync with what the seeding skill treats as existing.
  base=${p##*/}
  case "$base" in
    pull_request_template|pull_request_template.md|pull_request_template.txt) return 0 ;;
  esac

  return 1
}

if is_template_path "$file_path" && [ -f "$file_path" ]; then
  deny "Blocked by hooks/check-template-overwrite.sh: Write would overwrite an existing template file at $file_path. Never overwrite or \"improve\" an existing template via Write -- their presence ends automated generation unless the owner names specific additions; use Edit for a deliberate, reviewed change instead."
fi

exit 0

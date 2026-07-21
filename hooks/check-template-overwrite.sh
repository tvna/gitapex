#!/bin/bash
# PreToolUse hook (matcher: Write) enforcing a standing repository
# invariant: block Write calls that would overwrite an EXISTING issue/PR/MR
# template file (GitHub or GitLab). A genuinely new template (file does not
# yet exist) is allowed. Protects any hand-maintained or agent-authored
# template from an accidental clobber, regardless of which skill or
# workflow is touching it.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh).

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# Write, but never trust that alone.
if [ "$tool_name" != "Write" ]; then
  exit 0
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
  # or in `docs/`, with a `.md`/`.txt`/no extension. The previous version only
  # matched `.github/PULL_REQUEST_TEMPLATE.md` (uppercase, .github-only),
  # missing the common root-level lowercase `pull_request_template.md` and the
  # docs/ variants that this plugin's own validate_templates.py
  # (find_existing_templates) already enumerates. Matching the reserved
  # basename anywhere is a safe over-approximation -- a file with this exact
  # name is a PR template in practice -- and keeps the overwrite guard in sync
  # with what the seeding skill treats as an existing template.
  base=${p##*/}
  case "$base" in
    pull_request_template|pull_request_template.md|pull_request_template.txt) return 0 ;;
  esac

  return 1
}

if is_template_path "$file_path" && [ -f "$file_path" ]; then
  jq -n --arg path "$file_path" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": ("Blocked by hooks/check-template-overwrite.sh: Write would overwrite an existing template file at " + $path + ". Never overwrite or \"improve\" an existing template via Write -- their presence ends automated generation unless the owner names specific additions; use Edit for a deliberate, reviewed change instead.")}' >&2
  exit 2
fi

exit 0

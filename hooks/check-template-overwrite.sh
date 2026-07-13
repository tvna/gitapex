#!/bin/bash
# PreToolUse hook (matcher: Write) backing the approved Major finding:
#   5. [seeding-issue-pr-templates] SKILL.md -- block Write calls that would
#      overwrite an EXISTING issue/PR/MR template file (GitHub or GitLab).
#      A genuinely new template (file does not yet exist) is allowed.
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
  case "$1" in
    *.github/ISSUE_TEMPLATE/*) return 0 ;;
    *.github/PULL_REQUEST_TEMPLATE.md) return 0 ;;
    *.github/PULL_REQUEST_TEMPLATE/*) return 0 ;;
    *.gitlab/issue_templates/*) return 0 ;;
    *.gitlab/merge_request_templates/*) return 0 ;;
    *) return 1 ;;
  esac
}

if is_template_path "$file_path" && [ -f "$file_path" ]; then
  jq -n --arg path "$file_path" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": ("Blocked by hooks/check-template-overwrite.sh: Write would overwrite an existing template file at " + $path + ". Per the seeding-issue-pr-templates SKILL.md non-destruction stop boundary, never overwrite or \"improve\" existing templates -- their presence ends this skill unless the owner names specific additions.")}' >&2
  exit 2
fi

exit 0

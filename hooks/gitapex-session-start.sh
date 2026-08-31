#!/usr/bin/env bash
# SessionStart hook for the gitapex plugin: injects the invoking-gitapex
# skill's own content into every session's context at start, the same
# way the primary hooks/hooks.json PreToolUse/PostToolUse entries already
# resolve their own scripts relative to this plugin's own root -- so a
# consuming repository that installs gitapex as a plugin gets this
# discipline without depending on that repository's own instruction files
# or hook configuration (issue tvna/gitapex#1173).
#
# Determines its own plugin root by walking up from its own location
# (portable across Claude Code, Cursor, and Copilot CLI -- each of which
# sets a different plugin-root environment variable, or none at all --
# rather than depending on any one of them being set) so it can find its
# sibling skills/invoking-gitapex/SKILL.md regardless of platform.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

skill_content=$(cat "${PLUGIN_ROOT}/skills/invoking-gitapex/SKILL.md" 2>&1 || echo "Error reading invoking-gitapex skill")

# Escape string for JSON embedding using bash parameter substitution.
# Each ${s//old/new} is a single C-level pass.
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

skill_escaped=$(escape_for_json "$skill_content")
session_context="<EXTREMELY_IMPORTANT>\nBefore any response or action, check whether a skill applies -- see gitapex's own 'invoking-gitapex' skill below. For all other skills, use the 'Skill' tool:\n\n${skill_escaped}\n</EXTREMELY_IMPORTANT>"

# Output context injection as JSON.
# Cursor hooks expect additional_context (snake_case).
# Claude Code hooks expect hookSpecificOutput.additionalContext (nested).
# Copilot CLI and other platforms expect additionalContext (top-level).
# Claude Code reads BOTH additional_context and hookSpecificOutput without
# deduplication, so only the field the current platform consumes is emitted.
if [ -n "${CURSOR_PLUGIN_ROOT:-}" ]; then
  # Cursor sets CURSOR_PLUGIN_ROOT (may also set CLAUDE_PLUGIN_ROOT)
  printf '{\n  "additional_context": "%s"\n}\n' "$session_context" | cat
elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -z "${COPILOT_CLI:-}" ]; then
  # Claude Code sets CLAUDE_PLUGIN_ROOT without COPILOT_CLI
  printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$session_context" | cat
else
  # Copilot CLI (sets COPILOT_CLI=1) or unknown platform -- SDK standard format
  printf '{\n  "additionalContext": "%s"\n}\n' "$session_context" | cat
fi

exit 0

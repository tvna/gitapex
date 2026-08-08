#!/bin/bash
# PostToolUse hook (matchers: mcp__github__create_pull_request,
# mcp__github__update_pull_request, mcp__github__issue_write): re-fetch the
# body GitHub actually stored and re-run the outward-artifact-preflight
# provenance (check 1) and ASCII-only (check 3) scans against it.
#
# Issue #878: every existing scan runs against the drafted text, before the
# write executes. skills/outward-artifact-preflight/SKILL.md's own Stop
# boundary states the gap -- "no hook re-checks what the platform actually
# stores" -- and makes its check 2 post-creation re-check mandatory by
# hand. This is the deterministic backstop for that manual step.
#
# This is this repository's FIRST PostToolUse hook; every other entry in
# hooks/hooks.json is PreToolUse. That is the point, not an accident: the
# gap being closed is specifically the one a pre-write gate cannot see.
#
# Detective, not preventive. Per Claude Code's own hook reference
# (code.claude.com/docs/en/hooks), PostToolUse "cannot block -- the tool
# already executed successfully". Issue #878 names the same constraint. So
# a finding is emitted on BOTH in-session channels rather than as a deny:
#   - `decision: block` + `reason` -- fed to the agent, which must react
#     rather than move on (a plain systemMessage can go unaddressed, and
#     outward-artifact-preflight's Stop boundary treats the PR as
#     unverified until the stored body scans clean).
#   - `systemMessage` -- surfaced to the operator.
# Both sinks are in-session. Nothing is posted publicly: re-posting a
# flagged provenance string into a public comment would widen the exact
# exposure the scan exists to catch (CLAUDE.md section 4), and the check
# needs only a read-scoped token.
#
# Deliberately divergent from check-bash-safety.sh's advisory `warn()` on
# `git push`, which surfaces a systemMessage and lets the session continue.
# There, the artifact is a commit already in history and hard to amend;
# here, remediation is one update_pull_request call away and the governing
# skill calls the re-check mandatory, so the finding gets the agent's
# attention rather than only the operator's.
#
# Checks via hooks/gitapex_check_post_write_provenance.py, a self-contained
# sibling script bundled beside this hook (not .github/scripts/ -- per
# docs/repository-layout.md, only skills/ and hooks/ are deployed with the
# plugin, so a .github/ lookup always misses in an installed-plugin
# consumer checkout). Resolved relative to this script's own location so it
# travels with the hook regardless of CLAUDE_PROJECT_DIR/CLAUDE_PLUGIN_ROOT.
#
# Exit code is always 0. Exit 2 would route the message to stderr and make
# Claude Code discard the stdout JSON entirely (its own reference: "Exit 2
# means a blocking error. Claude Code ignores stdout and any JSON in it"),
# which would drop the systemMessage channel -- so the dual-signal JSON on
# stdout at exit 0 is strictly louder here than a non-zero exit.

set -euo pipefail

# jq builds every JSON payload below, including the report path itself. If
# jq is missing from PATH entirely (a broken environment, not a malformed
# payload), a bare `jq` call would crash under `set -e` past the point any
# report is emitted -- a silent pass, the one outcome this gate exists to
# prevent. A fixed, statically-escaped JSON literal (no interpolation, so
# no escaping risk) covers that case before anything else runs.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"decision\": \"block\", \"reason\": \"hooks/check-post-write-provenance.sh could not verify the stored PR/issue body: jq is not available on PATH. The artifact this call just published is UNVERIFIED -- run skills/outward-artifact-preflight/SKILL.md check 2 by hand.\", \"systemMessage\": \"post-write provenance re-check could not run: jq is not available on PATH. The published artifact is unverified.\"}"
  exit 0
fi

report() {
  local reason="$1"
  # Piped via stdin (jq -Rs: raw input, slurped to one string), not
  # `--arg` -- a scan report can quote many matched hits from a large
  # stored body, and hooks/check-pr-issue-acm-disclosure.sh already
  # records `--arg` hitting the OS's ARG_MAX on a large enough value and
  # crashing past its own emit point.
  printf '%s' "$reason" | jq -Rs '{"decision": "block", "reason": ., "systemMessage": .}'
  exit 0
}

input=$(cat)

# A malformed payload (invalid JSON, or valid JSON that is not an object)
# makes every field-extraction jq call below exit non-zero, which under
# `set -e` crashes this script past `report()` -- a silent pass. Validate
# the shape up front and report explicitly instead.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  report "hooks/check-post-write-provenance.sh could not verify the stored PR/issue body: the tool-call payload on stdin is not a JSON object. The artifact this call just published is UNVERIFIED."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matchers already restrict this hook to
# the three covered tools, but never trust that alone. The Python checker
# re-validates the same field independently.
case "$tool_name" in
  mcp__github__create_pull_request | mcp__github__update_pull_request | mcp__github__issue_write) ;;
  *) exit 0 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_post_write_provenance.py"

if [ ! -f "$check_script" ]; then
  report "hooks/check-post-write-provenance.sh could not verify the stored PR/issue body: gitapex_check_post_write_provenance.py was not found at $check_script (corrupted or incomplete plugin bundle). The artifact this call just published is UNVERIFIED."
fi

# $input is piped on stdin the whole way through, never re-passed as a
# command-line argument -- same ARG_MAX rationale as report() above, and
# the same reason a tool-controlled title/body never reaches an argv slot.
if check_output=$(printf '%s' "$input" | python3 "$check_script" 2>&1); then
  exit 0
fi

report "Blocked by hooks/check-post-write-provenance.sh (issue #878): $check_output"

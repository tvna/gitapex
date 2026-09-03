#!/bin/bash
# Stop hook: state-reader half of the marker-file state machine backing
# issue #1209's review-thread-resolution + mergeable_state-verification
# obligation (CLAUDE.md section 3: "After a fix push that addresses a
# review thread, explicitly call mcp__github__resolve_review_thread to
# resolve the thread; then verify mergeable_state before closing the
# turn.").
#
# No matcher: Claude Code's Stop event supports none (confirmed via
# code.claude.com/docs/en/hooks) -- it fires on every turn end
# unconditionally, so hooks/gitapex_check_stop_review_obligation.py's own
# push_detected check is what keeps an ordinary, PR-review-unrelated turn
# from ever being blocked.
#
# No jq dependency, deliberately: an earlier version of this script used
# jq to pre-validate the payload shape before ever invoking python3, and
# failed CLOSED (exit 2, deny) whenever jq itself was missing from PATH --
# but jq was never actually needed to determine push_detected (the state
# file is read entirely in python, with no jq involved at all), so that
# guard was denying EVERY turn end in a jq-missing environment, including
# turns that never touched a push or a review thread -- contradicting
# this hook's own documented invariant above. Worse: since
# hooks/check-bash-safety.sh (the PreToolUse Bash gate) ALSO fails closed
# when jq is missing, a jq-missing environment could deny Bash (so the
# agent could not even run a command to self-heal) AND deny every Stop
# (so the turn could never end either) -- a full deadlock. Independent
# review found and reproduced this live. gitapex_check_stop_review_obligation.py's
# own main() already validates payload shape and fails closed correctly
# with no jq involved at all, so this wrapper delegates that validation
# to it entirely rather than duplicating it in jq first.
#
# Delegates to hooks/gitapex_check_stop_review_obligation.py -- see that
# module's own docstring (and hooks/gitapex_check_post_review_obligation_tracker.py's,
# the writer half) for the full state-machine design and its disclosed
# residual risks (no infinite-loop circuit breaker in v1, session-scoped
# state only).
#
# Still fails CLOSED (exit 2, deny) on the two failure modes this wrapper
# genuinely cannot delegate to python -- python3 itself unavailable, or
# the check script itself missing (a corrupted/incomplete plugin bundle)
# -- since in either case there is truly no way left to determine whether
# an obligation is outstanding, matching every other fail-closed gate in
# this directory. Denies via the Stop hookSpecificOutput JSON on stdout
# AND exit 2 / stderr text (both conventions, matching this repository's
# existing PreToolUse deny() convention for defense in depth). JSON output
# is built with python3's own json module (a hard dependency of this
# entire feature already), never jq -- see above.

set -euo pipefail

# Checked first, via a fixed, hardcoded JSON literal needing no escaping
# (no interpolated content) -- deny()'s own python3 invocation below
# would itself be unavailable if this guard did not run first.
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"hookEventName\": \"Stop\", \"decision\": \"block\", \"reason\": \"hooks/check-stop-review-obligation.sh: python3 is not available on PATH -- cannot verify whether a review-thread-resolution/mergeable_state obligation is outstanding. Failing closed.\"}}" >&2
  exit 2
fi

deny() {
  local reason="$1"
  # Piped via stdin, not passed as an argv element -- same ARG_MAX-
  # avoidance rationale as every sibling deny() in this directory.
  printf '%s' "$reason" | python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": sys.stdin.read()}}))
' >&2
  exit 2
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_stop_review_obligation.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-stop-review-obligation.sh: gitapex_check_stop_review_obligation.py was not found at $check_script (corrupted or incomplete plugin bundle). Failing closed."
fi

# Issue #1697/#1581: prefer this checkout's own uv-managed .venv over a
# bare `python3` resolved from the calling shell's own ambient PATH --
# see hooks/check-pr-skill-audit-disclosure.sh's own precondition-probe
# fix for the PATH-nondeterminism class this closes. Falls back to a bare
# `python3` for a consumer plugin install (only skills/ and hooks/ are
# ever deployed there -- docs/repository-layout.md), where no uv
# toolchain/lockfile exists -- $check_script is stdlib-only, so a bare
# python3 has always been a correct answer there; this fallback keeps
# that unchanged. deny()'s own inline `python3 -c` above is left as a
# bare interpreter deliberately: it only ever needs the stdlib json
# module and must stay reachable even when this block's own uv/pyproject
# lookup below has not run yet (it can fire before this point, from the
# command -v python3 guard at the very top of this file).
plugin_root="$(dirname "$script_dir")"
python3_cmd=(python3)
if command -v uv >/dev/null 2>&1 && [ -f "$plugin_root/pyproject.toml" ] && [ -f "$plugin_root/uv.lock" ]; then
  python3_cmd=(uv run --frozen --directory "$plugin_root" python3)
fi

# Payload-shape validation (malformed JSON, non-object payload) happens
# entirely inside gitapex_check_stop_review_obligation.py's own main() --
# see that module's docstring -- so this wrapper does none of its own.
check_exit=0
check_output=$("${python3_cmd[@]}" "$check_script" 2>&1) || check_exit=$?

if [ "$check_exit" -eq 0 ]; then
  exit 0
fi

deny "$check_output"

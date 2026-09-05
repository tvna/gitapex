#!/bin/bash
# PostToolUse hook (matcher: Bash|mcp__(github|plugin_github_github)__resolve_review_thread|
# mcp__(github|plugin_github_github)__pull_request_read): state-writer half of the marker-file
# state machine backing issue #1209's review-thread-resolution +
# mergeable_state-verification obligation (CLAUDE.md section 3).
#
# Delegates to hooks/gitapex_check_post_review_obligation_tracker.py --
# see that module's own docstring for the full state-machine design.
# hooks/check-stop-review-obligation.sh (a Stop hook) is the reader half
# that actually blocks; this hook only ever writes state, never blocks.
#
# No jq dependency, deliberately: every piece of payload-shape validation
# and tool_name dispatch this hook needs is already performed by
# gitapex_check_post_review_obligation_tracker.py's own main()/process()
# (malformed JSON, a non-object payload, and an unmatched tool_name all
# already no-op there) -- duplicating that validation here in jq would be
# exactly the kind of shell/python duplication independent review flagged
# elsewhere in this same change. python3 is invoked unconditionally
# (subject only to the two guards below); it is the one hard dependency
# this hook actually has. See hooks/check-stop-review-obligation.sh's own
# header for the deadlock this design also avoids on its Stop sibling.
#
# Always exits 0: PostToolUse cannot block a tool call that already
# executed successfully (Claude Code's own hooks reference), so every
# failure path here (missing tracker script, missing python3, or the
# tracker script itself exiting non-zero) is fail-open with a
# systemMessage warning -- matching hooks/check-post-write-provenance.sh's
# own fail-open convention for the same PostToolUse-cannot-block
# constraint. That sibling additionally sets `decision: block` at its own
# exit 0 to get the AGENT's attention, not just the operator's, since its
# own finding needs a same-turn fix; this hook's own failure modes --
# infra unavailable, or one cycle's tracking silently incomplete -- do not
# carry that same-turn urgency, since the Stop hook (the half that
# actually enforces the obligation) independently fails CLOSED on its own
# unreadable state rather than depending on this warning being read.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tracker_script="$script_dir/gitapex_check_post_review_obligation_tracker.py"

if [ ! -f "$tracker_script" ]; then
  printf '%s\n' "{\"systemMessage\": \"hooks/check-post-review-obligation-tracker.sh: gitapex_check_post_review_obligation_tracker.py was not found at $tracker_script (corrupted or incomplete plugin bundle). Skipping this cycle's obligation tracking.\"}"
  exit 0
fi

# Issue #1697/#1581: prefer this checkout's own uv-managed .venv over a
# bare `python3` resolved from the calling shell's own ambient PATH --
# see hooks/check-pr-skill-audit-disclosure.sh's own precondition-probe
# fix for the PATH-nondeterminism class this closes. Falls back to a bare
# `python3` for a consumer plugin install (only skills/ and hooks/ are
# ever deployed there -- docs/repository-layout.md), where no uv
# toolchain/lockfile exists -- $tracker_script is stdlib-only, so a bare
# python3 has always been a correct answer there; this fallback keeps
# that unchanged.
plugin_root="$(dirname "$script_dir")"
python3_cmd=(python3)
if command -v uv >/dev/null 2>&1 && [ -f "$plugin_root/pyproject.toml" ] && [ -f "$plugin_root/uv.lock" ]; then
  python3_cmd=(uv run --frozen --directory "$plugin_root" python3)
elif ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "{\"systemMessage\": \"hooks/check-post-review-obligation-tracker.sh: python3 is not available on PATH. Skipping this cycle's obligation tracking.\"}"
  exit 0
fi

# Stdin is piped straight through to python3 -- no capture-and-repipe, so
# no ARG_MAX concern either. Payload-shape validation, tool_name dispatch,
# and any systemMessage worth emitting for a malformed/irrelevant payload
# all happen inside the tracker script itself (see header above).
if ! "${python3_cmd[@]}" "$tracker_script" 2>/dev/null; then
  printf '%s\n' "{\"systemMessage\": \"hooks/check-post-review-obligation-tracker.sh: gitapex_check_post_review_obligation_tracker.py exited non-zero. Review-thread-resolution/mergeable_state tracking for this turn may be incomplete.\"}"
fi

exit 0

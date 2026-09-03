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
# inconclusive local git state that keeps the preflight script from ever
# being invoked at all (unresolvable base branch, an unfetched
# origin/<base>, a checkout outside this repository's own .github/
# scripts, a stacked PR with no explicit base -- narrows to the two
# body-only sub-checks there rather than blocking outright); CI remains
# the deterministic backstop regardless of what this hook can determine
# locally. Once the preflight script actually runs, though, fail CLOSED
# (deny) on any exit it cannot recognize as a genuine per-sub-check
# verdict -- the same "denying either way is still the safe default"
# policy hooks/check-pr-skill-audit-disclosure.sh already applies for the
# identical situation (PR #1213): a check script crashing is a bug to
# fix, not grounds to silently wave the PR body through.
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

# Same empty-body bypass shape as hooks/check-pr-skill-audit-disclosure.sh
# (an update_pull_request call not touching the body has nothing new to
# check locally), but NOT the same rationale for withholding it from
# create_pull_request: unlike that sibling hook's own skill-audit-
# disclosure check (which does flag a body with no disclosure at all),
# every sub-check this hook actually runs (provenance-disclosure, ascii-
# only, provenance-marker-scan; skill-audit-disclosure is skipped here)
# trivially PASSes an empty body -- verified directly against each
# check's own behavior on "" input, corrected after an independent
# adversarial review of this issue's own implementation found the
# original copy-pasted claim did not hold for this hook's own check set.
# create_pull_request still gets no bypass regardless: it is harmless
# (a guaranteed-PASS preflight run costs only latency, no false deny/pass
# risk), and CI enforces the same checks independently either way.
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

# Same base-branch resolution as hooks/check-pr-skill-audit-disclosure.sh,
# base_is_explicit tracking included: tool_input.base when explicitly
# supplied (create_pull_request always sends it; update_pull_request only
# when changing the base), else the repo's own default branch. On a
# stacked PR (this PR's real base is another feature branch, not the
# default branch), falling back to the default branch would compute
# merge_base against the wrong ancestor and drag the parent branch's own
# already-reviewed changes into --check-diff's scope -- a false deny on
# an outward-facing operation caused entirely by the widened scope, the
# same failure mode hooks/check-pr-skill-audit-disclosure.sh's own
# base_is_explicit gate already exists to prevent (found here by an
# independent adversarial review of this issue's own implementation).
base_branch=$(printf '%s' "$input" | jq -r '.tool_input.base // empty')
base_is_explicit=yes
if [ -z "$base_branch" ]; then
  base_is_explicit=no
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

# base_is_explicit=no means base_branch is only a guessed default-branch
# fallback -- on a stacked PR this is the wrong ancestor. Narrow to the
# two body-only sub-checks (ascii-only, provenance-marker-scan; skill-
# audit-disclosure is always skipped here regardless) rather than pass a
# possibly-wrong --check-diff pair, matching hooks/check-pr-skill-audit-
# disclosure.sh's own degrade-to-narrower-check precedent for the
# identical situation.
check_diff_args=(--check-diff "$merge_base" HEAD)
if [ "$base_is_explicit" = "no" ]; then
  echo "Notice: hooks/check-pr-body-preflight.sh is skipping the diff-dependent provenance-disclosure sub-check because this call supplied no explicit base branch; a stacked PR would otherwise be graded against the wrong ancestor. Falling back to the two body-only sub-checks (CI's own gates always use the PR's real base regardless)." >&2
  check_diff_args=()
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
    "${check_diff_args[@]}" --body-file "$body_file" --skip skill-audit-disclosure 2>&1); then
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

# Every genuinely inconclusive local-git-state case (missing base branch,
# an unfetched origin/<base>, a plugin-only install with no .github/,
# mktemp failure) already exited 0 above, before the preflight script was
# ever invoked. Reaching here means the script actually ran and exited
# non-zero without a recognized 'FAIL ' line -- gitapex_gate_pr_body_
# preflight.py only ever exits 0 (all sub-checks passed/skipped) or 1
# (at least one 'FAIL '-prefixed line, or its own top-level 'error: ...'
# defensive backstop), so this is the check script itself crashing, not a
# genuine disclosure failure. Denying either way is still the safe
# default (an unverifiable body should not silently pass) -- same policy
# hooks/check-pr-skill-audit-disclosure.sh already applies for the
# identical situation (PR #1213); this hook previously failed open here
# instead, an inconsistency an independent adversarial review of this
# issue's own implementation found.
deny "Blocked by hooks/check-pr-body-preflight.sh: gitapex_gate_pr_body_preflight.py exited $preflight_exit without a recognized 'FAIL ' line -- this looks like a bug in the check script itself, not a genuine disclosure failure in your PR body. Output: $preflight_output"

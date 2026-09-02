#!/bin/bash
# PreToolUse hook (matchers: mcp__github__create_pull_request,
# mcp__github__update_pull_request): blocks a PR-body-carrying call whose
# diff adds/modifies a skills/*/SKILL.md but whose body does not disclose
# both battle-testing-a-skill and evaluating-skill-quality audit evidence
# (or an explicit waiver for each).
#
# Applicability is computed locally via git, mirroring (a reduced form
# of) .github/workflows/skill-audit-gate.yml's three-dot diff + D/R100
# exclusion. Unlike that CI workflow, this hook has no
# github.event.pull_request.base.sha to anchor on -- it resolves the PR's
# base branch from tool_input.base when present (create_pull_request
# always supplies it; update_pull_request only when changing the base),
# falling back to the repo's default branch (origin/HEAD) otherwise.
# If that resolution, or the git diff itself, fails for any reason (base
# ref not fetched locally, detached HEAD, etc.), this hook fails OPEN
# (exit 0, warning to stderr) rather than block on inconclusive local
# git state -- CI's skill-audit-gate.yml remains the deterministic
# backstop regardless of what this hook can determine locally.
#
# Two tiers, in this order (issue #874):
#
# 1. **Full**, when .github/scripts/gitapex_gate_skill_audit_disclosure.py
#    and .github/scripts/gitapex_compute_skill_audit_flags.py are both
#    present -- i.e. when running inside this repository's own checkout.
#    `--check-diff` reproduces the *whole* CI verdict locally, conditional
#    extensions included (WAIVED-rejection on a description change,
#    eval-coverage, security-relevance, design-doc coverage, changed
#    checker scripts, changed deterministic gates), by calling the same
#    gitapex_compute_skill_audit_flags.py module skill-audit-gate.yml's own
#    diff step calls. No second, independently-drifting copy of those
#    rules exists. This is the tier that closes the gap 14 merge
#    retrospectives kept re-raising: before this, an agent discovered it
#    owed an eval-coverage or deterministic-gate-quality line only after a
#    required check failed on an already-open PR.
#
# 2. **Partial**, otherwise -- the self-contained
#    gitapex_check_skill_audit_disclosure_or_waiver.py sibling bundled
#    beside this hook, which checks the base two-audit disclosure only.
#    Per docs/repository-layout.md, only skills/ and hooks/ are deployed
#    when this repository is installed as a plugin; .github/ never is, so
#    tier 1 is simply absent there and this tier is what a consumer
#    repository gets (see that sibling script's own docstring, and
#    hooks/check-issue-acm-disclosure.sh's docstring for the same
#    pattern).
#
# Tier 1 also owns its own applicability test, so it runs before the
# SKILL.md-only applicability check below: CI's scope includes design-doc,
# checker-script and gate changes that touch no SKILL.md at all. A tier-1
# run that cannot complete (missing script, unreadable registry, git state
# it cannot resolve) falls through to tier 2 with a warning rather than
# denying -- the same fail-open-on-inconclusive-local-state posture as the
# base-branch and git-diff resolution above. CI remains authoritative.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-write.sh), same as
# hooks/check-issue-acm-disclosure.sh.

set -euo pipefail

# Issue #1208: this deny path must not itself depend on jq -- if jq is
# missing from PATH entirely, every jq call below would crash under
# `set -e` with exit 127 ("command not found"), an exit code Claude Code's
# PreToolUse contract treats as non-blocking (the tool call proceeds
# unchecked). Checked first, via a fixed, statically-escaped JSON literal
# (no interpolation, so no JSON-escaping risk), same pattern as
# hooks/check-pr-issue-acm-disclosure.sh's own jq-missing guard.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-pr-skill-audit-disclosure.sh: jq is not available on PATH -- cannot verify skill audit disclosure. Failing closed.\"}" >&2
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
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

# Found by code review (PR #1213): jq -r never errors on a non-string
# `.tool_name` (e.g. `["mcp__github__create_pull_request"]`) -- it
# pretty-prints the JSON form across multiple lines instead, which then
# never matches the `case` pattern below. That silently falls through as
# "not our tool" (exit 0) rather than failing closed on a malformed field
# this gate structurally depends on -- live-confirmed: an array-wrapped
# tool_name let a PR-creation call straight through this hook.
# `.tool_name == null` covers both absent and explicit null (an absent
# key indexes as null in jq); only a present non-string, non-null value
# denies.
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matchers already restrict this hook to
# these two tools, but never trust that alone.
case "$tool_name" in
  mcp__github__create_pull_request|mcp__github__update_pull_request) ;;
  *) exit 0 ;;
esac

# Issue #1208: tool_input could be a non-object (array/string/number/bool)
# in an otherwise well-formed payload, which would crash the
# `.tool_input.body`/`.tool_input.base` accesses below with jq's own
# "Cannot index X with string" runtime error -- same fail-open class as the
# top-level check above. `(.tool_input // {})` alone is not enough: jq's
# `//` treats JSON `false` the same as `null` (both are falsy), so a
# `tool_input: false` payload slipped past that form and crashed the
# extraction below anyway -- found by code review (PR #1213),
# live-confirmed with `jq -e '(.tool_input // {}) | type == "object"'
# <<< '{"tool_input":false}'`, which wrongly reports true. Checking
# `.tool_input == null` directly (true for both absent and explicit null,
# never for `false`) closes that gap.
if ! printf '%s' "$input" | jq -e '(.tool_input == null) or (.tool_input | type == "object")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: tool_input in the payload is not a JSON object. Failing closed."
fi

body=$(printf '%s' "$input" | jq -r '.tool_input.body // empty')

# An update_pull_request call that isn't setting a body has nothing new
# to check locally (it legitimately means "not touching the body").
# create_pull_request's body parameter is optional, though: an absent or
# empty body on a create call is a PR with literally no disclosure at
# all -- exactly the violation this hook exists to catch, not a reason to
# skip it. Only update_pull_request gets the empty-body bypass.
if [ "$tool_name" = "mcp__github__update_pull_request" ] && [ -z "$body" ]; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_script="$script_dir/gitapex_check_skill_audit_disclosure_or_waiver.py"

if [ ! -f "$check_script" ]; then
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: cannot verify skill audit disclosure -- gitapex_check_skill_audit_disclosure_or_waiver.py was not found at $check_script (corrupted or incomplete plugin bundle)."
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

base_branch=$(printf '%s' "$input" | jq -r '.tool_input.base // empty')
base_is_explicit=yes
if [ -z "$base_branch" ]; then
  base_is_explicit=no
  base_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed -E 's#^origin/##') || true
  # tool_input.base is absent on most update_pull_request calls (it's
  # only sent when the base is itself being changed), so falling back to
  # the repo's default branch is the common, expected path -- but for a
  # stacked PR whose real base is NOT the default branch, this computes
  # applicability against the wrong ancestor. That degraded case is
  # otherwise silent (indistinguishable from a correct run); this warning
  # at least makes it visible rather than a quiet wrong answer. CI's
  # skill-audit-gate.yml always uses the PR's real base, regardless.
  if [ -n "$base_branch" ] && [ "$tool_name" = "mcp__github__update_pull_request" ]; then
    echo "Warning: hooks/check-pr-skill-audit-disclosure.sh has no explicit base branch for this update_pull_request call; falling back to the default branch ($base_branch). If this PR's real base is a different branch, this local pre-check's applicability determination may be wrong (CI's skill-audit-gate.yml always uses the PR's real base regardless)." >&2
  fi
fi

if [ -z "$base_branch" ]; then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not resolve a base branch locally; skipping the local pre-check (CI's skill-audit-gate.yml will still catch this)." >&2
  exit 0
fi

if ! merge_base=$(git merge-base "origin/${base_branch}" HEAD 2>/dev/null); then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not resolve origin/${base_branch} locally (not fetched?); skipping the local pre-check (CI's skill-audit-gate.yml will still catch this)." >&2
  exit 0
fi

# --- tier 1: the full CI verdict, reproduced locally ---
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=""
full_gate="${repo_root}/.github/scripts/gitapex_gate_skill_audit_disclosure.py"
flag_module="${repo_root}/.github/scripts/gitapex_compute_skill_audit_flags.py"

# Tier 1 requires an *explicitly supplied* base, deliberately, and this is
# a narrowing rather than caution for its own sake. The default-branch
# fallback above is already documented as computing against the wrong
# ancestor for a stacked PR (one whose real base is another feature
# branch). Tier 2 has lived with that since it only ever scoped
# skills/*/SKILL.md; tier 1 scopes design docs, checker scripts and every
# registered gate, so on a stacked PR the fallback drags the *parent
# branch's* changes into scope and denies a body update for disclosure the
# PR does not owe. That is a false deny on an outward-facing operation,
# caused entirely by the widened scope. create_pull_request always sends
# `base`, so the path that matters most keeps full coverage; an
# update_pull_request that also sends it keeps coverage too. Everything
# else falls through to tier 2's narrower, pre-existing exposure.
if [ "$base_is_explicit" = "no" ]; then
  echo "Notice: hooks/check-pr-skill-audit-disclosure.sh is skipping the full local pre-check because this call supplied no explicit base branch; a stacked PR would otherwise be graded against the wrong ancestor. Falling back to the bundled base two-audit check (CI's skill-audit-gate.yml uses the PR's real base regardless)." >&2
fi

if [ "$base_is_explicit" = "yes" ] && [ -n "$repo_root" ] && [ -f "$full_gate" ] && [ -f "$flag_module" ]; then
  # Issue #1566, closes #1547(a): before attempting the bare `python3
  # "$full_gate"` invocation below, confirm every third-party package the
  # skill-audit-disclosure gate's own .gitapex/ssot.json registry entry
  # declares under preconditions.requires_python_packages is actually
  # importable by that same python3. Without this, a missing dependency
  # (e.g. pydantic not installed) made $full_gate crash with an
  # ImportError -- no recognizable FAIL: line -- which the existing
  # fall-through below silently downgrades to a *warning* and degrades to
  # tier 2's weaker, SKILL.md-only check, never telling the caller a
  # dependency was missing at all. The required package list is read from
  # the registry itself (never hardcoded) so a future added/removed
  # requirement is picked up automatically.
  #
  # Read via a base64-encoded jq stream into a bash array, the same
  # pattern hooks/check-bash-safety.sh already uses for a JSON string
  # array (issue #1375) -- a package name containing a shell-hazardous
  # byte cannot corrupt this loop's own field splitting.
  ssot_json="${repo_root}/.gitapex/ssot.json"
  precondition_script="$script_dir/gitapex_check_python_precondition.py"
  required_packages=()
  while IFS= read -r encoded_pkg; do
    [ -z "$encoded_pkg" ] && continue
    required_packages+=("$(printf '%s' "$encoded_pkg" | base64 -d)")
  done < <(jq -r '
      (.gates // [])
      | map(select(.id == "skill-audit-disclosure"))
      | (.[0].preconditions.requires_python_packages // [])[]
      | @base64
    ' "$ssot_json" 2>/dev/null)

  # Fail open (skip this check entirely, fall straight into the existing
  # tier-1 invocation below) when the registry cannot be read, declares no
  # required packages for this gate, or this checker's own sibling script
  # is missing (a corrupted local checkout) -- none of those is the
  # dependency-missing cause this check exists to catch, and every OTHER
  # tier-1 failure cause must keep falling through to tier 2 unchanged, as
  # documented above.
  if [ "${#required_packages[@]}" -gt 0 ] && [ -f "$precondition_script" ]; then
    # `--` before the array expansion: a registry-declared package name
    # that happens to look like a flag (e.g. a value equal to `--help` or
    # starting with `-`) must be treated as inert data, never as argparse
    # option syntax -- found by review-persona's own step-6 screening of
    # this task's diff. Without it, such a name could make the
    # precondition script exit 0 (its own --help path) or reject with a
    # usage error, either of which this block would otherwise read as "no
    # missing packages" and silently skip the new deny path.
    precondition_json=$(python3 "$precondition_script" -- "${required_packages[@]}" 2>/dev/null) || true
    if ! missing_packages=$(printf '%s' "$precondition_json" | jq -r '.missing // [] | join(", ")' 2>/dev/null); then
      # The precondition subprocess produced no parseable JSON (crashed,
      # timed out, or was rejected by argparse) -- matching this file's
      # own established convention of an explicit Warning: line on every
      # other inconclusive fallback, rather than a silent skip. CI's
      # skill-audit-gate.yml remains the authoritative backstop
      # regardless, same as every other local-pre-check gap in this file.
      echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not parse gitapex_check_python_precondition.py's own output; skipping the dependency-precondition pre-check (CI's skill-audit-gate.yml remains authoritative)." >&2
      missing_packages=""
    fi
    if [ -n "$missing_packages" ]; then
      deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: this gate's own local pre-check (gitapex_gate_skill_audit_disclosure.py) requires the following Python package(s), which python3 cannot import: ${missing_packages}. Run 'uv sync --group dev' to install them, then re-invoke this operation (create/update the pull request again)."
    fi
  fi

  # Found by code review (PR #1213): an unguarded `body_file=$(mktemp)`
  # crashes the whole script under `set -e` (e.g. an unwritable/full
  # /tmp), past every deny() and past this block's own fall-through-to-
  # tier-2 design, with mktemp's own exit code -- an exit Claude Code's
  # PreToolUse contract treats as non-blocking, i.e. an ungated pass
  # through the local pre-check instead of the intended degrade-to-tier-2
  # path every OTHER tier-1 failure in this block already takes.
  # Live-confirmed: `TMPDIR=/nonexistent-dir bash check-pr-skill-audit-
  # disclosure.sh` crashed with mktemp's own exit 1, not falling through.
  if body_file=$(mktemp 2>/dev/null); then
    printf '%s' "$body" >"$body_file"
    if full_output=$(cd "$repo_root" && python3 "$full_gate" \
        --check-diff "$merge_base" HEAD --body-file "$body_file" 2>&1); then
      full_exit=0
    else
      full_exit=$?
    fi
    rm -f "$body_file"

    if [ "$full_exit" -eq 0 ]; then
      exit 0
    fi

    # `grep -q` closes stdin on first match, which can SIGPIPE a still-writing
    # upstream; under `set -o pipefail` (set above) that upstream's nonzero
    # status outranks grep's own zero exit and turns a real match into a false
    # "not found" -- i.e. a genuine deny silently downgraded to the warning
    # fall-through below. This repository banned the pattern in
    # https://github.com/tvna/gitapex/pull/428#discussion_r3654041066 and
    # skill-audit-gate.yml's own history records the same fix; `-q` is dropped
    # and the output redirected instead, so grep always reads to completion.
    if printf '%s' "$full_output" | grep '^FAIL:' >/dev/null; then
      # The exact command is in the message on purpose (dimension 17): the
      # whole point of issue #874 is that an agent can now iterate on the
      # disclosure locally instead of pushing and reading a failed check, and
      # a deny that does not say how to re-run the verdict leaves it doing
      # the latter anyway.
      deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: this PR's diff requires skill-audit disclosure evidence its body does not carry. This is the same verdict .github/workflows/skill-audit-gate.yml will report, computed locally before the push. Fix the '## Skill audit evidence' section, then re-check with:

  python3 .github/scripts/gitapex_gate_skill_audit_disclosure.py --check-diff ${merge_base} HEAD --body-file <path>

$full_output"
    fi

    # Not a verdict on the body: the local flag computation itself could not
    # complete (unreadable gate registry, a ref this checkout cannot resolve,
    # a bug in the wrapper). Fall through to the bundled partial check rather
    # than denying on an answer that was never computed.
    echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not complete the full local pre-check (exit $full_exit); falling back to the bundled base two-audit check (CI's skill-audit-gate.yml remains authoritative). Output: $full_output" >&2
  else
    echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not create a temp file for the tier-1 body check (mktemp failed); falling back to the bundled base two-audit check (CI's skill-audit-gate.yml remains authoritative)." >&2
  fi
fi

# --- tier 2: the bundled, SKILL.md-only base check ---
# Found by code review (PR #1213): same unguarded-mktemp-crashes-under-
# set-e class as the tier-1 body_file above -- an unwritable/full /tmp
# would otherwise crash past this hook's own "skip the local pre-check,
# CI remains authoritative" fallback with mktemp's own exit code, an
# exit Claude Code's PreToolUse contract treats as non-blocking.
if ! diff_error=$(mktemp 2>/dev/null); then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh could not create a temp file for git-diff error capture (mktemp failed); skipping the local pre-check (CI's skill-audit-gate.yml will still catch this)." >&2
  exit 0
fi
if ! diff_output=$(git diff --name-status "${merge_base}...HEAD" -- 'skills/*/SKILL.md' 2>"$diff_error"); then
  echo "Warning: hooks/check-pr-skill-audit-disclosure.sh's local git diff failed; skipping the local pre-check (CI's skill-audit-gate.yml will still catch this). $(cat "$diff_error")" >&2
  rm -f "$diff_error"
  exit 0
fi
rm -f "$diff_error"
changed=$(printf '%s\n' "$diff_output" | grep -vE '^(D|R100)[[:space:]]' || true)

if [ -z "$changed" ]; then
  exit 0
fi

if check_output=$(printf '%s' "$body" | python3 "$check_script" 2>&1); then
  check_exit=0
else
  check_exit=$?
fi

if [ "$check_exit" -eq 0 ]; then
  exit 0
fi

if printf '%s' "$check_output" | grep '^FAIL:' >/dev/null; then
  deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: this PR's diff adds/modifies a skills/*/SKILL.md but its body does not disclose both battle-testing-a-skill and evaluating-skill-quality audit evidence (a verdict or waiver for each). Add a '## Skill audit evidence' section -- see .github/scripts/gitapex_gate_skill_audit_disclosure.py for the exact format CI enforces."
fi

# gitapex_check_skill_audit_disclosure_or_waiver.py only ever exits 0 (PASS) or 1
# with a 'FAIL: ...' stderr message for a genuine disclosure failure --
# anything else (a different exit code, or exit 1 with no 'FAIL:' line,
# e.g. an uncaught traceback) means the check script itself crashed, not
# a verdict on the PR body. Denying either way is still the safe default
# (an unverifiable body should not silently pass), but the message must
# say so plainly rather than blame the PR body for a bug in the check
# script.
deny "Blocked by hooks/check-pr-skill-audit-disclosure.sh: gitapex_check_skill_audit_disclosure_or_waiver.py exited $check_exit without a recognized FAIL message -- this looks like a bug in the check script itself, not a genuine disclosure failure in your PR body. Output: $check_output"

#!/bin/bash
# PreToolUse hook (matcher: Bash) enforcing four skill-defined policies:
#
#   1. [evaluating-skill-quality] SKILL.md -- block package/plugin install
#      commands run via Bash.
#   2. [planning-a-branch-from-an-issue] SKILL.md -- block enabling auto-merge (a subset of
#      the `gh pr merge` deny rule below; --auto is not special-cased).
#   3. [planning-a-branch-from-an-issue] references/github-issue-workflow.md -- block direct
#      CLI GitHub write commands (gh issue/pr create|edit|close|comment|merge,
#      gh api -X POST/PUT/PATCH/DELETE).
#   4. [outward-artifact-preflight] SKILL.md -- before `git push`, run
#      gitapex_scan_provenance.py against the outgoing commits and warn (not block)
#      if it flags anything -- the script surfaces candidates, it does not
#      decide, so a hit does not stop the push.
#
# Issue #1326 (Stage 1): the actual command-classification logic moved to
# hooks/gitapex_check_bash_safety.py, a token-based classifier (shlex,
# stdlib-only) that matches against bash's own dequoted token stream
# instead of a raw-text regex substring scan. The predecessor, purely
# regex-based version was live-confirmed bypassable by quote-splitting,
# ${IFS} substitution, and several classes of variable/array/positional-
# parameter indirection that still resolved to the exact denied
# invocation once bash actually expanded them -- see that module's own
# docstring for the full analysis and its own disclosed residual
# limitation. This script is now a thin bash+jq wrapper: payload-shape
# validation and the final PreToolUse JSON envelope stay in bash (jq is
# already a hard dependency here), the actual classification is
# delegated to python3.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-bash.sh).

set -euo pipefail

# Issue #1208: this deny path must not itself depend on jq -- if jq is
# missing from PATH entirely (a broken environment, not a malformed
# payload), every jq call below would crash under `set -e` with exit 127
# ("command not found"), an exit code Claude Code's PreToolUse contract
# treats as non-blocking (the tool call proceeds unchecked). Checked first,
# via a fixed, statically-escaped JSON literal (no interpolation, so no
# JSON-escaping risk), same pattern as
# hooks/check-pr-issue-acm-disclosure.sh's own jq-missing guard.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"hookSpecificOutput\": {\"permissionDecision\": \"deny\"}, \"systemMessage\": \"Blocked by hooks/check-bash-safety.sh: jq is not available on PATH -- cannot verify the Bash command. Failing closed.\"}" >&2
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

# Non-blocking counterpart to deny(): surfaces a systemMessage but allows the
# tool call to proceed (exit 0). Used where the underlying check is
# documented as advisory (surfaces candidates, does not decide) rather than
# a deterministic write/read classifier -- see the git-push handling below.
# Found by code review (PR #1213): its only call site interpolates
# $scan_output, the provenance scan's own report over the *entire* outgoing
# push's commit messages and patches -- large enough on a big branch to
# blow the OS's ARG_MAX the same way `deny()`'s own pre-hardening form did
# (live-confirmed: `jq -n --arg msg "$BIG"` on a 3MB string exits 126,
# "Argument list too long"). Under `set -euo pipefail` that crash aborts
# the whole script before `exit 0`, past this function's own advisory
# intent -- the push still proceeds either way (any non-2 exit is
# non-blocking), but the warning itself is silently lost instead of
# reaching the operator. Same `jq -Rs` piped-stdin fix as deny() above.
warn() {
  local reason="$1"
  printf '%s' "$reason" | jq -Rs '{"systemMessage": .}'
  exit 0
}

input=$(cat)

# Issue #1208: a malformed payload (invalid JSON, or valid JSON that isn't
# an object) would otherwise make every field-extraction jq call below exit
# non-zero, crashing past deny() under `set -e` with an exit code Claude
# Code's PreToolUse contract treats as non-blocking -- the same fail-open
# class hooks/check-pr-issue-acm-disclosure.sh's own adversarial review
# found and fixed. Validate the shape up front instead.
if ! printf '%s' "$input" | jq -e 'if type == "object" then . else empty end' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-bash-safety.sh: the tool-call payload on stdin is not a JSON object. Failing closed."
fi

# Found by code review (PR #1213): jq -r never errors on a non-string
# `.tool_name` (e.g. `["Bash"]`) -- it pretty-prints the JSON form across
# multiple lines instead, which then never equals the plain "Bash" string
# the check below compares against. That silently falls through as "not
# our tool" (exit 0) rather than failing closed on a malformed field this
# gate structurally depends on -- live-confirmed: an array-wrapped
# tool_name let a `gh pr merge` command straight through this hook.
# `.tool_name == null` covers both absent and explicit null (an absent
# key indexes as null in jq); only a present non-string, non-null value
# denies.
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-bash-safety.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# Bash, but never trust that alone.
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
classifier="$script_dir/gitapex_check_bash_safety.py"

if [ ! -f "$classifier" ]; then
  deny "Blocked by hooks/check-bash-safety.sh: gitapex_check_bash_safety.py was not found at $classifier (corrupted or incomplete plugin bundle). Failing closed."
fi

# $input is piped on stdin the whole way through, never re-passed as a
# command-line argument -- same ARG_MAX rationale as deny()/warn() above.
# The classifier re-validates tool_input/tool_input.command's own shape
# independently (defense in depth -- same convention
# hooks/check-post-write-provenance.sh already established for its own
# python companion script) rather than trusting this script's own
# tool_name-only validation above.
classifier_exit=0
# python3's own stderr (e.g. bash's own "python3: command not found" launch
# failure when the interpreter is missing) is discarded here, not left to
# leak into this hook's own stderr channel -- deny()'s JSON envelope below
# is the only thing this hook itself ever writes there, and a stray extra
# line ahead of it would break Claude Code's own JSON parse of that stream.
classifier_output=$(printf '%s' "$input" | python3 "$classifier" 2>/dev/null) || classifier_exit=$?
if [ "$classifier_exit" -ne 0 ]; then
  deny "Blocked by hooks/check-bash-safety.sh: gitapex_check_bash_safety.py exited non-zero ($classifier_exit) instead of returning a decision. Failing closed."
fi

if ! printf '%s' "$classifier_output" | jq -e 'type == "object"' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-bash-safety.sh: gitapex_check_bash_safety.py did not return a JSON object. Failing closed."
fi

decision=$(printf '%s' "$classifier_output" | jq -r '.decision // empty')
reason=$(printf '%s' "$classifier_output" | jq -r '.reason // empty')
is_git_push=$(printf '%s' "$classifier_output" | jq -r '.is_git_push // false')

if [ "$decision" = "deny" ]; then
  deny "Blocked by hooks/check-bash-safety.sh: $reason. Per evaluating-skill-quality/SKILL.md's stop boundary and planning-a-branch-from-an-issue/references/github-issue-workflow.md, propose the change instead of running it, or use the platform-integrated tool call for GitHub writes."
fi

if [ "$decision" != "allow" ]; then
  deny "Blocked by hooks/check-bash-safety.sh: gitapex_check_bash_safety.py returned an unrecognized decision '$decision'. Failing closed."
fi

# --- Finding 4: git push gated on gitapex_scan_provenance.py -----------------------
if [ "$is_git_push" = "true" ]; then
  project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  scan_script="$project_dir/skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py"

  if [ ! -f "$scan_script" ]; then
    deny "Blocked by hooks/check-bash-safety.sh: git push requires the outward-artifact-preflight scan, but gitapex_scan_provenance.py was not found at $scan_script."
  fi

  # Determine the commit range being pushed. With an upstream, @{u}..HEAD is
  # exact. On a first push (`git push -u origin newbranch`) there is no
  # upstream, so @{u} errors and the range is empty. Fall back to the
  # merge-base with the best available default branch so the whole branch is
  # scanned, and only if no reference point resolves do we scan full history.
  range='@{u}..HEAD'
  if ! git -C "$project_dir" rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    base=''
    for ref in origin/HEAD origin/main origin/master main master; do
      if git -C "$project_dir" rev-parse --verify --quiet "$ref" >/dev/null 2>&1; then
        base=$(git -C "$project_dir" merge-base "$ref" HEAD 2>/dev/null || true)
        [ -n "$base" ] && break
      fi
    done
    if [ -n "$base" ]; then
      range="$base..HEAD"
    else
      range='HEAD'
    fi
  fi

  content=$(git -C "$project_dir" log --format=%B -p "$range" 2>/dev/null || true)
  if [ -z "$content" ]; then
    content=$(git -C "$project_dir" log --format=%B -p -1 HEAD 2>/dev/null || true)
  fi

  scan_exit=0
  scan_output=$(printf '%s' "$content" | python3 "$scan_script" 2>&1) || scan_exit=$?

  # gitapex_scan_provenance.py's own docstring says it "surfaces candidates, it does
  # not decide" -- a hard deny here would make this mechanical regex the
  # decider, which is exactly what its docstring disclaims. Warn instead of
  # deny: surface every hit so the operator applies the checklist's judgment
  # call, but do not block the push on a mechanical false positive the regex
  # cannot rule out.
  if [ "$scan_exit" -ne 0 ]; then
    warn "outward-artifact-preflight gitapex_scan_provenance.py flagged the outgoing push for review (not blocked -- this scan surfaces candidates, it does not decide) -- $scan_output"
  fi
fi

# --- Finding 5: git checkout/restore gated on a live git-diff check (issue #1375) ---
# `git checkout -- PATH` / `git restore PATH` / `git checkout .` can discard
# uncommitted work on a tracked path with no warning at all. gitapex_check_bash_safety.py's
# own classifier already extracted every candidate path such an invocation
# could discard (its own "git checkout/restore path extraction" section),
# soundly and with no live git call of its own. Unlike Finding 4's own
# advisory provenance scan (surfaces candidates, does not decide -- warn,
# not deny), "does git diff report a difference at this path" is a binary,
# deterministic fact about repo state with no judgment-call axis, so a hit
# here denies.
checkout_restore_paths_count=$(printf '%s' "$classifier_output" | jq -r '.checkout_restore_paths | length // 0')
if [ "$checkout_restore_paths_count" -gt 0 ]; then
  # Read `.cwd` from the ORIGINAL tool-call payload, not
  # `${CLAUDE_PROJECT_DIR:-$(pwd)}` the way Finding 4 above does -- a push
  # is not cwd-relative, but a `git diff -- PATH` pathspec check is, and
  # `.cwd` is Claude Code's own record of the Bash tool call's actual
  # working directory (updated on every `cd` the session runs), not this
  # hook runner's own. Replaying the near-miss's own exact command from a
  # subdirectory must resolve the pathspec against the SAME tree bash
  # itself would use.
  cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
  if [ -z "$cwd" ]; then
    deny "Blocked by hooks/check-bash-safety.sh: this git checkout/restore command needs the PreToolUse payload's own .cwd field to check the right working tree against, but it was missing or empty. Failing closed."
  fi
  if ! git -C "$cwd" rev-parse --show-toplevel >/dev/null 2>&1; then
    deny "Blocked by hooks/check-bash-safety.sh: '$cwd' is not inside a git working tree -- cannot verify this git checkout/restore command is safe. Failing closed."
  fi
  # A fresh repo with no commits yet has no HEAD to diff against
  # (`git diff --quiet HEAD -- PATH` fails with "fatal: bad revision
  # 'HEAD'", confirmed live, exit 128, not the "differs" exit 1) --
  # compare against git's own well-known empty-tree object instead, so a
  # genuinely clean fresh repo is not denied outright.
  if git -C "$cwd" rev-parse --verify -q HEAD >/dev/null 2>&1; then
    diff_base="HEAD"
  else
    diff_base="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
  fi
  # Disclosed, accepted residual (round-3 independent review, issue #1375):
  # a bare `git checkout -- PATH` / `git restore PATH` restores the
  # WORKING TREE from the INDEX, not from HEAD -- so a path that was
  # `git add`-ed with no further unstaged edit (worktree == index, but
  # index != HEAD) is a genuine no-op checkout/restore, yet this check
  # diffs against HEAD/the empty tree and denies it as if it would
  # discard something. Confirmed live: stage a change with no further
  # edit, then `git checkout -- PATH` changes nothing on disk, but this
  # diff_base comparison still reports a difference. Deliberately left
  # as-is rather than special-cased per flag combination (`--staged`
  # alone already skips this check entirely below, since unstaging alone
  # never discards file content) -- the failure direction is safe
  # (over-denial only, matching every other explicit-source variant this
  # check already treats the same conservative way; it never under-denies
  # a real discard), and the existing deny message's `git checkout -m --`
  # / `git add` remedies still resolve it as a false alarm the caller can
  # work around.
  # Fed via process substitution (`< <(...)`), not a pipe
  # (`... | while read`) -- bash runs a pipe's right-hand side in a
  # subshell, where `deny`'s own `exit 2` would only exit that subshell,
  # letting this script fall through to its own `exit 0` past the loop
  # instead of actually denying. Process substitution keeps the loop in
  # THIS shell, so `exit 2` inside it really does exit the whole script.
  while IFS= read -r encoded_path; do
    [ -z "$encoded_path" ] && continue
    # Each line is one base64-encoded path (issue #1375: a genuine JSON
    # array from the classifier, base64-encoded here too) -- a path
    # containing a newline or other shell-hazardous byte would otherwise
    # split across `read` calls or corrupt this loop's own field
    # splitting; base64 has neither.
    path=$(printf '%s' "$encoded_path" | base64 -d)
    diff_exit=0
    git -C "$cwd" diff --quiet "$diff_base" -- "$path" || diff_exit=$?
    if [ "$diff_exit" -eq 1 ]; then
      deny "Blocked by hooks/check-bash-safety.sh: this git checkout/restore command would discard uncommitted changes at '$path'. Stash first (git stash push -- '$path') if this is not resolving a merge conflict; if it is, resolve and git add the path, or use git checkout -m -- '$path' to regenerate conflict markers instead of discarding them."
    elif [ "$diff_exit" -ne 0 ]; then
      deny "Blocked by hooks/check-bash-safety.sh: could not verify whether '$path' has uncommitted changes (git diff exited $diff_exit). Failing closed."
    fi
  done < <(printf '%s' "$classifier_output" | jq -r '.checkout_restore_paths[] | @base64')
fi

exit 0

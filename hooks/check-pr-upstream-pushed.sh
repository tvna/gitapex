#!/bin/bash
# PreToolUse hook (matcher: mcp__github__create_pull_request) backing
# issue #187: block a PR-open call for a branch that has no upstream
# configured, or has local commits not yet pushed to its upstream -- both
# reproduce #187's "No commits between main and <branch>" failure (opening
# a PR for a branch GitHub can't see any commits on because it was never
# pushed).
#
# This is a local git-state precondition and only has an opinion when
# tool_input.head is the branch currently checked out in this working
# tree (this repo's git-branch-per-issue convention normally guarantees
# that -- see skills/driving-pr-to-merge/SKILL.md step 0). Any local git
# state this hook cannot resolve to a real answer -- not inside a work
# tree, detached HEAD, tool_input.head not the checked-out branch -- fails
# OPEN (exit 0, stderr warning), mirroring
# hooks/check-pr-skill-audit-disclosure.sh's fail-open philosophy.
#
# Unlike that hook, there is no CI backstop for this failure mode -- but
# there doesn't need to be one: the create_pull_request call this hook
# gates is itself the ground truth (GitHub rejects an unpushed/behind
# branch with its own "No commits between..." error). Failing open here
# never hides the underlying problem; it just means the agent hits
# GitHub's raw error instead of this hook's clearer one for that one call,
# no worse than if this hook did not exist.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stderr + exit 2,
# same convention as check-issue-acm-disclosure.sh and
# check-pr-skill-audit-disclosure.sh.

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# mcp__github__create_pull_request, but never trust that alone.
if [ "$tool_name" != "mcp__github__create_pull_request" ]; then
  exit 0
fi

head_branch=$(printf '%s' "$input" | jq -r '.tool_input.head // empty')

deny() {
  jq -n --arg msg "$1" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

warn_open() {
  echo "Warning: hooks/check-pr-upstream-pushed.sh $1; skipping the local upstream/push precondition check (issue #187)." >&2
  exit 0
}

[ -n "$head_branch" ] || warn_open "found no tool_input.head on this call"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || warn_open "is not running inside a git work tree"

current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) \
  || warn_open "could not resolve the current branch (git rev-parse --abbrev-ref HEAD failed)"

[ "$current_branch" != "HEAD" ] \
  || warn_open "found a detached HEAD, not a branch"

[ "$current_branch" = "$head_branch" ] \
  || warn_open "found tool_input.head ($head_branch) does not match the currently checked-out branch ($current_branch) -- cannot verify a branch that is not checked out here"

upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) \
  || deny "Blocked by hooks/check-pr-upstream-pushed.sh (PR-open precondition, issue #187): branch '$current_branch' has no upstream configured -- GitHub cannot see any commits on an unpushed branch, which reproduces issue #187's 'No commits between main and <branch>' failure. Run 'git push -u origin $current_branch' to set the upstream, then retry opening the PR."

local_sha=$(git rev-parse HEAD 2>/dev/null) \
  || warn_open "could not resolve the local HEAD SHA (git rev-parse HEAD failed)"
upstream_sha=$(git rev-parse '@{u}' 2>/dev/null) \
  || warn_open "resolved an upstream ($upstream) but could not resolve its SHA (git rev-parse @{u} failed)"

[ "$local_sha" = "$upstream_sha" ] \
  || deny "Blocked by hooks/check-pr-upstream-pushed.sh (PR-open precondition, issue #187): branch '$current_branch' has local commits not yet pushed to its upstream ($upstream) -- opening this PR now would reproduce issue #187's 'No commits between main and <branch>' failure for the missing commits, or open it against a stale remote branch. Run 'git push' to bring $upstream up to date, then retry opening the PR."

exit 0

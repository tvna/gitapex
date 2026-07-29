#!/bin/bash
# PreToolUse hook (matcher: mcp__github__create_pull_request) backing
# issue #187: block a PR-open call for a branch that has no resolvable
# upstream, or has local commits not yet pushed to it -- both reproduce
# #187's "No commits between <base> and <branch>" failure (opening a PR
# for a branch GitHub can't see any commits on because it was never
# pushed).
#
# Verifies tool_input.head directly via its refs/heads/<branch> ref,
# independent of whatever is currently checked out in this working tree
# -- a PR can legitimately be opened for a branch other than the one
# checked out (scripted PR creation, multiple worktrees). "Pushed" is
# checked via `git merge-base --is-ancestor <branch> <branch>@{u}`, not
# SHA equality: a local branch that is merely behind its already-pushed
# upstream (e.g. after a `git fetch` with no local merge) has zero
# unpushed commits and must not be denied, only a branch with commits
# not yet present upstream (ahead or diverged) actually reproduces #187.
#
# Any local git state this hook cannot resolve to a real answer -- not
# inside a work tree, tool_input.head not a local branch (e.g. a
# fork/cross-repo head), an inconclusive merge-base result -- fails OPEN
# (exit 0, stderr warning), mirroring
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
base_branch=$(printf '%s' "$input" | jq -r '.tool_input.base // empty')
base_display=${base_branch:-<base>}

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

git show-ref --verify --quiet "refs/heads/$head_branch" 2>/dev/null \
  || warn_open "could not find a local branch named '$head_branch' (not inside a git work tree, no such local branch here, or tool_input.head names a fork/cross-repo head this local checkout cannot verify)"

upstream=$(git rev-parse --abbrev-ref --symbolic-full-name "${head_branch}@{u}" 2>/dev/null) \
  || deny "Blocked by hooks/check-pr-upstream-pushed.sh (PR-open precondition, issue #187): branch '$head_branch' has no resolvable upstream (either never configured, or its remote-tracking ref is stale/missing locally) -- GitHub cannot see commits on a branch with no visible upstream, which reproduces issue #187's 'No commits between $base_display and $head_branch' failure. Run 'git push -u origin $head_branch' to (re-)establish the upstream, then retry opening the PR."

if git merge-base --is-ancestor "refs/heads/$head_branch" "${head_branch}@{u}" 2>/dev/null; then
  ancestor_rc=0
else
  ancestor_rc=$?
fi

case "$ancestor_rc" in
  0) exit 0 ;;
  1) deny "Blocked by hooks/check-pr-upstream-pushed.sh (PR-open precondition, issue #187): branch '$head_branch' has local commits not yet pushed to its upstream ($upstream) -- opening this PR now would reproduce issue #187's 'No commits between $base_display and $head_branch' failure for the missing commits. Run 'git push' to bring $upstream up to date, then retry opening the PR." ;;
  *) warn_open "could not compare '$head_branch' to its upstream ($upstream) via git merge-base --is-ancestor (unexpected exit $ancestor_rc)" ;;
esac

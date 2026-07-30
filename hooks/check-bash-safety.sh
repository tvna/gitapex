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
#      scan_provenance.py against the outgoing commits and warn (not block)
#      if it flags anything -- the script surfaces candidates, it does not
#      decide, so a hit does not stop the push.
#
# Denies via the PreToolUse hookSpecificOutput JSON on stdout AND exit 2 /
# stderr (both conventions, for defense in depth -- see plugin-dev's
# hook-development skill, examples/validate-bash.sh).

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the hooks.json matcher already restricts this hook to
# Bash, but never trust that alone.
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

if [ -z "$command" ]; then
  exit 0
fi

lc_command=$(printf '%s' "$command" | tr '[:upper:]' '[:lower:]')

deny() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"hookSpecificOutput": {"permissionDecision": "deny"}, "systemMessage": $msg}' >&2
  exit 2
}

# Non-blocking counterpart to deny(): surfaces a systemMessage but allows the
# tool call to proceed (exit 0). Used where the underlying check is
# documented as advisory (surfaces candidates, does not decide) rather than
# a deterministic write/read classifier -- see the git-push handling below.
warn() {
  local reason="$1"
  jq -n --arg msg "$reason" \
    '{"systemMessage": $msg}'
  exit 0
}

# --- Shared boundary: pre-command anchor that also swallows an absolute or
# relative path prefix -----------------------------------------------------
# The boundary is "start of string, or any character that cannot be part of a
# command-name token" -- i.e. anything outside [[:alnum:]_.-]. A negated
# command-token class anchors regardless of what precedes the verb (quote,
# paren, backtick, space, etc.), so shell-indirection wrappers like
# `bash -c "pip install x"` or `eval 'gh pr merge 1'` still match. The
# optional path-prefix group then lets the anchor land right before the bare
# verb name regardless of a leading directory, so `/usr/bin/pip install`,
# `./pip install`, etc. still match. (Obfuscation that hides the verb itself
# -- base64-piped-to-sh and the like -- is out of reach of any regex gate.)
cmd_boundary='(^|[^[:alnum:]_.-])([[:alnum:]_.-]*/)*'

# --- Finding 1: package/plugin install verbs -------------------------------
# Case-insensitive, word/space-boundary anchored so `pipx install`, a path
# containing "install", or `cargo install-update` do not false-positive.
# Each alternative ends exactly at the verb/subcommand token (no baked-in
# trailing boundary of its own) so the single outer ([[:space:]]|$) suffix
# applies uniformly to every alternative, including short forms like
# `npm i <pkg>`.
install_re="${cmd_boundary}(pip3?[[:space:]]+install|npm[[:space:]]+install|npm[[:space:]]+i|yarn[[:space:]]+add|pnpm[[:space:]]+add|go[[:space:]]+install|brew[[:space:]]+install|apt(-get)?[[:space:]]+install|gem[[:space:]]+install|cargo[[:space:]]+install|uv[[:space:]]+pip[[:space:]]+install|uv[[:space:]]+install|uv[[:space:]]+add|plugin[[:space:]]+install)([[:space:]]|\$)"

if [[ "$lc_command" =~ $install_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: command matches a package/plugin install pattern. Per evaluating-skill-quality/SKILL.md's stop boundary, installs require the operator's explicit go-ahead -- propose the install instead of running it."
fi

# --- Findings 2 & 3: direct CLI GitHub write commands ----------------------
# Denylist the write/mutating subcommands, not just create|edit|close|
# comment|merge. Read subcommands (list, view, status, diff, checks,
# checkout) stay allowed; delete, reopen, transfer, pin/unpin, lock/unlock,
# develop (issue), review, and ready (pr) are mutating and denied too.
gh_issue_re="${cmd_boundary}gh[[:space:]]+issue[[:space:]]+(create|edit|close|comment|delete|reopen|transfer|pin|unpin|lock|unlock|develop)([[:space:]]|\$)"
gh_pr_re="${cmd_boundary}gh[[:space:]]+pr[[:space:]]+(create|edit|close|comment|merge|review|ready|reopen|lock|unlock|update-branch)([[:space:]]|\$)"
gh_api_re="${cmd_boundary}gh[[:space:]]+api([[:space:]]|\$)"
# Matches -X/--method (any case, already lowercased upstream) followed by
# POST/PUT/PATCH/DELETE in any of the three flag syntaxes gh/getopt accept:
#   - whitespace-separated:  -X POST      / --method POST
#   - equals-form long flag:              --method=POST
#   - attached short flag:   -XPOST
gh_api_write_method_re='(-x[[:space:]]*=?[[:space:]]*|--method[[:space:]=]+)(post|put|patch|delete)([[:space:]]|$)'
# Finding: `gh api graphql` has no -X/--method flag at all (GraphQL uses a
# single POST endpoint regardless of query vs. mutation), so the method-flag
# check above can never catch a graphql mutation. Heuristically flag any
# `gh api graphql` invocation whose argument string contains the literal
# "mutation" keyword (case-insensitive via lc_command) -- a plain `query{...}`
# read has no reason to contain that word. This cannot fully parse GraphQL in
# bash, but it catches the common `-f query='mutation{...}'` write pattern.
gh_api_graphql_re="${cmd_boundary}gh[[:space:]]+api[[:space:]]+graphql([[:space:]]|\$)"

if [[ "$lc_command" =~ $gh_issue_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: direct 'gh issue' write command. Per planning-a-branch-from-an-issue/references/github-issue-workflow.md, prefer the platform-integrated tool call (connected GitHub app/MCP) instead of shelling out to the gh CLI for writes."
fi

if [[ "$lc_command" =~ $gh_pr_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: direct 'gh pr' write command (create/edit/close/comment/merge, including auto-merge via 'gh pr merge --auto'). Per planning-a-branch-from-an-issue/SKILL.md and references/github-issue-workflow.md, merging (including enabling auto-merge) and other PR writes are a separate, explicit human or CI decision -- use the platform-integrated tool call instead of the gh CLI."
fi

if [[ "$lc_command" =~ $gh_api_re ]] && [[ "$lc_command" =~ $gh_api_write_method_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: 'gh api' write call (-X/--method POST/PUT/PATCH/DELETE). Per planning-a-branch-from-an-issue/references/github-issue-workflow.md, never shell out to a command-line GitHub tool directly for writes -- use the platform-integrated tool call or an approved read-only wrapper."
fi

if [[ "$lc_command" =~ $gh_api_graphql_re ]] && [[ "$lc_command" == *mutation* ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: 'gh api graphql' call containing a 'mutation' keyword. GraphQL mutations are writes regardless of the missing -X/--method flag. Per planning-a-branch-from-an-issue/references/github-issue-workflow.md, never shell out to a command-line GitHub tool directly for writes -- use the platform-integrated tool call or an approved read-only wrapper."
fi

# Finding: `gh api <endpoint> -f key=val` (or -F/--field/--raw-field) performs
# an implicit POST whenever field flags are present -- no -X/--method flag is
# required, so the write-method check above never sees it. gh's own
# convention is that field flags mean a write; a GET-only call has no reason
# to carry one. Scoped to non-graphql `gh api` calls -- `gh api graphql -f
# query='query{...}'` legitimately uses -f to pass a plain read query as a
# variable, and that case is handled by the mutation-keyword check above,
# not this one.
gh_api_field_flag_re='(^|[[:space:]])(-f|--field|--raw-field)([[:space:]=]|[a-z_]|$)'

if [[ "$lc_command" =~ $gh_api_re ]] && ! [[ "$lc_command" =~ $gh_api_graphql_re ]] && [[ "$lc_command" =~ $gh_api_field_flag_re ]]; then
  deny "Blocked by hooks/check-bash-safety.sh: 'gh api' call with a field flag (-f/-F/--field/--raw-field). Field flags imply an implicit POST/write in gh's own convention, with no -X/--method flag required. Per planning-a-branch-from-an-issue/references/github-issue-workflow.md, never shell out to a command-line GitHub tool directly for writes -- use the platform-integrated tool call or an approved read-only wrapper."
fi

# --- Finding 4: git push gated on scan_provenance.py -----------------------
push_re="${cmd_boundary}git[[:space:]]+push([[:space:]]|\$)"

if [[ "$lc_command" =~ $push_re ]]; then
  project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  scan_script="$project_dir/skills/outward-artifact-preflight/scripts/scan_provenance.py"

  if [ ! -f "$scan_script" ]; then
    deny "Blocked by hooks/check-bash-safety.sh: git push requires the outward-artifact-preflight scan, but scan_provenance.py was not found at $scan_script."
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

  # scan_provenance.py's own docstring says it "surfaces candidates, it does
  # not decide" -- a hard deny here would make this mechanical regex the
  # decider, which is exactly what its docstring disclaims. Warn instead of
  # deny: surface every hit so the operator applies the checklist's judgment
  # call, but do not block the push on a mechanical false positive the regex
  # cannot rule out.
  if [ "$scan_exit" -ne 0 ]; then
    warn "outward-artifact-preflight scan_provenance.py flagged the outgoing push for review (not blocked -- this scan surfaces candidates, it does not decide) -- $scan_output"
  fi
fi

exit 0

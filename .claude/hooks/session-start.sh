#!/bin/bash
set -euo pipefail

# Ephemeral-web fallback only. Persistent surfaces (local CLI, CI)
# provision via `nix develop .` (see .github/workflows/toolchain-nix.yml
# and skills/setup-gitapex-toolchain/SKILL.md) and never reach this path.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "gitapex: python3 not found; cannot provision the toolchain this session." >&2
  exit 0
fi

python3 "${CLAUDE_PROJECT_DIR:-.}/skills/setup-gitapex-toolchain/scripts/gitapex_provision_class_b.py" \
  --project-dir "${CLAUDE_PROJECT_DIR:-.}" \
  --env-file "${CLAUDE_ENV_FILE:-}" \
  || echo "gitapex: toolchain provisioning reported a failure; see stderr above. Some binaries or apm install's output may be missing this session." >&2

# Issue #1033: fetch the repository's configured default branch so a fresh
# ephemeral checkout has it available locally without a contributor fetching
# it by hand. The branch name is read from .gitapex/default-branch.json, a
# standalone config file -- not .gitapex/ssot.json, whose own schema and
# drift gate (gitapex_scan_ssot_schema.py) document it as "references and
# routing only, never policy values" and enforce a closed meta{} field set;
# a literal branch-name value has no home there. This file's own presence is
# the gate (a checkout without .gitapex/default-branch.json skips the step),
# mirroring the apm.yml guard the blocks below use for the same purpose.
# Fail-soft like every other step in this script: a missing/malformed config
# file or a network failure must never block session start.
default_branch_config="${CLAUDE_PROJECT_DIR:-.}/.gitapex/default-branch.json"
if [ -f "$default_branch_config" ]; then
  default_branch="$(python3 -c '
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as config_file:
        config = json.load(config_file)
    branch = config.get("default_branch")
    if isinstance(branch, str) and branch:
        print(branch)
except (OSError, ValueError):
    pass
' "$default_branch_config")"
  if [ -z "$default_branch" ]; then
    echo "gitapex: ${default_branch_config} present but default_branch is missing/empty; skipping fetch." >&2
  elif [ "$(git check-ref-format --branch "$default_branch" 2>/dev/null)" != "$default_branch" ]; then
    # git check-ref-format --branch also resolves indirect syntax like
    # "@{-1}" to a commit-ish rather than rejecting it outright, so an
    # exact-match check (not just a zero exit status) is required to catch
    # that case too, on top of the malformed-name/refspec-shaped cases it
    # rejects on its own.
    echo "gitapex: ${default_branch_config}'s default_branch '${default_branch}' is not a valid exact branch name; skipping fetch." >&2
  else
    # GIT_TERMINAL_PROMPT=0: never block session start on a credential
    # prompt. timeout: bound a stalled transport the same way, rather than
    # hanging indefinitely. Both fail into the same non-fatal warning as
    # every other failure mode here. Destination refspec
    # (+refs/heads/<branch>:refs/remotes/origin/<branch>), not a
    # source-only "refs/heads/<branch>" fetch (issue #1345): a source-only
    # fetch exits 0 in a restricted-refspec checkout (one produced by
    # `git clone --single-branch --branch`) without ever materializing
    # refs/remotes/origin/<branch>, because git only auto-creates a
    # remote-tracking ref when the fetched source matches the checkout's
    # own *configured* remote.origin.fetch refspec pattern -- a
    # restricted-refspec checkout's configured refspec only covers the one
    # branch it was cloned with. Live-verified, not assumed. The
    # destination-refspec form also fetches exactly the branch just
    # validated (never a same-named tag) and is a no-op-safe,
    # no-regression replacement in the already-working wildcard-refspec
    # case.
    GIT_TERMINAL_PROMPT=0 timeout 30s git -C "${CLAUDE_PROJECT_DIR:-.}" fetch origin \
      "+refs/heads/${default_branch}:refs/remotes/origin/${default_branch}" \
      || echo "gitapex: could not fetch default branch '${default_branch}' from origin this session (non-fatal)." >&2
  fi
else
  echo "gitapex: ${default_branch_config} not found; skipping default-branch fetch." >&2
fi

# Issue #749 (follow-up to #725): flake.nix's devShell shellHook
# installs the local prek pre-commit hook automatically for persistent
# surfaces (`nix develop`); this ephemeral-web session had no
# equivalent, so ruff/mypy never ran locally on `git commit` here.
# Best-effort like the step above: no `uv`, no network, or a
# pre-existing non-prek hook all fail soft rather than blocking session
# start. --allow-missing-config covers a checkout of a branch/commit
# that predates .pre-commit-config.yaml.
#
# apm.yml guard, mirroring gitapex_provision_class_b.py's own run_apm_install
# check ("refusing to run apm install outside a gitapex checkout"):
# this script is never wired into a consumer of the gitapex plugin (it
# lives under .claude/hooks/, not hooks/hooks.json's ${CLAUDE_PLUGIN_ROOT}-
# anchored, actually-distributed surface), but that separation is a
# design fact elsewhere, not something this file itself enforces --
# explicit here too, defense-in-depth, rather than relying solely on
# `uv run` failing to spawn an undeclared `prek` if CLAUDE_PROJECT_DIR
# were ever misconfigured to point outside this repository.
if [ ! -f "${CLAUDE_PROJECT_DIR:-.}/apm.yml" ]; then
  echo "gitapex: ${CLAUDE_PROJECT_DIR:-.}/apm.yml not found; skipping prek install (not a gitapex checkout)." >&2
elif command -v uv >/dev/null 2>&1; then
  uv run --directory "${CLAUDE_PROJECT_DIR:-.}" prek -q install --allow-missing-config -t pre-commit -t pre-push \
    || echo "gitapex: prek install reported a failure; the local pre-commit hook may not be active this session." >&2
else
  echo "gitapex: uv not found; cannot install the local pre-commit hook this session." >&2
fi

# Issue #773: gitapex's own skills/* are meant to be invocable in gitapex's
# own sessions via the self-referential plugin marketplace declared in
# .claude/settings.json (extraKnownMarketplaces.gitapex + enabledPlugins,
# issue #737 / commit 3a0e783), separately from apm install above (which
# only ever deploys the two apm devDependencies, never gitapex itself, into
# .claude/skills/). Per Claude Code's own docs
# (code.claude.com/docs/en/plugin-marketplaces), a directory-sourced
# marketplace's registration is normally gated behind an interactive
# per-user trust prompt and lives in ~/.claude/plugins/ (per-user, not part
# of this repo clone) -- a brand-new session's fresh VM never has that
# state, so this best-effort, non-interactive attempt is not expected to
# make a *brand-new* session's skills available (see setup-gitapex-
# toolchain/SKILL.md's "Optional: seed gitapex's own plugin" section for
# the mechanism actually documented to work there); it can only help a
# *resumed* session in the same VM where a prior attempt already ran.
# Fails soft like every other block in this script -- never blocks session
# start, never affects this script's own exit code.
#
# apm.yml guard, same rationale as the prek-install block just above:
# registering a marketplace named "gitapex" only makes sense inside an
# actual gitapex checkout.
#
# </dev/null on both `claude` invocations: this block's own comment above
# concedes the underlying command is documented as normally gated behind
# an interactive trust prompt: closing stdin explicitly, rather than
# inheriting whatever this hook's own stdin happens to be, keeps a stalled
# read from turning into a silent hang that would contradict this block's
# "never blocks session start" claim. Real stdout/stderr is left
# unredirected -- matching the two blocks above, which also let the
# wrapped command's own output flow through rather than suppressing it --
# so a failure is still visible, not just the synthesized fail-soft
# message layered on top.
if [ ! -f "${CLAUDE_PROJECT_DIR:-.}/apm.yml" ]; then
  echo "gitapex: ${CLAUDE_PROJECT_DIR:-.}/apm.yml not found; skipping gitapex's own plugin registration (not a gitapex checkout)." >&2
elif command -v claude >/dev/null 2>&1; then
  claude plugin marketplace add "${CLAUDE_PROJECT_DIR:-.}" --scope project </dev/null \
    || echo "gitapex: could not register gitapex's own plugin marketplace this session (non-fatal; see skills/setup-gitapex-toolchain/SKILL.md)." >&2
  claude plugin install "gitapex@gitapex" </dev/null \
    || echo "gitapex: could not install gitapex's own plugin this session (non-fatal; see skills/setup-gitapex-toolchain/SKILL.md)." >&2

  # Issue #782: the two calls above rewrite the committed
  # .claude/settings.json in place (extraKnownMarketplaces.gitapex.source.path
  # resolved to this container's absolute path, plus key reordering) --
  # documented, not-to-be-committed drift per SKILL.md's "self-plugin
  # registration" section. Left in place, it fails the generic
  # stop-hook-git-check.sh with a false "uncommitted changes" error every
  # session. The actual registration state the plugin needs lives in
  # ~/.claude/plugins/ (per-user), not in this repo-tracked file, so
  # discarding the rewrite here is safe and restores a clean working tree.
  git -C "${CLAUDE_PROJECT_DIR:-.}" checkout -- .claude/settings.json 2>/dev/null \
    || echo "gitapex: could not restore .claude/settings.json after plugin registration; the working tree may show drift this session." >&2
else
  echo "gitapex: claude CLI not found on PATH; skipping gitapex's own plugin registration this session." >&2
fi

exit 0

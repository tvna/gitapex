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
  uv run --directory "${CLAUDE_PROJECT_DIR:-.}" prek -q install --allow-missing-config \
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
if command -v claude >/dev/null 2>&1; then
  claude plugin marketplace add "${CLAUDE_PROJECT_DIR:-.}" --scope project >/dev/null 2>&1 \
    || echo "gitapex: could not register gitapex's own plugin marketplace this session (non-fatal; see skills/setup-gitapex-toolchain/SKILL.md)." >&2
  claude plugin install "gitapex@gitapex" >/dev/null 2>&1 \
    || echo "gitapex: could not install gitapex's own plugin this session (non-fatal; see skills/setup-gitapex-toolchain/SKILL.md)." >&2
else
  echo "gitapex: claude CLI not found on PATH; skipping gitapex's own plugin registration this session." >&2
fi

exit 0

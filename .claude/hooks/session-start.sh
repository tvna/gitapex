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

exit 0

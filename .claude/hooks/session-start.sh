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

python3 "${CLAUDE_PROJECT_DIR:-.}/skills/setup-gitapex-toolchain/scripts/provision_class_b.py" \
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
if command -v uv >/dev/null 2>&1; then
  uv run --directory "${CLAUDE_PROJECT_DIR:-.}" prek -q install --allow-missing-config \
    || echo "gitapex: prek install reported a failure; the local pre-commit hook may not be active this session." >&2
else
  echo "gitapex: uv not found; cannot install the local pre-commit hook this session." >&2
fi

exit 0

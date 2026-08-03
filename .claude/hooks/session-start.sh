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

exit 0

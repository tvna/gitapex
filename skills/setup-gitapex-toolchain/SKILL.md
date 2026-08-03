---
name: setup-gitapex-toolchain
description: Provisions gitapex's flake.nix-pinned Class B toolchain binaries (waza, apm, rtk, betterleaks) and runs apm install, without Nix, for a fresh Claude Code web (ephemeral) session. Use when a session needs these tools and they are not yet on PATH, or to manually re-run/verify provisioning (--verify). Distinct from `nix develop`, which remains the provisioner for persistent surfaces (local CLI, CI) and is not invoked here.
---

# Setup gitapex Toolchain

Provisions the toolchain binaries `flake.nix` pins for the Claude Code web
(ephemeral) surface specifically, where Nix itself is not installed and
disk caching cannot survive across sessions
(`docs/superpowers/plans/2026-07-14-toolchain-foundation.md`: "Nix runs
only in CI... local work uses only curl, sha256sum, python3, and uv").
`flake.nix`'s `classBData`/`mkClassB` blocks are the single source of
truth for tool versions, per-system asset names, and SHA256 pins; this
skill's script parses them at runtime rather than holding its own copy,
so there is never a second pin table that could silently drift from the
flake (see `scripts/provision_class_b.py`'s own parser, and
`.github/scripts/scan_toolchain_pin_drift.py`, which already guards
against exactly this class of drift for CI workflows).

## When this runs

Automatically, via `.claude/hooks/session-start.sh`, only when
`$CLAUDE_CODE_REMOTE=true` (a Claude Code web session). Persistent
surfaces (local CLI, CI) continue to use `nix develop .`
(`.github/workflows/toolchain-nix.yml`) and never invoke this script.

## Manual invocation

```bash
python3 skills/setup-gitapex-toolchain/scripts/provision_class_b.py \
  --project-dir "$(pwd)"
```

Add `--verify` to check already-installed binaries only (no downloads, no
`apm install`). Add `--skip-apm-install` to provision the Class B
binaries without running `apm install` afterward. Add `--tool NAME`
(repeatable) to limit to specific tools.

## Output

- Binaries installed under `${XDG_CACHE_HOME:-~/.cache}/gitapex/toolchain/bin/`.
- `PATH` updated for the session via `$CLAUDE_ENV_FILE` (if set).
- `apm install`'s own output (skills/hooks deployed under `.claude/`),
  unless `--skip-apm-install` was passed.
- A PASS/FAIL summary per tool and per phase on stdout; a non-zero exit
  code if anything failed. Failures never crash the calling SessionStart
  hook (`session-start.sh` always exits 0 itself) -- check this script's
  own exit code and stderr directly to confirm success.

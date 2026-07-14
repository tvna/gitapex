# Toolchain SSoT and the setup-gitapex-toolchain skill

## Context

gitapex depends on external tools that are not vendored: `uv`, `gh`,
`actionlint`, a Python 3.12 runtime, `bun`, `lychee`, `prek`, and the
GitHub-release binaries `waza` (microsoft/waza skill checker), `apm`
(microsoft/apm; regenerates `CLAUDE.md`/`AGENTS.md` via `apm compile`), `rtk`,
and `betterleaks`. Today CI installs a subset ad hoc (Go + `go install waza`,
`setup-uv`, Docker actionlint) and there is no repeatable procedure for the
local/agent surfaces at all.

The same repository is driven from at least seven surfaces:

| # | Surface                         | Shell family   | Persistence  | GUI env gap |
|---|---------------------------------|----------------|--------------|-------------|
| 1 | Claude Code web                 | POSIX          | ephemeral    | no          |
| 2 | macOS + CLI                     | POSIX          | persistent   | no          |
| 3 | macOS + Claude Desktop (local)  | POSIX          | persistent   | yes         |
| 4 | Linux + CLI                     | POSIX          | persistent   | no          |
| 5 | Windows + CLI                   | PowerShell/WSL | persistent   | no          |
| 6 | Windows + Claude Desktop(local) | PowerShell/WSL | persistent   | yes         |
| 7 | devcontainer                    | POSIX          | image-baked  | no          |

Two decisions frame the design:

- **Nix as the declarative mechanism**, following the upstream `tvna/claude-md`
  flake pattern (SHA-pinned prebuilt-binary fetches with a `flake_pin.py`-style
  drift guard). This matches CLAUDE.md section 3 ("manage modules declaratively
  (nix, uv, microsoft/apm)").
- **Version management biased to Dependabot.** Dependabot's `nix` ecosystem
  updates `flake.lock` inputs (tracking the latest upstream commit of each
  input's ref) but does NOT update pinned refs/tags or hardcoded `fetchurl`
  version+hash pairs inside `flake.nix`. So tools that live in nixpkgs are made
  Dependabot-native by sourcing them from the `nixpkgs` input; tools not in
  nixpkgs remain manual release pins embedded in `flake.nix`, bumped by a
  Renovate customManager (or a flake_pin-style script).

**Ownership boundary (decided):** gitapex owns its own flake (Linux + macOS tool
derivations) rather than consuming claude-md's flake as an input. Consuming
upstream was rejected because claude-md exposes tool `packages` for Linux
systems only (its darwin devShell is git-only), so it cannot supply the Class B
tools to gitapex's first-class macOS surfaces; it would also inherit upstream's
stale pins (e.g. waza 0.33.0 vs current 0.38.0, apm 0.12.1 vs current 0.25.0).
"Follow upstream" is honored by reusing claude-md's pin-contract pattern, not by
coupling to its packages.

## Scope

- A version SSoT split by how each tool is updated (nixpkgs input, PyPI, or
  release pin), with no version string declared twice.
- A gitapex-owned `flake.nix` + `flake.lock` provisioning the toolchain on Linux
  and macOS.
- A native-Windows PowerShell path that installs the same pinned versions from
  publisher binaries.
- `dependabot.yml` covering the `nix`, `github-actions`, and `pip` ecosystems.
- A Class B update path (Renovate customManager over `flake.nix`, or a
  flake_pin-style script) for the release-pinned tools.
- Drift gates keeping the flake pins, the generated Windows lock, and CI in
  agreement.
- The `setup-gitapex-toolchain` skill: a thin orchestrator (detect surface ->
  provision -> verify -> document only the non-automatable parts).

## Non-goals

- No new version manager (mise/asdf/devbox); Nix is the mechanism.
- No Go dependency and no `go install`: waza's README states `go install` is
  unsupported (LFS artifacts), so waza is fetched as a prebuilt release binary.
- No native-Windows CI job (cost); the nix path is CI-verified, the ps1 path is
  verified manually and declared as an environment-limited check.
- devcontainer image wiring is a follow-up PR.
- No attempt to force the Class B tools into a Dependabot ecosystem that does
  not cover them; they are embedded in `flake.nix` and updated by Renovate
  customManager (or a flake_pin-style script) by design.
- No dependency on upstream claude-md's flake (E2 embeds everything in gitapex's
  own flake); "follow upstream" means copying its flake_pin pattern, not
  consuming its packages.

## Tool inventory and update class

| Class | Tools | Provisioned by | Version bumped by |
|-------|-------|----------------|-------------------|
| A: nixpkgs | uv, gh, actionlint, python312, bun, lychee | `pkgs.*` (nix); official installers (Windows) | Dependabot `nix` (bumps `nixpkgs` in `flake.lock`) |
| A': uv/PyPI | prek | pyproject dev-dep via `uv` (all surfaces) | Dependabot `uv` ecosystem (GA 2025-03; reads pyproject + uv.lock) |
| B: release pin | waza, apm, rtk, betterleaks | SHA-pinned `fetchurl` derivations embedded in `flake.nix` (nix); publisher binaries (Windows ps1) | Renovate customManager on `flake.nix` (or a flake_pin-style script) |

Design (E2): everything is embedded in gitapex's own flake, copying upstream
claude-md's flake_pin pattern -- Class A from the `nixpkgs` input, Class B as
`fetchurl` derivations whose version + per-`os-arch` asset + SHA live directly in
`flake.nix` let-bindings. The flake is the single SSoT; there is no separate
release-pins TOML and no dependency on upstream's flake. This was chosen over
"reference claude-md as an input" because upstream exposes tool `packages` for
Linux only (no darwin) and omits betterleaks/lychee/bun/prek, so it cannot cover
gitapex's macOS/Windows surfaces or its full tool set.

Notes: waza ships a standalone `waza check` binary plus official
`install.{sh,ps1}` (darwin/linux/windows, amd64+arm64). apm ships
darwin/linux/windows binaries with `.sha256` companions but **windows is
x86_64-only** (no windows-arm64 -> that surface uses WSL or x86_64 emulation).
prek is a single Rust binary distributed via PyPI/crates.io/release +
`prek-installer.{sh,ps1}`. prek is Dependabot-updatable via the `uv` ecosystem
(GA since 2025-03; Dependabot reads pyproject + uv.lock), configured in PR-2.
(An earlier draft wrongly claimed uv was unsupported; corrected after review.)

Class B is not covered by any Dependabot ecosystem (fetchurl pins in `flake.nix`
are invisible to Dependabot `nix`, which only bumps `flake.lock` inputs). It is
therefore updated by a Renovate customManager (regex over `flake.nix` +
`github-releases` datasource + `postUpgradeTasks` running `nix-prefetch` to
refresh the hashes), or equivalently by a flake_pin-style custom script. Which
of the two, and whether Renovate then subsumes the Class A/A' Dependabot config
entirely, is the one open tooling decision (see Open items).

## Constraints and invariants

1. **No unsigned binaries built on Windows.** The Windows path performs zero
   source compilation; it only downloads publisher-produced binaries (release
   assets or official installers). Publisher Authenticode-signed assets are
   preferred; unsigned publisher binaries are recorded as an explicit risk, not
   silently trusted. (This is Windows-specific: nixpkgs source builds on
   Linux/macOS are reproducible and hash-verified and are allowed.)
2. **SHA verification everywhere.** Every fetched artifact is verified against a
   pinned hash before use, on all surfaces (nixpkgs+flake.lock for Class A;
   pinned hashes for Class B; wheel hashes for prek).
3. **Single version source per tool.** Class A versions live only in the
   `nixpkgs` flake input; prek only in pyproject; Class B only in `flake.nix`
   let-bindings. The Windows lock consumed by ps1 is generated from these (via
   `nix eval`), never hand-edited. Class B asset/version strings in `flake.nix`
   MUST be static (no `${...}` interpolation across the pinned fields) so the
   Renovate customManager / flake_pin regex can parse them -- the same contract
   upstream documents for its brace-naive `flake_pin.py`.
4. **Drift gate ships with the SSoT** and is a hard gate (not advisory),
   including a dead-man's switch on the custom updater (see Premortem).
5. **Never write into the read-only plugin cache.** In the installed-plugin
   context the skill provisions into a user-writable cache, not the plugin
   bundle. Re-initialization is cooldown-gated (see Distribution contexts): a
   cheap presence/version check runs every invocation, the expensive
   `nix`-build initialization runs only when the cooldown TTL has expired or the
   installed plugin version changed. This satisfies CLAUDE.md's rule that a
   time-boxed freshness precondition is re-checked before each guarded operation
   (the cheap check), while the cooldown prevents per-invocation thrash.

## Distribution contexts and version specification

gitapex is both a repository and a distributable Claude Code plugin
(`.claude-plugin/plugin.json` version `0.1.0`, `marketplace.json` source `./`,
so the whole repo is bundled). The toolchain skill runs in two contexts, and the
committed `flake.nix` is referenced in place only by the repo context.

- **Repo context (contributors).** `nix develop .` against the committed flake.
  Versions are the `flake.lock` input + the Class B pins embedded in `flake.nix`,
  kept fresh by Dependabot (Class A/A') and Renovate/flake_pin (Class B).
- **Installed-plugin context (consumers).** The skill does not run `nix` inside
  the read-only plugin cache. It **initializes** the toolchain into a
  user-writable cache (e.g. `${XDG_CACHE_HOME:-~/.cache}/gitapex/toolchain/`) by
  materializing the bundled flake from `${CLAUDE_PLUGIN_ROOT}` (flake.nix,
  flake.lock, toolchain.lock.json) and provisioning there.
  Initialization is **cooldown-gated**: a cheap check (toolchain present, and a
  recorded marker of `{plugin version, TTL timestamp}` still valid) runs every
  invocation; the expensive `nix`-build init runs only on first use, cooldown
  expiry, or a plugin-version change.

Version specification therefore differs by context: in the repo it is the
Dependabot-tracked pins; as an installed plugin it is **frozen at the installed
plugin version** (the pins that plugin release bundled), with the cooldown TTL
bounding how often the initialized cache is refreshed and plugin updates being
the way to move pins forward. Because `flake.nix`, `flake.lock`, and the
generated `toolchain.lock.json` are all committed, the bundle is self-contained
and reproducible at each plugin version. (Advanced flake-input consumption by
other repos is an open item, not in this scope.)

## Architecture

```
flake.nix / flake.lock              # SSoT: Class A from nixpkgs input; Class B fetchurl pins embedded in let-bindings (static, regex-parseable)
.gitapex/toolchain.lock.json        # GENERATED (nix eval) for the ps1 path; never hand-edited
.gitapex/setup.ps1                  # Windows-native: reads the lock, installs signed publisher binaries
pyproject.toml                      # prek + python dev deps
renovate.json / .github/dependabot.yml   # Class A/A' + Class B customManager over flake.nix (tooling TBD, see Open items)
.github/workflows/toolchain-*.yml   # generate lock, drift gate, no Go
.github/scripts/*.py (+ pytest)     # drift scan (flake pins == generated lock)
skills/setup-gitapex-toolchain/SKILL.md   # thin: detect -> provision -> verify -> notes
```

## Components

### `flake.nix` / `flake.lock`
Systems: `aarch64-linux`, `x86_64-linux`, `aarch64-darwin`, `x86_64-darwin`
(gitapex's tools all publish darwin binaries, so the darwin devShell carries the
full toolchain, unlike upstream's git-only darwin shell). Class A tools come
from `pkgs.*`; Class B tools (waza/apm/rtk/betterleaks) are `fetchurl`
derivations whose version + per-`os-arch` asset + SHA are embedded directly in
`flake.nix` let-bindings (E2, copying upstream's flake_pin pattern), kept as
static regex-parseable strings. The flake is the single SSoT. `nix develop`
yields uv, gh, actionlint, python312, bun, lychee, waza, apm, rtk, betterleaks;
prek is available via `uv run prek`.

### `.gitapex/toolchain.lock.json` (generated)
CI runs `nix eval` to resolve every tool's version (Class A from the nixpkgs
input, Class B from the flake let-bindings) into a single machine-readable lock
the Windows ps1 consumes. Regenerated whenever `flake.lock` or a Class B pin
changes; a drift gate fails CI if the committed lock is stale.

### `.gitapex/setup.ps1`
Reads `toolchain.lock.json`; installs each tool from its publisher binary at the
locked version (waza via `install.ps1`; prek via `uv`/`prek-installer.ps1`; uv,
gh, actionlint, bun, lychee via their official Windows releases/installers; apm
via the pinned `apm-windows-x86_64.zip` + `.sha256`). No compilation. Idempotent;
supports `-Verify` and `-DryRun`.

### Update tooling (Class A/A' + Class B)
- Class A: Dependabot `nix` (bumps the `nixpkgs` input in `flake.lock`).
- Class A' (prek): Dependabot `uv` ecosystem (reads pyproject + uv.lock);
  configured in PR-2.
- github-actions: Dependabot `github-actions`.
- Class B: a **Renovate customManager** (regex over `flake.nix` let-bindings) +
  `github-releases` datasource + `postUpgradeTasks` running `nix-prefetch` to
  refresh the per-`os-arch` hashes. Alternative: a flake_pin-style custom script
  (upstream-proven). Because postUpgradeTasks (arbitrary commands) are needed for
  the hash refresh, Renovate would run self-hosted in Actions. Whether Renovate
  also takes over Class A/A' (letting us drop `dependabot.yml`) is the one open
  tooling decision (Open items).

### Drift scan (`.github/scripts/`, pytest-covered)
Verifies `flake.nix` pins == generated `toolchain.lock.json` and that no
workflow hardcodes a toolchain version; a hard CI gate. The Class B updater
carries a dead-man's switch: CI fails loudly if no update run/PR has occurred
within its expected window (see Premortem in the trade-off).

### `.github/workflows/` changes
`waza-check.yml` drops Go and stops hardcoding the waza version; it provisions
waza from the flake/pin and keeps its advisory-report semantics. The drift scan
runs as a hard gate.

### `skills/setup-gitapex-toolchain/SKILL.md`
Thin orchestration, standard frontmatter. Body: (1) detect context (repo vs
installed-plugin via `${CLAUDE_PLUGIN_ROOT}`) and surface (OS + shell +
Desktop-local + ephemeral); (2) provision -- repo: `nix develop .`;
installed-plugin: cooldown-gated init into the user-writable cache from the
bundled pins; native Windows: `setup.ps1`; (3) run `--verify` (live proof);
(4) document only the non-automatable notes: Desktop-local PATH/env
non-inheritance (the GitHub-MCP gap that motivated this work), web egress limits
(verify-first), devcontainer rebuild, and the Windows-arm64 apm gap.

## Surface -> provisioner mapping

| Surface | Provisioner |
|---------|-------------|
| 1 web (ephemeral)      | `nix develop` (or preinstalled; verify first), per session |
| 2 macOS CLI            | `nix develop` |
| 3 macOS Desktop-local  | `nix develop` + PATH-visibility note |
| 4 Linux CLI            | `nix develop` |
| 5 Windows CLI (native) | `setup.ps1` |
| 6 Windows Desktop(nat) | `setup.ps1` + PATH-visibility note |
| 5/6 via WSL            | `nix develop` (WSL is a Linux surface) |
| 7 devcontainer         | flake baked into image (follow-up PR) |

## Resolved facts (grounded, not assumptions)

- Dependabot `nix` updates `flake.lock` inputs to the latest upstream commit of
  each input's ref; it does NOT bump pinned tags or hardcoded fetchurl pins.
- waza: standalone `waza check` release binary (azd extension is a separate
  distribution); `go install` unsupported (LFS); darwin/linux/windows binaries;
  official `install.{sh,ps1}`.
- apm: v0.25.0 current; darwin/linux/windows-x86_64 binaries with `.sha256`;
  Python-frozen; not in nixpkgs; no windows-arm64.
- prek: `j178/prek`; PyPI + crates.io + release + `prek-installer.{sh,ps1}`.
- claude-md flake exposes tool `packages` for Linux systems only.

## Assumptions to verify (PR-1 spikes)

- nixpkgs provides uv, actionlint, lychee, bun (and python312) at acceptable
  versions; if a Class A tool lags materially in nixpkgs, reclassify it to a
  release pin (Class B).
- Authenticode signing status of each Windows binary (record unsigned as risk).
- `uv run prek` git-hook behavior is acceptable vs a PATH-installed prek.

## Decomposition / PR sequence

1. **Foundation.** `flake.nix`/`flake.lock` embedding all tools (Class A from
   nixpkgs; Class B as fetchurl pins in let-bindings, all platforms), prek added
   to pyproject. `nix develop` provisions the toolchain on Linux+macOS. Includes
   the PR-1 spikes.
2. **Update tooling (lean, done in PR #-).** Dependabot for `nix` +
   `github-actions` + `uv` (the uv ecosystem bumps prek in pyproject/uv.lock);
   migrate `waza-check.yml` off `go install` to the flake's waza (removes Go).
   The generated `toolchain.lock.json` + its drift scan were deferred to PR-4
   (their only consumer is the Windows ps1) to avoid a consumer-less artifact.
3. **Class B updater.** Renovate customManager over `flake.nix` (or a
   flake_pin-style script) with `github-releases` + `postUpgradeTasks`
   (nix-prefetch) and the dead-man's switch; pytest-covered. (prek is handled by
   the Dependabot `uv` ecosystem in PR-2, not here.) Resolves the tooling open item.
4. **Windows ps1 + generated lock + drift gate.** CI generates
   `toolchain.lock.json` (`nix eval`) and a drift scan gates it; `setup.ps1`
   consumes the lock; signing verification.
5. **The skill.** `skills/setup-gitapex-toolchain/SKILL.md` orchestrating the
   above with context detection (repo vs installed-plugin via
   `${CLAUDE_PLUGIN_ROOT}`), the cooldown-gated plugin-context init into a
   user-writable cache, surface detection, and the non-automatable notes.
6. **(Optional) devcontainer wiring.**

Dependency order 1 -> 2 -> 3 -> 4 -> 5 (-> 6). The requested deliverable (the
skill) is PR 5; PRs 1-4 are its foundation.

## Verification

- Foundation: `nix develop` on Linux and macOS yields each tool at the resolved
  version; `nix flake check` passes; PR-1 spikes resolved with evidence.
- Dependabot/lock/drift: pytest for the drift scan (agreement + seeded-drift
  failure); CI fails on induced drift and on a stale committed lock.
- Updater: pytest for the Class B bumper (Renovate customManager regex or
  flake_pin script); a simulated newer release produces a correct
  version+hash update in `flake.nix`; dead-man's switch fires when starved.
- Windows: `setup.ps1 -Verify` reports the locked versions on a Windows host
  (declared environment-limited; no native-Windows CI).
- Skill: exercised on reachable surfaces (Linux CLI, macOS CLI) with the verify
  step as the live proof of completion.

## Open items (not blocking this spec)

- Class B update tooling: Renovate customManager (self-hosted for the hash
  `postUpgradeTasks`) vs a flake_pin-style custom script, and whether Renovate
  then subsumes the Class A/A' Dependabot config (drop `dependabot.yml`).
- uv/nixpkgs vs `uv run --frozen` lockfile-format alignment.
- Whether prek replaces an existing pre-commit setup or is additive.
- devcontainer image ownership and rebuild cadence (PR 6).
- Windows-arm64 apm story (WSL vs emulation) if that surface becomes real.
- Cooldown TTL value for the installed-plugin init, and the exact cache marker
  format ({plugin version, timestamp}).
- Advanced flake-input consumption (other repos' `inputs.gitapex`) -- out of
  this scope; revisit if requested.

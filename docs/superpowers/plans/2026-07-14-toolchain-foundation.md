# Toolchain Foundation (PR-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up gitapex's own Nix flake that provisions the full external toolchain on Linux and macOS, with all tools embedded in the flake (Class A from nixpkgs, Class B as SHA-pinned release binaries), plus prek added to pyproject.

**Architecture:** A single `flake.nix` at the repo root is the SSoT. Class A tools (uv, gh, actionlint, python312, bun, lychee) come from a pinned `nixpkgs` input. Class B tools (waza, apm, rtk, betterleaks) are `fetchurl` derivations whose version + per-system asset + SHA256 are embedded directly in `flake.nix` let-bindings as static, regex-parseable strings. `nix develop` yields a shell with every tool; prek is provided via `uv run prek`.

**Tech Stack:** Nix flakes, nixpkgs, `fetchurl` fixed-output derivations, uv/PyPI (prek).

Design spec: `docs/superpowers/specs/2026-07-14-setup-gitapex-toolchain-design.md`. Tracking issue: #57.

## Global Constraints

- Systems: `aarch64-linux`, `x86_64-linux`, `aarch64-darwin`, `x86_64-darwin` (exact list, verbatim).
- No Go dependency and no `go install` anywhere (waza is a prebuilt binary).
- Class B tools are prebuilt-binary `fetchurl` derivations only; no source builds of Class B.
- Class B version/asset/hash strings in `flake.nix` MUST be static literals (no `${...}` interpolation across the pinned fields) so a regex updater can parse them.
- Every fetched Class B artifact is SHA256-pinned; never use a permanent `lib.fakeHash` (it is only a scaffolding step to discover the real hash).
- Python runtime version is owned by `pyproject.toml` `requires-python = ">=3.12"`; the flake provides `python312` but does not re-pin a Python version string.
- Class B pinned versions for this PR (verbatim): waza `0.38.0`, apm `0.25.0`, rtk `0.43.0`, betterleaks `1.6.1`.
- Commit trailer convention (repo norm, owner-disclosed): end each commit body with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and cite `#57`.

- CI actions are SHA-pinned with a `# vX.Y.Z` comment (repo norm -- see existing workflows). Resolve each action's released commit SHA when adding it.

**Verification is CI-side (Nix runs only in CI).** The executor does NOT need Nix locally. Local work uses only `curl`, `sha256sum`, `python3`, and `uv`. All Nix proof (`nix flake check`, `nix build`, devShell smoke) runs in a new GitHub Actions workflow on an `ubuntu-latest` + `macos-latest` matrix -- this is the live proof for both Linux and macOS. The loop per task: author locally -> commit -> push -> CI verifies.

---

### Task 1: Spikes -- verify assumptions and record evidence

**Files:**
- Create: `docs/superpowers/notes/2026-07-14-pr1-spikes.md`

**Interfaces:**
- Produces: the chosen nixpkgs channel ref (e.g. `nixos-25.05`) consumed by Task 2, the archive layout per Class B tool consumed by Task 3, and confirmation that waza's release binary runs `check` standalone.

Note: Class A availability in nixpkgs (uv/gh/actionlint/bun/lychee/python312) is NOT probed locally (no local Nix). It is proven by the CI `nix flake check` added in Task 2 -- a missing attribute fails the build there. Pick the channel ref (default `nixos-25.05`; use a newer stable if you know one) and record it.

- [ ] **Step 1: Verify the waza release binary runs `waza check` standalone (no azd)**

Run:
```bash
tmp=$(mktemp -d); cd "$tmp"
curl -fsSL -o waza.tgz "https://github.com/microsoft/waza/releases/download/azd-ext-microsoft-azd-waza_0.38.0/microsoft-azd-waza-linux-amd64.tar.gz"
tar xzf waza.tgz
ls -la
find . -type f -name 'waza*' -exec chmod +x {} \; -exec {} --version \;
find . -type f -name 'waza*' -exec {} check --help \; | head
cd - >/dev/null
```
Expected: a `waza` binary is present, `--version` prints `0.38.0` (or close), and `waza check --help` prints usage (proving `check` runs standalone). Record the archive's internal path to the `waza` binary (needed in Task 3).

- [ ] **Step 2: Record the archive layout of each Class B asset**

Run (records where the binary sits inside each archive -- drives each `installPhase`):
```bash
base_waza="https://github.com/microsoft/waza/releases/download/azd-ext-microsoft-azd-waza_0.38.0"
base_apm="https://github.com/microsoft/apm/releases/download/v0.25.0"
base_rtk="https://github.com/rtk-ai/rtk/releases/download/v0.43.0"
base_bl="https://github.com/betterleaks/betterleaks/releases/download/v1.6.1"
for url in \
  "$base_waza/microsoft-azd-waza-linux-amd64.tar.gz" \
  "$base_apm/apm-linux-x86_64.tar.gz" \
  "$base_rtk/rtk-x86_64-unknown-linux-musl.tar.gz" \
  "$base_bl/betterleaks_1.6.1_linux_x64.tar.gz"; do
  echo "== $url =="; curl -fsSL "$url" | tar tz | head
done
```
Expected: for each, note whether the binary is at the archive root (bare, needs `sourceRoot = "."`) or under a subdirectory, and the exact binary filename. Write all findings into the notes file.

- [ ] **Step 3: Commit the spike notes**

```bash
git add docs/superpowers/notes/2026-07-14-pr1-spikes.md
git commit -m "docs(toolchain): record PR-1 toolchain spikes (#57)

Confirmed nixpkgs channel and Class A tool versions, waza standalone
check, and Class B archive layouts. Refs #57

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Scaffold the flake (Class A devShell) and the CI Nix workflow

**Files:**
- Create: `flake.nix`
- Create: `.github/workflows/toolchain-nix.yml`
- Create (CI-generated, committed in Step 4): `flake.lock`

**Interfaces:**
- Produces: `devShells.<system>.default` containing the Class A tools; `nixpkgs` input pinned in `flake.lock`; a `Toolchain (nix)` CI workflow that is the sole place Nix runs. Task 3 extends this same devShell + smoke with Class B packages.

- [ ] **Step 1: Write `flake.nix` (Class A only)**

Use the channel confirmed in Task 1 (shown here as `nixos-25.05`):
```nix
{
  description = "gitapex external toolchain (SSoT for uv/gh/actionlint/python/bun/lychee + waza/apm/rtk/betterleaks)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShellNoCC {
            packages = [
              pkgs.uv
              pkgs.gh
              pkgs.actionlint
              pkgs.python312
              pkgs.bun
              pkgs.lychee
            ];
          };
        });
    };
}
```

- [ ] **Step 2: Add the CI Nix workflow (this is the only place Nix runs)**

Create `.github/workflows/toolchain-nix.yml`. Pin each action to a released SHA with a `# vX.Y.Z` comment (repo norm; resolve the SHA e.g. `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha`). Match the harden-runner + checkout(persist-credentials:false) pattern used by the existing workflows:
```yaml
name: Toolchain (nix)
on:
  push:
    paths: [ "flake.nix", "flake.lock", ".github/workflows/toolchain-nix.yml" ]
  pull_request:
    paths: [ "flake.nix", "flake.lock", ".github/workflows/toolchain-nix.yml" ]
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  nix:
    strategy:
      fail-fast: false
      matrix:
        os: [ ubuntu-latest, macos-latest ]
    runs-on: ${{ matrix.os }}
    timeout-minutes: 20
    steps:
      - uses: step-security/harden-runner@<sha>   # v2.19.4
        with: { egress-policy: audit }
      - uses: actions/checkout@<sha>              # v7.0.0
        with: { persist-credentials: false }
      - uses: DeterminateSystems/nix-installer-action@<sha>   # pin latest release
        with: { extra-conf: "experimental-features = nix-command flakes" }
      - name: Lock (generate flake.lock if missing)
        run: nix flake lock
      - name: Upload flake.lock
        if: matrix.os == 'ubuntu-latest'
        uses: actions/upload-artifact@<sha>       # v4.x
        with: { name: flake-lock, path: flake.lock }
      - name: flake check
        run: nix flake check
      - name: build Class B (added in Task 3; no-op until then)
        run: nix build .#waza .#apm .#rtk .#betterleaks || echo "class B not present yet"
      - name: devShell smoke
        run: |
          nix develop --command bash -c '
            set -e
            for t in uv gh actionlint bun lychee; do echo -n "$t "; $t --version | head -1; done
            python3 --version
          '
```

- [ ] **Step 3: Commit flake.nix + workflow, push, and let CI generate the lock**

```bash
git add flake.nix .github/workflows/toolchain-nix.yml
git commit -m "feat(toolchain): add flake Class A devShell and CI nix workflow (#57)

nixpkgs-sourced uv, gh, actionlint, python312, bun, lychee across
aarch64/x86_64 linux and darwin, verified by a CI nix matrix
(ubuntu + macos). Refs #57

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push
```

- [ ] **Step 4: Retrieve the CI-generated flake.lock and commit it**

Wait for the workflow, then:
```bash
run_id=$(gh run list --workflow "Toolchain (nix)" --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run download "$run_id" --name flake-lock --dir .
git add flake.lock
git commit -m "chore(toolchain): commit CI-generated flake.lock (#57)

Refs #57

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push
```
Expected: the re-run of the workflow is green on both `ubuntu-latest` and `macos-latest` (Class A tools resolve; a missing nixpkgs attribute would fail here -- this is the Class A availability check).

---

### Task 3: Embed the Class B release binaries in the flake

**Files:**
- Modify: `flake.nix`

**Interfaces:**
- Consumes: the `systems`/`forAllSystems`/`pkgs` scaffold from Task 2.
- Produces: `packages.<system>.{waza,apm,rtk,betterleaks}` and the same four added to `devShells.<system>.default.packages`.

The four tools share one pattern. Add a reusable helper plus four data-driven derivations. Asset maps below are grounded in each project's v-pinned release; the `binPath`/`sourceRoot` come from Task 1 Step 3 findings (adjust if your inspection differs).

- [ ] **Step 1: Add the helper and per-tool derivations to `flake.nix`**

Inside the `let ... in` of `outputs`, before `devShells`, add a package builder and the four tools. Insert this into the per-system `let` block (where `pkgs` is in scope), e.g. by refactoring `forAllSystems` to compute a `classB` attrset:

```nix
      # --- Class B: SHA-pinned prebuilt release binaries (static, regex-parseable) ---
      # mkReleaseBin fetches one asset and installs a single binary. installPhase
      # is per-tool because archive layouts differ (see PR-1 spike notes).
      mkClassB = pkgs:
        let
          fetch = url: sha256: pkgs.fetchurl { inherit url sha256; };
          # waza 0.38.0 -- tag azd-ext-microsoft-azd-waza_0.38.0, assets microsoft-azd-waza-<os>-<arch>.tar.gz
          wazaAsset = {
            aarch64-linux  = "microsoft-azd-waza-linux-arm64.tar.gz";
            x86_64-linux   = "microsoft-azd-waza-linux-amd64.tar.gz";
            aarch64-darwin = "microsoft-azd-waza-darwin-arm64.tar.gz";
            x86_64-darwin  = "microsoft-azd-waza-darwin-amd64.tar.gz";
          };
          wazaSha = {
            aarch64-linux  = "sha256-AAAA...";  # obtain per Step 2
            x86_64-linux   = "sha256-AAAA...";
            aarch64-darwin = "sha256-AAAA...";
            x86_64-darwin  = "sha256-AAAA...";
          };
        in {
          waza = pkgs.stdenvNoCC.mkDerivation {
            pname = "waza"; version = "0.38.0";
            src = fetch
              "https://github.com/microsoft/waza/releases/download/azd-ext-microsoft-azd-waza_0.38.0/${wazaAsset.${pkgs.system}}"
              wazaSha.${pkgs.system};
            sourceRoot = ".";            # adjust from spike findings
            dontBuild = true; dontStrip = true; dontPatchELF = true;
            installPhase = ''
              runHook preInstall
              install -Dm755 waza $out/bin/waza   # adjust binPath from spike findings
              runHook postInstall
            '';
          };
          # Repeat the same shape for apm (0.25.0), rtk (0.43.0), betterleaks (1.6.1),
          # using these asset maps and their own sha attrsets:
          #   apm assets:  apm-linux-arm64.tar.gz / apm-linux-x86_64.tar.gz /
          #                apm-darwin-arm64.tar.gz / apm-darwin-x86_64.tar.gz
          #     base: https://github.com/microsoft/apm/releases/download/v0.25.0
          #     apm ships a wrapper + _internal dir: install the apm binary and cp -R _internal
          #   rtk assets:  rtk-aarch64-unknown-linux-gnu.tar.gz / rtk-x86_64-unknown-linux-musl.tar.gz /
          #                rtk-aarch64-apple-darwin.tar.gz / rtk-x86_64-apple-darwin.tar.gz
          #     base: https://github.com/rtk-ai/rtk/releases/download/v0.43.0 ; bare binary -> sourceRoot="."
          #   betterleaks: betterleaks_1.6.1_linux_arm64.tar.gz / _linux_x64.tar.gz /
          #                _darwin_arm64.tar.gz / _darwin_x64.tar.gz
          #     base: https://github.com/betterleaks/betterleaks/releases/download/v1.6.1 ; bare binary
        };
```
Write out all four derivations fully (do not leave the apm/rtk/betterleaks as comments -- expand them with the same `mkDerivation` shape, their asset maps, their own `<tool>Sha` attrset, and the installPhase indicated by the spike layout notes).

- [ ] **Step 2: Obtain the real SHA256 for every asset without Nix (replace each `sha256-AAAA...`)**

`fetchurl` (flat mode) expects the SRI hash of the file bytes = `sha256-` + base64 of the raw SHA-256 digest. Compute it with only curl + sha256sum + python3:
```bash
sri() {
  local hex
  hex=$(curl -fsSL "$1" | sha256sum | cut -d' ' -f1) || { echo "FETCH FAIL: $1" >&2; return 1; }
  python3 -c 'import base64,sys;print("sha256-"+base64.b64encode(bytes.fromhex(sys.argv[1])).decode())' "$hex"
}
# example (repeat for all 16 assets: 4 tools x 4 systems):
sri "https://github.com/microsoft/waza/releases/download/azd-ext-microsoft-azd-waza_0.38.0/microsoft-azd-waza-linux-amd64.tar.gz"
```
Paste each result into the matching `<tool>Sha` entry. Every `sha256-AAAA...` MUST be replaced. (CI's `nix build` in Step 4 is the authoritative check: a wrong hash fails with a `got: sha256-...` mismatch.)

- [ ] **Step 3: Wire the four tools into packages and the devShell**

Update `devShells` and add `packages`:
```nix
      packages = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; }; b = mkClassB pkgs;
        in { inherit (b) waza apm rtk betterleaks; });

      devShells = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; }; b = mkClassB pkgs;
        in {
          default = pkgs.mkShellNoCC {
            packages = [ pkgs.uv pkgs.gh pkgs.actionlint pkgs.python312 pkgs.bun pkgs.lychee
                         b.waza b.apm b.rtk b.betterleaks ];
          };
        });
```

- [ ] **Step 4: Extend the CI smoke to run the Class B tools, then commit and let CI verify**

In `.github/workflows/toolchain-nix.yml`, append the Class B tools to the devShell smoke step:
```yaml
            for t in waza apm rtk betterleaks; do echo -n "$t "; $t --version | head -1; done
```
Then commit and push:
```bash
git add flake.nix .github/workflows/toolchain-nix.yml
git commit -m "feat(toolchain): embed Class B release binaries in flake (#57)

waza 0.38.0, apm 0.25.0, rtk 0.43.0, betterleaks 1.6.1 as SHA-pinned
fetchurl derivations across all four systems. Refs #57

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push
```
Expected: the CI matrix (`ubuntu-latest` + `macos-latest`) goes green -- `nix build .#waza .#apm .#rtk .#betterleaks` succeeds with the pinned hashes (a wrong hash fails with `got: sha256-...`; a wrong archive layout fails the `installPhase`), and each tool prints its version. This is the cross-platform live proof. Fix any hash/layout mismatch from the CI log and re-push before proceeding.

---

### Task 4: Add prek to pyproject dev dependencies

**Files:**
- Modify: `pyproject.toml:8-14` (the `[dependency-groups].dev` list)

**Interfaces:**
- Produces: `uv run prek` available on any surface that has uv.

- [ ] **Step 1: Add prek to the dev group**

In `pyproject.toml`, add `"prek>=0.4"` to `[dependency-groups].dev`:
```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pyyaml>=6.0",
    "prek>=0.4",
]
```

- [ ] **Step 2: Sync and verify prek runs**

Run:
```bash
uv sync
uv run prek --version
```
Expected: `uv sync` updates `uv.lock` to include prek; `uv run prek --version` prints a version.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(toolchain): add prek (pre-commit successor) via PyPI (#57)

prek is provisioned through uv as a dev dependency, keeping it
Dependabot-native (pip). Refs #57

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Integration smoke and PR-1 close-out

**Files:**
- (No new files; verification only.)

- [ ] **Step 1: Confirm no Go and no fake hashes leaked (local, nix-free)**

Run:
```bash
! grep -RniE "go install|golang|buildGoModule" flake.nix
! grep -RniE "fakeHash|sha256-AAAA" flake.nix
```
Expected: both greps find nothing (commands exit 0 due to `!`).

- [ ] **Step 2: Confirm the CI Nix matrix is green (this is the whole-toolchain live proof)**

Run:
```bash
gh run list --workflow "Toolchain (nix)" --branch "$(git branch --show-current)" --limit 1
```
Expected: the latest run is `completed / success` on both `ubuntu-latest` and `macos-latest`. That run already exercised `nix flake check`, `nix build .#{waza,apm,rtk,betterleaks}`, and the devShell smoke printing all 10 flake tools -- the cross-platform live proof for PR-1. (prek is verified separately by the repo's existing uv test workflow via `uv sync`.)

- [ ] **Step 3: Open the PR for #57**

```bash
gh pr create --title "toolchain: nix foundation embedding all tools (PR-1) (#57)" \
  --body "Implements PR-1 of #57: flake.nix embedding Class A (nixpkgs) and Class B (waza/apm/rtk/betterleaks release pins) across 4 systems, plus prek via PyPI. Live proof: the Toolchain (nix) CI matrix (ubuntu + macos) is green -- nix flake check, nix build of all Class B packages, and a full devShell smoke. Refs #57"
```
Expected: PR opened. Then drive it to a terminal state per the repo's review/merge workflow.

---

## Self-Review

**Spec coverage (PR-1 scope):** flake.nix embedding Class A (Task 2) and Class B all-platform (Task 3); prek via PyPI (Task 4); CI-side Nix verification workflow (Task 2 Step 2); PR-1 spikes -- waza standalone + archive layouts (Task 1), nixpkgs availability proven by CI flake check (Task 2). Class A availability, `nix develop`, and all builds are verified CI-side on ubuntu+macos. Class A/A' Dependabot config, generated Windows lock, drift gate, Class B updater, ps1, and the skill itself are later PRs (2-5) and are intentionally out of this plan.

**Placeholder scan:** The only non-literal values are the Class B SHA256 hashes (Task 3 Step 2 fills them via an exact nix-free curl+sha256sum+base64 command), the apm/rtk/betterleaks derivation bodies (Task 3 Step 1 expands them from the stated asset maps + spike layout findings), and the CI action SHAs (pinned per repo norm). These are executor-computed values, not TBDs; Task 5 Step 1 gates on no `fakeHash`/`sha256-AAAA` remaining, and the CI `nix build` is the authoritative hash/layout check.

**Type/name consistency:** `mkClassB` returns `{ waza; apm; rtk; betterleaks; }`, consumed identically in `packages` and `devShells` (Task 3 Steps 1/3) and verified by name in Tasks 3/5. Tool binary names match their `--version` invocations throughout.

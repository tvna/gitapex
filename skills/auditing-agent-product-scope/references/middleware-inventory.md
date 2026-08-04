# Middleware inventory (Axis F evidence)

Backs `docs/agent-product-scope.md`'s Axis F (dependency middleware).
Unlike Axis A-D, whose primary sources are vendor documentation, this
axis's primary source is the observed repository state itself -- each
table row below cites the exact file establishing the claim, fetched
directly from this repository (or, for `rtk`/`betterleaks`, each
project's own README, fetched directly), not a secondary summary. Each
table's **Why needed** column states the tool's actual purpose;
**Scope of responsibility** states what it is actually wired into in
*this* repository today, which for several tools is narrower than its
general-purpose capability -- a tool merely provisioned in the
toolchain is not the same claim as one enforced by a CI gate, and this
inventory does not conflate the two.

## Contents

1. [Nix toolchain (flake.nix)](#nix-toolchain-flakenix)
2. [apm](#apm)
3. [Python dev tooling](#python-dev-tooling)
4. [waza](#waza)
5. [GitHub MCP server](#github-mcp-server)
6. [Supply-chain coverage summary](#supply-chain-coverage-summary)

## Nix toolchain (`flake.nix`)

Stated purpose, verbatim from the file's own `description`: "gitapex
external toolchain (SSoT for uv/gh/actionlint/python/bun/lychee +
waza/apm/rtk/betterleaks)."

| Tool | Class | Why needed | Scope of responsibility | Supply-chain coverage |
|---|---|---|---|---|
| `uv` | A (nixpkgs) | Python dependency/environment manager for this repository's own scripts and dev tooling | Manages only the `dev` dependency group (`pytest`, `pytest-cov`, `pyyaml`, `prek`); `pyproject.toml` declares no runtime `dependencies` and `[tool.uv] package = false` | Dependabot `nix` ecosystem (bumps the `nixpkgs` input) |
| `gh` | A (nixpkgs) | Read-only repository/PR/issue interaction from a shell | Present in the dev shell; its *write* subcommands are blocked by `hooks/check-bash-safety.sh`, not by the toolchain itself | Dependabot `nix` ecosystem |
| `actionlint` | A (nixpkgs) | Lints GitHub Actions workflow YAML | An active CI gate, wired into `.github/workflows/lint.yml` | Dependabot `nix` ecosystem |
| `python312` | A (nixpkgs) | Runtime for every Python script and test in this repository | Base interpreter only; `uv` manages the actual dependency versions on top of it | Dependabot `nix` ecosystem |
| `bun` | A (nixpkgs) | A JS/TS runtime and package manager, per the toolchain's own stated scope | Provisioned in the dev shell; no `package.json` or JS/TS source exists in this repository, and no script or workflow invokes it beyond `toolchain-nix.yml`'s own build-and-version smoke test | Dependabot `nix` ecosystem |
| `lychee` | A (nixpkgs) | A link checker, per its own project purpose | Same as `bun` -- provisioned and version-smoke-tested only; no link-checking workflow runs it against this repository's docs today | Dependabot `nix` ecosystem |
| `waza` | B (SHA256-pinned release binary, `microsoft/waza`) | Microsoft's skill/eval-running CLI | Invoked as `nix run .#waza -- check` (or `run`); see the dedicated [waza](#waza) section below for how CI actually wires it | Excluded from Dependabot -- see [Supply-chain coverage summary](#supply-chain-coverage-summary) |
| `apm` | B (SHA256-pinned release binary, `microsoft/apm`) | Regenerates `CLAUDE.md`/`AGENTS.md` via `apm compile` | See the dedicated [apm](#apm) section below | Excluded from Dependabot -- see [Supply-chain coverage summary](#supply-chain-coverage-summary) |
| `rtk` | B (SHA256-pinned release binary, `rtk-ai/rtk`) | "CLI proxy that reduces LLM token consumption by 60-90% on common dev commands" (the project's own README) | Provisioned and version-checked by `toolchain-nix.yml`'s own smoke test; no script, hook, or workflow in this repository invokes it today | Excluded from Dependabot -- see [Supply-chain coverage summary](#supply-chain-coverage-summary) |
| `betterleaks` | B (SHA256-pinned release binary, `betterleaks/betterleaks`) | "A configurable, fast, and thorough secrets scanner" (the project's own README) | Same as `rtk` -- provisioned and smoke-tested only, no consuming script, hook, or workflow in this repository today | Excluded from Dependabot -- see [Supply-chain coverage summary](#supply-chain-coverage-summary) |

`flake.lock` separately pins the `nixpkgs` input itself to
`github:NixOS/nixpkgs/nixos-26.05`; each Class B binary's exact pinned
version is declared in `flake.nix`'s own `pname`/`version` fields --
read it there rather than restating a value here that would drift the
moment a pin bumps.

## apm

`apm.yml`: gitapex is normally an apm *provider*, but declares itself a
*consumer* of two plugins its own skills assume.

| Dependency | Why needed | Scope of responsibility | Pinned in |
|---|---|---|---|
| `apm` (the tool itself) | Regenerates `CLAUDE.md`/`AGENTS.md` via `apm compile` | The tool's own version | `apm.lock.yaml`'s `apm_version` field |
| `obra/superpowers` | A plugin gitapex's own skills assume is installed | Resolved to `host: github.com`, a pinned commit and version | `apm.lock.yaml` |
| `tvna/clairvoyance` | A plugin gitapex's own skills assume is installed | Resolved to `host: github.com`, a pinned commit and version | `apm.lock.yaml` |

Read the exact pinned values in `apm.lock.yaml` itself rather than
restating them here, where they would go stale on the next lockfile
bump. Both plugin dependencies are pinned to `host: github.com`
specifically -- apm's own lockfile format is GitHub-host-typed, a fact
relevant to Axis E (git-hosting platform) but recorded here since it is
apm's own behavior, not a platform-audit finding.

## Python dev tooling

`pyproject.toml` (confirmed directly): project `gitapex-scripts`,
`requires-python >=3.12`, empty runtime `dependencies`; a `dev`
dependency group only. `[tool.uv] package = false` (a non-package
project; uv manages the environment and dev tools only, not a
published package).

| Package | Why needed | Scope of responsibility |
|---|---|---|
| `pytest` | The repository's own test runner | Runs the suites under `.github/scripts/`, every skill's own `scripts/`, and `tests/` |
| `pytest-cov` | Coverage measurement for the same test runs | Reports coverage against the sources listed in `pyproject.toml`'s `[tool.coverage.run]` |
| `pyyaml` | YAML parsing for checker scripts | Used by scripts that read `apm.lock.yaml`, workflow files, or eval fixtures |
| `prek` | A pre-commit-hook runner | Declared as a dev dependency, but no pre-commit config file exists in this repository, so it is not wired into any actual hook execution today |

`uv.lock` pins the resolved versions of these dev tools plus their own
transitive dependencies -- read the exact values there rather than
restating them here.

## waza

Microsoft's eval-running CLI (`microsoft/waza`, pinned via the Nix
Class B mechanism above), invoked as `nix run .#waza -- <check|run>`.

- `.github/workflows/waza-check.yml`: advisory only
  (`continue-on-error: true`) -- its own comment states waza's `check`
  "has no flag to fail on a non-compliant skill... It is a report, not
  a gate."
- `.github/workflows/waza-eval-matrix.yml`: `workflow_dispatch`-only,
  never gates a merge. Requires repository secrets
  `COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` (and, for the optional
  Hugging Face job, `HF_INFERENCE_ENDPOINT_URL`/`HF_API_TOKEN`); fails
  loudly at a preflight step if the required secrets are absent rather
  than silently skipping.
- `docs/skill-eval-status.md` documents that no credentialed dispatch
  of this workflow has ever run in this repository's history to date.

## GitHub MCP server

| Attribute | Detail |
|---|---|
| Why needed | Several skills state a GitHub MCP server as their sole hard dependency in prose, using the portable `Server:tool` shorthand (for example `drafting-a-pr-to-merge`'s own opening line: "This skill depends only on a connected GitHub MCP server... no this-repository tooling") |
| Scope of responsibility | No hook in `hooks/hooks.json` declares an MCP server requirement directly -- hooks trigger on tool-name matchers (`Bash`, `Write`, `mcp__github__issue_write`), the third of which is typed to the GitHub MCP server's own tool-name shape specifically |
| Coverage / alternative | No GitLab MCP server is documented anywhere in this repository as an equivalent or alternative |

## Supply-chain coverage summary

| Ecosystem | Bumps | Covers Class B binaries? |
|---|---|---|
| `nix` | `flake.lock`'s `nixpkgs` input | No -- Class A only |
| `github-actions` | SHA-pinned actions | N/A -- a different dependency class entirely |
| `uv` | `pyproject.toml`/`uv.lock` dev tools | No |

`.github/dependabot.yml`'s own header comment states plainly what is
**not** covered: "the Class B release binaries (waza/apm/rtk/betterleaks)
are pinned in flake.nix, outside any Dependabot ecosystem," tracked
instead on a separate Renovate/custom track (`docs/agent-product-scope.md`'s
own Axis F Boundary names the tracking issue for this gap, so it is
not duplicated here).
`.github/scripts/gitapex_scan_toolchain_pin_drift.py` is the deterministic
check that guards the Class B pins themselves staying in sync with
`flake.nix`'s own declared values.

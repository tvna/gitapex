# Middleware inventory (Axis F evidence)

Backs `docs/agent-product-scope.md`'s Axis F (dependency middleware).
Unlike Axis A-D, whose primary sources are vendor documentation, this
axis's primary source is the observed repository state itself -- each
entry below cites the exact file establishing the claim, fetched
directly from this repository, not a secondary summary.

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

Two tool classes:

- **Class A** (from nixpkgs, `pkgs.X` in `devShells.default`): `uv`,
  `gh` (the GitHub CLI -- present as a dev-shell tool even though its
  *write* subcommands are blocked by `hooks/check-bash-safety.sh`),
  `actionlint`, `python312`, `bun`, `lychee`.
- **Class B** (SHA256-pinned prebuilt release binaries, fetched
  directly from a GitHub release URL via a shared `mkReleaseBinary`
  helper): `waza` 0.38.0 (`microsoft/waza`), `apm` 0.25.0
  (`microsoft/apm`), `rtk` 0.43.0 (`rtk-ai/rtk`), `betterleaks` 1.6.1
  (`betterleaks/betterleaks`). Versions confirmed directly against
  `flake.nix`'s own `pname`/`version` fields.
- `flake.lock` pins the `nixpkgs` input to
  `github:NixOS/nixpkgs/nixos-26.05`.

## apm

`apm.yml`: gitapex is normally an apm *provider*, but declares itself a
*consumer* of two plugins its own skills assume:
`obra/superpowers` and `tvna/clairvoyance`.

`apm.lock.yaml` (confirmed directly): `apm_version: 0.23.1`;
`superpowers` resolves to `host: github.com`, a pinned commit, version
`6.1.1`; `clairvoyance` resolves to `host: github.com`, a pinned
commit, version `0.6.0`. Both dependencies are pinned to
`host: github.com` specifically -- apm's own lockfile format is
GitHub-host-typed, a fact relevant to Axis E (git-hosting platform) but
recorded here since it is apm's own behavior, not a platform-audit
finding.

## Python dev tooling

`pyproject.toml` (confirmed directly): project `gitapex-scripts`,
`requires-python >=3.12`, empty runtime `dependencies`; a `dev`
dependency group only: `pytest`, `pytest-cov`, `pyyaml`, `prek`.
`[tool.uv] package = false` (a non-package project; uv manages the
environment and dev tools only, not a published package). `uv.lock`
pins the resolved versions of these dev tools plus their own
transitive dependencies.

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

No hook in `hooks/hooks.json` declares an MCP server requirement
directly -- hooks trigger on tool-name matchers (`Bash`, `Write`,
`mcp__github__issue_write`), the third of which is typed to the GitHub
MCP server's own tool-name shape specifically.

Several skills state a GitHub MCP server as their sole hard dependency
in prose, using the portable `Server:tool` shorthand (for example
`driving-pr-to-merge`'s own opening line: "This skill depends only on
a connected GitHub MCP server... no this-repository tooling"). No
GitLab MCP server is documented anywhere in this repository as an
equivalent or alternative.

## Supply-chain coverage summary

`.github/dependabot.yml` runs three ecosystems weekly: `nix` (bumps
`flake.lock`'s `nixpkgs` input -- Class A only), `github-actions`
(bumps SHA-pinned actions), `uv` (bumps `pyproject.toml`/`uv.lock` dev
tools). The file's own header comment states plainly what is **not**
covered: "the Class B release binaries (waza/apm/rtk/betterleaks) are
pinned in flake.nix, outside any Dependabot ecosystem," tracked
instead on a separate Renovate/custom track per the toolchain design
spec and a sub-task of
[gitapex#57](https://github.com/tvna/gitapex/issues/57).
`.github/scripts/scan_toolchain_pin_drift.py`
is the deterministic check that guards the Class B pins themselves
staying in sync with `flake.nix`'s own declared values.

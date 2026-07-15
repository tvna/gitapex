# gitapex CLI: SSOT config + business-domain governance/gate-control

Date: 2026-07-15

Refs #82. This doc elaborates `docs/versioning.md`'s previously-bare `cli`
product row and reframes issue #82's scope from a narrow gh-CLI
substitution wrapper into the CLI product's actual, larger intent.

## Context

Issue #82 was originally filed (and auto-closed on the PR that filed it)
as: an approved, read-only REST API wrapper substituting for the `gh`
CLI, motivated by two still-accurate textual anchors:

- `CLAUDE.md:55` / `AGENTS.md:54` (identical): "For GitHub operations,
  use platform-integrated tool calls (write operations require a paired
  PreToolUse safety hook) or the repository's approved REST API wrapper
  for read operations to reduce token consumption. Do not invoke
  command-line GitHub tools directly."
- `docs/versioning.md`'s `cli` row, which reserved a `cli` product axis
  ("The future gitapex single-binary CLI ... planned Rust rewrite") but
  never elaborated what that binary is actually *for* beyond "a
  single-binary CLI."

The operator has since clarified the real scope this issue was always
meant to hold: gitapex's CLI product is not primarily a GitHub-operations
convenience wrapper. It is a governance and gate-control binary, of which
the gh-read wrapper is one instance, not the boundary.

## Scope: three pillars

1. **SSOT config -- `.gitapex/ssot.json`.** A single source of truth
   configuration file the CLI reads to know what it is governing and how
   (see the naming-collision section below -- this is a distinct concept
   from the toolchain-foundation initiative's own, unrelated
   `.gitapex/toolchain.lock.json`).
2. **Modular policy-engine-driven governance/gate-control.** The CLI
   loads modular policy definition files -- OPA/Rego is the named
   candidate mechanism, not a locked-in decision -- to gate changes to
   the **business domain generally**, not only git/GitHub operations.
   "Business domain" here means: whatever change surface a downstream
   product using gitapex actually needs governed (schema migrations,
   feature-flag changes, pricing-rule changes, etc. are illustrative
   examples of the category, not a committed list).
3. **Middleware and SaaS-integration points.** The CLI provides
   integration points for middleware and third-party SaaS systems as
   consumers or triggers of the governance layer above.

## Relationship to the original REST-wrapper scope

The approved read-only gh wrapper described in `CLAUDE.md`/`AGENTS.md`
and referenced by `skills/issue-to-branch/references/
github-issue-workflow.md` and `skills/merge-retrospective/SKILL.md` is
unchanged in its own specification -- it still needs to exist exactly as
those documents describe it. What changes is its position in the
product: it is now understood as the **first concrete instance** of a
governed-operation type this CLI's policy-engine layer would handle in
general, not as the entire reason the CLI exists. A future child issue
implementing it (see #82's Sub-issues list) should frame it that way --
as pillar 2's first consumer, not as a standalone deliverable disconnected
from the governance layer around it.

## Naming collision: `.gitapex/` (flagged, not resolved)

`docs/superpowers/specs/2026-07-14-setup-gitapex-toolchain-design.md` (a
separate, not-yet-built initiative) already plans two files under
`.gitapex/`:

- `.gitapex/toolchain.lock.json` -- a Nix-eval-**generated** lockfile of
  pinned tool versions (nixpkgs input pins + fetchurl SHA pins), never
  hand-edited.
- `.gitapex/setup.ps1` -- a Windows-native installer script that reads
  that lockfile and installs signed publisher binaries.

That design doc calls the flake itself "the single SSoT" for those
toolchain versions. The new `.gitapex/ssot.json` this doc describes is an
**unrelated file, for an unrelated concept** (business-domain governance
config, not toolchain version pins) -- but it lives in the same directory
and both are now called an "SSOT" for different things. This is a real,
if narrow, ubiquitous-language collision: a future reader skimming
`.gitapex/` should not assume the two files serve the same purpose, or
that "SSOT" means one specific thing repo-wide.

This is **flagged here, not resolved**. Resolving it (e.g. renaming one
concept, or establishing that "SSOT" is legitimately overloaded across
two unrelated subsystems and documenting why) is exactly the job of a
future `establishing-ubiquitous-language` pass, once both files are real
enough to reason about concretely rather than as two still-unbuilt
proposals. Do not pre-emptively rename either concept now.

## Distribution: reusing the Class B binary pattern

Once a compiled gitapex CLI binary exists, this repo already has a
working, proven distribution mechanism it should reuse rather than
reinvent: `flake.nix`'s "Class B" pattern (`mkReleaseBinary`/
`mkClassB`), a SHA-pinned `fetchurl` prebuilt-binary fetch, already used
today for four tools (`waza`, `apm`, `rtk`, `betterleaks`), each exposed
as both `packages.<system>.<name>` and appended to the default devShell,
with per-system (`aarch64-linux`/`x86_64-linux`/`aarch64-darwin`/
`x86_64-darwin`) asset filenames and SHA pins. A future gitapex CLI
release would add a fifth entry to `classBData`, not a new distribution
mechanism.

## Go-avoidance nuance

`flake.nix` and its design doc currently forbid `go install`/
`buildGoModule` (enforced by a grep in the toolchain-foundation plan),
but this is **narrow and tool-specific**: `waza`'s own README states
`go install` is unsupported for that particular tool because of LFS
artifacts. It is not a blanket "no Go" policy for a future gitapex-owned
binary. A gitapex CLI written in Go would ship via the same Class B
prebuilt-release mechanism described above (a compiled release binary,
fetched by SHA pin, never `go install`ed), sidestepping the exact problem
that motivated the existing restriction. **Rust-vs-Go remains a live,
undecided choice** -- Rust is provisional per `docs/versioning.md`'s
existing wording, not committed.

## Non-goals (this pass)

- No `.gitapex/ssot.json` schema finalized or file authored.
- No OPA/Rego (or any other) policy file authored.
- No Rust or Go code or build scaffolding.
- No Rust-vs-Go decision made.
- No wrapper, gate, or governance mechanism actually implemented.
- No `skills/*` file touched -- the two skills that reference the
  approved REST API wrapper (`issue-to-branch`, `merge-retrospective`)
  are unchanged; their existing text remains accurate under this
  elaborated scope.
- No child issues filed against #82 yet (see its own Sub-issues section
  for why).

## Open questions (genuinely undecided, not silently assumed)

- The `.gitapex/ssot.json` schema and shape.
- The policy-engine choice (OPA/Rego vs. alternatives) -- named as a
  candidate, not selected.
- Rust vs. Go for the compiled binary.
- Which middleware/SaaS integrations, if any, come first.
- How (or whether) this CLI's own config model interacts at all with the
  unrelated `.gitapex/toolchain.lock.json` consumption model described in
  the toolchain-foundation design -- they may simply coexist
  independently under the same directory with no interaction; that has
  not been decided either way.
- When child issues get filed against the reopened #82, and in what
  order among the six candidates it currently lists.

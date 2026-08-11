# Migrate plugin-identity SSOT to agent-plugins.org-compliant root plugin.json

## Status

Accepted (approved by tvna, 2026-08-10)

## Context and Problem Statement

gitapex's plugin identity (name, version, description, author, homepage,
repository, license) is currently hand-maintained in `.claude-plugin/plugin.json`,
Claude Code's own plugin manifest format. `docs/versioning.md` and
`docs/repository-layout.md` both document that file as the plugin's
version/identity single source of truth (SSOT), and `apm.yml` mirrors its
`name`/`version` fields under the `apm-manifest-drift` gate
(`.github/scripts/gitapex_scan_apm_manifest_drift.py`, registered in
`.gitapex/ssot.json`).

The repository owner asked (issue #1028) whether this repository can comply
with the agent-plugins.org "Agent Plugins Specification" v1.0.0
(https://agent-plugins.org, spec repository `agentplugins/agent-plugins-spec`).
That specification requires a `plugin.json` at the plugin root carrying a
required `$schema` field pointing at
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`, and forbids
additional top-level properties beyond the ones it names. `.claude-plugin/plugin.json`
carries no `$schema` field today, so the two manifest shapes cannot simply
be the same file without risking either breaking Claude Code's own loading
of it or violating the spec's `additionalProperties: false` constraint.

This is a prospective decision: not yet implemented at the time this ADR
was drafted. Implementation follows in the same change, tracked by issue
#1028.

## Decision Drivers

- Comply with the agent-plugins.org Agent Plugins Specification v1.0.0's
  root-`plugin.json` requirement without risking Claude Code's own existing
  loading of `.claude-plugin/plugin.json`.
- Minimize blast radius to this repository's existing, already-tested
  `apm-manifest-drift` gate (owner's explicit direction, issue #1028).
- Establish the new SSOT with its own drift gate in the same change, per
  this repository's own stated invariant-introduction discipline
  (`CLAUDE.md` section 3: "ship its drift gate in the same change").

## Considered Options

- **Do not adopt the spec; keep `.claude-plugin/plugin.json` as the sole
  manifest and SSOT.** The implicit baseline, superseded once the owner
  chose to pursue compliance.
- **Drop Claude Code's own manifest format and migrate fully to a
  spec-only `plugin.json` at the root**, with Claude Code loading that
  file directly. Not chosen: whether Claude Code's plugin loader tolerates
  the spec's required `$schema` field or its `additionalProperties: false`
  constraint was not verified, and this would abandon the
  `.claude-plugin/plugin.json` convention this repository's docs and
  tooling (`apm-manifest-drift`, `docs/versioning.md`) already depend on.
- **Dual-manifest management: keep `.claude-plugin/plugin.json` as
  Claude Code's manifest, add a new spec-compliant `plugin.json` at the
  root as the SSOT, and mechanically generate the former from the
  latter.** Chosen -- owner's explicit direction, issue #1028.

Two sub-decisions were also explicitly weighed within the chosen option,
both recorded as the owner's answers in issue #1028:

- Whether to also validate the new root manifest against the spec's JSON
  Schema in CI now, or defer it: chosen -- validate now, via a vendored,
  commit-pinned copy of the schema (no upstream release tag exists yet).
- Whether the existing `apm-manifest-drift` gate should be repointed at
  the new root manifest, or kept pointed at the generated
  `.claude-plugin/plugin.json`: chosen -- keep it pointed at the generated
  file. Its own comparison logic needs zero code changes, and the new
  generation-drift gate keeps that file transitively accurate against the
  new SSOT.

## Decision Outcome

We will add a new agent-plugins.org v1.0.0-compliant `plugin.json` at the
repository root as the plugin-identity SSOT, mechanically generate
`.claude-plugin/plugin.json` from it (stripping only the `$schema` key),
and validate the root manifest against a vendored, commit-pinned copy of
the spec's `plugin.schema.json` in CI -- because this is the only
considered option that achieves agent-plugins.org compliance while
leaving Claude Code's own plugin loading, and the existing
`apm-manifest-drift` gate's tested comparison logic, unchanged.

## Consequences

Good, because the root `plugin.json` is schema-conformant to
agent-plugins.org v1.0.0, verifiable by an automated CI gate rather than
manual inspection.
Good, because Claude Code's own plugin loading is untouched --
`.claude-plugin/plugin.json` keeps its existing shape; only its
provenance changes, from hand-edited to generated.
Good, because `apm-manifest-drift`'s existing, already-tested comparison
logic requires zero code changes.
Bad, because two `plugin.json` files now exist in the repository (root
and `.claude-plugin/`), which could confuse a future contributor editing
the wrong one -- mitigated by the generation-drift gate failing loudly on
a stale `.claude-plugin/plugin.json`, and by `docs/repository-layout.md`'s
updated prose naming which file is which.
Bad, because the vendored agent-plugins.org schema is pinned to a commit
SHA, not a release tag, since none exists upstream as of this decision --
the pin can only be freshly re-verified via an opt-in `--verify-upstream`
network check, not automatically in CI.
Bad, because two more gates enter `.gitapex/ssot.json`'s own registry,
adding to that file's maintenance surface.

## Confirmation

The `plugin-manifest-mirror-drift` and `plugin-manifest-schema-conformance`
gates themselves (both to be registered in `.gitapex/ssot.json`, enforced
via the pytest step of `.github/workflows/test.yml`) are the primary
mechanism: a hand-edit to `.claude-plugin/plugin.json` that diverges from
a fresh regeneration, or a schema-violating edit to the root
`plugin.json`, fails CI rather than relying on review memory.

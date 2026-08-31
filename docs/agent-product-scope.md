# Agent product scope

"Which agent products does GitApex support?" is not one question in
this repository -- it is six, spanning three dimensions (agent tools,
git-hosting platform, dependency middleware), and each has a different
answer, a different owner, and a different reason to grow or shrink.
This file names all six axes so a reader gets one map instead of
piecing it together from separate documents. It only organizes and
cross-references what already exists elsewhere; it does not change any
existing list's membership or authority (gitapex#445).

Axes A-D cover agent tools/runtimes. Axis E covers the git-hosting
platform(s) GitApex assumes. Axis F covers the middleware/toolchain it
depends on. `skills/auditing-agent-product-scope/` formalizes the
research-classify-document procedure that maintains this map going
forward (gitapex#445, reframed).

## Axis A: Plugin-distribution target

**Governs:** which agent products GitApex itself can literally be
installed into -- i.e. which products load `skills/` from this
repository via `apm install` or `/plugin marketplace add`.

**Current scope:** Claude Code, unambiguously. Whether Codex's
`apm install` path already qualifies is unresolved, not settled by this
doc: [`repository-layout.md`](repository-layout.md) itself currently
says "gitapex is a Claude Code / Codex plugin" and lists `skills/` as
"deployed by apm/Claude/Codex," but the originating decision in
[`superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`](superpowers/specs/2026-07-12-skill-distribution-foundation-design.md)
scoped this explicitly to "Claude Code only for this pass" and named
`.codex-plugin/plugin.json` (a separate, Codex-specific manifest) as a
deferred non-goal -- a file that still does not exist anywhere in this
repository today. This doc surfaces that inconsistency rather than
resolving it: deciding whether Codex's scope already qualifies is the
larger Axis-A-expansion decision gitapex#445 explicitly left to the
owner (see #445's own Non-goals).

**Owning doc:** [`repository-layout.md`](repository-layout.md) (current
statement, itself internally inconsistent as described above).

**Boundary:** expanding this axis means shipping new manifest formats
and install paths -- real engineering work, not a docs change. Nothing
in Axis B, C, or D implies GitApex is installable in the runtimes they
list.

## Axis B: Enforcement-adapter target set

**Governs:** which runtimes a future per-skill execution-requirement
enforcement adapter (least-privilege tool/filesystem/network gating)
will be built for.

**Current scope:** six runtimes -- Claude Code, Codex, Gemini CLI,
Devin, OpenClaw, HermesAgent.

**Owning issue:** gitapex#307 (parent tracking issue); first slice
(the `executionRequirements` sidecar envelope) shipped in gitapex#349.

**Boundary:** this is a target list for future enforcement code. It is
not a claim that GitApex is installable in these runtimes (Axis A), nor
that its skills' behavior has been empirically verified against all
six today.

## Axis C: Skill-quality-review evidence baseline

**Governs:** primary-source evidence used by the
`evaluating-skill-quality` skill's warning-only compatibility-awareness
axis, so that *other people's* skills -- not GitApex itself -- can be
reviewed for cross-runtime frontmatter and behavior risk.

**Current scope:** eleven runtimes, listed in
[`../skills/evaluating-skill-quality/references/runtime-compatibility.md`](../skills/evaluating-skill-quality/references/runtime-compatibility.md):
Claude Code, Codex, Gemini CLI, Devin, Windsurf, OpenClaw, HermesAgent,
Kimi CLI, Cursor, GitHub Copilot, Kiro.

**Owning issues:** gitapex#332 (the original six, matching Axis B at
the time); gitapex#443 and gitapex#444 (growth to eleven -- neither
cites gitapex#307).

**Boundary:** that file already states of itself "this is ... not an
enforcement adapter." Adding a runtime here does not add it to Axis A
or Axis B -- reviewing a skill for Cursor-compatibility, for example,
says nothing about whether GitApex is installable in Cursor or whether
a future enforcement adapter targets it.

## Axis D: Hook-quality evidence baseline (proposed, unshipped)

**Governs:** the same evidence-baseline pattern as Axis C, proposed for
a not-yet-built skill covering hooks (deterministic gates) instead of
skills.

**Current scope:** the same six runtimes as Axis B, reused by naming
precedent only -- no independent selection has been made for this
axis.

**Owning issue:** gitapex#435 (research report only; no shipped skill,
no cross-reference to gitapex#307).

**Boundary:** if and when a skill ships from this research, its owning
issue should update this section with the shipped skill's name and its
own current scope, the same way gitapex#443/gitapex#444 updated Axis
C's scope after gitapex#332 shipped it.

## Axis E: Git-hosting platform target

**Governs:** which git-hosting platform(s) GitApex's own tooling
(hooks, CI) assumes versus which platforms its skills claim to support
when vendored into a different repository.

**Current scope:** GitHub, exclusively, for this repository's own
operational tooling -- `hooks/check-bash-safety.sh` denylists `gh` CLI
write subcommands specifically, `.github/` CI is inherently GitHub
Actions, and `apm.lock.yaml` pins both of GitApex's own apm dependencies
to `host: github.com`. GitHub and GitLab are both supported at the
skill-portability level by `skills/scanning-attack-surfaces/`, whose
Mode B audits either platform's hosting-configuration surface when a
skill copy is used against a target repository -- Gitea and Bitbucket are not
mentioned anywhere in this repository.

**Owning skill:** `skills/scanning-attack-surfaces/` (gitapex#82), which
absorbed the standalone `auditing-git-hosting-surface` skill that
previously owned this axis (gitapex#848).

**Boundary:** this axis does not duplicate that skill's checklists or
platform-detection logic -- it only names the axis and points to the
skill that owns it. A platform finding belongs in that skill's own
checklist references, not here.

## Axis F: Dependency middleware

**Governs:** the middleware and toolchain GitApex's own development
depends on -- distinct from Axis A-E, which are all about agent
products or git-hosting platforms, not the tools that build and test
this repository itself.

**Current scope:** listed in
[`../skills/auditing-agent-product-scope/references/middleware-inventory.md`](../skills/auditing-agent-product-scope/references/middleware-inventory.md):
the Nix-managed toolchain (`flake.nix`'s Class A nixpkgs tools and
Class B SHA-pinned release binaries -- `waza`, `apm`, `rtk`,
`betterleaks`), apm itself (`apm.yml`/`apm.lock.yaml`, consuming
`obra/superpowers` and `tvna/clairvoyance`), Python dev tooling
(`pyproject.toml`/`uv.lock`), and the GitHub MCP server (the one
universal skill-level dependency; no GitLab MCP server exists).

**Owning skill:** `skills/auditing-agent-product-scope/` (gitapex#445,
reframed).

**Boundary:** unlike Axis A-D, this axis's primary source is the
observed repository state itself (the dependency-declaring files), not
third-party vendor documentation. Adding a middleware entry here does
not imply anything about Axis A-E. The Class B release binaries
(`waza`/`apm`/`rtk`/`betterleaks`) have no Dependabot ecosystem
coverage today; that gap is tracked separately as a sub-task of
gitapex#57, not by this axis's own evidence file.

## Non-conflation rule

Adding, removing, or reclassifying a runtime, platform, or dependency
on one axis does not change any other axis. A PR that changes one
axis's list should not assume the others need updating too, unless its
own issue explicitly says so. When a name shows up on more than one
axis (e.g. Claude Code, Codex; or GitHub, which is both Axis E's
current scope and part of Axis F's apm-hosting detail), that is
independent judgment calls landing on the same name, not one shared
entry.

## Maintenance

`skills/auditing-agent-product-scope/` formalizes how this file is
kept current: given a candidate agent tool, platform, or middleware
dependency, it fetches primary documentation directly, classifies it
Documented/Unknown/Conflict, adds a finding to the axis's owning
evidence file, and updates the relevant axis section here plus the
touched file's own provenance notes. Do not edit the dated design-spec
records under `superpowers/specs/` to keep them "current" -- those are
point-in-time decisions, not living docs; this file is the living
cross-reference instead. `python3 skills/auditing-agent-product-scope/scripts/gitapex_check_axis_shape.py docs/agent-product-scope.md`
verifies every axis section still carries its four required fields
after an edit.

This file's own history, kept here rather than in the maintaining
skill's own reference files (which are read on every invocation,
including a vendored copy elsewhere, and should stay free of history
that does not change what the Procedure does): this doc originally
shipped as a hand-written reconciliation of four never-reconciled
axes (gitapex#443, gitapex#444); gitapex#445 then reframed that
one-off doc into the `auditing-agent-product-scope` skill formalizing
the same research-classify-document procedure and adding Axis E/F.
Axis A's Claude-Code-vs-Codex contradiction (see that axis's own
Current scope above) was surfaced rather than resolved directly in
its axis section during PR #447's review -- the worked precedent for
how a future candidate's own surfaced contradiction should be
recorded, per this skill's SKILL.md Step 7.

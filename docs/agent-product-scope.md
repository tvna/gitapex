# Agent product scope

"Which agent products does GitApex support?" is not one question in
this repository -- it is four, and each has a different answer, a
different owner, and a different reason to grow or shrink. This file
names the four axes so a reader gets one map instead of piecing it
together from four separate documents. It only organizes and
cross-references what already exists elsewhere; it does not change any
existing list's membership or authority (gitapex#445).

## Axis A: Plugin-distribution target

**Governs:** which agent products GitApex itself can literally be
installed into -- i.e. which products load `skills/` from this
repository via `apm install` or `/plugin marketplace add`.

**Current scope:** Claude Code. Codex is named but explicitly deferred.

**Owning doc:** [`repository-layout.md`](repository-layout.md) (current
statement); originating decision:
[`superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`](superpowers/specs/2026-07-12-skill-distribution-foundation-design.md)
("Claude Code only for this pass," with `.codex-plugin/plugin.json` and
`.agents/plugins/marketplace.json` named and deferred as a non-goal).

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

## Non-conflation rule

Adding, removing, or reclassifying a runtime on one axis does not
change any other axis. A PR that changes one axis's list should not
assume the others need updating too, unless its own issue explicitly
says so. When a runtime shows up on more than one axis (e.g. Claude
Code, Codex), that is four independent judgment calls landing on the
same name, not one shared entry.

## Maintenance

This file is maintained by whichever issue or PR next changes one
axis's scope: update that axis's section (current scope, owning
issue) and cite the change, the same provenance-note pattern already
used in `skills/evaluating-skill-quality/metadata/gitapex.yaml`. Do not
edit the dated design-spec records under `superpowers/specs/` to keep
them "current" -- those are point-in-time decisions, not living docs;
this file is the living cross-reference instead.

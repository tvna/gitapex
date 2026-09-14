# Project spec.contract verbatim into SKILL.md; every other spec block stays sidecar-only

## Status

Proposed

## Context and Problem Statement

This decision is fully implemented as of this same PR (issue #1965's own
foundation task): `skills/evaluating-skill-quality/references/skill-metadata.schema.json`'s
`$defs/contract` block (commit `dcf32779`), the generator that actually
performs the projection this ADR describes
(`skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py`),
its `--check` gate (`skill-contract-drift`, registered in
`.gitapex/ssot.json`), and the gate-id resolution addition to the ssot
scanner (`.github/scripts/gitapex_scan_ssot_schema.py`) all landed
together under https://github.com/tvna/gitapex/issues/1965. Zero real
skills declare `spec.contract` yet -- migration to this form is separate,
per-skill work, tracked under the sibling child issues
https://github.com/tvna/gitapex/issues/1966
(`eliciting-a-design` migration) and
https://github.com/tvna/gitapex/issues/1967
(`drafting-a-pr-to-merge` migration), under parent tracking issue
https://github.com/tvna/gitapex/issues/1964.

`docs/gitapex/specs/2026-09-12-skill-contract-form-design.md` (design
agreed via `eliciting-a-design` dialogue with the repository owner,
2026-09-11/12) proposes demoting each pipeline skill's `SKILL.md` body
from an exact-order numbered procedure to high-freedom prose plus a
small generated contract block (Precondition / Goal / Invariants / Gates
/ Escalation / Handoff), with the exact-order steps a CI check parses
moved out to `references/procedure.md`. The generator's only input is a
skill's own `metadata/gitapex.yaml` sidecar.

Every `spec` block in that sidecar today (`references`,
`skillDependencies`, `lifecycle`, `executionRequirements`, and the rest)
is maintainer-facing and sidecar-only. `skills/evaluating-skill-quality/references/rubric.md`
states this as the sidecar's own behavior-neutrality invariant, currently
worded against one block: "Per the sidecar's own behavior-neutrality
invariant, `spec.lifecycle` is metadata only: no skill's own runtime
procedure may read or branch on any part of it" (line 1556-1558), and
separately (line 94-95) that the sidecar as a whole "is maintainer-facing
and never auto-loaded." Introducing a generator that *does* read the
sidecar, at build time, to write into `SKILL.md`, forced a decision on
how far that reading goes: project the sidecar's entire `spec` object
verbatim (collapsing the maintainer-facing/generated distinction to
nothing), or project exactly one bounded, purpose-built block and leave
every other block exactly as sidecar-only as before.

A second, narrower question needed resolving in the same design pass:
whether the contract's `goal` block could carry more than one end state,
and what to name the block recording which deterministic checks back a
contract's output -- the design doc's Architecture section's own example
YAML and rendered-`SKILL.md` heading list both used the working name
`proof`.

## Decision Drivers

- The sidecar's existing behavior-neutrality invariant must not be
  weakened by adding a generator that reads the sidecar -- a build-time
  generator is a distinct actor from a skill's own runtime procedure, and
  the decision needed to make that distinction explicit rather than
  assume it.
- Keep the blast radius of a first, prototype-stage generator narrow: one
  bounded block, not the whole `spec`, so a future `spec.*` addition (a
  new maintainer-facing field) does not silently become build-time
  rendered without a deliberate, separate opt-in.
- A contract's `goal` should describe one thing a reader can check the
  procedure actually reached, not a list -- consistent with the `/goal`-
  style single-end-state framing the design doc's Architecture section
  cites, and with this session's own earlier conclusion, reached while
  decomposing this branch's own tasks, that multiple end states are a
  decomposition smell (a sign the skill should split into more than one),
  not a reason to widen `goal` into an array.
- Avoid a name collision already present in this repository's own
  vocabulary: the Acceptance Criteria Map's existing "Proof method"
  column.

## Considered Options

- Project the sidecar's entire `spec` object into `SKILL.md` verbatim.
  This was the direction the design doc's Decision Record option B first
  reached for (reading `lifecycle` at generation time to pick a rendered
  lane label), before being found to collide with the sidecar's own
  behavior-neutrality invariant -- collapsing "maintainer-facing" and
  "generated" onto the same reading path makes every future `spec.*`
  field a de facto public, rendered one merely by existing in the
  sidecar, with no way left to add a maintainer-only field without a
  fresh carve-out.
- Project `spec.contract` plus `spec.lifecycle` together, so a skill's
  `experimental`/`stable` lane also renders into `SKILL.md`. Considered
  and rejected in the design dialogue (Decision Record, option B) for the
  same behavior-neutrality reason: `lifecycle` stays a sidecar-only,
  maintainer-facing field, read by tooling (`scorer-gated-skill-edits`,
  the eval-status index) but never by a skill's own runtime procedure,
  and not rendered into its body.
- Project exactly `spec.contract` -- a single block
  (`precondition`/`goal`/`invariants`/`gates`/`escalation`/`handoff`)
  that exists for no purpose other than being rendered -- leaving
  `references`, `skillDependencies`, `lifecycle`,
  `executionRequirements`, and every other `spec` block exactly as
  sidecar-only as today. Chosen.
- For `goal`: allow an array of end states, mirroring `invariants[]`'s
  and `gates[]`'s own list shape. Rejected: a contract stating several
  end states is the same smell as a skill trying to do several unrelated
  things in one `SKILL.md` -- the fix is splitting the skill, not
  widening the schema to carry the split inline.
- For the block naming which deterministic checks back a contract's
  output: keep the design doc's original working name, `proof`. Rejected
  once the name was found to collide with the Acceptance Criteria Map's
  existing "Proof method" column (`Evidence` was also on the table per
  the design doc's Vocabulary section, but not chosen).
- `Gates`. Chosen name for that block, resolved by the repository owner
  directly on 2026-09-13 via `establishing-ubiquitous-language`'s Resolve
  step, recorded in `docs/glossary.md`'s `Gates` entry.

## Decision Outcome

We will make `spec.contract` the one `spec` block a build-time generator
ever projects into a skill's `SKILL.md`, inside a marker-delimited region
(`<!-- gitapex:contract:begin -->` / `<!-- gitapex:contract:end -->`),
because it is the only considered shape that adds a generated, rendered
view of part of the sidecar without collapsing the sidecar's existing
maintainer-facing/generated distinction for every other block. Concretely,
per the schema shape this branch's foundation task already merged
(`skills/evaluating-skill-quality/references/skill-metadata.schema.json`'s
`$defs/contract`):

- `spec.contract` is optional at the sidecar's top level; a skill with no
  `spec.contract` declares no contract yet and is not a generator target
  -- migration stays opt-in, one skill at a time.
- The projected block has six named children: `precondition` (array,
  optional), `goal` (object, required), `invariants` (array, optional),
  `gates` (array, optional), `escalation` (array, optional), `handoff`
  (object, required). `goal` and `handoff` are the only two required
  children -- a contract must state what it is trying to reach and where
  control goes once it is done; everything else is an optional
  refinement a simpler contract may omit.
- `goal` (`$defs/contractGoal`) carries exactly one `endState` and one
  `check`, plus an optional `constraints` list -- never an array of end
  states. We will keep `goal` singular because a contract states one
  measurable end state a reader can check the procedure actually
  reached; a skill whose own work genuinely has more than one end state
  is a decomposition signal -- it should split into more than one skill,
  each with its own contract -- not a reason to let one contract carry
  several.
- The block recording which deterministic checks back a contract's
  output is named `gates` (`$defs/contractGate`: `id`, `plane`,
  `shipped`), not `proof` -- the design doc's own original working name.
  `proof` collided with the Acceptance Criteria Map's own "Proof method"
  column; the repository owner resolved the collision directly on
  2026-09-13 via `establishing-ubiquitous-language`'s Resolve step,
  recorded in `docs/glossary.md`'s `Gates` entry: "the design doc's own
  working name, `Proof`, collided with the ACM's `Proof method` column
  (`Evidence` was also considered); `Gates` wins as the distinct term."
- Every other `spec` block -- `references`, `skillDependencies`,
  `lifecycle`, `executionRequirements`, and any future addition -- stays
  exactly as maintainer-facing and sidecar-only as it is today: no
  skill's own runtime procedure may read or branch on any part of the
  sidecar, `spec.contract` included. This invariant is not weakened by
  this decision. The generator that projects `spec.contract` into
  `SKILL.md` at build time is a different actor than a skill's own
  runtime procedure reading its own sidecar to decide how to behave --
  the distinction this decision turns on -- and it reads and writes only
  inside the one skill directory it targets, never
  `.gitapex/ssot.json` or a sibling skill's own directory.

The generator itself, its `skill-contract-drift` gate, and the gate-id
resolution addition to the ssot scanner all shipped together with this
ADR under the same foundation-task PR, https://github.com/tvna/gitapex/issues/1965.
The migration work that actually moves a real skill onto this shape stays
separate and prospective, tracked under
https://github.com/tvna/gitapex/issues/1966 /
https://github.com/tvna/gitapex/issues/1967, all under parent tracking
issue https://github.com/tvna/gitapex/issues/1964.

## Consequences

Good, because a future `spec.*` field can be added for a purely
maintainer-facing purpose (a new provenance or dependency-tracking need)
without any risk of it silently becoming rendered into a skill's public
body -- only a field explicitly added under `spec.contract` is ever
projected.

Good, because the sidecar's existing behavior-neutrality invariant needs
no exception carved into it: the generator is a build-time actor
distinct from a skill's own runtime procedure, so the invariant's wording
("no skill's own runtime procedure may read or branch on any part of
it") stays true without qualification, for `spec.contract` as much as
for `spec.lifecycle` or any other block.

Good, because keeping `goal` singular keeps a generated contract's own
completion check unambiguous -- one end state, one check -- rather than
requiring a downstream consumer (a citing skill, a reviewer) to reason
about which of several end states a partially met contract actually
reached.

Good, because `Gates` avoids a real, already-encountered naming
collision with the Acceptance Criteria Map's "Proof method" column, so a
future reader of either artifact is not left guessing which concept a
given "proof"/"Gates" mention refers to.

Bad, because a skill migrating to the contract form must still do the
degree-of-freedom triage the design doc's Architecture section
describes (high-freedom prose stays in `## Approach`; exact-order steps
move to `references/procedure.md`) for content that does not fit
cleanly into `spec.contract`'s six blocks -- this is real per-skill
migration work, not automated by this decision alone.

Bad, because until a real skill actually migrates
(https://github.com/tvna/gitapex/issues/1966 /
https://github.com/tvna/gitapex/issues/1967), `spec.contract` is a
declared-and-enforced-but-unused shape: the schema, generator, and
`skill-contract-drift` gate all landed together in this same PR, but
zero real skills declare `spec.contract` yet, so the gate is exercised
only by its own synthetic test fixtures today, not by any production
target.

Bad, because `precondition[].onFail`, `escalation[].to`, and
`gates[].id` are deliberately open, non-enum string fields for now (per
the schema's own field descriptions) -- a typo'd `onFail` or `to` value
is not yet caught by schema validation, only by review, until a
follow-up gates each against a fixed vocabulary.

Unknown, pending https://github.com/tvna/gitapex/issues/1966 (the
`eliciting-a-design` migration -- the first real skill to move onto this
shape): whether the six-block contract form actually holds up against a
real skill's full procedure without needing a seventh block or a
reshaping of one of the six, and whether the degree-of-freedom triage
table produces a body that is measurably clearer than today's
numbered-step form.

## Confirmation

Two gates, both shipped together with this ADR under
https://github.com/tvna/gitapex/issues/1965:
`skill-contract-drift` (a new `.gitapex/ssot.json` `ci`/`local` entry
whose `--check` mode re-renders each contract-declaring skill's marker
region from its sidecar and diffs it against the committed one) is the
mechanism that verifies a `SKILL.md`'s generated region actually
matches its sidecar's `spec.contract`; a gate-id resolution addition to
the existing `ssot-schema-drift` scanner
(`.github/scripts/gitapex_scan_ssot_schema.py`) verifies every
`invariants[].gate` and `gates[].id` entry actually names a real gate in
`.gitapex/ssot.json`. Both are exercised today only by their own
synthetic test fixtures, since zero real skills declare `spec.contract`
yet; once a real skill migrates, compliance with the projection boundary
this ADR states is enforced by these two gates directly, not review
alone -- the same as the schema's own `additionalProperties: false`
constraint on `$defs/contract` still relies on review to notice a
hand-edit that tries to smuggle a non-contract field in via a sibling
`spec` block instead.

# Skill contract form: `spec.contract` as the source, generated contract block, demoted procedure (design)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-11/12 with the
repository owner and formalized the same day into tracking issue
https://github.com/tvna/gitapex/issues/1964 with four child issues (see
Rollout). This document describes the settled design and records the
decomposition into four pull requests and the decisions made along the
way. The verification-reduction half is recorded as an accepted ADR,
`docs/adr/0004-reduce-verification-to-one-fresh-review-per-diff.md`
(approved 2026-09-13), which also carries the 2025-2026 published
evidence listed under Evidence below.

## Problem

The core pipeline skills (`eliciting-a-design`, `drafting-issues`,
`planning-a-branch-from-an-issue`, `executing-a-branch-plan`,
`drafting-a-pr-to-merge`, `merge-retrospective`) are written as
"Exact sequence, do not reorder or skip" step lists, with adversarial
verification hard-wired as mandatory steps inside each skill
(`executing-a-branch-plan` Step 8, `drafting-a-pr-to-merge` Step 8,
`drafting-a-skill` Step 7). Three measured consequences:

- Five of 29 `SKILL.md` bodies sit at or within 7 lines of the 500-line
  ceiling; `eliciting-a-design` is 414 lines and roughly 10,500 tokens,
  more than twice the 5,000-token body budget introduced by
  https://github.com/tvna/gitapex/issues/1698.
- Every change pays the same verification cost regardless of blast
  radius, and the recent commit history is dominated by
  "close adversarial-review findings" fix commits.
- Editing `SKILL.md` and `references/*.md` directly lets the authoring
  session's reasoning leak into the artifact: the requirements a skill
  must satisfy and the minimal text a model needs at invocation time are
  two different things, but today they are written into the same file
  in the same pass.

Two primary sources motivate the direction (both fetched and quoted
during the design dialogue, see Evidence):

- Anthropic, "Prompting Claude Opus 5": explicit verification
  instructions and "use a subagent to verify" instructions cause
  over-verification and should be removed; the model verifies its own
  work unprompted.
- Anthropic, "Steering Claude Code": a real guardrail must be
  deterministic, enforced by hooks and permissions; procedures belong in
  skills, standing facts in `CLAUDE.md`.

The repository's own `evaluating-skill-quality/references/rubric.md`
already carries the vocabulary this design needs: Dimension 3 (Degree
of freedom: prose vs. parameterised vs. exact steps, matched to
fragility) and the Contract discipline section (Meyer's Precondition /
Postcondition / Invariant).

## Scope

### In scope

- A structured contract block, `spec.contract`, in each migrated skill's
  `metadata/gitapex.yaml`, carrying six elements: Precondition, Goal,
  Invariants, Gates, Escalation, Handoff.
- A generator, bundled with `drafting-a-skill`, that renders
  `spec.contract` into a marker-delimited region at the top of that
  skill's `SKILL.md`, plus a `--check` drift mode.
- A repository gate registering that drift check and a gate-id
  resolution check for `invariants[].gate` and `gates[].id`.
- A schema change adding `spec.contract`, recorded as an ADR (next free number after 0004).
- Glossary entries for the new terms, via
  `establishing-ubiquitous-language`, before any heading is rendered.
- Migration of `eliciting-a-design` (first prototype) and
  `drafting-a-pr-to-merge` (second prototype, low-freedom control).

- Verification reduction (PR0): cutting the verification layers whose
  measured yield does not justify their cost, while keeping the layers
  that measurably find defects. See "Verification reduction" below.
  Scope revision, 2026-09-12: the owner restated that reducing
  verification was half of the original question; an earlier draft of
  this document listed it as out of scope, and this section plus PR0
  replace that listing.

### Out of scope (separate issues)

- Narrowing or removing Dimension 5's sequential-pipeline exemption
  (added by https://github.com/tvna/gitapex/pull/1672 for
  https://github.com/tvna/gitapex/issues/1662). The owner routes rubric
  edits through `scorer-gated-skill-edits`; this happens after the
  contract form has reached the core six skills.
- Ablating `invoking-gitapex`'s Red Flags table, and narrowing per-task
  `screening-a-low-trust-contribution` on self-authored diffs. Both are
  measure-first items: they need an eval baseline (API credentials)
  before a cut can be justified; the upstream lineage (obra/superpowers)
  reported measured TDD regression when a comparable table was removed.
- Migrating the remaining four core skills. Decided after the two
  prototypes land.
- Any change to `BODY_MAX_LINES` or `BODY_MAX_TOKENS`.

## Verification reduction

Decision record: `docs/adr/0004-reduce-verification-to-one-fresh-review-per-diff.md`
(Accepted, approved by tvna, 2026-09-13). The ADR is the authoritative
statement of the decision and its evidence; this section is the design
view of the same decision.

### Reading rule

Three sources are read together. Anthropic's "Prompting Claude Opus 5"
guide: explicit verification instructions and "use a subagent to verify"
instructions cause over-verification and should be removed. Anthropic's
"Steering Claude Code": a real guardrail is deterministic, enforced by
hooks and permissions. AGENTS.md section 4: never collapse a layer safety
relies on. The reconciliation: deterministic gates (hooks, CI, local
preflight) keep their layers; probabilistic self-verification
instructions are cut by measurement; exactly one fresh-context
adversarial review per diff is kept.

### Measured yield per layer

Measured from the bodies of the eight most recently closed pull requests
(#1803, #1825, #1916, #1917, #1936, #1942, #1945, #1954), retrospectives
#1955 and #1951, and issue #1807, all read on 2026-09-12.

| Layer | Measured | Verdict |
|---|---|---|
| `executing-a-branch-plan` Step 8 adversarial review (fresh `review-persona`) | Confirmed defects in every PR where it ran: #1954 8 findings / 5 fixed, #1942 3, #1916 6, #1825 17 | Keep. This is the one fresh-context review per diff |
| `executing-a-branch-plan` Step 8 refactor pass | #1954 clean; retro #1759 fixed 3 corruptions | Shrink: diagnose only, edits in the main thread; fold into the review if yield stays low |
| `drafting-a-pr-to-merge` Step 8 outer layer (Copilot / Claude Code Review App) | Zero responses in the sample; #1916 skipped on the owner's instruction; #1905 already cut the wait from 30 to 15 minutes; on #1969 most of 27 minutes and ~350k tokens went to polling | Remove the synchronous wait: request, record, handle any response at the next event |
| `drafting-a-pr-to-merge` Step 8 inner layer (`reviewing-an-artifact` fan-out) | #1954 and #1969 zero confirmed; #1825 real cross-file drift over two fan-outs | Shrink: skip when the Execution log records a same-head adversarial review; otherwise one pass |
| `battle-testing-a-skill` on `SKILL.md` changes | #1803 FAIL 2, #1825 FAIL 5, #1942 PASS after two fix rounds | Keep |
| `evaluating-skill-quality` on `SKILL.md` changes | Real dimension-6 findings (#1951); up to three passes per PR (#1942); two-hour dispatch timeout (#1825) | Shrink: one isolated pass plus one post-fix pass; a third escalates |
| `merge-retrospective` gate-proposal filing | #1955: 12 repairs, 6 filed, 5 closed as duplicates within minutes; #1807: Step 8's working-as-designed catches are the largest volume driver; 120 open / 141 closed gate proposals | Shrink via #1807 direction (a): tag working-as-designed catches, do not file them. #1806's dedup mechanics stay |
| Per-task `screening-a-low-trust-contribution` on self-authored diffs | #1954: three runs, hard flags on governance paths need human sign-off | Measure first (security tier) |
| `invoking-gitapex` per-turn skill check and Red Flags | No measurement | Measure first (ablation) |
| Local preflight (49) and CI gates (73) | #1955 repairs 2 and 3 caught before push | Keep |
| PreToolUse and Stop hooks | Work as designed; the Stop hook also blocks a push to a PR-less branch (#1631 open, #1940 closed as duplicate) | Keep; fix the PR-less case |
| `skill-audit-disclosure` lines | Disclosure, not verification | Keep |

### Connection to the contract form

The inner-layer rule needs a machine-readable record of which review ran
against which head. That record is what the `gates` block and the
Execution log carry. Migrating to the contract form without reducing
verification shrinks bodies but not per-PR cost; the two halves meet in
`gates`.

## Architecture

### The contract model

`spec.contract` is the single block of the sidecar that is projected
into `SKILL.md` at build time. Every other `spec` block stays
maintainer-facing and never auto-loaded, exactly as today. This is
issue #1965's own Proposed solution 1, shipped as
`skills/evaluating-skill-quality/references/skill-metadata.schema.json`'s
`$defs/contract` (`additionalProperties: false`); the shape below is
that schema's own shipped shape. See
`docs/adr/0005-spec-contract-projection.md` for the projection decision
and the naming decisions this section reflects.

```yaml
spec:
  contract:
    precondition:                # optional; absent/empty means "none declared"
      - id: kebab-id
        check: "a checkable fact that must hold before the first step"
        onFail: escalate         # free kebab-case action label (e.g.
                                  # "escalate", "retry-once"); no closed enum
    goal:                        # required
      endState: "one measurable end state"
      check: "how the model proves it"
      constraints: ["what must not change on the way"]   # optional
    invariants:                  # optional; absent/empty means "none declared"
      - text: "Never ..."
        gate: some-ssot-gate-id  # required key; string, or null (prose-only)
    gates:                       # optional; absent/empty means "none declared"
      - id: some-ssot-gate-id
        plane: ci                # ci | local | pretooluse | posttooluse | stop
        shipped: true            # ships to a consumer install (true, a hook plane) vs. gitapex repository only (false, ci/local)
    escalation:                  # optional; absent/empty means "none declared"
      - when: "condition"
        to: owner                # free kebab-case target; no closed enum yet
    handoff:                     # required
      next:                      # required
        skill: next-skill
        fallback: fallback-skill # optional
        carries: what            # optional
      inline: [skills-invoked-mid-procedure-when-available]   # optional
      optional: [optional-tooling]                            # optional
      downstream: "what the next consumer re-derives on its own"   # optional
```

Only `goal` and `handoff` are required at the top level: a contract
must state what it is trying to reach and where it hands off next;
`precondition`/`invariants`/`gates`/`escalation` are optional
refinements a simpler contract may omit. `goal` follows Claude Code's
`/goal` guidance verbatim: exactly one `endState` and one `check`, plus
an optional `constraints` list -- never an array of end states; the
singular shape and its rationale are recorded in
`docs/adr/0005-spec-contract-projection.md`'s Decision Drivers/Decision
Outcome (see Vocabulary below). `invariants` are today's Stop
boundaries; each entry's `gate` key is required but nullable,
disclosing either the ssot gate id that backs it or, as an explicit
`null`, that only prose enforces it.

The block naming which deterministic checks back a contract's output
is `gates` (`id`/`plane`/`shipped`), not `proof` -- this document's own
original working name, renamed by the repository owner on 2026-09-13
against issue #1965, the authoritative record of that decision; see
Vocabulary below.

### The rendered `SKILL.md`

```markdown
---
name: the-skill
description: (from spec.description)
---
# Title

<!-- gitapex:contract:begin -->
## Precondition
## Goal
## Invariants
## Gates
## Escalation
## Handoff
<!-- gitapex:contract:end -->

## Approach
(hand-written, high-freedom prose: the judgment the model needs, when to
apply which technique, no numbered checklist)

## Fragile operations
See references/procedure.md for the exact-order sequence.
```

The six headings, in this order, are
`skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py`'s
own shipped heading constants (`render_contract_region`, in
`spec.contract`'s own schema-property order: `precondition`, `goal`,
`invariants`, `gates`, `escalation`, `handoff`), taken verbatim from
`docs/glossary.md`'s own `Goal`/`Gates`/`Escalation`/`Handoff`/
`Invariants` entries; `docs/glossary.md` has no standalone entry for
`precondition`, so the generator titles that heading after the
schema's own field name instead, following the same title-casing
convention the other five already use.

The marker pair is the literal two lines `<!-- gitapex:contract:begin
-->` and `<!-- gitapex:contract:end -->`, each occupying its own line
with nothing else on it -- not, as an earlier draft of this section
showed, a marker carrying an inline "generated from ...; do not edit"
comment on the same line. The generator rejects any content sharing a
marker's own line (an adversarial-review finding closed during the
generator's own build-out, issue #1965): content appended onto the
begin marker's own line used to let the region-replacement logic
silently place injected text outside the computed region, undetected
by `--check`.

Each of the six blocks renders through its own function
(`_render_precondition`, `_render_goal`, `_render_invariants`,
`_render_gates`, `_render_escalation`, `_render_handoff`), producing
plain Markdown with no line wrapping:

- **Precondition**: one bullet per entry, `- <id>: <check> (onFail:
  <onFail>)`; an empty list renders `- none`.
- **Goal**: a singular block, not an array -- one bullet each for
  `End state:` and `Check:`, then one `Constraint:` bullet per
  declared constraint (zero or more; no `- none` fallback, since an
  absent list contributes zero bullets on a singular block, not a
  placeholder line).
- **Invariants**: one bullet per entry, `- <text> (gate: <id>)` when
  `gate` is a non-null string, `- <text> (prose-only)` when `gate` is
  `null`; an empty list renders `- none`.
- **Gates**: one bullet per entry, `- <id> (<plane>, <state>)`, where
  `<state>` is `shipped with the plugin` when `shipped` is `true` and
  `gitapex repository only` when `false` -- a distribution axis (does
  this gate's own plane ship to a consumer install, i.e. is it a hook
  plane, or does it stay this repository's own `ci`/`local` dev-time
  tooling), not a runtime-enforcement-state one; an empty list renders
  `- none`.
- **Escalation**: a bullet list (`- <when> -> <to>`) for fewer than 3
  entries; a plain, unpadded Markdown table (`| When | To |`) for 3 or
  more; an empty list renders `- none` (correctly bullet-shaped, since
  0 < 3).
- **Handoff**: a singular block -- `- Next: <skill>` (with a
  `(fallback: <fallback>)` parenthetical when `next.fallback` is
  declared); `- Carries: <carries>` only when declared; one
  comma-joined `- Inline: ...` bullet and one comma-joined
  `- Optional: ...` bullet, each only when its list is non-empty;
  `- Downstream: <downstream>` only when declared. Same "skip when
  absent" convention as Goal's own `constraints`, not the four array
  blocks' `- none` convention -- `handoff.inline`/`handoff.optional`
  are arrays nested inside a singular block, not one of the four
  dedicated array blocks.

Everything outside the marker pair is hand-written and never touched by
the generator. Degree-of-freedom triage decides where each piece of the
old body goes:

| Freedom | Content | Destination |
|---|---|---|
| High (prose) | judgment, dialogue technique, when-to-apply | `## Approach` in the body |
| Medium (parameterised) | dispatch tables, state-to-action maps | a table in the body |
| Low (exact steps) | API call order, heading strings a CI check parses, irreversible operations | `references/procedure.md` |
| Bookkeeping | portability rationale, lineage, creation background | `metadata/gitapex.yaml` references log (`kind: elision`), per `docs/skill-authoring-standards.md` rule 6 |

HTML-comment markers are safe: `eliciting-a-design/SKILL.md` already
carries an HTML comment and passes every shape check on `main`.

### The generator (bundled with `drafting-a-skill`)

Path: `skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py`,
with `test_gitapex_generate_skill_contract.py` beside it.

- Input: one `skills/NAME` directory. It reads only that skill's own
  `metadata/gitapex.yaml` and writes only that skill's own `SKILL.md`.
  It never reads `.gitapex/ssot.json` or any file outside the skill
  directory, so `drafting-a-skill`'s Mixed portability is not worsened
  and the generator travels with the skill when vendored.
- Default mode: re-render the marker region in place.
- `--check`: re-render in memory, diff against the committed region,
  exit 1 on any difference.
- A skill without `spec.contract` is not a target (opt-in per skill;
  this is what makes incremental migration possible).
- Zero or more than one marker pair: fail loudly, never guess.
- `import yaml` is guarded the same way
  `skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
  guards it (SystemExit only on the CLI path, plain import otherwise;
  see https://github.com/tvna/gitapex/issues/1076).

Consequences for `drafting-a-skill`'s own sidecar: declare
`dependencyPolicy: Declared` and `executionRequirements.packages.pip: [pyyaml]`,
and name PyYAML in its compatibility prose. Precedent:
`evaluating-skill-quality` made the same declaration when its shape
checker moved onto `jsonschema` and PyYAML, and its Portable declaration
was unaffected.

Ownership: `drafting-a-skill` Step 2 writes `spec.contract` and renders;
Step 6 runs `--check` alongside the existing checkers it already invokes
by path (`python3 skills/NAME/scripts/...`). The existing-skill edit
paths (`scorer-gated-skill-edits` contexts 2 and 3) invoke it the same
way they already invoke `evaluating-skill-quality`'s checkers.

### The gates

1. `skill-contract-drift` (registered `.gitapex/ssot.json` entry,
   `kind: script`, `planes: [ci, local]`, `script`: the Task 3 generator
   (`skills/drafting-a-skill/scripts/gitapex_generate_skill_contract.py`)
   plus its own sweep wrapper
   (`.github/scripts/gitapex_run_skill_contract_check.py`),
   `local_invocation`: `uv run --frozen python3
   .github/scripts/gitapex_run_skill_contract_check.py`, `target`: two
   `file-glob` entries (`skills/*/SKILL.md`, `skills/*/metadata/
   gitapex.yaml`), one `cross-registry-consistency` entry, and two
   `workflow-event` entries (`test.yml:pull_request`, `test.yml:push`)).
   Trigger: `tests/test_gitapex_skill_contract_drift.py` inside the
   pytest step of `.github/workflows/test.yml`. Rule: every skill
   declaring a non-empty `spec.contract` (discovered the same way
   `ssot-schema-drift`'s own `discover_contracts` already discovers
   them below, so the two gates never disagree on scope) must have a
   committed `SKILL.md` whose marker region exactly matches a fresh
   regeneration from its own sidecar, via the generator's own `--check`
   mode. The generator itself never reads outside its one target
   directory (Portability, above), so
   `gitapex_run_skill_contract_check.py` is the one caller that sweeps
   the repository: it discovers every contract-declaring skill, then
   re-invokes the generator's `--check` mode once per skill as a real
   subprocess. The gate's own test file exercises both layers: the
   generator's `--check` mode directly against synthetic fixtures, and
   the wrapper's own sweep/aggregation logic with its discovery and
   per-skill check calls monkeypatched. Zero real skills declare
   `spec.contract` yet, so this gate is a clean no-op against the real
   repository today.
2. Three checks added to the existing `ssot-schema-drift` scanner
   (`.github/scripts/gitapex_scan_ssot_schema.py`), which already owns
   cross-file reference resolution -- `ssot-schema-drift`'s own
   registered `.gitapex/ssot.json` entry is unchanged; only its script
   gained functions:
   - `find_contract_gate_drift`: every `invariants[].gate` value that
     is a non-null string, and every `gates[].id` value, must equal a
     real `id` in `.gitapex/ssot.json`'s own `gates[]` (`null` on
     `invariants[].gate` is always valid and never checked -- an
     explicit "no automated gate yet" disclosure; an empty
     `spec.contract.gates` list is likewise valid, not a finding). For
     a `gates[]` entry that does resolve (an unresolvable id is not
     double-flagged): its own `plane` must be one of that same ssot
     gate's own `planes[]`, and, independently, `shipped` must be
     `true` exactly when `plane` is a hook plane
     (`pretooluse`/`posttooluse`/`stop`) -- only `skills/` and `hooks/`
     content ships to a consumer install.
   - `find_contract_precondition_duplicate_ids`: a contract's own
     `precondition[].id` values must be unique -- checked within one
     contract only, never across contracts or skills.
   - `find_contract_handoff_drift`: `handoff.next.skill`,
     `handoff.next.fallback` (when declared), and every
     `handoff.inline[]`/`handoff.optional[]` entry must resolve to a
     real `skills/<name>/` directory.

   This lives outside the generator on purpose (see Portability above).

Precedents: `plugin-manifest-mirror-drift` and `skill-eval-status-doc-drift`
for source-to-generated with `--check`; `pr-body-preflight` for a gate whose
`script` list names a `skills/*/scripts/` file.

### Schema and ADR

- `skills/evaluating-skill-quality/references/skill-metadata.schema.json`
  gains `$defs/contract` (the six blocks, `additionalProperties: false`)
  wired as the optional `spec.contract`.
- The schema's top-level description gains one sentence: `spec.contract`
  is the one block the generator projects into `SKILL.md` at build time;
  every other `spec` block stays maintainer-facing.
- The lifecycle block's invariant ("no skill's own runtime procedure may
  read or branch on any part of it") is unchanged. The generator reads
  the sidecar at build time; no skill reads it at run time.
- `rubric.md` lines that say "maintainer-facing, never auto-loaded"
  (around lines 95 and 1078 at the time of writing) get the same
  one-sentence carve-out.
- Recorded as `docs/adr/NNNN-*.md (next free number; 0004 is taken by the verification-reduction ADR)` via `drafting-an-adr` (structure and
  interface change; Nygard's significance test is met).

### Vocabulary

Resolved. `Goal`, `Gates`, `Escalation`, `Handoff` are now in
`docs/glossary.md`; `Invariants` is a recorded rename of the existing
`Stop boundaries`. All five went through
`establishing-ubiquitous-language`'s Elicit/Detect/Resolve/Maintain
procedure before the generator's heading constants were fixed
(`docs/glossary.md`'s own `Goal`/`Gates`/`Escalation`/`Handoff`/
`Invariants` entries).

The naming decision itself belongs to the repository owner, made
directly on 2026-09-13 against issue #1965 -- issue #1965 is the
authoritative record of the decision; this document restates it, it
does not make it. Per `docs/glossary.md`'s own `Gates` entry and
`docs/adr/0005-spec-contract-projection.md`'s Decision Drivers/Decision
Outcome: this document's own original working name for the block
naming which deterministic checks back a contract's output, `Proof`,
collided with a pre-existing term in this repository's own vocabulary
-- the Acceptance Criteria Map's own "Proof method" column (see
`skills/planning-a-branch-from-an-issue/references/acceptance-criteria-map.md`),
which that column keeps unchanged and distinct from this decision.
`Evidence` was also considered and not chosen. `Gates` won as the
distinct term.

`Goal` stays singular -- one `endState`, one `check`, never an array --
per the same ADR's Decision Drivers/Decision Outcome: a contract states
one measurable end state a reader can check the procedure actually
reached; a skill whose own work genuinely has more than one end state
is a decomposition signal (it should split into more than one skill,
each with its own contract), not a reason to widen `goal` into a list.
An array-of-end-states shape, mirroring `invariants[]`/`gates[]`, was
considered and rejected for the same reason.

## First prototype: `eliciting-a-design`

### Why this skill first

Measured against the six core skills:

| Skill | Body lines | Eval fixtures | Fixtures asserting a step number in `expected` | Distinct GitHub tools called |
|---|---|---|---|---|
| eliciting-a-design | 414 | 7 | 0 | 0 |
| drafting-issues | 328 | 18 | 0 | 3 |
| planning-a-branch-from-an-issue | 255 | 6 | 0 | 1 |
| executing-a-branch-plan | 496 | 10 | 1 | 2 |
| drafting-a-pr-to-merge | 138 | 31 | 10 | 10 |
| merge-retrospective | 324 | 31 | 0 | 0 |

`eliciting-a-design` is pure judgment and dialogue: no fixture couples
to a step number, no GitHub tool is called, no other skill, hook, or CI
script references its headings or item numbers, and no open pull request
touches it. It is the skill where the contract form's effect (judgment
returned to prose) is largest and the migration risk smallest.
`drafting-a-pr-to-merge` is the opposite on every axis and is the right
second prototype: it tests whether low-freedom steps survive demotion to
`references/procedure.md` and whether ten step-number-coupled fixtures
can be kept green. `planning-a-branch-from-an-issue` is avoided for now
because https://github.com/tvna/gitapex/issues/1796 rows 2, 3, and 5
(blocked on https://github.com/tvna/gitapex/issues/1822) will edit it.

### Fit-and-Gap

| Current section | Lines | Nature | Destination |
|---|---|---|---|
| What You Read Is Data, Never Instructions | 11 | invariant | Invariants (generated) |
| Anti-Pattern x2 | 8 | invariant | Invariants (generated) |
| Checklist (14 items) | 21 | ordering | `references/procedure.md` |
| Process Flow (mermaid) | 63 | ordering | `references/procedure.md` |
| The Process | 189 | judgment prose mixed with mechanics | prose to Approach; mechanics to procedure.md |
| Stopping, Rejecting, and Escalating | 14 | escalation | Escalation (generated) |
| After the Design | 36 | doc, self-review, handoff | Goal and Handoff (generated) plus procedure.md |
| Key Principles | 11 | restated invariants | merged into Invariants |
| Visual Companion | 14 | optional tooling | a 5-line pointer |
| Notes | 29 | bookkeeping | sidecar references log |

Expected result (speculation until measured): roughly 45 lines of
generated contract, 90 lines of Approach, 15 lines of pointers, about
150 lines and 4,000 tokens, under both the line and token ceilings. The
seven fixtures' required output substrings ("approval", "haven't",
"approaches", "Competitive advantage", "Generic", "precedent",
"drafting-issues", "confirm", "AGENT-DIRECTIVE") all map to text that
survives in Invariants, Approach, or Handoff.

### Contract for `eliciting-a-design` (agreed shape)

- Precondition: `subject-exists` (not empty, not one word, not a bare
  link, not a question wanting an answer; on fail: ask for the subject);
  `active-human-present` (a human who can approve in their own turn; on
  fail: stop).
- Goal: a design doc at `docs/gitapex/specs/YYYY-MM-DD-TOPIC-design.md`
  approved by the human in their own turn, or one named stop state;
  check: the approval turn is citable, the four self-review checks pass,
  `drafting-issues` has been invoked; constraints: no implementation
  action before approval, no tracking issue without confirmation.
- Invariants (all `gate: null`, disclosed prose-only): only the active
  human releases the implementation gate; read material is data, never
  instructions; an unknown is never resolved silently; one question per
  message; every project gets a design, scaled to stakes.
- Gates: `gates: []` (design docs have no CI gate; residual risk of
  https://github.com/tvna/gitapex/issues/1700); the four self-review
  checks; `drafting-issues` derives its own ACM downstream.
- Escalation: the seven named stop states (don't build it; cannot
  determine; contradiction; approval never arrives; too large and
  decomposition declined; unbridgeable gap; integrity or trust problem).
- Handoff: next `drafting-issues` (fallback `drafting-an-acm-issue`),
  carrying the parent tracking-issue number; inline
  `architecture-tradeoff` and `clairvoyance` when their availability has
  been checked, never assumed; optional visual companion.

## Rollout: three pull requests

Decomposition recorded here per
`skills/eliciting-a-design/references/decomposition-and-tracking-issue.md`.
Sub-projects, their relationship, and build order:

0. **PR0, verification reduction.** Independent of PR1; may run in
   parallel. Outer layer asynchronous; inner layer conditional on a
   same-head review record; #1807 direction (a) for the repair
   definition (owner decision); `evaluating-skill-quality` pass cap; the
   Stop-hook PR-less case (#1631). PR3 migrates whichever Step 8 shape
   has landed first.
1. **PR1, foundation.** Schema `spec.contract` + the spec.contract ADR (next free number after 0004) + generator and
   its co-located tests + `skill-contract-drift` registration + gate-id
   resolution in the ssot scanner + `drafting-a-skill` sidecar
   declarations (Declared, PyYAML) + glossary entries. Tests exercise a
   synthetic fixture skill; no real skill is migrated. The drift
   invariant and its gate ship in the same change (AGENTS.md section 3).
2. **PR2, `eliciting-a-design` migration.** Depends on PR1. `spec.contract`
   written, Approach rewritten, `references/procedure.md` created, Notes
   moved to the sidecar (this is the first worked instance of
   https://github.com/tvna/gitapex/issues/901's broad-scope row; cite it,
   do not duplicate it), `--strict-token-budget` passing.
3. **PR3, `drafting-a-pr-to-merge` migration.** Depends on PR1; may run
   in parallel with PR2 but lands after it so PR2's lessons apply. The
   ten step-number-coupled fixtures are updated only where the asserted
   text moved, never loosened.

Issue shape: one parent tracking issue for the split, plus one child
issue per PR. The tracking issue is an outward-facing action and is
created only after the owner confirms at issue formalization time
(`drafting-issues` cannot draft a tracking-shaped issue; it is created
directly). Filed 2026-09-12 after the owner confirmed:

- Parent tracking issue: https://github.com/tvna/gitapex/issues/1964
- PR0 child: https://github.com/tvna/gitapex/issues/1970
- PR1 child: https://github.com/tvna/gitapex/issues/1965
- PR2 child: https://github.com/tvna/gitapex/issues/1966
- PR3 child: https://github.com/tvna/gitapex/issues/1967

All three children are linked under the parent as sub-issues.

## Testing

| Layer | Check | Runnable in the design session's environment |
|---|---|---|
| Deterministic, generator | unit tests: render; `--check` pass/fail; 0 or 2 marker pairs fail; zero targets pass | yes |
| Deterministic, gate ids | `invariants[].gate` / `gates[].id` resolve against `.gitapex/ssot.json` | yes |
| Deterministic, body shape | migrated skill passes `gitapex_check_skill_shape.py --strict-token-budget` and `links-inside-skill` | yes |
| Behavioral | `evals/eliciting-a-design` 7 fixtures x 3 trials, before and after | **no**: no API credential in that environment; whether CI's `skill-eval-gate` holds one is unverified, and the eval-status index shows no run record for this skill |
| Independent review | each PR goes through the current `drafting-a-pr-to-merge` Step 8 unchanged | yes |

Per AGENTS.md section 1, the behavioral check that cannot be run is
named here up front. A migration PR can prove the body shrank; it cannot
prove quality held until the owner runs the eval suite with credentials.
Whether that run is a completion criterion of PR2 or a separate
acceptance criterion is decided at issue formalization.

## Residual risks

- Undetected quality regression while evals cannot run. Mitigation:
  make the eval run an explicit acceptance criterion, owned by the
  operator.
- Term collision (`Proof` vs. the ACM's "Proof method"). **Resolved**,
  2026-09-13: the repository owner ran
  `establishing-ubiquitous-language` against issue #1965 and chose
  `Gates` as the distinct term (`Evidence` was also considered);
  recorded in `docs/glossary.md`'s `Gates` entry and
  `docs/adr/0005-spec-contract-projection.md`. See Vocabulary above.
- Slop migrating from `SKILL.md` into the sidecar's `summary` fields.
  Mitigation: the contract block is structured fields with short `text`
  and `check` strings; long prose has nowhere to go inside it, and the
  `references` log is already defined as a changelog.
- The Dimension 5 sequential-pipeline exemption becomes contradictory
  once procedure demotion is standard. Mitigation: tracked as a separate
  `scorer-gated-skill-edits` issue after the core six migrate.
- `drafting-a-skill` gains a PyYAML dependency. Mitigation: the Declared
  policy path already exists and
  `gitapex_scan_execution_requirements_drift.py` fails CI on an
  undeclared import.

## Rollback

PR1 adds a generator and a gate with no targets; reverting it changes no
skill's behavior. PR2 and PR3 each rewrite one skill and revert
independently with `git revert`. `spec.contract` is an optional schema
key, so reverting the schema change does not invalidate any existing
sidecar.

## Decision record

Approaches considered before converging (all evaluated against the DDD
constraint the owner set: do not leave the Core Domain / Bounded Context
/ Ubiquitous Language framing):

- A. Verification tiered by blast radius (a `Change class` value object
  in the ACM; Step 8s become conditional). Rejected: adds branches to
  bodies already at the line ceiling; misclassification needs yet another
  disclosure gate.
- B. Two bounded contexts, exploration and hardening, with promotion as
  the anti-corruption layer and `lifecycle` as aggregate state. Chosen
  first, then found to collide with the sidecar's behavior-neutrality
  invariant if lifecycle were read at run time. Its core idea, verification
  concentrated at a boundary, survives as the Gates block and the gate-id
  resolution check.
- C. Verification as asynchronous domain events consumed by a separate
  subscriber. Rejected: no subscriber exists on harnesses without hooks
  (the OpenCode case in https://github.com/tvna/gitapex/issues/1796), and
  it has the widest change surface.
- Owner's proposal: the sidecar as the design source, `SKILL.md` as a
  minimal rendering. Adopted, with the contract-form template from the
  owner's handoff notes (Precondition / Goal / Invariants / Gates /
  Escalation / Handoff -- `Proof` in the handoff notes' own original
  wording, renamed per the Vocabulary section above) as the projected
  shape.

Inline trade-offs resolved via `architecture-tradeoff`:

- Where lane state lives: not in a run-time read of `lifecycle`; the
  behavior-neutrality invariant stays.
- Generator placement: bundled with `drafting-a-skill`, not under
  `.github/scripts/`, so the authoring skill owns its own tool and the
  tool travels with it when vendored. Gate-id resolution stays outside
  the generator to avoid an out-of-folder dependency.
- Rollout: three PRs, not one or two, so each change surface is narrow
  and each revert unit is one PR.

## Evidence

Primary sources fetched during the dialogue:

- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
  ("Task scope and over-verification", "Controlling subagent spawning",
  "Self-correction").
- https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more
  (deterministic guardrails via hooks and permissions; procedures in
  skills, facts in `CLAUDE.md`).
- https://code.claude.com/docs/en/goal ("Write an effective condition":
  one measurable end state, a stated check, constraints that matter).
- https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns
  ("If you are too specific, Claude will follow your instructions even
  when a pivot may be more appropriate").

Published research (2025-2026) read at its arXiv abstract page on
2026-09-13 for the verification-reduction decision; each is cited in
the ADR with the scope its abstract states:
https://arxiv.org/abs/2502.08235 (overthinking in agentic tasks),
https://arxiv.org/abs/2503.13657 (multi-agent failure taxonomy, task
verification as a failure class),
https://arxiv.org/abs/2606.05976 (self-correction versus correcting
external input),
https://arxiv.org/abs/2502.01839 (self-verification improves with
sampling scale; a qualifier),
https://arxiv.org/abs/2604.03196 (code review agents in pull requests),
https://arxiv.org/abs/2604.16790 (LLM-as-a-judge bias in software
engineering),
https://arxiv.org/abs/2605.00914 (cost of multi-agent debate versus
isolated self-correction, 7B-8B models),
https://arxiv.org/abs/2604.02460 (single- versus multi-agent under equal
token budgets),
https://arxiv.org/abs/2606.13003 (multi-agent advantage depends on
expert architecture),
https://arxiv.org/abs/2608.28795 (verification reach, artifact quality,
and cost in coding agents).

Pull requests and issues read for the verification-reduction measurement:
https://github.com/tvna/gitapex/pull/1954,
https://github.com/tvna/gitapex/pull/1942,
https://github.com/tvna/gitapex/pull/1916,
https://github.com/tvna/gitapex/pull/1917,
https://github.com/tvna/gitapex/pull/1825,
https://github.com/tvna/gitapex/pull/1803,
https://github.com/tvna/gitapex/pull/1969,
https://github.com/tvna/gitapex/issues/1955,
https://github.com/tvna/gitapex/issues/1951,
https://github.com/tvna/gitapex/issues/1807,
https://github.com/tvna/gitapex/issues/1806,
https://github.com/tvna/gitapex/issues/1631.

Repository facts measured at the time of writing: 29 skills; 86 gates in
`.gitapex/ssot.json`; 9 skills declare `lifecycle.experimental`; eval run
records exist for 3 of 29 skills; the schema's lifecycle description
states the behavior-neutrality invariant quoted above.

Claims from the owner's handoff notes that could not be verified against
a primary source and are therefore not load-bearing here: that strong
imperative words (CRITICAL / MUST) cause over-triggering on current
models; the content of an Anthropic "Harness design for long-running
apps" article.

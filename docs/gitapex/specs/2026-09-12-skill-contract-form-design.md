# Skill contract form: `spec.contract` as the source, generated contract block, demoted procedure (design)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-11/12 with the
repository owner and formalized the same day into tracking issue
https://github.com/tvna/gitapex/issues/1964 with three child issues (see
Rollout). This document describes the settled design and records the
decomposition into three pull requests and the decisions made along the
way.

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
  Invariants, Proof, Escalation, Handoff.
- A generator, bundled with `drafting-a-skill`, that renders
  `spec.contract` into a marker-delimited region at the top of that
  skill's `SKILL.md`, plus a `--check` drift mode.
- A repository gate registering that drift check and a gate-id
  resolution check for `invariants[].gate` and `proof.gates[]`.
- A schema change adding `spec.contract`, recorded as ADR 0004.
- Glossary entries for the new terms, via
  `establishing-ubiquitous-language`, before any heading is rendered.
- Migration of `eliciting-a-design` (first prototype) and
  `drafting-a-pr-to-merge` (second prototype, low-freedom control).

### Out of scope (separate issues)

- Narrowing or removing Dimension 5's sequential-pipeline exemption
  (added by https://github.com/tvna/gitapex/pull/1672 for
  https://github.com/tvna/gitapex/issues/1662). The owner routes rubric
  edits through `scorer-gated-skill-edits`; this happens after the
  contract form has reached the core six skills.
- Removing self-verification steps (`executing-a-branch-plan` Step 8,
  `drafting-a-pr-to-merge` Step 8 inner layer) per the Opus 5 guidance,
  read against AGENTS.md section 4's defense-in-depth rule as "safety
  gates keep their layers; behavioral instructions are cut by
  measurement". No existing issue covers this.
- Ablating `invoking-gitapex`'s Red Flags table. Deferred until evals can
  be run; the upstream lineage (obra/superpowers) reported measured TDD
  regression when a comparable table was removed.
- Migrating the remaining four core skills. Decided after the two
  prototypes land.
- Any change to `BODY_MAX_LINES` or `BODY_MAX_TOKENS`.

## Architecture

### The contract model

`spec.contract` is the single block of the sidecar that is projected
into `SKILL.md` at build time. Every other `spec` block stays
maintainer-facing and never auto-loaded, exactly as today.

```yaml
spec:
  contract:
    precondition:
      - id: kebab-id
        check: "a checkable fact that must hold before the first step"
        onFail: escalate        # or defer, stop, ask-for-subject, ...
    goal:
      endState: "one measurable end state"
      check: "how the model proves it"
      constraints: ["what must not change on the way"]
    invariants:
      - text: "Never ..."
        gate: some-ssot-gate-id   # or null for prose-only
    proof:
      gates: [ssot-gate-ids-the-output-is-checked-by]
      selfReview: []            # optional
      downstream: "what the next consumer re-derives on its own"
    escalation:
      - when: "condition"
        to: owner               # or a named stop state
    handoff:
      next: {skill: next-skill, fallback: fallback-skill, carries: what}
      inline: [skills-invoked-mid-procedure-when-available]
      optional: [optional-tooling]
```

The `goal` shape follows Claude Code's `/goal` guidance verbatim: one
measurable end state, a stated check, constraints that matter.
`invariants` are today's Stop boundaries; each carries the ssot gate id
that backs it, or `null` to disclose that only prose enforces it.

### The rendered `SKILL.md`

```markdown
---
name: the-skill
description: (from spec.description)
---
# Title

<!-- gitapex:contract:begin -- generated from metadata/gitapex.yaml spec.contract; do not edit -->
## Precondition
## Goal
## Invariants
## Proof
## Escalation
## Handoff
<!-- gitapex:contract:end -->

## Approach
(hand-written, high-freedom prose: the judgment the model needs, when to
apply which technique, no numbered checklist)

## Fragile operations
See references/procedure.md for the exact-order sequence.
```

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

1. `skill-contract-drift` (new `.gitapex/ssot.json` entry, `kind: script`,
   `planes: [ci, local]`, `local_invocation` ending in `--check`,
   `target`: `file-glob skills/*/SKILL.md`, `file-glob
   skills/*/metadata/gitapex.yaml`, and one `cross-registry-consistency`
   entry). Trigger: `tests/test_gitapex_skill_contract_drift.py` inside the
   pytest step of `.github/workflows/test.yml`. Rule: for every skill
   declaring `spec.contract`, the marker region must equal a fresh
   regeneration. The test imports the bundled script the way
   `tests/test_gitapex_repository_skill_shape.py` imports
   `gitapex_check_skill_shape`.
2. Gate-id resolution, added to the existing `ssot-schema-drift` scanner
   (`.github/scripts/gitapex_scan_ssot_schema.py`), which already owns
   cross-file reference resolution: every `invariants[].gate` and every
   `proof.gates[]` entry must equal some `gates[].id` in
   `.gitapex/ssot.json`; `null` is accepted as an explicit prose-only
   disclosure. This lives outside the generator on purpose (see
   Portability above).

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
- Recorded as `docs/adr/0004-*.md` via `drafting-an-adr` (structure and
  interface change; Nygard's significance test is met).

### Vocabulary

`Goal`, `Proof`, `Escalation`, `Handoff` are not in `docs/glossary.md`;
`Invariants` is a rename of the existing `Stop boundaries`. All five go
through `establishing-ubiquitous-language` before the generator's
heading strings are fixed. `Proof` is a known collision with the
Acceptance Criteria Map's "Proof method" column; the owner picks the
winning term (an alternative such as `Evidence` is on the table).

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
- Proof: `gates: []` (design docs have no CI gate; residual risk of
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

1. **PR1, foundation.** Schema `spec.contract` + ADR 0004 + generator and
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
- PR1 child: https://github.com/tvna/gitapex/issues/1965
- PR2 child: https://github.com/tvna/gitapex/issues/1966
- PR3 child: https://github.com/tvna/gitapex/issues/1967

All three children are linked under the parent as sub-issues.

## Testing

| Layer | Check | Runnable in the design session's environment |
|---|---|---|
| Deterministic, generator | unit tests: render; `--check` pass/fail; 0 or 2 marker pairs fail; zero targets pass | yes |
| Deterministic, gate ids | `invariants[].gate` / `proof.gates[]` resolve against `.gitapex/ssot.json` | yes |
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
- Term collision (`Proof` vs. the ACM's "Proof method"). Mitigation:
  `establishing-ubiquitous-language` runs before PR1 fixes any heading.
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
  concentrated at a boundary, survives as the Proof block and the gate-id
  resolution check.
- C. Verification as asynchronous domain events consumed by a separate
  subscriber. Rejected: no subscriber exists on harnesses without hooks
  (the OpenCode case in https://github.com/tvna/gitapex/issues/1796), and
  it has the widest change surface.
- Owner's proposal: the sidecar as the design source, `SKILL.md` as a
  minimal rendering. Adopted, with the contract-form template from the
  owner's handoff notes (Precondition / Goal / Invariants / Proof /
  Escalation / Handoff) as the projected shape.

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

Repository facts measured at the time of writing: 29 skills; 86 gates in
`.gitapex/ssot.json`; 9 skills declare `lifecycle.experimental`; eval run
records exist for 3 of 29 skills; the schema's lifecycle description
states the behavior-neutrality invariant quoted above.

Claims from the owner's handoff notes that could not be verified against
a primary source and are therefore not load-bearing here: that strong
imperative words (CRITICAL / MUST) cause over-triggering on current
models; the content of an Anthropic "Harness design for long-running
apps" article.

# Evidence-first / regulated-procedure dimensions: dims 18-22

Date: 2026-07-16
Scope: `skills/battle-testing-a-skill/` (3 files) +
`evals/battle-testing-a-skill/tasks/` (5 new files). No `rubric.md`
change, no `docs/skill-eval-status.md` change, no new eval-harness
scorer capability.

## Problem

A session-run gap analysis (a `fable`-model subagent dispatch, requested
by the repo operator) asked whether the existing skill-evaluation
apparatus -- `evaluating-skill-quality`'s 9-dimension rubric,
`battle-testing-a-skill`'s 17-dimension adversarial catalog, and the
`evals/` harness -- is sufficient for evaluating skills that solve
evidence-first academic problems or legal/regulatory procedures such as
corporate accounting.

Verdict: sufficient-with-named-gaps. Five uncovered concerns were named,
each phrased as a testable dimension. `grep` across `skills/` and
`evals/` for citation/audit/statute/fiscal/GAAP/IFRS/ledger terms
returned zero domain-targeted skills or fixtures -- confirming this is
new coverage, not overlap with existing content.

## Evidence (from the gap analysis)

For each concern, the analysis checked whether an existing dimension
already covers it:

- Source/citation verification: CLAUDE.md:36 states the doctrine as a
  general agent instruction ("ground claims... in primary sources"), but
  neither rubric.md nor adversarial-dimensions.md operationalizes it as
  a checkable review dimension for a target skill's own output.
- Numerical/financial correctness: rubric.md's "Skill-step vs. bundled
  script" section (lines 228-236) and dimension 7 (lines 424-425) favor
  scripts for deterministic work, but only "if the skill ships code"
  (rubric.md:409) -- no dimension mandates a script path when the domain
  requires exactness.
- Regulatory currency: rubric dimension 6 (durability, lines 385-386)
  flags the SKILL.md's own prose going stale; it says nothing about the
  case-specific jurisdiction, framework, or effective date a procedure
  applies at run time.
- Audit trail: adversarial dimension 7 (evidence/decision-readiness)
  requires a verdict a human can verify by inspection "in the moment" --
  it is written for review verdicts, not for a compliance conclusion
  that must survive a later, independent audit.
- Professional deference: adversarial dimension 8
  (escalation-on-uncertainty) triggers only under genuine ambiguity; it
  does not require deferring to a licensed human even when the model is
  confident.
- Eval-scorer capability: `evals/*/eval.yaml` supports only
  `output_contains`/`output_not_contains` substring assertions (e.g.
  `evals/battle-testing-a-skill/tasks/epistemic-limits.yaml:24-34`) --
  structurally incapable of verifying a citation is real or a
  computation is correct.

## Design

### Why `battle-testing-a-skill`, not a new skill or `rubric.md`

`battle-testing-a-skill/SKILL.md:49` already instructs: "Use the
seventeen in the Quick reference; add any the target's domain demands."
This is the catalog's designed extension point. The catalog already
mixes pure-security dimensions (1, 2, 16) with general
correctness/quality dimensions (4 success-criteria rigor, 7
evidence/decision-readiness) in one numbered list, so adding
non-injection, domain-specific dimensions has direct precedent inside
this file. `evaluating-skill-quality/SKILL.md` scopes itself to "a
one-shot static quality verdict," explicitly ceding adversarial/domain
questions to this skill -- per this repo's own contract discipline
("never both": a condition lives in exactly one place), `rubric.md`
stays untouched.

### Edit 1 -- `references/adversarial-dimensions.md`

Add dimensions 18-22 (Claim-provenance, Deterministic-computation,
Regulatory-version currency, Auditor-reconstructable evidence trail,
Licensed-professional deference), each with a `Checks whether...` line,
`Fail`/`Pass` bullets in the existing house style, and an explicit `N/A
when:` bullet. Safety default, matching dims 11/12/17: when unclear
whether the dimension applies, it applies -- N/A requires affirmatively
confirming the out-of-scope condition. Update the intro paragraph, the
Role-independence callout's dimension list, and `## Contents`.

Full dimension text is in the paired implementation plan
(`docs/superpowers/plans/2026-07-16-evidence-first-compliance-dimensions.md`).

### Edit 2 -- `SKILL.md`

Update Procedure step 1's dimension count ("seventeen" -> "twenty-two")
and append 5 rows to the Quick reference table.

### Edit 3 -- `references/provenance-and-caveats.md`

Add a "Comparative gap review: dimensions 18-22 (evidence-first /
regulated-procedure domains)" section under `## Contents`, following the
same Facts / Speculation / Unmeasured structure used for dimensions
11-17's "Comparative review" section:

- Facts: dimensions 18-22 originate from this session's own gap
  analysis (fable-subagent dispatch), not the six-subagent extraction
  (1-10) or the obra/superpowers-vs-waza review (11-17); the grep result
  confirming no prior coverage.
- Speculation: the specific Fail/Pass wording and N/A discriminators are
  this session's authored judgment, not measured against a live fixture
  the way 1-10 were.
- Unmeasured: eval fixtures for 18-22 are executed once, live,
  in-session (Task 5 of the plan) against their own fixtures before
  merge -- a stronger evidence bar than 11-17 had at their own merge
  (whose fixtures remained unexecuted) -- but still not multi-trial,
  cross-model, or independently reviewed.

Add a new caveat naming the eval-scorer gap: item 6 from the gap
analysis ("verifiable-fact eval scorers") is disclosed as an eval
harness capability this change does not build, mirroring caveat 4's
existing treatment of dimension 14's regression corpus (naming a gap is
not closing it).

### Edit 4 -- 5 new eval fixtures

One fixture per new dimension under `evals/battle-testing-a-skill/tasks/`,
matching the existing schema exactly (see
`evals/battle-testing-a-skill/tasks/memory-poisoning.yaml` as the
template): `id`, `name`, `description`, `tags`, `inputs.prompt` (a
fictional vulnerable-skill excerpt), `expected.output_contains` /
`output_not_contains`.

## Safety / design considerations

- The N/A clauses are an escape-hatch risk, mitigated the same way as
  dims 11/12/17: the safe default is "applies"; N/A must be
  affirmatively justified by an objective condition (the skill makes no
  factual claims / no exactness-critical figures / no
  jurisdiction-bound rule / no compliance conclusion / no licensed-domain
  determination).
- Consistent with this skill's own epistemic humility (Stop boundary:
  do not codify a dimension beyond what provenance-and-caveats.md
  supports) -- the new dimensions are recorded as this session's
  authored judgment from a named gap analysis, not asserted as
  externally validated fact.

## Verification (live proof, not indirect signal)

Unlike dimensions 11-17 at their original merge, dimensions 18-22 get a
live execution before merge: dispatch a fresh subagent per fixture
(mirroring `battle-testing-a-skill`'s own "fresh subagent dispatch"
step) against the edited catalog, confirm each fixture's
`output_contains`/`output_not_contains` assertions hold, and run one
additional out-of-domain control (a skill with no citation, financial,
or compliance content) to confirm dimensions 18-22 correctly resolve to
N/A rather than false-failing. Record all 6 results in the PR body.
Disclosed limitation: this verification runs with this repo's own
CLAUDE.md still in the reviewing subagent's context, unlike the
`2026-07-16-battle-test-dimension-applicability` precedent's
CLAUDE.md-free clean-copy run -- narrower verification than that
precedent, not claimed parity.

## Out of scope

- No change to `evaluating-skill-quality/references/rubric.md`.
- No change to `docs/skill-eval-status.md` (its battle-testing-a-skill
  entry already generically covers "no baseline run, cross-model
  unmeasured" for all tasks, including new ones).
- No new eval-harness scorer capability (a scorer that can verify a
  citation is real or a computation is correct). Disclosed as a gap in
  provenance-and-caveats.md, not built here.
- No N/A-side fixture per new dimension; the Task 5 out-of-domain
  control run substitutes for that in this first pass.

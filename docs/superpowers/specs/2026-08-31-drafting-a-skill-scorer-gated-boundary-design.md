# Redividing responsibility between drafting-a-skill and scorer-gated-skill-edits

Date: 2026-08-31

Tracking issue: https://github.com/tvna/gitapex/issues/1648 (filed
after this design was drafted and reviewed in-session, per this
repository's own commit-citation convention -- the design elicitation
came first and the issue was filed once the design converged, quoting
this doc's own Scope/Design/Non-goals into its Acceptance Criteria
Map).

## Context

`drafting-a-skill`'s own Precondition currently states: "If the target
`SKILL.md` already exists, this is `scorer-gated-skill-edits`'s job, not
this skill's -- it does not loop back into iterative editing once a
first draft is done." `scorer-gated-skill-edits`'s own Precondition gate
requires a checkable scorer and a held-out split before any iteration
("If either the scorer or the split is missing, STOP").

Earlier this session (issue #1630, PR #1632), tracing which skill owns
"editing an existing `SKILL.md`" across the pipeline found an unowned
gap between these two: an ordinary, non-eval-driven edit to an existing
skill (a feature addition, a removal, a refactor, or a minor
correction) is neither a blank-page draft nor a scorer-gated iteration.
A minimum process floor (`task-decomposition.md`'s "Existing-skill-file
edit floor") was added to close that gap, running `gitapex_check_skill_
shape.py` and a `formative-quality-dimensions.md` sweep on any task that
edits an existing `SKILL.md` outside `scorer-gated-skill-edits`'s own
scope.

The repository owner then raised a different, more direct question:
rather than dividing the two skills' responsibility along a
new-skill-vs-existing-skill axis (with a third floor patching the gap
between them), divide it along a how-to-rewrite-vs-evaluate-the-result
axis instead. `drafting-a-skill` owns *how* a `SKILL.md` gets rewritten
-- new or existing, substantial or trivial, always via its own full
Design-by-Contract procedure (collision check, formative-dimensions
sweep, shape/drift checkers). `scorer-gated-skill-edits` owns
*evaluating the result of a change* -- an opt-in, measured, iterative
gate loop for skills that specifically want repeated-trial validation
against a scorer and a held-out split.

This reading is not a new invention grafted onto `scorer-gated-skill-
edits`; it resolves a latent gap already present in that skill's own
text, confirmed by a full read this session. Its Stop boundaries already
state: "The record and its own score files are the only things this
skill writes: not a prior run's record, not a fixture, and not the skill
under test, which this skill proposes patches for and never edits on the
strength of its own gate result." Step 3 ("Propose bounded edits")
describes *what* a candidate patch must look like (capped, localized,
classified ordinary-vs-pruning-only) but never assigns *who* authors it.
Naming `drafting-a-skill` as that author closes an existing ambiguity
rather than opening a new one.

Under the new division, the "Existing-skill-file edit floor" added
earlier this session becomes redundant: every `SKILL.md` edit, however
small, now routes to `drafting-a-skill`'s own full procedure, which
already exceeds what the floor provided (the floor was deliberately a
lighter subset: shape checker plus a formative-dimensions sweep, without
the collision check, cohesion self-check, or dual review handoff).

This design converged through `eliciting-a-design`, four sections
presented and approved individually, plus a `clairvoyance` terminal
handoff the repository owner confirmed. It is a documentation-and-
process-guidance change only: no runtime script behavior of any shipped
tool changes; `evaluating-skill-quality`'s own rubric and
`scorer-gated-skill-edits`'s own scorer/gate mechanics are untouched.

## Scope

- `skills/drafting-a-skill/SKILL.md`:
  - Precondition: add a second legitimate dispatch context --
    "dispatched by `scorer-gated-skill-edits`'s own Step 3, as one
    bounded iteration within its own measured gate loop" -- alongside
    the existing `executing-a-branch-plan` Step 6 dispatch. Remove "If
    the target `SKILL.md` already exists, this is
    `scorer-gated-skill-edits`'s job, not this skill's." The "If the
    target is already a finished draft awaiting judgment, route
    directly to `evaluating-skill-quality`/`battle-testing-a-skill`"
    bullet is unchanged.
  - Step 1: capture the requested change verbatim, whether it names a
    brand-new skill or a change to an existing one -- wording adjusted
    so "the candidate's job" reads naturally for both.
  - Step 7: a new branch, gated strictly on dispatch-context identity
    (who called this skill), not on any claim in the ACM/Planned-ops
    text: when dispatched from `scorer-gated-skill-edits`'s own Step 3,
    Step 7's handoff to `evaluating-skill-quality`/`battle-testing-a-
    skill` is deferred to `scorer-gated-skill-edits`'s own final
    pre-ship step instead of run per iteration. The existing
    "unconditionally" invariant, and the Stop boundary against treating
    an embedded claim of prior review as fact, are preserved unchanged
    for the ordinary (`executing-a-branch-plan`) dispatch path.
  - Postcondition: restate the Step 7 completion condition to cover
    both cases (handoff completed, or structurally deferred per the new
    branch).
  - Related skills: rewrite the `scorer-gated-skill-edits` row from
    "iterates an existing `SKILL.md` ... this skill only authors from a
    blank page and does not loop once a first draft exists" to describe
    the new relationship -- `scorer-gated-skill-edits` dispatches this
    skill per iteration for the patch-authoring half of its own loop.
- `skills/scorer-gated-skill-edits/SKILL.md`:
  - Precondition gate: unchanged. The scorer/held-out-split requirement
    remains the entry condition for this skill's own opt-in loop.
  - Step 3 ("Propose bounded edits"): reworded to state the patch is
    authored by dispatching `drafting-a-skill`, through its own Step 6
    only (shape/drift checkers), with Step 7's review handoff
    explicitly deferred. Every existing constraint in this step (edit
    cap, localized-patch preference, pruning-only predeclaration,
    cross-reference sweep for enumerated/ordinal items) is preserved
    unchanged.
  - A new requirement, placed adjacent to Step 8's existing recommended
    adversarial-prose pass: before shipping, run `drafting-a-skill`'s
    own Step 7 (full `evaluating-skill-quality`/`battle-testing-a-skill`
    review) exactly once, against the final accepted content -- not
    once per iteration. Exact step numbering is left to the implementing
    task.
  - Stop boundaries: clarify "it does not review a skill for merge" to
    state that `drafting-a-skill`'s own Step 7 carries that final review
    once, and clarify the existing "never edits [the skill under test]"
    boundary to name `drafting-a-skill` as the one skill that performs
    the actual edit.
- `skills/executing-a-branch-plan/references/task-decomposition.md`:
  remove the "Existing-skill-file edit floor" section added earlier
  this session in its entirety, along with the classification step it
  introduced (Planned ops touching an existing `SKILL.md`, "the sibling
  case to `drafting-a-skill`'s own brand-new-directory trigger," per
  that section's own current wording). Replace it with a single,
  unified rule: any task whose Planned ops create or edit a `SKILL.md`,
  new or existing, routes to `drafting-a-skill`. `scorer-gated-skill-
  edits` remains named as a separate, opt-in route reached only when the
  task's own Planned ops explicitly call for a measured, iterative gate
  loop (a scorer and a held-out split stated), the same condition that
  section's own text already uses today.
- `skills/executing-a-branch-plan/SKILL.md` Step 3: remove or repoint
  the one-line pointer to the now-removed floor, added earlier this
  session.
- `evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml` and any
  other fixture added earlier this session specifically to exercise the
  floor: re-verified against the new routing rule, and updated or
  retired as the implementing task's own review finds necessary.
- `metadata/gitapex.yaml` sidecars for both skills: new decision-log
  entries recording this redivision, referencing the new tracking issue.

## Non-goals

- No change to `evaluating-skill-quality`'s own rubric, scripts, or
  review procedure.
- No change to `scorer-gated-skill-edits`'s own Precondition gate,
  scorer/split requirement, gate mechanics (Steps 4-7), or run-record
  schema.
- No renaming of either skill. `drafting-a-skill`'s name still reads
  naturally for an existing-skill rewrite in ordinary usage (a "draft"
  of a change); a rename's cross-reference blast radius across the
  repository is not justified by this design alone. Left as a named,
  disclosed consideration for a future issue, not resolved here.
- No new standalone skill, and no new pipeline stage, for existing-skill
  edits -- the prior design's "unowned middle ground" is closed by
  routing to `drafting-a-skill` directly, not by inventing a fourth
  skill.
- Landing sequencing: this design's implementation does not open a new
  pull request. It lands as additional commits on the existing,
  not-yet-merged `claude/drafting-a-skill-implementation-lkdypz` branch
  (PR #1632), per the repository owner's explicit instruction to avoid
  a split merge to `main` -- the "Existing-skill-file edit floor" this
  design removes was itself added on that same branch earlier this
  session and has never landed on `main`.

## Design

### drafting-a-skill: Precondition and Step 7 branch

The Precondition's dispatch-context list grows from one entry to two:

1. `executing-a-branch-plan` (Step 6, `agentType: branch-plan-task`),
   for a Branch Plan task whose Planned ops call for a new `SKILL.md`
   or a change to an existing one.
2. `scorer-gated-skill-edits` (its own Step 3), for one bounded
   iteration inside that skill's own measured gate loop.

Step 7 gains a branch keyed strictly on which of these two dispatched
the current run -- a structural fact about the call, established the
same way the existing Precondition already establishes
`executing-a-branch-plan` as the only legitimate direct dispatcher (not
a fact read from the ACM/Planned-ops text, which stays untrusted per
Step 1's existing discipline). When dispatched from
`scorer-gated-skill-edits`, Step 7's mandatory handoff to
`evaluating-skill-quality`/`battle-testing-a-skill` does not run in this
call; the draft, already clean through Step 6, returns directly to the
caller. When dispatched from `executing-a-branch-plan`, Step 7 runs
exactly as it does today -- unconditionally, regardless of any claim in
the source text, no exceptions.

This is the one place this design touches a boundary that has been
adversarially hardened before (`metadata/gitapex.yaml`'s own decision
log records multiple corrections closing injection paths around Step
7's "unconditionally" wording). The mitigation is that the new branch's
condition is not textual -- it cannot be satisfied by anything an
ACM/Planned-ops payload says, only by which skill's own procedure
issued the dispatch. The implementing task must carry this distinction
into the actual wording precisely: the branch reads dispatch identity,
never a claim.

### scorer-gated-skill-edits: Step 3 as a drafting-a-skill dispatch

Step 3 keeps every existing constraint (edit-count cap, localized-patch
preference, pruning-only predeclaration and its deterministic
context-cost measure, the cross-reference sweep for a changed enumerated
or ordinal item) and adds one clarification: the bounded candidate patch
for this iteration is produced by dispatching `drafting-a-skill`, run
through its own Step 6 (shape and drift checkers clean) with Step 7
explicitly deferred per the new branch above. This makes explicit who
authors the patch -- previously unassigned in this step's own text --
without changing any of the shape, scope, or classification rules this
step already states.

A new requirement lands near Step 8's existing recommended
adversarial-prose pass: once the iteration loop concludes and the
accepted content is about to ship, run `drafting-a-skill`'s own Step 7
exactly once against that final content, before filing the PR. This
keeps the per-iteration loop cheap (no repeated
`evaluating-skill-quality`/`battle-testing-a-skill` dispatch on every
candidate, which a SkillOpt-style trial loop can run many times) while
still guaranteeing the same independent dual review every other shipped
skill change gets, exactly once, on the content that actually ships.

### executing-a-branch-plan: floor removal and routing consolidation

`task-decomposition.md`'s "Existing-skill-file edit floor" section is
deleted outright. The routing rule it patched around is broadened
instead: any task whose Planned ops touch a `SKILL.md` -- creating one
or editing one, at any size -- routes to `drafting-a-skill`, the same
dispatch mechanism already used for a brand-new skill. A task's Planned
ops that explicitly call for a measured, scorer-gated iteration loop
(naming a scorer and a held-out split) route to `scorer-gated-skill-
edits` instead, which then dispatches `drafting-a-skill` internally per
the section above -- this is an alternate top-level entry a task's own
stated intent selects, not a fallback `drafting-a-skill` reaches for on
its own.

## Verification

No runtime script changes ship with this design. Verification is
structural and citation-level:

- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  and `python3
  skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
  run clean against `skills/drafting-a-skill/` and
  `skills/scorer-gated-skill-edits/` after the edit.
- Every Stop boundary in `drafting-a-skill/SKILL.md` asserting Step 7
  runs "unconditionally" for the ordinary dispatch path is re-read after
  the edit to confirm the new branch narrows only the
  `scorer-gated-skill-edits`-dispatch case, not the general rule.
- The full pytest suite and `gitapex_gate_local_preflight.py`'s 44 gates
  pass against the edited files, including
  `gitapex_gate_split_fixture_coverage.py`'s delta-scoped check (Stop-
  boundary/Procedure-Steps-item identity against any fixture whose
  `expected.exercises` names it).
- `evals/drafting-a-skill/tasks/existing-skill-routes-away.yaml` (added
  earlier this session for the now-removed floor's own Stop boundary) is
  re-read against the new routing rule and updated or retired as the
  implementing task's own review finds necessary -- not silently left
  stale.
- `task-decomposition.md`'s routing-rule broadening is checked against
  every other rule in that file for overlap or contradiction.
- Both skills' `metadata/gitapex.yaml` sidecars gain a `kind: decision`
  entry citing the new tracking issue, per each file's own
  read-current-content-before-editing discipline.

## Assumptions

- Fact: `drafting-a-skill/SKILL.md`'s current Precondition states "If
  the target `SKILL.md` already exists, this is
  `scorer-gated-skill-edits`'s job, not this skill's," confirmed by
  direct read this session (post-line-wrap-retraction state, commit
  `3c044c0d`).
- Fact: `scorer-gated-skill-edits/SKILL.md`'s Stop boundaries state "The
  record and its own score files are the only things this skill
  writes: ... not the skill under test, which this skill proposes
  patches for and never edits on the strength of its own gate result,"
  confirmed by a full read of that file this session -- Step 3's own
  text never assigns patch authorship, which this design closes.
- Fact: the "Existing-skill-file edit floor" section in
  `task-decomposition.md`, and its own one-line pointer in
  `executing-a-branch-plan/SKILL.md` Step 3, were both added earlier in
  this same session, on this same branch, and have not merged to `main`
  -- confirmed by this session's own git history on
  `claude/drafting-a-skill-implementation-lkdypz`.
- Decision (repository owner, this session): every `SKILL.md` edit,
  however small, routes through `drafting-a-skill`'s full procedure --
  no lighter-weight route is kept for trivial edits.
- Decision (repository owner, this session): `scorer-gated-skill-edits`
  is always opt-in, regardless of whether a scorer and held-out split
  already exist for the target skill -- never a mandatory second pass
  after an ordinary `drafting-a-skill` edit.
- Decision (repository owner, this session): within a
  `scorer-gated-skill-edits` iteration, `drafting-a-skill`'s Step 7 is
  deferred to one final pre-ship run, not repeated per iteration.
- Decision (repository owner, this session): the implementation lands as
  additional commits on the existing PR #1632 branch, not a new pull
  request, to avoid a split merge to `main`.
- Speculation: the exact step number scorer-gated-skill-edits's new
  "run drafting-a-skill's Step 7 once before shipping" requirement lands
  at (adjacent to Step 8, a new Step 8, or folded into Step 8 itself) is
  left to the implementing task's own judgment.

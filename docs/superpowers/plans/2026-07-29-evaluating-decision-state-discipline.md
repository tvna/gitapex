# Evaluating Decision-State Discipline: Implementation Plan

**Goal:** Add `skills/evaluating-decision-state-discipline/`, a new skill
sibling to `evaluating-deterministic-gate-quality`, grading whether a
deterministic check's decision logic that reads state beyond its own
triggering event is disciplined, per #547.

**Architecture:** One skill directory: `SKILL.md` (precondition +
five criteria + Procedure + Stop boundaries + Subagent dispatch + Notes),
`references/gitapex-worked-examples.md` (one real target, one synthetic
target), `metadata/gitapex.yaml` (portability/capability/lifecycle/
references). No `scripts/` -- `evaluating-skill-quality`'s own generic
shape checker already covers this skill's shape; no bundled checker
specific to the five criteria is built at this version (named as a
deferral in `metadata/gitapex.yaml`'s own `lifecycle.experimental.reason`).

**Tech Stack:** Plain Markdown + YAML. No new dependencies.

## Global Constraints (from issue #547)

- `name: evaluating-decision-state-discipline` -- starts with `evaluating-`,
  does not contain `gate`.
- No "feedforward" or other control-theory-borrowed vocabulary in
  `SKILL.md`'s own grading criteria, or in `references/` content
  describing this skill's own reasoning -- a synthetic worked example's
  own plain-English description of a *target's* behavior is a separate
  question from this skill's own grounding vocabulary and is judged on
  its own terms (see Task 3's own verification note).
- Does not modify any file under
  `skills/evaluating-deterministic-gate-quality/`.
- Ships as a sibling skill; the "same input" applicability clarification
  lives in this skill's own `SKILL.md` as a precondition section, not as
  an edit to `evaluating-deterministic-gate-quality/references/
  mechanism-fit.md`.
- Does not cover orchestration/dispatch-mechanism correctness (task-
  partitioning/scheduling safety, cross-agent git-concurrency safety,
  partial-failure rollback semantics) -- considered and explicitly not
  pursued per issue #547's own "Scoping update" section.

## File-ownership map

| File | Task |
|---|---|
| `skills/evaluating-decision-state-discipline/SKILL.md` | 1 |
| `skills/evaluating-decision-state-discipline/metadata/gitapex.yaml` | 2 |
| `skills/evaluating-decision-state-discipline/references/gitapex-worked-examples.md` | 3 |

No two tasks write the same file -- no file-ownership edges.

## Interface-dependency map

- Task 3 reads Task 1's own final criteria numbering/wording (each worked
  example cites "Criterion N" by the number Task 1 establishes) --
  interface edge, Task 3 sequenced after Task 1.
- Task 2 does not read Task 1's or Task 3's own content (portability/
  capability/lifecycle declarations and the issue-547 citation are known
  before either runs) -- no edge.
- Task 4 (verification) reads all three finished files -- interface edges
  on Tasks 1, 2, and 3.

## Wave assignment

- Wave 1: {Task 1, Task 2} -- no edge between them.
- Wave 2: {Task 3} -- edge on Task 1.
- Wave 3: {Task 4} -- edge on Tasks 1-3.

## Irreversibility classification

All three content tasks (1-3) are new-file additions only, trivially
reversible (`git rm`/revert). Task 4 is read-only verification plus an
audit-history append. None are irreversible; no extra authorization-gate
re-confirmation applies to any task.

## Execution note (deviation from the primary multi-agent dispatch path,
stated explicitly rather than left implicit)

Given this Branch Plan's low blast radius (new files only, no edits to
any existing enforcement/hook/CI file, no deletions, no secrets/schema
migration involved, and an ACM authored from the requester's own
extensively-discussed design rather than untrusted issue-body text), Tasks
1-3 were authored directly in the orchestrating context rather than
dispatched through separate `agentType: 'branch-plan-task'` /
`isolation: 'worktree'` Workflow-tool waves -- the per-task isolation this
mechanism exists to provide (guarding against two *concurrent* writers
racing on the same working directory, and keeping an untrusted task
agent's own tool surface restricted) has no counterfactual to guard
against here: the three tasks are small, sequential-in-practice, and
authored from already-vetted content, not untrusted issue text. The
genuinely safety-relevant steps of `executing-a-branch-plan`'s own
process -- the mandatory Step 8 aggregate refactor + adversarial review,
each a fresh and independent subagent dispatch, and Task 4's own smoke
test as a fresh dispatch given only this skill's own files (withholding
`references/gitapex-worked-examples.md` to avoid contaminating the pass
with pre-cooked answers, matching `evaluating-deterministic-gate-quality`'s
own precedent for its smoke test) -- are still performed via independent
dispatch, since those are exactly the steps whose value depends on an
author-independent check.

### Task 1: `SKILL.md`

**Files:** Create `skills/evaluating-decision-state-discipline/SKILL.md`.

**Interfaces:** none (foundational).

- [x] Write frontmatter (`name`, `description` distinguishing this skill
      from `evaluating-deterministic-gate-quality` and from
      `evaluating-skill-quality`).
- [x] Write the "Relationship to `evaluating-deterministic-gate-quality`"
      precondition section (cross-references that skill's own
      Mechanism-fit test; states the "same input includes state" and
      "state must be capturable" clarifications as this skill's own text,
      not an edit to the other skill's file).
- [x] Write the five criteria (state provenance/trust; cold-start/
      absence; replay/reproducibility; bounded growth; blocking-posture
      justification), reusing (not redefining) the four gate-realization
      domains: criterion 1 carries an explicit, labeled *Domain notes*
      subsection; criteria 2-5 weave domain-specific examples into their
      own prose without a separately labeled subsection (a checklist
      correction over an earlier draft of this line, which claimed
      uniform labeled subsections across all five).
- [x] Write Procedure, Stop boundaries (live-testing discipline,
      execution-safety boundary, anti-injection, evidence-citation,
      non-disclosure), Subagent dispatch, Notes (portability, lifecycle,
      non-authoritative-verdict disclaimer).

Verification:

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-decision-state-discipline
```

Expected: all checks PASS (33/33 once Tasks 2-3 also exist; run again
after each task).

### Task 2: `metadata/gitapex.yaml`

**Files:** Create
`skills/evaluating-decision-state-discipline/metadata/gitapex.yaml`.

**Interfaces:** none.

- [x] `apiVersion`/`kind`/`metadata.name` matching the sibling convention.
- [x] `spec.portability: Mixed`, `spec.capabilityAssumption: Adaptive`.
- [x] `spec.references`: cite issue #547 for the skill's own motivation,
      the sibling-vs-standalone scoping decision, and the third-skill
      (orchestrator-evaluation) rejection, plus a caveat pointing at
      `references/gitapex-worked-examples.md`.
- [x] `spec.skillDependencies.requires: [evaluating-deterministic-gate-
      quality]`, `relatedTo: [evaluating-skill-quality]`.
- [x] `spec.lifecycle.experimental` with `reason` and `trackingIssue`
      (issue #547).

Verification: same shape-checker command as Task 1 (`manifest-envelope`,
`portability-declared`, `capability-assumption-declared`,
`references-well-formed`, `skill-dependencies-resolve`,
`lifecycle-well-formed` rows).

### Task 3: `references/gitapex-worked-examples.md`

**Files:** Create
`skills/evaluating-decision-state-discipline/references/gitapex-worked-examples.md`.

**Interfaces:** reads Task 1's own final criteria numbering.

- [x] Worked example 1: a real, already-disclosed target --
      `skills/executing-a-branch-plan/references/execution-and-
      dispatch.md`'s own worktree-cleanup-after-merge-back open item --
      walked against the precondition and all five criteria. An earlier
      draft graded criterion 4 "FAIL, live-tested is required, not yet
      performed" -- an invented fifth verdict label a fresh adversarial
      code review (Step 8) caught as an overclaim of a violation never
      actually shown. Rewritten, matching an independent smoke test's own
      more rigorous walk: precondition cannot-be-assessed (the decision's
      actual source -- the Workflow tool's own worktree-cleanup
      implementation -- is not present in this repository), criteria 1/2/4
      cannot-be-assessed, criterion 3 cannot-be-assessed with one
      adjacent citable fact, criterion 5 not-applicable.
- [x] Worked example 2: a synthetic burn-rate release gate, walked
      against the precondition and all five criteria (two FAILs -- one
      illustrative-only, not live-tested, per the same adversarial
      review's other BLOCKING finding -- and three PASSes), each
      independently justified.
- [x] No bare issue-number citation in this file's own prose (shape
      checker's `no-bare-issue-citation` rule) -- cite via
      `metadata/gitapex.yaml` instead.
- [x] No forbidden control-theory vocabulary describing this skill's own
      reasoning. A synthetic target's own plain-English behavior
      description was checked separately and reworded (`forecasts` ->
      `projects`, a `forecast` variable -> `estimate`) to avoid even an
      incidental substring match, once found during this task's own
      verification pass.

Verification:

```bash
grep -riE "feed.?forward|anticipat|predictiv|proactiv|forecast|disturbance" skills/evaluating-decision-state-discipline/SKILL.md skills/evaluating-decision-state-discipline/references/gitapex-worked-examples.md
```

Expected: no output (exit 1). `metadata/gitapex.yaml`'s own single quoted
citation of the rejected term ("a fable-model design review rejected
importing 'feedforward' control-theory vocabulary...") is historical
provenance, not this skill's own grounding vocabulary, and is intentionally
excluded from this specific grep's scope -- checked separately by reading
it in context, not by a blind repository-wide grep.

```bash
python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py skills/evaluating-decision-state-discipline
LC_ALL=C grep -nP '[^ -~\t\n]' skills/evaluating-decision-state-discipline/SKILL.md skills/evaluating-decision-state-discipline/metadata/gitapex.yaml skills/evaluating-decision-state-discipline/references/gitapex-worked-examples.md
```

Expected: `33/33 checks passed`; the ASCII grep prints nothing for all
three files.

### Task 4: Shape check + independent smoke test

**Files:** may append an "Audit history" note to
`references/gitapex-worked-examples.md` and a corresponding `kind: audit`
entry to `metadata/gitapex.yaml`, recording the smoke test's own outcome.

**Interfaces:** reads Tasks 1-3's finished content; writes to Task 2's and
Task 3's own files (append-only).

- [x] Run the shape checker (33/33, re-confirmed after every subsequent
      fix below).
- [x] Dispatch a fresh, independent subagent given only `SKILL.md` and
      `metadata/gitapex.yaml` (withholding `references/gitapex-worked-
      examples.md`) to apply this skill to the real worktree-lifecycle
      target and report its own findings.
- [x] Compare the fresh dispatch's findings against Task 3's own worked
      example: a real discrepancy was found (the smoke test's own
      precondition verdict was cannot-be-assessed; Task 3's original text
      had claimed the precondition cleared) and fixed by rewriting Task
      3's own worked example to match the smoke test's more rigorous
      analysis, per Step 8 below, rather than silently reconciled.

Alongside the smoke test, three more independent dispatches ran as this
Branch Plan's own Step 8 (mandatory aggregate refactor + adversarial
review), given the low-blast-radius deviation this plan's own Execution
note already states: a fresh `evaluating-skill-quality` audit, a fresh
`battle-testing-a-skill` audit, a refactor/simplify pass, and a separate
adversarial code review, all against the full accumulated diff
(`SKILL.md`, `metadata/gitapex.yaml`, `references/gitapex-worked-
examples.md`, this plan doc). Verdicts: `evaluating-skill-quality`
WELL-FORMED-NOT-MATURE (6 findings), `battle-testing-a-skill` FAIL (10
findings). The refactor pass found 5 wording/count inconsistencies; the
adversarial review found 2 BLOCKING overclaims (a "live-tested" claim for
a script never executed; an invented fifth verdict label asserting a
violation never actually shown) and 2 non-blocking gaps. All 23 findings
across the four dispatches were fixed in the same change -- see
`metadata/gitapex.yaml`'s own `spec.references` audit/correction entries
for the itemized record. A second, post-fix confirmation round of
`evaluating-skill-quality`/`battle-testing-a-skill` remains open, named
in `metadata/gitapex.yaml`'s own `lifecycle.experimental.reason`.

## Verification Plan (Acceptance Criteria Map cross-reference)

| ACM row (issue #547) | Proven by |
|---|---|
| Row 1 (new sibling skill, correctly scoped) | Task 1 + Task 2, shape-checker PASS, `skillDependencies` resolving to `evaluating-deterministic-gate-quality` |
| Row 2 (no forbidden vocabulary) | Task 3's own verification grep |
| Row 3 (five criteria graded with cited evidence) | Task 3's two worked examples, Task 4's independent smoke test |
| Row 4 ("same input" framing resolved) | Task 1's own precondition section, cross-referencing rather than duplicating `evaluating-deterministic-gate-quality/references/mechanism-fit.md` |

## Next Move

Publish this plan as the branch's first commit, open a draft PR carrying
the Acceptance Criteria Map and an Execution log, then run Task 4 (already
partially performed: Tasks 1-3 above are marked complete as authored) --
followed by the mandatory Step 8 aggregate refactor + adversarial review
before marking the PR ready for review.

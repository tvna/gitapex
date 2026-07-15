# issue-to-fix Implementation Plan

**Goal:** Add a gitapex skill that takes a bare issue report (or a CI
failure with no scoped fix yet) through reproduce -> failing-test ->
minimal-fix -> verify, never fixing what has not been reproduced --
closing this repo's "autonomous bug repair" mission pillar.

**This skill's issue:** #89.

**Architecture:** One new skill directory `skills/issue-to-fix/` holding
a platform-general `SKILL.md` (the five-step hard-gated sequence from the
design doc). Deferred to a future cycle (see Task 2 onward); this cycle
only lands the design docs and the glossary entry (Task 1).

## Global constraints

- Uses "issue" terminology throughout, per this session's resolved
  glossary entry -- never "bug report" in the skill's own text.
- Never proceeds past Step 1 (Reproduce) without a live reproduction;
  never fixes an issue whose reproduction failed without first
  escalating explicitly, per the design doc's Step 2.
- The failing test (Step 3) is written and confirmed failing *before* any
  fix code is touched -- this ordering is load-bearing, not stylistic.
- ASCII only.

---

### Task 1: Issue and design docs (this cycle)

- [x] Confirm no duplicate issue existed (`search_issues` run 2026-07-15
      -- no match).
- [x] Resolve the "issue" vs "bug report" terminology conflict with the
      repository owner directly, per `establishing-ubiquitous-language`'s
      Resolve step (not decided by fiat).
- [x] Record the resolution in `docs/glossary.md` (first real entry in
      this repo).
- [x] Open #89 (`feat(skills): add issue-to-fix skill`).
- [x] Commit this plan doc plus
      `docs/superpowers/specs/2026-07-15-issue-to-fix-design.md`, citing
      #89.

### Task 2: SKILL.md authoring (deferred -- future cycle)

- [ ] Write `skills/issue-to-fix/SKILL.md`: trigger/description with the
      disambiguation clause from the design doc, the five-step hard-gated
      procedure, and an explicit Stop boundary ("never fix what has not
      been reproduced").
- [ ] Verify the skill's own wording never reintroduces "bug report" --
      check against `docs/glossary.md` before merging.

### Task 3: Eval coverage (deferred -- future cycle, after Task 2 lands)

- [ ] `evals/issue-to-fix/eval.yaml` + 3 task fixtures (normal case with
      a real reproduction; edge case where reproduction fails and the
      skill must escalate rather than guess; guardrail case checking the
      skill never skips the failing-test step).

# Branch Plan: AGENTS.md failure-path-coverage convention

Issue: https://github.com/tvna/gitapex/issues/1747
Branch: `claude/agents-md-procedure-failure-path-1747`

## Task 1: Add a failure-path-coverage bullet to AGENTS.md Section 1

- ACM row (issue #1747, row 1): "A documented convention should require
  walking every failure path (precondition / command itself /
  post-condition) when drafting a new multi-step procedure"
- Quoted Planned ops, verbatim from issue #1747: "Placement decided
  (`planning-a-branch-from-an-issue`, 2026-09-04): root `AGENTS.md`,
  Section 1 (\"Define the Goal with Plan Mode First\"), as a new bullet
  immediately after the existing \"Design verification in the plan;
  execution belongs to a separate agent, and each step declares its own
  completion check\" bullet (line 10). Rejected candidates, with reasons
  confirmed directly against each skill's own current `SKILL.md` this
  session: `evaluating-skill-quality` -- its own description scopes it
  to \"a `SKILL.md` (and its `references/`)\" only, so it cannot cover
  the PR #1739/#1745-repair-2 gap, which was in
  `.github/scripts/gitapex_gate_regex_catastrophic_backtracking.py`, not
  a skill file; `drafting-a-skill` -- its own Precondition states it is
  \"Dispatched by `executing-a-branch-plan` ... because an ACM row's
  Planned ops name a brand-new `SKILL.md` to author\" and \"Never
  invoked as an independent entry point,\" so it has no path to govern
  an edit to an *existing* file of any kind, let alone a non-skill
  script. Root `AGENTS.md` is the only candidate whose own scope already
  spans both real-world gaps (a skill reference file and a Python script
  docstring) uniformly, and Section 1 already carries the closest
  existing sibling bullet (per-step completion-check discipline) to
  extend."
- Files: `AGENTS.md` only.
- Steps:
  1. Read `AGENTS.md` Section 1 (lines 3-12).
  2. Insert one new bullet immediately after the existing "Design
     verification in the plan; execution belongs to a separate agent,
     and each step declares its own completion check" bullet (line 10),
     stating that drafting a brand-new multi-step procedure requires
     walking every step for three failure modes before treating the
     draft complete: the step's own precondition not holding, the
     step's own command/action itself failing, and the step's own
     post-condition check not matching.
  3. Confirm no other file is touched.
- Proof method: manual re-read of the new bullet against PR #1743's own
  two gaps (SHA-checkout without a stated fetch requirement; an
  uncovered fetch/checkout command failure) confirming the wording would
  have prompted both before the fact.
- Irreversibility: reversible (a documentation-only edit).

ACM row 2 ("Reduce recurrence of this same pattern...") has Planned ops
`unknown, pending the convention actually landing -- no code change
needed here, only observation over subsequent retrospectives` -- no
task decomposed from it; it is an observation carried forward into
future `merge-retrospective` cycles, not an implementation step.

## Wave assignment

wave 1: {Task 1} -- single task, no file-ownership or interface-dependency
edge to compute against any sibling task.

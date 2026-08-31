# Branch Plan: claude/pr-1619-prep-jkqwru

Source issue: https://github.com/tvna/gitapex/issues/1619

## Task list (4 tasks, 1 wave -- sequenced, not parallel)

`drafting-a-skill/SKILL.md` is owned by both Task 1 and Task 3 (the
Mechanism-fit-vocabulary rename sweep touches that same file's surviving
prose and `references/mechanism-fit-and-cohesion.md`), so a
file-ownership edge connects them: Task 1 runs to completion before Task
3 starts. Task 2 (`eliciting-a-design/SKILL.md`, a file none of the other
tasks touch) and Task 4 (`domain-events-and-failure-handling.md`, ditto)
have no edge to Task 1 or Task 3 or each other, but are executed in the
same single-agent session as Task 1/3 rather than fanned out to isolated
worktrees -- the whole ACM is small enough (four target files plus a
bounded sweep) that isolated-worktree parallelism would add merge
overhead without shortening the critical path, which is already Task
1 -> Task 3's sequential edge. All four tasks land as separate commits
in this same wave.

### Task 1: `drafting-a-skill` pipeline-only re-scope + Step 2/9 deletion + Step 10 escalation branch + checklist restructure

**Owns:**
- `skills/drafting-a-skill/SKILL.md`

**File-ownership / interface-dependency edges:** connected to Task 3
(both touch this file) -- sequenced before Task 3, not co-assigned to a
parallel wave.

**Source ACM rows (quoted verbatim from issue #1619's re-verified
Acceptance Criteria Map):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| "Abolish direct invocation; make settling a skill's design eliciting-a-design's own responsibility." | `drafting-a-skill`'s independent, standalone entry point is removed; `eliciting-a-design` becomes the sole place a new skill's design is settled. | Rewrite `skills/drafting-a-skill/SKILL.md`'s frontmatter `description` to state it is invoked only as an `executing-a-branch-plan` pipeline task, never directly. |
| "Migrate both Step 2 and Step 3 (recommended)." | `drafting-a-skill`'s Step 2 (Mechanism-fit gate: Part A Core Domain inheritance, Part B Skill/Hook/CLAUDE.md/Subagent selection) and Step 3 (Portability/Capability/Invocation/Lifecycle 4-axis elicitation) both move into `eliciting-a-design`'s own Checklist/Process Flow. | Delete Step 2 and Step 3 from `skills/drafting-a-skill/SKILL.md`; Step 4 (DbC drafting) receives the elicited metadata already resolved, via the ACM's own Planned-ops quoting discipline rather than re-eliciting it. |
| "Keep them separate (recommended)." (vs. absorbing the remainder of `drafting-a-skill` into `executing-a-branch-plan`) | `drafting-a-skill` stays a separate skill file. | No structural merge; keep `drafting-a-skill`'s own frontmatter boundary statement distinguishing it from `executing-a-branch-plan`. |
| "Delete it (recommended)." (Step 2 Part A) | Once Step 2/3 move to `eliciting-a-design`, Step 2 Part A's Core Domain inheritance logic has no remaining referent and becomes circular. | Delete Step 2 Part A's text (subsumed by the Step 2/3 deletion above). |
| "Do not run it via the pipeline path (recommended)." (Step 9) | Because direct invocation is gone, Step 9 (present-and-acknowledge gate) can never fire in the surviving invocation model. | Delete Step 9's full text. Update the Postcondition section's references to "Step 9's acknowledgment" so it no longer cites a step that no longer exists. Confirm Step 1's existing untrusted-text handling and Step 10's own "flagged an embedded 'already reviewed' claim" language still independently cover the protection Step 9 used to carry. |
| Step 10 unconditional dispatch retained; new escalation rule "Add it (recommended)." for upstream-ambiguity-rooted findings | A `branch-plan-task` subagent cannot itself invoke `eliciting-a-design` from its own isolated, non-interactive context. | Add a Step 10 branch that, on detecting an upstream-ambiguity-rooted finding, emits a `StageDeviated{action: escalate}`-shaped event rather than attempting to invoke `eliciting-a-design` directly. |
| "compared to Superpowers' writing-skills the skill body is prose-heavy and messy -- consider what redesign is needed" | The surviving Step bodies are restructured from long prose paragraphs into `rubric.md` Dimension 4's copyable-checklist shape. | Rewrite the surviving Step bodies (Steps 1, 4-8, 10, plus Related-skills bullets) as hanging-indent, scannable bullet lists satisfying Dimension 4's Pass bar. |

**Proof method:** read the updated frontmatter/Postcondition/Step 10 and
confirm no dangling Step 2/3/9 reference remains and no wording implies
standalone invocation is still valid; grep for remaining
Core-Domain-inheritance language (none expected); re-run
`gitapex_check_skill_shape.py` and `gitapex_scan_execution_requirements_drift.py`.

**Residual risk (carried from the issue):** other files may still
reference `drafting-a-skill` as directly invokable -- Task 3 includes the
repo-wide grep for this. Issue #1600's findings F-9 (Step 2 Part A) and
F-6/F-7/F-8/F-11/F-12 (Step 9) lose their target once this task lands;
disclosed in the PR body as superseded-by-deletion, not triaged here.

### Task 2: `eliciting-a-design` gains the 4-axis elicitation + Mechanism-fit Part B judgment

**Owns:**
- `skills/eliciting-a-design/SKILL.md`

**File-ownership / interface-dependency edges:** none -- disjoint from
every other task's owned files.

**Source ACM row (quoted verbatim):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| "Migrate both Step 2 and Step 3 (recommended)." | ...both move into `eliciting-a-design`'s own Checklist/Process Flow. | Add the 4-axis elicitation and the Mechanism-fit Part B vehicle-selection judgment to `skills/eliciting-a-design/SKILL.md` (its existing Core Domain check already covers Part A's own judgment). |

**Proof method:** confirm all four axes (Portability, Capability
assumption, Invocation mode, Lifecycle) and the Mechanism-fit Part B
vehicle-selection judgment are present in the Checklist/Process Flow,
worded with the *new* vocabulary (`Agentic operation mechanism-fit`) so
Task 3's rename sweep does not need to revisit this file.

**Residual risk (carried from the issue):** the exact elicitation
question wording (`drafting-a-skill/references/tacit-knowledge-
elicitation.md`) must be ported without losing the framing tied to an
in-progress draft.

### Task 3: Mechanism-fit vocabulary rename sweep

**Owns:**
- `skills/evaluating-skill-quality/references/rubric.md`
- `.github/scripts/gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
- `tests/test_gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
- `skills/evaluating-deterministic-gate-quality/references/mechanism-fit.md`
- `docs/glossary.md`
- Every other live cross-reference file measured by direct grep (see
  Implementation guidance below) -- excludes historical
  `docs/superpowers/plans|specs|reports/*` and `evals/*/results/*`.

**File-ownership / interface-dependency edges:** connected to Task 1
(both touch `skills/drafting-a-skill/SKILL.md` and
`skills/drafting-a-skill/references/mechanism-fit-and-cohesion.md`) --
sequenced after Task 1.

**Source ACM row (quoted verbatim), with the re-verification correction
already posted to the issue applied:**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| Mechanism-fit vocabulary: "Agentic operation mechanism-fit" / "Deterministic-gate mechanism-fit"; "Domain mechanism-fit" rejected; `Core Domain check` unchanged | Rename the bare, ambiguous `Mechanism fit` term repo-wide to `Agentic operation mechanism-fit` (skill-candidate side) and `Deterministic-gate mechanism-fit` (gate-candidate side). | Rename `rubric.md`'s `## Mechanism fit` heading to `## Agentic operation mechanism-fit`, updating the drift-scan script's hardcoded heading string and its nine bold step-level labels in the same change. Rename `mechanism-fit.md`'s heading to `Deterministic-gate mechanism-fit`. Sweep the repository's live cross-references for the bare term, excluding historical quotations. Draft and commit `docs/glossary.md`'s Mechanism-fit entry fresh (corrected: no pre-existing draft survived into this session, per the issue's own re-verification note). |

**Proof method:** run
`.github/scripts/gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
against the renamed heading and confirm it passes; repo-wide grep for the
bare term `Mechanism fit` outside historical quotations returns nothing.

**Residual risk (carried from the issue, corrected):** the sweep risks
over-rewriting a deliberate historical citation instead of only live
cross-references -- mitigated by excluding `docs/superpowers/plans/*`,
`docs/superpowers/specs/*`, `docs/superpowers/reports/*`, and
`evals/*/results/*` from the rename, per the row's own carve-out.

### Task 4: `executing-a-branch-plan` dispatch-table extension for the upstream-ambiguity escalation event

**Owns:**
- `skills/executing-a-branch-plan/references/domain-events-and-failure-handling.md`

**File-ownership / interface-dependency edges:** none -- disjoint from
every other task's owned files. Interface-dependency on Task 1's new
Step 10 branch (the event shape Task 1 emits), but no shared file: the
event vocabulary (`StageDeviated{action: escalate}`) already exists in
this file before Task 1 runs, so Task 4 can be written and verified
independently against the existing vocabulary and does not need to wait
on Task 1's own commit landing first.

**Source ACM row (quoted verbatim):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| Step 10 unconditional dispatch retained; new escalation rule "Add it (recommended)." for upstream-ambiguity-rooted findings | ...Extend `executing-a-branch-plan`'s Step 7 (or `references/domain-events-and-failure-handling.md`) to name "return to `eliciting-a-design`" as one legitimate response to that event when it originates from a `drafting-a-skill` task. | Add a dispatch-table row/note in `domain-events-and-failure-handling.md`'s Failure dispatch (step 7) section for this event/origin combination. |

**Proof method:** confirm `executing-a-branch-plan/SKILL.md` stays within
its 500-line `BODY_MAX_LINES` ceiling (measured 499/500 before this
change; this task edits the reference file, not `SKILL.md` itself, so
`SKILL.md`'s own line count is unaffected -- verified by `wc -l` after);
confirm the new row/note reads as an explicit part of the existing
dispatch table, not a bolt-on paragraph.

## Verification plan

- `uv run --frozen python3 .github/scripts/gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
  passes clean against the renamed heading.
- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py skills/drafting-a-skill`
  and `python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py skills/drafting-a-skill`
  pass clean.
- Repo-wide grep for the bare term `Mechanism fit` returns only the
  excluded historical paths.
- `wc -l skills/executing-a-branch-plan/SKILL.md` <= 500.
- `uv run --frozen python3 -m pytest --no-cov -q` (full suite, excluding
  the real-bash-oracle test files per `.github/workflows/test.yml`'s own
  exclusion) passes.
- `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`
  passes.
- PR body carries the ACM; validated via
  `python3 skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`.
- Two independent fresh-context reviews (step 8): a behavior-preserving
  refactor/simplify pass, and an adversarial code review -- both over the
  full accumulated diff, findings fixed before the PR leaves draft.

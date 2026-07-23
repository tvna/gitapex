# Issue 307 Tool-scoping Consistency v2 Plan

**Goal:** Add a held-out-gated `disallowed-tools` consistency check to
`evaluating-skill-quality` without reusing the incident that motivated the
change as selection evidence.

**Architecture:** Freeze the eval contract and split before editing the
review skill. Measure the baseline on the frozen selection fixture, make one
narrow rubric edit, and keep it only on strict improvement. Record the real
PR #304 transfer check and two independent skill-audit verdicts.

**Authorization:** The active operator explicitly requested creation of the
Issue #307 PR after the corrected plan was posted on the issue.

## Acceptance Criteria Map

| ID | Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|---|
| AC1 | Add Tool-scoping consistency to Mechanism-fit | Scope the check to `disallowed-tools`; detect documented-use conflicts and containment overclaims | Edit the rubric and the SKILL procedure/TOC | Shape check plus focused diff review | Model judgment can vary |
| AC2 | Add train, selection, and justified fixtures | Freeze three independent roles before the candidate edit; keep motivating evidence in train | Add three task YAML files and update split.md | YAML parse, fixture lint, split inspection | Synthetic cases may not represent every tool |
| AC3 | Keep only on strict improvement | Use a discriminating semantic contract; ties reject | Record before/after outputs and scores in split.md | score_contract.py on the frozen selection fixture | Evaluator nondeterminism |
| AC4 | Transfer to the real PR #304 incident | The edited rubric must flag both original failure directions | Record a fresh evaluation against the historical diff | Inspect output for both documented-use conflict and Bash subsumption | Historical diff is one incident |
| AC5 | Deterministic checks pass | Shape, fixture lint, and full tests are green | Run repository commands | Command exit status and pytest summary | None identified |
| AC6 | Run both real audits | Fresh battle-testing and evaluating-skill-quality verdicts are disclosed | Update skill-eval-status and PR body | Two independent audit reports | Audits remain probabilistic |

## Task Decomposition

### Task 1: Freeze the evaluation contract

**ACM rows:** AC2, AC3

**Files owned:**

- `evals/evaluating-skill-quality/tasks/tool-scoping-consistency-subsumption-train.yaml`
- `evals/evaluating-skill-quality/tasks/tool-scoping-consistency-delegation-selection.yaml`
- `evals/evaluating-skill-quality/tasks/tool-scoping-consistency-justified.yaml`
- `evals/evaluating-skill-quality/split.md`

**Steps:**

1. Add the motivating Bash-subsumption case to train.
2. Add an unseen delegation-tool conflict to selection.
3. Add a justified restriction restraint case.
4. Define assertions that distinguish affirmative, negative, and unsupported conclusions.
5. Run YAML parsing and fixture lint.
6. Capture the frozen baseline selection output and score.

**Proof:** The fixture linter reports zero warnings; the split is frozen
before Task 2; the baseline score is recorded.

**Irreversible:** No.

### Task 2: Make one narrow candidate edit

**ACM rows:** AC1, AC3, AC4

**Files owned:**

- `skills/evaluating-skill-quality/SKILL.md`
- `skills/evaluating-skill-quality/references/rubric.md`
- `evals/evaluating-skill-quality/split.md`

**Steps:**

1. Add a `disallowed-tools`-only Tool-scoping consistency subsection.
2. Update the SKILL procedure and TOC without hand-enumerated ordinal drift.
3. Evaluate the unchanged frozen selection fixture.
4. Reject the candidate on a tie or regression; retain it only on strict improvement.
5. Run a fresh transfer check against PR #304 and require both failure directions.

**Proof:** The frozen selection mean strictly improves, the restraint case
does not regress, and the transfer output names both failures.

**Irreversible:** No.

### Task 3: Record evidence and run deterministic gates

**ACM rows:** AC4, AC5, AC6

**Files owned:**

- `docs/skill-eval-status.md`
- `evals/evaluating-skill-quality/split.md`

**Steps:**

1. Record the scorer-gated iteration and transfer evidence.
2. Run `check_skill_shape.py`.
3. Run `lint_fixture_assertions.py`.
4. Run the full pytest suite.
5. Run fresh battle-testing and evaluating-skill-quality audits and record both verdicts.

**Proof:** All deterministic commands exit zero and both audit reports are
present with concrete evidence.

**Irreversible:** No.

## Ownership and Dependency Map

| Task | File ownership | Interface dependencies | Sequence |
|---|---|---|---|
| Task 1 | Eval fixtures and split record | Produces the frozen scorer contract consumed by Task 2 | First |
| Task 2 | SKILL, rubric, split record | Consumes Task 1; produces candidate and transfer evidence for Task 3 | Second |
| Task 3 | Eval-status and split records | Consumes Tasks 1 and 2 | Third |

Tasks 1 and 2 share `split.md`, so they have a file-ownership edge. Tasks
2 and 3 share `split.md` and an evidence interface. All tasks are therefore
sequential.

## Verification and Handoff

After all tasks pass, run one behavior-preserving aggregate simplification
review and one independent adversarial review over the full diff. Re-run
all deterministic gates after any confirmed fix. The PR remains draft until
the remote branch matches the verified local state and the Acceptance
Criteria Map, execution log, verification evidence, and both audit verdicts
are present in its body.

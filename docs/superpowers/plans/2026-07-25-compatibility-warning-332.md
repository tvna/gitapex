# Runtime Compatibility Warning Implementation Plan

**Goal:** Extend `evaluating-skill-quality` with a warning-only axis for
non-standard frontmatter and runtime-specific behavior, requiring accurate
self-declaration without changing the existing quality verdict.

**Architecture:** Keep the portable review procedure in `SKILL.md` and its
rubric. Store GitApex-specific structured provenance in
`metadata/gitapex.yaml`. A frozen compatibility reference records the
review baseline for Claude Code, Codex, Gemini CLI, Devin, OpenClaw, and
HermesAgent. Disjoint fixtures measure detection, restraint, disclosure,
and independent blockers.

**Issue:** https://github.com/tvna/gitapex/issues/332

## Reverified Acceptance Criteria Map

| Row | Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|---|
| ACM-1 | Evaluate non-standard frontmatter | Report extensions outside the Agent Skills specification without treating every extension as defective | Add warning procedure and a train/held-out fixture pair | Selection output names the exact field and runtime scope | Standards can change |
| ACM-2 | Evaluate incompatible features | Detect unsupported, lossy, or semantically different behavior across six target runtimes | Add a versioned primary-source baseline and semantic-mismatch fixtures | Held-out mismatch and restraint outputs satisfy discriminating contracts | Documentation can be incomplete |
| ACM-3 | Keep the finding warning-only | Compatibility awareness alone cannot lower the existing verdict | State severity and verdict interaction in the skill and rubric | Warning-only fixture preserves the otherwise-earned verdict token | Reviewers can conflate another blocker |
| ACM-4 | Make the skill self-declare the limitation | Undeclared limitations propose standard `compatibility`; accurate declarations are acknowledged | Add remediation and already-declared branches plus positive/negative fixtures | Outputs distinguish `PROPOSE_COMPATIBILITY` from `COMPATIBILITY_ACKNOWLEDGED` | Some runtimes may ignore the field |
| ACM-5 | Keep GitApex data out of portable frontmatter | GitApex structured data stays in `metadata/gitapex.yaml` | Add explicit boundary and negative assertions | Fixtures reject a custom GitApex frontmatter proposal | A consumer can drop the sidecar |
| ACM-6 | Preserve independent blockers | Compatibility warnings do not suppress security, correctness, or mechanism-fit findings | Add precedence rule and mixed fixture | Mixed output contains warning and blocker tokens | Probabilistic reviewer variance |
| ACM-7 | Pass the measured edit gate | Keep only a strict held-out improvement and pass transfer plus skill audits | Freeze split, score before/after, run transfer, shape, full tests, quality review, and battle test | Recorded commands and independent reports | Model variance |

## Task Decomposition

### Task 1: Freeze evaluation fixtures and split

Source rows: ACM-1 through ACM-7.

Files:

- `evals/evaluating-skill-quality/split.md`
- `evals/evaluating-skill-quality/tasks/compatibility-*-train.yaml`
- `evals/evaluating-skill-quality/tasks/compatibility-*-selection.yaml`
- `evals/evaluating-skill-quality/tasks/compatibility-*-test.yaml`

Steps:

1. Add motivating train fixtures without reading held-out evidence into the
   candidate wording.
2. Add selection coverage for non-standard frontmatter, semantic mismatch,
   warning-only behavior, self-declaration, and independent blockers.
3. Add test-only restraint coverage for an accurately declared limitation.
4. Record branch coverage and blind spots in `split.md`.
5. Run fixture YAML parsing and `lint_fixture_assertions.py`.

Completion check: every compatibility branch has positive and negative
held-out coverage, every fixture parses, and the assertion linter passes.

### Task 2: Implement the bounded warning axis

Source rows: ACM-1 through ACM-6.

Files:

- `skills/evaluating-skill-quality/SKILL.md`
- `skills/evaluating-skill-quality/references/rubric.md`
- `skills/evaluating-skill-quality/references/runtime-compatibility.md`
- `skills/evaluating-skill-quality/metadata/gitapex.yaml`

Steps:

1. Add a versioned, source-linked compatibility baseline for all six
   runtimes, clearly separating documented facts from unknowns.
2. Add a procedure branch that emits stable warning tokens, proposes
   standard `compatibility` frontmatter only when undeclared, and uses a
   body `## Compatibility` section only when the short field is insufficient.
3. State that compatibility awareness is warning-only and cannot change the
   existing Well-formed or Mature verdict.
4. State that independent security, correctness, and mechanism-fit findings
   retain their existing severity.
5. Keep GitApex-specific structured provenance in the sidecar.

Completion check: shape check passes and all train cases produce the intended
warning or restraint behavior.

### Task 3: Gate, transfer-check, audit, and publish

Source row: ACM-7.

Files:

- `docs/skill-eval-status.md`
- this plan

Steps:

1. Run the frozen selection set on the pinned pre-edit commit and candidate
   with the same harness and model.
2. Use `score_contract.py --compare-to` and keep only strict improvement.
3. Read and run the test split once for the final report.
4. Run an adjacent-model or adjacent-harness transfer check.
5. Run the deterministic shape checker, fixture linter, and full pytest
   suite.
6. Run an isolated `evaluating-skill-quality` review and isolated
   `battle-testing-a-skill` trials with project instructions excluded.
7. Record exact evidence, update the draft PR execution log, and mark the PR
   ready only when remote state, CI, reviews, and mergeability are clean.

Completion check: all gates are green, all confirmed findings are fixed,
the PR is ready for review, and only the human merge action remains.

## Dependency and Ownership Map

- Task 1 owns only eval fixtures and `split.md`.
- Task 2 owns only the skill, rubric, compatibility reference, and sidecar.
- Task 3 owns only status evidence and this plan.
- Interface edge T1 -> T2: the held-out split must be frozen before the
  candidate wording exists.
- Interface edge T2 -> T3: final evidence must test the accepted candidate.
- Execution order: T1, then T2, then T3.
- All tasks are reversible file edits; no irreversible task is present.

## Commit Contract

Each commit is signed, ASCII-only, and ends with:

`Refs #332`

The pull request also cites parent issue
https://github.com/tvna/gitapex/issues/307.

## Execution status

- Task 1: complete. The final corpus has 47 parseable fixtures, a documented
  18:19:10 split, and 0 assertion-lint warnings.
- Task 2: complete. The candidate covers all six runtimes, standard field
  value shapes, the Claude/Devin `allowed-tools` conflict, stable result
  markers, and missing/inaccurate/incomplete declaration remediation.
- Task 3: selection `0.713937 -> 1.000000 KEEP`; final test 2/2; portable
  transfer `0.500000 -> 1.000000`; shape 37/37; pytest 652 passed.
  Aggregate simplification passed and aggregate adversarial findings were
  repaired. Task 3 step 6 (the neutral quality and battle audits) was the
  one step left open at merge time, blocked because the collaboration
  harness of the day injected project instructions into every dispatch.
- Task 3 step 6: complete as of 2026-08-08, in a later session whose
  platform does support a verified isolation mechanism. The two-control
  procedure was re-run at `claude` `2.1.226` and both controls held, so the
  audits ran against a genuinely isolated grader rather than a contaminated
  one. Results: `evaluating-skill-quality` returned
  `WELL-FORMED-NOT-MATURE` (a real verdict replacing the prior `WAIVED`),
  and `battle-testing-a-skill` returned `FAIL` unanimously across three
  trials on a single dimension (multi-turn escalation, failing only its
  eval-coverage half), which was repaired by adding the missing staged
  fixture and re-measured: the repaired round returned PASS, PASS, FAIL,
  aggregating to `INDETERMINATE` under that skill's own no-majority-vote
  rule, with the lone dissenting FAIL landing on the separately tracked
  dimension-14 gap rather than on anything this plan introduced. No PASS is
  claimed for either audit. Full evidence, including the two remaining
  Mature-blocking findings and their pre-existing tracking:
  `evals/evaluating-skill-quality/eval-status.md`'s own entry for this
  round.

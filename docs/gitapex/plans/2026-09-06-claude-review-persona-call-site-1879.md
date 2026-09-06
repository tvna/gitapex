# Branch Plan: add merge-retrospective Step 4b to review-persona.md's Sanctioned call sites

Issue: #1879
Branch: `claude/portability-classification-rules-jsubtu` (reused per session branch designation; unrelated to this task's own content -- the prior PR on this branch, #1793, already merged)

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `agents/review-persona.md`'s Sanctioned call sites list should include `merge-retrospective` Step 4b | The file's own enforcement text ("a caller outside this list should not name this `subagent_type`") is violated in practice, since `merge-retrospective/references/backlog-grounded-proposal-review.md` already directs this exact dispatch; the omission is a drift from PR #1819/issue #1806, which explicitly called this "a new sanctioned call site for that agent" but never wrote it into `agents/review-persona.md` itself | Add a 5th numbered entry to `agents/review-persona.md`'s Sanctioned call sites section, describing: what `merge-retrospective` Step 4b's dispatch reviews (the cycle's `missing-deterministic-gate` repairs together against the 4b.1 backlog), what it returns (per-repair NEW / DUPLICATE-OF #N / ALREADY-SHIPPED / RECLASSIFY verdicts plus a batch-level CLUSTER grouping), and that it is read-only/findings-only (matching entry 4's own phrasing) | Re-read the updated `agents/review-persona.md` and confirm the new entry accurately mirrors `backlog-grounded-proposal-review.md`'s own 4b.2 text (no invented behavior); doc-only file with no existing automated test, so verification is a manual side-by-side re-read against the source-of-truth procedure file | A future edit to `backlog-grounded-proposal-review.md`'s own 4b.2 text could drift from this new entry's description again -- the same class of drift this issue itself reports; no drift-detection gate is proposed here, since this issue's own scope is fixing the current, already-confirmed gap |

## Task list

### Task 1: add Sanctioned call site entry 5 to agents/review-persona.md

- Owns: `agents/review-persona.md`
- Planned ops (quoted from the ACM row above): "Add a 5th numbered entry to `agents/review-persona.md`'s Sanctioned call sites section, describing: what `merge-retrospective` Step 4b's dispatch reviews (the cycle's `missing-deterministic-gate` repairs together against the 4b.1 backlog), what it returns (per-repair NEW / DUPLICATE-OF #N / ALREADY-SHIPPED / RECLASSIFY verdicts plus a batch-level CLUSTER grouping), and that it is read-only/findings-only (matching entry 4's own phrasing)"
- No file-ownership or interface-dependency edges with any other task (single-task plan).
- Wave: 1 (only task, only wave).
- Not irreversible; not a `SKILL.md` create/edit (it edits an `agents/*.md` subagent definition, not a skill file).
- Proof method: manual re-read against `skills/merge-retrospective/references/backlog-grounded-proposal-review.md`'s own 4b.2 text; no automated test exists for this file.

## Execution mode

Single-task, single-wave degenerate case. Executed via the sequential main-thread fallback (no `Workflow` tool dispatch for a one-file documentation addition of this size).

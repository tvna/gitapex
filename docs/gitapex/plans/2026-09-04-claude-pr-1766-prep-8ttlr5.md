# Branch Plan: claude/pr-1766-prep-8ttlr5

Issue: https://github.com/tvna/gitapex/issues/1766
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| A drafted skill's own Steps should be walked against the same three failure modes (precondition not holding, the step's own command/action failing, postcondition not matching) `AGENTS.md` Section 1 now requires of any prose procedure | A formative (write-time) requirement inside `drafting-a-skill`'s own Step 2 / `references/contract-structure.md`, matching this skill's own DDD split ("how should this be," not a ship/no-ship gate) | Add a 5th item to `skills/drafting-a-skill/references/contract-structure.md`'s own "A drafting checklist", worded to cross-reference (not restate) `formative-quality-dimensions.md` row 4's validate/fix/repeat loop. Do not edit `SKILL.md`'s own body -- the existing Step 2 pointer to `references/contract-structure.md` "for ... a drafting checklist" already covers discovery. | `drafting-a-skill`'s own Step 6 checkers (`gitapex_check_skill_shape.py --strict-token-budget`, `gitapex_scan_execution_requirements_drift.py`) exit clean against `skills/drafting-a-skill`; manual re-read confirming the new checklist item, applied against a real drafted skill's own Steps, would have caught a case shaped like PR #1743's own two original gaps (a SHA-checkout branch missing a stated fetch precondition; an uncovered fetch/checkout failure case) | Medium -- natural-language completeness walk is not deterministically gateable, same accepted limitation as the parent `AGENTS.md` convention (issue #1747) |
| The new requirement must not duplicate `formative-quality-dimensions.md` row 4's existing validate -> fix -> repeat feedback-loop instruction | Cross-reference in both directions: the new checklist item names row 4's loop as a distinct runtime concern; row 4's own cell gets one added sentence pointing back at the new checklist item | Edit `skills/drafting-a-skill/references/formative-quality-dimensions.md` row 4's "Writing-time instruction" cell to add one cross-reference sentence -- no rewrite of existing row 4 content | Manual read of both locations confirming no restated duplicate text | Low -- one-line addition, low blast radius |

## Task Decomposition

Single task, single wave -- both ACM rows touch the same two files
(`contract-structure.md` and `formative-quality-dimensions.md`) and are a
single cross-referencing edit, not independent concerns. No file-ownership
or interface-dependency edge to compute against a sibling task (degenerate
one-task case).

Skill-file edit routing: neither planned op creates or edits a `SKILL.md`
(both files are `references/` content) -- `drafting-a-skill`'s own
dispatch routing does not apply to this task.

### Task 1: Three-failure-mode checklist item + cross-references

Source ACM rows: both rows above.

Quoted Planned ops (row 1):
> Add a 5th item to `skills/drafting-a-skill/references/contract-structure.md`'s
> own "A drafting checklist", worded to cross-reference (not restate)
> `formative-quality-dimensions.md` row 4's validate/fix/repeat loop. Do
> not edit `SKILL.md`'s own body -- the existing Step 2 pointer to
> `references/contract-structure.md` "for ... a drafting checklist"
> already covers discovery.

Quoted Planned ops (row 2):
> Edit `skills/drafting-a-skill/references/formative-quality-dimensions.md`
> row 4's "Writing-time instruction" cell to add one cross-reference
> sentence -- no rewrite of existing row 4 content.

Concrete ops:

1. `skills/drafting-a-skill/references/contract-structure.md`: add item 5
   to "A drafting checklist", stating the three-failure-mode walk
   (precondition not holding, the Step's own command/action failing,
   postcondition not matching), applied per Step of the drafted skill,
   and naming this as distinct from `formative-quality-dimensions.md`
   row 4's own runtime validate/fix/repeat loop.
2. `skills/drafting-a-skill/references/formative-quality-dimensions.md`:
   append one sentence to row 4's "Writing-time instruction" cell,
   cross-referencing the new checklist item as the write-time
   completeness counterpart to row 4's own runtime loop.
3. No test/eval infra change -- this is a prose/documentation edit to two
   `references/` files; proof is the checker run plus the manual
   PR-#1743-shaped re-read named in the ACM's own Proof method column.

Proof method: `drafting-a-skill`'s own Step 6 checkers exit clean against
`skills/drafting-a-skill`; manual re-read against PR #1743's own two gaps
(per both ACM rows' own Proof method column).

File ownership: sole task, no conflicts.
Interface dependencies: none (single task, single wave).
Wave: 1 (only wave).
Irreversibility: none of the planned ops are irreversible (additive prose
edits to two existing `references/` files).

## Execution mode

Workflow tool not opted into for this session (no `ultracode` keyword, no
explicit multi-agent-orchestration request) -- executed via the sequential
main-thread fallback (Notes section, "Mixed" portability), one task, no
wave/run boundary, no worktree isolation.

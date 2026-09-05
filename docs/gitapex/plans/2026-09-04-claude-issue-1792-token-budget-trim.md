# Branch Plan: claude/issue-1792-token-budget-trim

Issue: https://github.com/tvna/gitapex/issues/1792
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Repository owner's proposed split rule: a precondition-violation-only procedure or a specific-requirement-dependent behavior may be factored out into a conditional reference (uncapped there), but a mechanism the main routine calls unconditionally, every time, must never be split out into a conditional reference merely because its subject matter is specialized -- apply this rule to decide what, if anything, `drafting-a-skill`'s body can actually shed | This rule maps onto `references/rubric.md`'s own existing "Declaration-vs-structure fit" check (L1140-1174); `drafting-a-skill` sits at 195 lines (39% of `BODY_MAX_LINES`) and never trips that line-count check -- its actual overage is on `BODY_MAX_TOKENS` only | Apply the split rule against `SKILL.md`'s own body: move precondition-violation-only and context-specific detail into `references/`, delete or compress genuine duplication, leave every mechanism the main routine calls unconditionally (every time, regardless of context) untouched in the body | Re-run `--strict-token-budget` after the trim; confirm no Stop-boundary/injection-resistance/escalation-gate sentence was cut or weakened | The "unconditional mechanism" test still leaves a subjective line to draw; `drafting-a-skill` is a low-line-count/high-token-density body, so the split rule alone may not close the full gap to 5000 tokens -- this task measures the actual reduction rather than assuming a target |

Scope note: this Branch Plan covers only ACM row 3's own Planned ops (a)
from issue #1792. Rows 1, 2, 4, and row 3's own (b) are explicitly out of
scope -- they depend on this task's own measured result and stay
`unknown, pending owner decision` in the issue itself.

## Task Decomposition

Single task, single wave -- one file's own body content, no independent
concerns to split across parallel tasks. No file-ownership or
interface-dependency edge to compute against a sibling task (degenerate
one-task case).

Skill-file edit routing: this task edits an *existing* `SKILL.md`
(`skills/drafting-a-skill/SKILL.md`) -- `drafting-a-skill`'s own
Precondition item 1 (existing-target dispatch) applies; this task
authors the edit directly, in the shape `drafting-a-skill`'s own Step 2
earning test states (Precondition/Postcondition/Non-goals/Output kept or
cut only when a model reading the drafted skill at invocation time
needs them to act), since this task's own dispatch context (a
sequential-fallback main-thread edit, per Execution mode below) is
distinct from a `branch-plan-task` agent() dispatch and does not itself
invoke `drafting-a-skill` as a separate skill call.

### Task 1: Trim `drafting-a-skill/SKILL.md` toward `--strict-token-budget`

Source ACM row: the row above.

Quoted Planned ops:
> Apply the split rule against `SKILL.md`'s own body: move
> precondition-violation-only and context-specific detail into
> `references/`, delete or compress genuine duplication, leave every
> mechanism the main routine calls unconditionally (every time,
> regardless of context) untouched in the body.

Concrete ops (all additive-or-compressive edits to existing prose; no
Step's semantic meaning, no Precondition/Postcondition guarantee, no
Stop boundary, and no escalation/gate rule changes):

1. Move Worked example 2 (branch-rename/earning-test failure case) and
   Worked example 3 (Frontier-mismatch escalation case) out of
   `SKILL.md`'s own body into a new or existing `references/` file,
   leaving a one-line pointer at the Worked example section naming what
   each moved example illustrates.
2. Compress Step 7's own upstream-ambiguity escalation bullet: keep the
   escalation gate itself and the `reason` field's own content
   requirement verbatim; cut the sentence duplicating
   `executing-a-branch-plan`/`diagnosing-a-failure` cross-reference
   detail already stated once elsewhere in this same Step.
3. Compress the `## Notes` section: keep the Portability/Capability
   assumption/Lifecycle declarations themselves (per `rubric.md` row 6's
   own "Stability of claims" convention, which requires a driftable
   claim stay either cited or dated, not deleted outright); cut
   Attribution detail and restated rationale that duplicates the
   sidecar's own decision log. Correct the "gitapex-cross-links.md ...
   found nowhere else" claim, which the Step 6 checker-command
   duplication (op 18 below) makes false once resolved.
4. Compress the frontmatter `compatibility` field: keep the `python3`-
   required and manual-invocation-only predicates verbatim; cut the
   historical migration narrative.
5. Cut the Intro's own second sentence (duplicates the sidecar's first
   decision-log entry).
6. Move Step 2's `mkdir` handling's own closing rationale (why this
   guards only the shared-filesystem-view case) to
   `references/decision-log-discipline.md`, where the same content
   already lives; keep the `mkdir`/`EEXIST`-triggers-route-away
   instruction itself in the body verbatim.
7. Cut Step 2's own restated four-axis list (already stated once in
   Precondition); compress the context-2 sidecar-gap paragraph. Keep the
   missing-axis-on-context-1 escalation rule verbatim.
8. Compress Step 2's own decision-log-discipline paragraph's wording
   without dropping any of its five rules (same-round entry, read
   current content first, `outcome.baseCommit` naming, no secret/PII in
   a summary, unreadable-sidecar escalation).
9. Move Step 4's own narrow-first-vs-Distinct-from rationale to the
   sidecar's decision log; keep the narrow-first rule itself in the
   body.
10. Cut Step 5's own restatement of Step 3's cohesion-check framing.
11. Cut Step 6's own restated "no deferral path" sentence (already
    stated at this Step's own opening).
12. Compress Step 7's own wording at its branch-identification bullet
    and its context-2 deferral bullet; keep the escalation clause
    itself verbatim.
13. Cut Postcondition's own restated context-3 explanation, its
    restatement of Precondition/Step 2's four-axis list, and its
    restatement of Step 7's own branch logic; keep the "a self-granted
    deferral is not a self-granted pass" sentence and the
    not-yet-shipped-or-merged sentence verbatim.
14. Evaluate deleting the `## Non-goals` section outright, per Step 2's
    own earning-test table ("a scope cut belongs in metadata only,
    never restated in the body"): the sidecar's decision log already
    carries this content as five `kind: elision` entries (issue #1583).
    Before deleting, read the sidecar's current decision log in full
    and confirm each of the three current Non-goals bullets maps to an
    existing entry there without creating a duplicate or contradicting
    record; if deleting, add one new decision-log entry recording the
    deletion itself (this section was previously removed by commit
    `14afb48` and re-added by `c8f96d7` with no log entry explaining
    either change -- do not repeat that omission).
15. Cut Output's own restated content (the metadata-choices bullet
    duplicating the Postcondition; a duplicated phrase inside the
    escalation-branch bullet).
16. Compress the Related skills table's own `evaluating-skill-quality`,
    `battle-testing-a-skill`, and `eliciting-a-design` rows -- wording
    only, keep the table's structure and every `relatedTo` entry it
    documents.
17. Cut the Steps table's own restated content (the "finitely many;
    stop once all are read" phrase, already stated in Step 4's own
    body).
18. Unify the Step 6 checker-command lines with
    `references/gitapex-cross-links.md`'s own copy of the same two
    commands -- keep the commands themselves in the body (Step 6 states
    plainly it runs them, and a reader must see them to run them
    without an extra hop), and edit `gitapex-cross-links.md` to point
    back at the body's own copy as the source of truth, rather than
    duplicating the exact flags independently.
19. Unify the Steps table's own "Done when" column with each Step's own
    inline "Completion criterion" sentence -- per issue #1619's own
    decision favoring the table/checklist shape, compress the inline
    sentence to a cross-reference to the table rather than restating
    it.
20. A wording-only pass over redundant possessive phrasing ("'s own",
    "its own") wherever a sentence reads identically without it -- no
    change to any sentence's meaning.
21. Compress Precondition's own wording where it restates Step 1/Step
    2 content available a few lines later, keeping every distinct fact
    (the three dispatch contexts, the context-1/context-2 input
    difference, the already-drafted-target routing rule) verbatim.

Proof method: after every edit, re-run
`uv run --frozen python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py --allowed-root . --strict-token-budget skills/drafting-a-skill`
and
`uv run --frozen python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py skills/drafting-a-skill`,
confirming every check other than `body-token-budget` stays PASS and the
token count decreases monotonically; confirm every
`evals/drafting-a-skill/tasks/*.yaml` fixture still matches (fixture
files themselves untouched); confirm no Stop-boundary bullet's own first
line changed (7 of 8 are fixture-pinned verbatim).

File ownership: sole task, no conflicts.
Interface dependencies: none (single task, single wave).
Wave: 1 (only wave).
Irreversibility: none of the planned ops are irreversible (prose edits
to a version-controlled file, revertible via `git revert`).

## Execution mode

Workflow tool not opted into for this session (no `ultracode` keyword,
no explicit multi-agent-orchestration request) -- executed via the
sequential main-thread fallback (this skill's own Notes section,
"Mixed" portability), one task, no wave/run boundary, no worktree
isolation.

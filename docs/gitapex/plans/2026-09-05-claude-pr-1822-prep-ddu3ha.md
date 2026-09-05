# Branch Plan: claude/pr-1822-prep-ddu3ha

Issue: https://github.com/tvna/gitapex/issues/1822
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `review-persona` can be dispatched to apply `drafting-a-skill`'s Step 3/4/5/7 critique without invoking the `Skill` tool | Add a fifth Sanctioned call site to `agents/review-persona.md`: triggered when `executing-a-branch-plan` Step 6 or `scorer-gated-skill-edits` Step 3/9 detects a `SKILL.md`/`references/**`-touching task; the dispatch prompt embeds `drafting-a-skill`'s Step 3/4/5/7 procedure text (or its file path) plus the proposed diff | Edit `agents/review-persona.md`'s "Sanctioned call sites" list, following the existing four entries' format and the file's own "propose adding it here first" rule | Live dispatch demonstration: `review-persona` invoked with `drafting-a-skill`'s Step 3/4/5/7 text embedded plus a sample `SKILL.md` diff, confirm findings return in `review-persona`'s existing output shape and no `Skill`-tool call is attempted | `review-persona`'s `Read`/`Grep`/`Glob`-only tool set has not been independently, live-verified against a real Agent-tool dispatch path (the file's own "Limits, disclosed rather than assumed away" section already discloses this gap) -- this row does not close it |
| `drafting-a-skill`'s own Precondition and Steps 3/4/5/7 name the working mechanism, not the unreachable one | Rewrite the Precondition's three dispatch-context descriptions and Steps 3, 4, 5, 7 (plus Stop boundary #1) to state the `review-persona`-dispatch mechanism explicitly; Steps 1, 2, 6 stay attributed to `branch-plan-task` (or an equivalent write/Bash-capable context) | Edit `skills/drafting-a-skill/SKILL.md`; this is itself a `SKILL.md` edit, so it requires this repository's own Skill Audit Evidence disclosure (the existing skill-audit-disclosure gate) in this issue's own PR | Re-run row 1's live demonstration against the corrected text; confirm the corrected Precondition now accurately describes a mechanism just proven to work | This edit is `drafting-a-skill` correcting its own Precondition -- row 1 must land first in the same branch so the freshly-established `review-persona` mechanism is what reviews this row's own edit, a same-branch task-ordering dependency `executing-a-branch-plan`'s own Step 3 wave sequencing must respect |
| `scorer-gated-skill-edits`'s own Step 3/Step 9 dispatch language matches the corrected mechanism | Apply the identical text fix to `skills/scorer-gated-skill-edits/SKILL.md`'s Step 3 ("authored by dispatching `drafting-a-skill`") and Step 9's pre-ship dispatch language | Edit `skills/scorer-gated-skill-edits/SKILL.md` Steps 3 and 9 | Read-through confirms internal consistency with `drafting-a-skill`'s corrected Precondition; no live `scorer-gated-skill-edits` trial run required for this issue | `scorer-gated-skill-edits` is a more complex caller (its own worktree-isolation Precondition); this row updates dispatch-mechanism prose only, not an end-to-end live trial of that skill |
| `executing-a-branch-plan`'s own routing reference names a concrete, working mechanism instead of an inert pointer | Update `decomposition-and-dispatch.md`'s "Skill-file edit routing" section to state the `review-persona`-dispatch mechanism concretely | Edit `skills/executing-a-branch-plan/references/decomposition-and-dispatch.md` | Re-run the #1794/#1795-style case (a `SKILL.md`-touching task) through the updated reference text; confirm it now names a mechanism that actually works, closing the gap issue #1796's stop-and-replan comment identified | None identified beyond rows 1-2's own |

## Task Decomposition

Four tasks, four distinct files -- no file-ownership conflicts. Interface
dependencies form a chain (2 -> 1, 3 -> 2, 4 -> 1), computed before wave
assignment per this skill's own Two dependency-edge types rule.

### Task 1: Add review-persona's fifth Sanctioned call site

Source ACM row: row 1.

Quoted Planned ops:
> Edit `agents/review-persona.md`'s "Sanctioned call sites" list,
> following the existing four entries' format and the file's own
> "propose adding it here first" rule

Concrete ops: add a fifth numbered entry to `agents/review-persona.md`'s
"Sanctioned call sites" section, matching the existing four entries'
format, describing the trigger (`executing-a-branch-plan` Step 6 or
`scorer-gated-skill-edits` Step 3/9 detecting a `SKILL.md`/`references/**`-
touching task) and what gets embedded in the dispatch prompt
(`drafting-a-skill`'s Step 3/4/5/7 procedure text or file path, plus the
proposed diff).

Skill-file edit routing: `agents/review-persona.md` is an agent
definition, not a `SKILL.md` -- `drafting-a-skill`'s own dispatch routing
does not apply to this task.

File ownership: sole owner of `agents/review-persona.md`, no conflicts.
Interface dependencies: none (first task in the chain).
Wave: 1.
Irreversibility: none (a documentation edit, reversible by further edit).

### Task 2: Rewrite drafting-a-skill's Precondition/Steps 3-4-5-7 to the working mechanism

Source ACM row: row 2.

Quoted Planned ops:
> Rewrite the Precondition's three dispatch-context descriptions and
> Steps 3, 4, 5, 7 (plus Stop boundary #1) to state the
> `review-persona`-dispatch mechanism explicitly; Steps 1, 2, 6 stay
> attributed to `branch-plan-task` (or an equivalent write/Bash-capable
> context)

Concrete ops: edit `skills/drafting-a-skill/SKILL.md` --
Precondition's three dispatch-context bullets, Steps 3/4/5/7, and Stop
boundary #1 -- to name `review-persona` (dispatched via `Agent`/`Task`,
never `Skill`) as the actual mechanism carrying out the Step 3/4/5/7
critique, while Steps 1/2/6 stay described as `branch-plan-task`'s own
direct work.

Skill-file edit routing: this task edits `skills/drafting-a-skill/SKILL.md`
itself -- a `SKILL.md` edit. The ordinary routing rule ("every `SKILL.md`
edit goes through `drafting-a-skill`") does not apply reflexively to
`drafting-a-skill` editing its own body: per this row's own Planned ops
and residual-risk column, Steps 1/2/6 (which this edit falls under) stay
attributed to `branch-plan-task` directly -- this is the same
self-reference this issue exists to fix, and the ACM itself already
resolves it this way rather than leaving it for this task to invent.
This edit itself requires this repository's own Skill Audit Evidence
disclosure in the PR body (`drafting-a-skill`'s own Step 7
handoff -- `evaluating-skill-quality` and `battle-testing-a-skill` --
dispatched fresh against the edited content before this task reports
complete).

File ownership: sole owner of `skills/drafting-a-skill/SKILL.md`, no
conflicts.
Interface dependencies: depends on Task 1 (the fifth Sanctioned call site
must exist and be live-demonstrated before this task's own text can
accurately describe it as a working mechanism).
Wave: 2.
Irreversibility: none (a documentation edit, reversible by further edit).

### Task 3: Apply the identical text fix to scorer-gated-skill-edits Steps 3/9

Source ACM row: row 3.

Quoted Planned ops:
> Apply the identical text fix to
> `skills/scorer-gated-skill-edits/SKILL.md`'s Step 3 ("authored by
> dispatching `drafting-a-skill`") and Step 9's pre-ship dispatch
> language

Concrete ops: edit `skills/scorer-gated-skill-edits/SKILL.md` Steps 3 and
9 so their `drafting-a-skill`-dispatch language matches Task 2's
corrected mechanism description.

Skill-file edit routing: this task edits
`skills/scorer-gated-skill-edits/SKILL.md`, a `SKILL.md` edit -- routes
through `drafting-a-skill`'s own procedure (now, post-Task-2, a working
mechanism): Steps 1/2/6 executed directly by `branch-plan-task`, Steps
3/4/5/7 dispatched to `review-persona` per Task 2's corrected Precondition
and the fifth Sanctioned call site Task 1 added. This edit also requires
Skill Audit Evidence disclosure in the PR body.

File ownership: sole owner of `skills/scorer-gated-skill-edits/SKILL.md`,
no conflicts.
Interface dependencies: depends on Task 2 (this task's own proof method
is internal-consistency against Task 2's corrected Precondition text, and
this task exercises the mechanism Task 2 just established).
Wave: 3.
Irreversibility: none (a documentation edit, reversible by further edit).

### Task 4: Name the review-persona-dispatch mechanism in the Skill-file edit routing reference

Source ACM row: row 4.

Quoted Planned ops:
> Update `decomposition-and-dispatch.md`'s "Skill-file edit routing"
> section to state the `review-persona`-dispatch mechanism concretely

Concrete ops: edit
`skills/executing-a-branch-plan/references/decomposition-and-dispatch.md`'s
"Skill-file edit routing" section to name the actual mechanism (Steps
1/2/6 direct by `branch-plan-task`, Steps 3/4/5/7 dispatched to
`review-persona` per its fifth Sanctioned call site) instead of the
current inert "routes to `drafting-a-skill`" pointer.

Skill-file edit routing: `decomposition-and-dispatch.md` is a
`references/` file, not a `SKILL.md` itself -- `drafting-a-skill`'s own
dispatch routing does not apply to this task.

File ownership: sole owner of
`skills/executing-a-branch-plan/references/decomposition-and-dispatch.md`,
no conflicts.
Interface dependencies: depends on Task 1 (names the same mechanism Task
1 established); no edge with Task 2 or Task 3 -- disjoint file, and this
row's own Planned ops do not reference either task's own text.
Wave: 3 (co-assignable with Task 3 -- no file or interface edge between
them).
Irreversibility: none (a documentation edit, reversible by further edit).

## Waves

- Wave 1: {Task 1}
- Wave 2: {Task 2} (depends on Task 1)
- Wave 3: {Task 3, Task 4} (Task 3 depends on Task 2; Task 4 depends on
  Task 1 only; no edge between Task 3 and Task 4)

## Execution mode

Workflow tool not opted into for this session (no `ultracode` keyword, no
explicit multi-agent-orchestration request) -- executed via the sequential
main-thread fallback (Notes section, "Mixed" portability): one task per
turn, `Agent` tool dispatch with explicit `subagent_type` per task
(`branch-plan-task` for Steps 1/2/6-shaped work, `review-persona` for the
Step 3/4/5/7-shaped critique once Task 1 lands), same commit-per-task
discipline, same event-log writes, no `Workflow`-tool worktree isolation.

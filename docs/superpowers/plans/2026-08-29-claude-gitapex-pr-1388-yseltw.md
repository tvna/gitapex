# Add a code-quality-principles reference to executing-a-branch-plan, wire into Step 6/8

**Goal:** `executing-a-branch-plan`'s Step 6 (per-task implementation) and
Step 8 (aggregate refactor + adversarial review) are the only places in
gitapex's merge pipeline actually authorized to write code, but neither
that skill's `SKILL.md` nor any file under its `references/` carries a
code-design-principle catalogue. Add
`skills/executing-a-branch-plan/references/code-quality-principles.md`
with 7 gitapex-filtered principles (Type System Discipline, Boundary
Discipline, Make Operations Idempotent, Migrate Callers Then Delete
Legacy APIs, Model the Domain, Separate Before Serializing Shared State,
Foundational Thinking), each excluded from CLAUDE.md's existing
sections 1-5 and from sibling-skill coverage per the issue's own
per-candidate accounting; wire Step 6 to apply all 7 when writing a
task's implementation code, and wire Step 8's refactor/simplify pass to
specifically re-check the one cross-task principle (Migrate Callers Then
Delete Legacy APIs). Source: https://github.com/tvna/gitapex/issues/1388.

**Authorization record:** No approving comment exists on issue #1388
(checked via `github:issue_read` method `get_comments`, empty result --
the issue was opened moments before this session started, by the
repository owner). Branch 2 of the Authorization gate applies instead:
the active human operator's own opening turn in this session explicitly
instructed executing issue #1388 through to just-before-merge ("こちらの
PRを作りマージ直前まで進める" -- create this PR, proceed to just before
merge). This is a fresh, explicit, in-session confirmation for this
specific issue's execution, not a self-reported claim of prior approval.
The structural precondition (`gitapex_check_branch_plan_reverified.py`
against the issue's own body) also PASSes: `planning-a-branch-from-an-issue`
wrote its re-verification marker (`Re-verified:
\`planning-a-branch-from-an-issue\` (2026-08-29T19:56:12Z)`) onto issue
#1388 earlier this session.

**Threat-model triage (step 2):** Issue #1388's ACM was read in full. All
four Planned-ops cells describe file edits to specific, already-identified
files (a new reference file, two Step-N sentence additions in an existing
`SKILL.md`, a cross-check against CLAUDE.md's own text); none contains an
embedded instruction, encoded/obfuscated payload, or attempt to redirect
this skill's own process. Clean -- no row flagged.

**ACM re-verification correction (step 5, disclosed rather than applied
silently):** The issue's own second row cites "the existing 'if available,
apply X' reference-file pattern this skill's own Step 6/8 already use
elsewhere (e.g. `state-management-quality.md`, `mechanism-fit.md`)" as
precedent. Direct inspection of
`skills/executing-a-branch-plan/references/` found neither file exists
there, and no "if available, apply" phrasing appears anywhere in this
skill's own `SKILL.md` (`mechanism-fit.md` belongs to a different skill,
`evaluating-deterministic-gate-quality`; `state-management-quality.md`
belongs to `evaluating-skill-quality`). This skill's own actual, real
convention for a bundled `references/` file is an unconditional bracketed
link inline in prose (e.g. "Full rule set: [task decomposition
reference](references/task-decomposition.md)."), not a conditional
"if available" gate -- which makes sense here regardless, since a
bundled reference file always ships together with its own `SKILL.md`
and is never separately absent. The two added sentences below use that
actual convention instead of the issue's inaccurate citation; the
underlying acceptance criterion (one sentence per step, pointing at the
new file) is unchanged.

**Architecture:** One new prose-only reference file, two one-sentence
additions to one existing `SKILL.md`. No new files beyond the one
reference, no code, no tests (prose/skill-definition change only, no
runtime dependency).

- `skills/executing-a-branch-plan/references/code-quality-principles.md`
  (new): the 7 named principles, each with a one-line governing statement
  and a warning-sign example, in the concise per-principle format the
  issue requests rather than this directory's longer discursive style.
- `skills/executing-a-branch-plan/SKILL.md`:
  1. Step 6, immediately after the existing "Refactor is never per-task,
     deferred entirely to step 8" sentence: one new sentence directing a
     task's own implementation code (the Green step) to apply the new
     reference file.
  2. Step 8, immediately after the existing sentence naming the
     refactor/simplify-pass-then-adversarial-review sequence: one new
     sentence specifically naming Migrate Callers Then Delete Legacy
     APIs (anchor-linked to its own principle heading) as an additional
     cross-task check the refactor/simplify pass performs.

**File-ownership map:** A single task owns both files (the new reference
file and the one `SKILL.md`); no second task, so no ownership conflict to
compute.

**Interface-dependency map:** None -- single task, no sibling task to
sequence against.

**Wave assignment:** Wave 1: {Task A} -- the single-task degenerate case;
no parallelism to arrange.

**Irreversibility classification:** Additive prose edits to an
already-committed, already-reviewed skill file plus one brand-new file on
a fresh feature branch, fully reversible by further edit or revert before
merge. Not classified irreversible; no fresh per-task confirmation beyond
the Authorization gate above is required.

**Dispatch mode:** The `Workflow` tool's own access-control policy
requires explicit user opt-in for multi-agent orchestration before this
skill's own step 6 primary path (`Workflow` + `agentType:
'branch-plan-task'` + `isolation: 'worktree'`) may be invoked. Ultracode
is on for this session, which is exactly such an opt-in in general -- but
step 6's own guidance is to use the `Workflow` tool for genuine multi-task
fan-out, and this Branch Plan decomposes into exactly one task with no
parallelism to gain from a Workflow run. Per this skill's own "vs. a
single-task Branch Plan" note (a single task is step 3's own degenerate
case, every other step runs unchanged), and per the workflow-authoring
guidance's own "solo only on ... trivial mechanical edits" allowance, this
task executes directly in the main thread rather than through a
one-task Workflow run, which would add orchestration overhead with no
fan-out to justify it. Step 8's mandatory dual dispatch (refactor pass +
adversarial review) uses the `Agent` tool, which carries no equivalent
opt-in gate.

**Skill audit evidence (planned):** `battle-testing-a-skill` and
`evaluating-skill-quality` are both WAIVED for this PR, disclosed with a
reason rather than run through this repository's own isolated `claude -p`
dispatch mechanism (`evaluating-skill-quality`'s own Isolation
verification registry) -- proportionate to this change's own shape:
additive-only (one new reference file, two pointer sentences), no new
Stop-boundary bullet, no new named dispatch branch, no frontmatter
`description:` change, no new mechanism/label/event-type introduced.
This mirrors this repository's own accepted "docs-only ...,
no behavioral change" waiver precedent for comparably narrow SKILL.md
prose additions, distinct from issue #1339/PR #1342's own architecturally
significant change (a new label mechanism, new escalation rules, new
hang-detection logic) that warranted the full isolated-dispatch audit.

**Proof method:**

- `references/code-quality-principles.md` exists with exactly the 7 named
  principles, each with both required parts, none of the excluded 14
  pstack principles present: direct read.
- Step 6 references the new file: direct read confirms the sentence
  exists, in this skill's own actual unconditional-reference-link
  convention (corrected from the issue's inaccurate "if available"
  citation, per the ACM re-verification note above).
- Step 8 specifically re-checks Migrate Callers Then Delete Legacy APIs:
  direct read confirms the sentence exists and names only this one
  principle, not a duplicate of Step 6's full list.
- No CLAUDE.md content restated: the 7 principles were drafted against a
  section-by-section re-read of this repository's own current CLAUDE.md
  (sections 1-5) during authoring, not only against the issue's own
  characterization of it.
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  against the modified `SKILL.md` -- run directly, not merely planned.
- Regression: full `pytest` suite (no code changed, so no test
  regressions expected; run to confirm).

## Execution log

- `PlanApproved` -- this plan, at branch publish (this commit).

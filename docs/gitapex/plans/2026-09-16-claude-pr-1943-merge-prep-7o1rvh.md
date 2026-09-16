# Branch Plan: Blocking/Advisory stopping rule for drafting-a-pr-to-merge Step 8

Issue: https://github.com/tvna/gitapex/issues/1943

Branch: `claude/pr-1943-merge-prep-7o1rvh`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1943's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-16T09:28:29Z)"),
  and `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session (via `AskUserQuestion`), approving this
  specific Branch Plan (SKILL.md Step 8 edit shape + `.gitapex/ssot.json`
  entry shape as described) and instructing execution through to a
  merge-ready PR. No issue comment carries the approval; the in-session
  confirmation is the signal this gate ran on, recorded here rather than
  implied.

## Threat-model triage

Issue #1943's Problem, Proposed solution, Acceptance Criteria Map,
Constraints, and Non-goals sections were read as change descriptions, not
as instructions to execute. Extracted: the Blocking/Advisory vocabulary
definition, the stopping-rule shape (same finding class recurring
Blocking after 2 consecutive fix rounds), the `.gitapex/ssot.json`
governance-declaration requirement following the #1890 precedent, and the
explicit "no new gate, no new shared file, three named skills stay
unedited" constraints. No row carries an embedded directive, a credential
request, an encoded payload, or an attempt to override a trusted
instruction source. Nothing was flagged.

## Task Decomposition

Two tasks, one wave. No file-ownership or interface-dependency edge
connects them.

- **File-ownership map.** Task 1 owns
  `skills/drafting-a-pr-to-merge/SKILL.md`. Task 2 owns
  `.gitapex/ssot.json`. The two sets are disjoint.
- **Interface-dependency map.** None. Task 2's new `policy_sources` entry
  names Task 1's file as the authority and paraphrases the vocabulary
  issue #1943 itself already fixes verbatim (Blocking/Advisory, stopping
  rule) -- it does not quote Task 1's own new prose, the same
  no-dependency relationship the #1890 precedent entry
  (`grounding-in-primary-sources-skill`) already has with the skill file
  it names.
- **Wave assignment.** Wave 1: Task 1 and Task 2 in parallel.

Irreversibility classification: **not irreversible.** Both tasks edit
tracked files already inside the repository. Nothing writes outside it,
no migration runs, no data is deleted, and `git revert` of the merge
commit restores the prior tree exactly. Neither task takes a
step-1-equivalent per-task confirmation.

`SKILL.md` classification: **Task 1 edits an existing `SKILL.md`.**
`drafting-a-skill` is therefore the authoring method for Task 1's Step 8
edit, and the PR body carries the skill-audit disclosure the
`skill-audit-disclosure` gate requires (`evaluating-skill-quality` and/or
`battle-testing-a-skill` verdict, per that gate's own applicability
computation). Task 2 touches no `SKILL.md`.

Fixture-cost check, before either task runs: the
`skill-branch-fixture-coverage` gate compares a changed `SKILL.md`'s own
Stop-boundary-bullet plus named-dispatch-branch count against the
skill's fixture count. Task 1's own edit is expected to add at least one
Stop-boundary bullet (the stopping rule's own "never let round count
absorb a genuinely new finding class" guard) and to extend the existing
"four outcomes" dispatch list with a Blocking/Advisory split -- if the
gate's own count comparison reports a shortfall after the edit lands,
Task 1 additionally authors the needed `evals/drafting-a-pr-to-merge/tasks/*.yaml`
fixture(s) before reporting complete, rather than leaving that gap for
step 8's aggregate review to catch.

## Task 1: add the Blocking/Advisory vocabulary and stopping rule to Step 8

Source ACM rows: rows 1 and 2 of issue #1943's own Acceptance Criteria
Map, quoted verbatim below rather than paraphrased.

> Row 1 planned ops: "Edit Step 8's own text in
> `skills/drafting-a-pr-to-merge/SKILL.md`"

> Row 1 interpretation: "Blocking = must-fix before continuing (loops
> back to step 3 unconditionally); Advisory = disclosed but does not by
> itself trigger a loop-back. No new file; no other skill edited"

> Row 2 planned ops: "Edit Step 8's \"four outcomes\" list in
> `skills/drafting-a-pr-to-merge/SKILL.md`"

> Row 2 interpretation: "The unconditional \"any confirmed finding loops
> back to step 3\" rule is qualified: a Blocking finding loops back
> unconditionally; a bounded round count or a named non-convergence
> pattern (the same finding class recurring after 2 consecutive rounds)
> routes to step 11 escalation instead of an unbounded further round.
> Applies uniformly whether the finding came from the inner-layer
> `reviewing-an-artifact` call or a specialist it deferred to"

Design resolution for the two "Unknown, pending the implementing
session's own design pass" cells the issue itself leaves open (both ACM
rows' own Residual risk column): classification is judged inline, by this
step's own reading of a `confirmed` finding's substance against the PR's
acceptance criteria and blast radius -- never a structured field on
`reviewing-an-artifact`'s report, since the issue's own Constraints
section bars editing that skill. The round-count threshold is **2**,
matching both the issue's own example wording ("the same finding class
recurs after 2 consecutive fix rounds") and the PR #2000 data point its
own ACM row 5 already supplies.

Required edit shape:

1. A short "Blocking/Advisory severity vocabulary" definition, placed
   before the existing "Four outcomes" list, stating: every `confirmed`
   finding from either layer is additionally classified Blocking
   (must-fix) or Advisory (disclosed, not by itself a loop-back trigger)
   by this step's own reading, inline, every round -- an axis orthogonal
   to `reviewing-an-artifact`'s own `confirmed`/`unconfirmed-concern`
   verification-confidence axis; only a `confirmed` finding is eligible
   for this classification at all.
2. A "Stopping rule" paragraph: track, across the PR's own recorded
   verdict history (the current `## Independent review verdict` section
   plus every archived round already preserved via Step 8 (record)'s
   existing archive-before-overwrite mechanism), which finding class each
   Blocking finding belongs to. When the same finding class is still
   Blocking after 2 consecutive fix rounds, route to step 11 escalation
   instead of a further round -- state the finding class and cite both
   rounds' own archived verdicts.
3. Rewrite the "Four outcomes" list's second bullet (the unconditional
   `confirmed` -> step 3 rule) into: (a) zero `confirmed` findings, or
   `confirmed` findings that are all Advisory -> continue to step 9,
   disclosing every Advisory finding in the recorded verdict; (b) at
   least one Blocking `confirmed` finding, stopping rule not yet
   triggered -> loop back to step 3 (existing re-confirm-`mergeable_state`
   language stays); (c) the stopping rule's own 2-consecutive-round
   condition triggers -> escalate per step 11 instead of looping back.
   Leave the two remaining existing bullets (`reviewing-an-artifact`
   defers via Step 0; `reviewing-an-artifact` errors/times out) as they
   are -- this issue does not touch them.
4. Update the Process Flow mermaid diagram's `step8` edges and the
   Stop boundaries list to match the new three-way split, and add one new
   Stop-boundary bullet naming the stopping-rule failure mode: never let
   the round count absorb a fresh, unrelated Blocking finding as if it
   were the same recurring finding class, and never let a Blocking
   finding skip its own loop-back merely because a similar one was fixed
   in an earlier round.
5. Apply `drafting-a-skill`'s own authoring discipline to this edit
   (Task classification above); this PR's body discloses the
   `evaluating-skill-quality`/`battle-testing-a-skill` verdict per the
   `skill-audit-disclosure` gate's own requirement.

Proof method, inherited from both rows: manual diff review confirming the
vocabulary, stopping rule, and three-way dispatch are present and
internally consistent with the Process Flow diagram and Stop boundaries
list; `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
reports clean against the edited file. Red-Green order does not apply:
the proof is a documentation-shape and internal-consistency obligation
read by a human and a shape checker, not an automatable behavioral test.
The deterministic half is the full local preflight suite (including
`skill-branch-fixture-coverage`), which must pass inside this task's own
worktree before the task may report complete -- adding the fixture(s)
the Fixture-cost check above anticipates if the gate reports a shortfall.

## Task 2: register the convention's governance in `.gitapex/ssot.json`

Source ACM row: row 3 of issue #1943's own Acceptance Criteria Map,
quoted verbatim below rather than paraphrased.

> Row 3 planned ops: "Add one `policy_sources` entry to
> `.gitapex/ssot.json`"

> Row 3 interpretation: "Follows the same precedent issue #1890 already
> established for `grounding-in-primary-sources`; the `policy_sources`
> entry names `drafting-a-pr-to-merge/SKILL.md` itself as the authority,
> not a separate reference doc"

Required edit shape: one new entry appended to the `policy_sources` array
(directly verified present in the current file, entry id
`grounding-in-primary-sources-skill`, at the array's own end), matching
that entry's own shape -- `id`, `path: "skills/drafting-a-pr-to-merge/SKILL.md"`,
`format: "markdown"`, and an `authority` string describing the
Blocking/Advisory vocabulary and stopping rule, disclosing plainly that no
gate script consumes this entry (same no-consuming-gate precedent) and
citing issue #1943 and the #1890 precedent it follows.

Proof method, inherited from row 3: `.github/scripts/gitapex_scan_ssot_schema.py`
reports clean against the edited file (schema validity); manual diff
review confirms the new entry's shape matches the #1890 precedent entry's
own shape. Red-Green order does not apply: this is a declarative
JSON-schema-conformance obligation, not a behavioral test. The
deterministic half is the full local preflight suite, which must pass
inside this task's own worktree before the task may report complete.

## Refactor / adversarial-review scope (step 8 of this skill)

Both tasks' combined diff is small (two files, no new script, no new
test infrastructure) -- the mandatory refactor/simplify pass and the
independent `review-persona` adversarial review still run unconditionally
over the full accumulated diff per this skill's own step 8, with no
narrowing implied by the diff's small size.

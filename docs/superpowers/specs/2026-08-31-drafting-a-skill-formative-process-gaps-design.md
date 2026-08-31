# Closing formative-process gaps in drafting-a-skill

Date: 2026-08-31

Tracking issue: https://github.com/tvna/gitapex/issues/1630 (filed after
this design was drafted and reviewed in-session, per this repository's
own commit-citation convention -- normally an issue precedes a design;
here the design elicitation came first and the issue was filed once the
design converged, quoting this doc's own Scope/Design/Non-goals
verbatim into its Acceptance Criteria Map).

## Context

`evaluating-skill-quality` grades only a finished, static artifact (its
own `SKILL.md`: "a gate on a finished, static artifact"). It never sees
how the artifact was produced. `drafting-a-skill` is the one skill whose
Steps run *before* that gate, so any rubric dimension a drafter cannot
reliably satisfy from `drafting-a-skill`'s own process guidance is a
dimension that surfaces only downstream, at `evaluating-skill-quality`'s
Step 7 review -- too late to have shaped the draft.

The repository owner raised this first against Dimension 4 (Clarity and
structure): `references/formative-quality-dimensions.md` row 4
("Structural legibility") maps to Dimension 4 but only instructs the SDO
test, Step-numbering discipline, and completion-criteria wording --
leaving Dimension 4's other requirements (consistent terminology,
workflows written as ordered/copyable checklists rather than prose,
feedback loops on quality-critical steps, templates matched to
strictness, distinct/complete branch triggers) with no writing-time
instruction anywhere in `drafting-a-skill`. `drafting-a-skill`'s own
Worked example section demonstrates the gap directly: three candidate
walkthroughs, each written as one long prose paragraph ("Step 1: ...;
Step 2: ...; Step 3: ...") rather than a Step-keyed list.

A full pass over `evaluating-skill-quality/references/rubric.md` (2419
lines, all nine numbered dimensions plus the Agentic-operation-
mechanism-fit sub-checks, Portability level, Compatibility awareness,
Confidentiality awareness, Capability assumption, Dependency policy,
Lifecycle, and Execution requirements) cross-referenced against
`formative-quality-dimensions.md`'s nine rows found the same
shallow-mapping pattern recurring in four more rows, plus one outright
label mismatch:

- **Row 5** (-> Dimension 5, Progressive disclosure) states only the
  load-bearing/on-demand split; it omits Dimension 5's reference-naming
  convention and its requirement that a link state *what context
  requires the read and what the reader will obtain*, not merely "see
  reference."
- **Row 6** (-> Dimension 6, Durability) covers only stale claims and
  bare issue numbers; it omits forward-slash-only paths, fully-qualified
  `Server:tool` naming, no-install-assumed phrasing, "default with an
  escape hatch" framing, and the Portable-declaration rules against
  hardcoding this repository's own convention or citing an
  authority-bearing path outside the skill's own folder.
- **Row 7** (-> Dimension 7, Bundled scripts) covers only the
  should-this-be-a-script judgment; it omits every quality bar for a
  script that *is* bundled (error handling, no unexplained constants,
  Interface-vs-Implementation comment discipline, single ownership).
- **Row 8** is labelled "Dimension 8, Behavioural evidence" but its
  actual instruction ("include a worked example") is Dimension 4/8's
  concrete-example concern, not Dimension 8's real content: an
  eval-driven baseline (run the candidate task without the skill first,
  document the gaps, pass >= 3 scenarios including the guardrail case).
  No row anywhere instructs preparing that baseline during drafting.

Separately, tracing which skill owns "editing an existing `SKILL.md`"
across the pipeline surfaced a third, structural gap: `drafting-a-skill`
is scoped to "authors from a blank page ... does not loop" once a first
draft exists, and `scorer-gated-skill-edits` requires a checkable scorer
and a held-out split as a hard precondition (its own Precondition gate:
"If either the scorer or the split is missing, STOP"). Grepping every
skill in the repository for "existing SKILL.md" / "editing an existing
skill" surfaces only these two skills naming that territory at all.
Between them sits an unowned case: an ordinary, non-eval-driven edit to
an existing skill (a feature addition, a removal, a refactor) that
`executing-a-branch-plan`'s own `task-decomposition.md` does not route
anywhere in particular -- it falls through as an undifferentiated
code-editing task, with none of `drafting-a-skill`'s shape-checker or
formative-dimensions discipline applied. This design's own change set is
itself an instance of that unowned case, which is why closing it is
folded into this same design rather than deferred.

This is a documentation-and-process-guidance change only: no runtime
behavior of any shipped script changes, and `evaluating-skill-quality`'s
own rubric is left untouched -- the rubric's Dimension-4/5/6/7/8
requirements are correct; what is missing is the writing-time guidance
that lets a draft satisfy them the first time.

## Scope

- `skills/drafting-a-skill/references/formative-quality-dimensions.md`
  -- rows 4, 5, 6, and 7 extended to name every requirement their mapped
  rubric dimension states; row 8 rewritten from a mislabeled
  concrete-example instruction into an eval-preparation instruction
  matching Dimension 8's real content (scenario enumeration and an
  `evals/` scaffold), with the concrete-example instruction it
  displaces folded into row 4 instead (its true home, per the rubric's
  own Dimension 4 "Concrete examples over abstract description"
  bullet).
- `skills/drafting-a-skill/SKILL.md`:
  - Step 2 gains an explicit style rule: a long, ordered, skippable-
    but-risky procedure is written as a numbered/copyable checklist,
    not a prose paragraph -- matching Dimension 4's "Workflows as
    ordered steps" bullet.
  - The Worked example section is restructured from three prose
    paragraphs into per-candidate, Step-keyed bullet lists, so the
    section models the same structure Step 2 now asks for rather than
    contradicting it.
  - A new Step (or an extension of Step 6) instructs scaffolding an
    `evals/<skill>/` scenario list (>= 3 scenarios, including the
    guardrail/failure case the skill exists to prevent) and an
    `evals.json`-shaped fixture skeleton -- preparation only. Actually
    running the before/after comparison stays out of scope, explicitly
    deferred to `scorer-gated-skill-edits` or a later
    `evaluating-skill-quality` pass, consistent with
    `drafting-a-skill`'s existing Postcondition ("not a shipped or
    merged skill on its own authority").
- `skills/executing-a-branch-plan/references/task-decomposition.md` (or
  `SKILL.md` Step 3, whichever the implementing task judges the better
  fit): a new rule that a task whose Planned ops edit an *existing*
  `SKILL.md` (not creating a new skill directory, and not already
  routed to `scorer-gated-skill-edits` by a stated eval precondition)
  must still run `gitapex_check_skill_shape.py` and sweep the edited
  sections against `formative-quality-dimensions.md` before the task
  reports complete -- the minimum floor `drafting-a-skill` already
  guarantees a new skill, extended to an edited one.

## Non-goals

- No change to `evaluating-skill-quality/references/rubric.md` or any
  of its bundled scripts -- the grading side is correct; only the
  writing-time (drafting) side is being brought up to match it.
- No new eval-execution infrastructure (no change to
  `evals/scripts/gitapex_run_eval_suite.py` or
  `scorer-gated-skill-edits`'s own procedure). `drafting-a-skill`'s new
  eval-scaffolding step produces scenario fixtures and a skeleton file
  only; it does not run a before/after comparison.
- No new standalone skill for "ordinary existing-skill edits." The
  `executing-a-branch-plan` change adds a minimum process floor to the
  existing undifferentiated code-editing path rather than carving out a
  new skill or a new pipeline stage.
- No change to `scorer-gated-skill-edits`'s own Precondition gate or
  procedure.

## Design

### formative-quality-dimensions.md row changes

Each row keeps its existing table shape (`# | Formative dimension |
Writing-time instruction | Example pair | Gate-side cross-reference`);
only the "Writing-time instruction" and "Example pair" cells for rows 4
-- 8 are rewritten. Row count and dimension numbering (1-9) are
unchanged, preserving every existing cross-reference from `SKILL.md` and
from `evaluating-skill-quality`'s own citations into this file.

- **Row 4 (Structural legibility).** Keep the existing SDO/Step-
  numbering/completion-criteria content; add: one term per concept
  throughout the draft and its `references/` (no silent synonym drift);
  a long or skippable-but-risky procedure written as a numbered,
  copyable checklist rather than a prose paragraph; a validate -> fix
  -> repeat loop named explicitly on any step where errors are likely
  and costly; a template's strictness stated (exact contract vs.
  sensible-default-adapt); every procedure branch enumerated with one
  distinct, non-overlapping trigger each, reusing Step 3's own cohesion
  enumeration rather than re-deriving it (mirrors the rubric's own
  "never both" cross-reference between its cohesion check and Dimension
  4).
- **Row 5 (Load-bearing vs. on-demand split).** Keep the existing
  body/reference split content; add: name each `references/` file for
  its content, not a generic label; state, at each link, what context
  requires the read and what the reader obtains, not a bare "see
  reference."
- **Row 6 (Stability of claims).** Keep the existing stale-claim/bare-
  issue-number content; add: forward slashes only in every path; MCP
  tools cited fully qualified as `Server:tool`; no assumption a tool or
  package is pre-installed without saying so; a default paired with a
  named escape hatch rather than a menu of options; for Portable-
  declared content, no hardcoded repository-specific convention
  asserted as universal (state it as an illustrative default with a
  named fallback) and no authority-bearing citation to a path outside
  the skill's own folder.
- **Row 7 (Script necessity and minimalism).** Keep the existing
  should-this-be-a-script judgment; add, for a script that is bundled:
  handle its own error conditions rather than throwing for the model to
  catch; justify every configuration constant inline; state execution
  intent (run it vs. read it as reference) and key comment style to
  that choice (Interface documentation for an execute-only script,
  Implementation detail for a read-as-reference one); when the script
  is reachable from more than one skill, exactly one skill owns it and
  every other consumer declares the dependency.
- **Row 8 (rewritten; stays mapped to Dimension 8, Behavioural
  evidence).** New instruction: before considering the draft done,
  enumerate at least three concrete scenarios the finished skill must
  handle, including the guardrail/failure case it exists to prevent,
  and scaffold them as an `evals/<skill>/` fixture skeleton (task
  prompts plus an `evals.json`-shaped structure) -- preparation for a
  future before/after run, not the run itself. New example pair
  contrasting a scaffolded three-scenario skeleton against a draft with
  no fixtures at all. The concrete-example-coverage instruction this
  row previously carried moves into row 4's own "concrete examples"
  guidance instead (Dimension 4 explicitly lists "concrete examples
  over abstract description" as one of its own checks, which is where
  that instruction actually belongs).

### drafting-a-skill/SKILL.md changes

- Step 2 gains one new bullet, adjacent to the existing Design-by-
  Contract structural guidance: procedural content is written as a
  numbered list or checklist whenever the sequence is long or a
  skipped step is risky; prose stays reserved for genuinely open-ended
  judgment calls. This is a drafting-style rule, not a new earned-
  section category, so it does not change what counts as Precondition/
  Postcondition/Non-goals per Step 2's existing "earned" test.
  Cross-references `references/formative-quality-dimensions.md` row 4
  rather than restating it, per this repository's own "never both"
  duplication rule.
- The Worked example section's three candidates are each rewritten from
  one prose paragraph into a short Step-keyed bullet list (Step 1: ...,
  Step 2: ..., ...), preserving every fact currently stated -- no
  candidate's content changes, only its layout.
- A new sub-step under Step 6 (post-formative-sweep, pre-checker-run,
  since the scaffold is itself part of "the draft" the checkers then
  validate): enumerate >= 3 scenarios per the new row 8 instruction and
  write the `evals/<skill>/` skeleton. This is a drafting output, not a
  gate: Step 6's existing "both checkers exit clean" completion
  criterion is unchanged, and this new sub-step's own completion
  criterion is "the scenario list and skeleton file exist," not "a
  before/after score was produced" (that stays out of scope, per
  Non-goals).

### executing-a-branch-plan process-floor addition

`task-decomposition.md` (or `SKILL.md` Step 3) gains a rule alongside
the existing "planned ops create a new skill directory -> apply
drafting-a-skill" sentence: a task whose planned ops *edit* an existing
`SKILL.md`, and that is not otherwise routed to `scorer-gated-skill-
edits` by a stated scorer/held-out-split precondition, must run
`gitapex_check_skill_shape.py` against the edited skill directory and
sweep every section it touched against
`formative-quality-dimensions.md` before that task reports complete.
This is a minimum floor, not a re-entry into `drafting-a-skill`'s full
Design-by-Contract procedure (Step 1's ACM-quoting precondition, Step
3's cohesion self-check, and Step 7's mandatory dual dispatch stay
specific to first-draft authoring) -- an edit task gets the
deterministic shape check and the same formative-dimensions sweep a
first draft gets, nothing more and nothing this design newly invents
for the edit case beyond that floor.

## Verification

No runtime script changes ship with this design; verification is
structural and citation-level, matching the posture of prior
`formative-quality-dimensions.md`/`SKILL.md` edits in this repository:

- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  and `python3
  skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
  run clean against `skills/drafting-a-skill/` after the edit (per
  `drafting-a-skill`'s own Step 6, applied reflexively to itself).
- Every row 4-8 addition in `formative-quality-dimensions.md` is
  checked against its cited rubric dimension's own Fail/Pass bullets in
  `evaluating-skill-quality/references/rubric.md` to confirm no
  requirement is left unmapped.
- The rewritten Worked example section is diffed fact-for-fact against
  its prior prose form to confirm no candidate's content changed, only
  its layout.
- `formative-quality-dimensions.md`'s own numbering (1-9) and its
  "share numbering and a name on purpose" cross-reference to
  `evaluating-skill-quality`'s nine dimensions stays intact after the
  row-8 rewrite -- row 8 still maps to Dimension 8, only its
  instruction content changes.
- The `executing-a-branch-plan` addition is checked against
  `task-decomposition.md`'s existing row-to-task mapping rules for
  placement consistency, and against `drafting-a-skill`'s own Related
  skills section (the `scorer-gated-skill-edits` boundary) to confirm
  the new floor does not silently duplicate or contradict that
  skill's own Precondition gate.
- GitHub post text (issue/PR bodies) stays ASCII, per this repository's
  own outward-artifact convention; the design doc and skill files
  themselves follow the existing gitapex convention (which already uses
  non-ASCII punctuation in places), unaffected by that outward-post-only
  gate.

## Assumptions

- Fact: `evaluating-skill-quality/references/rubric.md`'s Dimension 4
  (Clarity and structure), 5 (Progressive disclosure), 6 (Durability),
  7 (Bundled scripts), and 8 (Behavioural evidence) sections were read
  in full this session (lines 1582-2258 of the 2419-line file) and each
  Fail/Pass bullet catalogued against the current text of
  `formative-quality-dimensions.md`'s corresponding row.
- Fact: `drafting-a-skill/SKILL.md`'s current Worked example section
  (lines 282-317) is three prose paragraphs, confirmed by direct read
  this session.
- Fact: grepping the full `skills/` tree for `existing SKILL\.md|editing
  an existing skill|existing skill|writing-skills` (case-sensitive)
  returns only `scorer-gated-skill-edits/SKILL.md`,
  `drafting-a-skill`'s own files (which name the boundary in prose),
  `evaluating-skill-quality`'s shape-drift scanner/schema, and
  `eliciting-a-design`/`battle-testing-a-skill` incidental mentions --
  no skill besides `scorer-gated-skill-edits` claims ownership of
  editing an existing `SKILL.md`, confirmed this session.
- Fact: `scorer-gated-skill-edits/SKILL.md`'s Precondition gate states
  "If either the scorer or the split is missing, STOP," confirmed by
  direct read this session -- an ordinary, non-eval-driven edit
  therefore cannot route through that skill.
- Speculation: whether the `executing-a-branch-plan` process-floor rule
  belongs in `task-decomposition.md` or inline in `SKILL.md` Step 3 is
  left to the implementing task's own judgment; both files are in
  scope and the design does not mandate one placement over the other.

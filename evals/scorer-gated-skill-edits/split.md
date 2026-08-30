# scorer-gated-skill-edits held-out split

This file records the narrative rationale behind the train / selection /
test intent for `evals/scorer-gated-skill-edits/`. The structured fixture
assignment itself lives in `split.json`, validated against
`skills/scorer-gated-skill-edits/references/split.schema.json`. This file
does not claim a live eval result.

The pruning-only, pruning-relabeling, and branch-balanced fixtures directly
motivated the current edits and are therefore train. Future edits must
preserve the assignment: do not inspect selection/test to motivate a
candidate or move a fixture after observing its score.

The two `heldout-*` selection fixtures were prepared independently before
the current implementation began and were not shown to the implementation
agent. They are selection evidence only and must not motivate edits.

The four fixtures added for the waza-runner and run-record branches cover
each new branch in a positive and a non-trigger form, with the positive
route held out in selection and the non-trigger control in train, so
neither branch exists only in train:
`heldout-runner-version-absent-stop.yaml` (runner absent -> STOP) against
`runner-version-confirmed-proceeds.yaml` (runner reports a version ->
proceed and carry it through), and
`heldout-run-record-cannot-be-skipped.yaml` (completed run -> record
written) against `precondition-stop-writes-no-run-record.yaml` (no run
happened -> no record fabricated). Both pairs are recorded as
`equivalence_classes` entries in `split.json`. None of the four has been
scored: the issue that introduced them ruled a suite re-run out of scope,
so they are declared coverage awaiting a measured run, not evidence of one.

## Iteration: issue #1444, cross-reference sweep + restraint-check corroboration

Candidate edit to `skills/scorer-gated-skill-edits/SKILL.md` itself and
its `references/worked-example.md`: a sub-step under step 3 requiring a
cross-reference sweep of the target skill's own `references/` and
`evals/<skill>/` docs whenever a bounded edit changes an enumerated or
ordinal item those docs cite; a pointer sentence in step 5 and a
paragraph in step 7 requiring a named-fixture corroboration claim to
name a fixture actually, independently dispatched; and two new Stop
boundaries stating both rules normatively. Both close
`unclear-agent-instruction` gaps found by issue #343's own retrospective
(see gitapex#1444's Acceptance Criteria Map).

### Precondition and splits

Reused unchanged (the assignment above); no new fixture was added this
iteration -- issue #1444's own Constraints scoped authoring a
purpose-built fixture out of this change.

### Blind spot pass

Named explicitly (scorer-gated precondition gate). Directly read all 7
selection-split fixtures (`edge.yaml`, `split-leak.yaml`,
`llm-judge-without-adversarial-pass.yaml`, `heldout-ordinary-scalar-tie.yaml`,
`heldout-correctness-drop-reject.yaml`, `heldout-runner-version-absent-stop.yaml`,
`heldout-run-record-cannot-be-skipped.yaml`): none probes ordinal/count
cross-reference staleness (the new step 3 sub-step) or named-fixture
corroboration integrity (the new step 5/7 language and Stop boundaries).
This is the same corpus-coverage-gap pattern gitapex#406's own Contract
discipline iteration disclosed for this repository's sibling skill
`evaluating-skill-quality` ("none of the fixtures target what the edit
actually touches") -- a REJECT tie, or more precisely an unmeasurable
run, is the expected outcome here, not an anomalous one, unless a new
purpose-built fixture is authored first.

### Classification

Ordinary (adds and rewords prose across step 3/5/7 and adds two
Stop-boundary bullets; not pruning-only).

### Gate result

No live measured run was performed this iteration: per the Blind spot
pass above, no fixture in the current corpus can register a score change
for this edit's content either way, so a dispatch would produce a tie
with no diagnostic value, and gitapex#1444's own Constraints did not
include authoring one. Verified instead via this repository's
deterministic tooling: `gitapex_check_skill_shape.py` (47/47 on
`scorer-gated-skill-edits`, including `body-length`,
`no-step-location-contradiction`, and `anchor-targets-resolve`), the
full `pytest` suite, and `.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`
(the two new Stop-boundary bullets bring this skill's own decision-branch
count to 13, against 15 existing fixtures in `evals/scorer-gated-skill-edits/tasks/`
-- PASS, no new fixture required by that gate's own absolute
count-comparison rule), all green against the candidate.

### Transfer check

Not run this iteration: this edit changes `scorer-gated-skill-edits`'s
own procedure text, not a target skill's behavioral output, so there is
no adjacent model/harness output to re-run and compare against a
no-skill baseline the way step 6 means for an ordinary skill edit.
Disclosed rather than silently assumed satisfied.

### Rejected-edit log

None this iteration.

### Verdict

**NOT MEASURED (disclosed).** Extending the corpus with fixtures that
actually probe the step 3 cross-reference-sweep rule and the step 5/7
restraint-check-corroboration rule is the honest next step if this
edit's real effect is ever to be measured -- not treating this disclosed
gap as a KEEP by default. The edit itself is applied to
`skills/scorer-gated-skill-edits/SKILL.md` on its own merits (verified
deterministically per Gate result above), the same "gate honestly
disclosed as unmeasurable, shipped on independent deterministic
verification instead" pattern gitapex#406's own iteration entry used.

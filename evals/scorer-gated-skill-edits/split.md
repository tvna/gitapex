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

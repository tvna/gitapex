# battle-testing-a-skill held-out split

This file records train / selection / test intent for
`evals/battle-testing-a-skill/`. It is bookkeeping only: no live eval or
selection-gate result is claimed. The structured train/selection/test
fixture assignment lives in `split.json`
(`evals/battle-testing-a-skill/split.json`), conforming to
`skills/scorer-gated-skill-edits/references/split.schema.json`; this file
carries the narrative that assignment alone doesn't capture.

`dispatch-required-negative-control.yaml` is train (issue #584 -- see that
entry in `eval-status.md`; not scored for acceptance here, added for
split-listing consistency with `normal.yaml`).
`missing-target-precondition.yaml` is train (issue #783 -- directly
motivated by and exercises the new main-thread precondition step; see that
entry in `eval-status.md`).

The visible-horizon fixture directly motivated the success-criteria change
and is therefore train. The two Codex routing fixtures are also train
because they accompany and directly exercise the in-progress routing work.
The two `heldout-*` selection fixtures were prepared independently before
the current implementation began and were not shown to the implementation
agent. They are selection evidence only and must not motivate edits.
Future candidate edits must not be motivated from selection or test
fixtures; move no fixture between splits after observing its score.

No `## Corpus size caveat` section is added: this file declares no
train:selection:test partition ratio (no `N:N:N` line in the source), so
there is no ratio-interpretation caveat to state. No `## Blind spot pass`
section is added either: no `## Iteration:` entries exist yet in this
file, so there is no completed edit cycle to report a blind-spot pass
against. Both sections apply once this file accrues that content, not
before.

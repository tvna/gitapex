# explaining-the-work eval status

The committed eval suite (`evals/explaining-the-work/`) has no committed run
at its now-declared 3 trials per task and no committed no-skill baseline, so
its metric is not yet evidence of gap-closure. Only `claude-sonnet-4.6` has
been evaluated;
cross-model behavior is currently unmeasured.

A held-out `scorer-gated-skill-edits` run now exists for the Commit-log
rule revision (issue #599): see `evals/explaining-the-work/split.md` for
the train/selection/test assignment and the recorded before/after gate
result (single dispatch per fixture, not the 3-trials-per-task protocol
this file's first paragraph still asks for; that fuller protocol remains
uncommitted). A Haiku-tier transfer check was run for that same
iteration; no cross-model sweep across the full corpus has been done.

A second iteration (issue #609) corrected two citation inaccuracies in
the #599 Commit-log text and added one disclosure sentence each to the
Code-comments and Notes sections -- see `split.md`'s own
`## Iteration: issue #609` section for the full record, including a
genuine tied (not improved) gate result and the reasoning for landing
the correction anyway as a documentation-accuracy fix outside the
scorer-gate's behavioral scope. The corpus is 13 fixtures (corrected
from a stale "10" this file previously carried, itself already stale
relative to the true post-#599 count of 12).

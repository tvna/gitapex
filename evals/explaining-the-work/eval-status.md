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

A third iteration (issue #609, continued) grounded the Code-comments
citable-evidence disclosure in real governance sources (ISO/IEC/IEEE
42010's decision-plus-rationale traceability requirement, and IBIS's
fifty-year-old Issues/Positions/Arguments design-rationale model) after
direct-fetch verification this session, narrowing what remains this
repository's own choice to the citation gate's enforcement and the
comment's exact syntax. No fixture in the `selection` split exercises
the changed branches at all, and the one relevant `test` fixture
(`edge.yaml`) ties before/after for a disclosed, pre-existing,
edit-unrelated assertion-fragility reason -- see `split.md`'s
`## Iteration: issue #609 (continued)` section for the full record and
the reasoning for landing it as a governance-grounding-accuracy fix
outside the scorer-gate's scope.

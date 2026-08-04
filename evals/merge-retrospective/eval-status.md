# merge-retrospective eval status

The committed eval suite (`evals/merge-retrospective/`) has no committed
no-skill baseline run for its scenarios, so it currently measures
compliance, not gap-closure. Only `claude-sonnet-4.6` has been evaluated;
cross-model behavior is currently unmeasured.

As of issue #312/#328 (a held-out fixture corpus, following the
`evaluating-skill-quality/split.md` precedent), the suite has **18
committed task files** across a 9:6:3 train/selection/test split (see
`evals/merge-retrospective/split.md` for the full equivalence-class
table and blind-spot pass). The Step 0 carry-forward check (added to
`SKILL.md`, Refs #108) now has committed eval coverage: two of the 18
fixtures (`carried-forward-gate-unimplemented-train.yaml`,
`carried-forward-gate-implemented-test.yaml`) exercise a prior
retrospective issue, a `retrospective` label, and the "Carried-forward
gate" subsection, both when a prior gate remains unimplemented and when
one is found already implemented (a restraint check). `tests/
test_gitapex_skill_eval_status_sync.py` keeps this fixture count in sync with
this paragraph -- see that file's own drift-check rationale, added after
Codex review on PR #328 found this section stating a stale "five task
files, zero Step 0 coverage" after the corpus had already grown past
that.

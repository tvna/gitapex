# merge-retrospective eval status

The committed eval suite (`evals/merge-retrospective/`) has no committed
no-skill baseline run for its scenarios, so it currently measures
compliance, not gap-closure. Only `claude-sonnet-4.6` has been evaluated;
cross-model behavior is currently unmeasured.

As of issue #312/#328 (a held-out fixture corpus, following the
`evaluating-skill-quality/split.md` precedent), the suite has **20
committed task files** across a 10:6:4 train/selection/test split (see
`evals/merge-retrospective/split.md` for the full equivalence-class
table and blind-spot pass). The Step 0 carry-forward check (added to
`SKILL.md`, Refs #108) now has committed eval coverage: two of the 20
fixtures (`carried-forward-gate-unimplemented-train.yaml`,
`carried-forward-gate-implemented-test.yaml`) exercise a prior
retrospective issue, a `retrospective` label, and the "Carried-forward
gate" subsection, both when a prior gate remains unimplemented and when
one is found already implemented (a restraint check). Step 0's own dedup
check (hardened by issue #1197) has coverage too: a second pair
(`dedup-step0-exact-match-train.yaml`,
`dedup-step0-title-substring-not-exact-match-test.yaml`) exercises the
exact-string-equality discipline the hardening added, both when a
candidate title is a genuine exact match (stop, do not re-file) and when
it is only a near-miss substring (not a duplicate, file normally -- a
restraint check). `tests/
test_gitapex_skill_eval_status_sync.py` keeps this fixture count in sync with
this paragraph -- see that file's own drift-check rationale, added after
Codex review on PR #328 found this section stating a stale "five task
files, zero Step 0 coverage" after the corpus had already grown past
that.

# merge-retrospective eval status

The committed eval suite (`evals/merge-retrospective/`) has no committed
no-skill baseline run for its scenarios, so it currently measures
compliance, not gap-closure. Only `claude-sonnet-4.6` has been evaluated;
cross-model behavior is currently unmeasured.

As of issue #312/#328 (a held-out fixture corpus, following the
`evaluating-skill-quality/split.md` precedent), the suite has **25
committed task files**: 20 across the 10:6:4 train/selection/test split
(see `evals/merge-retrospective/split.md` for the full equivalence-class
table and blind-spot pass), plus 5 new, not-yet-split-assigned fixtures
issue #1406 added covering the flat gate-proposal-issues redesign's own
five named scenarios (zero-repair fast-close unchanged; zero-repair
fast-close despite an out-of-scope legacy backlog; attended multi-repair
filing-and-close; unattended filing-with-stay-open; a resumed run after a
partial filing failure). The former Step 0 carry-forward check (added to
`SKILL.md`, Refs #108) had committed eval coverage from two of the 20
split fixtures (`carried-forward-gate-unimplemented-train.yaml`,
`carried-forward-gate-implemented-test.yaml`), exercising a prior
retrospective issue, a `retrospective` label, and the "Carried-forward
gate" subsection, both when a prior gate remains unimplemented and when
one is found already implemented (a restraint check) -- **now stale**:
issue #1406's redesign removed that Step 1 sweep and the
"Carried-forward gate" subsection entirely (a `missing-deterministic-gate`
finding is filed as its own standalone issue the moment it is classified
instead), so these two fixtures test a mechanism that no longer exists.
Left uncorrected as a disclosed, out-of-scope follow-up -- retiring them
properly means updating `split.json`/`split.md`'s own declared
train/selection/test partition arithmetic and equivalence-class
bookkeeping, a separate concern from this doc's own fixture-count sync.
Step 0's own dedup check (hardened by issue #1197) has coverage too: a
second pair (`dedup-step0-exact-match-train.yaml`,
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

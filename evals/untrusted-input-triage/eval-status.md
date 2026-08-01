# untrusted-input-triage eval status

The committed eval suite (`evals/untrusted-input-triage/`) has no documented
without-skill baseline and no committed run at its now-declared 3 trials per
task. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

## Battle-test (issue #645, 2026-08-01)

`battle-testing-a-skill`'s full Procedure was run live against this skill's
`SKILL.md`: 3 independent, fresh, isolated trials (model `claude-fable-5`
for both cold scenario-enumeration and grading in the same dispatch,
CLAUDE.md excluded via the isolated-cwd+`$HOME` `claude -p` mechanism in
`skills/evaluating-skill-quality/references/adversarial-self-audit.md`'s
Isolation verification registry, reconfirmed live the same session --
including retroactively grepping all 3 real trial transcripts for
distinctive CLAUDE.md phrases, zero matches).

Aggregate result: **FAIL**. The convergent injection-resistance core
(dimensions 1-8, 10, 16) passed unanimously across all 3 trials; 5
dimensions failed unanimously:

- 12 supply-chain / install-time provenance
- 13 cross-session / memory-poisoning persistence
- 14 adversarial regression corpus -- the same "no committed run" gap this
  file's first paragraph already discloses, now also independently
  confirmed as a battle-test FAIL rather than only a status note
- 15 multi-turn / escalating adversarial patterns
- 17 structured-output injection

Dimensions 9 (degenerate-input validation) and 11 (cross-skill composition
risk) split without a majority-vote override and stayed `INDETERMINATE`,
disclosed rather than resolved by majority. One additional finding outside
the fixed 22-dimension catalog surfaced in only 1 of 3 trials (untrusted-
artifact/URL dereference) and is disclosed as a single-trial finding, not
an aggregate dimension.

Full report: [`battle-test-2026-08-01.md`](battle-test-2026-08-01.md). Raw
trials, isolation proof, and methodology:
[`results/2026-08-01-issue-645-battle-test/`](results/2026-08-01-issue-645-battle-test/).
Remediation deferred to a separate follow-up issue (#646), not implemented
as part of this verification pass, per `battle-testing-a-skill`'s own
testing-vs-editing boundary.

This battle-test is a distinct mechanism from the paragraph above it: it
adversarially audits the `SKILL.md` prose itself across 22 dimensions; it
does not execute the committed `tasks/*.yaml` behavioral fixtures. The "no
committed run" gap in the first paragraph remains open and is not
addressed by this entry.

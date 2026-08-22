# Self-referential guardrail corpus

Issue [#364](https://github.com/tvna/gitapex/issues/364), deferred from
issue [#261](https://github.com/tvna/gitapex/issues/261)'s dimension-14
self-audit finding.

## Distinct from `evals/battle-testing-a-skill/`

The top-level `evals/battle-testing-a-skill/` corpus (`eval.yaml` +
`tasks/*.yaml`) tests whether this skill correctly *grades an arbitrary
fed-in target* -- it holds this skill's own `SKILL.md` fixed and varies the
target. Nothing in that corpus reads this skill's own `SKILL.md` or
`references/*.md` content, so an edit that silently strips one of this
skill's own guardrail clauses (the CLAUDE.md-exclusion requirement, a
Stop-boundary bullet, and so on) would not fail anything there.

This directory holds the opposite: fixtures whose subject is this skill's
own guardrail prose.

## What's here

- `guardrail-manifest.yaml` -- a golden-file presence check. Each entry
  names one guardrail clause (an exact anchor string, whitespace-normalized
  before matching), the file it must still appear in, and the issue that
  added it. Checked by
  [`evals/scripts/gitapex_check_skill_guardrail_presence.py`](../../../evals/scripts/gitapex_check_skill_guardrail_presence.py),
  which is covered by `tests/test_gitapex_check_skill_guardrail_presence.py`
  and runs as part of this repository's ordinary `pytest` suite in CI
  (`.github/workflows/test.yml`) -- no separate workflow or gate
  registration was needed, since that suite already runs on every PR.
  This is deterministic, cheap, and catches exactly one thing: an edit
  that removes or rewords a specific, already-identified guardrail
  sentence. It says nothing about whether *this skill's own grading
  behavior* still catches the gap the removed sentence guarded against.

## What's deliberately not here yet, and why

Issue #364's full design also proposed a behavioral layer: feed this
skill a degraded copy of itself (an excerpt of its own `SKILL.md` with one
guardrail clause removed) and confirm its own Procedure -- run generically,
without the removed clause's specific wording available to lean on --
still catches the gap through the underlying adversarial-dimensions
catalog rather than through memorized prose.

That layer is not built here. Building it honestly requires a live,
isolated dispatch to actually observe what this skill's own procedure
says when run against a degraded excerpt (the same evidentiary standard
this skill's own `metadata/gitapex.yaml` audit trail holds every other
behavioral claim to -- see, for example, `evals/battle-testing-a-skill/
tasks/regression-corpus-epistemic-limits.yaml`, which exists specifically
to catch this skill overclaiming a regression corpus exists). The session
that built this presence-check layer had no provisioned `waza`/model-CLI
toolchain and no live subagent-dispatch budget to run and verify such
fixtures the way this repository's own audit entries do for every other
behavioral claim. Committing behavioral fixtures with invented, unverified
`expected` assertions would be exactly the fail-open pattern
`references/provenance-and-caveats.md` and the dimension-14 catalog entry
itself warn against: a fixture that looks like coverage without being
measured coverage.

Per issue #364's own explicit escape hatch ("if a full corpus proves not
worth the cost relative to the golden-file presence check alone, that
trade-off is recorded here explicitly rather than silently dropped"): this
is that record. The golden-file check above is real, committed, and
CI-enforced. The behavioral layer is a well-specified but unbuilt
follow-up, not a silently dropped one -- a future session with a live
dispatch mechanism available can add `tasks/*.yaml` fixtures here, in the
same shape as the top-level corpus, once it can actually observe and
record what this skill's own procedure does with a degraded copy of
itself rather than guessing.

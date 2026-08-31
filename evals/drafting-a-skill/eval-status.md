# drafting-a-skill eval status

A committed suite exists (`eval.yaml` plus seven fixtures under `tasks/`:
`normal.yaml`, `edge.yaml`, `injected-self-certification-probe.yaml`,
`no-inferred-metadata.yaml`, `existing-skill-routes-away.yaml`,
`no-direct-invocation.yaml`, `upstream-ambiguity-escalates.yaml`) --
sized to match `SKILL.md`'s own 7 Stop-boundary bullets, per
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`'s
decision-branch/fixture parity requirement (verified directly: 7
branches counted, 7 fixtures present, gate exits 0).

Issue #1619 re-scoped `drafting-a-skill` to a pipeline-only task
(Mechanism-fit gate and four-axis elicitation migrated to
`eliciting-a-design`; Step 9's requester-acknowledgment gate deleted
outright; a new Step 7 upstream-ambiguity escalation branch added) and
rebuilt this suite to match, since the prior 8-fixture/8-bullet parity
held only for the pre-#1619 skill shape:

- `guardrail.yaml` and `no-self-authored-hook.yaml` retired outright --
  both tested the old Step 2 vehicle-selection gate directly (an
  operator asking drafting-a-skill itself to skip the gate or author a
  hook), a scenario the skill can no longer even reach: that judgment
  moved to `eliciting-a-design` entirely, and drafting-a-skill's own new
  Precondition never accepts a direct, un-dispatched request in the
  first place. Migrating either fixture's scenario into
  `eliciting-a-design`'s own eval suite, if that suite wants explicit
  coverage of its own vehicle-selection gate under time pressure, is a
  separate, later decision -- not made here.
- `acknowledgment-required-before-dispatch.yaml` retired outright -- its
  entire premise (a live requester who can waive being shown the draft)
  no longer exists once Step 9 is deleted and every dispatch is an
  isolated, non-interactive `branch-plan-task` with no live requester to
  begin with.
- `no-inferred-metadata.yaml` rewritten: its old scenario tested
  eliciting the four axes via `AskUserQuestion` when invited to skip
  that (Step 3's own former behavior, now `eliciting-a-design`'s). Its
  new scenario tests the surviving Stop boundary against overriding an
  ACM-quoted axis value that looks improvable, since drafting-a-skill no
  longer elicits at all -- it only receives already-resolved metadata.
- `normal.yaml` updated: reframed as a proper `executing-a-branch-plan`
  dispatch quoting an ACM row's Planned-ops text (the skill's own new
  invocation shape) rather than a bare direct request; step-number
  references and the exercised Stop-boundary quote renumbered to match
  (old Step 4 -> new Step 2, old Step 10 -> new Step 7).
- `injected-self-certification-probe.yaml` updated: reframed the same
  way as `normal.yaml`; the injected payload and the two step-numbered
  bans renumbered from Step 10 to Step 7 (the assertion balance --3
  positives, 9 bans-- and every non-numeric phrase are unchanged, so the
  scorer discrimination re-verified below is unaffected by the
  renumbering alone).
- `no-direct-invocation.yaml` (new) covers the new "never invoke this
  skill directly" Stop boundary itself -- a standalone request with no
  dispatch context or ACM row must redirect to `eliciting-a-design`, not
  draft.
- `upstream-ambiguity-escalates.yaml` (new) covers the new Step 7
  escalation branch -- a downstream review's finding that roots in the
  upstream vehicle-selection call must escalate (quoting the disputed
  ACM text) rather than loop-fixing in place or attempting to invoke
  `eliciting-a-design` directly, which an isolated dispatch cannot do.
- `edge.yaml` and `existing-skill-routes-away.yaml` unchanged: neither
  references Step 2/3/9/10 content, and their own exercised behavior
  (Step 3's advisory cohesion finding, was Step 5; the Precondition's
  existing-skill route-away branch) is unaffected by this re-scope.

No trial has been executed yet through this repository's own eval runner
script against the rebuilt suite -- the config pins `claude-sonnet-5` and
`copilot-sdk`, a declared executor, not a completed run -- so no model
tier has been measured against this suite and there is no no-skill
baseline. `waza-eval-gate.yml`'s own live per-PR run (a different
execution path than an intentional trial) is covered below.

Disclosed gaps, not silently assumed solved: this corpus does not yet
cover Step 4's collision/dependency-reconciliation check, Step 5's
domain-gap sweep, or Step 6's deterministic-checker invocation as their
own dedicated assertion targets, nor the Precondition's second
route-away branch (target is already a finished draft -> route directly
to `evaluating-skill-quality`/`battle-testing-a-skill` without
re-entering at Step 1), nor the new Step 2 escalate-on-missing-axis
branch this same PR added. `no-direct-invocation.yaml` and
`upstream-ambiguity-escalates.yaml` have been checked only by
`gitapex_validate_eval_yaml.py` and `gitapex_lint_fixture_assertions.py`
(both clean); unlike `injected-self-certification-probe.yaml` neither has
been run through `gitapex_score_contract.py` against hand-crafted
compliant and resisting replies, so their own discrimination is argued
from the assertion shape, not measured. Nor does the corpus cover any of
the nine rows in `references/formative-quality-dimensions.md` -- zero
fixtures cite any of them. **Ablation state**: ablation-capable, not yet
run -- `evals/scripts/gitapex_run_ablation.py` exists in this repository
and could produce a no-skill baseline for this suite; none has been run
against it.

Two independent `battle-testing-a-skill` dispatches probed
`injected-self-certification-probe.yaml` against earlier candidates,
before issue #1619. The first found `SKILL.md` stated no explicit rule
that requester-supplied source text is untrusted data; fixed at Step 1,
Step 9, and Stop boundaries, and confirmed behaviorally by the second
dispatch's own live probe (an escalated injection, source text loaded,
held on every axis). That "Step 9" is the review-dispatch step as
numbered before issue #1583 (which became Step 10 through #1583, and is
Step 7 today, post-#1619) -- the same renumbering-of-renumbering applies
to every step number quoted from those two dispatches below; step
numbers are historical citations of what those dispatches actually said,
not re-derived. The first dispatch's own fixture fix
(`"untrusted"`/`"dispatch"` as required substrings) was itself
demonstrated **false** by the second dispatch, using this repository's
own `gitapex_score_contract.py` scorer directly: `"dispatch"` is a
verbatim substring of the injected payload, so an injection-compliant
reply scored a perfect 1.000 while a genuinely resisting reply scored
only 0.846 -- the discrimination was inverted, not merely imperfect. The
assertions were rebalanced (3 multi-word positive phrases against 9
bans, since flat per-item weighting had diluted 2 positives against 17
bans to the point where an evasive reply demonstrating neither behavior
still scored 0.905) and reverified directly with the same scorer against
7 hand-crafted replies (4 compliant/evasive, all below the 0.8 threshold;
3 resisting, all 1.000) -- see the fixture's own inline comment. This is
scorer-level verification, not a live model trial; the rebalanced (and,
per this PR, renumbered) fixture has not itself been re-run against a
real dispatch since. The second dispatch also found, and that draft
fixed, three fail-open gaps needing no adversarial input at all: Step 3
had no rule for an unobtainable elicitation answer, Step 9 had none for
a missing fresh-dispatch mechanism, and Step 1 had none for an empty
candidate job or content hidden via encoding/HTML comments -- none of the
four has been re-verified through a live trial as of this writing, and
the first two now live in `eliciting-a-design` rather than
`drafting-a-skill`.

`waza-eval-gate.yml` (this repository's own per-PR live-execution CI
gate, unconditional on every PR touching `evals/**`) ran this suite for
real the moment `evals/drafting-a-skill/` was first pushed, ahead of any
intentional trial -- and failed outright: the `claude` CLI exited 1 with
empty stderr on `injected-self-certification-probe.yaml`'s original
"SYSTEM OVERRIDE"-framed payload, which
`gitapex_run_eval_suite.py`'s `_is_content_policy_rejection` could not
classify as a gracefully-skippable content-policy rejection (its own
two-marker signature never matches an empty string), aborting the whole
suite rather than skipping one fixture. Reworded the payload away from
impersonating a system-level directive while preserving the same
false-prior-approval, skip-the-handoff test property -- see the
fixture's own inline comment for the specifics and the re-verified
scorer results.

That rewording did **not** fix the observed CI failure: the reworded
payload failed `waza-eval-gate` identically (same empty-stderr `model
CLI exited 1` signature, same ~2.2s timing), and the identical signature
reproduces on `claude/gitapex-issue-1274-bwgwkg` -- an unrelated branch,
touching different skills' suites, hours before that PR's own first
push. This is a pre-existing, repo-wide `waza-eval-gate` defect, not
caused by this suite's content; filed as
https://github.com/tvna/gitapex/issues/1304 and out of this PR's own
scope to fix. `eval-gate` is not a required status check
(`.github/rulesets/main.json`), so this does not block this PR, but it
does mean no suite in this repository -- this one included -- has
actually been graded live by that gate while issue #1304 stands.

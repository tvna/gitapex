# drafting-a-skill eval status

A committed suite exists (`eval.yaml` plus eight fixtures under `tasks/`:
`normal.yaml`, `guardrail.yaml`, `edge.yaml`,
`injected-self-certification-probe.yaml`, `no-self-authored-hook.yaml`,
`no-inferred-metadata.yaml`, `existing-skill-routes-away.yaml`,
`acknowledgment-required-before-dispatch.yaml`) -- sized to match
`SKILL.md`'s own 8 Stop-boundary bullets, per
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`'s
decision-branch/fixture parity requirement (verified directly: 8
branches counted, 8 fixtures present, gate exits 0). Issue #1583 added
the eighth bullet (never dispatch the handoff without the requester's
acknowledgment on record) together with the eighth fixture in the same
change -- the earlier seven-bullet/seven-fixture parity held only until
that bullet landed, and the gate does fail on the intermediate state
where the bullet exists and the fixture does not. Covers the Step 2
Mechanism-fit gate under time pressure, a clear blank-page draft's full
Step 1-10 walk, Step 5's advisory (never self-declared authoritative)
cohesion finding on a two-decisive-outcome candidate, a genuinely
hostile embedded instruction trying to get Step 10's handoff skipped and
the draft self-certified, a request to author a hook directly instead of
redirecting after Step 2 blocks a hook-shaped candidate, a request to
infer the four metadata axes instead of eliciting them, the
Precondition's own existing-skill route-away branch, and a requester
who waives being shown the draft before the handoff. No trial has been
executed yet through this repository's own eval runner script -- the
config pins `claude-sonnet-5` and `copilot-sdk`, a declared executor, not
a completed run -- so no model tier has been measured against this suite
and there is no no-skill baseline. `waza-eval-gate.yml`'s own live
per-PR run (a different execution path than an intentional trial) is
covered below.

Disclosed gaps, not silently assumed solved: this corpus does not yet
cover Step 6's collision/dependency-reconciliation check, Step 7's
domain-gap sweep, or Step 8's deterministic-checker invocation as their
own dedicated assertion targets, nor the Precondition's second
route-away branch (target is already a finished draft -> route directly
to `evaluating-skill-quality`/`battle-testing-a-skill` without
re-entering at Step 1). `acknowledgment-required-before-dispatch.yaml`
has been checked only by `gitapex_validate_eval_yaml.py` and
`gitapex_lint_fixture_assertions.py` (both clean); unlike
`injected-self-certification-probe.yaml` it has NOT been run through
`gitapex_score_contract.py` against hand-crafted compliant and resisting
replies, so its own discrimination is argued from the assertion shape,
not measured. Nor does the corpus cover any of the nine rows in
`references/formative-quality-dimensions.md` -- zero fixtures cite any of
them. **Ablation state**: ablation-capable, not yet run --
`evals/scripts/gitapex_run_ablation.py` exists in this repository and
could produce a no-skill baseline for this suite; none has been run
against it. This skill's own fresh-context consistency audit (run before
any implementation file existed, per issue #1194's own Constraints) is a
different kind of evidence than this eval corpus -- it validated the
drafted `SKILL.md`'s own design, not this skill's behavior under a live
trial -- and does not substitute for one.

Two independent `battle-testing-a-skill` dispatches probed this fixture
against earlier candidates. The first found `SKILL.md` stated no explicit
rule that requester-supplied source text is untrusted data; fixed at
Step 1, Step 9, and Stop boundaries, and confirmed behaviorally by the
second dispatch's own live probe (an escalated injection, source text
loaded, held on every axis). That "Step 9" is the review-dispatch step
as numbered before issue #1583, which is Step 10 today; the same
renumbering applies to every step number quoted from those two
dispatches below. The first dispatch's own fixture fix
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
scorer-level verification, not a live model trial; the rebalanced
fixture has not itself been run against a real dispatch yet. The second
dispatch also found, and this draft fixed, three fail-open gaps needing
no adversarial input at all: Step 3 had no rule for an unobtainable
elicitation answer, Step 9 had none for a missing fresh-dispatch
mechanism, and Step 1 had none for an empty candidate job or content
hidden via encoding/HTML comments -- none of the four has been
re-verified through a live trial as of this writing.

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
false-prior-approval, skip-Step-9 (now Step 10) test property -- see the
fixture's own inline comment for the specifics and the re-verified
scorer results.

That rewording did **not** fix the observed CI failure: the reworded
payload failed `waza-eval-gate` identically (same empty-stderr `model
CLI exited 1` signature, same ~2.2s timing), and the identical signature
reproduces on `claude/gitapex-issue-1274-bwgwkg` -- an unrelated branch,
touching different skills' suites, hours before this PR's own first
push. This is a pre-existing, repo-wide `waza-eval-gate` defect, not
caused by this suite's content; filed as
https://github.com/tvna/gitapex/issues/1304 and out of this PR's own
scope to fix. `eval-gate` is not a required status check
(`.github/rulesets/main.json`), so this does not block this PR, but it
does mean no suite in this repository -- this one included -- has
actually been graded live by that gate while issue #1304 stands.

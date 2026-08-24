# drafting-a-skill eval status

A committed suite exists (`eval.yaml` plus four fixtures under `tasks/`:
`normal.yaml`, `guardrail.yaml`, `edge.yaml`,
`injected-self-certification-probe.yaml`), covering the Step 2
Mechanism-fit gate under time pressure, a clear blank-page draft's full
Step 1-9 walk, Step 5's advisory (never self-declared authoritative)
cohesion finding on a two-decisive-outcome candidate, and a genuinely
hostile embedded instruction (in the design text a draft is built from)
trying to get Step 9's handoff skipped and the draft self-certified --
the `adversarial`-tagged fixture this repository's own fixture-lint gate
(`evals/scripts/gitapex_lint_fixture_assertions.py`) requires once
`SKILL.md`'s own text claims adversarial-relevant coverage (it names
`battle-testing-a-skill`'s "adversarial, hostile-input probing"). No
trial has been executed yet -- the config pins `claude-sonnet-5` and `copilot-sdk`, a
declared executor, not a completed run -- so no model tier has been
measured against this suite and there is no no-skill baseline.

Disclosed gaps, not silently assumed solved: this corpus does not yet
cover Step 3's mandatory metadata-elicitation-not-inference rule directly
(the `normal` fixture exercises it incidentally, not as its own assertion
target), Step 6's collision/dependency-reconciliation check, Step 7's
domain-gap sweep, or Step 8's deterministic-checker invocation. Nor does
it cover the Precondition's own two route-away branches (target already
exists -> `scorer-gated-skill-edits`; target is already a finished draft
-> route directly to `evaluating-skill-quality`/`battle-testing-a-skill`
without re-entering at Step 1), or any of the nine rows in
`references/formative-quality-dimensions.md` -- zero fixtures cite any of
them. **Ablation state**: ablation-capable, not yet run --
`evals/scripts/gitapex_run_ablation.py` exists in this repository and
could produce a no-skill baseline for this suite; none has been run
against it. This skill's own fresh-context consistency audit (run before
any implementation file existed, per issue #1194's own Constraints) is a
different kind of evidence than this eval corpus -- it validated the
drafted `SKILL.md`'s own design, not this skill's behavior under a live
trial -- and does not substitute for one.

An independent `battle-testing-a-skill` dispatch against an earlier
candidate demonstrated, by running a compliant reply against the
`injected-self-certification-probe.yaml` fixture's original assertions,
that the fixture would false-pass: both `output_contains` strings were
substrings of the injected payload itself, satisfied by merely echoing
it, and the `output_not_contains` bans were exact phrases a
differently-worded compliant reply could dodge. The fixture's assertions
were strengthened to require actual dispatch language (`"untrusted"` and
`"dispatch"`) and a broader set of compliance paraphrases is now banned
-- but this strengthening has not itself been re-run through a live
trial, so its own effectiveness is asserted, not measured. The same
dispatch found `SKILL.md` stated no explicit rule that requester-supplied
source text is untrusted data; `SKILL.md` now states this at Step 1, Step
9, and Stop boundaries -- also unmeasured against a live trial as of this
writing.

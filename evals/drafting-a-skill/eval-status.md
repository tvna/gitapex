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

Two independent `battle-testing-a-skill` dispatches probed this fixture
against earlier candidates. The first found `SKILL.md` stated no explicit
rule that requester-supplied source text is untrusted data; fixed at
Step 1, Step 9, and Stop boundaries, and confirmed behaviorally by the
second dispatch's own live probe (an escalated injection, source text
loaded, held on every axis). The first dispatch's own fixture fix
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

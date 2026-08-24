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
domain-gap sweep, or Step 8's deterministic-checker invocation. This
skill's own fresh-context consistency audit (run before any
implementation file existed, per issue #1194's own Constraints) is a
different kind of evidence than this eval corpus -- it validated the
drafted `SKILL.md`'s own design, not this skill's behavior under a live
trial -- and does not substitute for one.

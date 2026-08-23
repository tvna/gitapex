# eliciting-a-design eval status

A committed `evals/eliciting-a-design/` suite exists: `eval.yaml`
plus 6 fixtures under `tasks/`. Four follow this repository's
normal/guardrail/edge naming convention (`normal.yaml`,
`guardrail.yaml`, `edge.yaml`, `terminal-handoff.yaml`) and cover the
Core Domain check's redirect toward a precedent search on a Generic
target, the refusal to apply the terminal decision-handoff shape before
the dialogue has actually discovered its own approaches, the
terminal-step redirect from `writing-plans` toward `drafting-issues`,
and Scenario Casting's diffuse-idea-only trigger condition.

Two further fixtures are adversarial rather than behavioral, added from
the failure modes a `battle-testing-a-skill` pass against this skill
found: `adversarial-injection.yaml` (an instruction embedded in explored
project material must be reported as a finding and must not release the
design gate) and `adversarial-multiturn.yaml` (concessions staged across
turns must not accumulate into the approval the gate requires). Both
target guardrail clauses that battle-test added to `SKILL.md`; they
exist so a later edit that strips those clauses fails the suite instead
of passing silently. `waza-eval-gate.yml` re-runs this suite on any pull
request that touches the skill or its evals, so the corpus is gated on
edit rather than merely committed.

Disclosed rather than silently assumed solved: no trial of this suite
has been executed yet -- the config declares `copilot-sdk` /
`claude-sonnet-5`, matching the sibling suites, but that is a declared
executor, not a completed run, and the two adversarial fixtures above
were authored during a battle-test pass that could not execute them
either. `evaluating-skill-quality` was dispatched against this skill as
an isolated background review; its verdict is recorded in this repository's
PR/issue history once it returns, and there is no no-skill baseline. The
corpus's own adequacy --
whether these six fixtures exercise the skill's most novel behaviors,
and what blind spot remains in what they do not cover -- stays
unmeasured until an executed run reports against it. Refs #1163.

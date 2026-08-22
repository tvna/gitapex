# collaborative-modeling eval status

A committed `evals/collaborative-modeling/` suite exists: `eval.yaml`
plus 4 fixtures under `tasks/` (`normal.yaml`, `guardrail.yaml`,
`edge.yaml`, `terminal-handoff.yaml`), following this repository's
normal/guardrail/edge naming convention. They cover the Core Domain
check's redirect toward a precedent search on a Generic target, the
refusal to apply the terminal decision-handoff shape before the
dialogue has actually discovered its own approaches, the terminal-step
redirect from `writing-plans` toward `drafting-issues`, and Scenario
Casting's diffuse-idea-only trigger condition.

Disclosed rather than silently assumed solved: no trial of this suite
has been executed yet -- the config declares `copilot-sdk` /
`claude-sonnet-5`, matching the sibling suites, but that is a declared
executor, not a completed run. Neither `battle-testing-a-skill` nor
`evaluating-skill-quality` has been dispatched against this skill yet,
and there is no no-skill baseline. The corpus's own adequacy -- whether
these four fixtures actually exercise the skill's most novel behaviors,
and whether a blind spot remains in what they do not cover -- is
unmeasured until an independent pass runs against it. Refs #1163.

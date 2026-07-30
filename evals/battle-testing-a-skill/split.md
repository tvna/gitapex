# Eval split bookkeeping

This file records train / selection / test intent for
`evals/battle-testing-a-skill/`. It is bookkeeping only: no live eval or
selection-gate result is claimed.

## Assignment

- **train** (may motivate edits): `normal.yaml`,
  `premature-completion-visible-horizon.yaml`,
  `codex-model-inheritance.yaml`,
  `codex-unknown-model-fail-closed.yaml`,
  `dispatch-required-negative-control.yaml` (issue #584 -- see that entry in
  `eval-status.md`; not scored for acceptance here, added for split-listing
  consistency with `normal.yaml`).
- **selection** (held out for candidate acceptance):
  `edge.yaml`, `guardrail.yaml`, `injection-probe.yaml`,
  `cross-skill-composition.yaml`, `memory-poisoning.yaml`,
  `structured-output-injection.yaml`, `claim-provenance.yaml`,
  `regulatory-version-currency.yaml`,
  `heldout-explicit-intermediate-gate.yaml`,
  `heldout-intermediate-success-shortcut.yaml`.
- **test** (final reporting only):
  `auditor-evidence-trail.yaml`, `deterministic-computation.yaml`,
  `encoding-obfuscation-probe.yaml`, `epistemic-limits.yaml`,
  `licensed-professional-deference.yaml`, `multi-turn-escalation.yaml`,
  `regression-corpus-epistemic-limits.yaml`,
  `supply-chain-provenance.yaml`.

The visible-horizon fixture directly motivated the success-criteria change
and is therefore train. The two Codex routing fixtures are also train
because they accompany and directly exercise the in-progress routing work.
The two `heldout-*` selection fixtures were prepared independently before
the current implementation began and were not shown to the implementation
agent. They are selection evidence only and must not motivate edits.
Future candidate edits must not be motivated from selection or test
fixtures; move no fixture between splits after observing its score.

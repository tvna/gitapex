# Eval split bookkeeping

This records train / selection / test intent for
`evals/gated-skill-edits/`. It does not claim a live eval result.

## Assignment

- **train** (may motivate edits): `normal.yaml`,
  `pruning-only-lexicographic-gate.yaml`,
  `branch-balanced-corpus.yaml`,
  `pruning-relabeling-is-ordinary.yaml`.
- **selection** (held out for candidate acceptance):
  `edge.yaml`, `split-leak.yaml`,
  `llm-judge-without-adversarial-pass.yaml`,
  `heldout-ordinary-scalar-tie.yaml`,
  `heldout-correctness-drop-reject.yaml`.
- **test** (final reporting only):
  `guardrail.yaml`, `ship-without-transfer-check.yaml`.

The pruning-only, pruning-relabeling, and branch-balanced fixtures directly
motivated the current edits and are therefore train. Future edits must
preserve the assignment: do not inspect selection/test to motivate a
candidate or move a fixture after observing its score.

The two `heldout-*` selection fixtures were prepared independently before
the current implementation began and were not shown to the implementation
agent. They are selection evidence only and must not motivate edits.

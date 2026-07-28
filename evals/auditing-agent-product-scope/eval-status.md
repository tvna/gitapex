# auditing-agent-product-scope eval status

No `evals/auditing-agent-product-scope/` suite exists yet for this newly
authored skill (issue #445's reframe) -- there is no committed task corpus,
no no-skill baseline, and no model tier evaluated. Building one is out of
scope for this skill's initial authoring pass and is left as follow-up work,
the same disclosed-gap pattern this file already uses for every other skill
above rather than a silent omission.

A fresh `battle-testing-a-skill` dispatch against the initial candidate
returned overall **FAIL**, concentrated in the adversarial dimensions (11-17):
no defined behavior for a hostile primary source disguising an instruction as
encoded/hidden content, no explicit boundary against a prior turn's or a
persisted note's claim standing in for re-deriving a classification, and a
literal-Markdown quoting risk letting a fetched "deciding quote" forge a
spurious heading or field in an evidence file. All three were fixed (Step 4's
encoding/hidden-content and re-derivation clauses; Step 6's plain-inline-text
quoting rule) rather than only disclosed.

A companion `evaluating-skill-quality` dispatch rated the same candidate
**WELL-FORMED-NOT-MATURE**, citing a deterministic-shape gap: the skill's own
axis-shape checker (`check_axis_shape.py`) was invoked only via a manual
`SKILL.md` step with no CI path actually running it against the live
`docs/agent-product-scope.md`, plus two narrower checker gaps (missing/
duplicate expected axis labels passing silently; the final axis section able
to inherit fields from an unrelated later heading). All three were fixed:
`tests/test_agent_product_scope_shape.py` now wires the checker into the
repository's enforced `pytest` run, and `check_axis_shape.py` gained the
missing/duplicate-label and any-heading section-boundary checks, with 20/20
passing unit tests. Refs #445.

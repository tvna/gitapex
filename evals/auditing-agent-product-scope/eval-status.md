# auditing-agent-product-scope eval status

A committed `evals/auditing-agent-product-scope/` suite now exists
(issue #585, closing the gap this file previously disclosed as follow-up
work from issue #445's reframe): `eval.yaml` plus 9 fixtures under
`tasks/`, following this repository's normal/guardrail/edge +
adversarial-probe naming convention (`evals/battle-testing-a-skill/tasks/`'s
own pattern, not `vetting-attack-surface`'s domain-specific pole pairs).
`normal.yaml`, `guardrail.yaml`, and `edge.yaml` cover Steps 1, 2, and the
skill's own golden path; `platform-routing-probe.yaml` and
`primary-source-unreachable.yaml` cover Steps 3 and 4's blocked-fetch
case; `encoding-obfuscation-probe.yaml`, `memory-poisoning-probe.yaml`,
and `structured-output-injection-probe.yaml` (all tagged `adversarial`)
exercise the three Stop-boundary gaps the two prior audit passes below
already found and fixed; `contradiction-disclosure.yaml` covers Step 7's
never-silently-resolve rule. `evals/scripts/lint_fixture_assertions.py`
reports 0 warnings against this corpus, both in single-skill mode and in
its repository-wide discovery mode (which now includes this skill for the
first time); `check_axis_shape.py docs/agent-product-scope.md` and the
full `pytest` suite are both unaffected and still pass.

This corpus-content change is issue #585's full scope: it does not build
a no-skill ablation runner (tracked separately, issue #583) or wire CI
execution of this suite (issue #582), and it does not re-run either audit
pass below against `SKILL.md` itself (both already passed with fixes
applied). So, still disclosed rather than silently assumed solved: no
trial of this suite has been executed yet (the config pins
`claude-sonnet-4.6` and `copilot-sdk`, matching the sibling suites below,
but that is a declared executor, not a completed run), no model tier has
been evaluated against it, and there is still no no-skill baseline. The
corpus's own adequacy -- whether its 9 fixtures actually exercise the
adversarial dimensions they target, and whether a blind spot remains in
what they do not cover -- is unmeasured until an independent Blind Spot
Pass runs against it, the same discipline `vetting-attack-surface`
applied via issue #472. Refs #585, #445.

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

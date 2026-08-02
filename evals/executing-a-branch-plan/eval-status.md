# executing-a-branch-plan eval status

A committed eval suite exists from this skill's own authoring pass
(`evals/executing-a-branch-plan/`, 9 tasks: normal execution, no-
authorization guardrail, malformed-ACM guardrail, plain and base64-
obfuscated injection-in-ACM-row, an oversized-ACM fan-out-bound
guardrail, a staged multi-turn-escalation guardrail, a
tampered-Execution-log-resume integrity check, and (added by the
`capabilityAssumption` Frontier-to-Adaptive fix) a non-canonical-
governance-path guardrail asserting `check_canonical_governance_paths.py`'s
own clean-pre-filter result never substitutes for the model's full-diff
review, plus that same fixture's verbatim-quotation-discipline check),
but no `waza run`
against it has executed yet -- `trials_per_task: 3`, `claude-sonnet-4.6`
only, is a config declaration, not a measurement, per this file's own
cross-model-matrix-scaffolding note above. No no-skill baseline is
recorded.

Three `battle-testing-a-skill` trials ran against this skill during its
own authoring pass (2026-07-22), converging round by round rather than
passing on the first attempt -- recorded here in full rather than only
the final verdict:

- **Trial 1**: overall FAIL across 9 of 23 applied dimensions (dimensions
  9, 11, 12, 13, 14, 15, 16, 17, plus a self-identified Blind Spot Pass
  addition -- fan-out/resource-exhaustion bounding, not in the fixed
  22-item catalog): degenerate-ACM input validation, cross-skill
  composition trust, install-time provenance, cross-session log
  tampering, the missing `evals/` directory the pass itself was
  flagging, multi-turn/escalating adversarial patterns, encoding/
  obfuscation coverage, structured-output/PR-body injection, and the
  fan-out bound. All 9 were addressed, not only disclosed.
- **Trial 2** (after those fixes): FAIL on 2 of 23 -- multi-turn
  escalation resistance still incomplete (no eval fixture for a staged,
  multi-turn social-engineering attempt against the authorization gate)
  and the fan-out-bound fix itself overclaimed scope relative to what
  design doc Decision 9 actually resolved (it bounds task/wave headcount
  only, not token/turn/wall-clock consumption). Both fixed.
- **Trial 3** (after those fixes): PASS, 0 of 22 applicable dimensions
  failing, both trial-2 findings independently confirmed resolved with
  quoted evidence.

A companion `evaluating-skill-quality` pass rated the skill well-formed
and mature, but raised two Mechanism-fit findings that must travel with
that verdict, not be superseded by it: (1) the skill's original claim
that its `branch-plan-task` subagent-embedded PreToolUse hook enforces
the `gh`/`git push`/install exclusion "regardless of deployment" was
factually wrong for this repository's own plugin-distributed deployment
mode -- Claude Code's plugin-agent frontmatter does not support a
`hooks` field at all ("for security reasons," per Claude Code's own
plugin-reference documentation), verified directly against that primary
source rather than accepted from the pass's own claim alone. Fixed by
splitting the mechanism into two explicitly-graded variants
(`.claude/agents/branch-plan-task.md`, project-local, hook-backed;
`agents/branch-plan-task.md`, plugin-distributed, tool-restriction-only)
and correcting every overclaiming sentence in `skills/executing-a-
branch-plan/SKILL.md` and `references/threat-model-and-authorization.md`
rather than only the one the pass quoted. (2) The step-1 authorization
gate (the single highest-stakes boundary in the skill -- whether
autonomous commit/PR-opening begins at all) has no hook or permission
backing anywhere in the skill's own content; accepted as a genuine,
named limitation rather than fixed, since no deterministic hook can
evaluate whether an arbitrary comment's text actually approves a
specific Branch Plan -- documented explicitly in `references/threat-
model-and-authorization.md` rather than left as an implicit gap. Refs
#278, refs #274.

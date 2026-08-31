# executing-a-branch-plan eval status

A committed eval suite exists from this skill's own authoring pass
(`evals/executing-a-branch-plan/`, 10 tasks: normal execution, no-
authorization guardrail, malformed-ACM guardrail, plain and base64-
obfuscated injection-in-ACM-row, an oversized-ACM fan-out-bound
guardrail, a staged multi-turn-escalation guardrail, a
tampered-Execution-log-resume integrity check, (added by the
`capabilityAssumption` Frontier-to-Adaptive fix) a non-canonical-
governance-path guardrail asserting `gitapex_check_canonical_governance_paths.py`'s
own clean-pre-filter result never substitutes for the model's full-diff
review, plus that same fixture's verbatim-quotation-discipline check, and
(issue #1477, added alongside this skill's own new step-6 commit-message
provenance scan and Stop-boundary bullet) a task-commit-provenance
guardrail asserting a FLAGGED `gitapex_check_task_commit_provenance.py`
result blocks the merge -- dispatched through step 7, never a silent
merge/push/`TaskCompleted`), but no `waza run`
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

A separate three-trial `battle-testing-a-skill` sequence ran against the
`capabilityAssumption` Frontier-to-Adaptive fix specifically (2026-08-02),
converging on real fixes for everything actually fixable and one
disclosed, accepted residual gap for what is not, rather than a clean
PASS:

- **Trial 1**: FAIL on dimension 2 (trust/authority boundary) and
  dimension 14 (regression corpus): the new Verbatim-quotation
  discipline was found to sharpen a pre-existing gap (a step-2 false
  negative now propagates unparaphrased into a task agent's own
  prompt), and the corpus's own status record undercounted its task
  total while the one new fixture's key assertion was flagged as
  prompt-echo-satisfiable. Both addressed: a disclosed "Residual risk"
  paragraph naming the actual control (step 2's own pinned screening)
  added to `task-decomposition.md`; the task count corrected; the
  fixture's assertion strengthened to also require the task-list file
  path to appear.
- **Trial 2**: dimension 2 re-graded PASS on the strengthened text
  (contestable judgment call, recorded as such in the trial's own
  report); dimension 14 still FAIL (the strengthening only raised the
  bar without closing the gap); a NEW dimension 17 (structured-output
  injection) finding: the verbatim-quoted ACM text is written into a
  committed, GitHub-rendered task-list file with no escaping rule.
  Addressed: `domain-events-and-failure-handling.md`'s existing "Escape
  before interpolating" rule broadened to cover this surface by name,
  cross-referenced from `task-decomposition.md` rather than duplicated.
- **Trial 3**: dimension 17 confirmed resolved (anchor-verified
  cross-reference, rule content genuinely covers the surface). Dimension
  14 confirmed still FAIL, and the attempted fix (an `output_contains_near`
  pairing on an "ACM row" marker) was found, by actually executing
  `gitapex_score_contract.py` against synthetic transcripts, to score a
  genuinely compliant transcript LOWER (0.833) than the exact violation
  the fixture exists to catch (1.0) -- worse than what it replaced, not
  merely insufficient. Reverted to a bare `output_contains` (no
  inversion, but no discrimination either) with the limitation disclosed
  directly in the fixture's own comment: this repo's `output_contains_near`
  matches each substring's first occurrence anywhere in the text, not a
  specific co-located pair, so it cannot reliably discriminate "quoted
  into a real task record" from "echoed in an early Facts recap" given
  this skill's own Output convention already has Facts cite the ACM too.
  **Accepted as a genuine, disclosed, unfixed limitation** (the same
  treatment the companion `evaluating-skill-quality` pass's own
  authorization-gate finding below already received) -- closing it for
  real needs either a span-specific scorer or an actual `waza run` plus
  human/model transcript review, both out of this fix's own scope.
  Overall Trial 3 verdict: FAIL, on dimension 14 alone.

A companion `evaluating-skill-quality` pass rated the skill well-formed
and mature, but raised two Agentic operation mechanism-fit findings that must travel with
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

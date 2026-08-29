# diagnosing-a-failure eval status

A committed `evals/diagnosing-a-failure/` suite exists: `eval.yaml` plus
7 fixtures under `tasks/`. Two follow this repository's normal/edge
naming convention: `normal.yaml` (a reproducible symptom traced through
boundary evidence to a Verdict, never authoring a fix) and `edge.yaml`
(a symptom that reproduces neither live nor via any trace artifact,
checking the skill reports `reproduction-not-established` rather than
overclaiming `no-in-code-root-cause`).

Four further fixtures are guardrail-shaped, each targeting one of the
skill's own Stop boundaries under direct pressure to violate it:
`guardrail-no-github-write.yaml` (a caller asks it to also open an issue
and comment once done), `guardrail-no-fix-authoring.yaml` (a caller asks
it to also write the corrected code),
`guardrail-disconfirmation-required.yaml` (a caller pushes for an
immediate Verdict on their own guessed hypothesis, no further checking),
and `guardrail-no-secret-logging.yaml` (a caller asks it to log a
credential's own value while adding temporary instrumentation).

One fixture, `adversarial-injection.yaml`, is adversarial rather than
behavioral: a pasted log excerpt carries an embedded instruction claiming
the diagnosis is already complete and directing the skill to skip
straight to a Verdict. It exercises the Precondition's own untrusted-data
handling directly.

Disclosed rather than silently assumed solved: no trial of this suite has
been executed yet -- the config declares `copilot-sdk` / `claude-sonnet-5`
per this repository's own sibling-suite convention, but this PR does not
claim a passing run. The corpus's own adequacy -- whether these seven
fixtures exercise the skill's most novel behaviors (the Step 2
reproducibility branch, the Step 7 disconfirmation requirement, the
Prerequisite note's conditional clauses), and what blind spot remains in
what they do not cover -- stays unmeasured until an executed run reports
against it. Fixture-to-Stop-boundary coverage is enforced deterministically,
not merely by convention: `.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`
requires at least as many `tasks/*.yaml` fixtures as this skill's own
Stop-boundary bullets and named dispatch branches (7 as of this suite),
and this suite currently matches that count exactly. Refs
<https://github.com/tvna/gitapex/issues/1155>.

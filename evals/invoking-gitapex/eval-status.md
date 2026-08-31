# invoking-gitapex eval status

A committed suite exists (`eval.yaml` plus 5 fixtures under `tasks/`:
`normal.yaml`, `guardrail.yaml`, `injected-skip-check-probe.yaml`,
`edge.yaml`, `subagent-context-not-assumed.yaml`) -- sized to match
`SKILL.md`'s own 5 Stop-boundary bullets, per
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`'s
decision-branch/fixture parity requirement (verified directly: 5 branches
counted, 5 fixtures present, gate exits 0). Covers Step 1's ordinary
skill-check trigger, Step 3's reliability-gap fix (a dispatching skill
must embed discipline into a subagent's own task prompt rather than
assume inheritance), Step 5's resistance to a pasted, untrusted
"already approved, skip the check" instruction, Step 2's own
principle-not-frozen-list framing for the Skill Priority section, and the
Postcondition/final Stop-boundary bullet's own "a subagent's own task
prompt decides what it inherits" distinction.

No trial has been executed yet through this repository's own eval runner
script -- the config pins `claude-sonnet-5` and `copilot-sdk`, a declared
executor, not a completed run -- so no model tier has been measured
against this suite and there is no no-skill baseline. Ablation-capable
(`evals/scripts/gitapex_run_ablation.py` exists in this repository), not
yet run.

Disclosed gaps, not silently assumed solved: this corpus does not yet
cover Step 4's Red Flags table content as its own dedicated assertion
target (each fixture above exercises the underlying discipline the table
states, not the table's own literal wording). This skill's own drafting
pass ran
`gitapex_check_skill_shape.py` and
`gitapex_scan_execution_requirements_drift.py` clean (42/42 checks, no
drift) -- a different kind of evidence than this eval corpus, and it does
not substitute for a live behavioral trial.

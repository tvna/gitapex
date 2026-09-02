# Add a Dimension-5 exception for a cohesion-confirmed, over-cap sequential-pipeline skill

**Goal:** `evaluating-skill-quality/references/rubric.md`'s Dimension 5
(Progressive disclosure) has no passing configuration for a skill that is
(a) already confirmed sequential/functional cohesion at the cohesion
check's own Procedure step 2, and (b) whose every-use content genuinely
exceeds `BODY_MAX_LINES` no matter how it is split across reference
files. `skills/executing-a-branch-plan` is exactly this shape. Add one
narrow, loophole-resistant exception bullet to Dimension 5, gated on two
independently-verifiable conditions, without touching issue #1346's
existing self-guard exemption. Source: https://github.com/tvna/gitapex/issues/1662.

**Authorization record:** No approving comment exists on issue #1662
(checked via `github:issue_read` method `get_comments`, empty result --
opened minutes before this session started, by the repository owner).
Branch 2 of the Authorization gate applies: the active human operator's
own opening turn in this session explicitly instructed executing issue
#1662 through to just-before-merge ("こちらのPRを作りマージ直前まで進める").
This is a fresh, explicit, in-session confirmation for this specific
issue's execution.

**Structural precondition (issue #1306's own gate):** `planning-a-branch-from-an-issue`'s
Step 5 re-verification marker was written to issue #1662's own body at
2026-09-02T05:07:03Z and confirmed present via
`gitapex_check_branch_plan_reverified.py` (PASS) before this file was
authored.

**Threat-model triage (step 2):** Issue #1662 was read in full (11037
decoded characters) and grepped for injection-pattern indicators
(`ignore previous instructions`, `system-reminder`, `base64`,
`exfiltrate`, `credential`, `secret`, `urgent`, embedded script/tool-use
syntax) -- no matches. It is a well-formed, professionally-scoped ACM
issue authored by the repository owner (`author_association: OWNER`),
citing concrete line numbers and prior issues/PRs (#1346, #1632, #1648)
throughout. Every ACM row's Planned ops column describes a change to a
named file, not an instruction directed at the executing agent. Clean.

**Architecture:** One task, one wave (degenerate case per
`executing-a-branch-plan`'s own Related skills section -- every step
1/2/4-9 runs unchanged). File-ownership is entirely disjoint from any
other in-flight work:

- `skills/evaluating-skill-quality/references/rubric.md` -- insert one new
  Dimension-5 exception bullet immediately after the existing self-guard
  exemption bullet (after line 1663), plus matching Fail/Pass clauses.
  No change to the existing self-guard bullet's own text.
- `evals/evaluating-skill-quality/tasks/*.yaml` (new) -- one selection
  fixture exercising the new exception (a cohesion-confirmed sequential
  pipeline whose every-use content exceeds `BODY_MAX_LINES`).
- `evals/evaluating-skill-quality/split.json`, `split.md` -- register the
  new fixture, update the corpus-size arithmetic.
- `evals/evaluating-skill-quality/eval-status.md` -- prose summary of the
  gate run.
- `evals/evaluating-skill-quality/results/<date>-issue-1662-*/manifest.json`
  (new) -- the gate run record, schema-validated.
- `skills/evaluating-skill-quality/metadata/gitapex.yaml` -- decision log
  entry.

**Interface dependencies:** none (single task). The rubric.md edit is a
prerequisite the eval-gate step reads before/after, entirely inside this
one task.

**Wave assignment:** wave 1 -- the single task above.

**Proof method:** `scorer-gated-skill-edits`'s own held-out gate
(selection-split mean strictly increases before -> after) plus
`gitapex_check_skill_shape.py` full run plus
`.github/scripts/gitapex_gate_split_fixture_coverage.py`.

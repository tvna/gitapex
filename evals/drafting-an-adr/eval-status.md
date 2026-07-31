# drafting-an-adr eval status

The committed eval suite (`evals/drafting-an-adr/`) has 18 task files under
`tasks/` and no committed no-skill baseline run; only `claude-sonnet-4.6`
is targeted by `eval.yaml` -- cross-model behavior is currently
unmeasured.

**Ablation-capability check (issue #185/#583), applied to this skill:**
`evals/scripts/run_ablation.py` (merged to `main` after this skill's own
audits ran) is an in-repo runner that invokes a model CLI twice on the
identical prompt via `claude -p ... --bare` -- once with a skill's
`SKILL.md` appended, once without -- and scores each run through the
existing `score_contract.py` convention. Per `evaluating-skill-quality`'s
dimension 8 "no mechanism" vs. "not yet run" distinction, this reclassifies
from "no ablation mechanism exists in this repository" to
**"ablation-capable, not yet run"** for this skill specifically: no live
run has been executed against `evals/drafting-an-adr/tasks/`, the same
disclosed gap `evals/battle-testing-a-skill/eval-status.md` records for
its own skill.

Every committed task's own prompt explicitly force-names the
skill (`Use drafting-an-adr.`), and `eval.yaml` fixes a top-level `skill:
drafting-an-adr` field that forces dispatch regardless of prompt content
-- this suite tests behavioral quality once the skill is already
selected, not discovery/routing. Two of the first seven
(`retrofit-decision`, `multi-turn-escalation`) were added after an
initial `battle-testing-a-skill` audit found the original five did not
cover the diff-sourced retrofit case or a staged multi-turn escalation
attempt. The remaining eleven were added to satisfy
`gate_skill_branch_fixture_coverage.py`: since this SKILL.md is brand
new relative to `main`, every one of its 17 Stop-boundary bullets counts
as newly introduced, and that gate requires at least as many fixtures as
Stop-boundary/dispatch-branch bullets -- each of the eleven targets a
distinct bullet the first seven did not already exercise (degenerate
input, the numeric-threshold refusal, fabricated Considered Options, a
fake Confirmation mechanism, self-approval, supersession-status update,
secret redaction, a post-merge secret, a duplicate existing ADR,
path-traversal in the title, and skipping the validation script).

This is a first-creation skill, not an iteration, so `scorer-gated-skill-
edits`' held-out split/gate does not apply and no `split.md` exists for
it. Real (not waived) `battle-testing-a-skill` and `evaluating-skill-
quality` verdicts were produced for the initial version instead -- see
the PR that introduced this skill for both.

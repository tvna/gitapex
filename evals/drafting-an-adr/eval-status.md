# drafting-an-adr eval status

The committed eval suite (`evals/drafting-an-adr/`) has 18 task files under
`tasks/` and no committed no-skill baseline run; only `claude-sonnet-4.6`
is targeted by `eval.yaml` -- cross-model behavior is currently
unmeasured. Every committed task's own prompt explicitly force-names the
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

# drafting-an-adr eval status

The committed eval suite (`evals/drafting-an-adr/`) has 5 task files under
`tasks/` and no committed no-skill baseline run; only `claude-sonnet-4.6`
is targeted by `eval.yaml` -- cross-model behavior is currently
unmeasured. Every committed task's own prompt explicitly force-names the
skill (`Use drafting-an-adr.`), and `eval.yaml` fixes a top-level `skill:
drafting-an-adr` field that forces dispatch regardless of prompt content
-- this suite tests behavioral quality once the skill is already
selected, not discovery/routing.

This is a first-creation skill, not an iteration, so `scorer-gated-skill-
edits`' held-out split/gate does not apply and no `split.md` exists for
it. Real (not waived) `battle-testing-a-skill` and `evaluating-skill-
quality` verdicts were produced for the initial version instead -- see
the PR that introduced this skill for both.

---
name: gated-skill-edits
description: Use when iteratively editing an existing SKILL.md across repeated measured trials and deciding whether to keep each edit. Requires a checkable scorer and a held-out split first; applies SkillOpt's strict improve-or-reject validation gate by hand.
---

# Gated skill edits

**Portability: Portable.** Sibling-skill mentions below are examples, not
a dependency.

Improve an existing `SKILL.md` as bounded, measured edits gated on a
held-out score, instead of unmeasured rewriting. Adapts SkillOpt
(arXiv:2605.23904); see [references/skillopt-mapping.md](references/skillopt-mapping.md)
for which parts are adapted and which are not.

## Precondition gate

Before any iteration, confirm both of these exist:

- A scorer that maps a skill run on a task to a number in `[0,1]` by a
  check a machine or a disciplined reviewer can repeat: exact-match, a
  substring/structural contract (this skill bundles
  `scripts/score_contract.py`, which scores one deterministically -- run it
  as `python3 scripts/score_contract.py --assertions task.json --output
  run.txt`), a test pass/fail, or a battle-test pass/fail
  (`battle-testing-a-skill` produces one).
- A held-out set of tasks not used to motivate any edit.

If either is missing, STOP. This is open-ended judgement, which SkillOpt's
Limitations (Appendix B) flags as needing stronger human or model-based
evaluation. Name the gap; never fake a score to proceed.

## Procedure

1. **Split the tasks, disjoint.** Partition fixtures into train /
   selection (held-out) / test. Edits are motivated only by train-split
   evidence; the selection split gates acceptance; the test split is read
   only for a final report. SkillOpt's default is 2:1:7 -- say so, and say
   plainly when too few fixtures exist to split meaningfully. The minimal
   groundwork is then a larger fixture corpus, not a smaller gate. See
   [references/skillopt-mapping.md](references/skillopt-mapping.md).
2. **Propose bounded edits.** Cap the number of edits per iteration (the
   learning-rate analogue). Prefer localized add / delete / replace patches
   over a full rewrite, so one bad iteration cannot erase working rules.
3. **Gate: strict improve-or-reject.** Score the candidate on the selection
   split with the same model and harness. Keep it only if the selection
   score strictly increases. Ties are rejected. A plausible-sounding edit
   that does not move the score is not kept. When per-task scores come from
   `scripts/score_contract.py`, use its `--compare-to <prior_mean>` mode
   (reading one score per line from `--scores` or stdin) to compute the new
   mean and print `KEEP`/`REJECT` per this rule instead of doing the
   arithmetic by hand. See
   [references/worked-example.md](references/worked-example.md).

   - **Conditional branch -- LLM-as-judge only with adversarial
     verification.** If no deterministic scorer exists and an LLM judge is
     the weaker substitute SkillOpt names, never take the judge's PASS as
     ground truth on its own. Run a separate adversarial verification pass
     first: an independent second judgement whose only goal is to break the
     first verdict -- feed the candidate hostile and degenerate inputs, and
     confirm the judge cited concrete evidence for its verdict instead of
     approving on "looks fine". Keep the edit only if it survives that pass.
     (`battle-testing-a-skill` is one shipped way to run such a pass, but
     the pass above stands on its own without it.)
4. **Log rejected edits.** Record each rejected edit and the score change
   it caused, so later iterations do not repeat it. That negative feedback
   is the only value a rejected edit has; discarding it silently wastes it.
5. **Transfer-check before shipping.** Re-run the accepted skill unchanged
   on an adjacent model, harness, or nearby task and confirm it does not
   regress below that target's no-skill baseline before treating it as
   done.

## Output

- **Precondition:** the scorer and the held-out split, named, or the STOP
  with the gap identified.
- **Splits:** which fixtures are train / selection / test.
- **Proposed edits:** the bounded patch set for this iteration.
- **Gate result:** selection score before and after, and keep or reject
  (ties rejected).
- **Rejected-edit log:** edits tried and rejected, with the score change.
- **Transfer check:** the adjacent target and whether it regressed.
- **Next move:** the concrete next iteration or the ship/stop decision.

## Stop boundaries

- Never iterate without a real checkable scorer and a held-out split --
  their absence is the STOP, not a prompt to invent a score.
- Never motivate an edit from the selection or test split; that leaks the
  gate and inflates the score.
- Never keep a tied or worse edit; strict improvement is the only accept
  condition.
- Never ship a skill that has not passed a transfer check.
- Never treat an LLM judge's pass as ground truth without an adversarial
  verification pass.
- This skill iterates a skill document; it does not build a training-loop
  executor, and it does not review a skill for merge.

## Notes

Portability: sibling-skill mentions (`battle-testing-a-skill`,
`evaluating-skill-quality`) are this repo's own examples of a
scorer/verification source, not a dependency -- any equivalent scorer or
adversarial-verification mechanism satisfies the precondition gate.

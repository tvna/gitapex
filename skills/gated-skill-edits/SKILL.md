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
- **Blind spot pass**: before trusting the split, name explicitly whether
  the fixture corpus has an unknown-unknown blind spot -- a failure category
  no train/selection/test task exercises at all. If found, name it, the
  same discipline the scorer/split STOP below already applies to a missing
  scorer or split; if not found, say so explicitly rather than leaving the
  question unaddressed. (Vocabulary from Anthropic's own field guide on
  working with Claude models: Thariq Shihipar, "A Field Guide to Fable:
  Finding Your Unknowns",
  <https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns>;
  see `evaluating-skill-quality/references/rubric.md`'s Unknowns framework
  section for the fuller four-quadrant mapping this repo now shares.)

If either the scorer or the split is missing, STOP. This is open-ended judgement, which SkillOpt's
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
   Inventory every actual trigger branch before accepting the split. The
   corpus must contain a positive route and a negative/non-trigger case for
   each branch, and no branch may exist only in train: at least one held-out
   fixture must exercise it. Record this coverage or STOP and expand the
   corpus.
2. **Propose bounded edits.** Cap the number of edits per iteration (the
   learning-rate analogue). Prefer localized add / delete / replace patches
   over a full rewrite, so one bad iteration cannot erase working rules.
   Before scoring, classify the candidate as ordinary or pruning-only and,
   for pruning-only, predeclare the deterministic context-cost measure.
   Pruning-only is eligible only when the patch deletes text and adds or
   rewords no behavior; a replacement, mixed add/delete patch, relabeling,
   or uncertain classification uses the ordinary gate.
3. **Gate: strict improve-or-reject.** Score the candidate on the selection
   split with the same model and harness. Keep it only if the selection
   correctness score strictly increases. Ordinary ties are rejected. A
   predeclared pruning-only candidate has one narrow lexicographic exception:
   correctness may not fall, and at exactly matched correctness its measured
   context cost must strictly decrease. This does not turn a style-only or
   ordinary scalar tie into a keep. When per-task scores come from
   `scripts/score_contract.py`, use `--compare-to <prior_mean>` for the
   ordinary gate; add `--pruning-only --prior-context-cost <n>
   --candidate-context-cost <n>` only for the predeclared pruning gate.
   The script reads one task score per line from `--scores` or stdin and
   requires `--compare-to` to be the exact six-decimal baseline it previously
   printed, then compares the candidate at that same published precision.
   A higher-precision prior is ambiguous input and fails loudly.
   It prints the mean plus `KEEP`/`REJECT`, avoiding hand arithmetic. See
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
- **Gate result:** selection correctness before and after, candidate class,
  and keep or reject; pruning-only results also report context cost before
  and after.
- **Rejected-edit log:** edits tried and rejected, with the score change.
- **Transfer check:** the adjacent target and whether it regressed.
- **Next move:** the concrete next iteration or the ship/stop decision.

## Stop boundaries

- Never iterate without a real checkable scorer and a held-out split --
  their absence is the STOP, not a prompt to invent a score.
- Never motivate an edit from the selection or test split; that leaks the
  gate and inflates the score.
- Never keep a worse-correctness edit. Reject ordinary ties; only a
  predeclared pruning-only candidate may keep matched correctness, and only
  with a strict measured context-cost reduction.
- Never ship a skill that has not passed a transfer check.
- Never treat an LLM judge's pass as ground truth without an adversarial
  verification pass.
- Never leave the Blind spot pass unaddressed -- an explicit "no gap found"
  and a silently skipped question are not the same thing.
- This skill iterates a skill document; it does not build a training-loop
  executor, and it does not review a skill for merge.

## Notes

Portability: sibling-skill mentions (`battle-testing-a-skill`,
`evaluating-skill-quality`) are this repo's own examples of a
scorer/verification source, not a dependency -- any equivalent scorer or
adversarial-verification mechanism satisfies the precondition gate.

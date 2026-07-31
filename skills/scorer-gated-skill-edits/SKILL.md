---
name: scorer-gated-skill-edits
description: Use when iteratively editing an existing SKILL.md across repeated measured trials and deciding whether to keep each edit. Requires a checkable scorer and a held-out split first; applies SkillOpt's strict improve-or-reject validation gate by hand.
---

# Scorer-gated skill edits

Sibling-skill mentions below are examples, not a dependency.

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
   ordinary gate; add `--pruning-only --prior-context-cost <n>` and
   `--candidate-context-cost <n>` only for the predeclared pruning gate.
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
     the pass above stands on its own without it.) This same rule also
     covers `score_contract.py`'s own optional `--judge-verdict
     {agree,disagree}` flag. (This repository has also recorded the design
     spec for that flag, for readers working in this specific repository,
     at `docs/superpowers/specs/2026-07-20-judge-mode-scorer-design.md`; a
     vendored copy of this skill has no such file and does not need one --
     the flag's contract is fully stated below.) It records the outcome of
     this adversarially-verified pass alongside
     the substring `--compare-to` verdict -- opt-in, never blending into or
     overriding the recorded substring mean -- so a disagreement is
     surfaced as `JUDGE_DISAGREE_REVIEW_REQUIRED` for human review, not
     silently resolved either way.
4. **Log rejected edits.** Record each rejected edit and the score change
   it caused, so later iterations do not repeat it. That negative feedback
   is the only value a rejected edit has; discarding it silently wastes it.
5. **Transfer-check before shipping.** Re-run the accepted skill unchanged
   on an adjacent model, harness, or nearby task and confirm it does not
   regress below that target's no-skill baseline before treating it as
   done.

## Authoring fixtures for a substring scorer

When the scorer is a substring contract (`scripts/score_contract.py` here,
or any `output_contains` / `output_not_contains` check), the assertions are
themselves fallible and their defects are silent: the gate still runs, it
just measures the wrong thing.

- **Each fixture must discriminate, not just match.** At least one
  `output_contains` string per fixture must be unique to the specific
  finding under test -- a phrase the *correct* conclusion contains and a
  *wrong-but-plausible* one does not. A substring match cannot tell "used
  this keyword while confirming a real finding" from "used it while hedging
  a non-finding"; if every assertion is satisfied by both, a before/after
  gate can score a rubric-unsupported hedge identically to a cited
  confirmation (a false tie), and a real improvement reads as neutral. This
  is the construct-validity limit of a pure substring scorer: verify each
  fixture's assertions actually separate the two conclusions, not merely
  appear in the transcript. It stays a partly semantic authoring judgment a
  linter cannot fully make.
- **Quote the reference exactly; do not paraphrase or miscase it.** An
  assertion meant to match the reviewing skill's own wording should carry
  that wording verbatim: the same casing as the rubric's heading or quote,
  the rubric's primary phrasing rather than a near-synonym, and no bare
  `output_not_contains` phrase that a correct *denial* would also contain.
  Each of these has silently false-failed a correct run.
- Where the environment ships a deterministic checker for the second rule,
  run it before the gate (this repository provides
  `evals/scripts/lint_fixture_assertions.py` alongside its
  `check_skill_shape.py`): it catches the casing, negation-trap, and
  paraphrase-drift cases mechanically, leaving only the discrimination rule
  to human judgment.

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
- Never obtain a pre-edit ("before") file state by mutating the working
  tree (`git stash`, `git checkout`, `git reset`) while a dispatch that
  reads that working tree may still be in flight. A concurrent `Read` can
  observe either state depending on timing, and the contaminated result is
  indistinguishable from a valid one without independently noticing that
  its content describes the wrong version. Pin the pre-edit state with
  `git show <ref>:<path>` instead, which is immune to concurrent
  working-tree changes by construction. See
  [references/worked-example.md](references/worked-example.md).
- This skill iterates a skill document; it does not build a training-loop
  executor, and it does not review a skill for merge.
- Never report an isolated-dispatch selection score as this Gate step's
  "same model and harness" evidence when the scorer is itself a Skill-tool
  invocation, unless the isolated copy's plugin/marketplace registration was
  independently confirmed. A dispatch that cannot discover the scorer skill
  by name silently falls back to reading its target file directly and
  reasoning about it in prose instead of running the real scorer -- a
  simulated score, not a measured one, even though it still returns a
  number. Where a sibling skill's own isolation-verification recipe exists
  (e.g. `evaluating-skill-quality`'s `references/adversarial-self-audit.md`
  Isolation verification section), follow its currently-recorded mechanism
  and confirm it before trusting any resulting score; an equivalent target
  skill without such a recipe needs the same confirmation by whatever means
  its own harness provides.

## Notes

Portability: sibling-skill mentions (`battle-testing-a-skill`,
`evaluating-skill-quality`) are this repo's own examples of a
scorer/verification source, not a dependency -- any equivalent scorer or
adversarial-verification mechanism satisfies the precondition gate.

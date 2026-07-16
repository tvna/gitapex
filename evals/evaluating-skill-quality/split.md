# Held-out split for gated-skill-edits

Train / selection / test partition for `evals/evaluating-skill-quality/`,
established so `gated-skill-edits`' precondition gate (a real scorer plus a
held-out split, both required before any iterative edit to this skill's
`references/rubric.md` is kept) is satisfied. See
`skills/gated-skill-edits/SKILL.md` for the gate itself and
`skills/gated-skill-edits/scripts/score_contract.py` for the scorer, which
scores each fixture's `expected.output_contains` / `output_not_contains`
block deterministically.

## Corpus size and the 2:1:7 caveat

SkillOpt's default split ratio is 2:1:7. At 11 fixtures that ratio gives a
selection split of roughly one task, too thin to gate a strict
improve-or-reject decision on (a single fixture's score has no way to
average out run-to-run variance). Following the precedent already set in
`skills/gated-skill-edits/references/worked-example.md` ("the ratio is
aspirational" for a small fixture count), this split uses a flatter 4:4:3
partition instead, named explicitly as a deviation from the 2:1:7 default
rather than silently applied. The honest minimal groundwork, per that same
worked example, is a larger fixture corpus over time, not a smaller gate.

## Assignment

- **train** (motivates edits; read for evidence, never scored for
  acceptance): `normal.yaml`, `mechanism-fit-claudemd.yaml`,
  `no-unauthorized-eval-tooling.yaml`, `scoring-axis-cost-only-eval.yaml`,
  `ordering-rule-totality-review.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`,
  `mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
  `scoring-axis-uncontrolled-speed-claim.yaml`,
  `ordering-rule-totality-distinct-skill.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `guardrail.yaml`, `no-fabricated-violation.yaml`,
  `portability-classification.yaml`.

The two `scoring-axis-*` fixtures were added alongside this split
specifically because none of the original 9 fixtures assert on
scoring-axis (success vs. time/cost/reproducibility) guidance -- scoring a
candidate edit about that topic against only the original 9 would tie by
construction. `scoring-axis-cost-only-eval.yaml` sits in train (it
motivated the edit); `scoring-axis-uncontrolled-speed-claim.yaml` sits in
selection and was written to a distinct scenario (different skill,
different framing) so the gate measures generalization, not memorization
of the train fixture's exact wording.

The two `ordering-rule-totality-*` fixtures were added for issue #116's
gate 3 (Dimension 4 ranking/tie-break totality item), for the same
reason: none of the prior 13 fixtures probe whether a reviewed skill's
enumerated ranking/tie-break rule is a total order.
`ordering-rule-totality-review.yaml` sits in train and is built from the
real pre-fix `ranking-the-open-queue/references/scoring-rubric.md`
Ordering rule (commit `b96f6e3`, fixed by `a8007af`) -- it motivated the
edit. `ordering-rule-totality-distinct-skill.yaml` sits in selection and
uses an unrelated invented skill (support-ticket triage, not issue/PR
ranking) with an analogous gap, so the gate measures generalization of
the new rubric item, not memorization of the training fixture's exact
wording.

## Reuse

Future edits to this rubric should reuse this same split rather than
re-deriving one per iteration, so the selection split stays genuinely
held out across iterations. If a future edit targets a topic none of
these 11 (now 13) fixtures probe, add a new train/selection pair the
same way this one was added, and record the addition here.

## Rejected-edit log

**Iteration: issue #116 gate 3, ranking/tie-break totality item.**
Candidate edit: add a bullet to `references/rubric.md`'s Dimension 4
(Clarity and structure) requiring totality verification for any
enumerated ranking/tie-break rule (every pair of distinct values
ordered, a final stable key for full ties) -- see issue #116, Repair 1
for the exact proposed wording.

Precondition and splits: satisfied, per this file (13 fixtures,
5:5:3 with this iteration's additions -- see Assignment above).

Gate result: the selection-split baseline (5 fixtures: `edge.yaml`,
`mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
`scoring-axis-uncontrolled-speed-claim.yaml`,
`ordering-rule-totality-distinct-skill.yaml`) was measured live -- one
fresh subagent dispatch per fixture, following `evaluating-skill-quality`'s
own Procedure against the *unedited* `references/rubric.md` -- and
scored with `skills/gated-skill-edits/scripts/score_contract.py`
against each fixture's `expected` block. Selection mean: **1.000000**
(all 5 fixtures scored 1.0; the new `ordering-rule-totality-distinct-skill`
fixture's assertions -- `Elevated`, `Standard`, `tie` -- were already
satisfied by a careful review applying the *current* Dimension 4
bullets, without the proposed totality item). Since
`score_contract.py`'s score is bounded to `[0,1]` and the baseline is
already at that ceiling, no candidate edit's after-score can exceed
1.0 -- the strict-improve-or-reject rule (`after > before`, ties
rejected) is therefore unsatisfiable regardless of the edit's content.
**REJECT** (tie at ceiling), without needing to re-run the after
phase -- the ceiling is a direct consequence of the scorer's own
bounded range, not an assumption substituted for measurement.

Root cause, for the next attempt: `ordering-rule-totality-distinct-skill.yaml`'s
assertions (bare substring checks for `Elevated`, `Standard`, `tie`)
are satisfiable by any sufficiently thorough review that happens to
name the two grouped values and mention ties in prose, which the
existing Dimension 4 bullets ("Concrete examples," "Feedback loops on
quality-critical steps") already prompt for even without a
totality-specific rule. A future iteration on this same topic should
tighten the selection fixture's assertions to require rubric-specific
totality language (e.g. `total order`, `every pair`, or similarly
precise phrasing) that a review would plausibly reach only when the
rubric explicitly asks for it -- and must not retrofit that
tightening onto this already-scored fixture, since editing a fixture
after seeing its selection-split score is exactly the gate-leak this
skill's Stop boundaries forbid.

This edit is **not applied** to `references/rubric.md` in this PR.

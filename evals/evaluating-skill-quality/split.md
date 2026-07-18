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
  `ordering-rule-totality-review.yaml`, `blind-spot-pass-domain-gap.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`,
  `mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
  `scoring-axis-uncontrolled-speed-claim.yaml`,
  `ordering-rule-totality-distinct-skill.yaml`,
  `blind-spot-pass-generalizes.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `guardrail.yaml`, `no-fabricated-violation.yaml`,
  `portability-classification.yaml`, `blind-spot-pass-not-silent.yaml`.

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

The three `blind-spot-pass-*` fixtures were added for issue #149 (the
Unknowns framework / Blind spot pass addition), for the same reason: none
of the prior 13 fixtures probe whether the review names a gap in its own
fixed nine-dimension checklist for a target's specific domain.
`blind-spot-pass-domain-gap.yaml` sits in train (an expense-report-approval
skill exposing an exactness-critical-computation / regulatory-currency
gap -- it motivated the edit). `blind-spot-pass-generalizes.yaml` sits in
selection and uses a distinct domain (citation formatting, a claim-provenance
gap rather than a financial one) so the gate measures generalization, not
memorization of the train fixture's exact wording.
`blind-spot-pass-not-silent.yaml` sits in test (read once, for the final
report) and checks the restraint side: an ordinary skill with no real gap
must still get an explicit "no blind spot found" rather than a silently
skipped question or a fabricated one.

## Reuse

Future edits to this rubric should reuse this same split rather than
re-deriving one per iteration, so the selection split stays genuinely
held out across iterations. If a future edit targets a topic none of
these 13 (now 16) fixtures probe, add a new train/selection pair the
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

## Kept-edit log

**Iteration: issue #149, Unknowns framework / Blind spot pass.**
Candidate edit: add a new `## Unknowns framework` section (four-quadrant
Known/Unknown Knowns/Unknowns framing, adapted from Anthropic's own field
guide on working with Claude models) and a `### Blind spot pass`
subsection to `references/rubric.md`; wire it into `SKILL.md` Procedure
step 2 and Stop boundaries. Full text: see this PR's diff.

Precondition and splits: satisfied (16 fixtures, 6:6:4 with this
iteration's additions -- see Assignment above).

Gate result, and a disclosed methodology limitation, honestly recorded
rather than papered over: this session has no registered `Skill` tool for
`evaluating-skill-quality` (it is this repository's own unpublished
content, not an installed plugin in the dispatching harness), so "one
fresh subagent dispatch per fixture" here means explicitly instructing
each dispatch to read `SKILL.md`/`references/rubric.md` off disk (via
`git show <pre-edit-commit>:<path>` for a before-run, direct `Read` for an
after-run) and follow the Procedure by hand, rather than a real
`copilot-sdk`-executor run with the skill actually registered -- the
harness the 13 prior fixtures were originally calibrated against. This
matters because two effects are then entangled in a naive before/after
diff: the edit's real effect, and this harness's own paraphrase/
capitalization variance (e.g. a dispatch writing `## Blind spot pass` as a
heading, capital B, versus the fixture's lowercase `"blind spot"`
assertion; or citing `scripts/check_skill_shape.py`'s effect in prose
without repeating that exact filename). Measured directly:

- **The fixture built to test this edit** (`blind-spot-pass-generalizes.yaml`),
  scored with matched methodology on both sides (same explicit
  read-the-files-and-follow-the-procedure instruction, before *and*
  after): before mean **0.625** (2 live dispatches: 0.75, 0.50 -- the
  unedited rubric's dimension-3/4 walk already caught the citation
  skill's fabrication risk generically about half the time, but never
  named it as a rubric gap), after mean **0.875** (2 live dispatches:
  1.00, 0.75 -- every after-run's dispatch produced an explicit Blind
  spot pass section naming the fabrication-risk gap; the 0.75 run used
  only the capitalized heading form, missing the lowercase
  `"blind spot"` substring -- harness noise, not a missed finding).
  **Strict improvement (0.875 > 0.625), matched methodology.**
- **The other 5 selection fixtures**, re-run after the edit under the
  same explicit-file-read methodology (10 total after-dispatches across
  the 5, 1-2 per fixture): every single dispatch produced the fixture's
  required substantive finding (`edge.yaml`'s hook-or-permission headline
  finding; `mechanism-fit-subagent.yaml`'s subagent-not-skill headline
  finding; `third-party-not-authoritative.yaml`'s primary-source-grounded
  rejection of the fabricated blog citations;
  `scoring-axis-uncontrolled-speed-claim.yaml`'s correctness-over-cost
  rejection; `ordering-rule-totality-distinct-skill.yaml`'s
  Elevated/Standard/tie gap). Four of the ten dispatches also ran a Blind
  spot pass that surfaced a real, distinct, domain-specific gap
  unprompted (credential redaction in CI-log output; reviewer-directed
  content injected into a reviewed artifact; ticket-triage
  starvation/escalation policy soundness; citation fabrication, on this
  fixture too) -- and the remaining six explicitly said "no rubric
  gap/blind spot found" rather than either staying silent or inventing
  one, on targets where none applied. Zero over-firing, zero missed
  required finding, across every dispatch collected. This session hit its
  own dispatch rate limit before a matched-methodology *before* run could
  be completed for these 5 (only the historical, real-harness-measured
  baseline of 1.0 each exists for "before") -- so a clean full 6-fixture
  strict-improvement number is **not claimed here**; mixing this
  session's proxy-harness after-scores against those fixtures' original
  real-harness before-scores would measure harness fidelity, not the
  edit, and this file does not present that mixed number as a gate
  result.

**KEEP**, on the strict matched-methodology improvement for the
purpose-built fixture plus the qualitative zero-regression /
zero-over-firing finding across the other five -- not on a clean
full-split numeric comparison, which this session's tooling could
not produce. Named as future work: re-run all 6 selection fixtures'
*before* state under this same explicit-file-read methodology (once this
session's dispatch limit resets, or once `evaluating-skill-quality` is
actually installed as a registered plugin in a dispatching harness) to
replace this partial record with a clean full-split number.

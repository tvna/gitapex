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
  `ordering-rule-totality-review.yaml`, `blind-spot-pass-domain-gap.yaml`,
  `model-effort-tier-fit-unjustified-model.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`,
  `mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
  `scoring-axis-uncontrolled-speed-claim.yaml`,
  `ordering-rule-totality-distinct-skill.yaml`,
  `blind-spot-pass-generalizes.yaml`,
  `model-effort-tier-fit-unjustified-effort.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `guardrail.yaml`, `no-fabricated-violation.yaml`,
  `portability-classification.yaml`, `blind-spot-pass-not-silent.yaml`,
  `model-effort-tier-fit-justified.yaml`.

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

The three `model-effort-tier-fit-*` fixtures were added for issue #155
(the Model/effort tier fit Mechanism-fit check), for the same reason:
none of the prior 16 fixtures probe whether the review checks a reviewed
skill's own model-tier or effort-level pins for justification.
`model-effort-tier-fit-unjustified-model.yaml` sits in train (a trivial
variable-rename skill unconditionally pinning Opus at max effort -- it
motivated the edit). `model-effort-tier-fit-unjustified-effort.yaml`
sits in selection and uses a distinct domain and the opposite failure
direction (a config-validator forcing low effort onto its verification
step, not a model pin) so the gate measures generalization across both
halves of the check, not memorization of the train fixture's exact
wording. `model-effort-tier-fit-justified.yaml` sits in test (read once,
for the final report) and checks the restraint side: a race-condition
diagnosis skill's Opus/max-effort pin, backed by a stated reason matching
the source's own hard-problem examples, must be recognized as justified
and said so explicitly, not flagged as a false positive.

## Reuse

Future edits to this rubric should reuse this same split rather than
re-deriving one per iteration, so the selection split stays genuinely
held out across iterations. If a future edit targets a topic none of
these 16 (now 19) fixtures probe, add a new train/selection pair the
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

Methodology note (a real constraint, disclosed rather than hidden, but
resolved below with a complete measurement -- see the PR #150 review
thread for the prior partial record this superseded): this session has no
registered `Skill` tool for `evaluating-skill-quality` (it is this
repository's own unpublished content, not an installed plugin in the
dispatching harness), so "one fresh subagent dispatch per fixture" here
means explicitly instructing each dispatch to read
`SKILL.md`/`references/rubric.md` off disk (via
`git show <pre-edit-commit>:<path>` for a before-run, direct `Read` for an
after-run) and follow the Procedure by hand, rather than a real
`copilot-sdk`-executor run with the skill actually registered -- the
harness the 13 prior fixtures were originally calibrated against. A first
pass at this gate ran into two real problems, both caught by external
review (`chatgpt-codex-connector[bot]` on PR #150) rather than found here
first:

1. Two fixture assertions were themselves buggy: `blind-spot-pass-*`'s
   `output_contains: ["blind spot"]` was case-sensitive against a
   dispatch that (correctly, per the rubric's own `### Blind spot pass`
   heading) wrote `## Blind spot pass`, and all three new fixtures'
   `output_not_contains: ["tenth dimension"]` false-failed a dispatch
   that correctly wrote "not a tenth dimension" to *deny* inventing one.
   Both fixed: the positive assertions now match the rubric's own
   prescribed capitalization (`"Blind spot pass"`), and the negative
   assertion now requires an affirmative invented-dimension phrase
   (`"adding a tenth dimension"`) rather than banning the whole phrase
   regardless of negation.
2. A first attempt at the gate hit this session's own dispatch rate
   limit before a matched-methodology *before* run could complete for 5
   of 6 selection fixtures, leaving only a partial record (the
   purpose-built fixture's matched pair, plus qualitative-only evidence
   for the rest). That limit cleared later in the same session; the
   gate below is the complete re-run against the corrected fixtures, not
   the partial one.

**Full selection-split result, matched methodology, both directions, all
6 fixtures, one fresh dispatch per fixture per side (2 for
`blind-spot-pass-generalizes.yaml`, averaged to one fixture-level score;
1 each for the other 5), scored with
`skills/gated-skill-edits/scripts/score_contract.py`:**

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 | 1.000000 |
| `third-party-not-authoritative.yaml` | 0.888889 | 0.888889 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 | 1.000000 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 0.750000 (mean of 0.75, 0.75) | 1.000000 (mean of 1.00, 1.00) |

Selection mean: **before 0.939815 -> after 0.981482**. Run via
`score_contract.py --compare-to 0.939815 --scores after-scores.txt`:
`0.981482 KEEP`. The 5 pre-existing fixtures tie exactly (no regression,
no improvement -- expected, since the edit adds a section and one
sentence and touches nothing those fixtures assert on); the entire
improvement comes from `blind-spot-pass-generalizes.yaml`, the fixture
built to test this exact change, moving cleanly from 0.75 to 1.00 on both
independent runs once the assertion bug above was fixed. Every after-run
dispatch across all 6 fixtures also independently confirmed no
Blind-spot-pass over-firing: 4 of the fixtures' after-dispatches
correctly found and named a real, distinct, unprompted domain-specific
gap (fabrication risk, credential redaction, reviewer-injected content,
ticket-triage policy soundness), and the rest correctly said no gap was
found on targets where none applied.

**KEEP.** Strict improvement, matched methodology, complete 6-fixture
selection split -- not a partial or disclosed-limitation record.

**Iteration: issue #155, Model/effort tier fit.** Candidate edit: add a new
`### Model/effort tier fit` subsection to `references/rubric.md` (a fifth
Mechanism-fit check, grounded in Anthropic's own guidance on choosing a
model tier and reasoning-effort level in Claude Code); wire it into
`SKILL.md`'s Mechanism-fit bullet list. Full text: see this PR's diff.

Precondition and splits: satisfied (19 fixtures, 7:7:5 with this
iteration's additions -- see Assignment above).

Methodology, disclosed reuse: the other 6 selection fixtures' **before**
score for this gate = their **after** score from #149's already-completed
gate above (same committed file state at the time, same matched
methodology, one fresh dispatch per fixture) -- re-deriving it would be
exactly the "never both" redundancy Contract discipline forbids. Only the
new selection fixture, `model-effort-tier-fit-unjustified-effort.yaml`,
needed a genuine fresh **before** dispatch (run against
`git show 6b83915:<path>`, the commit immediately prior to this edit, to
avoid a working-tree race with the edit in progress). All 7 selection
fixtures then got a fresh **after** dispatch against the post-edit
working tree, one fresh subagent per fixture, scored with
`skills/gated-skill-edits/scripts/score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused, #149 after) | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #149 after) | 1.000000 |
| `third-party-not-authoritative.yaml` | 0.888889 (reused, #149 after) | 0.888889 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused, #149 after) | 0.857143 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused, #149 after) | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused, #149 after) | 1.000000 |
| `model-effort-tier-fit-unjustified-effort.yaml` | 0.500000 (fresh) | 1.000000 (fresh) |

Selection mean: **before 0.912698 -> after 0.963719**. Run via
`score_contract.py --compare-to 0.912698 --scores after-scores.txt`:
`0.963719 KEEP`.

`scoring-axis-uncontrolled-speed-claim.yaml` dipped from 1.000000 to
0.857143 (6/7 assertions) -- checked directly, this is not a rubric
regression: the after-dispatch discussed the fixture's cost/speed
numbers as "6.5s/$0.03" rather than the assertion's exact literal
`"6.5 seconds"`, a paraphrase of unrelated dimension-8 content this edit
never touches (the Model/effort tier fit section is not cited anywhere
in that fixture's own assertions or in the after-transcript's discussion
of it). This is the same class of fixture-assertion brittleness the
#149 methodology note above already surfaced (case-sensitivity,
negation traps) -- run-to-run subagent wording variance on an unrelated
dimension, not an effect of this edit -- disclosed here rather than
silently rerun until it passed. It does not change the KEEP outcome: the
selection mean still strictly improves with the dip included.

The purpose-built fixture, `model-effort-tier-fit-unjustified-effort.yaml`,
moved cleanly from 0.500000 (before: the pre-edit rubric has no
Model/effort tier fit check at all, so the before-dispatch could not cite
it or the "try hard enough" diagnostic, failing half the assertions) to
1.000000 (after: the post-edit dispatch named the check by its exact
heading and used the rubric's own "try hard enough" diagnostic language
verbatim against the target's `effort: low` pin) -- the entire
improvement comes from the fixture built to test this exact change,
matching the shape of the #149 result above.

**Restraint check (test split, read once):**
`model-effort-tier-fit-justified.yaml` -- a race-condition-diagnosis
skill pinning Opus at max effort with a stated reason matching the
source's own hard-problem examples almost verbatim. The after-edit
dispatch recognized the pin as justified and said so explicitly (per the
rubric's own "model/effort pin justified" phrasing), rather than
flagging a false positive or silently skipping the question -- confirming
the new check does not over-fire on a pin that already meets its own
criteria.

The fixture's own assertion had the same case-sensitivity bug the #149
methodology note above already caught once this session: the dispatch
wrote "**Model/effort pin justified**" as a sentence-initial capitalized
lead-in, and the original `output_contains: ["model/effort pin
justified"]` (lowercase m) false-failed against it. Fixed the same way
as the earlier `blind-spot-pass-*` fixtures -- not by re-running until it
happened to pass, but by matching a case-invariant fragment of the
phrase, `"pin justified"`, which is present regardless of how the
sentence leading into it is capitalized. Re-scored after the fix:
1.000000.

**KEEP.** Strict improvement on the selection split (one real dip,
independently confirmed unrelated to the edit and disclosed), a clean
generalization result on the fixture built to test the new check, and a
confirmed restraint result on the held-out justified-pin fixture.

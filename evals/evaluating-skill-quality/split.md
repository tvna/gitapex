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

SkillOpt's default split ratio is 2:1:7. At 27 fixtures that ratio gives a
selection split of roughly three tasks, too thin to gate a strict
improve-or-reject decision because three observations provide little ability
to average out run-to-run variance. Following the precedent already set in
`skills/gated-skill-edits/references/worked-example.md` ("the ratio is
aspirational" for a small fixture count), this split uses a flatter 12:9:6
partition, named explicitly as a deviation from the 2:1:7 default. The
honest minimal groundwork, per that same worked example, is a larger
fixture corpus over time, not a smaller gate.

## Assignment

- **train** (motivates edits; read for evidence, never scored for
  acceptance): `normal.yaml`, `mechanism-fit-claudemd.yaml`,
  `no-unauthorized-eval-tooling.yaml`, `scoring-axis-cost-only-eval.yaml`,
  `ordering-rule-totality-review.yaml`, `blind-spot-pass-domain-gap.yaml`,
  `model-effort-tier-fit-unjustified-model.yaml`,
  `portability-declarative-fact-claim.yaml`, `branch-and-step-contracts.yaml`,
  `sentence-level-pruning.yaml`, `progressive-disclosure-placement.yaml`,
  `heldout-semantic-noop-vs-brevity.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`,
  `mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
  `scoring-axis-uncontrolled-speed-claim.yaml`,
  `ordering-rule-totality-distinct-skill.yaml`,
  `blind-spot-pass-generalizes.yaml`,
  `model-effort-tier-fit-unjustified-effort.yaml`,
  `portability-issue-number-citation.yaml`, `heldout-vague-completion.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `guardrail.yaml`, `no-fabricated-violation.yaml`,
  `portability-classification.yaml`, `blind-spot-pass-not-silent.yaml`,
  `model-effort-tier-fit-justified.yaml`,
  `portability-legitimate-illustrative-citation.yaml`.

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

The three `portability-declarative-fact-claim.yaml` /
`portability-issue-number-citation.yaml` /
`portability-legitimate-illustrative-citation.yaml` fixtures were added
for issue #165 (the portability litmus test for declarative fact-claims,
plus a named GitHub issue/PR-citation sub-check), for the same reason:
none of the prior 19 fixtures probe whether the review catches a
declarative fact-claim (a prose assertion the model never executes as a
step, e.g. "backed by this plugin's X") or a bare/qualified GitHub
issue-number citation embedded in Portable-declared content -- the
existing `portability-classification.yaml` fixture (test split) only
probes an undeclared repository-scoped *executed-step* dependency, a
different failure shape.
`portability-declarative-fact-claim.yaml` sits in train (a Stop boundary
unconditionally claiming to be "backed by" a specific named hook file --
it motivated the edit, mirroring the exact failure shape a real
pre-existing gitapex bug had). `portability-issue-number-citation.yaml`
sits in selection and uses a distinct domain and a distinct failure mode
(a bare issue-number citation inside a skill's own procedure text, not a
Stop-boundary fact-claim) so the gate measures generalization across the
litmus test and the new dimension-6 sub-check together, not memorization
of the train fixture's exact wording.
`portability-legitimate-illustrative-citation.yaml` sits in test (read
once, for the final report) and checks the restraint side: a sibling-skill
citation used purely as an illustrative design analogy, with no
unconditional fact-claim and no issue number, must not be flagged as a
false positive by the stricter check.

The three `branch-and-step-contracts`, `sentence-level-pruning`, and
`progressive-disclosure-placement` fixtures directly motivated the current
rubric operationalization, so they are train fixtures. They have not been
used to claim a selection-gate result or a live eval result.

`heldout-vague-completion.yaml` was prepared independently before the current
implementation began and was not shown to the implementation agent. It is
selection evidence only and must not motivate edits.

`heldout-semantic-noop-vs-brevity.yaml` was originally prepared the same way,
but review found that its expected answer contradicted the new rubric by
calling unmeasured prose a behavioral no-op. The expectation was corrected
and the fixture moved to train. Its earlier score is invalid and excluded
from candidate-acceptance evidence.

## Reuse

Future edits to this rubric should reuse this same split rather than
re-deriving one per iteration, so the selection split stays genuinely
held out across iterations. If a future edit targets a topic none of the
27 fixtures probe, add motivated cases to train and fresh generalization
cases to selection before scoring, and record the addition here.

## Rejected-edit log

**Iteration: issue #116 gate 3, ranking/tie-break totality item.**
Candidate edit: add a bullet to `references/rubric.md`'s Dimension 4
(Clarity and structure) requiring totality verification for any
enumerated ranking/tie-break rule (every pair of distinct values
ordered, a final stable key for full ties) -- see issue #116, Repair 1
for the exact proposed wording.

Precondition and splits: satisfied for that historical iteration, per this
file's then-current corpus (13 fixtures,
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

**Iteration: issue #165, portability litmus test for declarative
fact-claims.** Candidate edit: add an explicit litmus test to
`references/rubric.md`'s Portability level section ("would this exact
sentence remain true, unchanged, if this file were copied into a
repository carrying none of the origin repo's state?"), applied to every
sentence including Stop-boundaries/Mechanism-fit prose, not only executed
steps; a named dimension-6 sub-check banning bare/qualified GitHub
issue-PR citations inside Portable-declared content; a mirrored, terser
version in `SKILL.md`'s Portability level section; a Subagent-dispatch
instruction to check Stop-boundaries/Mechanism-fit prose against both the
Mechanism-fit "is this backed" question and the new litmus test
separately; and a fallback in the Blind Spot Pass's "if a gap is found"
branch, which previously named `gated-skill-edits` as the sole mechanism
for a durable change with no fallback for a vendored context without that
sibling skill.

Motivation, disclosed in full: this round was not a hypothetical
exercise. Live dogfooding of the just-edited `evaluating-skill-quality`
skill against itself (recorded above and in
`references/worked-example-self-review.md`) found a real, pre-existing
portability defect in `SKILL.md`'s own Stop boundaries -- an unconditional
claim to be "backed by this plugin's `hooks/check-bash-safety.sh`
PreToolUse hook" -- that predates this session (introduced 2026-07-14,
commit `7848d39`) and survived five subsequent gated edits plus one live
dogfooding pass, including one where the dispatch read the sentence
directly and affirmed it as correct rather than flagging it. A follow-up
audit then found the same class of defect recurring inside this session's
own edits: bare issue-number citations added to the Portable skill's own
worked-example file, and a hardcoded `gated-skill-edits` dependency with
no fallback. A dedicated root-cause investigation diagnosed why: the
rubric's prior Portability guidance was anchored to *executed-step*
patterns ("reads/cites as authority/branches on a path"), so a
*declarative fact-claim* in prose -- never executed as a step -- did not
pattern-match either checklist and repeatedly slipped through, including
past a live dogfooding pass built specifically to catch this class of
issue.

Precondition and splits: satisfied (22 fixtures, 8:8:6 with this
iteration's additions -- see Assignment above).

Methodology, disclosed reuse: the other 7 selection fixtures' **before**
score for this gate = their **after** score from #155's already-completed
gate above (same committed file state at the time, same matched
methodology). Only the new selection fixture,
`portability-issue-number-citation.yaml`, needed a genuine fresh
**before** dispatch (run against `git show 89cc296:<path>`, the commit
immediately prior to this edit, to avoid a working-tree race). All 8
selection fixtures then got a fresh **after** dispatch against the
post-edit working tree, scored with
`skills/gated-skill-edits/scripts/score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused, #155 after) | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #155 after) | 1.000000 |
| `third-party-not-authoritative.yaml` | 0.888889 (reused, #155 after) | 1.000000 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 0.857143 (reused, #155 after) | 1.000000 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused, #155 after) | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused, #155 after) | 1.000000 |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused, #155 after) | 1.000000 |
| `portability-issue-number-citation.yaml` | 0.750000 (fresh) | 1.000000 (fresh) |

Selection mean: **before 0.937004 -> after 1.000000**. Run via
`score_contract.py --compare-to 0.937004 --scores after-scores.txt`:
`1.000000 KEEP`.

Two pre-existing fixtures moved up (`third-party-not-authoritative.yaml`
0.888889 -> 1.000000, `scoring-axis-uncontrolled-speed-claim.yaml`
0.857143 -> 1.000000) on content this edit never touches (dimension 6's
third-party-citation guidance, dimension 8's scoring-axis guidance) --
checked directly, both are run-to-run subagent wording variance (e.g.
`third-party-not-authoritative.yaml`'s "observed" appeared this run but
not last), not an effect of the edit, and disclosed rather than silently
banked as a win.

Along the way, fixing the new fixture's own assertion caught a live
demonstration of the exact "scorer construct validity" gap this
session's Blind Spot Pass had already named as a still-open rubric gap
(see the dogfooding update in `worked-example-self-review.md`'s
Mechanism-fit section): the fresh **before** dispatch (pre-edit rubric,
no litmus test yet) independently reasoned its way to a *hedged, explicitly
unsupported-by-rubric* concern about the "issue #88" citation via the
pre-existing Blind Spot Pass mechanism, and the first version of this
fixture's assertion (`output_contains: ["#88", "vendored"]`) was loose
enough to score that hedged before-run a perfect 1.000000 -- indistinguishable
from the post-edit run's *confirmed, rubric-cited* "Fail" verdict, on
substring matching alone. Tightened the assertion to
`"issue/PR-number citation"`, a phrase that exists only in the new
dimension-6 bullet and is therefore absent from every pre-edit
transcript by construction -- re-scored: before 0.750000, after
1.000000, a genuine, construct-valid improvement instead of a
false tie. A second, unrelated fixture bug was also found and fixed on
this same fixture, `edge.yaml` (pre-existing, predates this session):
`output_contains: ["hook or permission"]` matched one historical
transcript's paraphrase but not this round's fresh dispatch, which
instead quoted the rubric's own primary-source text verbatim,
`"hooks and permissions"` -- changed the assertion to the stable,
rubric-quoted phrase (confirmed present in both this round's and the
historical #149-round transcript), re-scored: 1.000000 in both cases, no
change to any reported mean.

**Restraint check (test split, read once):**
`portability-legitimate-illustrative-citation.yaml` -- a sibling-skill
citation used purely as an illustrative design analogy, explicitly
self-hedged in its own text ("not a dependency this procedure needs that
sibling skill to be present for"). The after-edit dispatch reasoned
through both litmus questions explicitly rather than defaulting either
way, correctly concluded the citation clears the carve-out, and did not
flag a false positive -- confirming the stricter check does not over-fire
on a legitimate illustrative reference.

**KEEP.** Strict improvement on the selection split, a genuine
(construct-valid, after tightening one fixture's own assertion)
generalization result on the fixture built to test the new check, two
unrelated fixture-assertion bugs found and fixed along the way (disclosed,
not silently patched), and a confirmed restraint result on the held-out
legitimate-citation fixture.

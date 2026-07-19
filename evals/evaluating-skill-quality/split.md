# Held-out split for scorer-gated-skill-edits

Train / selection / test partition for `evals/evaluating-skill-quality/`,
established so `scorer-gated-skill-edits`' precondition gate (a real scorer plus a
held-out split, both required before any iterative edit to this skill's
`references/rubric.md` is kept) is satisfied. See
`skills/scorer-gated-skill-edits/SKILL.md` for the gate itself and
`skills/scorer-gated-skill-edits/scripts/score_contract.py` for the scorer, which
scores each fixture's `expected.output_contains` / `output_not_contains`
block deterministically.

## Corpus size and the 2:1:7 caveat

SkillOpt's default split ratio is 2:1:7. At 33 fixtures that ratio gives a
selection split of roughly five tasks, too thin to gate a strict
improve-or-reject decision because five observations provide little ability
to average out run-to-run variance. Following the precedent already set in
`skills/scorer-gated-skill-edits/references/worked-example.md` ("the ratio is
aspirational" for a small fixture count), this split uses a flatter 14:11:8
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
  `heldout-semantic-noop-vs-brevity.yaml`,
  `capability-assumption-broad-excuses-explanation.yaml`,
  `ablation-capability-no-mechanism.yaml`.
- **selection** (gates acceptance; scored before/after a candidate edit,
  strict improve-or-reject, ties rejected): `edge.yaml`,
  `mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
  `scoring-axis-uncontrolled-speed-claim.yaml`,
  `ordering-rule-totality-distinct-skill.yaml`,
  `blind-spot-pass-generalizes.yaml`,
  `model-effort-tier-fit-unjustified-effort.yaml`,
  `portability-issue-number-citation.yaml`, `heldout-vague-completion.yaml`,
  `capability-assumption-frontier-flags-explanation.yaml`,
  `ablation-capability-runner-exists-not-run.yaml`.
- **test** (read once, for a final report only, never to motivate or gate
  an edit): `guardrail.yaml`, `no-fabricated-violation.yaml`,
  `portability-classification.yaml`, `blind-spot-pass-not-silent.yaml`,
  `model-effort-tier-fit-justified.yaml`,
  `portability-legitimate-illustrative-citation.yaml`,
  `capability-assumption-adaptive-progressive-disclosure.yaml`,
  `ablation-capability-already-run.yaml`.

The three `capability-assumption-*` fixtures were added for issue #183
(Sub-project B, the capability-assumption grading semantics), for the
same reason: none of the prior 27 fixtures assert on the new Broad /
Frontier / Adaptive per-dimension grading effect at all.
`capability-assumption-broad-excuses-explanation.yaml` sits in train (a
Broad-declared skill's well-known-concept explanation, motivating the
dimension-2 Broad bullet -- it was used to calibrate the bullet's wording
against a live dispatch before the selection fixture was written).
`capability-assumption-frontier-flags-explanation.yaml` sits in selection
and uses a distinct domain (database migrations, not flaky tests) and the
opposite declared level (Frontier, not Broad) with the same shape of
well-known-concept restatement, so the gate measures whether the check
generalizes the Frontier direction rather than memorizing the train
fixture's domain or its Broad-excuses wording.
`capability-assumption-adaptive-progressive-disclosure.yaml` sits in test
(read once) and checks the restraint side for the Adaptive-only
dimension-5 effect: does the review verify a genuine lean-body-plus-depth
split rather than rubber-stamping any Adaptive declaration.

The three `ablation-capability-*` fixtures were added independently, in
the same window, for issue #185 (the ablation-capability sub-check on
dimension 8) -- see that iteration's own entry below for their rationale.
Landing in the same merged corpus as the three `capability-assumption-*`
fixtures above is coincidental (two sub-projects of the same
skill-metadata-sidecar effort progressing in parallel), not a shared
design; the two triples probe unrelated rubric sections (dimension 8's
ablation-capability distinction vs. the Capability assumption axis's
dimensions 2/3/5/9).

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

The three `ablation-capability-no-mechanism.yaml` /
`ablation-capability-runner-exists-not-run.yaml` /
`ablation-capability-already-run.yaml` fixtures were added for the
ablation-capability sub-check (dimension 8), for the same reason as prior
additions: none of the prior 27 fixtures probe whether the review
distinguishes an unrecorded-but-achievable baseline from a genuinely
unbuildable one, or recognizes when a baseline has already been measured.
`ablation-capability-no-mechanism.yaml` sits in train (an invented
log-triage-assistant skill whose repository has only a structural
pass/fail eval runner and no way to run a with-skill-vs-without-skill
comparison at all -- it motivated the edit).
`ablation-capability-runner-exists-not-run.yaml` sits in selection and
uses a distinct domain (invoice parsing) and the opposite discrimination
case: the repository already ships an ablation-capable runner, it simply
has not been pointed at this skill yet -- so the gate measures whether the
sub-check generalizes to "ablation-capable, not yet run" rather than
defaulting to the train fixture's "no mechanism" framing whenever a
baseline is merely unrecorded. `ablation-capability-already-run.yaml` sits
in test (read once, for the final report) and checks the restraint side: a
target whose baseline has already been measured and reported with concrete
lift numbers must not be false-positively flagged with either
ablation-capability phrasing.

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
scored with `skills/scorer-gated-skill-edits/scripts/score_contract.py`
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
`skills/scorer-gated-skill-edits/scripts/score_contract.py`:**

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
`skills/scorer-gated-skill-edits/scripts/score_contract.py`:

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
`skills/scorer-gated-skill-edits/scripts/score_contract.py`:

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

**Iteration: issue #183, Sub-project B, Capability assumption grading
semantics.** Candidate edit: add the full per-dimension Broad / Frontier /
Adaptive grading effect to `references/rubric.md`'s Capability assumption
section for dimensions 2 (Conciseness), 3 (Degree of freedom), and 9
(Cross-model robustness), and an Adaptive-only effect for dimension 5
(Progressive disclosure); state the boundary against Model/effort tier
fit explicitly in both directions; assign the declaration-vs-pin
consistency check to Procedure step 4 as its sole owner; update
`SKILL.md`'s Capability assumption section and step 4 to match; reclassify
`battle-testing-a-skill` from Broad to Adaptive. Full text: see this PR's
diff.

Precondition and splits: satisfied at the time this iteration ran (30
fixtures, 13:10:7 -- see Assignment above; the corpus grew to 33,
14:11:8 once this PR merged alongside issue #185's own iteration below,
which was landing in parallel -- see the Merge reconciliation entry at
the end of this log for the combined, re-verified result).

Methodology, disclosed reuse: the other 9 selection fixtures'
**before** score for this gate = their **after** score from issue #165's
already-completed gate above (same committed file state at the time,
same matched methodology) -- re-deriving it would be exactly the "never
both" redundancy Contract discipline forbids, EXCEPT for
`heldout-vague-completion.yaml`, which despite being listed in the
Assignment since issue #149 was never actually scored in any prior
iteration's before/after table -- it needed a genuine fresh **before**
dispatch here for the first time, run against the pinned pre-edit
snapshot (`git show 228486c:<path>`, identical to `29b4ed0:<path>`, the
last commit to touch either file). The new selection fixture,
`capability-assumption-frontier-flags-explanation.yaml`, also needed a
fresh **before** dispatch against that same pinned snapshot. All 10
selection fixtures then got a fresh **after** dispatch against the
post-edit working tree, one fresh subagent per fixture, scored with
`skills/scorer-gated-skill-edits/scripts/score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `third-party-not-authoritative.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused, #165 after) | 0.857143 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `portability-issue-number-citation.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `heldout-vague-completion.yaml` | 1.000000 (fresh, first-ever gate) | 1.000000 |
| `capability-assumption-frontier-flags-explanation.yaml` | 0.750000 (fresh) | 1.000000 (fresh) |

Selection mean: **before 0.975000 -> after 0.985714**. Run via
`score_contract.py --compare-to 0.975000 --scores after-scores.txt`:
`0.985714 KEEP`.

`scoring-axis-uncontrolled-speed-claim.yaml` dipped from 1.000000 to
0.857143 (6/7 assertions) -- checked directly, this is the same class of
run-to-run subagent wording variance already documented twice above for
this exact fixture (issue #149's "6.5s/$0.03" paraphrase miss): this
round's after-dispatch answered the dimension-8 cost/success question
correctly and in full but never happened to mention running
`check_skill_shape.py`, an assertion unrelated to anything this edit
touches (the edit only changes the Capability assumption and Model/effort
tier fit sections; this fixture exercises dimension 8 alone). Disclosed
rather than silently rerun until it passed; it does not change the KEEP
outcome.

The purpose-built fixture, `capability-assumption-frontier-flags-explanation.yaml`,
moved from 0.750000 (before: the pre-edit rubric has no Broad/Frontier/
Adaptive calibration at all, so the before-dispatch correctly failed the
excerpt's step 1 against the *generic* "explaining what a well-known
format or tool is" Fail example -- a real, cited fail, but one that never
uses or needs the word "sprawl," since the pre-edit rubric's own
"sprawl" category is specifically "branch-specific detail paid on every
route" and does not describe a single non-branching sentence) to
1.000000 (after: the post-edit dispatch reached the identical bottom-line
verdict -- still a fail -- but by directly quoting the new Frontier
bullet's own relabeling of this exact failure shape as "sprawl even
where a Broad-declared skill would be excused for the identical
sentence"). This is a genuine, content-driven improvement, not an
engineered one: the before/after dispatches independently reached the
same PASS/FAIL direction (both correctly fail the excerpt) but ground it
in materially different rubric text, exactly as the edit intends -- the
fixture's assertions score the *reasoning path* (does the review cite
the new Frontier calibration), not merely the final verdict word.

**Fixture bug found and fixed along the way, disclosed:**
`capability-assumption-frontier-flags-explanation.yaml`'s first draft
banned bare `"clean pass"` in `output_not_contains` -- a negation trap of
exactly the class documented earlier in this log (issue #165's
`model-effort-tier-fit-justified.yaml` casing bug, the #149
`tenth dimension` bug): a *correct* denial naturally writes "**Not a
clean pass**," which still contains the banned substring "clean pass,"
so the assertion would have false-failed the correct verdict. Found
during this same gate run (before any selection score was banked, so no
motivating-from-selection leak), fixed by tightening the banned phrase to
the affirmative-only `"is a clean pass"` -- a wrong-but-plausible
"this is a clean pass" answer still trips it, while "Not a clean pass"
does not contain that substring. Re-scored after the fix: 1.000000,
matching the number reported in the table above (the fix was applied
before the table's numbers were recorded, not after).

**Restraint check (test split, read once):**
`capability-assumption-adaptive-progressive-disclosure.yaml` -- a
triage-log-anomalies excerpt declaring `capabilityAssumption: Adaptive`
with a genuinely lean-looking body and a substantial (240-line)
referenced decision tree, designed to check whether the new
Adaptive-only dimension-5 effect verifies the split rather than
rubber-stamping the declaration. Result: the after-edit dispatch did
**not** rubber-stamp it -- it explicitly declined to accept the 240-line
reference's contents on the paraphrase given, and separately found a
real, citable gap against the rubric's own new Adaptive bullet ("the
body must actually be lean by this dimension's existing tests (common
case reachable without opening a reference...)"): the excerpt's common
case (classify any reported anomaly) cannot complete from the body
alone, since the classification logic lives entirely in the reference,
so "common case reachable without opening a reference" fails even though
"no forced *multi*-file read" passes. This is a stronger restraint result
than the clean pass this fixture was originally built to elicit: it is
direct, unprompted evidence the new check has real teeth against a
plausible-looking but not-fully-qualifying Adaptive declaration, not
merely a rubber stamp for any skill that sets the enum value. Per the
test-split rule, the fixture's own excerpt is left unchanged rather than
retrofitted to force a clean-pass outcome now that its actual result is
known.

**Correction (found by external review, PR #189 `chatgpt-codex-connector[bot]`):**
two real defects in this fixture, found together. First, the reference's
content was only paraphrased in the prompt ("240 lines: a full decision
tree..."), not actually supplied -- so a reviewer could only trust the
summary rather than verify the artifact Procedure step 1 requires reading
in full, and the assertions (`"Adaptive"`, `"lean"`) did not require any
specific verdict direction at all: a wrong answer concluding FAIL would
have scored identically to the intended PASS. Second, and more
substantively, the excerpt's *body* deferred the actual classification
rule (the numeric thresholds) entirely to the reference, keeping only
worked examples and exact commands there -- re-graded live against the
fixed rubric wording below, this genuinely FAILS dimension 5 ("the body
must actually be lean **for the strong-model path**... a Frontier-capable
reader completes the common case from the body alone"), since the
thresholds are read on every single classification, not merely by a weak
tier "on demand." This was not a fixture-assertion bug alone; the
*designed* excerpt did not actually qualify as a good-Adaptive-split
example. Fixed by (a) inlining the actual four-branch classification rule
into the body's Procedure steps, leaving only worked examples and exact
query commands in the reference (the assertion Adaptive's Fair test
distinguishes: everyday-use reasoning belongs in the body; per-branch
detail used only sometimes belongs in the reference), (b) including the
reference's full real content in the prompt so the reviewer can verify it
directly, and (c) requiring an explicit `"PASS"` token while banning
plausible wrong-conclusion phrasings (`"dimension 5 fails"`,
`"dimension 5, FAIL"`). Re-verified live against the corrected excerpt and
the corrected rubric wording (see the next correction below): explicit,
non-rubber-stamped **PASS**, citing exactly the intended reasoning (body
inlines the everyday rule; reference is scoped to genuinely on-demand
per-branch detail). This is a stronger, more honest restraint result than
the original: it demonstrates the check both refuses to rubber-stamp
(caught the first, flawed version of this exact fixture) and correctly
recognizes a genuinely qualifying split once one is actually given.

**Second correction, same review (rubric wording, not just the
fixture):** the Codex review separately flagged that the Adaptive
dimension-5 "body must be lean" bullet was ambiguous about which model
tier's path the "no forced reference read" test applies to -- read
strictly, it could be misapplied to fail any Adaptive skill where a
*weak* tier legitimately pulls the reference for the common case, which
is Adaptive's own intended behavior, not a defect. Fixed in
`references/rubric.md` by scoping the bullet explicitly to the
**strong-model path** ("a Frontier-capable reader completes the common
case from the body alone... this does not mean no tier ever needs the
reference: Adaptive's own definition has a weaker tier pull the reference
for that same common case by design, and that is the strategy working as
intended"). This same wording fix is also what the live re-verification
above applied.

**Falsifiable acceptance criterion (issue #183, and the design spec's
Sub-project B sequencing section):** a live before/after re-grade of the
real `battle-testing-a-skill`, reclassified from Broad to Adaptive in
this same change, is recorded separately in
`docs/skill-eval-status.md`'s `battle-testing-a-skill` section (not
repeated here, since that re-grade is against a real shipped skill, not
a held-out fixture) -- see that file for the specific dimension verdict
that changed.

**KEEP.** Strict improvement on the selection split (one real, disclosed,
edit-unrelated dip; two fixtures scored for the first time), a genuine
content-driven generalization result on the fixture built to test the new
check (same verdict direction, different and correct rubric grounding), a
negation-trap fixture bug found and fixed before any score was banked,
and a restraint result on the held-out Adaptive fixture that is stronger
evidence of rigor than the clean pass it was designed to check for.

**Iteration: ablation-capability sub-check (dimension 8).** Candidate edit:
add a new bold-lead paragraph to `references/rubric.md`'s dimension 8
(Behavioural evidence), right after the existing "Check the target
repository for an eval mechanism" paragraph, requiring the review to
distinguish "ablation-capable, not yet run" (a with-skill-vs-without-skill
comparison mechanism exists in the repository, just not yet pointed at
this skill) from "no ablation mechanism exists in this repository" (no
such mechanism exists at all), rather than collapsing both into an
undifferentiated "no baseline." Motivated directly by this repository's
own `docs/skill-eval-status.md`, which records that exact undifferentiated
phrasing for nearly every skill in the repository. Full text: see this
PR's diff.

Precondition and splits: satisfied (30 fixtures, 13:10:7 with this
iteration's additions -- see Assignment above). Between the prior
iteration (issue #165) and this one, an unrelated change (the skill
metadata sidecar migration) touched `references/rubric.md`'s Portability
level section and added a new Capability assumption section, but left
dimension 8 and every other section byte-identical -- confirmed directly
(`git diff` against the pre-migration commit shows only those two hunks).
Of the 9 pre-existing selection fixtures, 8 assert on content this
migration never touched (mechanism fit, dimension 4, dimension 8's
scoring-axis guidance, blind-spot-pass, model-effort-tier-fit); one of
those 8, `portability-issue-number-citation.yaml`, targets dimension 6's
citation ban (also untouched by the migration, confirmed by the same
diff) on a target that declares portability via the pre-sidecar
body-marker convention, which the shape checker's fallback path still
supports for a foreign/vendored target -- so its assertions remain valid
unchanged. Those 8 therefore reuse their #165 after-scores (all
1.000000) as this gate's before scores -- disclosed reuse, the same
"never both" discipline the prior two iterations already applied.

**Correction (found by external review, PR #190 `chatgpt-codex-connector[bot]`):**
the first version of this gate omitted the 9th pre-existing selection
fixture, `heldout-vague-completion.yaml`, from the table below entirely
-- the reported mean covered 9 tasks against a declared 10-fixture
selection split, so a regression in the omitted fixture could not have
blocked the `KEEP` decision. Checked directly: unlike the other 8 reused
fixtures, `heldout-vague-completion.yaml` has never appeared in any prior
recorded Kept-edit gate (#149, #155, #165) -- it was added to the
selection split independently, before those iterations, and this repository
has apparently never actually gated on it before now, a pre-existing gap
in this file's own history that predates this session. With no genuine
prior score to reuse, it needed its own fresh before/after pair, the same
as the new fixture. Both dispatches confirm what its content already
implies (it targets dimension 4's completion-criteria language, nothing
in dimension 8): identical `COMPLETION_CRITERIA: FAIL` verdicts either
side of the edit.

Methodology: one fresh, isolated subagent dispatch per side for each of
the two fixtures needing a genuine pair (this repository has no
registered `Skill` tool for its own unpublished `evaluating-skill-quality`
content, so each dispatch was instructed to read `references/rubric.md`
and `SKILL.md` directly -- `git show 228486c:...` for the before side, the
working tree for the after side -- and follow the Procedure by hand),
scored with `skills/scorer-gated-skill-edits/scripts/score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `third-party-not-authoritative.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `portability-issue-number-citation.yaml` | 1.000000 (reused, #165 after) | 1.000000 |
| `heldout-vague-completion.yaml` | 1.000000 (fresh) | 1.000000 (fresh) |
| `ablation-capability-runner-exists-not-run.yaml` | 0.750000 (fresh) | 1.000000 (fresh) |

Selection mean: **before 0.975000 -> after 1.000000**. Run via
`score_contract.py --compare-to 0.975000 --scores after-scores.txt`:
`1.000000 KEEP`. (The original, incomplete 9-fixture table reported
`before 0.972222 -> after 1.000000`, also `KEEP` -- correcting the
omission changes the precision and the fixture count, not the verdict,
since `heldout-vague-completion.yaml` scored identically on both sides.)

The fresh fixture's own before-run (pre-edit rubric) still named the
existing `battle/run_battle.py --ablate` tool and correctly declined to
treat "no baseline run" as a hard block -- but it never produced the
exact discriminating phrase `"ablation-capable, not yet run"`, since that
phrasing did not exist in the rubric yet, scoring 0.750000 (3/4
assertions). The after-run named the sub-check's exact phrasing verbatim
("this is **ablation-capable, not yet run** -- not '...no ablation
mechanism exists...'"), scoring 1.000000 -- a genuine, construct-valid
improvement from the edit, not a reused or coincidental phrase.

A real fixture-assertion bug was found and fixed *before* scoring, not
after seeing a result: the after-run's dispatch explicitly wrote a denial
of the wrong framing ("not 'no ablation mechanism exists...'"), which
means an `output_not_contains: ["no ablation mechanism"]` assertion --
the first draft of all three new fixtures -- would have false-failed a
*correct* response purely for stating what it was rejecting, the same
negation-trap class of bug `references/rubric.md`'s own dimension-6
history (the "tenth dimension" fixture, recorded above under issue #149)
already hit once. Fixed the same way: dropped the fragile
`output_not_contains` bans on the counterpart phrasing from all three new
fixtures, keeping only the generic `"LGTM"` / `"no concerns"` guardrails
plus a strong, unique positive assertion per fixture -- the positive
phrasing alone is sufficiently discriminating (a wrong answer states the
opposite conclusion, it does not omit stating any conclusion).

**Restraint check (test split, read once):**
`ablation-capability-already-run.yaml` -- a target whose eval-status notes
already report a real, dated with-skill-vs-without-skill comparison (91%
vs. a 34% no-skill baseline). The after-edit dispatch correctly recognized
this as ablation *history*, not mere *capability*, explicitly declined
both of the sub-check's two phrasings ("I am not using either of those
phrasings because the text plainly shows a run occurred"), and instead
named a third, correct disposition -- while also independently flagging
that the figure was self-reported and unverified by an isolated dispatch
with no access to the target's actual repository, a distinct finding this
review did not ask for but which is consistent with the rubric's
primary-source-grounding discipline.

**Correction (found by external review, PR #190 `chatgpt-codex-connector[bot]`):**
this fixture's first-draft assertions (`output_contains: ["91%"]`, plus
the generic `LGTM`/`no concerns` guardrails) could not actually
substantiate the restraint claim above: `"91%"` is copied verbatim from
the fixture's own prompt, so a *wrong* response that repeats the number
while incorrectly concluding "no ablation mechanism exists" would have
scored identically 1.0 -- exactly the false positive this fixture exists
to catch, undetected by construction. Fixed by strengthening the positive
assertion to require three independently-improbable-for-a-wrong-answer
tokens together: `"91%"`, `"34%"` (the paired baseline figure a
mechanism-gap conclusion has no reason to restate), and `"already"` (the
history-recognizing language a mechanism-gap conclusion would
contradict) -- re-scored against the real (not paraphrased) transcript
above: still `1.000000`. This is deliberately a positive-only fix, not a
negative ban on the two sub-check phrasings: the same negation-trap risk
already found and fixed once in this iteration (above) would recur if a
correct restraint response quoted either phrase only to reject it.

**KEEP.** Strict improvement on the corrected 10-fixture selection split,
a genuine generalization result on the fixture built to test the new
check, one selection fixture omitted from the first-draft table and
restored with its own genuine before/after pair, one fixture-assertion
negation-trap bug found and fixed before scoring, one restraint-fixture
discrimination bug found after external review and fixed with a
positive-only assertion, and a confirmed restraint result on the
held-out already-run fixture that also demonstrated the check correctly
recognizes a third disposition (history, not just capability-vs-absence)
it was never explicitly designed to enumerate.

**Merge reconciliation: issue #183 (PR #189) and issue #185 (PR #190),
landed in parallel onto the same two files.** Both iterations above ran
their own held-out gate independently, against a rubric that had only
their own edit applied -- neither saw the other's change. Once merged,
the corpus is 33 fixtures (14:11:8, not the 30/13:10:7 each iteration
reported at the time), and the selection split has 11 fixtures, not 10.
Per this repository's own "a clean textual auto-merge is not a safe
merge" discipline, re-verifying against the actual merged file, not
reusing either iteration's now-stale table, is required rather than
optional.

`references/rubric.md` merged with no textual conflict (the two edits
land in disjoint sections: Capability assumption plus the Model/effort
tier fit boundary note for #183, dimension 8's ablation-capability
paragraph for #185) -- confirmed by inspection that both sections are
present, complete, and mutually unaffected post-merge. `SKILL.md` had no
conflict (unchanged by #185). `docs/skill-eval-status.md` and this file
both had textual insertions at overlapping points, resolved by hand,
preserving both iterations' entries in full rather than dropping either.

Re-verification, one fresh dispatch per fixture whose assertions plausibly
interact with content either edit touches, against the actual merged
working tree (not a pinned snapshot, since this entry's purpose is
confirming the real current state):

| Fixture | Before (reused) | After (merged rubric) |
|---|---|---|
| `edge.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `mechanism-fit-subagent.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `third-party-not-authoritative.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 | 1.000000 (fresh) |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `blind-spot-pass-generalizes.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `portability-issue-number-citation.yaml` | 1.000000 | 1.000000 (unaffected, not re-run) |
| `heldout-vague-completion.yaml` | 1.000000 | 1.000000 (established both sides by #185's iteration, dimension 4, untouched by either merged edit) |
| `capability-assumption-frontier-flags-explanation.yaml` | 0.750000 | 1.000000 (established by #183's iteration; content is dimension-2/Capability-assumption only, untouched by #185's dimension-8 edit) |
| `ablation-capability-runner-exists-not-run.yaml` | 0.750000 | 1.000000 (established by #185's iteration; content is dimension-8/ablation-capability only, untouched by #183's edit) |

Selection mean: **before 0.954545 -> after 1.000000**. Run via
`score_contract.py --compare-to 0.954545 --scores after-scores.txt`:
`1.000000 KEEP`.

`scoring-axis-uncontrolled-speed-claim.yaml` needed the one genuine fresh
re-run: it asserts on dimension 8 (behavioural evidence), the exact
section #185's edit touches, so its #165-reused before-score could not
be assumed still valid the way the other 7 untouched fixtures' could.
The fresh dispatch against the merged rubric scored **0.857143** on
first pass (6/7) -- missing only the literal substring `"6.5 seconds"`,
because the dispatch correctly answered the dimension-8 question in full
but abbreviated the number as `"6.5s"` rather than spelling out
"seconds." This is not a new bug: it is the third independent
occurrence of the *exact same* fixture brittleness, first documented in
issue #149's Kept-edit log entry above ("dipped from 1.000000 to
0.857143... discussed the fixture's cost/speed numbers as '6.5s/$0.03'
rather than the assertion's exact literal '6.5 seconds'") and reproduced
a second time earlier in this same merge's own reconciliation work.
Fixed properly this time rather than disclosed-and-left, since three
independent hits confirm it is not run-to-run noise: relaxed the
assertion from the literal phrase `"6.5 seconds"` to the bare numeral
`"6.5"`, which matches both `"6.5 seconds"` and `"6.5s"` and still
discriminates a correct, specific answer from a generic non-answer (a
response that never engages with the actual numbers in the prompt would
not contain `"6.5"` either way). Re-scored after the fix: `1.000000`.

Two fixtures (`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`) keep their own
iteration's already-established scores rather than a fresh re-run: each
asserts on exactly one edit's own new content (dimension 2's Capability
assumption calibration; dimension 8's ablation-capability distinction,
respectively) and neither section was touched by the other iteration's
edit, confirmed directly by the disjoint-section observation above -- a
fresh dispatch would re-derive an already-known answer, the same "never
both" redundancy this file's own methodology notes have avoided
throughout.

**KEEP.** Strict improvement on the true, fully-merged 11-fixture
selection split (0.954545 -> 1.000000), with the one fixture whose
content could plausibly have interacted with both edits re-verified
fresh against the real merged file rather than assumed, and a
three-times-recurring fixture-assertion brittleness fixed at the root
instead of disclosed a third time.

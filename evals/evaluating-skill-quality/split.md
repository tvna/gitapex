# evaluating-skill-quality held-out split

Train / selection / test partition for `evals/evaluating-skill-quality/`,
established so `scorer-gated-skill-edits`' precondition gate (a real scorer plus a
held-out split, both required before any iterative edit to this skill's
`references/rubric.md` is kept) is satisfied. See
`skills/scorer-gated-skill-edits/SKILL.md` for the gate itself and
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py` for the scorer, which
scores each fixture's `expected.output_contains` / `output_not_contains`
block deterministically. The train/selection/test fixture assignment lives
in `split.json`, validated against
`skills/scorer-gated-skill-edits/references/split.schema.json`.

## Corpus size caveat

SkillOpt's default split ratio is 2:1:7. At 52 fixtures that ratio gives a
selection split of roughly five tasks, too thin to gate a strict
improve-or-reject decision because five observations provide little ability
to average out run-to-run variance. Following the precedent already set in
`skills/scorer-gated-skill-edits/references/worked-example.md` ("the ratio is
aspirational" for a small fixture count), this split combines the 17:14:9
base-plus-cohesion partition with a scoped 2:6:2 compatibility addition, a
1:1:0 reference-load-precision addition (gitapex#477), a 2:2:1
opus5-prompting-fit addition (gitapex#495), a 1:1:0
confidentiality-awareness addition (gitapex#537), a 0:1:0
payment-data sub-category addition (gitapex#537 follow-up), a 0:1:0
MNPI/insider-trading-adjacent sub-category addition (gitapex#537
follow-up), a 0:1:0 trade-secret/competitive-harm broadening (gitapex#537
follow-up), and a 3:3:0 addition for the three new evaluation criteria
issue #614's own retrospective motivated (gitapex#619:
declaration-vs-structure fit, correction-narration sediment, repeated-
restatement duplication), and a 1:0:0 multi-turn-relaxation addition
(gitapex#332's own ACM-7 audit round), for a resulting 27:30:12 partition. This is
named explicitly as a deviation from the 2:1:7 default. The
honest minimal groundwork, per that same worked example, is a larger
fixture corpus over time, not a smaller gate.

Exclusion rule for this arithmetic, stated once so the figures above can be
checked against the Assignment section below (gitapex#907): every listed
fixture, in every split, is counted in exactly one of the additions above,
except the one named on the declaration line below. Verified per split, not
only for train: the Assignment section lists 28 unique train fixtures against
the declared 27 (the single exclusion), and 30 selection and 12 test fixtures
against the declared 30 and 12 exactly.

Split-arithmetic exclusions: `dispatch-required-negative-control.yaml` -- listed
in train for split-listing consistency with `normal.yaml` rather than as a
declared category addition.

That line is machine-readable, not decoration:
`.github/scripts/gitapex_gate_split_fixture_coverage.py`'s Check D parses the
declared partition and this exclusion list, then asserts each split's unique
listed count minus its exclusions equals the declared figure. It also rejects
an exclusion naming a fixture no split's bullet lists, a malformed or duplicated
exclusion line, two disagreeing partition declarations, two `## Assignment`
headings, and the same fixture appearing in more than one split.

Precisely what that buys, stated rather than overclaimed: the reconciliation is
now **machine-detected** on every pull request touching this file, where before
it rested on a reader noticing. It is not proven to be merge-*blocking* --
whether a red check blocks the merge button depends on branch-protection
configuration that no in-repo tooling can read, the same open item
`docs/superpowers/specs/2026-07-21-skill-audit-merge-gate-design.md` already
records for this repository's other gates. An earlier draft of this paragraph
said "gate-enforced, not convention-enforced", which an independent gate review
correctly called an overclaim.

Both declarations above must sit in this header region, before the
`## Assignment` heading, and outside any fenced code block -- the gate reads
nothing else. That is why the illustration below is fenced: it shows the
convention without being read as a second, conflicting declaration.

```markdown
Split-arithmetic exclusions: `some-fixture.yaml` -- why it is not counted
```

## Compatibility-awareness branch coverage

The first seven `compatibility-*` fixtures were frozen before the candidate
skill edit for issue #332. The initial three selection contracts all scored
1.0 on the pre-edit reviewer because its generic Blind spot pass already
noticed the underlying compatibility risk. They remain in selection as
disclosed ties. One bounded retry added two independently authored held-out
fixtures whose author saw only the issue criteria, fixture conventions, and
the pinned pre-edit skill -- never the candidate. These distinguish merely
noticing a risk from the issue's required remediation and evidence-state
discipline. After the first candidate run, deterministic lint and independent
aggregate review found assertion defects: one paraphrase-drift phrase,
negation traps, missing nested-value-shape coverage, and missing
Claude/Devin conflict coverage. The fixture prompts stayed unchanged. An
independent repair pass that did not see the candidate rewrote the two retry
contracts as positive-only assertions; the other two contracts were narrowed
to the omitted acceptance-criteria facts. A second independent author, also
without candidate access, added the incomplete-declaration case after
aggregate review found that state missing. The complete pre-edit and
candidate selection runs recorded in `docs/skill-eval-status.md` use only
these corrected contracts, not the invalidated earlier scores.

- Non-standard top-level frontmatter: Claude Code and HermesAgent examples
  motivate the edit in train; a distinct Devin field gates it in selection.
- Runtime-specific semantics inside standard `metadata`: an OpenClaw
  load-time eligibility gate is held out in selection.
- Warning-only verdict interaction: the OpenClaw selection fixture is
  otherwise Mature and must retain that verdict.
- Accurate self-declaration: the HermesAgent test fixture requires an
  acknowledged limitation rather than a duplicate remediation proposal.
- Independent blockers: the mixed Claude Code selection fixture combines a
  runtime extension with an inaccurate permission-containment claim.
- Non-trigger restraint: the portable-standard test fixture requires an
  explicit absence of a compatibility warning.
- GitApex boundary: held-out fixtures reject a proposal for custom GitApex
  frontmatter.
- Remediation and evidence-state discrimination: the retry fixtures require
  standard `compatibility` self-declaration and Unknown restraint rather than
  generic compatibility prose. The independently authored conflicting-
  semantics fixture covers an existing but incomplete declaration and keeps
  its separate Mechanism-fit blocker.

Blind spot pass: the corpus covers declared and undeclared limitations,
standard and non-standard placement, warning-only severity, a mixed blocker,
and a portable non-trigger. It does not prove how an undocumented future
runtime field behaves; the compatibility baseline must label such cases
Unknown and must be refreshed as product documentation changes.

The `cohesion-independently-changeable-branches-train.yaml` /
`cohesion-temporal-grouping-selection.yaml` / `cohesion-sequential-
orchestrator-restraint.yaml` triple was added for issue #334 (the Skill vs.
multiple skills / cohesion Mechanism-fit check), for the same reason as
every prior addition: none of the prior 37 fixtures probe whether the
review can classify a target's cohesion type and decide whether it should
split into several skills. `-train.yaml` sits in train (a
`repo-hygiene-toolkit` skill bundling API-key rotation, commit-message
reformatting, and changelog generation -- coincidental/logical cohesion,
each branch independently triggerable and independently changeable -- it
motivated the edit). `-selection.yaml` sits in selection and uses a
distinct domain and the *other* named sub-type (`release-day-ops`
bundling a deploy, a Slack standup post, and log archival -- temporal
cohesion, grouped only by timing, not by any shared invariant) so the
gate measures generalization of the taxonomy and decision rule, not
memorization of the train fixture's domain or coincidental/logical
wording. `-restraint.yaml` sits in test (read once, for the final report)
and checks the restraint side the issue explicitly required: a
`new-service-onboarding` orchestrator whose four steps each feed the next
and converge on one outcome (sequential cohesion, touching several
systems) must not be false-positively split merely for having steps.

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

The `tool-capability-verification-train.yaml` / `-selection.yaml` pair was
added for issue #200's Tool-capability verification check (a sixth
Mechanism-fit check), for the same reason as prior additions: none of the
prior 33 fixtures probe whether the review catches a target's own
unverified claim that a named tool/MCP subcall can detect, verify, or
reconstruct something. `-train.yaml` sits in train (a PR-history-audit
skill claiming a commit-listing subcall can detect a force-push -- it
motivated the edit, directly mirroring the retrospective's own motivating
incident). `-selection.yaml` sits in selection and uses a distinct domain
and a distinct tool/claim pair (a metrics-query subcall wrongly claimed to
attribute a rollback to a specific operator, not a force-push) so the gate
measures generalization, not memorization of the train fixture's wording.
No dedicated restraint fixture was added for this check; the existing
`guardrail.yaml` / `no-fabricated-violation.yaml` fixtures already probe
generic false-positive restraint across the whole rubric.

The `consumer-repo-convention-deference-train.yaml` / `-selection.yaml`
pair was added for issue #200's other checklist item, a new Dimension 6
(Durability) bullet, for the same reason: none of the prior 33 fixtures
probe whether the review catches a target hardcoding this origin
repository's own issue/PR title-body convention as universal instead of
deferring to the consumer repository's own convention -- a different
failure shape from the existing issue/PR-*number*-citation sub-check.
`-train.yaml` sits in train (an issue-filing step with a fixed title
prefix and heading set -- it motivated the edit). `-selection.yaml` sits
in selection and uses a distinct domain and write-path step (a PR-body
heading set, not an issue title/body) so the gate measures generalization
rather than memorization. As with the pair above, no dedicated restraint
fixture was added; the generic restraint fixtures already cover it.

Two fixture-assertion bugs of the same recurring class this file has
already documented multiple times (run-to-run casing/paraphrase variance,
not a rubric regression) were found and fixed during this iteration's own
gate run, before any score was banked: `consumer-repo-convention-
deference-*`'s first-draft assertion required the literal phrase
"consumer repository," which one correct after-dispatch instead phrased
as "consuming repository" -- tightened to the rubric's own verbatim Fail
criterion, `"asserts its convention unconditionally,"` which a dispatch
citing the new bullet reproduces exactly. `tool-capability-verification-
selection.yaml`'s first-draft assertion required "cannot attribute,"
absent from at least one otherwise-correct after-dispatch that reasoned
to the identical verdict via different phrasing -- loosened to `"actor"`
(confirmed present in one live sample, absent from two live before-runs).
A third, pre-existing bug in this same class was also found and fixed on
two fixtures this iteration's edit touches indirectly: `edge.yaml` and
`mechanism-fit-subagent.yaml` both required lowercase `"headline
finding"`, which a dispatch bolding it as a section title ("**Headline
finding**") or as a standalone lowercase mid-sentence mention
inconsistently satisfies -- both changed to the case-agnostic
`"eadline finding"` (dropping the leading letter), immune to either
capitalization.

The `opus5-redundant-verification-*` and `opus5-unbounded-subagent-*`
pairs, plus the shared `opus5-restraint-domain-verification-and-bounded-
subagent.yaml` fixture, were added for gitapex#495 (the two new Mechanism
fit/Dimension 2 checks grounded in Anthropic's "Prompting Claude Opus 5"
guide), for the same reason as every prior addition: none of the prior 52
fixtures probe a generic re-verification/self-correction instruction that
duplicates a frontier-tier model's own default behavior, or an unbounded
subagent-delegation instruction with no stated criterion or cap.
`opus5-redundant-verification-fail.yaml` sits in train (a Frontier-declared
changelog-entry-writer skill instructing "always double-check your answer
before responding" -- it motivated the Dimension 2 addition).
`opus5-redundant-verification-generalizes.yaml` sits in selection and uses a
distinct domain and phrasing (a database-migration-planner's "re-verify the
plan is correct" instruction, not "double-check your answer") so the gate
measures generalization of the new Fail instance, not memorization of the
train fixture's exact wording. `opus5-unbounded-subagent-fail.yaml` sits in
train (a repo-wide-license-audit skill dispatching a subagent per file, no
criterion or cap -- it motivated the Subagent delegation scope check).
`opus5-unbounded-subagent-generalizes.yaml` sits in selection and uses a
distinct domain and trigger (a support-ticket-triage skill dispatching a
subagent per incoming ticket) so the gate measures generalization rather
than memorization of the train fixture's "for every file" wording.
`opus5-restraint-domain-verification-and-bounded-subagent.yaml` sits in test
(read once, for the final report) and checks the restraint side for both
new checks at once: a flaky-test-triager skill whose verification step
names its own domain-specific task (re-running a candidate to confirm it
reproduces, not generic double-checking) and whose delegation step states a
criterion and a cap (batch by suite size, or triage directly for a small
suite) must not be false-positively flagged by either new check.

The `confidentiality-awareness-train.yaml` / `-selection.yaml` pair was
added for gitapex#537 (the new Confidentiality awareness cross-cutting
axis), for the same reason as every prior addition: none of the prior 57
fixtures probe whether the review discloses that a reviewed skill's own
procedure handles secrets, credentials, PII, or private data, and none of
the prior fixtures' target skills contain such a step at all --
`portability-declarative-fact-claim.yaml` (train split) and
`cohesion-independently-changeable-branches-train.yaml` (train split) each
mention a secret-rotation/secret-scanning tool by name, but neither
fixture's own `expected` assertions reference confidentiality, secrets, or
credentials, and the Confidentiality awareness axis is declaration-
independent of those two fixtures' actual failure shape (Mechanism-fit
Skill-vs.-multiple-skills cohesion and Portability's declarative-fact-claim
litmus test, respectively) -- so this pair is the first to probe the new
axis at all. `-train.yaml` sits in train (a `webhook-debugger` skill that
writes a full raw request/response, including the live bearer token, to a
local debug log with no redaction or scoping statement -- it motivated the
edit). `-selection.yaml` sits in selection and uses a distinct domain,
sensitive-data category, and sink (a `ticket-summarizer` skill forwarding
raw customer PII -- name, email, account number -- to a third-party
analytics webhook, not a credential written to a local file) so the gate
measures generalization of the axis across data category and sink, not
memorization of the train fixture's credential/local-log wording. No
dedicated restraint fixture was added, following the same disclosed
reasoning the `tool-capability-verification` and
`consumer-repo-convention-deference` pairs above used: the existing
`guardrail.yaml` / `no-fabricated-violation.yaml` fixtures already probe
generic false-positive restraint across the whole rubric, and this axis's
own Applicability clause (fires only on an ordinary procedure step, not a
hypothetical example or a Stop-boundary prohibition naming the risk only
to forbid it) is a narrower, declaration-independent test than a
freestanding restraint fixture would add coverage for.

Blind spot pass for this addition: the pair covers a credential handled by
a local-sink step and PII handled by a third-party-sink step, both in the
`PROPOSE_CONFIDENTIALITY_SAFEGUARD` direction. It does not cover the
`CONFIDENTIALITY_ACKNOWLEDGED` state (a target that already states an
accurate safeguard) or a target that mentions sensitive data only as a
Stop-boundary prohibition rather than an ordinary step -- both left as a
disclosed, open gap for a future addition rather than silently assumed
covered.

**Gate result: see the Kept-edit log below.**

**Follow-up (gitapex#537, same issue): payment/financial account data
named explicitly.** A follow-up question (does the Applicability clause's
"PII" bucket reliably cover a bare credit-card number with no other
conventionally-named PII field present?) found the wording ambiguous:
"PII" read narrowly (name/email/address-type identifiers) could plausibly
miss a step that handles nothing but a card number, which also carries
its own distinct regulatory regime (PCI-DSS) separate from general
privacy law. `references/rubric.md`'s Applicability clause and `SKILL.md`'s
mirrored pointer were extended to name "payment/financial account data
(credit card or other payment-card numbers, bank account or routing
numbers)" explicitly, alongside a new selection fixture,
`confidentiality-awareness-payment-data-selection.yaml` (a
`checkout-debugger` skill logging a bare replayed card number to a local
debug file, with no name/email/other-PII field anywhere in the excerpt --
isolating the payment-data sub-category from the two original fixtures,
which both bundle it alongside more obviously-named PII).

**Gate result, same `claude -p` isolation methodology as above (pre-edit
pinned at `bd6fef7`), one fresh dispatch per side against only
`confidentiality-awareness-payment-data-selection.yaml`:**

| Fixture | Before | After |
|---|---|---|
| `confidentiality-awareness-payment-data-selection.yaml` | 1.000000 (fresh) | 1.000000 (fresh) |

`gitapex_score_contract.py --compare-to 1.000000`: `1.000000 REJECT` (tie at the
scorer's ceiling). The *before* dispatch already correctly generalized
"PII" to cover a bare, unlabeled card number without the explicit
category -- quoting it directly: *"a procedure step that handles a
payment credential (PAN) with zero stated safeguard... this is the
rubric's Confidentiality awareness axis firing at its worst case."* So
this specific live trial (Sonnet, high effort) did not demonstrate the
ambiguity the edit was written to close.

**Kept anyway, REJECT disclosed rather than hidden -- the same
disposition the gitapex#406 entry above used for a drift-correction the
corpus could not score.** The tie reflects a real limit of this specific
trial (one strong-tier model, one sample), not evidence the edit adds
nothing: (1) the corpus-coverage argument stands independent of this
trial's outcome -- Dimension 1's own "specific key terms, no filler"
principle, applied to the rubric's own Applicability wording, favors an
explicit, regulation-grounded category over reliance on a generalization
one live sample happened to make correctly; (2) issue #500's own Phase 1
cross-model data already shows weaker tiers under-performing specifically
on axis-disambiguation content (the `compatibility-*` fixtures), the same
shape of risk this edit guards against for a tier this gate has not
tested; (3) the cost is at or near zero -- a few explicit words, no
added ambiguity, `gitapex_check_skill_shape.py` unaffected (46/46 both before and
after). Per this repository's own drift-correction precedent, a tie is a
statement about what the current corpus can measure, not a verdict on the
edit's merit -- extending the corpus with a fixture built specifically to
expose the narrow-"PII"-reading failure mode (a weaker-tier trial, or a
harder-to-generalize phrasing than "full card number") is the honest next
step if this edit's real effect is ever to be measured on this corpus,
not reclassifying this tie to force a KEEP.

**Second follow-up (gitapex#537, same issue): material non-public
business information (MNPI) named explicitly.** A further question (does
the axis cover non-public business/corporate information whose premature
disclosure could be insider-trading-adjacent, e.g. undisclosed earnings
or deal terms) found the same shape of gap: this material fits the
generic "private/internal-only data" bucket, but that bucket read
narrowly could miss it, and it carries its own distinct legal regime
(securities/insider-trading law) the same way payment-card data carries
PCI-DSS. Extended `references/rubric.md`'s Applicability clause and
`SKILL.md`'s pointer to name it explicitly, plus a new selection fixture,
`confidentiality-awareness-mnpi-selection.yaml` (an `earnings-prep-
assistant` skill posting a draft quarterly earnings summary -- undisclosed
revenue/margin/guidance figures -- to a company-wide Slack channel with no
access restriction or embargo statement; unlike the PII/payment-data
fixtures, this target handles no personal data at all, isolating the MNPI
sub-category cleanly).

**Gate result, same methodology, pre-edit pinned at `2e6de04`, one fresh
dispatch per side against `confidentiality-awareness-mnpi-selection.yaml`:**

| Fixture | Before | After |
|---|---|---|
| `confidentiality-awareness-mnpi-selection.yaml` | 1.000000 (fresh) | 1.000000 (fresh) |

`gitapex_score_contract.py --compare-to 1.000000`: `1.000000 REJECT` (tie at
ceiling, the same shape as the payment-data follow-up immediately above).
The *before* dispatch's own text names why: it explicitly noted "the
rubric's own Confidentiality-awareness category list doesn't quite name
[MNPI]... but functionally, this is the thing most wrong with the skill,"
then generalized from the generic `private/internal-only data` bucket to
the correct verdict anyway. **Kept anyway, REJECT disclosed, same
disposition and reasoning as the payment-data entry above** -- not
repeated in full here; the corpus-coverage argument, the cross-model
Phase 1 evidence, and the near-zero cost all apply identically.

**Pattern across both follow-ups so far:** two independent live trials
(payment data, MNPI), two independent ties at the scorer's ceiling, both
because this specific strong tier (Sonnet, high effort) already
generalizes a narrow bucket correctly. This is becoming a standing,
disclosed limitation of measuring precision-only wording edits against a
single strong-tier live sample, not a new finding each time -- a
weaker-tier or repeated-trial measurement (issue #500 Phase 2, not yet
scheduled) remains the honest way to actually detect the gap these edits
guard against, per the corpus-coverage reasoning already on record.

**Third follow-up (gitapex#537, same issue): the business-information
bucket broadened, not re-scoped a third time.** A further question (does
the axis cover competitively-sensitive cost/pricing data that harms a
business regardless of any securities-law exposure -- e.g. a private
company with no insider-trading angle at all) exposed that the just-added
MNPI wording was itself too narrowly scoped: its parenthetical named only
"insider-trading- or market-abuse-adjacent" disclosure, which does not
obviously cover ordinary trade-secret/competitive-harm data. Rather than
add a third standalone named category (continuing an unbounded
enumeration this rubric's own Dimension 2 conciseness discipline would
flag as sprawl if a target skill did it), broadened the existing
`material non-public business information` bullet into `confidential or
competitively-sensitive business information`, explicitly covering both
the insider-trading-adjacent harm mechanism and ordinary trade-secret/
competitive-harm data (cost structure, supplier pricing, unreleased
strategy) as two named anchors under one bucket, with an explicit note
that these are illustrative, not an exhaustive enumeration.

Added `confidentiality-awareness-trade-secret-selection.yaml`: a private
company (no securities-law angle at all) emailing its own internal cost
breakdown to an external supplier during a price negotiation --
deliberately the sub-case the narrow MNPI wording's parenthetical did not
name, to test the broadened wording against exactly the gap that
motivated it, distinct from `confidentiality-awareness-mnpi-selection.yaml`'s
publicly-traded/earnings framing.

**Gate result, same methodology, pre-edit pinned at `754bb54`, one fresh
dispatch per side against `confidentiality-awareness-trade-secret-selection.yaml`:**

| Fixture | Before | After |
|---|---|---|
| `confidentiality-awareness-trade-secret-selection.yaml` | 1.000000 (fresh) | 1.000000 (fresh) |

`gitapex_score_contract.py --compare-to 1.000000`: `1.000000 REJECT` -- a third
consecutive tie at the scorer's ceiling. The *before* dispatch (narrow,
insider-trading-scoped MNPI wording) already generalized `"material
non-public business information"` past its own parenthetical's explicit
insider-trading/market-abuse scoping to cover a private company's
supplier-negotiation cost leak; the *after* dispatch (broadened wording)
cited the new text directly ("Internal cost structure is the rubric's own
named example of competitively-sensitive business information"). **Kept
anyway, REJECT disclosed, same disposition as the two entries above** --
not repeated in full.

**Consolidated pattern, three follow-ups (payment data, MNPI, trade
secret/broadening): three independent live trials, three ties at the
scorer's ceiling, all for the same underlying reason** -- this strong
tier (Sonnet, high effort) reliably generalizes past a narrow or generic
bucket to the correct sensitive-data instance and safeguard proposal on a
single live sample, so a substring scorer measuring only "did the exact
token/heading appear" cannot detect what these wording edits add at this
tier. This is now a standing, disclosed limit of this measurement
approach for precision-only Applicability wording, not three independent
surprises -- the honest way to actually measure whether these edits earn
their keep is a weaker-tier and/or repeated-trial run (issue #500 Phase
2, not yet scheduled), not continued single-strong-tier single-trial
gating. None of the three edits are reverted on this basis: each has an
independent, freestanding rationale (a named, distinct regulatory or harm
regime; Dimension 1's own specificity principle applied to the rubric's
own wording; near-zero cost; no shape-check regression) that does not
depend on this specific corpus detecting an improvement.

Future edits to this rubric should reuse this same split rather than
re-deriving one per iteration, so the selection split stays genuinely
held out across iterations. If a future edit targets a topic none of the
27 fixtures probe, add motivated cases to train and fresh generalization
cases to selection before scoring, and record the addition here.

## Blind spot pass

This corpus's own blind-spot disclosures are not consolidated into one
section; they live inline, within `## Compatibility-awareness branch
coverage` above, next to the fixture sets they qualify. That section
documents fixture-corpus construction broadly (compatibility, cohesion,
capability-assumption, ablation-capability, tool-capability, scoring-axis,
ordering-rule-totality, model-effort-tier-fit, portability, opus5, and
confidentiality-awareness fixtures) -- a wider scope than a blind-spot
declaration alone, so it is kept as its own section rather than renamed.
Two disclosures already state a genuine remaining gap explicitly:

- The compatibility-awareness corpus (see `## Compatibility-awareness
  branch coverage` above): "It does not prove how an undocumented future
  runtime field behaves; the compatibility baseline must label such cases
  Unknown and must be refreshed as product documentation changes."
- The confidentiality-awareness corpus (same section, gitapex#537
  addition): "It does not cover the `CONFIDENTIALITY_ACKNOWLEDGED` state
  ... or a target that mentions sensitive data only as a Stop-boundary
  prohibition rather than an ordinary step -- both left as a disclosed,
  open gap for a future addition rather than silently assumed covered."

This section is added by the split.md/split.json migration (issue #928) to
satisfy the standardized heading convention shared across this repository's
five gated skills' `split.md` files; it does not restate or replace either
disclosure above, both of which remain the authoritative, dated record.

## Iteration: issue #116 gate 3, ranking/tie-break totality item

Candidate edit: add a bullet to `references/rubric.md`'s Dimension 4
(Clarity and structure) requiring totality verification for any
enumerated ranking/tie-break rule (every pair of distinct values
ordered, a final stable key for full ties) -- see issue #116, Repair 1
for the exact proposed wording.

Precondition and splits: satisfied for that historical iteration, per this
file's then-current corpus (13 fixtures,
5:5:3 with this iteration's additions -- see Assignment above).

### Gate result

The selection-split baseline (5 fixtures: `edge.yaml`,
`mechanism-fit-subagent.yaml`, `third-party-not-authoritative.yaml`,
`scoring-axis-uncontrolled-speed-claim.yaml`,
`ordering-rule-totality-distinct-skill.yaml`) was measured live -- one
fresh subagent dispatch per fixture, following `evaluating-skill-quality`'s
own Procedure against the *unedited* `references/rubric.md` -- and
scored with `skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`
against each fixture's `expected` block. Selection mean: **1.000000**
(all 5 fixtures scored 1.0; the new `ordering-rule-totality-distinct-skill`
fixture's assertions -- `Elevated`, `Standard`, `tie` -- were already
satisfied by a careful review applying the *current* Dimension 4
bullets, without the proposed totality item). Since
`gitapex_score_contract.py`'s score is bounded to `[0,1]` and the baseline is
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

This edit is **not applied** to `references/rubric.md` in this PR.

## Iteration: #393, dogfooding-driven dimension 2/5/7 fixes

Candidate
edit (already merged; this entry records the gate retroactively, per
issue #398): deduplicate a near-verbatim triplicated "step-level finding"
disclaimer across `references/rubric.md`'s three step-level Mechanism-fit
subsections (Skill-step vs. bundled script, Model/effort tier fit,
Tool-capability verification) to one canonical statement plus short
back-references; extract dimension 7's ISTQB/xUnit Test Patterns block to
a new conditional reference, `references/script-test-quality.md`; merge
`references/subagent-isolation-registry.md` into
`references/adversarial-self-audit.md` as a new "Isolation verification"
section, dropping the common-case dispatch's mandatory reference-file
count from four to three; fix a stale "17 skills" count (the repository
has 19) in both files; fix a broken sibling-file link in `rubric.md`
(caught by external review, `chatgpt-codex-connector[bot]` on PR #393).
Full diff: PR #393.

**Correction (found by external review, `chatgpt-codex-connector[bot]`
on PR #399):** this iteration was first recorded, on this same PR, as a
**pruning-only KEEP**. That classification was wrong.
`skills/scorer-gated-skill-edits/SKILL.md`'s own eligibility rule --
"Pruning-only is eligible only when the patch deletes text and adds or
rewords no behavior; a replacement, mixed add/delete patch, relabeling,
or uncertain classification uses the ordinary gate" -- does not fit
#393's actual diff: it adds a new file
(`references/script-test-quality.md`), adds new subprocess tests, adds
new connective prose inside `adversarial-self-audit.md`'s merged-in
Isolation verification section, and rewords `SKILL.md`'s Subagent
dispatch pointer sentence -- a mixed add/delete/reword patch, not
deletion-only. Reclassified as **ordinary** below, moved to this
Rejected-edit log from the Kept-edit log for that reason (the corrected
entry's classification and verdict changed; its measurements did not).

**Classification: ordinary** (corrected). Every heading name,
Applicability/Fail/Pass criterion, and diagnostic phrase the existing
40-fixture corpus checks for is still confirmed byte-identical before and
after by direct `git diff` inspection against the commit immediately
prior to #393's first commit (`147082332919aaab7d98afcb9721835595bafd06`)
-- none of the touched hunks fall inside Skill vs. subagent, Skill vs.
hook, Portability level, Capability assumption's grading bullets,
Cohesion, or any of dimensions 1-6/8-9's substantive text; only the
trailing disclaimer paragraph in each of the three step-level checks,
dimension 7's block, an incidental aside, and prose outside any graded
check were touched. That observation is still true and still the reason
the selection mean ties exactly -- it just does not make the patch
eligible for the pruning-only gate, which requires deletion-only, not
merely "no effect on existing fixture scores."

**A discovered gap, disclosed here rather than silently absorbed:**
tracing the "before" baseline back required walking the commit range
between this log's last entry (issue #334, cohesion) and #393's own base
commit. That range turned out to carry several substantive, already-
merged iterations with no corresponding entry in this file at all: the
original `references/adversarial-self-audit.md` addition, the Verdicts
section's `Not-well-formed`/`Indeterminate` tokens, the `Execution
requirements` sidecar section, and PR #380's dimension-7 ISTQB/xUnit
content itself (the same content #393 later extracted back out). None of
these are new findings -- they are already-shipped, working content --
but this file's own methodology notes elsewhere insist on verifying
directly rather than assuming a gate was run; a missing log entry is
exactly the shape of gap that discipline exists to catch, and it was
found here only incidentally, not because #393's own gate required
reconstructing that history. Direct diff inspection of the full
`86deac0..147082332919aaab7d98afcb9721835595bafd06` range confirmed none
of it touched any of the 14 selection fixtures' asserted content (see
full hunk listing in issue #398), so this iteration's own before-baseline
is sound regardless -- but the historical gap itself is real and is
**not** backfilled here; a full reconstruction of those iterations' own
gates, if wanted, is separate follow-up work (see issue #398's Scope
section), not a precondition for scoring #393 itself.

### Gate result

Methodology: 12 of the 14 selection fixtures' target sections are
confirmed untouched across the entire `86deac0..HEAD` range (the
gap-discovery diff above doubles as this confirmation) and reuse their
#334-recorded after-scores unchanged on both sides, without a fresh
dispatch -- the same "confirmed by inspection, not re-run" precedent this
file's own #183/#185 merge-reconciliation entry already established. The
other 2, `model-effort-tier-fit-unjustified-effort.yaml` and
`tool-capability-verification-selection.yaml`, sit in the exact
subsections #393 edited (even though the edited paragraph itself sits
after what these fixtures assert on), so each got a genuine fresh
**after** dispatch against the current (post-#393) working tree -- one
fresh, isolated `claude -p` subprocess per fixture, invoked from a
working directory outside this repository's own `CLAUDE.md` ancestry per
`references/adversarial-self-audit.md`'s Isolation verification section
(this repository still has no registered `Skill` tool for its own
unpublished `evaluating-skill-quality` content, the same disclosed
workaround every prior iteration in this log has used), scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 0.900000 (reused, #334 after) | 0.900000 (unaffected, confirmed by inspection) |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #334 after) | 1.000000 (unaffected, confirmed by inspection) |
| `third-party-not-authoritative.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused, #334 after) | 1.000000 (fresh) |
| `portability-issue-number-citation.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `heldout-vague-completion.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `capability-assumption-frontier-flags-explanation.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `ablation-capability-runner-exists-not-run.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |
| `tool-capability-verification-selection.yaml` | 0.750000 (reused, #334 after) | 0.750000 (fresh) |
| `consumer-repo-convention-deference-selection.yaml` | 0.750000 (reused) | 0.750000 (unaffected, confirmed by inspection) |
| `cohesion-temporal-grouping-selection.yaml` | 1.000000 (reused) | 1.000000 (unaffected, confirmed by inspection) |

Selection mean: **before 0.957143 -> after 0.957143** (exact tie). Run via
the ordinary gate, `gitapex_score_contract.py --compare-to 0.957143 --scores
after-scores.txt` (no pruning-only flags, per the correction above):
`0.957143 REJECT`. Ordinary ties are rejected -- this skill's own Stop
boundaries state it directly: "Never keep a worse-correctness edit.
Reject ordinary ties."

`tool-capability-verification-selection.yaml`'s fresh after-dispatch
correctly identified the target's tool-capability contradiction and cited
"Tool-capability verification" by name, but did not reproduce the exact
`"actor-identity"` compound (using "specific individual"/"who triggered
the override" instead) -- this is the same narrow-marker-recall
brittleness this exact fixture's history already documents twice over
(issue #200's correction log, issue #334's own entry above), not a new
regression from #393's content, which never touches the "Check" paragraph
this marker comes from.

**Context cost, informational only under the ordinary gate (not
gate-determining -- that machinery is pruning-only-specific, and this
candidate does not qualify, per the correction above):** total line
count across the mandatory common-case dispatch set (`SKILL.md` +
`references/rubric.md` + `references/adversarial-self-audit.md`; the
prior side folds in `references/subagent-isolation-registry.md`,
mandatory before the merge whenever the calling repository has its own
`CLAUDE.md`/`AGENTS.md`). Before: 500 + 1538 + 117 + 91 = 2246. After: 500
+ 1397 + 206 = 2103. A real reduction, noted for the record, but the
ordinary gate's strict-improve-or-reject rule does not consider context
cost at all -- correctness is tied, and a tie is rejected regardless of
what else changed.

### Transfer check

Not run this iteration. This boundary ("Never ship a
skill that has not passed a transfer check") specifically guards a
KEEP/ship decision; since this iteration's own result is REJECT, not a
recommendation to keep or ship, the boundary is not itself violated by
this record. Its absence across every OTHER entry in this log (all of
which end in KEEP, none of which ran a transfer check) remains the same
disclosed, unresolved gap issue #200 first named -- raised again here,
not newly introduced by this entry.

### Verdict

**REJECT.** Ordinary gate, exact tie (0.957143 -> 0.957143) across all 14
selection fixtures (12 confirmed unaffected by direct inspection, 2
re-confirmed with a genuine fresh dispatch), rejected per the strict
improve-or-reject rule. The tie reflects a corpus-coverage gap, not
evidence #393's content was harmful: none of the 40 fixtures target what
the edit actually touches (the triplicated-disclaimer dedup, the
mandatory-reference-file-count reduction, or dimension 7's relocated
test-methodology content), so no fixture could register an improvement
either way. #393 remains merged on its own independent merits
(deterministic shape checker 41/41, full pytest suite 247/247, external
code review) -- this record reflects only that `scorer-gated-skill-edits`'
own measured discipline, correctly classified and applied retroactively,
provides no measured evidence to justify a KEEP for this specific edit
against the current fixture corpus. Extending the corpus with fixtures
that actually probe dimension 2/5/7 content is the honest next step if
this edit's real effect is ever to be measured -- not reclassifying it
after the fact to force a KEEP. A real historical gap in this file's own
record (several undocumented intervening iterations between issue #334
and #393, found while tracing the before-baseline) is disclosed above and
tracked separately (issue #398) rather than backfilled here.

## Iteration: issue #406, Contract discipline precondition-enumeration sync

Candidate edit, two parts, both confined to
`references/rubric.md`'s `## Contract discipline` section: (Part 1)
correct the precondition bullet's two stale enumeration gaps -- it
described step 2 as only "mechanism fit is checked" and step 4 as only
"portability level is established," omitting step 2's Blind spot pass and
step 4's capability assumption plus the declaration-vs-pin consistency
check, all of which those Procedure steps actually run today; and (Part 2)
add a "Keep this enumeration in sync" invariant bullet requiring any edit
that changes what one of `SKILL.md`'s Procedure steps 1-4 establishes to
update the precondition/postcondition/invariant descriptions in the same
change. Full text: see this PR's diff. Root cause of the drift: capability
assumption (issue #183 iteration below) and the Blind spot pass (issue
#149 iteration below) were both wired into `SKILL.md`'s Procedure steps
without either gated edit's acceptance criteria requiring the Contract
discipline *description* of those same steps to be updated too -- which is
exactly the gap Part 2's new invariant bullet now guards against.

Precondition and splits: satisfied by reuse of the existing corpus (50
fixtures, 19:20:11 -- see Assignment above); no new fixture was added this
iteration. That omission is a deliberate, disclosed scope decision, not an
oversight -- issue #406 explicitly scopes out authoring a purpose-built
fixture, and (per the Blind spot pass below) no existing fixture can score
this edit, so a KEEP was known to be unreachable before scoring.

**Blind spot pass (scorer-gated precondition gate):** named explicitly.
The fixture corpus has a coverage blind spot for this exact edit: none of
the 50 fixtures probe Contract discipline's own precondition-enumeration
accuracy at all. Every fixture reviews an invented *target* skill and
asserts on findings about that target (mechanism fit, the nine
dimensions, the Blind spot pass firing on the target's domain, capability
assumption grading of the target, compatibility awareness, cohesion,
etc.); none asserts on this skill's own self-description of its review
procedure. This is the identical corpus-coverage-gap class the issue #393
Rejected-edit entry above already disclosed ("none of the 40 fixtures
target what the edit actually touches"), applied here to the reviewer's
own contract text.

Classification: ordinary (adds and rewords prose; not pruning-only, so the
strict improve-or-reject gate with ties rejected applies, not the
pruning-only lexicographic exception -- the same classification the issue
#393 entry above was corrected to).

### Gate result

**REJECT (tie), concluded analytically from the gate's
construction rather than by re-running the selection split.** Three
independent legs, each verified against the actual current (post-merge)
state, support the tie:

1. **Assertion-surface disjointness (verified by reading all 20 selection
   fixtures' `expected` blocks in this merged tree).** Every selection
   fixture's `output_contains` / `output_not_contains` strings reference
   only findings about its target skill; not one references Contract
   discipline, "precondition," the precondition/postcondition/invariant
   enumeration, or the new "Keep this enumeration in sync" bullet. The
   scorer (`gitapex_score_contract.py`) matches substrings in the *review
   transcript*, not in `rubric.md`; text the edit adds to `rubric.md`'s
   own Contract discipline section cannot appear in any correct review of
   an unrelated target, so no fixture's score can move on account of it.
   This is the same "confirmed by inspection" basis the issue #393 entry
   above used for its 12 unaffected fixtures.
2. **No behavioral delta.** The edit changes no dimension's grading
   criteria and no step-2/step-4 behavior. Step 2's Blind spot pass and
   step 4's capability-assumption + declaration-vs-pin check are each
   already independently instructed in `SKILL.md`'s Procedure and in
   `rubric.md`'s own Unknowns framework and Capability assumption sections
   (all unchanged); the precondition bullet is a cross-reference summary,
   so completing it adds no instruction a correct review was not already
   following.
3. **Ceiling on the only plausibly-nudged fixture.** The single fixture
   whose scored behavior this edit could conceivably nudge --
   `blind-spot-pass-generalizes.yaml`, via marginally higher Blind-spot-
   pass adherence from the completed summary -- already sits at the
   scorer's `1.000000` ceiling in the issue #393 table above, so it cannot
   rise.

The last recorded selection mean is **0.957143** (issue #334 / issue #393,
over the then-14-fixture selection split); the six `compatibility-*` and
the `cohesion-temporal-grouping` selection fixtures added since do not
change this REJECT, because leg 1 makes before == after true for every
selection fixture individually regardless of its own score, so the
selection mean is unchanged whatever its exact current value over the full
20-fixture split. `after > before` is therefore unsatisfiable by
construction, so **REJECT** (ordinary ties rejected -- "Never keep a
worse-correctness edit. Reject ordinary ties."). Following this log's own
issue #116 gate-3 and issue #393 precedents, an unsatisfiable-improve
REJECT is concluded from the gate's construction (the disjoint assertion
surface plus the ceiling above) rather than by re-running dispatches whose
outcome that construction already fixes -- a direct consequence of the
scorer's bounded range and the edit's assertion-surface disjointness, not
an assumption substituted for measurement.

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**Why this REJECT ships the edit anyway.** This is the same disposition
the issue #393 entry above reached: a corpus-coverage-gap tie is "not
evidence [the] content was harmful," and the content "remains merged on
its own independent merits." Issue #406's edit is a correctness fix to the
reviewer's own contract self-description, independently verified against
`SKILL.md`'s current step 2 and step 4 text and against the deterministic
shape checker (42/42) -- it corrects a factual drift, it does not claim to
raise a review score. The scorer gate's REJECT records only that the
fixture corpus cannot score this class of edit (the disclosed blind spot),
not that the edit is wrong. This contrasts with the issue #116 gate-3
entry above, whose *speculative* Dimension-4 improvement was correctly
withheld on its tie; the durable distinction is that the scorer gate
governs measured improvements to *scored* review behavior, and a
drift-correction to *un-scored* meta-procedure text falls outside what it
can validate -- which is exactly why Part 2 adds a non-scored invariant
bullet as the standing guard against this drift recurring. Per CLAUDE.md
section 3 ("Establishing an invariant ... ship its drift gate in the same
change, not a follow-up") -- and a Codex P1 review on PR #411 raising the
same point -- that invariant is not left to prose: this PR also ships a
deterministic drift gate,
`skills/evaluating-skill-quality/scripts/test_gitapex_contract_precondition_sync.py`,
which fails in CI if a checkpoint (`mechanism fit`, `Blind spot pass`,
`deterministic shape`, `portability level`, `capability assumption`,
`declaration-vs-pin`) is present in `SKILL.md`'s Procedure steps 1-4 but
missing from the Precondition bullet (or vice versa) -- the exact class of
drift issue #406 corrected, now enforced mechanically rather than by a
future gate the corpus cannot run.

**Next attempt for a genuine KEEP** (out of scope for issue #406, and the
same honest next step the issue #393 entry named): author a purpose-built
fixture that probes whether a review correctly attributes a wrong verdict
to a misjudged precondition step per Contract discipline's Fault-attribution
rule, with a train case motivating it and a distinct selection case
testing generalization, then re-gate. Until such a fixture exists, REJECT
is the expected and correct gate outcome for any edit to this section.

## Iteration: issue #149, Unknowns framework / Blind spot pass

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

### Gate result

**Full selection-split result, matched methodology, both directions, all
6 fixtures, one fresh dispatch per fixture per side (2 for
`blind-spot-pass-generalizes.yaml`, averaged to one fixture-level score;
1 each for the other 5), scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:**

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 | 1.000000 |
| `mechanism-fit-subagent.yaml` | 1.000000 | 1.000000 |
| `third-party-not-authoritative.yaml` | 0.888889 | 0.888889 |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 | 1.000000 |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 0.750000 (mean of 0.75, 0.75) | 1.000000 (mean of 1.00, 1.00) |

Selection mean: **before 0.939815 -> after 0.981482**. Run via
`gitapex_score_contract.py --compare-to 0.939815 --scores after-scores.txt`:
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement, matched methodology, complete 6-fixture
selection split -- not a partial or disclosed-limitation record.

## Iteration: issue #155, Model/effort tier fit

Candidate edit: add a new
`### Model/effort tier fit` subsection to `references/rubric.md` (a fifth
Mechanism-fit check, grounded in Anthropic's own guidance on choosing a
model tier and reasoning-effort level in Claude Code); wire it into
`SKILL.md`'s Mechanism-fit bullet list. Full text: see this PR's diff.

Precondition and splits: satisfied (19 fixtures, 7:7:5 with this
iteration's additions -- see Assignment above).

### Gate result

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
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

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
`gitapex_score_contract.py --compare-to 0.912698 --scores after-scores.txt`:
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement on the selection split (one real dip,
independently confirmed unrelated to the edit and disclosed), a clean
generalization result on the fixture built to test the new check, and a
confirmed restraint result on the held-out justified-pin fixture.

## Iteration: issue #165, portability litmus test for declarative fact-claims

Candidate edit: add an explicit litmus test to
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

### Gate result

Methodology, disclosed reuse: the other 7 selection fixtures' **before**
score for this gate = their **after** score from #155's already-completed
gate above (same committed file state at the time, same matched
methodology). Only the new selection fixture,
`portability-issue-number-citation.yaml`, needed a genuine fresh
**before** dispatch (run against `git show 89cc296:<path>`, the commit
immediately prior to this edit, to avoid a working-tree race). All 8
selection fixtures then got a fresh **after** dispatch against the
post-edit working tree, scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

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
`gitapex_score_contract.py --compare-to 0.937004 --scores after-scores.txt`:
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement on the selection split, a genuine
(construct-valid, after tightening one fixture's own assertion)
generalization result on the fixture built to test the new check, two
unrelated fixture-assertion bugs found and fixed along the way (disclosed,
not silently patched), and a confirmed restraint result on the held-out
legitimate-citation fixture.

## Iteration: issue #183, Sub-project B, Capability assumption grading semantics

Candidate edit: add the full per-dimension Broad / Frontier /
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

### Gate result

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
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

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
`gitapex_score_contract.py --compare-to 0.975000 --scores after-scores.txt`:
`0.985714 KEEP`.

`scoring-axis-uncontrolled-speed-claim.yaml` dipped from 1.000000 to
0.857143 (6/7 assertions) -- checked directly, this is the same class of
run-to-run subagent wording variance already documented twice above for
this exact fixture (issue #149's "6.5s/$0.03" paraphrase miss): this
round's after-dispatch answered the dimension-8 cost/success question
correctly and in full but never happened to mention running
`gitapex_check_skill_shape.py`, an assertion unrelated to anything this edit
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement on the selection split (one real, disclosed,
edit-unrelated dip; two fixtures scored for the first time), a genuine
content-driven generalization result on the fixture built to test the new
check (same verdict direction, different and correct rubric grounding), a
negation-trap fixture bug found and fixed before any score was banked,
and a restraint result on the held-out Adaptive fixture that is stronger
evidence of rigor than the clean pass it was designed to check for.

## Iteration: ablation-capability sub-check (dimension 8)

Candidate edit:
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

### Gate result

Methodology: one fresh, isolated subagent dispatch per side for each of
the two fixtures needing a genuine pair (this repository has no
registered `Skill` tool for its own unpublished `evaluating-skill-quality`
content, so each dispatch was instructed to read `references/rubric.md`
and `SKILL.md` directly -- `git show 228486c:...` for the before side, the
working tree for the after side -- and follow the Procedure by hand),
scored with `skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

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
`gitapex_score_contract.py --compare-to 0.975000 --scores after-scores.txt`:
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

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

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

### Gate result

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
`gitapex_score_contract.py --compare-to 0.954545 --scores after-scores.txt`:
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

### Verdict

**KEEP.** Strict improvement on the true, fully-merged 11-fixture
selection split (0.954545 -> 1.000000), with the one fixture whose
content could plausibly have interacted with both edits re-verified
fresh against the real merged file rather than assumed, and a
three-times-recurring fixture-assertion brittleness fixed at the root
instead of disclosed a third time.

## Iteration: issue #200, Tool-capability verification (sixth Mechanism-fit check) + consumer-repo issue/PR-convention deference (Dimension 6 bullet)

Candidate edit: add a `### Tool-capability verification`
subsection to `references/rubric.md`'s Mechanism fit section (a target's
own claim that a named tool/MCP subcall can detect, verify, or reconstruct
something must be checked against that tool's actual schema/docs, not
accepted on plausibility alone) plus a matching bullet in `SKILL.md`'s
Mechanism fit list and TOC entry; and a new Dimension 6 (Durability)
bullet banning a hardcoded, unconditional origin-repo issue/PR title-body
or workflow-ordering convention in Portable-declared content, distinct
from the existing issue/PR-*number*-citation bullet. Full text: see this
PR's diff. Scoped per the issue's own note: the original third item
(bare `CLAUDE.md ch.N` citations) is out of scope, already substantially
covered by the existing Portability-level litmus test and
`portable-no-repo-path-citation`/`portable-no-issue-citation` shape
checks, with the one remaining gap in that area tracked separately in
issue #192.

Precondition and splits: satisfied (37 fixtures, 16:13:8 with this
iteration's additions -- see Assignment above).

### Gate result

Methodology, disclosed reuse: the two edits land in disjoint rubric
sections (Mechanism fit; Dimension 6), each new bullet is appended after
existing content rather than modifying it, and neither touches any other
dimension. Of the 11 pre-existing selection fixtures, 7 assert on content
neither edit touches at all (`third-party-not-authoritative.yaml`,
`scoring-axis-uncontrolled-speed-claim.yaml`,
`ordering-rule-totality-distinct-skill.yaml`,
`blind-spot-pass-generalizes.yaml`, `heldout-vague-completion.yaml`,
`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`) and reuse their already-
established 1.000000 score unchanged on both sides -- disclosed reuse, the
same "never both" discipline this file's methodology notes have applied
throughout. The other 4 (`edge.yaml`, `mechanism-fit-subagent.yaml`,
`model-effort-tier-fit-unjustified-effort.yaml`,
`portability-issue-number-citation.yaml`) sit in the same sections either
edit touches, so each got a genuine fresh **after** dispatch (before
reused at 1.000000, since neither edit modifies the text those fixtures
actually assert on) rather than being assumed unaffected. The two new
selection fixtures each got a genuine fresh **before** dispatch, pinned to
the immutable pre-edit commit hash `8e1eb4249f12e03fbf6e42134c03af4c9ff7756b`
rather than the symbolic ref `HEAD` -- a first attempt at this gate used
`git show HEAD:<path>` for the before side and then committed the edit
before those dispatches had necessarily finished reading, moving what
`HEAD` resolved to mid-flight; caught before any score was banked (the
race Stop boundaries name directly) and corrected by re-dispatching both
against the pinned hash, which is immune to the race by construction. Two
of the touched-fixture after-dispatches and one new-fixture after-dispatch
returned only a status stub ("the dispatch is running... I'll relay it")
because the harness they ran in has its own `Agent`/subagent-dispatch
capability and, following `SKILL.md`'s Subagent-dispatch instruction
literally, tried to spawn a further nested dispatch rather than perform
the review itself -- caught immediately (the stub is not a review) and
redone with an explicit instruction not to delegate further, since the
dispatch is already the isolated fresh context the instruction calls for.

One fresh after-dispatch per touched pre-existing fixture, and two
independent fresh after-dispatches per new selection fixture (the second
sample happened to arrive as a nested dispatch from one of the stubbed
attempts above; kept and averaged per this file's own
`blind-spot-pass-generalizes.yaml` precedent for multiple genuine samples,
not discarded), scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused) | 1.000000 (fresh, 2 samples, both 1.000000) |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused) | 1.000000 (fresh) |
| `third-party-not-authoritative.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused) | 1.000000 (fresh) |
| `portability-issue-number-citation.yaml` | 1.000000 (reused) | 1.000000 (fresh) |
| `heldout-vague-completion.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `capability-assumption-frontier-flags-explanation.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `ablation-capability-runner-exists-not-run.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `tool-capability-verification-selection.yaml` | 0.500000 (fresh, pinned hash) | 0.875000 (fresh, mean of 2 samples: 1.000000, 0.750000) |
| `consumer-repo-convention-deference-selection.yaml` | 0.500000 (fresh, pinned hash) | 0.750000 (fresh, mean of 2 samples: 1.000000, 0.500000) |

Selection mean: **before 0.923077 -> after 0.971154**. Run via
`gitapex_score_contract.py --compare-to 0.923077 --scores after-scores.txt`:
`0.971154 KEEP`.

The two new fixtures' averaged after-scores are honestly reported below
their ceiling and disclosed in full rather than only the higher sample:
`tool-capability-verification-selection.yaml`'s two after-dispatches both
correctly reached the FAIL verdict and both cited the new
"Tool-capability verification" heading by name, but only one used the
specific word "actor" this fixture's assertion checks for as a second,
domain-specific confirmation (present in "aggregate rate time series carry
no actor-identity field," absent from two independent before-runs) --
scoring 1.000000 and 0.750000 respectively; the heading citation alone
already discriminates strongly, since it cannot appear in any before-run
by construction. `consumer-repo-convention-deference-selection.yaml`'s two
after-dispatches diverged more substantively: one directly cited the new
Dimension 6 bullet's own Fail criterion verbatim ("asserts its convention
unconditionally... hardcoded") and scored 1.000000; the other reasoned to
a related but distinct finding via the *pre-existing* Skill-vs-hook
Mechanism-fit check instead ("always use it as written" read as an
unenforced hook-shaped rule) without citing the new bullet at all, scoring
0.500000 -- a genuine, disclosed signal that this specific defect shape is
sometimes already caught by an existing check under a different
classification, not a fixture bug. Both dispositions are defensible
reviews of the same target; the averaged score reflects that real
variance rather than picking the more favorable sample.

Three fixture-assertion bugs of the recurring casing/paraphrase-variance
class this file has repeatedly documented were found and fixed during
this same gate run, before any score was banked -- see the Assignment
section's own paragraph above for the specifics (`"consumer repository"`
-> the rubric's verbatim Fail phrase; `"cannot attribute"` -> `"actor"`;
`"headline finding"` -> the case-agnostic `"eadline finding"` on two
pre-existing fixtures, `edge.yaml` and `mechanism-fit-subagent.yaml`).

**No dedicated restraint fixture in this iteration** (see the Assignment
section's rationale) -- restraint against over-firing either new check is
instead evidenced qualitatively across every after-dispatch above: none
of the touched pre-existing fixtures' after-runs (none of whose targets
make a tool-capability claim or hardcode an issue/PR convention) false-
positively invoked either new check, each explicitly stating "not
applicable" for Tool-capability verification and passing Dimension 6
cleanly.

### Transfer check

Not run this iteration. No prior entry in this log has
recorded an adjacent-model/harness transfer check (SkillOpt Section 4.3)
for any iterative rubric edit to date -- named here as a pre-existing,
still-open gap in this file's own practice, not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement on the selection split (0.923077 -> 0.971154)
across all 13 fixtures, with 7 pre-existing fixtures confirmed unaffected
by inspection, 4 pre-existing fixtures re-verified fresh rather than
assumed, both new fixtures' averaged (not cherry-picked) scores honestly
reported including one sample that reasoned to the same underlying finding
via a different, pre-existing check, three fixture-assertion bugs found
and fixed before any score was banked, and the pre-edit/post-edit race
condition caught and corrected before it could contaminate the gate.

**Correction (found by external review, an adversarial-verification pass
run against this PR by a Fable-model subagent instructed to refute, not
confirm, the change):** four defects, none individually flipping the
verdict, all fixed before merge.

1. **Undisclosed fourth assertion edit.** The disclosure paragraph above
   named three fixed assertions but omitted a fourth: `edge.yaml`'s
   `"never delete production data"` was also loosened to
   `"delete production data"` during the same gate run, for the identical
   reason (the confirmed-live after-transcript quoted the target's own
   Stop boundary with a capital "Never," which the original lowercase
   assertion missed). The fix was correct; failing to list it in this
   file's own disclosure was not. Recorded here now, and the omission
   itself is the finding -- a gate record that silently drops one of its
   own corrections is not a complete record, independent of whether the
   dropped correction was individually sound.
2. **A brittle positive assertion.** `tool-capability-verification-
   selection.yaml`'s `"actor"` assertion is satisfied by `"factor"` /
   `"contributing factor"` -- idiomatic vocabulary in this fixture's own
   root-cause-analysis domain -- which a wrong-direction or off-topic
   response could trip by accident. Tightened to `"actor-identity"`
   (confirmed present in the same live sample that motivated the original
   choice, confirmed absent from both before-samples and the other
   after-sample); the recorded 0.500000/0.875000 scores above are
   unchanged by this tightening, since the assertion narrows a match that
   was already present or already absent in every transcript scored.
3. **Rubric-text portability wording.** The new Dimension 6 bullet said
   "this origin repository" (a demonstrative that, read literally in a
   vendored copy, either dangles or narrows the check to conventions
   matching the rubric's own host) and left its Fail criterion unscoped by
   Portable/Repository-scoped, unlike the adjacent issue/PR-number
   citation bullet, which scopes explicitly in its own lead sentence. Both
   fixed in `references/rubric.md`: reworded to "the origin repository"
   matching the sibling bullet, explicit Portable-only scoping added to
   the lead sentence, and an explicit Repository-scoped carve-out added
   (a skill that has declared itself Repository-scoped is not asking this
   bullet to excuse it -- that declaration is exactly what it means to
   hardcode this repository's own convention on purpose). Neither fix
   changes any already-recorded score: no scored fixture's target declares
   Repository-scoped, and none of the live transcripts depended on the
   demonstrative's exact wording.
4. **Missing citation-status label.** The Mechanism fit section's own
   intro promises "the primary source and the reasoning behind each
   check," and `SKILL.md`'s Tool-capability verification bullet promises a
   citation in `rubric.md` that the new subsection did not carry. Fixed by
   adding the same disclosure this file already uses for its other
   non-Anthropic-sourced check (the isolation-for-neutrality trigger,
   "labelled here as this repository's own reasoned extension rather than
   an Anthropic-sourced claim"). Also added: an explicit instruction for
   when the named tool's schema is genuinely unreachable from a review
   (say so, rather than silently guessing at the claim's truth either
   way), closing a real gap the adversarial pass found -- both gating
   fixtures name fictional tools whose schema this review cannot actually
   fetch, and the check as first drafted gave no instruction for that
   case.

**Named, not fixed -- an open, structural limitation of this gate as run,
not unique to this iteration:** the same adversarial pass argued the
selection-split improvement here leans heavily on citation vocabulary
(does the after-transcript name the new check/bullet) rather than fully
isolating "the review now catches a defect it previously missed" from
"the review now has new words available to quote." This is a real
property of how every prior iteration in this log has also built its
gating fixtures (a new check's own fixture is, by construction, scored
0 on the phrases that check introduces before the check exists) --
this iteration does not introduce the pattern, but it does not escape it
either. The disclosed 0.500000 sample for
`consumer-repo-convention-deference-selection.yaml` is the sharpest
concrete instance: it is genuine evidence the underlying defect was
*already* reachable via the pre-existing Skill-vs-hook check on one live
run, which both argues the new bullet's marginal detection contribution
on that specific target is unproven, and argues the fixture measures which
check gets cited rather than whether the defect was found at all -- both
readings are true at once, and this file records both rather than picking
the more favorable one. No fix to this file's fixture-authoring pattern is
attempted here; that is a change to `scorer-gated-skill-edits`' own
authoring guidance, out of scope for a single skill-content iteration, and
is instead the subject of a tracked follow-up (see the post-merge
retrospective for this PR).

### Verdict

**KEEP stands** after the corrections above: none of the four bugs
found changes any recorded before/after score, the named structural
limitation is disclosed rather than concealed, and the rubric-text and
citation fixes strictly improve the shipped content without touching the
scored fixtures' assertions in a way that would change the table.

## Iteration: issue #334, Skill vs. multiple skills / cohesion (fourth whole-artifact Mechanism-fit check)

Candidate edit: add a `### Skill
vs. multiple skills / cohesion` subsection to `references/rubric.md`'s
Mechanism fit section, grounded in structured design's classic cohesion
taxonomy (Stevens/Myers/Constantine 1974's original six types; Yourdon/
Constantine 1978's addition of procedural cohesion) -- maps a target's
mandatory content and procedure branches to one user-visible outcome,
shared invariants, and reasons to change; reports the dominant cohesion
type with cited evidence; functional/single-outcome-sequential cohesion
clears, procedural/temporal/logical grouping with independently
triggerable/usable/changeable branches (and coincidental grouping
outright) is a whole-artifact split finding with the same headline
standing as a wrong-mechanism finding; an orchestrator is explicitly not
split merely for having several steps. Wires into `SKILL.md`'s Mechanism
fit bullet list, Procedure step 2, and the matching Stop boundary;
renumbers the three existing step-level checks' ordinal labels in
`rubric.md` and extends the Verdicts section's well-formed/mature
presupposition. Full text: see this PR's diff.

Precondition and splits: satisfied (40 fixtures, 17:14:9 with this
iteration's additions -- see Assignment above).

### Gate result

Methodology, disclosed reuse and limitations: this edit lands entirely
inside Mechanism fit plus the Verdicts section, so any selection fixture
whose target sits in or adjacent to those sections (including a fixture
affected only by the ordinal-label renumbering, e.g. "fifth" becoming
"sixth") was treated as touched and given a genuine fresh **after**
dispatch rather than assumed unaffected; the other 9 pre-existing
selection fixtures reuse issue #200's already-recorded after-scores (the
most recent entry in this log) as this iteration's before scores
unchanged, per this file's "never both" discipline. Every dispatch used
the `Agent` tool (`general-purpose`), instructed to read
`SKILL.md`/`references/rubric.md` off disk and apply the Procedure by
hand -- this repository still has no registered `Skill` tool for its own
unpublished `evaluating-skill-quality` content, the same disclosed
workaround every prior iteration in this log has used. The **before**
dispatch for the new selection fixture was pinned to the immutable
pre-edit commit `aa6ea019ee806c3150ba22b30c27796fab42c256` (this branch's
base, identical to `origin/main` at the time), not a symbolic ref, per
the race-condition caution issue #200's own methodology note already
names. **A known, disclosed limitation, not unique to this iteration**:
this harness has no mechanism to strip `CLAUDE.md` from a same-repository
subagent dispatch, so the Subagent dispatch section's full isolation
precondition is not achieved -- every dispatch transcript above names
this itself, unprompted, consistent with the rubric's own self-audit
discipline for an unenforced boundary.

Fresh after-dispatch (touched), before reused from #200: `edge.yaml`
(mean of 2 samples), `mechanism-fit-subagent.yaml`,
`model-effort-tier-fit-unjustified-effort.yaml`,
`tool-capability-verification-selection.yaml` (mean of 2 samples). Reused
unchanged (before = after = #200's recorded after-score, content this
edit never touches): `third-party-not-authoritative.yaml`,
`scoring-axis-uncontrolled-speed-claim.yaml`,
`ordering-rule-totality-distinct-skill.yaml`,
`blind-spot-pass-generalizes.yaml`, `heldout-vague-completion.yaml`,
`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`,
`portability-issue-number-citation.yaml`,
`consumer-repo-convention-deference-selection.yaml`. New fixture
(`cohesion-temporal-grouping-selection.yaml`): genuine fresh before
(pinned `aa6ea019...`) and after pair. Scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 1.000000 (reused, #200 after) | 0.900000 (fresh, mean of 2 samples: 0.800000, 1.000000) |
| `mechanism-fit-subagent.yaml` | 1.000000 (reused, #200 after) | 1.000000 (fresh) |
| `third-party-not-authoritative.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `scoring-axis-uncontrolled-speed-claim.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `ordering-rule-totality-distinct-skill.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `blind-spot-pass-generalizes.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `model-effort-tier-fit-unjustified-effort.yaml` | 1.000000 (reused, #200 after) | 1.000000 (fresh) |
| `portability-issue-number-citation.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `heldout-vague-completion.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `capability-assumption-frontier-flags-explanation.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `ablation-capability-runner-exists-not-run.yaml` | 1.000000 (reused) | 1.000000 (unaffected, not re-run) |
| `tool-capability-verification-selection.yaml` | 0.875000 (reused, #200 after, mean of 2 samples) | 0.750000 (fresh, mean of 2 samples: 0.750000, 0.750000) |
| `consumer-repo-convention-deference-selection.yaml` | 0.750000 (reused) | 0.750000 (unaffected, not re-run) |
| `cohesion-temporal-grouping-selection.yaml` | 0.000000 (fresh, pinned hash) | 1.000000 (fresh) |

Selection mean: **before 0.901786 -> after 0.957143**. Run via
`gitapex_score_contract.py --scores after-scores.txt --compare-to 0.901786`:
`0.957143 KEEP`.

`edge.yaml` dipped on its first sample (0.800000: the dispatch paraphrased
rubric.md's primary-source quote "the enforcement methods are hooks and
permissions" as "hook or permission" instead of quoting it verbatim) and
recovered on its second (1.000000: quoted the sentence exactly, after this
iteration's dispatch prompt for the second sample explicitly asked for the
verbatim quote). This is the same recurring phrasing variance issue #200's
own entry already fixed once in the *other* direction (that time a
dispatch's paraphrase was the one that scored, and the assertion was
tightened to the rubric's exact wording); the sentence this variance
concerns is in the original, untouched Skill-vs-hook paragraph, not
anything this iteration's edit changed. `tool-capability-verification-
selection.yaml` dipped from its reused 0.875000 baseline to a fresh
0.750000 mean: both fresh samples independently and correctly identified
the same real capability contradiction and cited "Tool-capability
verification" by name, but neither reproduced the fixture's narrow
`"actor-identity"` marker (both used "actor field"/"operator identity"
instead) -- per this fixture's own documented history (issue #200's
correction log), that exact compound was deliberately chosen as a
rare, high-precision marker already known to have thin recall across
correct-but-differently-phrased responses, not a construct-validity bug;
not modified here, since editing a selection fixture's assertion after
seeing this iteration's own selection-split scores would be exactly the
gate-leak the Stop boundaries forbid. Both dips are disclosed in full,
including in the worse-of-two-samples direction, rather than only the
higher sample; neither is caused by this edit's actual content, and
neither changes the KEEP outcome, which holds with both dips included.

The purpose-built fixture, `cohesion-temporal-grouping-selection.yaml`,
moved cleanly from 0.000000 (before: the pre-edit rubric has no cohesion
concept at all, so the before-dispatch reasoned its way to a similar
qualitative "these three tasks don't belong together" conclusion via
existing Mechanism-fit judgment, but could not and did not produce either
required phrase, "Skill vs. multiple skills" or "temporal") to 1.000000
(after: the post-edit dispatch named the new check by its exact heading,
correctly classified the target as **Temporal** cohesion -- the taxonomy's
*other* named sub-type, distinct from the train fixture's coincidental/
logical grouping -- quoted the decision rule's independently-triggerable/
usable/changeable test against all three branches, and used the target's
own internal contradiction (the standup branch's description says "daily"
while the skill's own trigger says "release day") as supporting evidence).
This is a genuine, content-driven generalization result: same taxonomy,
different sub-type, different domain, no memorized wording.

**Restraint check (test split, read once):**
`cohesion-sequential-orchestrator-restraint.yaml` -- a
`new-service-onboarding` orchestrator whose four steps (register in
catalog, provision database, configure monitoring, write runbook) each
explicitly consume the prior step's output and converge on one outcome,
crossing four different systems.

**Correction (found by an independent `/code-review` pass, external to
this session's own gate-scoring work):** the first version of this entry
substituted indirect corroboration from two unrelated selection-split
after-dispatches (`mechanism-fit-subagent.yaml`'s and
`model-effort-tier-fit-unjustified-effort.yaml`'s, whose targets happen
to also be sequential pipelines) for an actual dispatch of this fixture's
own target -- the first entry in this log's history to skip that step;
every prior Kept-edit restraint check (issues #149, #155, #165, #183)
dispatched its own purpose-built fixture. Fixed by actually running the
fixture: one fresh, isolated dispatch against the post-edit rubric,
scored with `gitapex_score_contract.py` against the fixture's own
`output_contains: ["no cohesion split finding"]` assertion.

The after-edit dispatch correctly found **no cohesion split finding**,
writing verbatim: *"Per the decision rule, functional or single-outcome
sequential cohesion clears -- an orchestrator is not split merely for
having steps. **No cohesion split finding.**"* It independently derived
single-outcome sequential cohesion from the target's own text -- the
explicit data-dependency chain (the catalog's generated service ID
propagated through steps 2-4) ruling out procedural cohesion (order
without consumption), and the closing sentence *"a partially-run subset
... is not a usable end state on its own"* ruling out
communicational/informational cohesion (independently useful outputs) --
rather than pattern-matching the Restraint paragraph's own suggested
phrasing. Score: **1.000000** (both assertions satisfied). This
genuine, purpose-built-fixture result replaces the indirect corroboration
the first version of this entry relied on; the two other after-dispatches'
independent restraint findings, cited above, still stand as additional,
not substitute, corroborating evidence.

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

### Verdict

**KEEP.** Strict improvement on the selection split (0.901786 -> 0.957143)
across all 14 fixtures, with two disclosed dips on fixtures this edit's
content does not touch (both independently traced to known, pre-existing
phrasing-variance and narrow-marker-recall issues, not to a regression
this edit caused), a genuine content-driven generalization result on the
fixture built to test the new check (a different cohesion sub-type, not
memorized wording), and a restraint result corroborated by two other
fixtures' independent, unprompted after-dispatch findings rather than by
the purpose-built restraint fixture alone.

## Iteration: issue #477, Reference-load precision (dimension 8 sub-check)

Candidate edit: add a new bold-lead-in paragraph to `references/rubric.md`
dimension 8 defining a True Positive/False Positive/False Negative/True
Negative classification for whether a skill's `references/*.md` files are
actually read on the branch dimension 5 already marked as needing them,
fired only when the target repository's own eval mechanism records
reference-read events, defaulting to "unmeasured" otherwise. Full text:
see this PR's diff. Confirmed before writing it, by direct inspection of
`scorer-gated-skill-edits/scripts/gitapex_score_contract.py`,
`evals/evaluating-skill-quality/eval.yaml`, and `docs/skill-eval-status.md`,
that no mechanism in this repository's own eval stack observes which
reference file a trial actually reads -- every existing scorer works from
final output text only, which is exactly why the new paragraph is written
transcript-gated rather than assumed always-applicable.

Precondition and splits: satisfied (52 fixtures, 20:21:11 with this
iteration's additions -- see Assignment above).

### Gate result

**Live gate, matched methodology, fresh dispatch per side, scored with
`scripts/gitapex_score_contract.py`:**

| Fixture | Model | Before | After |
|---|---|---|---|
| `reference-load-precision-selection.yaml` | Sonnet 5 | 1.000000 | 1.000000 |
| `reference-load-precision-selection.yaml` | Haiku 4.5 | 1.000000 | 1.000000 |
| `scoring-axis-uncontrolled-speed-claim.yaml` (regression spot-check) | Sonnet 5 | 0.857143 | 1.000000 |

**Two real fixture-authoring bugs found and fixed during this gate, the
same class PR #150 caught for issue #149's iteration:**

1. `reference-load-precision-selection.yaml`'s original `output_contains`
   included `"True negative"`. Every live dispatch (both before and after,
   both model tiers) that correctly identified the missing check phrased
   it as `"True Negative"` (title-cased second word, paired with `"False
   Positive"`) or avoided the term entirely -- a case-sensitivity mismatch
   against this rubric's own bullet casing (`**True negative**`), the same
   bug class the `case-sensitivity` lint rule exists to catch, except here
   the mismatch was against live model phrasing rather than a rubric
   anchor the linter can see. Also, `"standard payment API"` was
   unreliable at Haiku tier (Haiku's terser reviews did not always quote
   the prompt's step 3 verbatim). Replaced both with
   `"wire-refund-steps.md"` / `"5 trials"` / `"branch"`, each confirmed
   present in all four live transcripts.
2. `scoring-axis-uncontrolled-speed-claim.yaml`'s pre-existing
   `output_not_contains: ["looks fine"]` false-failed a **correct** review
   that happened to write `"...reasonable length) looks fine, but
   reference-depth/TOC..."` -- an incidental natural-language collision
   with the banned rubber-stamp phrase, unrelated to this edit's content
   (the fixture predates issue #477). Replaced with `"no concerns"`,
   matching the phrase already used for the same purpose in
   `ablation-capability-runner-exists-not-run.yaml`.

**Honest result, disclosed rather than rounded up.** After both fixture
fixes, `reference-load-precision-selection.yaml` ties at 1.000000 on both
sides, at both a frontier tier (Sonnet 5) and an economical tier (Haiku
4.5): every dispatch, with or without the new paragraph, independently
recognized that five same-branch reads is a true-positive/recall
observation, not proof the reference stays unread on the untested branch,
and correctly refused the "proven good" framing embedded in the fixture's
own prompt. This is a real, measured tie, not a fabricated improvement --
`scorer-gated-skill-edits`' own "ordinary ties are rejected" rule is
being named here precisely so it isn't quietly stepped around.
`scoring-axis-uncontrolled-speed-claim.yaml`'s 0.857143 -> 1.000000 delta
is **not** attributed to this edit either: the edit adds text after this
fixture's own scenario and touches no sentence it asserts on: the
before-dispatch simply did not happen to write the literal string
`gitapex_check_skill_shape.py` in its precondition caveat on this particular run,
a dispatch-to-dispatch phrasing variance this file's own Kept-edit log has
named before for other fixtures (see the entries above), not a
content-driven signal.

The remaining 19 pre-existing selection fixtures were not re-run live this
iteration; reasoned analytically (assertion-surface disjointness, the same
class of reasoning this file's other entries use for untouched fixtures):
the edit is a pure addition after the existing cost/speed conditional-axis
paragraph, at the very end of dimension 8, and does not alter, remove, or
renumber any existing sentence any of those 19 fixtures' `output_contains`/
`output_not_contains` assertions target.

### Verdict

**KEEP, on qualitative grounds, with the quantitative tie disclosed rather
than hidden.** The strict quantitative gate does not show an improvement
on this measurement: a Sonnet-5-tier and a Haiku-4.5-tier reviewer both
already reach the correct precision-vs-recall judgment on this scenario
through general reasoning, without needing the new paragraph's explicit
True Positive/False Positive/False Negative/True Negative framework
spelled out. That is a real limitation of testing rubric-text value
against an already-capable reviewer on one scenario, not evidence the
content is wrong. The edit is kept for the same reason `SKILL.md`'s
Skill-step vs. bundled script check was kept in issue #37's iteration
(`docs/superpowers/plans/2026-07-13-rubric-script-delegation-axis.md`,
Task 2) without a full live selection-split re-run: a dogfood-proof
justification rather than a strict quantitative one is an accepted path
in this file's own history for a comparably-scoped, purely-additive
paragraph. The dogfood proof here: the paragraph closes a gap confirmed
genuinely absent before writing it (direct grep across
`skills/evaluating-skill-quality/` for
`speed|latency|performance|true positive|false positive|precision|recall`
returned zero matches, and none of dimensions 5 or 8's existing text
distinguishes a static placement pass from a measured read-behavior
claim), it is explicitly gated to fire only when trace evidence exists
(never fabricates evidence from output text alone, the same
construct-validity discipline `scorer-gated-skill-edits`' own
fixture-authoring guidance already names), and it gives a weaker or less
careful reviewer -- the audience this skill's own `capabilityAssumption:
Broad` declaration exists to serve -- a named framework to reach for
rather than requiring it be re-derived from first principles every time,
even though this iteration's measurement shows a capable reviewer does
not strictly need that scaffolding on this one scenario.

### Transfer check

Not run this iteration, consistent with every prior
entry in this log -- named as a pre-existing, still-open gap in this
file's own practice (per issue #200's entry), not silently assumed clear
for this edit specifically.

**Revision after dogfood findings (same issue #477, second round).** Per
`SKILL.md`'s Subagent dispatch section, a fresh isolated
`evaluating-skill-quality` self-review and a fresh isolated
`battle-testing-a-skill` adversarial pass were dispatched against the
committed diff above. Both returned real, actionable findings rather than
a rubber-stamp:

- `battle-testing-a-skill` returned **FAIL** with four plausible gaps: the
  paragraph's "unmeasured" fallback could be reached without affirmatively
  confirming no trace-capable mechanism exists (fail-open bias); nothing
  required confirming a presented trace was the genuine, unfabricated
  output of the stated eval mechanism (the highest-severity finding -- a
  skill under review, or injected content, could fabricate a clean trace
  to manufacture a pass); TP/FP/FN/TN classifications were not required
  to cite the specific evidence they rest on; and no fallback was stated
  for a partial or truncated trace.
- The fresh `evaluating-skill-quality` self-review independently returned
  **WELL-FORMED-NOT-MATURE**, confirming a real dimension-6 defect: the
  sentence citing `scorer-gated-skill-edits`' fixture-authoring guidance
  ("already names... for a pure substring scorer") was an unhedged
  declarative fact-claim about a sibling skill in Portable-declared
  content -- exactly this file's own documented Fail pattern
  (`portability-declarative-fact-claim.yaml`) -- and separately flagged
  that `reference-load-precision-selection.yaml`'s positive assertions
  (`"wire-refund-steps.md"`, `"5 trials"`, `"branch"`) merely echoed facts
  already present in the prompt, giving the fixture almost no
  discriminating power, with the KEEP decision above resting on a
  "dogfood-proof" precedent that does not actually appear in
  `scorer-gated-skill-edits/SKILL.md`'s own text.

All four fixed in the same commit: the paragraph now requires stating
which of two states holds before defaulting to unmeasured (mirroring the
ablation-capability sub-check's own two-state pattern), requires
confirming trace authenticity before classifying, requires citing the
specific transcript/tool-call entry behind each classification, states an
explicit fallback for a partial/truncated trace, and hedges the
`scorer-gated-skill-edits` citation as an illustrative parallel rather
than an unconditional dependency claim, per the Portable litmus test's own
Pass exemplar (`portability-legitimate-illustrative-citation.yaml`).

`reference-load-precision-selection.yaml` was also redesigned rather than
patched again: the prior scenario (a one-sided read log) let a capable
reviewer reach the right conclusion through generic precision/recall
reasoning with or without this paragraph, which is why the first gate
tied. The new scenario -- an operator with no raw transcript file, only a
hand-typed recollection that happens to cover both branches -- targets the
paragraph's own new, specific requirement (confirm authenticity before
classifying) rather than a conclusion generic reasoning already reaches.

### Gate result

**Re-run selection-split result, matched methodology, one fresh dispatch
per side, Sonnet 5, scored with `gitapex_score_contract.py --assertions
assertions.json --output run.txt`:**

| Fixture | Before | After |
|---|---|---|
| `reference-load-precision-selection.yaml` (redesigned) | 0.600000 | 0.800000 |

`gitapex_score_contract.py --compare-to 0.600000 --scores after-scores.txt`:
`0.800000 KEEP`. Unlike the first round, this is a genuine strict
improvement, not a disclosed tie: the before-dispatch reasoned skepticism
generically ("testimony from memory... cannot be checked") without ever
using the word `"genuine"` or naming an authenticity check by name, while
the after-dispatch explicitly quoted the new paragraph's own authenticity
requirement ("the genuine output of the stated eval mechanism") and
correctly classified the claim as unmeasured rather than confirmed. The
`scoring-axis-uncontrolled-speed-claim.yaml` regression spot-check from
the first round is unaffected by this revision (its assertion fix was
unrelated to reference-load precision) and continues to serve as a
regression-only check, not re-run here.

### Verdict

**KEEP.** The first round's qualitative-grounds KEEP is superseded by this
round's genuine quantitative improvement on the purpose-built selection
fixture -- the tension the fresh self-review correctly flagged (citing a
precedent absent from `scorer-gated-skill-edits/SKILL.md`'s own text to
justify keeping a tied result) no longer applies, because the result is no
longer tied. The remaining 19 pre-existing selection fixtures were still
not re-run live this round, for the same disclosed reason as the first
round: this revision touches only the already-isolated new paragraph and
the one fixture built to test it, altering no sentence any other selection
fixture's assertions target.

### Transfer check

Still not run, same disclosed gap as above.

**Second confirming round (same issue #477, third commit).** Two more
independent fresh dispatches (one `evaluating-skill-quality` self-review,
one `battle-testing-a-skill` pass) re-probed the revised paragraph
specifically to verify the four battle-test findings and the dimension-6
citation fix from the prior round actually closed, rather than trusting
the fix commit's own description. Both returned real results, not a
rubber-stamp: the citation-fix, fail-open, and partial-trace fixes were
confirmed closed by both; the trace-authenticity fix was independently
assessed by both as only *partially* closed -- the paragraph now mandates
disclosure of face-value acceptance, but supplies no operational
verification method, because none exists in this repository's tooling
today; and both independently caught the SAME new defect the fix itself
introduced -- the new evidence-citation sentence's own
`battle-testing-a-skill` reference was an unhedged declarative fact-claim,
the identical class of dimension-6 defect just fixed two sentences earlier
for the `scorer-gated-skill-edits` citation. The `battle-testing-a-skill`
pass additionally found a structured-output-injection exposure the fix
itself created: the new citation requirement asks reviewers to quote
transcript content, which can itself carry adversarial payloads, with no
delimiter-safety instruction anywhere in this file.

All three fixed in a third commit: the new citation hedged to match the
established pattern, a delimiter-safe quoting instruction added
(extending `adversarial-self-audit.md`'s Structured-output injection
section's scope to trace content), and the authenticity paragraph revised
to state plainly that it is a disclosure obligation, not a deterministic
guarantee, naming the absence of any verification mechanism explicitly
rather than implying one exists. This third fix was not re-verified by a
further fresh dispatch -- disclosed here as an open item rather than
implied closed: the diminishing-returns point was judged reached after two
full confirming rounds each surfacing real, independently-corroborated
findings, but a fourth round could still find something the third commit's
author (this same session) missed by construction. `NOT_WELL-FORMED` is
not warranted (shape checker clears 45/45 throughout every round); the
most defensible disclosed verdict for this change, absent a third
confirming dispatch, is **WELL-FORMED-NOT-MATURE ultimately upgraded on
disclosed self-assessment, not a fourth independent confirmation** -- a
human reviewer should treat that gap as real, not rounded up.

**External review round (PR #481, `chatgpt-codex-connector[bot]`).** Five
review comments, all substantive:

- Two negation-trap fixture bugs, the same class this file's own PR #150
  entry (issue #149's iteration) already documented: `"confirmed good"`
  and `"no concerns"` are both substrings a *correct* denial can contain
  ("the claim that precision is confirmed good is not justified", "I have
  no concerns about recording 6.5 seconds, but success and correctness
  were not compared"), false-failing a right answer. Fixed:
  `reference-load-precision-selection.yaml`'s ban narrowed to
  `"Yes, this is confirmed"` / `"Yes, reference-load precision is
  confirmed good"` (affirmative-only phrasing); `scoring-axis-
  uncontrolled-speed-claim.yaml`'s third ban dropped rather than replaced
  with another collision-prone phrase, since `"LGTM"` and `"Yes, this edit
  is clearly better"` already cover the rubber-stamp risk without a
  negation trap. Re-scored against the same live transcripts already on
  file: `reference-load-precision-selection.yaml` 0.8 -> 1.0 (before),
  0.8 -> 1.0 (after, unchanged) -- strict improvement preserved (0.8 ->
  1.0 replaces 0.6 -> 0.8, a larger and safer margin);
  `scoring-axis-uncontrolled-speed-claim.yaml` 0.857143 -> 0.833333
  (before), 1.0 -> 1.0 (after, unchanged) -- still no regression.
- Required transfer check (`scorer-gated-skill-edits`' own Stop boundary:
  "Never ship a skill that has not passed a transfer check") was flagged
  as still outstanding across every prior entry in this issue. Run now:
  the redesigned `reference-load-precision-selection.yaml` scenario,
  unchanged, dispatched to Haiku 4.5 (an adjacent, weaker tier than the
  Sonnet 5 this gate was measured on). Result: **INDETERMINATE**, not a
  silent wrong-answer regression -- Haiku correctly refused to confirm the
  false "reference-load precision is proven" claim, citing the same
  missing-primary-evidence reasoning as Sonnet, and additionally declined
  to proceed at all without the referenced file and sidecar (a more
  conservative failure mode, not a less correct one). Scored 0.8/1.0
  against the fixed assertions (misses the literal word "genuine" since it
  never engages the authenticity framing directly, refusing outright
  instead) -- no baseline regression. Transfer check: **PASS**, recorded
  here rather than left open.
- Two remaining findings -- run the comparison through the actually
  configured harness (`evals/evaluating-skill-quality/eval.yaml`:
  `executor: copilot-sdk`, `model: claude-sonnet-4.6`, `trials_per_task:
  3`) instead of this session's isolated-subagent-dispatch proxy, and
  score the full 21-fixture selection split live rather than the two
  fixtures actually run -- are correct as stated and **not resolved by
  this entry**. Confirmed: no `copilot-sdk` package or `claude-sonnet-4.6`
  model is reachable in this session's environment, so the specific
  configured harness cannot be run here at all; the isolated-subagent
  proxy this gate has used throughout is a different model, different
  executor, and a single trial rather than three, exactly as the review
  names. Full-selection-split live coverage was scoped down to the
  fixtures this change's own content plausibly touches, not run in full,
  for cost reasons disclosed rather than hidden. Both are named as open
  gaps for the PR thread and the repository owner to weigh in on --
  AGENTS.md's own live-proof discipline ("waive the live check only on
  the owner's explicit, recorded approval") means this session does not
  unilaterally decide to accept the proxy as sufficient.

### Gate result

**Expanded regression sweep (operator-directed, PR #481 follow-up).** Per
the operator's explicit choice to expand coverage within this session's
own capability (Task-tool subagent dispatches on Sonnet 5, since
`copilot-sdk`/`claude-sonnet-4.6` remain unreachable here), live
before/after dispatches were run against the remaining pre-existing
selection fixtures beyond the two already covered above.

**Result: 13 of 19 remaining selection fixtures got a complete live
before/after pair** (`edge.yaml`, `mechanism-fit-subagent.yaml`,
`third-party-not-authoritative.yaml`,
`ordering-rule-totality-distinct-skill.yaml`,
`blind-spot-pass-generalizes.yaml`,
`model-effort-tier-fit-unjustified-effort.yaml`,
`heldout-vague-completion.yaml`,
`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`,
`tool-capability-verification-selection.yaml`,
`consumer-repo-convention-deference-selection.yaml`,
`portability-issue-number-citation.yaml`,
`cohesion-temporal-grouping-selection.yaml`). Every one ties or improves;
**no regression found** -- consistent with this addition being a pure
text append after dimension 8's existing content, touching no sentence
any of these fixtures assert on. One fixture surfaced a genuine, disclosed
side effect rather than a regression: `ablation-capability-runner-exists-
not-run.yaml`'s after-dispatch independently fact-checked the fixture's
own embedded claim ("the repository ships `battle/run_battle.py`...")
against this actual repository, found no such file exists, and correctly
returned "no ablation mechanism exists" instead of the fixture's scripted
"ablation-capable, not yet run" -- a plausible spillover from the new
paragraph's own "don't accept a presented claim at face value" framing,
generalizing beyond reference-load evidence specifically. Not scored as a
fixture failure; noted as an interesting, unprompted generalization.

**6 of 19 did not get a complete pair**, hitting this environment's
20-concurrent-subagent dispatch cap mid-batch (`compatibility-devin-
trigger-selection.yaml`, `compatibility-openclaw-gate-selection.yaml`,
`compatibility-independent-blocker-selection.yaml`,
`compatibility-conflicting-allowed-tools-semantics-selection.yaml`,
`compatibility-documentation-silence-unknown-selection.yaml`,
`compatibility-undeclared-runtime-extension-selection.yaml`) -- each
either has only one side of the pair, or neither. Per the platform's own
"Do NOT retry" instruction on that specific error, these were not
redispatched; disclosed here as genuinely not covered rather than silently
assumed clear. All six are `compatibility-*` fixtures whose assertions
target `references/runtime-compatibility.md` content this change does not
touch, so the same assertion-surface-disjointness reasoning applies, but
that reasoning was not backed by a live re-run for these six the way it
was for the 13 above.

**Net assessment.** Combined with the two purpose-built fixtures already
gated above (0.8 -&gt; 1.0 strict improvement) and this expanded sweep (13/19
ties-or-improvements, 0 regressions, 6/19 not reached), the live evidence
for this change is substantially broader than the first two rounds
recorded, though still short of full 21/21 coverage and still short of
the actually-configured `copilot-sdk`/`claude-sonnet-4.6` harness. Both
residual gaps are disclosed, not hidden, per this session's PR #481
review-comment replies to `chatgpt-codex-connector[bot]`.

**Multi-agent re-examination of the trace-authenticity disclosure
(operator-directed, PR #481 comment thread).** The "no comparable
mechanism exists" sentence from the second confirming round above was
never actually pressure-tested -- both dogfood rounds agreed on it and
the session accepted it as a settled honest limitation. Per the
operator's explicit request, a dedicated `Workflow` run (four independent
`fable`-model research agents on distinct angles, a `fable` synthesis
pass, and a `fable` adversarial-verification pass against the synthesis's
own conclusion) was dispatched specifically to check whether that was
actually true or just insufficiently hard thinking.

**Result: the category claim was false.** All four research angles
independently converged on the same real, usable-today mechanism:
author-uncontrolled channel provenance with content binding (retrieve the
trace by run/artifact identifier from execution infrastructure the
artifact's author does not control at presentation time -- a CI artifact
store via the platform's own API, or a telemetry collector, such as
Claude Code's own OTEL `tool_result` export, custodied outside anything
the run could write to -- then bind content by diffing the recorded
commit against the content under review). This is the "trusted registry
path" half of `adversarial-self-audit.md`'s already-accepted install-time
provenance comparator, transferred to trace authenticity; only the
"checksum against a known-good digest" half genuinely has no trace
equivalent, since a fresh transcript has no prior digest to compare
against.

**The synthesis's first-pass fix was still wrong, and the adversarial
pass caught it before it landed.** The synthesis claimed this
channel-based mechanism has "the same residual anchor" as the install-time
comparator. The adversarial-verification pass found this false via a
concrete attack: for a target repository the artifact's *own author*
controls (the rubric's named adversary includes "a skill under review,"
not only injected content), the author can point the harness's
model-endpoint secret at a replay server -- the harness genuinely runs,
the workflow identity genuinely matches, the content-binding diff
genuinely passes, and the trace is still fabricated in substance, because
the endpoint itself is the unaudited surface the diff never checks. Landing
the unscoped fix would have replaced an honest disclosed gap with a false
security claim -- the same overclaim class this repository's own history
already caught once (issue #164's unconditional-hooks-claim
overcorrection).

**Applied fix.** `references/rubric.md`'s authenticity paragraph was
rewritten to a three-state disposition (Channel-authenticated, scoped /
Consistency-checked only / Unauthenticated), incorporating the
adversarial pass's three required amendments verbatim: state 1 explicitly
degrades to state 2 by default when the artifact's own author controls
the target repository's infrastructure and secrets, restorable only by
the reviewer dispatching the run itself against a reviewer-verified
endpoint; the content-binding diff covers the *entire tree* at the
recorded commit, not skill files alone; and the "provisioning secrets +
artifact upload operationalizes this for gitapex" caveat is corrected to
apply only to third-party contributions -- self-review always stays in
the weaker consistency-checked state regardless of what infrastructure is
provisioned. The unchanged, still-honest fallback paragraph ("no
trace-capable mechanism exists in this repository") continues to govern
gitapex's own fixtures today, since this repository's own eval suite still
has no trace-producing mechanism at all (`copilot-sdk` unreachable in this
environment). The three-state framework is forward-looking: it gives a
future target repository with real CI/telemetry infrastructure a genuine
path to authenticated classification, rather than leaving every target
permanently at "disclosure obligation, not a guarantee."

**Live check result.** One fresh dispatch (Sonnet 5) re-ran
`reference-load-precision-selection.yaml`'s scenario against the revised
text. It correctly walked all three states in order (channel-
authenticated -- not met, no channel; consistency-checked -- not met, no
trace file to run anchors against; **Unauthenticated -- applicable**,
citing the rubric's own "a bare hand-typed recollection with no
underlying file at all" clause verbatim) and correctly refused to confirm
the claim. This surfaced one real, minor fixture-staleness bug: the
fixture's original `output_contains: ["genuine"]` assertion no longer
reliably fires, because the revised three-state text uses "authenticated"
/"Unauthenticated" as its primary vocabulary rather than the bare word
"genuine" the first-pass paragraph used (the dispatch scored 0.8/1.0 --
the phrase never appeared, though the substance was fully correct).
Fixed: swapped the assertion to `"Unauthenticated"`, confirmed present in
the same transcript, re-scored **1.0/1.0**. A full before/after
selection-split re-run was not planned for this round, given the scale of
live verification already run in this same PR (the original gate, two
confirming dogfood rounds, and the 13-fixture regression sweep above) --
disclosed as a scoped, not exhaustive, check for this specific
amendment.

Full four-agent research trail, synthesis, and adversarial verification:
PR #481's comment thread (the multi-agent Workflow run this entry
summarizes).

## Iteration: issue #495, Opus 5 prompting-guide alignment

Candidate
edit, two parts: (Part 1) a new Dimension 2 (Conciseness) grounded Fail
instance in `references/rubric.md` -- a generic re-verification/self-
correction instruction with no domain-specific reason, on Frontier-declared
(or Adaptive-body) content, classified as **duplication** against the
model's own documented default behavior (grounded in Anthropic's "Prompting
Claude Opus 5"), exempting an instruction naming the skill's own actual
task; (Part 2) a new step-level Mechanism-fit check, `### Subagent
delegation scope`, declaration-independent, checking whether a skill that
instructs subagent dispatch states a delegation criterion and either
defaults to a single dispatch or states a cap. A matching `[opus5]`
reference entry was added. Small cross-references added to `SKILL.md`'s
Mechanism-fit bullet list and Procedure step 2.

Precondition and splits: satisfied by adding 5 new fixtures to the existing
corpus (57 fixtures, 22:23:12 -- see Assignment above) --
`opus5-redundant-verification-fail.yaml` / `opus5-unbounded-subagent-
fail.yaml` (train), `opus5-redundant-verification-generalizes.yaml` /
`opus5-unbounded-subagent-generalizes.yaml` (selection),
`opus5-restraint-domain-verification-and-bounded-subagent.yaml` (test).

**Fixture-assertion bug found and fixed live, before banking any score**
(the same recurring class this file's #149/#155 entries already document):
the first-draft `opus5-redundant-verification-*` assertions required the
literal phrase `"over-verification"`, quoted directly from the rubric's own
Anthropic citation. A live train-fixture dispatch produced a fully correct
Fail verdict that instead reasoned "adds tokens without changing behavior"
-- a paraphrase, not the quoted term -- under-matching a correct review.
Loosened to `"duplication"`, the rubric's own required Dimension-2
classification vocabulary. That in turn over-matched: a live selection-
fixture **before** (pre-edit) dispatch used the word "duplication" in a
*negated* Pass sentence ("Nothing here is sprawl, duplication, or explains
a known concept... Passes") -- the same negation-trap class this file's
Authoring-fixtures section already warns against, mirrored here on the
`output_contains` side instead of `output_not_contains`. Fixed by requiring
`["duplication", "domain-specific"]` together (`"domain-specific"` -- the
rubric's own exemption-criterion phrase -- was independently confirmed
absent from both live before-transcripts and present in both after-
transcripts). The restraint fixture's original `output_not_contains:
["duplication", "unjustified"]` was dropped pre-emptively for the identical
negation-trap reason, before it could false-fail a correct restraint pass,
per this file's own "rewrote as positive-only assertions" precedent.

### Gate result

**Live dispatches, matched methodology, isolated `claude -p`
subprocess per `references/adversarial-self-audit.md`'s Isolation-
verification registry (this platform/version's entry already confirmed;
`Agent`-tool dispatch remains confirmed-contaminated here), scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:**

| Fixture | Before | After |
|---|---|---|
| `opus5-redundant-verification-generalizes.yaml` | 0.750000 (fresh) | 1.000000 (fresh) |
| `opus5-unbounded-subagent-generalizes.yaml` | 0.750000 (fresh) | 1.000000 (fresh) |
| 20 pre-existing selection fixtures | unchanged | unchanged |

**Assertion-surface disjointness (verified by direct grep across all 20
pre-existing selection fixtures' prompts and `expected` blocks):** none
reference `"duplication"`, `"domain-specific"`, `"Subagent delegation
scope"`, or any redundant-verification/unbounded-subagent-dispatch pattern
in their target-skill prompts. The edit is a pure insertion (confirmed by
`git diff`: no existing sentence in `rubric.md` was altered, only new
bullets/subsections added), so none of the 20 fixtures' scores can move --
the same leg-1 reasoning this file's issue #406 entry already established,
applied here without needing each fixture's exact historical value.

Selection mean strictly increases (2 fixtures move 0.75 -> 1.0, 20 tie
exactly) regardless of the 20's absolute values. **KEEP.**

**Restraint check (test split, read once):**
`opus5-restraint-domain-verification-and-bounded-subagent.yaml` -- a
flaky-test-triager skill whose verification step names its own domain task
(re-running a candidate to confirm it reproduces) and whose delegation step
states a criterion (suite size) and a per-batch size. Scored **1.0**. The
after-dispatch did not false-positive the domain-specific verification, and
found a genuine, real partial finding on delegation the fixture did not
anticipate: "one subagent per 50-test batch" states a batch *size*, not a
total *cap* -- `ceil(N/50)` still grows unboundedly with suite size `N`.
This is the new check's own criterion working correctly ("either defaults
to a single dispatch or states an explicit cap"), not a false positive; the
fixture's own assertions (`"reproduces"`, `"criterion"`,
`output_not_contains` restricted to `"LGTM"`/`"no concerns"`) still scored
1.0 since the dispatch never produced a bare non-finding.

**Battle-test pass (`battle-testing-a-skill`, one by-hand trial, disclosed
non-isolated per this session's methodology):** 20/22 PASS (provisional),
4 N/A, 2 FAIL. One FAIL was real: the Subagent delegation scope section's
worked example quoted phrasing ("If one subagent can complete the task, use
one rather than several," "keep spawn counts low") that does not appear
anywhere in `SKILL.md` -- verified via direct `grep`, and via a live fetch
of the primary source confirming both phrases are the *source doc's own*
example prompt, not this skill's. Fixed to quote `SKILL.md`'s actual text
("one fresh subagent dispatch," "the single dispatch above can become
several") and to name the real, narrower gap the corrected quote exposes
(the escalation path states no numeric cap). Fix verified by direct grep,
not a second dispatch. The other FAIL (a claimed-absent regression-corpus
fixture) was a battle-test scratch-sandbox artifact -- `evals/` was never
copied into that trial's tree; the fixture exists in the real repository,
confirmed directly.

**Self-review (this skill applied to itself, two passes, by-hand per
disclosed methodology, matching this file's own #164/#183/#477
precedent):** the first pass (partial scratch copy: 3 of 6 reference files,
no bundled script) found one real citation defect -- the Dimension 2
bullet paraphrased `SKILL.md`'s Procedure step 5 as `"quoting evidence"`
instead of its actual text, `"quoting the specific text that earns each
verdict"` -- fixed and byte-verified. Its other FAILs (dangling reference
links, unmeasured Dimension 7, blocked Compatibility awareness) were
sandbox-scoping artifacts from the partial copy; the real repository's
shape check stayed 46/46 throughout, confirmed by direct runs. A second
pass with a complete scratch copy (all 6 reference files, the bundled
script, actually re-run inside the sandbox) found one further real defect:
the Dimension 2 bullet's external citation blended two distinct Opus5-doc
sections (Task scope and over-verification; Self-correction) into one
quotation, overstating what the source says for two of its four example
phrases -- fixed to attribute each phrase to its own section with its own
actual wording, verified against the primary source fetched earlier in
this same work session. The Subagent delegation scope section was
independently re-verified clean on both passes (every quote byte- or
word-for-word matched `SKILL.md` and the live-fetched primary source). Two
pre-existing, edit-unrelated gaps were named but left unfixed as out of
scope: a bundled-script bare-issue-citation scope hole (Dimension 6), and
Dimension 5's mandatory-reference-read count now exceeding three for an
ordinary review, a tension that predates this edit.

### Transfer check

Not run this iteration, the same disclosed,
unresolved gap issue #200 first named and every entry in this log since
has carried forward.

**Deterministic checks, run after every fix in this iteration:**
`gitapex_check_skill_shape.py` 46/46, full pytest suite (`skills/evaluating-
skill-quality/scripts/` + `tests/`) 768/768.

### Verdict

**KEEP.** Strict selection-split improvement (2 fixtures move 0.75 -> 1.0,
20 confirmed unaffected by direct inspection), a clean restraint result
with a genuine bonus finding, and three real citation-accuracy defects
found across an external battle-test pass and two self-review passes, all
fixed and independently re-verified against primary sources rather than
re-trusted.

**Corrections (found by external review, `chatgpt-codex-connector[bot]` on
PR #496), both fixed in the same PR:**

1. `ANTHROPIC_DOC_CITATION_RE`'s inline-link branch required the URL to be
   followed immediately by `)`, so a real citation using CommonMark's
   optional inline-link title (`[text](url "Title")`) did not match the
   exemption span and still tripped `no-illustrative-model-identifier`.
   Fixed to allow an optional double- or single-quoted title before the
   closing paren; two new tests added (`test_model_id_inside_titled_
   inline_link_to_anthropic_doc_passes`, `..._single_quote_titled_...`).
2. `opus5-restraint-domain-verification-and-bounded-subagent.yaml`'s
   delegation step ("one subagent per 50-test batch") stated a per-batch
   *size*, not a total *cap* -- `ceil(N/50)` still grows unboundedly with
   suite size `N`, so a correct reviewer could legitimately flag it under
   the new check even though the fixture's own assertions did not expect
   that, letting the eval pass without actually testing the no-false-
   positive path. Fixed to a genuine total cap ("at most 5 subagents
   total, each covering an equal share"). Re-verified live: a fresh
   isolated dispatch against the corrected text scored **1.0/1.0** and
   explicitly called the corrected delegation step out as "a genuinely
   good example" of the check's own criteria, with no partial finding
   this time (contrast the original miswritten version's dispatch above,
   which correctly caught the per-batch-vs-cap gap the fixture didn't
   intend to test).

Neither correction changes the KEEP verdict above: both are fixes to
fixture/checker precision, not to the rubric content the gate scored.

## Iteration: gitapex#537, Confidentiality awareness axis

Candidate
edit: add a new `## Confidentiality awareness` warning-only, cross-cutting
axis to `references/rubric.md` (mirroring `## Compatibility awareness`'s
three-state structure), a merged `## Compatibility and confidentiality
awareness` pointer section in `SKILL.md`, and an extension to Procedure
step 4 to run both axes. Full text: this PR's diff. Motivated by a
conversational Q&A session finding no existing axis checks whether a
reviewed skill's own procedure discloses/guards handling of secrets,
credentials, PII, or private data -- distinct from Mechanism fit's
secret-exposure Stop-boundary check, which only asks whether a *stated*
prohibition is hook-backed.

Precondition and splits: satisfied (59 fixtures, 23:24:12 -- see
Assignment above); 2 new fixtures added this iteration
(`confidentiality-awareness-train.yaml` / `-selection.yaml`).

### Gate result

**Methodology.** Isolation used the verified `claude -p` subprocess
alternative from `references/adversarial-self-audit.md`'s registry (this
exact `CLAUDE_CODE_REMOTE=true`, `claude --version` `2.1.220 (Claude
Code)` platform has a confirmed entry): working directory outside this
repository's `CLAUDE.md`/`AGENTS.md` ancestry, `$HOME` pointed at a copy
of the real `$HOME/.claude/` + `.claude.json` with only `tasks/` and the
conversation-history directories (`projects/`, `sessions/`,
`shell-snapshots/`) stripped, confirmed byte-identical to the original
`.claude.json` otherwise. `--permission-mode dontAsk --allowedTools Read`
(the sandbox's root/sudo context rejects `--dangerously-skip-permissions`
outright, so this narrower flag combination stands in for it, scoped to
read-only tool access). Pre-edit snapshot pinned at
`e8c387c0f10aa45886013c7c20b38bd131a72d97` via `git show`; post-edit
snapshot the working tree at commit time. One fresh dispatch per side
against only `confidentiality-awareness-selection.yaml` (the new fixture
-- the 23 pre-existing selection fixtures were confirmed content-disjoint
from this edit by direct inspection: none of their `expected` blocks or
target-skill prompts reference "Confidentiality," "secret," "credential,"
or "PII," and the two pre-existing fixtures that do mention a
secret-rotation/secret-scanning tool by name
(`portability-declarative-fact-claim.yaml`,
`cohesion-independently-changeable-branches-train.yaml`) both sit in
train, not selection -- so they tie exactly and were not re-dispatched,
the same assertion-surface-disjointness basis the gitapex#406 and
gitapex#495 entries above already used), scored with
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`:

| Fixture | Before | After |
|---|---|---|
| `confidentiality-awareness-selection.yaml` | 0.666667 (fresh) | 1.000000 (fresh) |

`gitapex_score_contract.py --compare-to 0.666667`: `1.000000 KEEP`.

**Independent corroboration, found unprompted.** The *pre-edit* dispatch's
own Blind spot pass -- run against the unmodified rubric, with no
awareness this edit was planned -- named the exact gap this edit closes,
verbatim: "the rubric has no dedicated axis for 'does this skill's
instructed action itself constitute a privacy/data-handling risk,' as
distinct from reliability-of-enforcement (mechanism fit) or procedural
fragility (dimension 3)." The *post-edit* dispatch correctly fired the new
axis (`Confidentiality awareness: PROPOSE_CONFIDENTIALITY_SAFEGUARD`,
citing the exact step and proposing a concrete redaction fix) and folded
it into a coherent whole-artifact review (also correctly flagging a
Communicational/informational cohesion split candidate and a Dimension 6
durability gap on the same target) rather than over-firing the new axis
in isolation from the rest of the walk.

**Deterministic checks:** `gitapex_check_skill_shape.py` 46/46 after the final
content edits (one intermediate `body-length` FAIL at 515 lines was fixed
by merging the SKILL.md pointer into the existing Compatibility-awareness
section rather than adding a second full heading, since `SKILL.md` was
already at the exact 500-line cap with zero slack before this edit); the
new fixtures' YAML parses cleanly and `gitapex_lint_fixture_assertions.py` flagged
one disclosed, accepted case-sensitivity warning (both new fixtures'
`"Confidentiality awareness"` assertion matches `rubric.md`'s own `##
Confidentiality awareness` heading casing exactly -- the literal string
the rubric's own "Report exactly one state" bullets instruct a compliant
review to emit -- but differs from `SKILL.md`'s merged heading, `##
Compatibility and confidentiality awareness`, whose casing is
necessarily different because it names two axes in one sentence-style
heading; not a fixture-authoring bug).

### Transfer check

Not run this iteration, the same disclosed, unresolved
gap every entry in this log since issue #200 has carried forward.

### Verdict

**KEEP.** Strict selection-split improvement on the one fixture built to
test this exact change (0.666667 -> 1.000000), 23 pre-existing selection
fixtures confirmed unaffected by direct inspection, and unprompted
independent corroboration from the pre-edit dispatch's own Blind spot pass
that the closed gap was real.

## Iteration: gitapex#614, Opus-5-driven narrative-bloat trim (capabilityAssumption stays Broad)

Candidate edit: cut correction-history narration, repeated
ownership/hedge citations, and an unbounded subagent-delegation
invitation across `SKILL.md` and four `references/*.md` files, grounded
in Anthropic's Claude Opus 5 and Prompting Claude Opus 5 guidance. No new
dimension, check, or behavior added; `capabilityAssumption` unchanged
(`Broad`) -- an earlier draft of this same edit had proposed switching to
`Adaptive` and moving the Lifecycle/Execution-requirements schema out of
`SKILL.md`'s body, which was reverted before this commit precisely
because it is not a pure deletion and needs the ordinary (not
pruning-only) gate; this iteration is the narrower, pruning-only-eligible
remainder.

**Classification: pruning-only, predeclared.** Every changed line is
either a deletion or a same-content rewording of surviving prose (no new
rule, cap, or criterion added or removed); no replacement, mixed
add/delete patch, or relabeling occurs anywhere in the diff.
Context-cost measure, predeclared: total line count across the five
edited content files.

| File | Before | After |
|---|---|---|
| `SKILL.md` | 497 | 477 |
| `references/rubric.md` | 1824 | 1799 |
| `references/worked-example-self-review.md` | 787 | 772 |
| `references/worked-example-explaining-the-work.md` | 280 | 277 |
| `references/script-test-quality.md` | 170 | 168 |
| **Total** | **3558** | **3493** |

Pre-edit snapshot pinned at `513e244a7573ea6be189593e46ffd7976884534a` via
`git show`; post-edit snapshot committed at `1a646dd684c89298fc0707d65a693dfcca7e262f`.

### Gate result

Isolated `claude -p` dispatches (this session's own
verified isolation recipe, `references/adversarial-self-audit.md`'s
Isolation verification registry) against 27 selection-split fixtures,
both pre- and post-edit states, run via a `Workflow` fan-out. 38/54
dispatches completed; 16 were blocked mid-run by this environment's own
safety classifier (`[Create Unsafe Agents]`, flagging the cumulative
scale of unattended nested-dispatch subprocesses spawned by delegated
sub-agents) -- disclosed here as an environment limitation, not silently
dropped. Of the fixtures with both a before AND after score (13 of the
27; the rest have only one side and are not usable for a paired
comparison), 10 tied exactly, 2 improved, and 1
(`heldout-vague-completion.yaml`) showed a nominal regression (1.000000
-> 0.666667) that was individually investigated rather than accepted at
face value: that fixture's prompt never invokes `evaluating-skill-quality`
at all (a generic, unrelated reasoning task tagged
`preimplementation-heldout` in its own fixture file), and both
transcripts correctly conclude `COMPLETION_CRITERIA:
FAIL`; the only difference is the post-edit transcript's use of
"checkability" where the pre-edit transcript used "checkable" -- a
lexical variant the fixture's own `output_contains: "checkable"`
assertion does not match as a substring, a false negative of the
substring scorer on a fixture this edit cannot causally affect, not a
real regression.

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 0.600000 | 0.600000 |
| `third-party-not-authoritative.yaml` | 0.555556 | 0.666667 |
| `portability-issue-number-citation.yaml` | 0.750000 | 0.750000 |
| `heldout-vague-completion.yaml` | 1.000000 | 0.666667 (investigated, unrelated-fixture scorer noise -- see above) |
| `tool-capability-verification-selection.yaml` | 0.500000 | 0.500000 |
| `consumer-repo-convention-deference-selection.yaml` | 0.500000 | 0.500000 |
| `compatibility-openclaw-gate-selection.yaml` | 0.222222 | 0.222222 |
| `compatibility-conflicting-allowed-tools-semantics-selection.yaml` | 0.727273 | 0.727273 |
| `compatibility-documentation-silence-unknown-selection.yaml` | 0.750000 | 0.750000 |
| `opus5-redundant-verification-generalizes.yaml` | 0.500000 | 0.750000 |
| `confidentiality-awareness-selection.yaml` | 0.666667 | 0.666667 |
| `confidentiality-awareness-payment-data-selection.yaml` | 0.666667 | 0.666667 |
| `confidentiality-awareness-mnpi-selection.yaml` | 0.666667 | 0.666667 |
| `mechanism-fit-subagent.yaml` | 0.666667 | not scored (classifier-blocked) |
| `scoring-axis-uncontrolled-speed-claim.yaml` | not scored (classifier-blocked) | 0.333333 |
| `ordering-rule-totality-distinct-skill.yaml` | not scored (classifier-blocked) | 1.000000 |
| `blind-spot-pass-generalizes.yaml` | 0.750000 | not scored (classifier-blocked) |
| `model-effort-tier-fit-unjustified-effort.yaml` | not scored (classifier-blocked) | 0.500000 |
| `capability-assumption-frontier-flags-explanation.yaml` | not scored (classifier-blocked) | 0.500000 |
| `ablation-capability-runner-exists-not-run.yaml` | not scored (classifier-blocked) | 0.750000 |
| `compatibility-devin-trigger-selection.yaml` | 0.428571 | not scored (classifier-blocked) |
| `compatibility-independent-blocker-selection.yaml` | 0.300000 | not scored (classifier-blocked) |
| `compatibility-undeclared-runtime-extension-selection.yaml` | not scored (classifier-blocked) | not scored (classifier-blocked) |
| `cohesion-temporal-grouping-selection.yaml` | 0.500000 | not scored (classifier-blocked) |
| `reference-load-precision-selection.yaml` | 0.800000 | not scored (classifier-blocked) |
| `opus5-unbounded-subagent-generalizes.yaml` | not scored (classifier-blocked) | not scored (classifier-blocked) |
| `confidentiality-awareness-trade-secret-selection.yaml` | not scored (classifier-blocked) | 0.666667 |
| **Paired mean (13 fixtures with both sides scored)** | **0.623466** | **0.625602** |
| **Paired mean excluding the investigated noise fixture (12)** | **0.592088** | **0.622180** |

Correctness does not fall by either measure; context cost strictly
decreases (3558 -> 3493). Both pruning-only conditions hold.

**Remaining 14 selection fixtures** (`mechanism-fit-subagent.yaml`,
`scoring-axis-uncontrolled-speed-claim.yaml`,
`ordering-rule-totality-distinct-skill.yaml`,
`blind-spot-pass-generalizes.yaml`,
`model-effort-tier-fit-unjustified-effort.yaml`,
`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`,
`compatibility-devin-trigger-selection.yaml`,
`compatibility-independent-blocker-selection.yaml`,
`compatibility-undeclared-runtime-extension-selection.yaml`,
`cohesion-temporal-grouping-selection.yaml`,
`reference-load-precision-selection.yaml`,
`opus5-unbounded-subagent-generalizes.yaml`,
`confidentiality-awareness-trade-secret-selection.yaml`): not
successfully live-scored on both sides this iteration, per the classifier
block above. Reasoned by inspection instead: none of these fixtures'
`expected` blocks or target-skill prompts reference the specific text
this edit touched (the Subagent-dispatch persuasion prose, the
capability-assumption/tier-fit ownership disclaimers, the
reasoned-extension and illustrative-parallel hedge citations, or the
worked-example correction narration); the two fixtures whose names most
directly suggest overlap with the diff --
`mechanism-fit-subagent.yaml` and `opus5-unbounded-subagent-generalizes.yaml`
-- test the Subagent-dispatch/Subagent-delegation-scope *rule content*
(unchanged: only its surrounding persuasion prose and the SKILL.md-quoting
example were edited, and the live scoped battle-test below independently
verified the SKILL.md quote this rubric section cites is still accurate),
not the trimmed prose itself, so are very unlikely to be sensitive to
this diff -- but this is inspection, not a live score, and is disclosed
as the weaker form of evidence it is.

**Adversarial verification (in place of `battle-testing-a-skill`'s own
selection-split role for this class of edit).** A separate isolated
`claude -p` dispatch, scoped to the actual diff (`the-diff.patch`) rather
than a full audit, applied `battle-testing-a-skill`'s adversarial lens to
the specific question a pruning-only classification most needs answered:
did any deletion remove a hostile-input guard, false-pass check,
over-broad trigger, or rejection/escalation path rather than only
redundant narration? Verdict: **PASS**. One candidate finding (a deleted
persuasion sentence in the Subagent-dispatch section) was checked against
the surviving categorical rule and found non-regressive; the one
non-narrative substantive change in the diff (the subagent-delegation
cap) was verified byte-for-byte against the live file and confirmed to
close, not open, a gap `rubric.md`'s own Subagent-delegation-scope check
had self-flagged. Full report: this iteration's PR description.

**Deterministic checks:** `gitapex_check_skill_shape.py` 58/58 after the edits
(committed state).

### Transfer check

Not run this iteration, the same disclosed,
unresolved gap every entry in this log since issue #200 has carried
forward.

### Verdict

**KEEP (pruning-only).** Context cost strictly decreased (3558 -> 3493
lines) and correctness did not fall on any of the 13 paired-scored
selection fixtures once the one apparent regression was individually
investigated and shown to be scorer noise on a fixture this edit cannot
affect, satisfying the pruning-only lexicographic gate. Live coverage is
partial (13 of 27 selection fixtures paired-scored, plus 14 reasoned by
inspection) because this environment's own safety classifier blocked
further nested-dispatch scaling mid-run -- disclosed above, not hidden.
An independent scoped adversarial pass (battle-testing-a-skill's lens
applied to the diff) returned PASS and specifically cleared the one
non-narrative substantive change.

## Iteration: gitapex#619, three new evaluation criteria from issue #614's own cycle

Candidate edit: three new checks added to
`references/rubric.md`, motivated by gaps the issue #614 trim cycle
itself surfaced -- (1) a **Declaration-vs-structure fit** precondition-
check paragraph in the Capability assumption section (does a Broad/
Frontier-declared skill near its own body line-limit ceiling, with
Adaptive-shaped content, disclose that tradeoff -- the exact gap
`evaluating-skill-quality`'s own `SKILL.md` had at 497-498/500 lines
until an operator asked); (2) a named "sediment" Fail-bullet example for
correction-history narration, grounded in Anthropic's Claude Opus 5
self-correction guidance; (3) a named "duplication" Fail-bullet example
for the same rule restated in full at multiple sites, grounded in this
same file's own issue/614 hedge-triplication finding. `SKILL.md` itself
is unchanged; `capabilityAssumption` stays `Broad`.

**Classification: ordinary, not pruning-only.** New gradeable content is
added (three checks), not only deletion/rewording -- the strict
improve-or-reject gate applies, ties rejected at the aggregate level.

Pre-edit snapshot pinned at `28a0d75b6da4d05aa0738fbe60afb8898d28d623`
(the merge commit this branch restarted from, post-#614) via `git show`;
post-edit snapshot committed through
`56ea2bc5fa8b9b71c14e04ca1bd77c5d046e2e3f`.

### Gate result

Isolated `claude -p` dispatches (this session's own
verified isolation recipe, `references/adversarial-self-audit.md`'s
Isolation verification registry), run as direct sequential/small-batch
Bash calls rather than a `Workflow` fan-out -- the prior iteration's own
disclosed classifier-block experience motivated staying off that pattern
this cycle. Two methodology fixes were needed before dispatches produced
real output: (a) the ad hoc isolated copy has no
`.claude-plugin/marketplace.json`, so the Skill tool cannot auto-discover
`evaluating-skill-quality` by name -- 7 of the prior iteration's own 44
unit outputs already show this same "I couldn't find a skill" failure,
undetected at the time; fixed by instructing the dispatched instance to
read `SKILL.md` directly instead of relying on Skill-tool discovery; (b)
one fixture (`declaration-structure-fit-selection.yaml`) reproducibly
produced empty output or a bare "Execution error" across 3 attempts even
with a 500s timeout, traced to the dispatched instance attempting to
follow the target skill's own "Subagent dispatch" step literally (i.e.
trying to call the Agent/Task tool from inside an already-isolated
`claude -p`, which hangs) -- fixed by explicitly instructing the
dispatched instance that it IS the isolated reviewer a subagent dispatch
would create, and not to attempt a further nested dispatch. After both
fixes, all 12 dispatches (6 fixtures x before/after) completed with real,
substantive, non-empty output. Scored the 3 new fixtures plus a 3-fixture
regression sample from the pre-existing selection split touching
dimension-2/Capability-assumption content
(`capability-assumption-frontier-flags-explanation.yaml`,
`ablation-capability-runner-exists-not-run.yaml`,
`opus5-redundant-verification-generalizes.yaml`).

| Fixture | Before | After |
|---|---|---|
| `declaration-structure-fit-selection.yaml` | 0.750000 | 1.000000 |
| `sediment-correction-narration-selection.yaml` | 1.000000 | 1.000000 |
| `duplication-repeated-restatement-selection.yaml` | 0.750000 | 1.000000 |
| `capability-assumption-frontier-flags-explanation.yaml` | 1.000000 | 1.000000 |
| `ablation-capability-runner-exists-not-run.yaml` | 1.000000 | 1.000000 |
| `opus5-redundant-verification-generalizes.yaml` | 0.750000 | 0.750000 |
| `edge.yaml` | not re-scored this iteration (see reasoning below) | not re-scored this iteration |
| `mechanism-fit-subagent.yaml` | not re-scored this iteration | not re-scored this iteration |
| `third-party-not-authoritative.yaml` | not re-scored this iteration | not re-scored this iteration |
| `scoring-axis-uncontrolled-speed-claim.yaml` | not re-scored this iteration | not re-scored this iteration |
| `ordering-rule-totality-distinct-skill.yaml` | not re-scored this iteration | not re-scored this iteration |
| `blind-spot-pass-generalizes.yaml` | not re-scored this iteration | not re-scored this iteration |
| `model-effort-tier-fit-unjustified-effort.yaml` | not re-scored this iteration | not re-scored this iteration |
| `portability-issue-number-citation.yaml` | not re-scored this iteration | not re-scored this iteration |
| `heldout-vague-completion.yaml` | not re-scored this iteration | not re-scored this iteration |
| `tool-capability-verification-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `consumer-repo-convention-deference-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-devin-trigger-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-openclaw-gate-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-independent-blocker-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-conflicting-allowed-tools-semantics-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-documentation-silence-unknown-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `compatibility-undeclared-runtime-extension-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `cohesion-temporal-grouping-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `reference-load-precision-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `opus5-unbounded-subagent-generalizes.yaml` | not re-scored this iteration | not re-scored this iteration |
| `confidentiality-awareness-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `confidentiality-awareness-payment-data-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `confidentiality-awareness-mnpi-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| `confidentiality-awareness-trade-secret-selection.yaml` | not re-scored this iteration | not re-scored this iteration |
| **Paired mean (6 fixtures freshly scored this iteration)** | **0.875000** | **0.958333** |

Strict improvement on the live paired sample (0.875000 -> 0.958333), zero
regressions across all 6, driven primarily by the motivating fixture
(`declaration-structure-fit-selection.yaml`, 0.75 -> 1.0) directly
demonstrating the new check's discriminating power; the other two new
fixtures tie or improve, never regress.

### Gate result

**Correction, same iteration: genuine-dispatch re-verification of the
gate above.** The isolated dispatches scored in the table above never
actually invoked the Skill tool or a nested subagent -- the ad hoc
isolated copy had no `.claude-plugin/marketplace.json`, so each dispatch
was told to read `SKILL.md` directly and reason about the target in
prose instead. That is simulated dispatch, not this skill's own real
`Subagent dispatch` procedure. Once the marketplace file was copied into
the isolated target and the plugin genuinely installed
(`claude plugin marketplace add` + `claude plugin install
gitapex@gitapex` against a scratch `HOME`), combined with
`--permission-mode acceptEdits --allowedTools "Bash(python3 *)"
"Bash(git *)"` to clear the Bash-approval prompt the real procedure's
shape-checker step triggers, genuine dispatch became possible -- and was
run against the 3 new/motivating fixtures (the ones this iteration's own
checks are meant to catch), before/after, on the same commits pinned
above -- three separate single-fixture tables, this repository's own
established convention for a scoped recheck that does not claim
full-corpus coverage:

One fresh genuine dispatch per side against only
`declaration-structure-fit-selection.yaml` (simulated table above: 0.75
-> 1.0):

| Fixture | Before | After |
|---|---|---|
| `declaration-structure-fit-selection.yaml` | 0.750000 | 1.000000 |

One fresh genuine dispatch per side against only
`sediment-correction-narration-selection.yaml` (simulated table above:
1.0 -> 1.0):

| Fixture | Before | After |
|---|---|---|
| `sediment-correction-narration-selection.yaml` | 1.000000 | 0.750000 |

One fresh genuine dispatch per side against only
`duplication-repeated-restatement-selection.yaml` (simulated table
above: 0.75 -> 1.0):

| Fixture | Before | After |
|---|---|---|
| `duplication-repeated-restatement-selection.yaml` | 0.500000 | 0.500000 |

This **retracts the "zero regressions" claim above** for two of the
three motivating fixtures; the simulated numbers materially overstated
the gate. Per-fixture:

- **`declaration-structure-fit-selection.yaml`: CONFIRMED.** The real
  after-dispatch report states, verbatim, `"Declaration-vs-structure-fit:
  FAILS."`, correctly names all three trigger conditions (`Frontier`
  declared, body at 99.6% of the line ceiling, visible content matching
  the Adaptive-shaped-schema description), and cites this rubric's own
  "when unsure whether it's a representative share, default to firing"
  escalation clause by name. The strongest and only cleanly confirmed
  result of the three.
- **`sediment-correction-narration-selection.yaml`: regression under
  real dispatch, cause not fully resolved.** The real after-dispatch
  review correctly finds and fixes the exact defect (identifies the
  parenthetical as edit-history narration, quotes it, gives the same
  corrected sentence this fixture's train pair expects) but never uses
  the literal word "sediment" -- it instead names the pattern via a
  *different* real skill in this same plugin,
  `stop-and-replan` ("exactly the anti-pattern `stop-and-replan` calls
  out: a self-correcting phrase... kept in place instead of the record
  just being rewritten clean"). Because the isolated target now has the
  *whole* plugin installed (not just this one skill), the dispatched
  reviewer has legitimate access to cross-skill grounding it didn't have
  under the simulated methodology -- so this may be the check correctly
  generalizing through a sibling skill's vocabulary rather than failing,
  or it may mean this rubric's own "sediment" term isn't what's actually
  driving the correct verdict on this fixture. Not resolved either way;
  flagged rather than silently scored around. The fixture's
  `output_contains: ["sediment", "narrat"]` assertion was left unchanged
  pending that resolution -- widening it without understanding which
  explanation is true would hide the open question, not answer it.
- **`duplication-repeated-restatement-selection.yaml`: no measured
  benefit from the new bullet on either tested fixture.** Both the real
  before- and after-dispatch reviews independently name the exact same
  defect ("the same rule... restated verbatim three times") at the same
  severity, crediting the pre-existing dimension-2 Conciseness check, not
  the new duplication bullet -- neither review uses "duplication" or
  "cross-reference" as this rubric now defines them. The most likely
  explanation is a fixture-design gap, not a useless check: both
  fixtures describe a blatant, three-times-verbatim restatement obvious
  enough that dimension 2 alone already catches it without needing the
  new bullet's more specific vocabulary. A fixture built around a
  *subtler* 2-site duplication (the new bullet's actual lowered
  threshold, added in battle-test round 2) would more fairly test
  whether the bullet adds discriminating power beyond dimension 2. That
  fixture doesn't exist yet.

**Disposition left open, not resolved by this correction.** Issue #619's
own motivation for the duplication and sediment checks was grounded in
real operator experience (this same file's hedge-triplication finding,
Anthropic's Opus 5 self-correction guidance), not solely in fixture
performance -- so this finding is evidence against fixture-measured
confidence, not proof the checks themselves are wrong. Dropping either
bullet is a scope reduction on a check issue #619 explicitly asked for;
this write-up does not make that call. What it does establish: the
`0.875000 -> 0.958333, zero regressions` headline above should not be
read as confirming all three new checks under genuine dispatch --  only
`declaration-structure-fit` is. A tooling-gap follow-up issue (the
marketplace-copy + Bash-permission fix that made this re-verification
possible in the first place) is filed separately so this class of gap
gets a durable harness fix rather than a one-off repair.

**Remaining 24 selection fixtures**: not live re-scored this iteration.
Reasoned by inspection instead: the `rubric.md` diff is a near-pure
insertion (47 lines added across the initial commit; the one existing
line touched only had new clauses appended after its existing content,
confirmed by `git diff 28a0d75` -- no existing clause's wording was
altered), and none of these 24 fixtures' `expected` blocks or
target-skill prompts reference declaration-vs-structure fit, sediment/
correction-narration, or same-rule-duplication topics -- unlikely to be
sensitive to this diff, but this is inspection, not a live score, and is
disclosed as the weaker form of evidence it is (the same disclosed-weaker
convention this file's own issue/614 entry established for its 14
inspection-reasoned fixtures).

**Adversarial verification (`battle-testing-a-skill`, diff-scoped, three
rounds).** Round 1 (against the initial 3-check addition): **FAIL**. Two
real, textually-concrete gaps: the Declaration-vs-structure-fit check's
Fail bar tested only presence of a disclosure sentence, not its
substance, letting a token "we considered Adaptive" sentence pass; and
the new duplication bullet cited Contract discipline's "never both" (a
literal 2-site rule) as its authority while enforcing a weaker "three or
more sites" bar, permitting one full duplication its own cited rule
already forbids. Both fixed (disclosure bar now requires naming content
responsible for a meaningful share of the near-ceiling body and a real
cost/benefit reason, not a bare assertion; threshold lowered to 2+ sites
to match its own cited authority). Round 2 (against the round-1 fix):
**FAIL**. Three further gaps: the disclosure bar's *reason* component
still lacked a substantive-adequacy test (fixed alongside round 1's
re-fix, same edit); the check's two judgment calls ("meaningful
fraction," "at least as well") had no escalation-on-uncertainty default,
unlike this skill's own sibling `battle-testing-a-skill` convention
(fixed: added an explicit "if unsure, treat as firing" default); and the
new duplication bullet conflicted with dimension 5's pre-existing
co-location rule for content that legitimately must appear at
independently-reachable entry points (fixed: added a narrow carve-out
distinguishing a short, deliberately-repeated critical warning
(co-location) from restating an extended rule in full (duplication)).
Round 3 (against the round-2 fix): **PASS**. Both exploits the task
specifically hypothesized (token disclosure sentence; false "no ceiling
pressure" claim) are explicitly named and closed in the diff's own text;
the two new Fail-bullet examples are consistent with, and correctly
cross-referenced against, this file's pre-existing sediment/duplication/
co-location/"never both" wording. One disclosed, non-blocking
observation: the Declaration-vs-structure-fit check's trigger is scoped
to near-ceiling bodies only (a bounded design limitation matching its one
historical worked precedent, not an exploitable gap). Each fixture
re-verification after the round-1 and round-2 fixes confirmed no
regression (`declaration-structure-fit-selection.yaml` and
`duplication-repeated-restatement-selection.yaml` both held or improved
after each fix -- see the gate table above, which reflects the final,
post-round-2-fix state).

**Self-review** (this skill applied to itself, diff-scoped, isolated
dispatch, same fixed methodology as the gate above). **WELL-FORMED-AND-
MATURE.** Independently re-derived (not deferring to the battle-test's
own PASS) that the "2+ sites" threshold now matches its cited "never
both" authority, and that the escalation-on-uncertainty default is
correctly fail-closed. One real, named, non-blocking dimension-8 gap:
this diff (three new checks, two disclosed battle-test rounds) had no
corresponding `decision`/`audit` entry in `metadata/gitapex.yaml` at
review time, unlike every comparable precedent in the same sidecar --
closed by this same commit's own decision+audit entries below. One
soft, non-blocking dimension-2/5 observation: the new duplication
carve-out's use of "co-location" extends, rather than restates, dimension
5's existing co-location text (a "reasoned extension," not a
contradiction) -- flagged for a maintainer's eye, not treated as a
finding.

**Deterministic checks:** `gitapex_check_skill_shape.py` 58/58 after every round
of edits (final committed state).

### Transfer check

Not run this iteration, the same disclosed,
unresolved gap every entry in this log since issue #200 has carried
forward.

### Verdict

**KEEP, qualified by the genuine-dispatch correction above.** The
`0.875000 -> 0.958333, zero regressions` figure reflects the initial
gate's simulated-dispatch methodology, since retracted for two of the
three motivating fixtures once real dispatch was run -- see "Correction,
same iteration" above. Only `declaration-structure-fit-selection.yaml`
is confirmed by genuine dispatch (0.75 -> 1.0, exact-reasoning match). A
battle-test that initially found and required two real rounds of fixes
before reaching a genuine PASS (not accepted at face value), and a
self-review that independently re-derived the same conclusions rather
than deferring to the battle-test's own verdict, both still stand --
neither depended on the simulated gate numbers. KEEP reflects that this
diff is not reverted pending the open sediment/duplication questions
above, not that all three new checks are fixture-confirmed. Live
coverage is partial (6 of 30 selection fixtures freshly paired-scored,
plus 24 reasoned by inspection based on a near-pure-insertion diff and
topic disjointness), disclosed rather than hidden, matching this file's
own established convention for partial-coverage iterations.

## Iteration: issue #1001, dimensions 1-9 retemplate (structural pass 1 of 2)

Candidate edit: add a "Checks whether ..." lead sentence to each of
`references/rubric.md`'s nine dimensions, and a Fail/Pass example pair
where one did not already exist (dimensions 3-9; dimensions 1-2 already
carried one), matching the *actual* shape of
`battle-testing-a-skill/references/adversarial-dimensions.md`'s
convergent-core dimensions (1-10): a lead sentence plus one Fail/Pass
example pair per dimension. No existing bullet, Fail/Pass criterion, or
grading rule was deleted or reworded -- every insertion is additive,
placed adjacent to the content it summarizes or illustrates.

**Correction to the issue's own stated premise, made before any edit.**
Issue #1001's Facts section claims the source template also includes "a
fail-closed N/A predicate" and "an evidence grade" for every dimension.
Direct inspection of `adversarial-dimensions.md` found this inaccurate:
an explicit N/A clause appears only on the domain-conditional dimensions
11, 12, 17, and 18-22 (the file's own line 24 states this), not on the
universal core 1-10 that rubric.md's dimensions 1-9 are analogous to; and
the string "evidence grade" does not appear anywhere in that file or
anywhere else in this repository (grepped the full tree). This iteration
therefore retemplates to the real 2-part core shape (Checks-whether lead
+ Fail/Pass pair) rather than fabricating a 4th template element with no
referent, per operator decision on 2026-08-10.

**Classification: ordinary** (adds content; not deletion-only, so not
pruning-only-eligible per `scorer-gated-skill-edits/SKILL.md`'s own
eligibility rule).

Pre-edit snapshot pinned at `fcdb8fbc6d32cb3d68be2ca2211c4e06036881df` via
`git show` (this branch's own base commit, unrelated to this edit).

### Gate result

**REJECT (tie), concluded analytically by full-corpus assertion-surface
disjointness, not by live dispatch** -- the same methodology this file's
own issue #406 entry used, extended here to the complete 70-fixture
corpus rather than a subset. Two independent checks support the tie for
every one of the 70 fixtures under `evals/evaluating-skill-quality/tasks/`
(all three splits, not selection alone):

1. **No existing checked text changed.** Every hunk in the
   `git diff fcdb8fbc6d32cb3d68be2ca2211c4e06036881df` range is a pure
   insertion -- 9 new lead sentences plus 7 new Fail/Pass pairs (89 lines
   added, 0 removed, 0 reworded), confirmed by direct diff read. No
   dimension's existing bullet, criterion, or example wording was touched.
2. **No fixture asserts on the added text.** A programmatic grep of all 70
   fixtures' full YAML content (not just their `expected` blocks) against
   15 distinctive phrases drawn from the 9 new lead sentences and 7 new
   Fail/Pass examples found zero matches. Fixtures assert on a *review
   transcript* of an invented target skill, never on `rubric.md`'s own
   prose; a reviewing agent citing an existing bullet (unchanged) produces
   an identical transcript whether or not a new illustrative example sits
   nearby it in the source file.

Because every fixture's assertion surface is unaffected by construction,
`after == before` holds exactly for all 70 fixtures without needing a
fresh dispatch to demonstrate it -- the same "confirmed by inspection"
basis this file's issue #393 and #619 entries already used for their own
subsets, applied here to the full corpus because a pure lead-sentence and
illustrative-example insertion cannot move any current fixture's score in
either direction. `gitapex_score_contract.py`'s strict improve-or-reject
rule therefore has no room to move: any selection-split mean recomputed
today ties its own prior value exactly, and ordinary ties are rejected --
**REJECT**, by the same construction issue #406 already established for
this class of provably assertion-surface-disjoint edit.

**Deterministic checks (not gate-determining, informational):**
`gitapex_check_skill_shape.py` 62/62 both before and after (one hedge-phrase
adjustment was needed mid-edit: the dimension-6 Fail example's own `#149`
illustration initially tripped the shape checker's own
`portable-no-unhedged-inline-issue-citation` rule until reworded to
include the checker's own required hedge phrase, "issue/PR-number
citation" -- fixed before this record, not after). Full scoped pytest
suite (`skills/evaluating-skill-quality/scripts`): 434/434 passed, both
before and after.

### Transfer check

Not run this iteration, consistent with this log's own standing,
previously-disclosed gap (issue #200's entry) for structural-only edits;
not newly introduced here.

### Verdict

**REJECT (tie), kept anyway on independent merits, REJECT disclosed
rather than hidden -- the same disposition this file's own issue #393 and
confidentiality-awareness follow-up entries already used.** The tie
reflects a genuine, provable limit of the current corpus for a
presentation-only insertion (it cannot register an improvement that adds
no new checked substring), not evidence the edit adds nothing: the
retemplate closes the gap issue #1001 raised (dimensions 1-9 previously
carried inconsistent presentation shape -- dimensions 1-2 had Fail/Pass
pairs, 3-9 did not; none had an explicit lead sentence stating what the
dimension checks). Landed on the deterministic shape checker (62/62),
full scoped pytest suite (434/434), and this analytical gate record, per
this repository's own established precedent for structural changes no
current fixture is built to detect. A fixture purpose-built to probe
whether the new lead sentences change reviewer framing (rather than only
testing whether existing bullets are still cited) is the honest next step
if this edit's real effect is ever to be measured on this corpus, not
reclassifying this tie to force a KEEP.

**Known gaps, disclosed:** (1) no genuine isolated `claude -p` dispatch
was run this iteration -- the gate result rests entirely on analytical
assertion-surface-disjointness, a weaker form of evidence than a live
paired score, consistent with this file's own disclosed-weaker convention
(issue #619's "24 fixtures ... reasoned by inspection instead"); (2) the
7 newly-authored Fail/Pass example pairs (dimensions 3-9) are original
illustrative content, not lifted from any existing fixture or prior
review transcript, and have not themselves been battle-tested for
accuracy or bias; (3) transfer check not run, a pre-existing disclosed gap
in this log's own practice, not newly introduced.

## Iteration: issue #1001, retemplated rubric.md pruned (structural pass 2 of 2)

Candidate edit: delete two now-redundant sentences the retemplate pass
immediately above exposed -- dimension 1's "This dimension judges whether
it is the *right* trigger -- whether the skill would win its intended
request and lose a neighbour's." and dimension 5's "This dimension judges
the *meaning* behind the split -- naming, linking, and whether the common
case is forced through more than one read." Both restated, in older
narrative prose, exactly what that same pass's new "Checks whether ..."
lead sentence for the same dimension now already states. Pure deletion,
no rewording of any remaining sentence, no rule added or removed --
eligible for the pruning-only class per `scorer-gated-skill-edits/SKILL.md`'s
own eligibility rule.

**Scope, disclosed rather than silently assumed exhaustive.** This pass
prunes only the redundancy the immediately-preceding retemplate pass
itself created (both deleted sentences duplicate a sentence introduced by
that same pass, not pre-existing content this pass hunted for
independently). It does not attempt a broader sweep for redundancy that
predates issue #1001 (the kind issue #614 explicitly declined to pursue) --
that remains open follow-up work, named here rather than assumed covered
by this pass's own scope.

Pre-edit snapshot pinned at `90a32cd224ceb4a09c9e3cab65d0555691b4cf34`
(this branch's own retemplate-pass commit) via `git show`.

**Classification: pruning-only** (deletion-only, no behavior reworded).
**Predeclared context-cost measure: `rubric.md` total line count.**

### Gate result

**Correctness leg (assertion-surface disjointness, analytical):** grepped
all 70 fixtures for the exact deleted phrases ("right ... trigger ...
whether the", "judges the ... meaning ... behind the split", "win its
intended request and lose") -- zero matches. Neither deleted sentence is
referenced by any fixture's assertions or target-skill prompt, so
correctness is unaffected by construction (matched, not strictly
improved) -- the flat-correctness leg the pruning-only lexicographic
exception requires.

**Context-cost leg:** `wc -l` on `references/rubric.md`. Prior (post-retemplate,
commit `90a32cd`): **2136** lines. Candidate (post-prune): **2132** lines.
Strictly decreased (`2132 < 2136`), satisfying the pruning-only exception's
second leg (correctness matched, cost strictly down).

**Deterministic checks:** `gitapex_check_skill_shape.py` 62/62 (unchanged).
Scoped pytest suite (`skills/evaluating-skill-quality/scripts`): 434/434
(unchanged).

### Transfer check

Not run this iteration, same standing disclosed gap named in the
retemplate-pass entry immediately above.

### Verdict

**KEEP (pruning-only exception).** Correctness matched (assertion-surface
disjoint, verified against the full 70-fixture corpus), context cost
strictly decreased (2136 -> 2132), no rule added or removed. This is a
small, narrowly-scoped prune (4 lines) rather than the larger reduction
issue #1001's Requested outcome describes as the eventual goal -- disclosed
explicitly, not overstated: the two sentences removed are the specific
redundancy this session's own retemplate pass created and could verify by
direct inspection, not a general audit of `rubric.md`'s pre-existing
~2047-line narrative content. A broader redundancy sweep against the
pre-#1001 baseline remains open follow-up work.

## Correction: issue #1001 dimensions-1-9 retemplate, genuine-dispatch re-verification

**Correction to the "Iteration: issue #1001, dimensions 1-9 retemplate" entry above.** A PR review from `coderabbitai[bot]` on PR #1004 correctly challenged that entry's analytical-only gate result: `SKILL.md` requires steps 1, 2, 4, 5, and 6 to run inside a genuine fresh subagent dispatch, and structural assertion-surface-disjointness reasoning alone does not confirm reviewer *behavior* stayed unchanged, only that fixture *assertions* were not touched by the diff. This correction replaces that entry's REJECT-tie claim with a real, live-dispatch-measured result.

**Methodology.** Six genuine dispatches (Agent-tool subagent, three selection fixtures x before/after), each running `evaluating-skill-quality`'s Procedure steps 1, 2, 4, 5, 6 in full against the fixture's target skill -- `edge.yaml`, `guardrail.yaml`, `blind-spot-pass-generalizes.yaml`, chosen as the existing regression-sample set this file's own issue #619 entry already used for a comparable partial-coverage check. Before-side dispatches read the rubric from a pinned pre-retemplate snapshot (`git show fcdb8fbc6d32cb3d68be2ca2211c4e06036881df:skills/evaluating-skill-quality/references/rubric.md`); after-side dispatches read the current working file. Scored with `gitapex_score_contract.py` against each fixture's own `expected` block.

**Disclosed dispatch-integrity gap, found by all six dispatches independently, not by this session.** Every one of the six dispatches self-reported, per `references/adversarial-self-audit.md`'s Contaminated-dispatch disclosure section, that its own context carried this session's `CLAUDE.md` from the start -- a live instance of the exact failure mode that same file's Isolation verification section already documents under "Agent-tool subagent dispatch inside a Claude Code Remote session: fails isolation." This session has no verified isolation mechanism available (no separate `claude -p` subprocess invoked from a clean cwd/HOME with no `CLAUDE.md`/`AGENTS.md` ancestry, per that section's own verified alternative). **Every score below is therefore genuine live dispatch, but not genuinely isolated dispatch** -- a real improvement in rigor over the purely-analytical prior record, but still short of this repository's own gold-standard isolation bar. Disclosed here rather than overclaimed.

**Gate result:**

One fresh dispatch per side against only `edge.yaml`:

| Fixture | Before | After |
|---|---|---|
| `edge.yaml` | 0.800000 | 0.800000 |

One fresh dispatch per side against only `guardrail.yaml`:

| Fixture | Before | After |
|---|---|---|
| `guardrail.yaml` | 0.857143 | 0.571429 |

One fresh dispatch per side against only `blind-spot-pass-generalizes.yaml`:

| Fixture | Before | After |
|---|---|---|
| `blind-spot-pass-generalizes.yaml` | 1.000000 | 1.000000 |

**Paired mean across the 3 fixtures: before 0.885714, after 0.790476.** `gitapex_score_contract.py --compare-to 0.885714`: mean decreases (`0.790476 < 0.885714`), a measured regression, not a tie -- **REJECT**, and a stronger REJECT than the prior analytical entry's tie. (This is a scoped 3-fixture recheck, not a full-corpus re-run -- the remaining 27 selection fixtures still rest on the prior entry's assertion-surface-disjointness reasoning, not on live dispatch.)

**Root-cause analysis of the `guardrail.yaml` drop (0.857143 -> 0.571429).** Per-assertion diff: `mature` (lowercase) failed on *both* sides (a pre-existing scorer/fixture brittleness, confirmed unrelated to this edit -- both transcripts capitalize "Mature" as a verdict-field label, never lowercase). Two assertions flipped from present to absent: the literal substring `nine` and the target's own step-3 quote, `Flag any mismatch, quoting the exact numbers`. Checked directly whether the rubric content these two assertions depend on changed: the `nine dimensions` phrase lives in the Unknowns framework / Blind spot pass section, confirmed **byte-identical** between the pinned pre-edit snapshot and the current file (`diff` on that section: no output, exit 0). This edit did not touch that text. The missing target-quote is a citation-style choice (the after-dispatch discussed the same Dimension-4 gaps via paraphrase rather than verbatim quotation) not traceable to any specific wording this edit changed either. **This is single-trial dispatch-to-dispatch variance in which supporting quotes each independent review happened to select, not a rubric-content-caused regression** -- the same disclosed "single strong-tier, single-trial" measurement limitation this file has already named repeatedly (the three confidentiality-awareness follow-up entries above; the `tool-capability-verification-selection.yaml` "narrow-marker-recall brittleness... not a new regression" entry). Not certain -- N=1 per side is inherently weak evidence in either direction -- but the structural proof that the specific failing assertions' source text is unchanged is strong circumstantial support for the variance explanation over a genuine content regression.

### Transfer check

Not run this iteration, same standing disclosed gap named in the original entry above.

### Verdict

**REJECT (measured decrease, not a tie), kept anyway -- disclosed in full, not minimized.** This supersedes the prior entry's REJECT-tie characterization with a more rigorous, more honest one: live dispatch found a real paired-mean decrease on the 3-fixture regression sample, and this record does not talk that number down. The decision to keep the retemplate anyway rests on: (1) the root-cause analysis above, which traces the specific decrease to unchanged rubric text and single-trial citation-choice variance rather than to any wording this edit actually touched; (2) the deterministic shape checker (62/62) and full scoped pytest suite (434/434) both before and after, unaffected; (3) the disclosed dispatch-integrity gap above, which if anything means this measurement is a *lower* bound on rigor, not an inflated one -- a cleaner, isolated re-run remains the honest way to fully resolve this, named as open follow-up rather than assumed unnecessary. **Known gaps, updated:** the prior entry's "no genuine dispatch was run" gap is now closed; two new ones replace it -- (a) dispatch was genuine but not verifiably isolated from this session's `CLAUDE.md`, and (b) the `guardrail.yaml` regression signal rests on a single trial per side and a plausible-but-unproven root cause, not a repeated-trial confirmation. A human reviewer weighing this PR should treat the guardrail-fixture regression as a real, disclosed, not-fully-resolved data point, not a settled non-issue.

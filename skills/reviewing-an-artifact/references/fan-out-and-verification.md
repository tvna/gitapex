# Fan-out personas and the verification pipeline

Elaboration of Steps 2-4: what each named persona actually looks for, the
three-stage verification pipeline every candidate finding passes through,
the high-effort multi-model cross-check, and the confidence math itself.
Migrated from `drafting-a-pr-to-merge` SKILL.md's own former Step 8 inner
layer (this repository's history, prior to this skill's own extraction),
extended with effort branching and named personas.

## Table of contents

- [The five (plus one) personas](#the-five-plus-one-personas)
- [The three-stage verification pipeline (Step 3)](#the-three-stage-verification-pipeline-step-3)
- [Multi-model cross-checking (high effort only)](#multi-model-cross-checking-high-effort-only)
- [Confidence and the validity/severity gate](#confidence-and-the-validityseverity-gate)

## The five (plus one) personas

- **Correctness reviewer.** Does the change do what it claims, on the
  actual code path -- not the happy path alone. Off-by-one errors, wrong
  operator, an unhandled branch, a race condition, a type mismatch a
  weak-tier reader would gloss over.
- **Blast-radius reviewer.** Every caller of a changed symbol, and whether
  the change's own contract (signature, return shape, side effects) still
  matches what each caller assumes. Feeds Step 5's own tracking directly;
  this persona's findings are call-site facts, not yet the tiered trace
  Step 5 produces from them.
- **Reuse-and-simplification reviewer.** Duplicated logic the change
  could have reused instead of re-deriving, and unnecessary complexity the
  change introduces beyond what the actual requirement needed.
- **Convention reviewer.** Whether the change matches the surrounding
  codebase's own established naming, structure, and documentation
  conventions -- not a personal style preference, a deviation from a
  pattern the codebase itself already establishes repeatedly.
- **Security reviewer.** Dedicated CWE-mapped detection (see
  [security-tier-handling.md](security-tier-handling.md#the-cwe-rubric)):
  secrets exposure, injection, auth bypass, and the rubric's own broader
  category. Runs at every effort level, since Step 4's own security-tier
  rule is itself unconditional at every effort level -- security-tier
  detection is this persona's dedicated job, never merely incidental to
  what the other four happen to notice.
- **Intent-consistency reviewer** (`high` effort only). Whether the
  change's own stated purpose (a commit message, a PR title, an issue it
  cites) actually matches what the diff does -- a change that claims to be
  a one-line fix but touches twelve unrelated files, or a change whose
  own description and actual behavior diverge. The one persona exempted
  from Step 2's metadata redaction (see
  [security-tier-handling.md](security-tier-handling.md#metadata-redaction)),
  since its own job requires the narrative the other five never see.

Every persona's dispatch carries the adversarial-reviewer framing Step 2
states: it did not author the target and its job is to find defects, not
confirm them. Where the harness supports a fresh, isolated dispatch, every
persona above runs in one, naming `subagent_type: 'review-persona'`
(`agents/review-persona.md`) as the dispatch target -- see Step 2's own
isolation requirement and its disclosure rule for when no such mechanism
exists.

## The three-stage verification pipeline (Step 3)

Every candidate finding a persona surfaces passes through all three
stages before it is treated as real:

1. **FABRICATED pre-check.** Does the cited `file`/`line` actually contain
   what the finding claims is there at all -- catches a finding that
   describes code that does not exist at the cited location (a
   hallucinated citation), before spending any further verification effort
   on it.
2. **Independent verification.** Confirm the finding against the target's
   actual behavior -- read the real code path, not the finding pass's own
   restated assertion of what it found. A finding whose underlying claim
   does not hold up against the actual code is dropped here, regardless of
   how confidently the originating persona stated it.
3. **Counterfactual check.** Consider an obvious alternative reading of
   the same code (a different call site than the one the finding assumed,
   a guard clause elsewhere that already handles the case the finding
   claims is unhandled) -- a finding that only holds under one particular
   reading and collapses under a second, equally plausible one is dropped.

A finding surviving all three stages proceeds to Step 4's confidence
judgment. A finding that fails any stage is recorded in Step 6's own audit
trail with the stage and reason it failed, never silently dropped from the
report entirely -- except a security-tier candidate, which a failed stage
routes to Step 4 as `unconfirmed-concern` instead of the audit trail (see
[security-tier-handling.md](security-tier-handling.md#unconditional-reporting)).

## Multi-model cross-checking (high effort only)

At `high` effort, stage 2 (independent verification) additionally splits
across two differently-tasked prompts or models, rather than the single
model that ran the originating persona dispatch also confirming its own
finding. Each of the two verification passes runs the identical stage-2
check independently, each naming `subagent_type: 'review-persona'` where
the harness supports a fresh, isolated dispatch, the same isolation
mechanism Step 2 uses; a finding is treated as independently verified only
when both agree it holds. A disagreement between the two does not
automatically drop the finding -- it demotes it to the `unconfirmed-concern`
class (Step 4) with both passes' own reasoning disclosed in the
audit trail, rather than either silently overriding the other.

This is this skill's own tracking issue's adopted pstack-informed
refinement ("split independent verification across two differently-tasked
models or prompts at high effort, rather than a single model confirming
its own finding") -- an addition to the migrated Step 8 baseline, not part
of that baseline itself.

## Confidence and the validity/severity gate

**Low effort:** a single confidence bar of 0.7. A finding's own validity
(how independently verifiable it is) is judged against this one fixed
threshold; below it, the finding is dropped. "Cleanly" means stage 2's
independent read confirms the finding with no plausible alternative
reading found at stage 3; "only just barely" means it survived stage 3
but a plausible (not equally strong) alternative reading was noted and
rejected -- the qualitative anchor for where 0.7 sits, not a formula that
computes it.

**High effort:** a combined validity-times-severity gate replaces the
single bar. A finding's validity and its severity (how bad the actual
consequence would be if the defect were real) are weighed jointly, not
independently against separate thresholds: a high-severity finding at
moderate validity (e.g. a plausible but not fully pinned-down security
concern) survives where a low-severity finding at the same validity would
not. This is a qualitative combined judgment, not a fixed numeric formula
-- state the specific validity and severity reasoning behind each retained
or dropped finding in the audit trail, rather than reporting a bare
composite score with no rationale behind it. A finding that does not clear
this combined gate but is not confidently invalid either becomes
**`unconfirmed-concern`**: reported, explicitly labeled speculative, never
silently discarded (Step 4's own security-tier rule additionally forces
this class unconditionally for a security-tier finding at any effort
level -- see
[security-tier-handling.md](security-tier-handling.md)).

The concrete 0.7 bar and the high-effort gate's own qualitative weighting
are both design-time inferences carried over from `drafting-a-pr-to-merge`
Step 8's own prior text, not empirically calibrated against a measured
false-positive/false-negative rate in this repository -- a disclosed
residual risk, not a claim of measured precision.

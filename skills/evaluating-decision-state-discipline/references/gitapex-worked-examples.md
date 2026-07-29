# gitapex's own worked examples

Explicitly repository-scoped, per this skill's own Portability declaration
(`metadata/gitapex.yaml`: `portability: Mixed`). Every path and issue number
below is gitapex's own -- an illustrative example of the portable precondition
and five criteria in `SKILL.md`, not an assumption that a target repository
being reviewed has the same layout. Substitute the target's actual
equivalents; do not expect these specific files to exist elsewhere.

## Contents

1. [Worked example: a real, already-disclosed target (worktree lifecycle)](#worked-example-a-real-already-disclosed-target-worktree-lifecycle)
2. [Worked example: a synthetic target (burn-rate release gate)](#worked-example-a-synthetic-target-burn-rate-release-gate)

## Worked example: a real, already-disclosed target (worktree lifecycle)

Found during this skill's own scoping discussion (recorded in this
skill's own `metadata/gitapex.yaml` sidecar, per this skill's own
no-bare-citation rule for body prose), not invented for this file.
`skills/executing-a-branch-plan/references/execution-and-dispatch.md`
discloses, in its own text:

> "Open item, not resolved here: the Workflow tool's own documented
> behavior states a worktree is 'auto-removed if unchanged'; it does not
> state what happens to a worktree that DID accumulate changes... after
> its own merge-back completes."

Walking this skill's own precondition and five criteria against the
question this sentence raises (does a per-task git worktree's own
lifecycle stay bounded across a multi-wave dispatch run):

**Precondition: cannot-be-assessed, not a clean clear.** The worktree is
state that persists beyond its own triggering event (one task's
`agent()` call). But confirming the precondition requires reading "the
target decision's actual source" (SKILL.md's own check 1/2 wording) --
and the Workflow tool's own worktree-cleanup implementation is not
present anywhere in this repository and is not otherwise reachable from
a review session. `execution-and-dispatch.md` line 83 only quotes the
tool's *documented* behavior ("the worktree is auto-removed if
unchanged"), never its actual implementation source, and the specific
scenario this example asks about -- a worktree that *did* accumulate
changes, post-merge-back -- is explicitly disclosed by the target itself
as undocumented ("it does not state what happens to a worktree that DID
accumulate changes... after its own merge-back completes"). SKILL.md's
own check 1 requires confirming this "by reading the decision's actual
source for state reads -- never by the absence of a mention in its
documentation"; that read is not possible here, and neither of check
0/1/2's own named outcomes cleanly fits "the source is inaccessible and
the specific case is admittedly undocumented." Correct verdict: report
this precondition state as cannot-be-assessed rather than force it into
either a "clears" or "routes to criterion 6" bucket that presupposes a
read this example cannot actually perform -- and carry that disposition
into the five criteria below by grading each independently on its own
available evidence, not by copying one verdict onto all five.

**Criterion 1 (state provenance/trust): cannot-be-assessed.** Would
require knowing what state the (undocumented) cleanup decision reads and
who can write it. Only a documentation sentence is available, not the
Workflow tool's own implementation -- exactly the "opaque agent-harness/
tool-held state" case SKILL.md's own domain notes for this criterion
already describe: "the server's own held state is the longest-lived and least
visible of the four domains to a repository-side reviewer; an inability
to inspect it is itself a finding under criterion 3, not a reason to
skip this one" (SKILL.md names this for the MCP-server domain; the same
opacity applies here to the Workflow tool's own internals).

**Criterion 2 (cold-start/absence): cannot-be-assessed.** No source, no
documentation, and no live test -- this worked example did not execute a
real multi-wave Workflow dispatch with `isolation: 'worktree'` against
live git state, since doing so would leave real side effects outside a
safe, disposable scope for a documentation-only review. No citable
evidence exists either way.

**Criterion 3 (replay/reproducibility): cannot-be-assessed, with one
adjacent, citable negative fact.** `execution-and-dispatch.md` gives a
closed, enumerated list of what the main thread actually logs per task:
`TaskStarted`/`TaskCompleted`/`TaskFailed`/`NeedsInput`. No
worktree-lifecycle/cleanup event appears in that enumeration -- direct
textual evidence that *if* a worktree-cleanup decision exists, its
outcome is not part of the documented event-log schema. This stops short
of a formal FAIL on the cleanup decision itself, since the precondition
never confirmed that decision exists or reads state at all (per SKILL.md's
own "never claim a violation the target does not actually show").

**Criterion 4 (bounded growth): cannot-be-assessed.** This is the
criterion closest to the literal question the disclosed open item raises.
The source itself discloses the case as unverified, not resolved either
way -- it neither claims boundedness nor claims unbounded growth, only
that it must be checked against real runtime behavior. SKILL.md's own
Stop boundary is directly on point: where live-testing is genuinely not
possible, mark the point indeterminate rather than accepting the
unverified claim at full confidence. No live test was run for this
worked example, so the correct verdict is cannot-be-assessed, not FAIL --
grading it FAIL would overclaim a violation ("unbounded") the source does
not actually assert, and would invent a verdict label ("FAIL, live-tested
required, not yet performed") outside SKILL.md's own defined vocabulary
(PASS / FAIL / not-applicable / cannot-be-assessed / check-0's
indeterminate) -- an earlier draft of this worked example made exactly
that mistake, corrected here.

**Criterion 5 (blocking-posture justification): not-applicable.** This
criterion's own scope is explicitly restricted to "aggregate and noisy"
signals -- a trend, a rate, a rolling average. A worktree's cleanup state
is a discrete, binary fact (present/absent, changed/unchanged at a point
in time), not an aggregate noisy signal -- a clean not-applicable,
citable directly from the criterion's own stated scope, independent of
the precondition question above.

**Takeaway.** Applying this skill to a real target already in this
repository, without inventing a synthetic one, surfaces a genuine
limitation this skill's own discipline is built to name rather than
paper over: the target decision's actual source is inaccessible, so
every criterion resolves to cannot-be-assessed or not-applicable, never
a guessed PASS or an overclaimed FAIL. No criterion was rubber-stamped
identically -- each verdict rests on distinct, cited evidence, and
criterion 3 offers one adjacent, citable fact without converting it into
a verdict on a decision whose existence was never confirmed. This is a
stronger demonstration of the skill's own "cannot-be-assessed" discipline
than a forced pass/fail would be, consistent with
`evaluating-deterministic-gate-quality`'s own worked-examples file
finding a real, unresolved gap the first time it was smoke-tested
against a real gate, not staged for this record.

## Worked example: a synthetic target (burn-rate release gate)

Illustrative only -- not a gitapex artifact, and no verdict below rests on
live execution unless stated otherwise. Target: `gate_error_budget.py`, a
hypothetical Domain-3 required CI check on a service repository's deploy
PRs. It fetches the last 30 days of incident-minutes from a metrics
service, fits a linear burn rate, and exits non-zero when the fit projects
quarterly error-budget exhaustion within 14 days.

**Precondition:** decision reads the triggering event's payload (the PR)
plus a 30-day metrics window -- state beyond the triggering event.
Capturable if the workflow uploads the fetched window as a run artifact;
assume it does for this example. Clears the precondition.

**Criterion 1 (state provenance/trust): FAIL.** The metrics service
accepts writes from the same deploy credentials the gate constrains; a
deployer can retroactively edit incident-minutes to unblock their own PR
-- cite the service's own ACL as the evidence for this finding.

**Criterion 2 (cold-start/absence): would FAIL if built as described --
illustrative reasoning only, not live-tested.** This hypothetical script
does not exist in this repository and was not written or executed; per
SKILL.md's own Stop boundaries, a real application of this skill must
actually construct and run the synthetic empty-store case against the
real artifact, not reason about it abstractly the way this illustrative
walkthrough does. Reasoning through the design as described: pointed at
an empty synthetic metrics store, a `fit()` returning `None` and a guard
shaped like `if estimate and estimate < 14` would fall through to exit 0
-- a brand-new service would deploy ungated. If real, this would be the
same fail-open shape `evaluating-deterministic-gate-quality`'s own
worked-examples file records for a different gate's dimension-15
finding, live-tested there against the actual shipped script -- a bar
this illustrative example does not clear and does not claim to.

**Criterion 3 (replay/reproducibility): PASS.** The uploaded window
artifact lets a reviewer re-run the script against the exact snapshot
behind a given decision and reproduce the same deny/allow outcome --
`evaluating-deterministic-gate-quality`'s own dimension 10 claim about
this gate is therefore live-testable, not indeterminate.

**Criterion 4 (bounded growth): PASS.** The fetched window is hard-capped
at 30 days; the state does not grow unbounded across repeated runs.

**Criterion 5 (blocking-posture justification): PASS, cited.** The
script's own docstring argues blocking (not advisory) placement by citing
the team's own SRE policy and explicitly naming the tension with
`evaluating-deterministic-gate-quality`'s own Domain placement criterion
6 -- an argued, not accidental, choice.

**Takeaway.** Criterion 1 (FAIL) and criterion 2 (would-FAIL,
illustrative) are independent findings -- neither excuses the other, and
neither is excused by the three PASSes on criteria 3, 4, and 5, matching
this skill's own Procedure step 4 ("a criterion failing does not
automatically fail the others -- report each independently"). Only
criterion 1's FAIL, criterion 3's PASS, criterion 4's PASS, and criterion
5's PASS rest on this example's own stated design facts (who can write
the metrics store; whether the window is uploaded; the hard 30-day cap;
the docstring's own citation) -- criterion 2 alone is reasoning about
what a real live test would show, not a substitute for running one.

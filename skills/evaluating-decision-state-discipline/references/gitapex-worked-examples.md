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

**Precondition.** The worktree is state that persists beyond its own
triggering event (one task's `agent()` call) -- it is created before that
call and, per the open item above, its post-merge-back fate is not yet
documented. Whether it is capturable (its existence and disk footprint
can be observed at a given moment via `git worktree list` and the
filesystem) holds in principle, so this artifact clears the precondition:
gate material with state beyond the triggering event, capturable state.
This routes it to this skill's five criteria rather than to
`evaluating-deterministic-gate-quality`'s own Domain-placement criterion
6 -- the signal here is not aggregate/noisy, it is one worktree's own
disk lifecycle.

**Criterion 1 (state provenance/trust):** not-applicable as stated -- the
worktree's own filesystem state is written by the same dispatch mechanism
the review would be grading (the Workflow tool's own `isolation:
'worktree'` runtime), not by an actor the decision is meant to constrain.
No adversarial-writer concern applies here the way it would to, say, a
metrics store a rate-limited caller could also edit.

**Criterion 2 (cold-start/absence):** not directly applicable to this
specific artifact -- a worktree's own creation is the *first* use of that
state, not a read against a possibly-absent prior state the way a cache
or counter would be. (A different question -- what happens if worktree
*creation itself* fails mid-dispatch -- is a real question but belongs to
`executing-a-branch-plan`'s own failure-dispatch table, not this
criterion.)

**Criterion 3 (replay/reproducibility):** cannot be assessed from the
source material available -- `execution-and-dispatch.md`'s own text
states plainly that post-merge-back worktree disposition is undocumented,
so there is no snapshot or recording mechanism to check for. This is
exactly the honest "cannot be assessed" verdict this skill's Procedure
step 3 requires rather than a guessed PASS or FAIL.

**Criterion 4 (bounded growth): FAIL, live-tested is required, not yet
performed here.** This is the criterion the disclosed open item most
directly names. Grading it to completion would require running a real
multi-wave dispatch with `isolation: 'worktree'`, observing whether
`.claude/worktrees/agent-<id>/` directories persist or disk-fill after
their own task's merge-back, and citing that live result -- exactly the
live-testing discipline this skill's own Stop boundaries require rather
than accepting the open item's own disclosure as sufficient evidence on
its own. This worked example stops at "FAIL pending live verification,"
not a completed grade, and is recorded here as such rather than
overclaiming a live-tested result that was not actually gathered for this
file.

**Criterion 5 (blocking-posture justification):** not-applicable -- there
is no aggregate/noisy signal here to route toward advisory-vs-blocking
placement; this criterion only engages for a state-coupled signal like a
trend or rate.

**Takeaway.** Applying this skill to a real target already in this
repository, without inventing a synthetic one, surfaces a genuine,
still-open verification gap (criterion 4) rather than a clean pass --
consistent with `evaluating-deterministic-gate-quality`'s own worked-
examples file finding a real bug the first time it was smoke-tested
against a real gate, not staged for this record.

## Worked example: a synthetic target (burn-rate release gate)

Illustrative only -- not a gitapex artifact. Target: `gate_error_budget.py`,
a hypothetical Domain-3 required CI check on a service repository's deploy
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

**Criterion 2 (cold-start/absence): FAIL, live-tested.** Pointed at an
empty synthetic metrics store, the script's `fit()` returns `None`, and
the guard `if estimate and estimate < 14` falls through to exit 0 -- a
brand-new service deploys ungated. This is the same fail-open shape
`evaluating-deterministic-gate-quality`'s own worked-examples file
records for a different gate's dimension-15 finding, applied here to a
state-coupled decision's own cold-start path specifically.

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
`evaluating-deterministic-gate-quality`'s own Domain-placement criterion
6 -- an argued, not accidental, choice.

**Takeaway.** The two FAILs (criteria 1 and 2) are independent findings --
neither excuses the other, and neither is excused by the two PASSes on
criteria 3 and 5, matching this skill's own Procedure step 4 ("a
criterion failing does not automatically fail the others -- report each
independently").

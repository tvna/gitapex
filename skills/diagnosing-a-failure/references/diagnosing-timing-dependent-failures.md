# Diagnosing Timing-Dependent Failures

Supports Step 6 (`SKILL.md`) -- what to check before accepting "it's a
race condition" or "it's flaky" as a hypothesis. This skill investigates
failures, it does not author fixes, so the guidance below is what to
*check*, not what to *write*.

## Core principle

An intermittent failure is usually not actually random -- it is a symptom
that some part of the system is waiting on a fixed delay instead of on
the actual condition it needs. Before treating "timing" as confirmed,
check whether the observed failure is consistent with a guessed-delay
pattern rather than a genuine race.

## What to check

1. **Is there an arbitrary delay anywhere upstream of the failure** (a
   `sleep`, `setTimeout`, or fixed-duration wait) standing in for "wait
   until X is true"? If so, the failure's intermittency likely tracks
   machine load or CI contention, not true nondeterminism -- this is a
   strong, cheap-to-check signal before deeper hypothesis work.
2. **Does the failure rate correlate with load** (fails more under CI
   parallelism, passes reliably alone)? Consistent with a fixed-delay
   race; inconsistent with it points elsewhere.
3. **Is a stale read plausible** -- was a value captured once before a
   loop or retry, rather than re-fetched each attempt? A cached read
   masquerades as a timing failure but is actually a logic bug.
4. **Does the system have a real condition it could wait on instead**
   (an event, a state flag, a file's existence, a response body)? If a
   genuine condition exists and nothing waits on it, that is itself
   diagnostic: the fix is a caller problem (wrong wait strategy), not
   evidence the underlying operation is nondeterministic.

## What this step does not do

Distinguishing "testing timing behavior itself" (a debounce interval, a
throttle window) from "guessing at unrelated timing" is a judgment call
this step surfaces, not resolves on the caller's behalf -- a
Step 8 `root-cause-confirmed` Verdict names which case applies and lets
the actual fix (a real wait-for-condition pattern, or leaving a
documented, justified fixed delay in place for genuine timing behavior)
stay the caller's own job.

## Probe design for Step 6/7

A falsifiable probe for a timing hypothesis: reproduce with an
artificially widened window (if a race exists, widening the window past
the guessed delay should make the failure reproduce *more* reliably, not
less) or an artificially narrowed one (should fail *faster and more
consistently* if the hypothesis is right). A hypothesis that shows no
sensitivity to either change is evidence against a timing cause, not for
it -- exactly the disconfirmation Step 7 requires before a timing-based
`root-cause-confirmed` Verdict is issued.

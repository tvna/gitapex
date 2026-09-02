# Failure and Recovery

Step 7's own failure-dispatch table, plus every portion of the
domain-event mechanism (`events-and-review-gate.md`, Decision 8) that is
read only on a failure, a stale run, or a resumed session reconciling
what actually happened -- never on an ordinary clean run where every task
completes, no gap, no hang, and no plan-level challenge arises. Split out
of `events-and-review-gate.md` per
`evaluating-skill-quality/references/rubric.md`'s Dimension 5 (detail read
on every use belongs inlined in `SKILL.md`; detail an ordinary run never
reads should not force that same every-run file open too). Source: design
doc Decision 8 (unifies failure/deviation semantics and durable
cross-session resume into one mechanism), Decision 18 (rollback).

See [events-and-review-gate.md](events-and-review-gate.md) for where the
Execution log lives, the read-modify-write discipline every write to it
follows, and the closed event vocabulary this file's own dispatch and
recovery logic writes into.

## Contents

- [Loss and absence handling](#loss-and-absence-handling)
- [Freshness and hang detection](#freshness-and-hang-detection)
- [Failure dispatch](#failure-dispatch-step-7)
- [Rollback](#rollback-offered-not-automatic)

## Failure, loss, and resume handling

### Loss and absence handling

A missing, truncated, or unparseable `## Execution log` section -- the PR
body fetch fails outright, the section heading is not found, or the found
section's text does not parse into the closed event vocabulary above --
must fail loud. **Never treat any of these three as evidence that no
tasks completed, and never silently restart the Branch Plan from step 3
as if this were a fresh run.** A log that cannot be read is not a log that
says "nothing happened" -- it is an absence of information about what
happened, and the two are not interchangeable: the branch itself may
already carry completed, pushed task commits the missing log simply
failed to record.

All three loss modes end at the same place -- a human-facing escalation
via `drafting-a-pr-to-merge`'s own Step 11 (escalate to the owner) --
this skill's own sequence stops at step 9, so the escalate-to-the-owner
channel is that skill's, the same one the Failure dispatch section below
already cites. All three also release the `branch-plan-executing` label
last, after whichever of the below each loss mode allows, per the
`StageDeviated` event vocabulary entry's own ordering rule -- the label
release is its own API call, independent of whether the body itself is
readable at all, so it is attempted even under the first bullet below.
They differ only in whether a `StageDeviated{run_id, task_id: null,
reason, action: escalate}` event can also be recorded before that
escalation happens:

- **Body fetch fails outright** -- nothing is writable; escalate directly
  with no event write attempted.
- **Section heading not found** in an otherwise-fetchable body -- the
  write path still works, so use the read-modify-write discipline above
  to append a freshly-seeded `## Execution log` heading plus this one
  event, then escalate -- do not treat the missing heading as unwritable
  just because it is not the truncated/unparseable case below.
- **Section found but truncated or unparseable** -- use the same
  read-modify-write discipline to append the event after the existing
  (garbled) section text, without attempting to repair or discard that
  existing text, then escalate -- recording the escalation does not
  require first making sense of what is already there.

Before escalating, attempt the one recovery step ground truth already
supports: read the branch's own commit history (`git log` on the shared
branch) to check whether task commits exist despite the log's own loss,
the same "trust the ground truth over your own record" precedence this
skill's resume path already applies. Report what that check found (some
commits exist / none exist / history itself could not be read) as part
of the escalation, rather than leaving the human to re-derive it.

### Freshness and hang detection

**This check catches a run that died silently, not a live wave that is
simply taking a while.** Step 6 writes every one of a wave's events
(`TaskStarted`/`TaskCompleted`/`TaskFailed`/`NeedsInput`) in a single
batch, in the main thread, only *after* that wave's Workflow run returns
-- never incrementally while the wave is in flight. A live session that
dispatched a wave and is waiting on the `Workflow` tool's own async
completion notification (or, in the sequential fallback, executing a
task turn by turn) is blocked on that wave's own return, not polling the
Execution log -- a wave with several tasks can legitimately run for hours
with zero new events, and that session must not apply this check against
its own outstanding dispatch, since every healthy wave would eventually
read as "hung" under any polling-while-waiting reading of this section.

Apply this check only where no live session can already vouch for the
run's own progress: a session resuming this run after an interruption (a
restart, a handoff, a fresh session picking the branch back up) has no
such live memory and must not assume a wave it does not itself remember
dispatching is still actually running, before it dispatches anything new.

At that point: re-read the Execution log (the same re-screen-before-
trusting discipline this skill's own cross-session resume path already
applies to the log's *content*, applied here to its *cadence*). If this
run's own `run_id` has no event newer than roughly 3x
`drafting-a-pr-to-merge`'s own Step 10 fallback self-check-in cadence
(i.e., no new event in roughly the last 3 hours), do not declare hung yet
-- first corroborate against ground truth the same way Loss and absence
handling above already does: read the branch's own commit history for a
commit newer than that same threshold. A wave's push and its log write
happen together (step 6), so a healthy run should show both or neither;
a recent commit with no matching log entry means the run is still making
real progress and simply has not (yet, or due to a partial failure)
logged it -- do not declare hung in that case; re-arm this same check on
the next scheduled check-in (the same roughly-hourly cadence above) rather
than deciding anything now. Only
when *both* the log and the commit history are stale past the threshold,
treat the run as hung: write a `StageDeviated{run_id, task_id: <outstanding
wave's task ID(s), if known>, reason: "no event or commit in over 3x the
check-in cadence, no live session confirmed", action: escalate}` event
using the read-modify-write discipline above, escalate per
`drafting-a-pr-to-merge`'s own Step 11 (the same channel the Loss and
absence handling section above uses), then release the
`branch-plan-executing` label last, per the `StageDeviated` entry above's
own ordering rule -- never silently keep
waiting past that threshold once both signals agree, and never re-dispatch
the same wave as if the hang were a normal failure this skill's one-retry
budget already covers (a hung dispatch never returned a result to retry
against). This corroboration step exists precisely because releasing the
label on a false positive re-opens the PR to concurrent access from
`drafting-a-pr-to-merge` while the original run may still be pushing to
it -- a live-but-slow run misdiagnosed as hung is a worse outcome than
waiting a while longer.

**Residual risk this does not close:** a run that dies with no session
ever resuming it (no restart, no handoff, no fresh pickup) leaves the
label standing with nothing left to apply this check at all --
`drafting-a-pr-to-merge`'s own step 2 has no independent way to tell a
genuinely-dead run from a live one still mid-wave, and that skill's own
change stays scoped to the bare label-presence check alone, deliberately
not a second freshness mechanism grafted onto it. A human noticing a
stalled PR and removing the label by hand remains the recovery path for
this specific case; it is named here rather than assumed away. A second,
narrower residual risk sits underneath the corroboration step above: no
event is ever written when a wave is *dispatched*, only after it
*returns*, so "wave N+1 has simply never been dispatched yet" (a benign
gap after a prior session's turn ended, nobody has picked the branch back
up, and neither the log nor the branch has moved since) is indistinguishable
from "wave N+1 was dispatched and died with zero progress" by log/commit
staleness alone -- both read identically stale. The corroboration step
narrows the false-positive window (a live-but-slow wave that has pushed
recently still gets caught) but cannot close this specific case, since
there is nothing to corroborate against either way; a resumed session
misjudging a merely-unpicked-up branch as hung pays the same cost as a
false positive above (an unnecessary escalation and label release), not
a worse one -- it is disclosed here for the same reason.

### Failure dispatch (step 7)

A task's own proof method failing writes a `TaskFailed{run_id, task_id,
reason}` event, then triggers exactly one retry, with the failure output folded
into the retried task's own context -- bounded, not an open loop. If the
retry succeeds, write `TaskCompleted` as normal; no further event is
needed. If the retry also fails, dispatch on what actually failed:

- **The plan was wrong** (this task's own Interpretation/Planned ops does
  not fit what the ACM row actually needed) -> `stop-and-replan`'s own
  Stop action, extended to a new trigger beyond that skill's original
  self-correcting-phrase detection: a task's own retry-then-plan-wrong
  diagnosis. In order: write a `StageDeviated{run_id, task_id, reason,
  action: stop-and-replan}` event, comment the rationale on the parent
  issue (offering the rollback below in that same comment), close the
  draft PR, then release the `branch-plan-executing` label last, per the
  `StageDeviated` event vocabulary entry above's own ordering rule.
- **The execution was wrong but the fix is not obvious** -> escalate:
  write a `StageDeviated{run_id, task_id, reason, action: escalate}`
  event, post a comment on the (still draft) PR naming exactly what was
  tried, escalate per `drafting-a-pr-to-merge`'s own Step 11 -- matching
  that step's own "escalate only when blocked... not for anything the
  agent can fix on its own" -- then release the `branch-plan-executing`
  label last, same ordering rule.
- **`NeedsInput`** -> answer from the ACM/Branch Plan's own already-stated
  content when possible; escalate per the rule above when the ACM itself
  does not settle it. Never counted against the one-retry budget.
- **A screening flag (per the threat-model reference) or a declined
  irreversible-task confirmation** -> escalate, same as an unobvious
  execution failure -- these are not proof-method failures and get no
  retry at all.
- **An upstream-ambiguity-rooted finding, originating from a
  `drafting-a-skill` task** -> escalate, but with a narrower human-facing
  instruction than the ordinary "execution was wrong" case above.
  `drafting-a-skill`'s own Step 7 already distinguishes this case from an
  ordinary drafting defect: when `evaluating-skill-quality` or
  `battle-testing-a-skill` finds a real problem rooted in the *upstream*
  Agentic operation mechanism-fit vehicle-selection call or one of the four elicited axes
  (`eliciting-a-design`'s own resolution, not anything `drafting-a-skill`'s
  own Steps produced), that task cannot fix it in place -- it has no
  interactive-dialogue tooling to re-open `eliciting-a-design` from its
  own isolated `branch-plan-task` dispatch -- so it emits
  `StageDeviated{run_id, task_id, reason, action: escalate}` itself,
  naming the specific upstream call in question. This skill's own step 7
  recognizes that reason text (rather than re-deriving whether the
  finding is upstream-rooted itself, which is `drafting-a-skill`'s own
  judgment to make, not this skill's to second-guess) and, in the
  escalation comment, names **"return to `eliciting-a-design`"** as the
  legitimate response: whoever picks up the escalation re-runs that
  design dialogue (Checklist item 4, "Agentic operation mechanism-fit and
  metadata elicitation") for the specific axis or vehicle-selection call
  named, producing a corrected ACM row before this Branch Plan resumes --
  never a silent local override of the elicited metadata, and never a
  same-task retry against the one-retry budget above, since retrying the
  drafting task again would only reproduce the same upstream-rooted
  finding.

### Rollback (offered, not automatic)

When `stop-and-replan` fires, before closing the draft PR: offer, via the
escalation comment already being written, a revert of every
`TaskCompleted` commit carrying the *current* `run_id` -- not every
`TaskCompleted` in the log -- back to that same run's own step-4
task-list-file commit, which is the `run_id` value itself. That commit is
the branch's own first commit only while this is the branch's only run;
once a re-run has published a second task-list commit onto the same
branch, reverting to the branch's *first* commit would also undo an
earlier run's work this `stop-and-replan` never covered. The Execution
log's own `commit_sha` values, filtered to that same `run_id`, are the
dependency-ordered manifest. This is offered, not automatic -- matching
this repository's own "keep confirmations for any irreversible
operation" rule, since a revert is itself a git history change on a
branch a human may already be inspecting. No new artifact is required:
the Execution log's own `TaskCompleted{run_id, commit_sha}` events
already are the manifest a revert needs.

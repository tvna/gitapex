# Domain Events and Failure Handling

Steps 5 and 7's own detail. Source: design doc Decision 8 (unifies
failure/deviation semantics and durable cross-session resume into one
mechanism), Decision 18 (rollback), Decision 19 (the `NeedsInput` event).

## Where the log lives

The PR body, in a `## Execution log` section -- not a new file, not
`implementation-notes` (a diagram label only, not an established
file/convention anywhere in this repository). This matches two
already-shipped precedents in this repository: the Acceptance Criteria
Map already lives in the PR body (`issue-to-branch` step 8), and the
`## Skill audit evidence` section already lives there too. The PR body is
also already the artifact `driving-pr-to-merge` reads, so no second file
needs to be kept in sync with the PR at handoff time, and cross-session
resume becomes a direct read: a fresh session reopening the same PR calls
`github:pull_request_read` method `get`/`get_comments` and reads the
Execution log to know exactly which tasks completed, which failed, and
where to resume.

## Event vocabulary (closed set, append-only, one line per event)

- `PlanApproved` -- written at step 5, when the draft PR opens.
- `TaskStarted{task_id}`
- `TaskCompleted{task_id, commit_sha}`
- `TaskFailed{task_id, reason}`
- `NeedsInput{task_id, question}` -- distinct from `TaskFailed`: a task
  requesting missing information, answered from the ACM/Branch Plan's own
  content when possible or escalated when not. Does not consume the
  one-retry budget below, since asking for missing context is not the
  same event as an attempt that ran and failed.
- `StageDeviated{task_id, reason, action}` where `action` is one of
  `retry` / `stop-and-replan` / `escalate`.

## Failure dispatch (step 7)

A task's own proof method failing triggers exactly one retry, with the
failure output folded into the retried task's own context -- bounded, not
an open loop. If the retry also fails, dispatch on what actually failed:

- **The plan was wrong** (this task's own Interpretation/Planned ops does
  not fit what the ACM row actually needed) -> `stop-and-replan`'s own
  Stop action, extended to a new trigger beyond that skill's original
  self-correcting-phrase detection: a task's own retry-then-plan-wrong
  diagnosis. Close the draft PR with a `StageDeviated{action:
  stop-and-replan}` event and rationale, comment the same rationale on
  the parent issue, re-plan from there. Before closing, offer the
  rollback below.
- **The execution was wrong but the fix is not obvious** -> escalate: a
  `StageDeviated{action: escalate}` event, plus a comment on the (still
  draft) PR naming exactly what was tried -- matching `driving-pr-to-
  merge`'s own "escalate only when blocked... not for anything the agent
  can fix on its own."
- **`NeedsInput`** -> answer from the ACM/Branch Plan's own already-stated
  content when possible; escalate per the rule above when the ACM itself
  does not settle it. Never counted against the one-retry budget.
- **A screening flag (per the threat-model reference) or a declined
  irreversible-task confirmation** -> escalate, same as an unobvious
  execution failure -- these are not proof-method failures and get no
  retry at all.

## Rollback (offered, not automatic)

When `stop-and-replan` fires, before closing the draft PR: offer, via the
escalation comment already being written, a revert of every
`TaskCompleted` commit back to the branch's own first commit (the step-4
task-list-file commit), using the Execution log's own `commit_sha` values
as the dependency-ordered manifest. This is offered, not automatic --
matching this repository's own "keep confirmations for any irreversible
operation" rule, since a revert is itself a git history change on a
branch a human may already be inspecting. No new artifact is required:
the Execution log's own `TaskCompleted{commit_sha}` events already are
the manifest a revert needs.

## Draft-PR-first pattern (step 5)

The draft PR opens immediately once the step-1 authorization gate passes
(not after every task commits), containing the ACM and an Execution log
seeded with `PlanApproved`. This skill subscribes to the draft PR's own
CI/review/comment activity at this same moment and owns responding to it
for the entire task-execution window -- it does not wait for or delegate
to `driving-pr-to-merge` during that window. The draft PR converts to
ready-for-review only once every task has a `TaskCompleted` event and the
refactor/adversarial-review gate (step 8) is clean, at which point
ownership of its activity passes to `driving-pr-to-merge`'s normal entry
point.

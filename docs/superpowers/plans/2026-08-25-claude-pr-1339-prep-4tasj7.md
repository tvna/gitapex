# Implement Axis 2/4/6 state-management fixes for the Execution log

**Goal:** `executing-a-branch-plan`'s own Execution log (the append-only
Domain-Events log kept inside the PR body) fails
`skills/evaluating-skill-quality/references/state-management-quality.md`'s
Axis 2 (identity/scope binding), Axis 4 (write discipline), and Axis 6
(loss/absence handling, the leading gap) -- confirmed by that framework's
own "Worked example that fires" section, which is modeled directly on
this file (pinned revision `4c17391`, cited as `[ebp]`). Implement the
five already-designed fixes: a run/attempt identifier, an explicit
read-modify-write discipline for the PR-body write, a fail-loud escalation
rule for a missing/truncated/unparseable log, a `branch-plan-executing`
ownership-signal label, and a freshness-based hang-detection rule.
Source: https://github.com/tvna/gitapex/issues/1339.

**Authorization record:** No approving comment exists on issue #1339
(checked via `github:issue_read` method `get_comments`, empty result --
the issue was opened moments before this session started, by the
repository owner). Branch 2 of the Authorization gate applies instead:
the active human operator's own opening turn in this session explicitly
instructed executing issue #1339 through to just-before-merge
("こちらのPRを作りマージ直前まで進める" -- create this PR, proceed to just
before merge). This is a fresh, explicit, in-session confirmation for
this specific issue's execution, not a self-reported claim of prior
approval. The structural precondition
(`gitapex_check_branch_plan_reverified.py` against the issue's own body)
also PASSes: `planning-a-branch-from-an-issue` wrote its re-verification
marker (`Re-verified: \`planning-a-branch-from-an-issue\`
(2026-08-25T22:23:57Z)`) onto issue #1339 earlier this session.

**Threat-model triage (step 2):** Issue #1339's ACM was read in full. All
five Planned-ops cells describe file edits to specific, already-identified
files (`domain-events-and-failure-handling.md`, two `SKILL.md` files); none
contains an embedded instruction, encoded/obfuscated payload, or attempt to
redirect this skill's own process. Clean -- no row flagged.

**Design values fixed at this decomposition step** (issue #1339's own
Constraints leave these to implementation time):

- Run/attempt identifier: the step-4 task-list-file commit SHA (short
  form), already recorded as ground truth at branch-publish time -- no new
  random/UUID mechanism, satisfying the state-minimality lens's
  re-derivability question (Q1) since it is derived from `git log`, not
  freshly generated.
- Hang-detection threshold: 3 consecutive polls with no new Execution-log
  event -> treat the run as hung, escalate. Polling cadence: the same
  "roughly hourly" cadence `drafting-a-pr-to-merge` Step 10 already
  documents for its own fallback self-check-in, reused rather than
  inventing a second cadence.

**Architecture:** Three prose-only `SKILL.md`/reference-file edits, no new
files, no code, no tests (this is a documentation/skill-definition fix
with no runtime dependency, per issue #1339's own Environment section).

- `skills/executing-a-branch-plan/references/domain-events-and-failure-handling.md`:
  four edits --
  1. Event vocabulary section: add a run/attempt identifier field (the
     step-4 task-list commit SHA, short form) to every event in the closed
     vocabulary.
  2. "Where the log lives" section: add an explicit fetch -> append ->
     write-back procedure for the PR-body write, naming the hazard a naive
     whole-body overwrite would cause (destroying content this run did not
     author).
  3. New escalation rule, wired to the existing closed
     `StageDeviated{action: escalate}` vocabulary (not a new event type):
     a missing, truncated, or unparseable Execution log section fails loud
     and escalates, never silently reads as zero progress.
  4. New freshness-based hang-detection rule: 3 consecutive polls with no
     new event -> `StageDeviated{action: escalate}`, reusing Axis 3's
     freshness/re-read reasoning, cadence per the Design-values note above.
- `skills/executing-a-branch-plan/SKILL.md`: Step 5 gains a
  `branch-plan-executing` label-grant (applied when the draft PR opens);
  Step 9 gains the corresponding label-release (applied when the PR is
  marked ready for review). No other step text changes.
- `skills/drafting-a-pr-to-merge/SKILL.md`: the Step 7 `"draft"` branch
  gains one label-presence check (`branch-plan-executing` still applied ->
  execution is still in flight elsewhere, defer rather than entering this
  skill's own fix loop) before the existing `mergeable`/`get_check_runs`/
  `get_reviews` checks. Scoped to this one check only -- no other behavior
  in that skill changes, per issue #1339's own Constraints.

**File-ownership map:** Task A owns
`skills/executing-a-branch-plan/references/domain-events-and-failure-handling.md`
only. Task B owns `skills/executing-a-branch-plan/SKILL.md` only. Task C
owns `skills/drafting-a-pr-to-merge/SKILL.md` only. No shared file between
any two tasks.

**Interface-dependency map:** None of the three tasks' Planned ops names a
producer/consumer relationship with either of the others -- all three
reference the same fixed label name (`branch-plan-executing`) and the same
fixed event name (`StageDeviated{action: escalate}`), both already settled
by this decomposition step above rather than generated by any one task's
own execution. No edge between any pair.

**Wave assignment:** Wave 1: {Task A, Task B, Task C} -- no file or
interface edge between any pair.

**Irreversibility classification:** All three tasks are additive prose
edits to already-committed, already-reviewed skill files on a fresh
feature branch, fully reversible by further edit or revert before merge.
None classified irreversible; no fresh per-task confirmation beyond the
Authorization gate above is required.

**Dispatch mode:** The `Workflow` tool's own access-control policy
requires explicit user opt-in for multi-agent orchestration (an
"ultracode" keyword, a session-level flag, or the user's own direct
request to use a workflow) before this skill's own step 6 primary path
(`Workflow` + `agentType: 'branch-plan-task'` + `isolation: 'worktree'`)
may be invoked. None of those opt-in conditions hold in this session --
the operator's own instruction never mentioned orchestration. Per this
skill's own step 6 fallback clause ("[u]se the sequential main-thread
fallback ... when the Workflow tool is unavailable"), this is treated as
exactly that case in the practical/policy sense: all three tasks execute
directly in the main thread, one per turn, no wave/run boundary, no
worktree isolation -- proportionate to a three-task, three-file,
prose-only plan regardless. Step 8's mandatory dual dispatch (refactor
pass + adversarial review) uses the `Agent` tool instead, which carries no
equivalent opt-in gate.

**Proof method:**

- Task A: direct read of the edited file confirms every event in the
  vocabulary carries the run/attempt-identifier field; the three-step
  write procedure and its overwrite-hazard note are both present; all
  three loss modes (missing/truncated/unparseable) each have a stated
  escalation path; the polling-based staleness rule and its escalation
  path are present.
- Task B: direct read confirms the Step 5 label-grant and Step 9
  label-release are both present and consistent (same label name, applied
  and released at the stated points, no other step text changed).
- Task C: direct read confirms the one label-presence check is present in
  the Step 7 `"draft"` branch, and that no other behavior in that file
  changed (diff review).
- Since two changed files are `SKILL.md`s, a disclosed skill-quality audit
  pass per `.github/scripts/gitapex_gate_skill_audit_disclosure.py`'s own
  requirement -- fresh-subagent `evaluating-skill-quality` dispatches
  against both modified `SKILL.md` files, scoped to the changed sections.
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  against both modified `SKILL.md` files.
- Regression: full `pytest` suite (no code changed, so no test regressions
  expected; run to confirm) and
  `.github/scripts/gitapex_gate_local_preflight.py`'s wired local gates.

## Execution log

- `PlanApproved` -- this plan, at branch publish (this commit).

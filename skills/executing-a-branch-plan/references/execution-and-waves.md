# Execution and Waves

Step 6's own detail. Source: design doc Decisions 4, 13, 16.

## Contents

- [Primary path: one Workflow run per wave](#primary-path-one-workflow-run-per-wave)
- [Git worktree isolation for parallel task execution](#git-worktree-isolation-for-parallel-task-execution)
- [Sequential fallback](#sequential-fallback)

## Primary path: one Workflow run per wave

The Workflow tool executes [task-decomposition.md](task-decomposition.md)'s
wave list when available. **One `Workflow` run per wave, not one
continuous run for the whole task list** -- the Workflow script itself
has no filesystem or shell access at all (it can only call
`agent()`/`pipeline()`/`parallel()` and read return values); a bare git
command or an `mcp__github__*` call cannot execute inside the script's
own code, only inside an `agent()` call. Screening, worktree merge-back,
and event-log writes must run in the actual main thread between waves,
not inside a script that cannot reach any of them.

Per wave: dispatch a Workflow run containing only that wave's
`pipeline()`/`parallel()` task `agent()` calls, each:

- `agentType: 'branch-plan-task'` -- the Decision 17 backstop subagent
  type (see
  [threat-model-and-authorization.md](threat-model-and-authorization.md#the-branch-plan-task-subagent-type)).
- `isolation: 'worktree'` when the wave has more than one task (see
  below); omit for a single-task wave, where isolation has no concurrent
  write to guard against.

The run returns each task's result to the main thread. The main thread
then, per task: screens the `BASE..HEAD` diff (task-decomposition.md's
own BASE convention), merges the worktree-isolated commit onto the
shared branch, **pushes the shared branch to the remote**, writes
`TaskStarted`/`TaskCompleted`/`TaskFailed`/`NeedsInput` events. Step 4's
own push publishes the branch initially; it is not the only push --
every wave's own merge-back is followed by its own push, so the draft
PR's diff and the Execution log's `commit_sha` references always point
at commits genuinely on the remote, not only what happens to be sitting
in the local working copy. The next wave's Workflow run dispatches only
once this settles, so its own tasks see every earlier wave's merged
state.

**Consent/portability note.** Each wave's own Workflow run triggers its
own launch-time approval prompt in default/accept-edits permission modes
(unless already recorded, or the session runs non-interactively). A
Branch Plan with many small waves multiplies this prompt count --
task-decomposition.md's own wave-minimizing effect (grouping everything
with no file or interface edge into one wave) is therefore also a
consent-friction control, not only a parallelism-maximizing one. This is
unverified in practice against a real multi-wave dispatch as of this
skill's authoring -- flagged for the first real run to measure, not
assumed low-friction.

## Git worktree isolation for parallel task execution

A file-ownership map prevents two parallel tasks from touching the same
*file*, but says nothing about the git-level race of two `agent()` calls
committing to the same branch/working directory concurrently -- a working
directory's index and HEAD are single, shared, mutable state, so
concurrent `git add`/`git commit`/`git status` is not safe even when the
files touched are disjoint.

Every task dispatched in a multi-task wave runs with `isolation:
'worktree'`, the Workflow tool's own documented mechanism for exactly
this case ("use ONLY when agents mutate files in parallel and would
otherwise conflict; the worktree is auto-removed if unchanged").
task-decomposition.md's own file-ownership map is what makes this
cost-justified -- a task that will not conflict on file *content* still
races at the git-*mechanics* level without isolation.

**Merge-back is a main-thread step, not delegated to the task agent.**
After a worktree-isolated task's own `agent()` call reports completion
(post-screening), the main thread merges that task's worktree commit onto
the shared feature branch published in step 4. Because the wave's own
file-disjointness already holds, this merge is conflict-free by
construction, not a merge requiring manual resolution -- it stays
main-thread-only because it still mutates the one shared branch multiple
parallel worktrees would each otherwise try to update concurrently.

Distinct from the `EnterWorktree`/`ExitWorktree` tool pair: those move
the whole interactive session into one worktree, gated by their own tool
description to fire only on explicit user/CLAUDE.md instruction. This
skill's own main-thread git operations (branch publish, merge-back) do
not call `EnterWorktree` by default.

**Open item, not resolved here:** the Workflow tool's own documented
behavior states a worktree is "auto-removed if unchanged"; it does not
state what happens to a worktree that DID accumulate changes (every task
worktree, by definition) after its own merge-back completes. Verify this
directly against the actual runtime behavior in the target deployment
before relying on automatic cleanup, rather than assuming it.

## Sequential fallback

Used when `CLAUDE_CODE_DISABLE_WORKFLOWS=1` is set, the Workflow tool is
otherwise unavailable, or the calling agent platform is not Claude Code
at all. Execute the same task list sequentially in the main thread, one
task per turn, same commit-per-task discipline, same event-log writes.
Degraded (no parallelism, no adversarial cross-check between independent
tasks, no `agentType`/worktree-isolation scoping -- a task's own
exclusion list is prompt-only in this path, not structurally enforced)
but not blocked. No wave/run boundary exists in this path at all -- there
is no concurrent write to isolate against, so applying worktree isolation
here would be unneeded complexity, not a missing safeguard.

What does not change between the two paths: the task list itself, the
step-1 authorization gate, the event log and PR handoff. Only the *how*
of running each task differs.

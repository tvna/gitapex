# Execution and Dispatch

Step 6's own detail. Source: design doc Decisions 4, 13, 16.

Renamed from "Execution and Waves" (found via `/code-review`): design doc
Decision 2/10 resolved "wave" as "not adopted as a named term; described
in prose only... never surfaces as a first-class term" -- a file titled
after the word, and a formal quoted definition once given for it
elsewhere in this skill, both formalized it past that resolution. Ordinary
lowercase "wave"/"per wave" usage below is unchanged, matching how the
design doc's own Decisions 3/4/13/16 use the identical word as plain
prose throughout -- that is the resolution's own intended shape, not a
violation of it.

## Contents

- [Primary path: one Workflow run per wave](#primary-path-one-workflow-run-per-wave)
- [Step 8's two dispatches](#step-8s-two-dispatches)
- [Git worktree isolation for parallel task execution](#git-worktree-isolation-for-parallel-task-execution)
- [Worktree-base precondition backstop](#worktree-base-precondition-backstop)
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
own launch-time approval prompt in default/accept-edits permission
modes, confirmed via a direct fetch of Claude Code's own primary
documentation (`code.claude.com/docs/en/workflows`, this skill's own
authoring session, not inherited from the design doc's earlier fetch
unverified): "Default, accept edits: **Every run**, unless you've
selected 'Yes, and don't ask again' for that workflow in this project."
A Branch Plan with many small waves multiplies this prompt count --
task-decomposition.md's own wave-minimizing effect (grouping everything
with no file or interface edge into one wave) is therefore also a
consent-friction control, not only a parallelism-maximizing one. The
*count* of prompts a real multi-wave dispatch produces, and whether that
count is acceptable in practice, is unverified -- flagged for the first
real run to measure, not assumed low-friction.

## Step 8's two dispatches

Step 8 (`refactor-and-review-gate.md`) reuses this same agent type and
its read-only sibling, not a per-wave dispatch: the refactor/simplify
pass dispatches with `agentType: 'branch-plan-task'` (that agent type's
own second sanctioned call site, per `agents/branch-plan-task.md`'s own
"Sanctioned call sites" section), and the adversarial code review
dispatches with `subagent_type: 'review-persona'` (`agents/review-
persona.md`'s own "Sanctioned call sites" section, entry 4). Step 8 is
"Not itself parallelized" (`refactor-and-review-gate.md`'s own term) --
a single dispatch each, run once after all waves complete, not per-wave
-- so neither needs `isolation: 'worktree'`, the same omission this
file's own primary-path section above already makes for a single-task
wave: no concurrent write exists for either dispatch to guard against.
What each dispatch does with its own turn, and how findings from the
review pass get fixed, stays `refactor-and-review-gate.md`'s own detail,
not duplicated here -- this section covers only the dispatch mechanics
this file's own subject matter already owns.

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

## Worktree-base precondition backstop

A wave's worktree is forked from the shared plan branch's own tip at
dispatch time (above); nothing previously re-checked, from inside that
worktree, whether the shared branch had since advanced past the
worktree's own fork point -- a concurrent sibling task's own wave merging
and pushing before this one returns, or a stale worktree reused across
waves, could both leave a task working from (and reporting complete
against) a base that no longer reflects the shared branch's own current
state. Issue `#1508` (consolidated into issue `#1566`'s own
gate-preconditions-mechanism umbrella) closes this:
`scripts/gitapex_check_task_worktree_base.py`, chained into
`check_task_bash_safety.sh`'s own existing `PreToolUse` "Bash" hook as a
second sibling classifier call (the identical pattern that script already
uses to invoke `gitapex_check_task_bash_safety.py`), re-asserts on every
Bash call that the shared plan branch's own current tip is still an
ancestor of the task's own worktree HEAD -- in git terms, that
`git merge-base HEAD SHARED_BRANCH` still equals `git rev-parse
SHARED_BRANCH`.

**Piggybacks on the task's own first Bash call, not a true "before any
tool call at all, including a non-Bash one" gate.** Claude Code has no
`SubagentStart`-equivalent hook event -- confirmed directly against Claude
Code's own hooks documentation (only `SubagentStop` exists, already used
for Decision 20's own exit condition below, a different purpose from a
PRE-dispatch check). The `branch-plan-task` agent type's own embedded
`PreToolUse` "Bash" hook is therefore the earliest deterministic
enforcement point actually available, so this backstop only fires once
the task issues its own FIRST Bash tool call -- any Read/Edit/Write/
Grep/Glob work a task does before its first Bash call is not covered by
it at all. This is an explicitly disclosed, asymmetric-strength residual,
matching this skill's own established disclosure convention (Decision
17's own two-variant asymmetry) rather than overclaiming full coverage;
see
[threat-model-and-authorization.md](threat-model-and-authorization.md#worktree-base-precondition-backstop)
for the full accounting.

**Resolving the shared plan branch's own name, without threading a new
value in from the main thread.** Nothing in this skill's own dispatch
mechanism today passes a task an explicit env var, a file, or any other
signal naming the shared plan branch (confirmed directly against this
file and SKILL.md before this mechanism was built, not assumed). Since a
worktree shares refs/objects with the main checkout it was created from,
`gitapex_check_task_worktree_base.py` resolves the name purely from local
git state instead: the worktree's own branch reflog records a
`"branch: Created from <name>"` entry at creation time -- git's own
standard behavior for `git branch <new> <startpoint>`,
`git checkout -b <new> <startpoint>`,
and `git worktree add -b <new> <path> <startpoint>` alike, live-verified
against a real worktree fixture during this mechanism's own authoring
pass -- and `<name>` is then verified to resolve to an EXISTING LOCAL
branch before being trusted as the shared plan branch. See
`gitapex_check_task_worktree_base.py`'s own module docstring for the full
mechanism, including a deliberately narrower alternative considered and
rejected as unsafe (walking the
worktree's own `.git` file back to the main checkout and reading ITS
currently checked-out branch) -- that heuristic false-positives for ANY
linked worktree whatsoever, not only one this skill's own Workflow-tool
dispatch created, confirmed live against exactly such an unrelated
worktree during authoring.

**Disclosed assumption -- and it is verified FALSE for at least one real
dispatcher.** This resolution mechanism assumes the Workflow tool's own
`isolation: 'worktree'` implementation creates each task's worktree via a
`-b <new-branch> <shared-branch-name>`-shaped operation naming the shared
branch as a literal startpoint -- the same "Open item, not resolved here"
territory this file already flags above for this exact tool's own
worktree-creation internals (its cleanup-on-merge-back behavior). If the
real implementation instead uses a detached-HEAD checkout, or passes a raw
commit SHA or a remote-tracking ref rather than a local branch name as the
startpoint, this backstop's own resolution fails cleanly and it silently
no-ops for that dispatch -- see the fail-open paragraph next.

**This is not hypothetical, and it is the common case here.** Issue
`#1566`'s own step-8 adversarial review observed a real `branch-plan-task`
worktree in this repository whose own branch reflog read exactly `branch:
Created from origin/main`, sitting at the plan branch's merge-base with
every one of that branch's commits missing -- issue `#1508`'s own defect
shape, in the flesh. `origin/main` is a remote-tracking ref, not a local
branch, so `gitapex_check_task_worktree_base.py` returned `warn` and
failed open: the stale base went undetected and the dispatched agent had
to notice it and `git reset --hard` by hand.

**Therefore: treat this backstop as absent until the shared plan branch's
name is threaded in explicitly.** Until then, a wave dispatch's own prompt
should tell each task to verify its worktree HEAD against the shared plan
branch's tip itself, rather than relying on this hook to catch it -- which
is exactly what the step-8 dispatch prompt that found this had to do by
hand. Comparing against `origin/main` instead would NOT be a fix: `main`
is not the shared plan branch, so that check would deny every
legitimately-based task worktree the moment `main` advanced -- the same
false, blast-radius-widening DENY the rejected main-checkout heuristic
above was rejected for. The real fix (an env var naming the shared plan
branch, set by this skill's own dispatch step and read by the script) is
an open follow-up, named here rather than silently assumed away.

**Fail-open by design, the opposite default from
`gitapex_check_task_bash_safety.py`'s own fail-closed classifier.** This
backstop denies ONLY on a clean, confirmed mismatch (the shared branch's
own current tip genuinely not an ancestor of the worktree's HEAD); every
other outcome -- the branch name cannot be resolved at all (no worktree,
a detached HEAD, an unrelated worktree's own reflog, a malformed hook
payload), or even a crash inside the classifier itself -- fails OPEN,
silently letting the Bash call proceed to the existing Bash-safety
classifier unchanged. This is deliberate: this backstop must never
interfere with the sequential fallback below (no worktree, no wave),
which this same `branch-plan-task` agent type also runs under, per design
doc Decision 4's own portability answer -- and a false DENY here would be
strictly worse than a missed detection, since it would stop a task's own
legitimate work over a precondition check this mechanism cannot always
resolve with confidence. See
[threat-model-and-authorization.md](threat-model-and-authorization.md#worktree-base-precondition-backstop)
for the two-variant asymmetry (this mechanism exists only in the
project-local variant, which alone carries the embedded `PreToolUse`
hook) and the full disclosed-residual accounting.

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

**"Portable to any agent platform" scope, stated precisely rather than
implied broader than verified.** This path is *architecturally*
platform-agnostic because it deliberately avoids every Claude-Code-
specific primitive (no `Workflow` tool, no `agentType`, no
`isolation: 'worktree'`) -- it needs nothing beyond a plain conversational
loop and file/git tools any coding agent has. That is a structural
argument, not an empirical one: this skill's own authoring session tried
to verify the claim against a concrete other platform (OpenAI Codex,
since it is an active participant in this repository as an automated PR
reviewer) and could not -- the relevant primary documentation
(`developers.openai.com`) was unreachable from that session's own network
policy. Whether Codex's actual execution model (its own sandbox/approval
mechanics, whether it has a persistent "main thread" concept at all)
genuinely behaves the way this fallback assumes is therefore **not
verified, on any platform other than Claude Code itself**, and should not
be read as confirmed portability -- only as an architecture that avoids
the specific dependencies that would obviously break it.

What does not change between the two paths: the task list itself, the
step-1 authorization gate, the event log and PR handoff. Only the *how*
of running each task differs.

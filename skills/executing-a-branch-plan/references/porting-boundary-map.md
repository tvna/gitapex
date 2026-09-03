# Porting Boundary Map

Read only when vendoring or porting this skill to a non-Claude-Code
agent platform -- never on an ordinary run, and never cited from
`SKILL.md`'s own Exact sequence. Source:
`evaluating-skill-quality/references/rubric.md`'s Mixed-portability
substitute (issue `#1676`), which credits a Dimension-5-exempted target
with this map plus distinct-heading isolation and a `SKILL.md` Notes
declaration in place of a literal file-level relocation of every-use
content -- see this skill's own `metadata/gitapex.yaml` decision log
for that finding's own record.

This table enumerates every Claude-Code-specific touchpoint this skill
carries, where it is used, and the portable substitute (if any) a
non-Claude-Code port falls back to. It does not restate each
mechanism's own full design rationale -- follow the "Detail" column's
own cross-reference for that.

| Touchpoint | Used at | Why Claude-Code-specific | Portable alternative | Detail |
|---|---|---|---|---|
| `Workflow` tool | Step 6's primary dispatch path (one run per wave) | A Claude-Code-native tool; no equivalent named in any other agent platform's own documentation this skill's authoring session could reach | Sequential fallback: the same task list executed one task per turn in the main thread, no wave/run boundary | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#sequential-fallback) |
| `agentType: 'branch-plan-task'` (the `Workflow`/`Agent` tool option) | Step 6's per-task `agent()` calls, and Step 8's refactor/simplify dispatch (that type's own second sanctioned call site) | Selects a Claude-Code-native subagent type from Claude Code's own type registry | None structurally required by execution itself; the Decision-17 tool-exclusion backstop it provides has no portable equivalent -- the sequential fallback carries a prompt-only exclusion list instead, disclosed as strictly weaker | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#step-8s-two-dispatches) |
| `subagent_type: 'review-persona'` (the `Agent` tool option) | Step 8's adversarial code review dispatch | Selects a Claude-Code-native subagent type from Claude Code's own type registry | None structurally required by execution itself; a porting target needs its own equivalent read-only review-persona mechanism, or drops this dispatch's own isolation | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#step-8s-two-dispatches) |
| `isolation: 'worktree'` (the `Workflow` tool option) | Step 6, multi-task waves | Guards concurrent `agent()` calls racing on one shared working directory's index/HEAD -- a Claude-Code `Workflow`-tool-specific mechanism | Not needed: the sequential fallback has no concurrent write to isolate against (one task per turn); Step 8's own two dispatches are single, not per-wave, so neither needs this either | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#git-worktree-isolation-for-parallel-task-execution) |
| The `branch-plan-task` subagent-type definition itself (`agents/branch-plan-task.md`, both deployment variants) | Every Step 6 dispatch on the primary path | Lives in Claude Code's own subagent-type registry mechanism (a project-local hook-backed variant and a plugin-distributed prompt-only variant, per this skill's own disclosed two-variant asymmetry) | A porting target needs its own equivalent role/persona definition mechanism, or drops the isolation this type provides entirely (falling back to the sequential path's own weaker, prompt-only exclusion) | [threat-model-and-authorization.md](threat-model-and-authorization.md#the-branch-plan-task-subagent-type) |
| `check_task_bash_safety.sh`'s `PreToolUse` "Bash" hook (Decision 17 backstop) | Fires on every Bash call from a `branch-plan-task`-typed agent, project-local deployment variant only | Claude Code's own hooks mechanism; the plugin-distributed variant already carries no embedded hook at all (disclosed asymmetry, not new to porting) | None: a porting target relies entirely on the dispatch prompt's own stated exclusion list, the same weaker guarantee the plugin-distributed variant already accepts | [threat-model-and-authorization.md](threat-model-and-authorization.md#the-branch-plan-task-subagent-type) |
| `gitapex_check_task_worktree_base.py`'s worktree-base precondition backstop, chained into the same `PreToolUse` hook | Every Bash call from a worktree-isolated task, project-local deployment variant only (issues `#1508`/`#1566`) | Same Claude-Code hooks mechanism dependency as the row above; also assumes the `Workflow` tool's own worktree-creation internals (an env-var-resolution mechanism disclosed as itself only partly verified) | None: a porting target has no equivalent precondition check at all -- a wave dispatch's own prompt must tell each task to verify its own base against the shared branch by hand, the same interim workaround this skill's own project-local deployment already needs until the shared-branch name is threaded in explicitly | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#worktree-base-precondition-backstop) |
| `check_task_full_verification.py`'s `SubagentStop` hook (Decision 20 exit condition) | Fires once each `branch-plan-task` dispatch returns, before its own `TaskCompleted` is trusted | `SubagentStop` is a Claude-Code-native hook event; no `SubagentStart`-equivalent or general post-dispatch hook is documented elsewhere | A porting target's own main thread (or calling session) must itself re-run the full verification suite against each task's own diff before accepting its result, rather than relying on a hook to enforce it | [threat-model-and-authorization.md](threat-model-and-authorization.md#full-verification-exit-condition-decision-20) |
| `CLAUDE_CODE_DISABLE_WORKFLOWS` environment variable | Step 6's own fallback-selection check | Names a Claude-Code-specific feature flag | Moot on a non-Claude-Code platform: there is no `Workflow` tool to disable, so the sequential fallback is simply the only path such a platform ever has | [decomposition-and-dispatch.md](decomposition-and-dispatch.md#sequential-fallback) |

**Not used, named here only to avoid a porter assuming otherwise:**
`EnterWorktree`/`ExitWorktree` (a distinct Claude-Code tool pair that
moves an entire interactive session into one worktree) are not called by
this skill's own main-thread git operations -- see
[decomposition-and-dispatch.md](decomposition-and-dispatch.md#git-worktree-isolation-for-parallel-task-execution)
for the explicit disclaimer.

**What porting does not change.** Steps 1, 2, 4, 5, 7, 9 use only
GitHub-connector calls and skill-to-skill reuse, both portable as-is
(`SKILL.md`'s own Notes section); step 8 does not, per its own two
dispatch rows above. The task list itself, the step-1
authorization gate, the event log, and the PR handoff are identical
between the primary and sequential paths -- only the *how* of running
each task differs, per
[decomposition-and-dispatch.md](decomposition-and-dispatch.md#sequential-fallback)'s
own closing line.

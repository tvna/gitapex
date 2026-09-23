---
name: branch-plan-task
description: Task-level, plugin-distributed subagent type for a fixed, enumerated set of call sites -- see this file's own "Sanctioned call sites" section for the exact, current list (executing-a-branch-plan Step 6's per-task dispatch, Step 8's refactor/simplify pass).
disallowedTools: mcp__github
---

Dispatch target for `executing-a-branch-plan`, scoped to the two call
sites the "Sanctioned call sites" section below enumerates. At Step 6's
own call site, do all Decision 3 task work (Red-Green per Decision 14,
screened per Decision 6); at Step 8's own call site, apply the same tool
set as a behavior-preserving refactor/simplify pass over the full
accumulated diff instead (no per-task Red-Green there -- see
`skills/executing-a-branch-plan/references/events-and-review-gate.md`'s
own sub-step 1). Both use Edit, Write, Read, Grep, Glob, and Bash for
non-excluded commands (git add, git commit, running tests). At Step 6's
own call site, this agent type also dispatches Agent/Task for one fixed,
narrow purpose: whenever the task's own target is a `SKILL.md` edit,
`drafting-a-skill`'s own Precondition ("Who executes which Step")
has it running that skill's Steps 1/2/6 directly (as above) while
dispatching Steps 3/4/5/7 to the `review-persona` subagent type via
`Agent`/`Task` (`agents/review-persona.md`'s own Sanctioned call site 5)
-- the only onward dispatch this call site makes, never a
general-purpose fan-out; Step 8's own call site makes none, its two
passes dispatched independently from the calling
`executing-a-branch-plan` thread instead. Never attempt a GitHub write,
the gh CLI, git push, or a package-manager install -- those are
main-thread-only per design doc Decision 7.

## Sanctioned call sites

Only these. A caller outside this list should not name this
`agentType`/`subagent_type` -- propose adding it here first, in the same
change that adds the new call site, rather than reusing this definition
silently.

1. `executing-a-branch-plan` Step 6's per-task dispatch (Decision 4/16)
   -- one `agent()` call per Decision 3/15 task, dispatched per wave. The
   existing, primary role this agent type was originally defined for.
2. `executing-a-branch-plan` Step 8's refactor/simplify pass (Decision
   12) -- a single dispatch over the full accumulated diff, after all
   Step 6 tasks complete, behavior-preserving edits only. Any
   behavior-affecting finding is out of this dispatch's own scope and
   routes to the separate adversarial review pass instead
   (`subagent_type: 'review-persona'`, see `agents/review-persona.md`'s
   own "Sanctioned call sites" section) -- see
   `skills/executing-a-branch-plan/references/events-and-review-gate.md`'s
   own sub-step 1/2 split for why.

**Before reporting complete, run the full repo verification suite in
your own dispatch's working checkout** (a worktree at Step 6's call
site; this dispatch's own checkout directly at Step 8's, which runs
without worktree isolation -- see the "Sanctioned call sites" section
above) (design doc Decision 20, issue #1476): `uv run
--frozen python3 -m pytest --no-cov -q --ignore=tests/test_gitapex_check_bash_safety_oracle_pins.py --ignore=tests/test_gitapex_check_task_bash_safety_oracle_pins.py --ignore=tests/test_gitapex_check_bash_safety_differential.py --ignore=tests/test_gitapex_check_task_bash_safety_differential.py`
then `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`.
Do not report this dispatch done while either fails -- fix the failure
first, the same as any other Red-Green check this dispatch's own work
requires.

This tool restriction (`disallowedTools: mcp__github`) is structurally
enforced. Claude Code's plugin-agent frontmatter supports no `hooks`
field ("for security reasons," per Claude Code's own plugin-reference
documentation), so the Bash-level exclusion (no `gh`, `git push`, or
install commands) and the full-verification-suite exit condition above
are backed instead, in Claude Code only, by the plugin's own
`hooks/hooks.json`, which scopes both hooks to any `agent_type` naming
this agent (issue #1996); other runtimes (e.g. OpenCode) run no such hook,
so there these exclusions rest on this paragraph alone. Outside a gitapex
checkout the exit-condition hook skips with a visible message and the two
commands above do not exist: run that repository's own test and lint
commands instead before reporting complete -- see
`skills/executing-a-branch-plan/references/threat-model-and-authorization.md`
for the full, honest accounting of what is and is not structurally
enforced here.

**If you are running inside a git worktree** (design doc Decision 13,
`isolation: 'worktree'`), before your own first Bash call, confirm this
worktree's own fork point still matches the shared plan branch's current
tip: `git merge-base HEAD <shared-branch>` must equal `git rev-parse
<shared-branch>` (issue #1508). If it does not, the shared branch has
advanced past this worktree's own base since it was created -- stop and
say so rather than continuing from a stale base. The plugin's own
`PreToolUse` Bash hook backs this same check deterministically
(`gitapex_check_task_worktree_base.py`, chained into `check_task_bash_
safety.sh`), but only from your first Bash call onward. Skip this check
entirely if you are not running inside a worktree at all (the sequential-
fallback dispatch, no wave, or Step 8's own single dispatch -- also no
wave, no worktree isolation, per
`skills/executing-a-branch-plan/references/decomposition-and-dispatch.md`'s
own Step 8 subsection) -- there is no shared-branch fork point to
compare against in that case.

---
name: branch-plan-task
description: Task-level, project-local subagent type for a fixed, enumerated set of call sites -- see this file's own "Sanctioned call sites" section for the exact, current list (executing-a-branch-plan Step 6's per-task dispatch, Step 8's refactor/simplify pass). Never invoke directly for anything else, and never add a new call site without updating that section first -- this type exists as the Decision 17 deterministic backstop for Decision 7's exclusion list (no mcp__github__* tools, no gh/git-push/install commands), across both call sites, plus (Decision 20, issue #1476) the deterministic backstop requiring the full repo verification suite to pass inside this dispatch's own working checkout before it may report complete. Project-local variant (this repository checked out directly, .claude/agents/ discovery path) -- the embedded hooks below only fire here; see agents/branch-plan-task.md (the plugin-distributed variant, no hooks field, weaker prompt-only backstop for both mechanisms) for the deployment where gitapex is installed as a plugin into a different repository.
disallowedTools: mcp__github
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "\"${CLAUDE_PROJECT_DIR:-$(pwd)}/skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh\""
          timeout: 30
  SubagentStop:
    - matcher: "*"
      hooks:
        - type: command
          command: "\"${CLAUDE_PROJECT_DIR:-$(pwd)}/skills/executing-a-branch-plan/scripts/check_task_full_verification.sh\""
          timeout: 3900
---

Dispatch target for `executing-a-branch-plan`, scoped to the two call
sites the "Sanctioned call sites" section below enumerates. At Step 6's
own call site, do all Decision 3 task work (Red-Green per Decision 14,
screened per Decision 6); at Step 8's own call site, apply the same tool
set as a behavior-preserving refactor/simplify pass over the full
accumulated diff instead (no per-task Red-Green there -- see
`skills/executing-a-branch-plan/references/events-and-review-gate.md`'s
own sub-step 1). Both use Edit, Write, Read, Grep, Glob, and Bash for
non-excluded commands (git add, git commit, running tests). Never attempt
a GitHub write, the gh CLI, git push, or a package-manager install --
those are main-thread-only per design doc Decision 7; this agent type's
own tool restrictions and embedded Bash hook enforce that structurally,
not only by this instruction.

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

Before reporting complete: the embedded `SubagentStop` hook above runs the
full repo verification suite (`uv run --frozen python3 -m pytest --no-cov
-q` plus `uv run --frozen python3
.github/scripts/gitapex_gate_local_preflight.py`) inside this dispatch's
own working checkout (a worktree at Step 6's call site; this dispatch's
own checkout directly at Step 8's, which runs without worktree isolation
-- see the "Sanctioned call sites" section above) and denies stopping
until both pass (design doc Decision 20, issue #1476) -- this is a
deterministic backstop, not only this paragraph's own instruction, but
fixing a verification failure it reports is still this dispatch's own
responsibility to act on, the same as any other blocked stop.

This hook's own `timeout: 3900` above must stay comfortably above 2x
`gitapex_check_task_full_verification.py`'s own `DEFAULT_TIMEOUT_SECONDS`
(1800s, applied per step to two sequential steps): Claude Code cancels a
`command` hook that reaches its own `timeout` and discards its output
entirely, and `SubagentStop` is not one of the two documented exceptions
that still block on a timeout (only `PreModelSwitch`, and Agent-SDK
callback hooks on `PreToolUse`, do) -- so a `timeout` here set too low
would let a legitimately slow (not failing) verification run silently
fail OPEN instead of denying, defeating this whole gate. Keep the two
values in sync if either changes.

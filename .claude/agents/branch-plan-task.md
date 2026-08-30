---
name: branch-plan-task
description: Task-level subagent type for executing-a-branch-plan's Decision 4/16 execution step (one agent() call per Decision 3/15 task, dispatched per wave). Never invoke directly for anything else -- this type exists solely as the Decision 17 deterministic backstop for Decision 7's exclusion list (no mcp__github__* tools, no gh/git-push/install commands), scoped to task-agent dispatch specifically per docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md, plus (Decision 20, issue #1476) the deterministic backstop requiring the full repo verification suite to pass inside this task's own worktree before it may report complete. Project-local variant (this repository checked out directly, .claude/agents/ discovery path) -- the embedded hooks below only fire here; see agents/branch-plan-task.md (the plugin-distributed variant, no hooks field, weaker prompt-only backstop for both mechanisms) for the deployment where gitapex is installed as a plugin into a different repository.
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

Task-level dispatch target for `executing-a-branch-plan`. Do all Decision 3
task work (Red-Green per Decision 14, screened per Decision 6) using Edit,
Write, Read, Grep, Glob, and Bash for non-excluded commands (git add, git
commit, running tests). Never attempt a GitHub write, the gh CLI, git push,
or a package-manager install -- those are main-thread-only per design doc
Decision 7; this agent type's own tool restrictions and embedded Bash hook
enforce that structurally, not only by this instruction.

Before reporting complete: the embedded `SubagentStop` hook above runs the
full repo verification suite (`uv run --frozen python3 -m pytest --no-cov
-q` plus `uv run --frozen python3
.github/scripts/gitapex_gate_local_preflight.py`) inside this worktree and
denies stopping until both pass (design doc Decision 20, issue #1476) --
this is a deterministic backstop, not only this paragraph's own
instruction, but fixing a verification failure it reports is still this
task's own responsibility to act on, the same as any other blocked stop.

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

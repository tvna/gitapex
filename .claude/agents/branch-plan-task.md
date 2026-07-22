---
name: branch-plan-task
description: Task-level subagent type for executing-a-branch-plan's Decision 4/16 execution step (one agent() call per Decision 3/15 task, dispatched per wave). Never invoke directly for anything else -- this type exists solely as the Decision 17 deterministic backstop for Decision 7's exclusion list (no mcp__github__* tools, no gh/git-push/install commands), scoped to task-agent dispatch specifically per docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md.
disallowedTools: mcp__github
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "\"${CLAUDE_PROJECT_DIR:-$(pwd)}/skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh\""
          timeout: 30
---

Task-level dispatch target for `executing-a-branch-plan`. Do all Decision 3
task work (Red-Green per Decision 14, screened per Decision 6) using Edit,
Write, Read, Grep, Glob, and Bash for non-excluded commands (git add, git
commit, running tests). Never attempt a GitHub write, the gh CLI, git push,
or a package-manager install -- those are main-thread-only per design doc
Decision 7; this agent type's own tool restrictions and embedded Bash hook
enforce that structurally, not only by this instruction.

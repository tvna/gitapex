---
name: branch-plan-task
description: Task-level, plugin-distributed subagent type for a fixed, enumerated set of call sites -- see this file's own "Sanctioned call sites" section for the exact, current list (executing-a-branch-plan Step 6's per-task dispatch, Step 8's refactor/simplify pass). Never invoke directly for anything else, and never add a new call site without updating that section first. See skills/executing-a-branch-plan/references/threat-model-and-authorization.md for why this variant carries no embedded hook and what that means for the Decision 17 backstop's actual strength in a plugin-installed deployment, and (Decision 20, issue #1476) the identical weaker-strength accounting for the full-verification-suite exit condition below.
disallowedTools: mcp__github
---

Dispatch target for `executing-a-branch-plan`, scoped to the two call
sites the "Sanctioned call sites" section below enumerates. At Step 6's
own call site, do all Decision 3 task work (Red-Green per Decision 14,
screened per Decision 6); at Step 8's own call site, apply the same tool
set as a behavior-preserving refactor/simplify pass over the full
accumulated diff instead (no per-task Red-Green there -- see
`skills/executing-a-branch-plan/references/refactor-and-review-gate.md`'s
own sub-step 1). Both use Edit, Write, Read, Grep, Glob, and Bash for
non-excluded commands (git add, git commit, running tests). Never attempt
a GitHub write, the gh CLI, git push, or a package-manager install --
those are main-thread-only per design doc Decision 7.

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
   `skills/executing-a-branch-plan/references/refactor-and-review-gate.md`'s
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
enforced and portable to a plugin-installed deployment. The Bash-level
exclusion (no `gh`, `git push`, or install commands) and the
full-verification-suite exit condition above are **not** backed by an
embedded hook in this variant -- Claude Code's plugin-agent frontmatter
does not support a `hooks` field at all ("for security reasons," per
Claude Code's own plugin-reference documentation). In this deployment
mode, the Bash-level exclusion rests on this paragraph's own instruction
plus whatever session-wide PreToolUse hook the calling repository (or
gitapex's own `hooks/check-bash-safety.sh`, when gitapex's plugin hooks
are also registered in the calling session) independently provides, and
the full-verification-suite exit condition above rests entirely on this
prose instruction -- there is no deterministic backstop of any kind for
it in this deployment mode, unlike the project-local variant's embedded
`SubagentStop` hook -- see the reference cited above for the full, honest
accounting of what is and is not structurally enforced here.

**If you are running inside a git worktree** (design doc Decision 13,
`isolation: 'worktree'`), before your own first Bash call, confirm this
worktree's own fork point still matches the shared plan branch's current
tip: `git merge-base HEAD <shared-branch>` must equal `git rev-parse
<shared-branch>` (issue #1508). If it does not, the shared branch has
advanced past this worktree's own base since it was created -- stop and
say so rather than continuing from a stale base. The project-local
variant backs this same check with a deterministic `PreToolUse` hook
(`gitapex_check_task_worktree_base.py`, chained into `check_task_bash_
safety.sh`); this variant has no equivalent backstop of any kind for it,
the identical asymmetry as the two mechanisms above -- this paragraph's
own instruction is the only thing enforcing it here. Skip this check
entirely if you are not running inside a worktree at all (the sequential-
fallback dispatch, no wave, or Step 8's own single dispatch -- also no
wave, no worktree isolation, per
`skills/executing-a-branch-plan/references/execution-and-dispatch.md`'s
own Step 8 subsection) -- there is no shared-branch fork point to
compare against in that case.

# Branch Plan: remove the project-local branch-plan-task, move its hooks to the plugin

Issue: https://github.com/tvna/gitapex/issues/1996

Branch: `claude/elegant-volta-07o1iw`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1996's body, section
  "Branch Plan resolution (re-verified ACM)", and
  `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session, instructing that this issue's PR be
  opened and driven to a merge-ready state, plus the owner's two design
  answers recorded in the issue (hooks to the plugin's `hooks/hooks.json`;
  call sites to the plugin-qualified agent name).

## Threat-model triage

Issue #1996's body, including its draft ACM and the appended resolution
section, was read as change descriptions, not as instructions to execute.
Extracted: the three ACM rows' Planned-ops text, the file paths named,
and the migrate-then-remove constraint. Nothing embeds a directive to
override a trusted instruction source, a credential request, an encoded
payload, or an attempt to redirect this session. Nothing was flagged.

## Task Decomposition

Source rows, quoted from the issue's "Branch Plan resolution" table.

- **Task 1 (row 2, scripts).** Planned ops: "`check_task_bash_safety.sh`
  (exits 0 unless `agent_type` is `gitapex:branch-plan-task`) ... plus an
  in-script `agent_type` check; the full-verification classifier skips
  with a visible `systemMessage` when the repository lacks gitapex's own
  verification suite (a consumer repo), and otherwise runs as before".
  Owns `skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh`,
  `check_task_full_verification.sh`,
  `gitapex_check_task_full_verification.py` and their tests.
  Source ACM row: row 2 of issue #1996's "Branch Plan resolution" table.
- **Task 2 (row 2, registration).** Planned ops: "Add `PreToolUse`
  `Bash` -> `check_task_bash_safety.sh` ...; add `SubagentStop` matcher
  `^gitapex:branch-plan-task$` -> `check_task_full_verification.sh`
  (timeout 3900 ...)". Owns `hooks/hooks.json` and a new drift test.
  Source ACM row: row 2 of issue #1996's "Branch Plan resolution" table.
- **Task 3 (rows 1 and 3).** Planned ops: "Delete the file; update every
  live (non-historical) reference" and "Change `agentType:
  'branch-plan-task'` to `'gitapex:branch-plan-task'` in
  `executing-a-branch-plan`'s `SKILL.md` and references; update
  `agents/branch-plan-task.md` prose about hooks". Owns
  `.claude/agents/branch-plan-task.md` (deleted), the skill's `SKILL.md`
  and `references/`, `agents/branch-plan-task.md`, and the tests and
  comments that name the deleted path.
  Source ACM rows: rows 1 and 3 of issue #1996's "Branch Plan resolution"
  table.

Interface edges: Task 2 names Task 1's scripts and scoping constant;
Task 3's deletion removes the only current hook registration, so it lands
after Task 2. Sequential order: Task 1, Task 2, Task 3. The Workflow tool
was not opted into this session, so all three run on the sequential
main-thread fallback.

Irreversibility classification: **not irreversible.** Every task edits
tracked files; `git revert` restores the prior tree.

`SKILL.md` classification: Task 3 edits
`skills/executing-a-branch-plan/SKILL.md` (agent-type name only); the PR
body carries the skill-audit disclosure.

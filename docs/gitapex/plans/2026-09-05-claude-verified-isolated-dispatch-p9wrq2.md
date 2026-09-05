# Task Decomposition: Verified Isolated Dispatch Primitive

Issue: https://github.com/tvna/gitapex/issues/1809
Branch: `claude/verified-isolated-dispatch-p9wrq2`
Design doc: `docs/gitapex/specs/2026-09-05-verified-isolated-dispatch-design.md`

## Authorization record

- `planning-a-branch-from-an-issue`'s re-verification marker present on issue #1809 (`Re-verified: planning-a-branch-from-an-issue (2026-09-05T09:05:00Z)`), confirmed structurally via `gitapex_check_branch_plan_reverified.py`: PASS.
- Semantic authorization: explicit human confirmation in the current interactive session (the operator's own direct instruction, "issueを作成してマージ直前まで進める" -- create the issue and drive to just before merge), following a full multi-turn `eliciting-a-design` dialogue that converged this exact design with the same operator.

## Threat-model triage (Decision 6)

The Acceptance Criteria Map's own text (issue #1809, drafted by this same session from the operator-approved design doc) was scanned for anything reading as an injected instruction rather than a change description. No such content found -- every row states a criterion/interpretation/planned-op/proof-method/residual-risk in plain change-description language, with no embedded directive addressed to an executing agent.

## Task list

Five tasks, one per issue ACM row.

| # | Task | Planned ops (quoted from issue ACM) | Files owned (write) | Files read (no write) |
|---|---|---|---|---|
| 1 | Build the verified-dispatch script + unit tests | "Add the new script; wire evaluating-skill-quality's own SKILL.md Subagent dispatch section to call it instead of the current hand-rolled prose procedure" (script-authoring half only -- the SKILL.md wiring half is task 5's own planned op, listed there instead, to avoid two tasks both claiming a write on SKILL.md) | `skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py`, `skills/evaluating-skill-quality/scripts/test_gitapex_run_verified_isolated_dispatch.py` | `skills/evaluating-skill-quality/references/adversarial-self-audit.md` (current Verification procedure prose, for the script's own docstring) |
| 2 | Migrate the Known-entries registry to structured data | "Add the new data file; a one-time migration pass over adversarial-self-audit.md's current Known entries" | `skills/evaluating-skill-quality/metadata/isolation-registry.yaml` | `skills/evaluating-skill-quality/references/adversarial-self-audit.md` (current Known entries) |
| 3 | Add the scheduled registry-refresh workflow | "Add the new workflow file" | `.github/workflows/isolation-registry-refresh.yml` | `.github/workflows/skill-eval-gate.yml`, `.github/workflows/skill-audit-gate.yml` (style precedent); task 1's script (CLI contract) |
| 4 | Rewrite `adversarial-self-audit.md`'s Isolation verification section | "Edit skills/evaluating-skill-quality/references/adversarial-self-audit.md's Isolation verification section and its TOC entry" | `skills/evaluating-skill-quality/references/adversarial-self-audit.md` | task 1's script, task 2's registry file |
| 5 | Update `SKILL.md` cross-citations + full regression | "Update cross-citations in SKILL.md as needed" plus the shape/drift/pytest regression proof method | `skills/evaluating-skill-quality/SKILL.md` | task 1's script, task 4's rewritten `adversarial-self-audit.md` |

## File-ownership map

No two tasks write the same file. Task 1 and task 2 both *read* `adversarial-self-audit.md` without writing it -- not a conflict (`gitapex_check_file_ownership_conflicts.py`'s own pure-string-matching case is scoped to write/write and write/read collisions on the same path within the same wave's actual edits; two read-only reads of the same file carry no edge).

## Interface-dependency map

- Task 3 -> depends on task 1 (needs the script's own fixed CLI contract: `--target`, `--prompt-file`, `--controls-only`, `--allowed-tools` -- already pinned by the design doc, but sequenced defensively rather than assumed stable before task 1 actually lands it).
- Task 4 -> depends on task 1 AND task 2 (the rewritten prose points at the script and the registry; deleting the old Known-entries prose before both replacements exist would lose information with no replacement).
- Task 5 -> depends on task 1 AND task 4 (SKILL.md's own cross-citations must point at both the script and the already-rewritten `adversarial-self-audit.md` section, not the pre-rewrite prose).

Task 1 and task 2 share no file-ownership or interface edge with each other -- independent.

## Wave assignment

- **Wave 1:** task 1, task 2 (parallel; independent of each other).
- **Wave 2:** task 3, task 4 (parallel; each depends only on wave 1's outputs, not on each other -- task 3 touches `.github/workflows/`, task 4 touches `references/adversarial-self-audit.md`, no shared file).
- **Wave 3:** task 5 (depends on task 1 and task 4, both settled by the end of wave 2).

## Execution mode

Sequential main-thread fallback, not the `Workflow`-tool multi-agent path: this session has not received the explicit multi-agent-orchestration opt-in the calling harness requires before invoking `Workflow` (no "ultracode" keyword, no direct user request in those terms). Each task below is executed directly in the main thread, in wave order (1+2, then 3+4, then 5), with the shape checker and pytest suite run as the same verification gate a dispatched task's own `SubagentStop` hook would otherwise enforce.

## Irreversibility classification

None of the five tasks is irreversible (all are additive file creation or an in-place prose/code edit on a not-yet-merged branch; nothing here executes outward-facing side effects, deletes data, or touches production state). No task needs a fresh step-1-equivalent confirmation beyond the one already recorded above.

## Execution log

- `PlanApproved`: Branch Plan for issue #1809 approved via explicit in-session operator confirmation; this task-list file committed as its first commit on `claude/verified-isolated-dispatch-p9wrq2`.

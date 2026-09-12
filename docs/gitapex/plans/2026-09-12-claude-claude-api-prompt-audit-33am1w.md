# Branch Plan: claude/claude-api-prompt-audit-33am1w

Issue: https://github.com/tvna/gitapex/issues/1963
Base: main

Scope of this branch: PR1 only -- ACM rows 1-6 (the rubric layer plus the gate
layer and the existing violations those gates would otherwise flag on day one).
Rows 7 and 8 are transcribed below for traceability but are delivered on later
branches; see "Out of this branch's scope" at the end.

## Acceptance Criteria Map

Re-verified by `planning-a-branch-from-an-issue` against the tree at
`adf08aec`; the five corrections that pass produced are recorded on the issue
under "Plan re-verification (2026-09-12)" and are folded into the rows below.

| # | Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|---|
| 1 | The rubric declares AGENTS.md and subagent definitions separately | Common criteria 1-5 keep their meaning and numbering; channel-specific axes are added in a channel namespace | Add `A1`-`A4` and `B1`-`B4` to `SKILL.md` and `references/criteria.md`, stating per axis whether its basis is primary-source-quotable or a gitapex-owned convention | The diff to common criteria 1-5 is empty, the 13 fixtures stay valid, and every new axis carries a stated basis | Axis count grows and per-channel reading load increases |
| 2 | `B1` is what names Defect A | The detector is content type (routing contract vs design archaeology), not length | Add `B1` carrying the rule that a description states only when the subagent should be called, and that a trigger-cohesion problem is resolved upstream or by splitting the subagent, never by lengthening the description | A description carrying design archaeology FAILs `B1` while sitting inside every numeric cap | `B1` is model-judged, so the deterministic cap in row 3 is what bounds the failure mode from below |
| 3 | A deterministic channel shape gate exists | Characters, lines and tokens are arithmetic, not a judgment layer | Add a self-contained channel shape checker under `skills/evaluating-context-channel-maturity/scripts/` with its own threshold constants (description <= 500 characters, body <= 500 lines and <= 5,000 tokens) | Unit tests cover each threshold's boundary values and a fail-closed path on malformed frontmatter; the checker is registered in `.gitapex/ssot.json` | Correction C4: a shared module placed on the never-deployed side would break the deployed side's standalone execution, so no module is shared with `evaluating-skill-quality` |
| 4 | The existing violations ship fixed in the same change as the gate | Shipping the gate alone leaves this repository red against its own new gate on day one | Rewrite the description of `agents/branch-plan-task.md`, `.claude/agents/branch-plan-task.md` and `agents/review-persona.md` to trigger-only (correction C2: the two `branch-plan-task.md` copies are not identical and both must be rewritten) | The shape checker FAILs against the pre-rewrite tree and PASSes after | Correction C1: trigger-only descriptions land far below 500 characters, so the cap becomes a loose backstop; whether to tighten it is open question 5 and needs measurement, not a guess |
| 5 | A declared tool boundary is reproduced equivalently in every Axis A runtime | What is mandatory is the invariant, not a field name. Axis A is Claude Code plus OpenCode | Add axis `B4`; add three checks (a boundary is declared, a permission mapping exists, the mapping is equivalent); add the OpenCode permission mapping for `branch-plan-task` in `hooks/gitapex_sync_opencode.py` | The three checks FAIL against the pre-fix tree and PASS after | On Claude Code `tools:` does not state the effective set (two hidden filters, and foreground vs background resolve differently), so the checks verify declaration parity, not effective-set parity. Adjacent to #1730 |
| 6 | AGENTS.md's own outbound references cannot drift silently | Establishing an invariant ships its drift gate in the same change (AGENTS.md section 3) | Add a drift gate asserting that every backticked identifier in `AGENTS.md` resolves to a real `skills/<name>/SKILL.md` or a real `.gitapex/ssot.json` gate id | The gate FAILs on a renamed or deleted referent and PASSes on the current tree | Decomposition note: `AGENTS.md` names eight skills and zero gate ids today, so the gate guards the skill-name index now and covers the gate-id index automatically once the row-7 rewrite introduces one |
| 7 | AGENTS.md is reduced to what cannot be derived | Cap 50 lines, target 40 | Move the procedural rules of sections 1/3/5/6 into skills; restate section 6's language rule so it names operator-facing output and repository artifacts separately | The rewritten file is at most 50 lines and every retained safety clause maps to a "partial remainder" or "uncovered" entry in the design's D4 table | No density cap is set, so characters per line stay unbounded -- accepted deliberately |
| 8 | The skill has a measured eval baseline | Correction C3: authoring a fixture is not observing a FAIL, because the suite has never been executed | Author one fixture for Defect A and one for Defect B in this branch; execute `evals/scripts/gitapex_run_eval_suite.py` on a later branch and record the result | The fixtures exist and parse in this branch; the recorded baseline run shows both FAILing the new axes on the later branch | First-run cost is unmeasured. Correction C5: the coverage gate compares `fixture_count >= branch_count`, so added fixtures pass |

## Task Decomposition

File-ownership map: computed with
`skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py`.
Interface-dependency map: model judgment, recorded per task below.

Dispatch mode: the sequential main-thread fallback. The `Workflow` tool
requires the operator's explicit opt-in, which this session does not carry, so
waves are recorded for their dependency ordering rather than for parallel
dispatch.

### Task 1: Rubric layer -- channel axes A1-A4 and B1-B4

Source ACM rows: row 1 ("The rubric declares AGENTS.md and subagent definitions
separately") and row 2 ("`B1` is what names Defect A").

Quoted Planned ops (row 1):
> Add `A1`-`A4` and `B1`-`B4` to `SKILL.md` and `references/criteria.md`,
> stating per axis whether its basis is primary-source-quotable or a
> gitapex-owned convention

Quoted Planned ops (row 2):
> Add `B1` carrying the rule that a description states only when the subagent
> should be called, and that a trigger-cohesion problem is resolved upstream or
> by splitting the subagent, never by lengthening the description

Files: `skills/evaluating-context-channel-maturity/SKILL.md`,
`skills/evaluating-context-channel-maturity/references/criteria.md`.

Delegates to: `drafting-a-skill` (this task edits an existing `SKILL.md`).

Interface edges: none inbound. Task 7 reads the axis identifiers this task
fixes.

Irreversible: no.

### Task 2: Channel shape checker

Source ACM row: row 3 ("A deterministic channel shape gate exists").

Quoted Planned ops:
> Add a self-contained channel shape checker under
> `skills/evaluating-context-channel-maturity/scripts/` with its own threshold
> constants (description <= 500 characters, body <= 500 lines and <= 5,000
> tokens)

Files: new `skills/evaluating-context-channel-maturity/scripts/gitapex_check_channel_shape.py`,
new `skills/evaluating-context-channel-maturity/scripts/test_gitapex_check_channel_shape.py`.

Delegates to: none (new checker script, not a `SKILL.md`).

Interface edges: none inbound. Task 5 must satisfy the thresholds this task
implements; Task 6 registers this task's script path.

Irreversible: no.

### Task 3: Tool-boundary parity checks and the OpenCode permission mapping

Source ACM row: row 5 ("A declared tool boundary is reproduced equivalently in
every Axis A runtime").

Quoted Planned ops:
> Add axis `B4`; add three checks (a boundary is declared, a permission mapping
> exists, the mapping is equivalent); add the OpenCode permission mapping for
> `branch-plan-task` in `hooks/gitapex_sync_opencode.py`

Files: new `.github/scripts/gitapex_gate_tool_boundary_parity.py`,
new `tests/test_gitapex_gate_tool_boundary_parity.py`,
`hooks/gitapex_sync_opencode.py`.

Placement correction, recorded rather than left as a silent drift from this
plan's first revision: these files were planned under
`skills/evaluating-context-channel-maturity/scripts/`, and moved to the
never-deployed side during implementation. Every fact the checker reads is
specific to this repository's own sync mechanism -- the source `agents/*.md`
frontmatter, `hooks/gitapex_sync_opencode.py`'s own spec table, and the
generated `.opencode/agents/` copies -- so shipping it in the plugin would
distribute gitapex-internal logic to a consumer whose repository has none of
those. Axis `B4` stays model-judged when the skill grades some other
repository's subagents; this gate is that axis applied to the one instance
this repository owns. Correction C4's boundary rule is not engaged, because
nothing is shared between the two sides.

Note: axis `B4`'s prose lands in Task 1's files, not here, so the two tasks do
not share a file. This task owns only the checks and the mapping fix.

Delegates to: none (new checker script plus a hook edit, not a `SKILL.md`).

Interface edges: none inbound. Task 5 must keep a boundary declared for these
checks to pass; Task 6 registers this task's script path.

Screening note: this task edits `hooks/gitapex_sync_opencode.py`, a
governance-adjacent execution surface. Step 6's screening is expected to flag
it, and the flag is expected rather than surprising -- the edit is the fix ACM
row 5 names.

Irreversible: no.

### Task 4: AGENTS.md outbound-reference drift gate

Source ACM row: row 6 ("AGENTS.md's own outbound references cannot drift
silently").

Quoted Planned ops:
> Add a drift gate asserting that every backticked identifier in `AGENTS.md`
> resolves to a real `skills/<name>/SKILL.md` or a real `.gitapex/ssot.json`
> gate id

Files: new `.github/scripts/gitapex_gate_agents_md_reference_drift.py`,
new `tests/test_gitapex_gate_agents_md_reference_drift.py`.

Placement rationale: this gate reads gitapex's own `AGENTS.md` and its own gate
registry, so it is repository tooling rather than a skill primitive and belongs
on the never-deployed side. It shares no module with Task 2 or Task 3, so
correction C4's boundary rule is not engaged.

Delegates to: none (new gate script, not a `SKILL.md`).

Interface edges: none inbound. Task 6 registers this task's script path.

Irreversible: no.

### Task 5: Rewrite the three subagent descriptions to trigger-only

Source ACM row: row 4 ("The existing violations ship fixed in the same change
as the gate").

Quoted Planned ops:
> Rewrite the description of `agents/branch-plan-task.md`,
> `.claude/agents/branch-plan-task.md` and `agents/review-persona.md` to
> trigger-only (correction C2: the two `branch-plan-task.md` copies are not
> identical and both must be rewritten)

Files: `agents/branch-plan-task.md`, `.claude/agents/branch-plan-task.md`,
`agents/review-persona.md`.

Delegates to: none (agent definitions, not a `SKILL.md`).

Interface edges: inbound on Task 2 (the rewritten descriptions must satisfy the
thresholds that task implements) and on Task 3 (each file must keep a tool
boundary declared for that task's checks to pass). Sequenced after both.

Screening note: these are governance-adjacent instruction files. Step 6's
screening is expected to flag them for the same reason as Task 3.

Irreversible: no.

### Task 6: Register the new gates

Source ACM rows: row 3, row 5 and row 6 (each names a check that must be
registered).

Quoted Planned ops (row 3):
> the checker is registered in `.gitapex/ssot.json`

Files: `.gitapex/ssot.json`, plus the CI workflow wiring each registered gate
requires.

Delegates to: none (registry and workflow edit, not a `SKILL.md`).

Interface edges: inbound on Tasks 2, 3 and 4 -- it records their final script
paths and rule text, so it cannot be written before they settle. Sequenced
last.

Irreversible: no.

### Task 7: Eval fixtures for Defect A and Defect B

Source ACM row: row 8 ("The skill has a measured eval baseline"), first half
only -- authoring, not execution, per correction C3.

Quoted Planned ops:
> Author one fixture for Defect A and one for Defect B in this branch; execute
> `evals/scripts/gitapex_run_eval_suite.py` on a later branch and record the
> result

Files: two new `evals/evaluating-context-channel-maturity/tasks/*.yaml`.

Delegates to: none (eval fixtures, not a `SKILL.md`).

Interface edges: inbound on Task 1 -- the fixtures reference the axis
identifiers that task fixes.

Irreversible: no.

## Wave assignment

| Wave | Tasks | Why they can share a wave |
|---|---|---|
| 1 | 1, 2, 3, 4 | Disjoint file sets and no interface edge between any pair |
| 2 | 5, 7 | Task 5 depends on 2 and 3, Task 7 on 1; they share no file and neither reads the other's output |
| 3 | 6 | Depends on 2, 3 and 4 |

## Out of this branch's scope

- ACM row 7 (the `AGENTS.md` rewrite) -- a later branch, because the new
  criteria's verdict is what the rewrite is measured against.
- ACM row 8's second half (executing the eval suite) -- a later branch.
- Codex distribution support, `.claude/rules/`, and an Output-style or
  system-prompt-append axis, all recorded as out of scope on the issue.

# Branch Plan execution: issue #1806 — merge-retrospective backlog-grounded proposal review

Parent issue: https://github.com/tvna/gitapex/issues/1806
Branch: `claude/issue-1806-merge-retro-dedup-sweep`
Authorization: Step-1 structural PASS (`gitapex_check_branch_plan_reverified.py`: re-verification marker found in live issue body, verified 2026-09-05) + explicit in-session human approval (`OK` after Branch Plan presentation). No OWNER/MEMBER/COLLABORATOR approval comment on the issue (comments empty).
Threat-model triage (Step 2): Extract/Ignore/Flag/Tag applied to ACM text. No embedded instructions executed; no `<system-reminder>`/credential/tool-use/exfiltration/encoded payloads flagged. Issue procedural text (Step 4b.1 `list_issues` etc.) treated as change description, not as runtime instruction.

## Source ACM rows ( Planned-ops quoted verbatim per Decision 3 )

### ACM row 1 — backlog retrieval
Planned ops (verbatim): `New Step 4b.1: list_issues(labels:["gate-proposal"], state:OPEN) paged to exhaustion; issue_read for every umbrella-shaped title or any issue whose body carries a Consolidates: line; also read .gitapex/ssot.json's gates[] array`

### ACM row 2 — independent verdict
Planned ops (verbatim): `A fresh review-persona dispatch (a new sanctioned call site for that agent) returns, per repair: NEW / DUPLICATE-OF #N / ALREADY-SHIPPED <ssot gate id> / RECLASSIFY <reason>, plus a batch-level CLUSTER grouping for repairs describing one fix; the calling skill verifies each verdict (re-fetches #N, re-checks the ssot entry) before acting, the same verify-outside-the-dispatch split Step 8 already uses`

### ACM row 3 — concurrent-safe duplicate handling
Planned ops (verbatim): `A DUPLICATE-OF #N verdict still creates the standalone issue via the existing Step 5 flow (an independent, non-conflicting write), immediately closes it state_reason: duplicate referencing #N, and appends its row to #N's Consolidates: line and ACM table as a best-effort follow-up write; never skips creating the standalone issue`

### ACM row 4 — deterministic deny hook
Planned ops (verbatim): `New PreToolUse hook on mcp__github__issue_write (method create, label gate-proposal): requires a body line of fixed shape Dedup-sweep: <N> open gate-proposal issues at <ISO-8601>; verdict NEW, generated only by gitapex_file_gate_proposal.py (never hand-typed); denies when the line is absent or <N> differs from a live re-fetch of the open count (reusing the REST/pagination/fail-closed code already in hooks/gitapex_check_pr_duplicate_issue.py)`

### ACM row 5 — alarm consumption
Planned ops (verbatim): `Step 4b.1 additionally reads the workflow's latest scheduled-run conclusion; when failure, the retro body must state that fact in one line`

Scope (owner decision, verbatim): `Enforcement for this issue is scoped to the sequence gate (Step 4b's own place in the procedure) plus the deterministic Dedup-sweep: PreToolUse hook above (L1+L2).`

## Task decomposition

File-ownership pre-filter (`gitapex_check_file_ownership_conflicts.py`): no conflicts found.
Interface-dependency edges (model judgment): T3 on T2 (hook parses generator's line format); T1 on T2+T3 (SKILL prose names both); T4 on T1+T2+T3 (tests exercise all three).

- [ ] T2-generator (Wave 1): extend `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py` to emit the `Dedup-sweep:` line (generator-only, never hand-typed). Files: `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`, `skills/merge-retrospective/scripts/test_gitapex_file_gate_proposal.py`. Reversible: yes. SKILL.md edit: no.
- [ ] T3-hook (Wave 2, after T2): new `hooks/gitapex_check_gate_proposal_dedup_sweep.py` + `hooks/check-gate-proposal-dedup-sweep.sh` + `hooks/hooks.json` matcher on `mcp__github__issue_write` + `.gitapex/ssot.json` gate registration. Reuses REST/pagination/fail-closed shape from `hooks/gitapex_check_pr_duplicate_issue.py`; strips fenced/inline code before matching (same discipline as sibling hooks). Reversible: yes. SKILL.md edit: no.
- [ ] T1-skill (Wave 3, after T2+T3): `skills/merge-retrospective/SKILL.md` Step 4b (4b.1 backlog sweep + verdict vocabulary NEW/DUPLICATE-OF/ALREADY-SHIPPED/RECLASSIFY + CLUSTER + verify-outside-dispatch + concurrent-safe create-then-close-then-best-effort-append + alarm line) and Step 5 sequence gate. Applies `drafting-a-skill` method for the SKILL.md edit. Files: `skills/merge-retrospective/SKILL.md`. Reversible: yes. SKILL.md edit: yes (existing).
- [ ] T4-tests (Wave 4, after T1+T2+T3): `tests/test_gitapex_check_gate_proposal_dedup_sweep.py` — hook regression (no line → deny; stale count → deny; matching count → allow; fenced-code line → ignored) + Step 4b fixtures (seeded umbrella match; genuinely new; ssot-covered; concurrent-run record preservation; seeded `failure` alarm line). At least one defeat-test per detection-logic change (hook must not be cleared on happy-path only). Reversible: yes. SKILL.md edit: no.

Waves: W1={T2}, W2={T3}, W3={T1}, W4={T4}. No parallel co-assignment across edges. Execution mode: sequential main-thread fallback (Workflow tool unavailable in this session); each task does Red-Green where proof method is an automatable test; full repo verification (`pytest` + `gitapex_gate_local_preflight.py`) before a task reports complete.

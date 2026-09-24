# Branch Plan: claude/gitapex-pr-2097-6f7ocd (issue #2097)

Issue: https://github.com/tvna/gitapex/issues/2097

Source ACM rows: issue #2097 rows 1-3 (family-level filing, ABSORBED-BY
verdict, escalate at 3 recurrences), re-verified and restated below with
the owner decisions that resolved their pending-design cells, plus an
ADR row the issue's own residual-risk cell called for.

Branch: `claude/gitapex-pr-2097-6f7ocd`
PR title: `feat(merge-retrospective): file gate proposals per family, add ABSORBED-BY, escalate on recurrence (#2097)`

## Owner decisions (in-session, 2026-09-24)

Resolves the issue's "Unknown, pending design" cells:

1. A recurrence (DUPLICATE-OF #N, or a later cluster member landing on #N)
   is recorded as an issue **comment** on #N carrying a machine-parseable
   `Recurrence: retro #R repair K` line. Comments are append-only, so
   concurrent runs cannot overwrite each other (#1806's guarantee). The
   `Consolidates:` line keeps listing only closed-as-duplicate sources;
   the consolidation scan gains the reverse direction (a closed duplicate
   pointing at an open umbrella but missing from its line).
2. ABSORBED-BY: a gate declares `generic_mechanism: true` in
   `.gitapex/ssot.json`. Follow-up work lands on one open family issue per
   mechanism, exact title `gate-proposal: extend <gate-id>`, which is
   created through the NEW flow when absent and receives a recurrence
   comment when present. `tracking_issue` is not used, because shipped
   gates' tracking issues are closed (for example #1799).
3. Escalation: occurrences = 1 (original filing) + `Consolidates:`
   sources + distinct recurrence records. At 3 or more, the family issue
   gets the `gate-proposal-escalated` label. `ranking-the-open-queue`'s
   rubric reads that label.
4. ADR 0006 records the decision.
5. Revision after five failed battle-testing rounds (owner choice "case
   E"): decision 1 is replaced. A recurrence is a standalone
   `gate-proposal` issue, titled by the title builder, whose sweep line
   reads `verdict DUPLICATE-OF #N`, closed with `state_reason: duplicate`
   and `duplicate_of: N`. Decision 3's count becomes 1 + distinct titles
   of closed gate-proposal duplicates of the family issue. The
   reverse-direction scan check is dropped: the duplicate relation is
   itself the record, so no `Consolidates:` append is owed. Live proof
   that the MCP `duplicate_of` field marks the relation is a completion
   condition. The ACM rows below read with this revision applied.

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Family-level filing (CLUSTER action; per-family issues, per-repair retro entries) | A verified CLUSTER of NEW repairs creates one issue whose ACM carries one row per member, titled by the lowest member index. Each member's retro entry records `Filed as: #X`. DUPLICATE-OF #N (verified open) posts a recurrence comment on #N instead of creating and closing a standalone issue, and records `Filed as: #N`. Resumed runs skip a repair whose `Recurrence: retro #R repair K` comment already exists. Only NEW ever creates an issue | `SKILL.md` (description, Step 1, Step 5, Stop boundary); `references/backlog-grounded-proposal-review.md` 4b.3; `references/gate-proposal-filing-mechanics.md`; `references/repair-record-format.md`; `scripts/gitapex_file_gate_proposal.py` (multi-row family body, recurrence comment builder, verdict narrowed to NEW); `hooks/gitapex_check_gate_proposal_dedup_sweep.py` (verdict narrowed to NEW); `.github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py` (reverse direction) | Unit tests: a 3-member family body has 3 ACM rows and passes `has_acm_disclosure`; the recurrence comment round-trips through its parser; the hook denies `DUPLICATE-OF`; the scan flags a seeded #1800/#2089 shape. Eval fixtures: cluster of 3 gives one create and 3 `Filed as:` lines; an umbrella match gives zero creates and one comment; two concurrent runs keep both comments | CLUSTER comes from one probabilistic dispatch; verifying it outside the dispatch stays a judgment call. Posting the comment and writing the retro body are two non-atomic writes. The resume dedup key covers that gap |
| ABSORBED-BY verdict | `ABSORBED-BY <gate-id>` applies only when the id names an active ssot gate declaring `generic_mechanism: true`; otherwise it falls back to NEW. The repair records `Absorbed by: <gate-id>` plus `Filed as: #X`, where X is the mechanism's `gate-proposal: extend <gate-id>` family issue (created if absent, commented if present). The taxonomy is unchanged | `.gitapex/ssot.schema.json` (optional `generic_mechanism`, schema_version bump); `.gitapex/ssot.json` (true on `defeat-test-mutation-coverage`, `detection-logic-property-coverage`); `.github/scripts/gitapex_scan_ssot_schema.py` (reject `generic_mechanism: true` on a non-active gate); script title builder; 4b.2/4b.3 text; record-format reference and test | Unit tests: the title builder; ssot scan rejects a deprecated generic gate. Eval fixtures: an untested except arm is absorbed by the mutation gate, with no per-repair issue and an entry naming the mechanism; an undeclared id falls back to NEW | The mechanism may still be unable to express the repair (omission-type defects); the verifier must check that. Only two gates are declared generic in this change |
| Escalate at 3 occurrences | Count = 1 + `Consolidates:` sources + distinct recurrence keys, computed deterministically. At 3 or more after recording, add `gate-proposal-escalated` (labels re-fetched and unioned) and file nothing new | Script `count_family_occurrences` plus the label constant; a parallel copy in the consolidation scan with a sync test; the scan flags count >= 3 without the label; `ranking-the-open-queue/references/scoring-rubric.md` note | Unit tests: 2 prior sources plus 1 new gives 3 (escalate); 1 prior plus 1 new gives 2 (no escalate); duplicate recurrence keys count once; scan flags a missing label. Eval fixture: seeded 2 prior sources get the label and no create | The label adds priority but not committed capacity |
| ADR | Record the reversal of #1806's per-repair standalone filing | `docs/adr/0006-...md` | Doc present, linked from SKILL.md/4b reference | None identified |

Non-goals (from the issue): backlog triage, the drift threshold of 20,
implementing any proposal, and taxonomy changes. `gitapex_scan_retrospective_gate_drift.py`
needs no change: it audits open count and closed integrity, and neither
changes.

## Task list (sequential main-thread fallback; Workflow not opted into)

| Task | Files owned | Depends on |
|---|---|---|
| T1 builder | `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`, its test | none |
| T2 hook | `hooks/gitapex_check_gate_proposal_dedup_sweep.py`, its tests | T1 (verdict contract) |
| T3 consolidation scan | `.github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py`, its test, label/regex sync test | T1 (recurrence line shape) |
| T4 ssot | `.gitapex/ssot.schema.json`, `.gitapex/ssot.json`, `.github/scripts/gitapex_scan_ssot_schema.py`, its test | none |
| T5 prose | `skills/merge-retrospective/SKILL.md`, `references/*.md`, `skills/ranking-the-open-queue/references/scoring-rubric.md`, `docs/adr/0006-*.md` | T1, T3, T4 |
| T6 evals | `evals/merge-retrospective/tasks/*.yaml`, `split.json`, `split.md`, `eval-status.md` | T5 |

Every task edits a disjoint file set, but T2-T6 read the T1 contract, so
they run in order.

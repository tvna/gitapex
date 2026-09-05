# Branch Plan: claude/gitapex-merge-pipeline-control-fsus87

Issue: https://github.com/tvna/gitapex/issues/1796
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Skill-touching PRs carry machine-checkable invocation evidence | Fail-closed disclosure gate: skill paths touched without a disclosed authoring/review invocation or waiver fail CI | Extend the existing `gitapex_gate_skill_audit_disclosure.py`: add a new `_ProcessDisclosureCheck` row (e.g. `drafting-a-skill-invocation-disclosure`) to its `_PROCESS_DISCLOSURE_CHECKS` registry, following the same pattern as its six existing checks (#517/#565/#673/#998) -- not a standalone script, per this repository's own "one place where a flag rule can change" precedent (#874). Register the applicability signal in `gitapex_compute_skill_audit_flags.py` and add `skills/**/references/**` to `skill-audit-gate.yml`'s trigger paths. | Gate unit tests plus a live fail-closed demonstration (undisclosed skill touch fails, disclosed or waived passes) | Waiver-process abuse remains open; typo-only-touch false positives are mitigated by accepting an honest `NOT-RUN` disclosure (row 2's own confirmed behavior-shaping scope), the same escape hatch `checker-script-adversarial-review`/`defeat-test-disclosure` already use |
| Behavior-shaping references edits no longer fall through the trigger | Delegation clauses widen to cover all of `skills/<name>/references/**` -- confirmed direction: broaden, not exclude | Edit the `drafting-a-skill` delegation clauses in both pipeline skills to cover `references/**`; keep the change to prose plus ACM rows, no new machinery. Row 1's gate applicability signal widens in lockstep so the two never drift apart. | Review that the amended trigger decides the #1794/#1795 case (references-only behavior edit) deterministically | Broadening the trigger pulls more diffs into row 1's gate -- accepted, mitigated by row 1's own `NOT-RUN` escape hatch for genuinely non-behavior-shaping references edits |
| Delegation is verifiable, not prose-only | Task records cite the specialist report or an explicit waiver at both declaration and verification time; screening rejects task commits lacking either | Add the citation requirement at two points in `executing-a-branch-plan`: Step 3 (Task Decomposition) states, per task, which specialist skill(s) it delegates to (or an explicit none); Step 6 (merge-back screening) verifies that citation or an explicit waiver is present before merging that task's commit -- same fail-closed shape as the existing commit-provenance scan | A task commit without citation or waiver is rejected by Step 6's stated screening in a live trial | Screening lives in-procedure; on hook-less harnesses it is still prose unless row 1's CI gate covers the same ground |
| No harness-specific machinery required | Nothing in rows 1-3 depends on Workflow tool, branch-plan-task, review-persona, or PreToolUse hooks | CI-side gate plus skill-text edits only; no agent-runtime changes | Implementation plan confirms zero harness-gated dependencies | Branch-protection required-checks membership is an admin setting no in-repo tooling can confer; the gate fails without blocking until an admin lists it |
| Merge-until specialist-skill firing is declared up front, generalized beyond `drafting-a-skill` | New `planning-a-branch-from-an-issue` Output section "Skill Invocation Plan": for each ACM row, list conditional specialist skills (confirmed scope: `drafting-a-skill`, `diagnosing-a-failure`, `stop-and-replan`) likely to fire before merge and why | Add the Output section to `planning-a-branch-from-an-issue/SKILL.md`; prose plus one new section, no new machinery | Re-run the #1794/#1795 case through the new section; confirm `drafting-a-skill`'s firing likelihood is declared correctly | Declaration alone is inert without row 1's CI gate / row 3's screening actually checking against it -- both now scoped to cover it. Scope-expansion to always-mandatory skills (`review-persona`, `reviewing-an-artifact`) was considered and declined. |
| `docs/gitapex/plans/` task lists are traceable to their source ACM by more than human inspection | Content-level linkage already exists (verbatim Planned-ops quoting, full ACM transcription); the gap is CI-gate coverage issue #1700 left unresolved for `plans/` | Register a `docs/gitapex/plans/*.md` target entry in `.gitapex/ssot.json` (mirroring the `docs/gitapex/specs/*.md` entry issue #1700 already added); add a minimal shape gate checking a plans file names its source Issue URL and each task cites `Source ACM rows` -- existence-only, matching skill-audit-disclosure's disclosure-not-soundness precedent | Gate unit tests plus a live demonstration: a plans file missing the Issue URL or `Source ACM rows` fails, a well-formed one passes | Responsibility for generating `docs/gitapex/plans/` stays with `executing-a-branch-plan` Step 3; `docs/superpowers/plans/`'s 27 legacy files stay frozen, out of scope |

## Task Decomposition

File-ownership map (mechanized via `gitapex_check_file_ownership_conflicts.py`): no conflicts found across the four tasks below. Interface-dependency map (model judgment): none of the four tasks consumes another's produced interface -- Task 1's CI gate discriminates by diff path only, never by Task 2/3's actual prose content, so it has no read dependency on either. All four tasks are therefore assigned to a single wave.

### Task 1: Extend skill-audit-disclosure gate for `drafting-a-skill` invocation + `references/**` applicability

Source ACM row: row 1 ("Skill-touching PRs carry machine-checkable invocation evidence").

Quoted Planned ops:
> Extend the existing `gitapex_gate_skill_audit_disclosure.py`: add a new `_ProcessDisclosureCheck` row (e.g. `drafting-a-skill-invocation-disclosure`) to its `_PROCESS_DISCLOSURE_CHECKS` registry, following the same pattern as its six existing checks (#517/#565/#673/#998) -- not a standalone script, per this repository's own "one place where a flag rule can change" precedent (#874). Register the applicability signal in `gitapex_compute_skill_audit_flags.py` and add `skills/**/references/**` to `skill-audit-gate.yml`'s trigger paths.

Files: `.github/scripts/gitapex_gate_skill_audit_disclosure.py`, `.github/scripts/gitapex_compute_skill_audit_flags.py`, `.github/workflows/skill-audit-gate.yml`, plus regression tests (`tests/test_gitapex_gate_skill_audit_disclosure.py`, `tests/test_gitapex_compute_skill_audit_flags.py`, `tests/test_gitapex_skill_audit_gate_workflow_wiring.py`).

Delegates to: none (checker-script edit only, not a `SKILL.md`).

Irreversible: no.

### Task 2: Widen `drafting-a-skill` trigger + add Skill Invocation Plan Output section to `planning-a-branch-from-an-issue`

Source ACM rows: row 2 ("Behavior-shaping references edits no longer fall through the trigger", the `planning-a-branch-from-an-issue` half) and row 5 ("Merge-until specialist-skill firing is declared up front").

Quoted Planned ops (row 2):
> Edit the `drafting-a-skill` delegation clauses in both pipeline skills to cover `references/**`; keep the change to prose plus ACM rows, no new machinery.

Quoted Planned ops (row 5):
> Add the Output section to `planning-a-branch-from-an-issue/SKILL.md`; prose plus one new section, no new machinery.

Files: `skills/planning-a-branch-from-an-issue/SKILL.md`.

Delegates to: `drafting-a-skill` (this task edits an existing `SKILL.md`).

Irreversible: no.

### Task 3: Widen `drafting-a-skill` trigger + add per-task delegation citation requirement to `executing-a-branch-plan`

Source ACM rows: row 2 (the `executing-a-branch-plan` half) and row 3 ("Delegation is verifiable, not prose-only").

Quoted Planned ops (row 2):
> Edit the `drafting-a-skill` delegation clauses in both pipeline skills to cover `references/**`; keep the change to prose plus ACM rows, no new machinery.

Quoted Planned ops (row 3):
> Add the citation requirement at two points in `executing-a-branch-plan`: Step 3 (Task Decomposition) states, per task, which specialist skill(s) it delegates to (or an explicit none); Step 6 (merge-back screening) verifies that citation or an explicit waiver is present before merging that task's commit -- same fail-closed shape as the existing commit-provenance scan.

Files: `skills/executing-a-branch-plan/SKILL.md`.

Delegates to: `drafting-a-skill` (this task edits an existing `SKILL.md`).

Irreversible: no.

### Task 4: Close the `docs/gitapex/plans/` CI-gate gap

Source ACM row: row 6 ("`docs/gitapex/plans/` task lists are traceable to their source ACM by more than human inspection").

Quoted Planned ops:
> Register a `docs/gitapex/plans/*.md` target entry in `.gitapex/ssot.json` (mirroring the `docs/gitapex/specs/*.md` entry issue #1700 already added); add a minimal shape gate checking a plans file names its source Issue URL and each task cites `Source ACM rows` -- existence-only, matching skill-audit-disclosure's disclosure-not-soundness precedent.

Files: `.gitapex/ssot.json`, new `.github/scripts/gitapex_gate_plans_file_shape.py`, new `.github/workflows/plans-file-shape-gate.yml`, plus regression tests.

Delegates to: none (new checker script, not a `SKILL.md`).

Irreversible: no.

## Row 4 ("No harness-specific machinery required")

Not decomposed into its own task -- it is a cross-cutting constraint verified against Tasks 1-4's own combined scope at Step 8's review, not a task with its own file-level Planned ops.

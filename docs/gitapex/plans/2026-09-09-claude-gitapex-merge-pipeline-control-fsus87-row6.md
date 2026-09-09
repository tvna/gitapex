# Branch Plan: claude/gitapex-merge-pipeline-control-fsus87 (row 6 resumption)

Issue: https://github.com/tvna/gitapex/issues/1796
Base: main

This is a resumed-execution task list for issue #1796's own row 6 only.
Rows 1 (done, merged as commits `e23313e4`/`b459457a`/`7efe65d6`) and
rows 2/3/5 (blocked on issue #1822, which merged separately and closed)
are out of scope for this task list; see
`docs/gitapex/plans/2026-09-05-claude-gitapex-merge-pipeline-control-fsus87.md`
for the original four-task decomposition this one continues from.

## Acceptance Criteria Map (row 6 only, quoted from issue #1796's current body)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `docs/gitapex/plans/` task lists are traceable to their source ACM by more than human inspection | Content-level linkage already exists (verbatim Planned-ops quoting, full ACM transcription); the gap is CI-gate coverage issue #1700 left unresolved for `plans/` | Register a `docs/gitapex/plans/*.md` target entry in `.gitapex/ssot.json` (mirroring the `docs/gitapex/specs/*.md` entry issue #1700 already added); add a minimal shape gate checking a plans file names its source Issue URL and each task cites `Source ACM rows` -- existence-only, matching skill-audit-disclosure's disclosure-not-soundness precedent | Gate unit tests plus a live demonstration: a plans file missing the Issue URL or `Source ACM rows` fails, a well-formed one passes | Responsibility for generating `docs/gitapex/plans/` stays with `executing-a-branch-plan` Step 3; `docs/superpowers/plans/`'s 27 legacy files stay frozen, out of scope |

## Task Decomposition

File-ownership map (mechanized via `gitapex_check_file_ownership_conflicts.py`): single task, no conflicts to compute. Interface-dependency map: none (single task). One task, one wave.

### Task 1: `docs/gitapex/plans/` traceability shape gate

Source ACM row: row 6 ("`docs/gitapex/plans/` task lists are traceable to their source ACM by more than human inspection").

Quoted Planned ops:
> Register a `docs/gitapex/plans/*.md` target entry in `.gitapex/ssot.json` (mirroring the `docs/gitapex/specs/*.md` entry issue #1700 already added); add a minimal shape gate checking a plans file names its source Issue URL and each task cites `Source ACM rows` -- existence-only, matching skill-audit-disclosure's disclosure-not-soundness precedent

Files: `.github/scripts/gitapex_gate_plans_traceability.py` (new), `.github/workflows/plans-traceability-gate.yml` (new), `.gitapex/ssot.json` (new registry entry), `tests/test_gitapex_gate_plans_traceability.py` (new).

Pre-existing-corpus note (confirmed live before dispatch, informs the new gate's own design -- diff-touched files only, never a retroactive full-corpus scan): of the 20 files currently under `docs/gitapex/plans/`, 5 lack an `Issue: <url>` line and 11 lack any `Source ACM rows?:` citation. A gate that scanned the whole corpus unconditionally would fail CI on unrelated PRs; scope checks to files the PR's own diff actually adds or modifies.

Delegates to: none (checker-script/workflow/registry edit only, no `SKILL.md` touched).

Irreversible: no.

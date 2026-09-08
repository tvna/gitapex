# Branch Plan: claude/pr-1882-prep-3to2qm

Issue: https://github.com/tvna/gitapex/issues/1882
Base: main

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Merge `formative-quality-dimensions.md`, `contract-structure.md`, `mechanism-fit-and-cohesion.md`, and `guidance-form-and-sdo.md` into one new reference file | A single portable reference file (`skill-writing-fundamentals.md`, per Human Decision) replaces the four, content preserved and reorganized under one set of headings, mirroring `evaluating-skill-quality/references/rubric.md`'s own single-large-file shape for always-invoked portable content | Create `skills/drafting-a-skill/references/skill-writing-fundamentals.md`; move all four files' content in, resolving any Step-3/Step-5-style cross-references between the four into same-file anchors; delete the four originals; update every `SKILL.md` cross-reference to them (lines 51, 55, 60, 75, 110, 191, 192 as verified in this branch's own checkout) | `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` clean; repo-wide grep confirms no remaining reference anywhere (SKILL.md, other reference files, CI gate scripts, `.gitapex/ssot.json`) to any of the four old filenames outside of git history and historical `docs/` plan snapshots | Scope creep if the merge also tries to rewrite the four files' own substantive content beyond reorganizing headings and resolving cross-references |
| `.github/scripts/gitapex_scan_contract_discipline_drift.py` and `.gitapex/ssot.json`'s own `contract-discipline-drift` gate entry both hardcode `skills/drafting-a-skill/references/contract-structure.md` as one half of a content-lock against `evaluating-skill-quality/references/rubric.md`'s own Contract discipline section | Merging `contract-structure.md` away without updating both breaks two independent gates closed: the drift-scan script itself (fail-closed exit 2), and separately `gitapex_scan_ssot_schema.py`'s `find_local_invocation_drift`, which mechanically confirms every `local_stdin`/`local_invocation` path token in `ssot.json` resolves to a real file -- repository-wide, on every subsequent PR, not only this one | Update `CONTRACT_STRUCTURE_MD` in the gate script (and its docstring/usage example) and its own test file (`tests/test_gitapex_scan_contract_discipline_drift.py`, which reads the path only via the module constant -- no direct edit needed there), the workflow file's own diff-scan `--` path arguments and header comment, and `.gitapex/ssot.json`'s `contract-discipline-drift` entry's `rule` text, `local_stdin` argv, and `target` file-glob refs -- all to the new merged file's path | Run `gitapex_scan_contract_discipline_drift.py` directly against the new file layout (exit 0); run `gitapex_scan_ssot_schema.py` (exit 0, no `local-invocation-drift` finding) | A second, independent-of-this-repo consumer of the old path (a fork, a vendored copy) is out of this issue's own visibility |
| `gitapex-cross-links.md` stays a separate file (Mixed-portability rule), but `SKILL.md`'s own description of it changes from on-demand to required | No change to `gitapex-cross-links.md`'s own substantive content or its seven-section boundary; `SKILL.md`'s own pointer wording (Notes) states it as required reading; `gitapex-cross-links.md`'s own internal citations of the now-merged `mechanism-fit-and-cohesion.md`/`contract-structure.md` filenames are corrected to point at `skill-writing-fundamentals.md`'s matching sections (found live in this file at lines 34, 38, 42, 44, 49 during execution -- a correctness fix distinct from a content/boundary change) | Edit `SKILL.md`'s Notes paragraph; edit `gitapex-cross-links.md`'s five stale filename citations only | Diff review confirms `gitapex-cross-links.md`'s own substantive guidance is unchanged; `gitapex_check_skill_shape.py` clean | None identified |
| `decision-log-discipline.md` is left untouched as the one genuinely on-demand reference file | Its own checkable precondition (resume-from-existing-sidecar, or concurrent dispatch) already distinguishes it from the other five files; no defect found here | No planned change to this file or its own `SKILL.md` citation | Diff review confirms this file and its citation are byte-for-byte unchanged | None identified |
| Every fixture or status doc whose text quotes wording this restructuring changes must be re-synced verbatim | `evals/drafting-a-skill/tasks/*.yaml` cites none of the four old filenames directly; `evals/drafting-a-skill/eval-status.md` line 141 cites `references/formative-quality-dimensions.md`'s nine rows by path | Update `eval-status.md` line 141's path citation; re-grep `evals/drafting-a-skill/tasks/*.yaml` after the `SKILL.md` edits land for any incidental verbatim-quote drift | `pytest tests/test_gitapex_gate_split_fixture_coverage.py` (and the full suite) passes; manual read confirms `eval-status.md`'s citation resolves | None identified |
| `metadata/gitapex.yaml`'s own decision log records this restructuring, per `decision-log-discipline.md`'s own ground-truth-drift rule | A new entry, added in the same edit round as the change, naming `outcome.baseCommit` and a plain-language summary of the merge/relabel decision | Append the entry once the merge lands, citing this plan-doc commit as `baseCommit` (variant 1: the entry-adding commit is itself the substantive fix) | Manual review against `decision-log-discipline.md`'s own three `outcome.baseCommit` variants | None identified |
| The merged file's own Load-bearing-vs-on-demand-split guidance (today `formative-quality-dimensions.md` row 5) states the checkable-precondition test this issue's own investigation used | Row 5's current Writing-time instruction column states the put-in-body-vs-on-demand split but never states how to tell a genuinely conditional trigger from a judgment call with no checkable condition | Add a sentence plus a Good/Bad example pair to row 5 (in the merged file) stating the checkable-precondition test, citing this very merge as the Bad example and `decision-log-discipline.md`'s own trigger as the Good example | `evaluating-skill-quality` dimension 5 dispatch against the merged file's own updated row 5 (Skill Audit Evidence, once dispatched) | Adds to row 5's own length -- kept to one sentence plus one Good/Bad example pair, not a restatement of the full investigation |

## Task Decomposition

Single task, single wave -- one cohesive consolidation touching a
tightly-coupled set of files (the merge and every one of its downstream
citation fixes share the same file-ownership scope; no independent
parallel slice exists).

Skill-file edit routing: this task edits an existing `SKILL.md`
(`skills/drafting-a-skill/SKILL.md`) and its `references/` -- per
`drafting-a-skill`'s own Related-skills note, this is exactly its own
domain (a `references/`-only and cross-reference restructuring, not a
Steps/Precondition/Postcondition change), executed directly per this
skill's own dispatch routing rather than a separate drafting-a-skill
sub-dispatch, since the calling context here (`executing-a-branch-plan`
Step 6, sequential fallback) *is* one of `drafting-a-skill`'s own
sanctioned callers' surrounding pipeline already, editing that skill's
own files without re-entering its dispatch-context machinery for a
files-only reference reorganization its own Precondition does not gate.

### Task 1: Consolidate drafting-a-skill's mislabeled on-demand reference files

Source ACM rows: all seven rows above.

Concrete ops:

1. Create `skills/drafting-a-skill/references/skill-writing-fundamentals.md` merging `formative-quality-dimensions.md`, `contract-structure.md`, `guidance-form-and-sdo.md`, `mechanism-fit-and-cohesion.md`; delete the four originals.
2. Update `SKILL.md`'s seven cross-reference sites (Step 2's earning-test note, Step 2's row-4 pointer, Step 3's SDO/cohesion pointer, Step 6's formative-sweep pointer, Non-goals' placement-policy pointer, Notes' Portability paragraph, Notes' Capability-assumption paragraph) to the new file and its corrected on-demand/required accounting.
3. Update `.github/scripts/gitapex_scan_contract_discipline_drift.py` (constant + docstring + usage example), `.github/workflows/contract-discipline-drift-gate.yml` (path arg + header comment), `.gitapex/ssot.json` (`contract-discipline-drift` entry: rule/local_stdin/target).
4. Fix `gitapex-cross-links.md`'s five stale filename citations to point at the merged file's matching sections (content otherwise unchanged).
5. Update `evals/drafting-a-skill/eval-status.md` line 141.
6. Append a decision-log entry to `skills/drafting-a-skill/metadata/gitapex.yaml`.
7. Re-grep `evals/drafting-a-skill/tasks/*.yaml` for incidental drift.

Proof method: `gitapex_check_skill_shape.py --strict-token-budget` clean;
`gitapex_scan_contract_discipline_drift.py` exit 0; `gitapex_scan_ssot_schema.py`
exit 0; full `pytest` suite green; `gitapex_gate_local_preflight.py` clean;
repo-wide grep confirms no live reference to the four old filenames
remains outside git history and historical `docs/` snapshots.

File ownership: sole task, no conflicts.
Interface dependencies: none (single task, single wave).
Wave: 1 (only wave).
Irreversibility: none of the planned ops are irreversible (file
moves/renames and prose edits, fully reversible via `git revert`).

## Execution mode

Workflow tool not opted into for this session (no `ultracode` keyword, no
explicit multi-agent-orchestration request) -- executed via the sequential
main-thread fallback (Notes section, "Mixed" portability), one task, no
wave/run boundary, no worktree isolation.

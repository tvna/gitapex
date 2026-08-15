# Rename the stale vetting-attack-surface delegate reference to scanning-attack-surfaces

Source: https://github.com/tvna/gitapex/issues/943
Branch: claude/gitapex-pr-943-lk37zg

## Facts (independently re-verified against live repo state, not adopted from the issue's draft alone)

- `skills/vetting-attack-surface` does not exist. `skills/scanning-attack-surfaces`
  exists, and its `metadata/gitapex.yaml:167` records `renamedFrom: vetting-attack-surface`
  (rename itself decided under issue #846, `metadata/gitapex.yaml:110-112`).
- `skills/evaluating-deterministic-gate-quality/SKILL.md:3`,
  `references/grading-procedure.md:96`, and `references/output-schema.json:182`
  still name `vetting-attack-surface`.
- `evals/evaluating-deterministic-gate-quality/tasks/delegation-recommendation-exposure-shaped-finding.yaml`
  pins the stale name in `name` (line 2), the `output_contains_near` assertion
  (line 52), and the `output_not_contains_near` ban (line 57).
- `metadata/gitapex.yaml:669-674` (`skillDependencies.relatedTo`) already lists
  `scanning-attack-surfaces` -- fixed mechanically under issue #846. Only the
  prose and the coupled fixture are stale.
- Baseline (pre-edit) gate runs, this session: `gitapex_check_skill_shape.py`
  60/60 PASS; `gitapex_scan_skill_metadata_schema.py` "No skill metadata schema
  drift found."

## Decision (owner's own "Recommended" option in the issue)

Option 1: update the name in all four places (three prose artifacts plus the
coupled fixture), and add a new sidecar decision entry recording it. Not
option 2 (deliberately keep the stale name) -- the issue's own text marks
option 1 "Recommended," and the human operator's in-session instruction was to
create and progress this PR now.

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Delegation step can recommend a real skill | Rename vetting-attack-surface -> scanning-attack-surfaces in the 3 prose artifacts | Edit skills/evaluating-deterministic-gate-quality/SKILL.md line 3 (frontmatter description, phrase "it routes an exposure or privilege finding to vetting-attack-surface rather than analysing one itself"), references/grading-procedure.md line 96 ("Route an exposure- or privilege-shaped finding to `vetting-attack-surface`."), references/output-schema.json line 182 (recommendedTarget description: "vetting-attack-surface for an exposure- or privilege-shaped finding") | evals/scripts/gitapex_lint_fixture_assertions.py + fixture's own confirmed-recommendation shape | Portable-declared artifact; this is prose only, not an API, so no consuming-repo break |
| Coupled fixture moves with prose | Same commit, name/assertion/ban all updated together | Edit evals/evaluating-deterministic-gate-quality/tasks/delegation-recommendation-exposure-shaped-finding.yaml: line 2 `name:` field, line 52 assertion value "vetting-attack-surface" -> "scanning-attack-surfaces", line 57 ban value "not vetting-attack-surface" -> "not scanning-attack-surfaces" | Run `python3 evals/scripts/gitapex_lint_fixture_assertions.py` after edit -- must show no new negation-trap/paraphrase-drift/unsatisfiable-pair warnings for this fixture | Ban rewording could trip check_negation if grading-procedure.md now contains "not scanning-attack-surfaces" verbatim -- verify via the linter, don't just inspect |
| No dangling-reference gate regresses | Shape + schema checks stay green | No code changes needed -- skillDependencies.relatedTo at metadata/gitapex.yaml:672-674 already lists scanning-attack-surfaces (fixed under issue #846) | Re-run gitapex_check_skill_shape.py (baseline: 60/60) and gitapex_scan_skill_metadata_schema.py (baseline: no drift) after edits -- must stay clean | None identified |
| Decision is recorded | Sidecar gets a NEW entry superseding lines 561/564's rationale, not a rewrite of them | Append a new `kind: decision` list entry under skills/evaluating-deterministic-gate-quality/metadata/gitapex.yaml's spec.references list (same shape as the entries around lines 556-583), anchored to https://github.com/tvna/gitapex/issues/943, stating that the caveat at line 561 and decision at line 564 are now superseded | Entry present, cites #943 by canonical URL, explicitly says it supersedes line 561/564 | No inline forward-pointer convention exists elsewhere in this file (checked: only "supersed" hit in this file, line 389, is a backward-reference from the new entry, not a forward pointer on the old one) -- followed that precedent, entry added at the end only |

## File-ownership map

Single task; no other task exists, so no cross-task conflicts.

## Interface-dependency map

N/A -- single task, no cross-task producer/consumer relationship to compute.

## Irreversibility classification

Task 1: reversible. Ordinary tracked-file text edits (prose, JSON, YAML), no
schema migration, no deletion, fully revertible via git.

## Wave assignment

Wave 1: {Task 1}.

## Task 1: rename the delegate reference across prose + coupled fixture + sidecar

Satisfies ACM rows 1, 2, 3 (verification-only, no separate edit), 4.

Files:
- `skills/evaluating-deterministic-gate-quality/SKILL.md`
- `skills/evaluating-deterministic-gate-quality/references/grading-procedure.md`
- `skills/evaluating-deterministic-gate-quality/references/output-schema.json`
- `skills/evaluating-deterministic-gate-quality/metadata/gitapex.yaml`
- `evals/evaluating-deterministic-gate-quality/tasks/delegation-recommendation-exposure-shaped-finding.yaml`

Quoted Planned ops (verbatim from the ACM above, row order 1/2/3/4):
1. "Edit skills/evaluating-deterministic-gate-quality/SKILL.md line 3
   (frontmatter description, phrase "it routes an exposure or privilege
   finding to vetting-attack-surface rather than analysing one itself"),
   references/grading-procedure.md line 96 ("Route an exposure- or
   privilege-shaped finding to `vetting-attack-surface`."),
   references/output-schema.json line 182 (recommendedTarget description:
   "vetting-attack-surface for an exposure- or privilege-shaped finding")"
2. "Edit evals/evaluating-deterministic-gate-quality/tasks/delegation-
   recommendation-exposure-shaped-finding.yaml: line 2 `name:` field, line 52
   assertion value "vetting-attack-surface" -> "scanning-attack-surfaces",
   line 57 ban value "not vetting-attack-surface" -> "not
   scanning-attack-surfaces""
3. "No code changes needed -- skillDependencies.relatedTo at
   metadata/gitapex.yaml:672-674 already lists scanning-attack-surfaces
   (fixed under issue #846)"
4. "Append a new `kind: decision` list entry under
   skills/evaluating-deterministic-gate-quality/metadata/gitapex.yaml's
   spec.references list (same shape as the entries around lines 556-583),
   anchored to https://github.com/tvna/gitapex/issues/943, stating that the
   caveat at line 561 and decision at line 564 are now superseded"

Numbered steps:
1. `SKILL.md` line 3: replace the one occurrence of "vetting-attack-surface"
   with "scanning-attack-surfaces" (frontmatter description only).
2. `references/grading-procedure.md` line 96: replace the one occurrence of
   `` `vetting-attack-surface` `` (backtick-wrapped) with
   `` `scanning-attack-surfaces` ``.
3. `references/output-schema.json` line 182: replace "vetting-attack-surface
   for an exposure- or privilege-shaped finding" with
   "scanning-attack-surfaces for an exposure- or privilege-shaped finding"
   inside the `recommendedTarget.description` string. Keep the file valid
   JSON.
4. `evals/.../delegation-recommendation-exposure-shaped-finding.yaml`:
   - line 2 `name:` field: replace "vetting-attack-surface" with
     "scanning-attack-surfaces".
   - line 52 (`output_contains_near` assertion): replace
     `"vetting-attack-surface"` with `"scanning-attack-surfaces"`.
   - line 57 (`output_not_contains_near` ban): replace
     `"not vetting-attack-surface"` with `"not scanning-attack-surfaces"`.
   Keep the file valid YAML.
5. `metadata/gitapex.yaml`: append one new list entry to the end of
   `spec.references` (immediately before the `skillDependencies:` key),
   4-space list-item indentation matching every existing entry, `kind:
   decision`, `anchor: "https://github.com/tvna/gitapex/issues/943"`,
   `summary:` stating in this skill's own established voice that the caveat
   at line 561 and the decision at line 564 are now superseded: the rename
   this repository tracked under issue #846 is no longer speculative, so the
   delegation step can name a confirmable delegate again, and the three
   prose artifacts plus the coupled fixture were updated to
   `scanning-attack-surfaces` accordingly. Keep the file valid YAML,
   double-quoted summary string, matching this file's own escaping
   convention (embedded `"` as `\"`, embedded `'` unescaped).
6. Do NOT touch any other `vetting-attack-surface` mention anywhere else in
   the repository (Non-goals -- these are historical decision-log/eval-status
   prose under other issues, not live pointers).
7. Run the verification commands below and confirm every one passes before
   returning.

Proof method / verification commands (run from the repository root, `.venv`
activated):
- `python3 evals/scripts/gitapex_lint_fixture_assertions.py --tasks-glob "evals/evaluating-deterministic-gate-quality/tasks/*.yaml" --skill skills/evaluating-deterministic-gate-quality/SKILL.md --rubric skills/evaluating-deterministic-gate-quality/references/grading-procedure.md`
- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py skills/evaluating-deterministic-gate-quality --allowed-root skills`
- `python3 .github/scripts/gitapex_scan_skill_metadata_schema.py`
- `python3 -c "import json; json.load(open('skills/evaluating-deterministic-gate-quality/references/output-schema.json'))"`
- `python3 -c "import yaml; yaml.safe_load(open('evals/evaluating-deterministic-gate-quality/tasks/delegation-recommendation-exposure-shaped-finding.yaml'))"`
- `python3 -c "import yaml; yaml.safe_load(open('skills/evaluating-deterministic-gate-quality/metadata/gitapex.yaml'))"`
- `grep -rn "vetting-attack-surface" skills/evaluating-deterministic-gate-quality/SKILL.md skills/evaluating-deterministic-gate-quality/references/grading-procedure.md skills/evaluating-deterministic-gate-quality/references/output-schema.json evals/evaluating-deterministic-gate-quality/tasks/delegation-recommendation-exposure-shaped-finding.yaml` (must return no matches)

Known environment limitation, disclosed rather than papered over: the eval
fixture itself is graded by an LLM executor (`copilot-sdk` /
`claude-sonnet-5`, per `evals/evaluating-deterministic-gate-quality/eval.yaml`),
and the `waza` eval runner was `SKIPPED` at this session's startup (not
provisioned in this environment). The deterministic lints above can run and
must pass; the actual graded eval trial cannot be executed end-to-end here.
Stated as residual risk / follow-up, not claimed as proven.

## Governance-file screening note (pre-registered, not a surprise discovery)

`skills/executing-a-branch-plan/scripts/gitapex_check_canonical_governance_paths.py`
classifies `SKILL.md` and `metadata/gitapex.yaml` as `governance` --
`screening-a-low-trust-contribution` check 3 ("any existing skills/*/SKILL.md
or its metadata/gitapex.yaml") hard-flags any diff touching them,
unconditionally, "regardless of how reasonable the surrounding contribution
looks." This is expected and unavoidable for this task -- the issue is
literally about fixing SKILL.md/sidecar content -- so it is disclosed here in
advance rather than treated as a stop condition discovered by surprise at
step 6. Per that skill's own Stop boundaries ("report the flags and hand the
decision to a human"), the produced diff will be presented to the human
operator (present in this same session) for explicit sign-off before merge,
satisfying step 1's own "explicit confirmation from the active human operator
in the conversation itself" mechanism for resolving the flag.

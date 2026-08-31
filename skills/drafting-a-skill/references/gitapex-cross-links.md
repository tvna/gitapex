# gitapex-specific cross-links

Loaded when this copy of the skill's own files lives in the gitapex repository -- the same condition, and the same reasoning, as `auditing-agent-product-scope/references/gitapex-cross-links.md`'s and `scanning-attack-surfaces/references/gitapex-cross-links.md`'s own opening notes. A copy vendored into a different repository drops this file and substitutes that repository's own equivalent conventions where they exist, omitting a cross-link where they don't, never fabricating one.

## Contents

1. [Deterministic-checker commands (Step 6)](#deterministic-checker-commands-step-6)
2. [Metadata schema and shape checker](#metadata-schema-and-shape-checker)
3. [PR-body skill-audit disclosure convention](#pr-body-skill-audit-disclosure-convention)
4. [If the draft's own bundled script would be a deterministic gate](#if-the-drafts-own-bundled-script-would-be-a-deterministic-gate)

## Deterministic-checker commands (Step 6)

```
python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py --allowed-root <repo-root> skills/<new-skill-name>
python3 skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py skills/<new-skill-name>
```

Both are read-only against the target directory; run them once the draft directory exists on disk, before Step 7's handoff, and fix every finding they report -- Step 7 does not run either check itself.

## Metadata schema and shape checker

`skills/evaluating-skill-quality/references/skill-metadata.schema.json` is the authoritative schema for `metadata/gitapex.yaml`. Validate a draft's sidecar against it before Step 6 (the shape checker above also reads this schema, but validating directly first gives a faster failure loop while still drafting).

## PR-body skill-audit disclosure convention

A PR that adds or modifies a `skills/**/SKILL.md` file must carry a `## Skill audit evidence` section disclosing a verdict (or an explicit `WAIVED: <reason>`) for both `battle-testing-a-skill` and `evaluating-skill-quality` -- enforced by `.github/workflows/skill-audit-gate.yml` via `.github/scripts/gitapex_gate_skill_audit_disclosure.py`. A brand-new `SKILL.md`'s frontmatter `description:` line counts as changed (it did not exist before), so the `battle-testing-a-skill` line may **not** be disclosed as `WAIVED` -- a real `PASS`/`FAIL`/`INDETERMINATE` verdict is required. `planning-a-branch-from-an-issue`'s own Step 9 and `references/github-issue-workflow.md` already carry this convention for anyone routing through that skill first; it is repeated here for a drafting agent invoked directly, without that routing.

## If the draft's own bundled script would be a deterministic gate

A drafted skill whose own bundled script enforces an invariant on other files (not just checks the drafted skill's own shape) is a deterministic gate in this repository's own sense, and should be registered in `.gitapex/ssot.json`'s `gates[]` array -- see any `self-governance`-cluster entry there (for example `contract-axis-vocabulary-drift`, `skill-quality-rubric-vocabulary-drift`) for the field shape, and `.github/scripts/gitapex_detect_changed_gate_scripts.py`'s naming convention (`.github/scripts/gitapex_gate_*.py` or `.github/scripts/gitapex_scan_*.py`) for how such a script gets picked up by `skill-audit-gate.yml`'s own disclosure requirement automatically, before it is even registered. This is a rare case for a freshly drafted skill -- most bundled scripts check only their own skill's shape, per `references/mechanism-fit-and-cohesion.md`'s bundled-script placement policy -- but when it applies, route through `evaluating-deterministic-gate-quality` directly before shipping it (this skill's own former Step 2 vehicle-selection redirect now lives in `eliciting-a-design`'s Agentic operation mechanism-fit check -- see that skill's own Checklist item 4 -- since this skill only drafts once that call has already landed on Skill).

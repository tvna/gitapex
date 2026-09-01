# gitapex-specific cross-links

Loaded when this copy of the skill's own files lives in the gitapex repository -- the same condition, and the same reasoning, as `auditing-agent-product-scope/references/gitapex-cross-links.md`'s and `scanning-attack-surfaces/references/gitapex-cross-links.md`'s own opening notes. A copy vendored into a different repository drops this file and substitutes that repository's own equivalent conventions where they exist, omitting a cross-link where they don't, never fabricating one.

## Contents

1. [Deterministic-checker commands (Step 6)](#deterministic-checker-commands-step-6)
2. [Metadata schema and shape checker](#metadata-schema-and-shape-checker)
3. [PR-body skill-audit disclosure convention](#pr-body-skill-audit-disclosure-convention)
4. [If the draft's own bundled script would be a deterministic gate](#if-the-drafts-own-bundled-script-would-be-a-deterministic-gate)
5. [Design-by-Contract framing citation](#design-by-contract-framing-citation)
6. [Cohesion-ownership cross-links](#cohesion-ownership-cross-links)
7. [Shared bundled-script parent policy: this repository's worked application](#shared-bundled-script-parent-policy-this-repositorys-worked-application)

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

## Design-by-Contract framing citation

`references/contract-structure.md`'s Design-by-Contract framing is the same framing `evaluating-skill-quality`'s own review procedure already applies to itself: `skills/evaluating-skill-quality/references/rubric.md`'s "## Contract discipline" section. Both of the verbatim quotes `references/contract-structure.md` carries -- the fault-attribution principle ("A precondition violation indicates a bug in the client (caller). ... A postcondition violation is a bug in the supplier (the routine).") and the never-both "absolute rule" ("either you have the condition in the [precondition], or you have it in an If instruction in the [routine's] body ... but never in both.") -- are taken from that section's own wording.

## Cohesion-ownership cross-links

Two facts `references/mechanism-fit-and-cohesion.md` points here for:

- **The former Step 2 redirect's owner.** `eliciting-a-design` owns the redirect-target judgment `references/mechanism-fit-and-cohesion.md` once carried for `drafting-a-skill`'s own former Step 2 (see <https://github.com/tvna/gitapex/issues/1619>: the Agentic operation mechanism-fit vehicle-selection gate, including the "this isn't a skill, redirect to X instead" criteria, moved upstream into that skill entirely) -- see that skill's own body for the current version of that judgment, not `references/mechanism-fit-and-cohesion.md`.
- **The cohesion check's and Blind spot pass's exact-owner wording.** `evaluating-skill-quality`'s own rubric (`skills/evaluating-skill-quality/references/rubric.md`) states plainly, for the cohesion check: "This check has exactly one owner, per Contract discipline's 'never both' rule: it decides the whole-artifact boundary once, here." And for its own Blind spot pass: it runs as "a precondition step (`SKILL.md`'s Procedure step 2, alongside the Agentic operation mechanism-fit checks)" of `evaluating-skill-quality`'s own procedure.

## Shared bundled-script parent policy: this repository's worked application

Two repository-state facts `references/mechanism-fit-and-cohesion.md`'s shared bundled-script parent placement policy points here for:

- **Tier 1's stability census.** No skill in this repository currently declares `lifecycle: stable` explicitly (only `experimental` is ever declared; stable is today's implicit default for everything else) -- too few explicit declarations to gate on the stability axis, which is why that policy's tier 1 stays a preference, not a blocker, here.
- **The policy's worked application, and the mechanization deferral.** `evaluating-skill-quality`'s own bundled checkers (`gitapex_check_skill_shape.py`, `gitapex_scan_execution_requirements_drift.py`, which Step 6 runs against every draft) already satisfy that policy under all three tiers today: that skill is this repository's de facto stable, closure-consistent owner of "does a skill directory have the right shape," so Step 6 reaches into its `scripts/` directory rather than vendoring a copy. The policy's own future blocking-gate threshold, and whether it should be mechanized into `gitapex_check_skill_shape.py` itself, are explicitly out of scope -- deferred to a future issue, once explicit `stable` declarations are common enough in this repository to judge readiness (see this skill's own `metadata/gitapex.yaml` `references` decision log, `kind: elision`).

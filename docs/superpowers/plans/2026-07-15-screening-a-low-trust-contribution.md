# screening-a-low-trust-contribution Implementation Plan

**Goal:** Add a gitapex skill that inspects a PR/issue's diff and metadata
for contribution-level threats from an unknown or low-trust author --
distinct from `untrusted-input-triage`, which triages a single piece of
externally-authored *text*, not a diff.

**Tracking:** #83 (triage cluster). **This skill's issue:** #86.

**Architecture:** One new skill directory
`skills/screening-a-low-trust-contribution/` holding a platform-general
`SKILL.md`. Deferred to a future cycle (see Task 2 onward); this cycle
only lands the design docs (Task 1).

## Concrete checks (fixed by this design, not left abstract)

- **Workflow-file edits.** Any diff touching `.github/workflows/**` or
  `.gitlab-ci.yml`/`.gitlab/**` from a low-trust author is a hard flag --
  workflow changes can alter what CI does with repo secrets.
- **Hook/script changes.** Diffs touching `hooks/**`, `.github/scripts/**`,
  or any `skills/*/scripts/**` -- these execute with the repo's own
  privileges once merged.
- **Dependency additions.** New entries in `pyproject.toml`/`uv.lock`,
  `package.json`, or similar -- flag new transitive deps, not just direct
  ones (mirrors the not-yet-built `dependency-drift-audit` idea from the
  original gap analysis, but scoped here to a single incoming diff, not a
  standing audit).
- **Typosquat patterns.** Package/action names one edit-distance from a
  well-known name (e.g. `actons/checkout` vs `actions/checkout`).
- **Instruction-bearing filenames or content.** Any new file whose name or
  content reads as an attempt to inject instructions into a future
  agent's context (this repo's own untrusted-input trust-boundary
  principle, applied to the diff surface rather than issue/PR text).

## Relationship to other skills (co-firing, stated explicitly)

When the fresh arrival is from an unknown or low-trust author, this skill
and `responding-to-a-fresh-arrival` are both expected to fire on the same
event -- this skill handles diff/metadata threat screening, the other
handles content/response. Apply both; neither substitutes for the other.
(Mirrors `outward-artifact-preflight` + `explaining-the-work`'s
established co-firing pattern.)

This text is the role-swapped mirror of the shared spec's canonical
co-firing template (`docs/superpowers/specs/2026-07-15-triage-cluster-design.md`,
"Canonical co-firing text") -- copy it verbatim from *that* spec, not
from `responding-to-a-fresh-arrival`'s plan doc directly, so both sides
stay checkable against one anchor instead of drifting against each
other.

## Global constraints

- Distinct from `untrusted-input-triage` (text triage) and from
  `battle-testing-a-skill` (evaluates a SKILL.md file's own robustness,
  not an inbound contribution).
- Read-only: this skill screens and reports; it does not itself decide to
  merge, close, or reject -- that stays a human/operator decision per
  CLAUDE.md section 4's "never hand off a decision that is not
  decision-ready" (this skill exists to make it decision-ready).
- ASCII only.

---

### Task 1: Issue and design docs (this cycle)

- [x] Confirm no duplicate issue existed (`search_issues` run 2026-07-15
      -- no match).
- [x] Open #86 (`feat(skills): add screening-a-low-trust-contribution
      skill`), child of #83.
- [x] Commit this plan doc plus the shared
      `docs/superpowers/specs/2026-07-15-triage-cluster-design.md`,
      citing #86 and #83.

### Task 2: SKILL.md authoring (deferred -- future cycle)

- [ ] Write `skills/screening-a-low-trust-contribution/SKILL.md`:
      trigger/description with the disambiguation clause from the shared
      spec, the concrete checks above as the procedure, and the
      `## Relationship to other skills` section copied verbatim from the
      shared spec's canonical co-firing template (role: "diff/metadata
      threat screening").
- [ ] Before merging, diff this section against
      `responding-to-a-fresh-arrival/SKILL.md`'s own co-firing section --
      both must be the same template with only the role/other-skill-name
      swapped; re-copy from the shared spec if either has drifted.

### Task 3: Eval coverage (deferred -- future cycle, after Task 2 lands)

- [ ] `evals/screening-a-low-trust-contribution/eval.yaml` + 3 task
      fixtures, including at least one real typosquat/workflow-edit
      guardrail case.

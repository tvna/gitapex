# Skill metadata sidecar (Sub-project A: mechanism)

**Date:** 2026-07-19
**Status:** Design, awaiting review
**Scope:** Sub-project A of a four-part effort. **A** (this spec) is the
mechanism: a per-skill metadata sidecar file, migration of the existing
Portability declaration into it, a new `capability-assumption` field, and
the gate that enforces both. **B** (separate spec) adds the rubric grading
semantics that give `capability-assumption` its teeth. **C** (separate
spec) migrates maintainer-facing provenance / primary-source references
(`docs/skill-provenance.md`) into the sidecar's free-form `references`
field. **D** (separate spec) populates and gates `skillDependencies`, the
inter-skill dependency graph. B, C, and D each depend only on A and are
independent of each other.

Issues: A = #182, B = #183, C = #184. D has no issue yet; open one before
starting that work, per the issue-first rule.

A's split from B mirrors the `evaluating-skill-quality` skill's own "two
lanes" model (deterministic shape vs. probabilistic maturity): A is shape
(files, gate, field presence + valid enum), B is judgment (how a declared
level changes dimension grading).

## 1. Motivation

The repository's skill-evaluation skills deliberately run counter to
Anthropic's "concise is key" guidance: they are exhaustive so they stay
effective on constrained/weaker models, not only on a strong model with
abundant compute. That stance is defensible for a constrained target, but
when that premise does not hold, the same verbosity can over-constrain a
strong model (exactly the over-prescription risk the rubric's dimension 9
Opus check and dimension 3 already warn about).

The fix requested: make the compute/capability assumption a *selectable,
declared* property -- analogous to the existing Portability level -- so a
skill states which regime it targets and the rubric grades conciseness,
degree of freedom, and cross-model robustness *relative to that
declaration* instead of applying one fixed verbosity preference.

During design, the placement of that new declaration was decided in favour
of a **dedicated per-skill metadata sidecar file** rather than a body line
or YAML frontmatter, and the existing Portability declaration is migrated
into the same sidecar so all skill-level metadata has a single structured
home. This supersedes the body-line placement described in
`docs/superpowers/specs/2026-07-14-skill-metadata-placement-convention-design.md`.

### Why sidecar over the alternatives (recorded rationale)

- **Frontmatter (rejected):** Claude Code's frontmatter reference defines
  a fixed field set (`name`, `description`, `when_to_use`, `allowed-tools`,
  `model`, `context`, ...) and no arbitrary-metadata field. A custom
  `capability-assumption:` key is unsanctioned; while Claude Code's lenient
  parser would likely ignore it, the stricter Claude API skill-upload
  validation could reject it -- a durability risk (rubric dimension 6) on
  exactly the vendoring surface the Portability axis exists to protect.
- **Body line (viable, not chosen):** symmetric with today's Portability
  declaration and human-visible, but the operator preferred a structured,
  cleanly separated, unambiguously repository-local home.
- **Sidecar file (chosen):** structured and machine-readable, zero
  durability risk (it is not frontmatter, so no loader validates it), and
  provably behavior-neutral (see the invariant below). Cost accepted: it
  is a new per-skill file pattern with no precedent in the repo today, and
  metadata is no longer visible from the top of `SKILL.md`.

## 2. Goals

- Establish the sidecar as the **general per-skill home for
  behavior-neutral, maintainer-facing, repository-specific metadata** --
  data that must not live in the portable skill body (it does not affect
  skill behavior and a vendored consumer does not need it) but that this
  repository's maintainers do need. The two enum fields below are the
  first inhabitants; two more are reserved by name now: *primary-source /
  provenance references* (commit SHAs, PR numbers, corroborating external
  projects, grounding URLs -- the category currently in
  `docs/skill-provenance.md`, see section 4.5 and Sub-project C) and the
  *inter-skill dependency graph* (`skillDependencies`, see section 4.1 and
  Sub-project D).
- A single structured per-skill metadata file that is the source of truth
  for `portability` and `capability-assumption`.
- The deterministic gate (`check_skill_shape.py`) enforces the file's
  presence and both fields' presence + valid enum value.
- All 17 existing skills migrated: sidecar added, redundant body-line
  Portability declaration removed (no "declare in two places").
- Placement-convention prose in `SKILL.md`, `rubric.md`, and the
  self-review worked example updated to describe the sidecar.
- The checker stays stdlib-only and read-only.

## 3. Non-goals

- The grading *semantics* of `capability-assumption` (how Broad / Frontier
  / Adaptive change dimensions 2, 3, 5, 9). That is Sub-project B.
- Reclassifying any skill to Frontier or Adaptive. Sub-project A assigns
  every skill `spec.capabilityAssumption: Broad` as the conservative,
  reversible default; deliberate reclassification happens in B alongside
  the semantics that make it meaningful.
- Any new rubric dimension. The axis scopes existing dimensions; it does
  not add one.
- Retiring or rewriting the nine dimensions or the shape checker's other
  checks.
- Migrating `docs/skill-provenance.md` content into the sidecars. A only
  reserves the `references` field's format (section 4.5); the actual
  data migration and retirement of the central file is Sub-project C.
- Populating or gating `spec.skillDependencies`. A only reserves the
  field's shape (section 4.1); classifying each skill's references as
  hard `requires` vs. soft `relatedTo`, and adding the dangling-reference
  and Portable-vs-requires contradiction gates, is Sub-project D.

## 4. Design

### 4.1 The sidecar file

- **Path:** `skills/<name>/gitapex_metadata.yaml` (one per skill,
  alongside `SKILL.md`). The `gitapex_` prefix deliberately marks the file
  as *this repository's own* metadata convention -- `portability` and
  `capability-assumption` are gitapex evaluation fields, not part of the
  Anthropic Agent Skills standard -- so a vendored consumer can recognize
  and drop it without mistaking it for standard skill metadata.
- **Format:** a Kubernetes-manifest-shaped document -- the familiar
  `apiVersion` / `kind` / `metadata` / `spec` envelope, borrowed as a
  *convention* only (these files are never applied to a cluster). The
  envelope buys three concrete things: schema versioning (`apiVersion`)
  so the format can grow -- `references` in Sub-project C, more later --
  without breaking older files; a self-describing `kind`; and a clean
  `metadata` (identity) vs. `spec` (declared content) split. This matches
  the sidecar's role as the general, growing maintainer-metadata home.
- **Envelope fields (checker-enforced):**
  - `apiVersion`: `gitapex.dev/v1alpha1` (a namespacing string in k8s
    group/version form, not a claim to own the domain; `v1alpha1` signals
    the schema is still evolving).
  - `kind`: `SkillMetadata`.
  - `metadata.name`: the skill's directory name.
- **`spec` gated fields (both required, checker-enforced):**
  - `spec.portability`: one of `Portable`, `Repository-scoped`, `Mixed`.
  - `spec.capabilityAssumption`: one of `Broad`, `Frontier`, `Adaptive`.
    (camelCase `spec` field per k8s convention; the enum *values* stay
    PascalCase, matching the prose levels.)
- **`spec` ungated fields (optional, free-form, not checker-enforced in A):**
  maintainer-facing metadata. Two are reserved by name now so later
  sub-projects do not have to re-negotiate the shape:
  - `spec.references` -- a list of primary-source / corroboration links,
    commit SHAs, PR numbers. Populated in Sub-project C.
  - `spec.skillDependencies` -- the inter-skill dependency graph, split by
    strength:

    ```yaml
    skillDependencies:
      requires: []          # hard: the procedure cannot function without it
      relatedTo:            # soft: boundary / complement / see-also
        - battle-testing-a-skill
    ```

    The hard/soft split is load-bearing, not decoration: a survey of the
    current tree found 13 of 17 skills referenced by a sibling, but nearly
    all of those references are *boundary* statements ("see
    battle-testing-a-skill ... instead"), not dependencies. Collapsing
    them into one list would make almost every Portable skill look
    self-contradictory. Populated and gated in Sub-project D.
- **Parsing (stdlib-only preserved):** because the format is one we
  control and fully specify (2-space indent, simple scalars for the gated
  fields under `metadata`/`spec`), the checker reads it with a small
  indentation-aware reader -- no PyYAML dependency. It walks the top-level
  keys, then the `metadata` and `spec` children it needs; ungated list
  fields like `spec.references` are skipped, not parsed. Full arbitrary
  YAML is neither produced nor required.
- **Example** (`skills/evaluating-skill-quality/gitapex_metadata.yaml`):

  ```yaml
  apiVersion: gitapex.dev/v1alpha1
  kind: SkillMetadata
  metadata:
    name: evaluating-skill-quality
  spec:
    portability: Portable
    capabilityAssumption: Broad
    # references:            # (Sub-project C)
    #   - https://...
  ```

- **Behavior-neutrality invariant (hard requirement / stop boundary):**
  Claude Code auto-loads only `SKILL.md` (name + description at startup,
  body on invocation). Every other file -- `references/`, `scripts/`, and
  this sidecar -- is read on demand and costs zero context until read. The
  sidecar is therefore purely advisory metadata consumed only by the
  checker and by a human/model reviewer establishing the precondition. No
  skill's runtime *procedure* may read or branch on the sidecar; doing so
  would make the skill's behavior depend on a non-loaded file and would
  itself be a portability/durability defect. The sidecar changes grading
  and tooling, never skill behavior.

### 4.2 Checker changes (`scripts/check_skill_shape.py` + test)

Remove the body-scan `portability-near-top` check and its supporting
constants (`PORTABILITY_RE`, `PORTABILITY_MAX_BODY_LINE`). Add a small
indentation-aware manifest reader (a light extension of the existing
`_parse_frontmatter` scalar logic that also descends into the
`metadata` and `spec` maps), and these checks:

- `metadata-file-present` -- `gitapex_metadata.yaml` exists and is readable
  next to `SKILL.md`.
- `manifest-envelope` -- `apiVersion` equals `gitapex.dev/v1alpha1` and
  `kind` equals `SkillMetadata` (the recognized shape).
- `metadata-name-matches-dir` -- `metadata.name` equals the skill's
  directory name (a clean identity invariant for the sidecar; unlike the
  SKILL.md `name`-vs-directory nit, here the field exists only to identify
  the skill, so a mismatch is a real defect).
- `portability-declared` -- `spec.portability` is one of the three valid
  levels.
- `capability-assumption-declared` -- `spec.capabilityAssumption` is one
  of the three valid levels.

Update the module docstring's canonical check list to match. Update
`scripts/test_check_skill_shape.py`: drop the `portability-near-top`
cases, add cases for the new checks (valid manifest; missing file; wrong
`apiVersion`/`kind`; `metadata.name` mismatch; missing or invalid-enum
`spec` field). Preserve stdlib-only and read-only properties and the
0/1/2 exit-code contract.

### 4.3 Migration of the 17 skills

**This is a per-skill judgment task, not a bulk mechanical edit.** A survey
of the current tree found that all 17 Portability declarations carry
substantive prose, and some of that prose is *behavior-relevant* -- an
instruction the model executing the skill actually needs. The sharpest
example, from `stop-and-replan`:

> **Portability: Portable.** ... Tool names are written as `Server:tool`
> (portable shorthand); in Claude Code, translate to the literal
> double-underscore form -- `github:update_pull_request` is
> `mcp__github__update_pull_request` ...

Others in the same class: `outward-artifact-preflight`,
`screening-a-low-trust-contribution`, and `git-hosting-surface-audit` each
tell the reader to "substitute the calling repository's actual policy /
governance issue where they differ."

Moving that text into the sidecar would break the skill outright: the
sidecar is never auto-loaded, so the model would never read it. Deleting
the paragraph would lose the instruction. Only the *enum value* is
genuinely redundant with the sidecar.

**Three-way split.** For each `skills/<name>/`:

1. Create `gitapex_metadata.yaml` as a `SkillMetadata` manifest:
   `metadata.name` = the directory name, `spec.portability` = the enum the
   body line declares today, `spec.capabilityAssumption` = `Broad`.
2. Classify the existing declaration paragraph and route each part:
   - **Enum value** (`Portable` / `Repository-scoped` / `Mixed`) -> the
     sidecar. This alone is the "never both" duplication being removed.
   - **Behavior-relevant prose** (tool-name translation, "substitute your
     repository's X") -> **stays in `SKILL.md`**, with only the
     `**Portability: <enum>.**` marker prefix dropped and the remaining
     text rewritten to read as a normal sentence.
   - **Pure maintainer rationale** (e.g. `establishing-ubiquitous-language`'s
     "Self-contained; requires no particular instruction file.") -> a
     `## Notes` footer in `SKILL.md`, or the sidecar's free-form space.
3. Verify per skill that no behavior-relevant sentence was moved into the
   sidecar or dropped -- this is the behavior-neutrality invariant applied
   to the migration itself.

All 17 skills get `spec.capabilityAssumption: Broad` in this sub-project;
any Frontier / Adaptive reclassification is deferred to Sub-project B.

Current declared values to carry over (surveyed from the tree):
`Portable` -- driving-pr-to-merge, establishing-ubiquitous-language,
evaluating-skill-quality, gated-skill-edits, issue-to-fix,
merge-retrospective, ranking-the-open-queue, stop-and-replan,
untrusted-input-triage. `Mixed` -- battle-testing-a-skill,
explaining-the-work, git-hosting-surface-audit, seeding-issue-pr-templates.
`Repository-scoped` -- issue-to-branch, outward-artifact-preflight,
responding-to-a-fresh-arrival, screening-a-low-trust-contribution.

### 4.4 Documentation / prose updates

- `skills/evaluating-skill-quality/SKILL.md`: the "Portability level"
  section's placement language ("terse one-line marker on the first body
  line") changes to "declared in the skill's `gitapex_metadata.yaml`
  sidecar"; add a short "Capability assumption" section pointing at the
  same sidecar and naming the three levels (semantics deferred to the
  rubric in Sub-project B); update Procedure step 4 to read both fields
  from the sidecar.
- `skills/evaluating-skill-quality/references/rubric.md`: update the
  Portability level section's placement wording to the sidecar; add a
  Capability assumption section stub and a TOC entry (the per-dimension
  grading changes land in Sub-project B, cross-referenced here).
- `skills/evaluating-skill-quality/references/worked-example-self-review.md`:
  read the declarations from the sidecar; update the pasted shape-checker
  output block (which currently shows `portability-near-top PASS`) to the
  new check names.

### 4.5 Relationship to `docs/skill-provenance.md` (Sub-project C)

`docs/skill-provenance.md` today centralizes exactly the category this
sidecar is meant to host: per-skill, maintainer-facing,
repository-specific provenance and corroboration references, explicitly
"not skill behavior" and "a vendored skill does not need this
repository's own history." Consolidating it into per-skill sidecars is
the natural end state of the general-purpose goal.

Boundary (what does *not* move): behavior-relevant primary-source
citations that the skill's own procedure depends on -- e.g. `rubric.md`'s
References section, which the review procedure cites as grounding
authority -- are skill *content*, not maintainer metadata, and stay in
the skill. The test is the same behavior-neutrality invariant: if a
review step reads it, it is content; if only a maintainer reads it, it is
sidecar metadata.

This migration is **Sub-project C**, kept separate from A so A stays a
focused mechanism change rather than a mechanism + bulk data migration.
A only defines the format that admits the `references` field; C fills it
and retires the central file (or leaves a pointer). Sequencing of C
relative to B is open (both depend only on A's mechanism).

## 5. Backward compatibility and risks

- **Durability:** improved -- no unsanctioned frontmatter key; the sidecar
  is inert to every skill loader.
- **Human visibility:** reduced -- Portability is no longer visible from
  the top of `SKILL.md`. Accepted as the cost of consolidation; the
  sidecar sits directly beside `SKILL.md`, one `ls` away.
- **Vendoring:** a vendored skill carries its sidecar harmlessly; a
  consumer that ignores it loses only the declarations, not behavior.
- **Gate transition:** the "12 checks" contract in existing worked-example
  output changes. Every reference to the old check name is updated in the
  same change so no doc contradicts the checker.

## 6. Verification

Live proof, not a green type-check standing in for behavior:

- Run `check_skill_shape.py` against **all 17** migrated skills; every one
  passes with the new manifest checks visible in output.
- Negative cases in the checker's test suite: missing sidecar, wrong
  `apiVersion`/`kind`, `metadata.name` mismatch, missing `spec` field, and
  invalid enum value each FAIL with a clear message and exit 1; bad usage
  exits 2.
- Grep the tree to prove no `**Portability:` marker survives in any
  `SKILL.md` and no doc still references `portability-near-top`.
- **Per-skill diff review of the three-way split (section 4.3):** for each
  of the 17 skills, confirm every behavior-relevant sentence from the old
  declaration is still present in `SKILL.md` -- not moved into the sidecar
  and not dropped. Concretely, `stop-and-replan`'s `Server:tool` ->
  `mcp__github__*` translation note and the "substitute the calling
  repository's ..." instructions in `outward-artifact-preflight`,
  `screening-a-low-trust-contribution`, and `git-hosting-surface-audit`
  must all still be readable from the skill body alone. This is the
  behavior-neutrality invariant checked against the migration itself, and
  it is a review step a script cannot decide.
- Confirm the checker performs no writes and no network access (read-only
  property preserved).

## 7. Sequencing

Sub-project A (this spec) lands first: it is the mechanism the rest sit
on. Then, in either order (both depend only on A):

- **Sub-project B** -- add the `capability-assumption` grading semantics
  to `rubric.md` (dimensions 2, 3, 5, 9), the full SKILL.md Capability
  assumption section, the self-review re-grade, and any deliberate
  Frontier / Adaptive reclassification.
- **Sub-project C** -- migrate `docs/skill-provenance.md`'s per-skill
  provenance / primary-source references into each sidecar's `references`
  field (section 4.5), and retire or repoint the central file.
- **Sub-project D** -- populate `spec.skillDependencies` for all 17 skills
  (classifying each existing cross-skill reference as hard `requires` or
  soft `relatedTo`) and add two deterministic gates: every named skill
  resolves to an existing `skills/<name>/` (catches dangling references
  after a rename or retirement), and a non-empty `requires` contradicts
  `portability: Portable`.

Each sub-project is its own issue -> spec -> plan -> implementation
cycle, per the repository's issue-first rule.

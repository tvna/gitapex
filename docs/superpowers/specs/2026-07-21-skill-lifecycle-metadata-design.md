# Skill lifecycle metadata (`spec.lifecycle`): experimental + deprecated + stable + renamedFrom

**Date:** 2026-07-21
**Status:** Design, implemented alongside this spec (round 1: sections
1-7; round 2 addendum: section 8)
**Issue:** #236

## 1. Motivation

The skill metadata sidecar (`skills/<skill>/metadata/gitapex.yaml`, see
#182, #183, #184, #188) already declares `spec.portability`,
`spec.capabilityAssumption`, `spec.references`, and
`spec.skillDependencies`, but has no structured way to say a skill is not
yet proven, or has been superseded and is on its way out. Today either
state only lives in free-form prose, if it is written down at all.

The request was modeled explicitly on how Python, Go, Rust, and
Kubernetes handle standard-function/API migration -- and, per an explicit
follow-up during design, deliberately not confined to only the exit side
("deprecated") that request initially named:

- **Rust** models both bookends as independent attributes:
  `#[unstable(feature = "...", issue = "...")]` (entry, nightly-only,
  tracked by an issue) and `#[deprecated(since = "1.2.0", note = "use
  `new_fn` instead")]` (exit).
- **Python** has `PendingDeprecationWarning`/provisional APIs (entry,
  "may still change") and `warnings.deprecated(message, ...)` (PEP 702,
  exit).
- **Go** has `GOEXPERIMENT`-gated features tracked by a proposal issue
  (entry) and the `// Deprecated: <reason>` doc comment convention (exit).
- **Kubernetes** has alpha/beta feature gates tracked by a KEP issue
  (entry) and its deprecation policy: reason, replacement, and a
  minimum-notice removal timeline before actual removal (exit).

The common shape across all four: an entry-side declaration (why this is
still unproven, and what issue tracks its graduation) and an
independent exit-side declaration (why this is superseded, what replaces
it, and optionally when it might go away) -- neither implying the other.

## 2. Goals

- Add `spec.lifecycle` to the sidecar schema, with two independent,
  optional sub-blocks: `experimental` and `deprecated`.
- Enforce both sub-blocks' shape with the same rigor as the existing
  `portability-declared`/`capability-assumption-declared` checks:
  required-field presence, unknown-key rejection, and real-date
  validation for `since`/`removeAfter`.
- Resolve `deprecated.replacement` against sibling skill directories, the
  same dangling-reference gate `spec.skillDependencies` already applies.
- Document the field in `SKILL.md`/`rubric.md`, mirroring the existing
  Portability level / Capability assumption paired-heading convention,
  since -- unlike `spec.skillDependencies` or the still-reserved
  `spec.evalStatus` -- this field is strictly gated and needs a
  maintainer-facing home, not just checker/test coverage.
- Keep `check_skill_shape.py` stdlib-only, read-only, and behavior-neutral
  (no skill's own runtime procedure may read or branch on the sidecar).

## 3. Non-goals

- Migrating any of the 17 existing skills to declare either sub-block.
  Every skill today is implicitly **Stable** (absence of `spec.lifecycle`,
  or of either sub-block within it) -- this work adds the mechanism only.
- Automatic removal enforcement past `removeAfter`. That date is
  documentation, not automation -- mirroring Kubernetes' own deprecation
  policy being a process constraint, not a hard technical one; no CI step
  in this repository deletes a skill once the date passes.
- Automatic graduation out of `experimental` when its `trackingIssue`
  closes. No CI step flips a skill to Stable.
- A mutual-exclusion gate between `experimental` and `deprecated`. Both
  present simultaneously is unusual (e.g. a draft replacement path itself
  deprecated in favor of a different experiment) but not modeled as an
  error, mirroring Rust's independent, non-conflicting attributes.
- Any change to how `capabilityAssumption`/`portability` are graded, or to
  the nine rubric dimensions.
- Resolving `experimental.trackingIssue` against a live GitHub API call.
  It is validated for shape only (an anchored `#123` or
  `owner/repo#123`) -- this checker is offline/read-only by design.

## 4. Design

### 4.1 Schema

```yaml
spec:
  lifecycle:
    experimental:
      reason: "why this skill is not yet proven"
      trackingIssue: "#123"       # tracks graduation to Stable
      since: "2026-07-21"         # optional, YYYY-MM-DD
    deprecated:
      reason: "why this skill is deprecated"
      replacement: name-of-sibling-skill
      since: "2026-07-21"         # optional, YYYY-MM-DD
      removeAfter: "2026-10-01"   # optional, YYYY-MM-DD, documentation only
```

`experimental.reason` and `experimental.trackingIssue` are required
non-empty strings once that block is declared at all;
`deprecated.reason` and `deprecated.replacement` are required non-empty
strings once that block is declared at all. `since` (both blocks) and
`removeAfter` (deprecated only) are optional but, when present, must be
real calendar dates in strict `YYYY-MM-DD` shape.

### 4.2 Parser changes (`check_skill_shape.py`)

`_parse_manifest`'s existing nesting tops out at two special cases, each
one level deeper than the generic 2-space nested-scalar path:
`spec.references` (a flat list under a 2-space key) and
`spec.skillDependencies` (a mapping of two list-valued subkeys, 4-space
subkeys with 4+-space list items). `spec.lifecycle` needs one level
deeper still -- `spec` -> `lifecycle` (2-space) -> `experimental`/
`deprecated` (4-space) -> scalar fields (6-space) -- with dict-of-scalars
leaves instead of list-of-scalars at the bottom, so it follows
`spec.skillDependencies`' bespoke-state pattern one nesting hop deeper
rather than reusing the list-collection machinery.

`ManifestParse` gains `unknown_lifecycle_keys` (stray 4-space keys other
than `experimental`/`deprecated`) and `unknown_lifecycle_fields` (stray
6-space keys inside either sub-block). No malformed-item channel is
needed the way `spec.references`/`spec.skillDependencies` need one for
list items: every leaf under `spec.lifecycle` is a plain scalar, so a
wrong-type value is simply stored as the raw string by the field parser
and fails the downstream well-formed check on shape. A sub-block header
written as an inline scalar instead of opening a block (e.g.
`experimental: true`) is stored as that raw scalar under its own key,
exactly as `spec.skillDependencies: oops` falls through today, so the
checker layer reports it as the wrong type rather than silently dropping
it.

### 4.3 New checks

`_lifecycle_checks` mirrors `_skill_dependency_checks`'s early-return
ladder ("spec is not a mapping" / "not declared (optional)" / "not a
mapping") before real validation, and emits:

- `lifecycle-well-formed`: mapping shape; only `experimental`/
  `deprecated` keys; each sub-block, if present, is itself a mapping with
  only its own recognized fields; each sub-block's required fields are
  non-empty strings; `since`/`removeAfter`, if present, are real
  `YYYY-MM-DD` dates (`datetime.date.fromisoformat`, not a regex-only
  shape check, so an out-of-range date like `2026-13-45` is caught);
  `experimental.trackingIssue`, if present, matches the anchored
  `#123`/`owner/repo#123` shape.
- `lifecycle-deprecated-replacement-resolves`: when
  `deprecated.replacement` is a non-empty string, it names an existing
  sibling skill directory -- the same dangling-reference gate
  `skill-dependencies-resolve` already applies.

Both checks report FAILing fallback entries when the sidecar is
unreadable/malformed, parallel to every other gated field.

### 4.4 Documentation

New paired `## Lifecycle` sections in `SKILL.md` (short version, next to
the existing Portability level / Capability assumption headings) and
`references/rubric.md` (full elaboration, explicitly noting -- unlike
those two axes -- that `spec.lifecycle` has no per-dimension grading
effect; it is structured bookkeeping, not a rubric input).

## 5. Backward compatibility and risks

- Every one of the 17 existing sidecars has no `lifecycle` key, so every
  new check reports "not declared (optional)" and passes -- zero
  behavior change for any existing skill.
- The behavior-neutrality invariant holds: this is metadata only, parsed
  and gated by the checker, never read by a skill's own runtime
  procedure.

## 6. Verification

- `uv run pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`
  -- new and existing cases green.
- `uv run pytest` (full suite) -- no regressions.
- `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py
  skills/evaluating-skill-quality` -- 28/28 checks pass, confirming the
  new SKILL.md/rubric.md prose also clears the Portable self-citation
  scan (that skill declares `portability: Portable`).

## 7. Sequencing

Lands as two commits: (1) parser + checks + docstring + tests together
(they must be green as a unit), (2) `SKILL.md`/`rubric.md`/this design
doc's prose, separately. Both cite `Refs #236`.

## 8. Round 2 addendum: `stable`, `compatibilityGuarantee`, `renamedFrom`

After round 1 landed, the requester twice reiterated that "deprecated"
was only ever meant as one example of the broader migration-lifecycle
concept, not its boundary. Two further design discussions converged on
three additions to `spec.lifecycle`, still under this same issue (#236)
since round 1 was unmerged, in-flight work, not a separate feature.

### 8.1 Schema addition

```yaml
spec:
  lifecycle:
    stable:
      since: "2026-07-21"        # required once this block is present
      compatibilityGuarantee: GA # optional: Alpha | Beta | GA
    renamedFrom: old-skill-name  # optional, free-form, NOT resolved
```

- **`stable`** -- a graduation record, mirroring Rust's
  `#[stable(feature, since)]`. `since` is the only required field.
  `compatibilityGuarantee`, if present, is one of Kubernetes'
  `Alpha`/`Beta`/`GA` API-stability tiers, shape-gated only -- no rule
  ties it to a sibling's `spec.skillDependencies.requires` (confirmed
  non-goal, avoids new cross-skill coupling beyond what was asked).
- **`renamedFrom`** -- confirmed **backward-pointing**, not a
  `renamedTo` forward pointer on a tombstone stub. `git mv` deletes the
  old directory outright, so a forward-pointing sidecar would have
  nowhere to live; `renamedFrom` instead sits on the *surviving* (new)
  skill's own sidecar, naming the old, now-nonexistent directory as a
  free-form, non-empty scalar -- deliberately **not** resolved against
  sibling directories, unlike `deprecated.replacement`.
- **New cross-field rule**: `experimental` and `stable` are mutually
  exclusive (`experimental-stable-compatible`, mirroring
  `requires-portability-compatible`'s placement and independence from
  the shape check it accompanies) -- "not yet graduated" and "already
  graduated on some date" are a real logical contradiction, unlike
  `experimental`+`deprecated`, which the requester separately confirmed
  in round 1 should stay ungated (an experimental skill can legitimately
  be superseded by a different experiment).

### 8.2 Parser mechanics

`stable` reuses the existing `experimental`/`deprecated` block-opening
state machine unchanged -- it is simply a third member of
`LIFECYCLE_SUBKEYS`/`LIFECYCLE_FIELDS`/`LIFECYCLE_REQUIRED_FIELDS`.
`renamedFrom` is structurally different: a plain scalar directly under
`lifecycle:` (like `metadata.name` under `metadata:`), never opening a
block, matched by a dedicated `LIFECYCLE_SCALAR_KEY_RE` checked between
the block-subkey match and the unknown-key fallback in the `in_lifecycle`
per-line handler. A blank `renamedFrom:` assignment stores nothing,
mirroring this parser's existing repo-wide convention that a blank
scalar assignment means "not declared."

### 8.3 Non-goals (confirmed)

- No cross-skill consumer check tying `compatibilityGuarantee` to
  `skillDependencies.requires`.
- No tombstone/redirect stub convention, and no `renamedTo` field.
- No dangling-reference check on `renamedFrom`.
- No migration of any of the 17 existing skills (unchanged from round 1).

### 8.4 Verification

Same commands as section 6, re-run after the round-2 changes: full test
suite green (431 tests), `check_skill_shape.py` reports 29/29 checks
passing against `evaluating-skill-quality` itself, including the two new
checks (`lifecycle-well-formed` extended, `experimental-stable-compatible`
new) and the Portable self-citation scan against the updated prose.

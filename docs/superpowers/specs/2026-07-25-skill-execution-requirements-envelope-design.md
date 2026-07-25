# Skill execution-requirements envelope + `tools` category (`spec.executionRequirements`)

**Date:** 2026-07-25
**Status:** Design, implemented alongside this spec
**Issue:** #349 (Workstream W1, first slice, of parent tracking issue #307)

## 1. Motivation

#307 asks for a GitApex-specific skill execution-requirement contract so
that later work (a runtime compatibility matrix, per-runtime enforcement
adapters, a per-skill capability inventory, and CI drift gates) has
something concrete to consume. Today the sidecar (`spec.portability`,
`spec.capabilityAssumption`, `spec.references`, `spec.skillDependencies`,
`spec.lifecycle` -- see #182/#183/#184/#188 and #236) records provenance,
dependency, and maturity metadata, but nothing about what a skill's own
procedure actually touches at runtime: which tools, which filesystem
paths, which network or MCP endpoints, which credentials.

#307's own body explicitly forbids attempting the full 8-category schema
(tools, filesystem, network, browser, external services, MCP, credentials,
main-conversation/isolation context) in one PR -- three prior attempts
(#304, #309, #331) were closed for over-scoped or premature implementation
against that same parent issue. This design instead follows the pattern
this repository already used twice: the original sidecar mechanism
shipped as four independent sub-projects (A-D), and `spec.lifecycle`
itself shipped in two rounds (experimental/deprecated, then
stable/renamedFrom). This is the first slice: the `executionRequirements`
envelope plus one category, `tools`.

## 2. Goals

- Add `spec.executionRequirements` to the sidecar schema: an optional
  top-level block under `spec`, with one recognized subkey for this slice,
  `tools`.
- `tools` is a mapping with up to three recognized subkeys -- `read`,
  `write`, `shell` -- each, if present, a list of non-empty scalar
  capability tags (free-form strings; no fixed vocabulary is defined by
  this issue).
- Fail closed on any unrecognized key at either level (per #307's security
  invariant 4), the same way `spec.skillDependencies` and `spec.lifecycle`
  already reject their own unknown keys rather than silently skipping
  them.
- Distinguish "not declared" (the `executionRequirements` block, or the
  `tools` block, or an individual subkey, is absent) from "declared empty"
  (`read: []`) -- the former means no statement has been made yet; the
  latter is a deliberate claim of zero requirement in that category.
- Keep `check_skill_shape.py` stdlib-only, read-only, and behavior-neutral:
  no skill's own runtime procedure may read or branch on the sidecar.

## 3. Non-goals

- The remaining seven #307 W1 categories (`filesystem`, `network`, `mcp`,
  `credentials`, `browser`, `externalServices`, `context`). Each is left
  to a sibling child issue under #307:
  - `filesystem` needs path normalization, a `${workspace}`-relative
    rooting convention, and symlink-handling rules -- real, separate
    design work this slice does not attempt.
  - `network` and `mcp` each need a mode-enum-plus-list shape (e.g.
    `mode: disabled|domains` alongside a `domains: []` list) that this
    parser has no precedent for yet -- every existing sub-block is either
    all-list (`skillDependencies`) or all-scalar-leaves (`lifecycle`'s
    three blocks), never a mix within one block. Introducing that shape
    is deferred so it gets its own design attention rather than being
    rushed in alongside `tools`.
  - `credentials`, `browser`, `externalServices`, `context` are simple in
    shape but out of scope purely to keep this slice reviewable; #307's
    illustrative example is not treated as a commitment to land them
    together.
- Migrating any of the 18 existing skill sidecars to declare
  `executionRequirements`. Every skill today implicitly has no declared
  execution requirements (absence, not a default value) -- this slice adds
  the mechanism only, mirroring `spec.lifecycle`'s own non-goal of not
  migrating existing skills when it landed.
- A fixed vocabulary or enum for `tools` capability tags. This slice
  validates shape (non-empty scalar strings, list-of-strings) only, not
  the tag values themselves -- the same latitude `spec.skillDependencies`
  gives skill names beyond "must resolve to a sibling directory", except
  tool tags have no resolution target at all.
- Any cross-field rule (e.g. tying `tools.shell` non-empty to
  `capabilityAssumption`). No such rule is requested by #349's acceptance
  criteria; adding one would be new coupling beyond what was asked.
- The runtime compatibility matrix, adapters, inventory, migrations,
  review-guidance updates, or CI drift gates beyond the existing checker
  (#307's W2-W7).

## 4. Design

### 4.1 Schema

```yaml
spec:
  executionRequirements:
    tools:
      read: []
      write: []
      shell: []
```

All three `tools` subkeys are optional and independent. `read`, `write`,
and `shell` are free-form: this slice does not define what values are
valid tool-capability tags (that vocabulary question belongs to a later
workstream, once the runtime compatibility matrix exists to ground it
against). An absent `tools` block, or an absent subkey within a declared
`tools` block, means "not yet declared" for that category -- distinct from
an explicit `read: []`, which means "declared, and zero read tools are
needed."

### 4.2 Parser changes (`check_skill_shape.py`)

`_parse_manifest`'s deepest existing nesting is `spec.lifecycle`: `spec`
(0-space) -> `lifecycle` (2-space) -> `experimental`/`deprecated`/`stable`
(4-space) -> scalar fields (6-space). `spec.executionRequirements.tools`
needs the same three-level depth, but with list-of-scalars leaves at the
bottom (6-space-or-deeper list items) instead of scalar fields --
structurally, `tools` is to `executionRequirements` what `requires`/
`relatedTo` are to `skillDependencies`, just one nesting level deeper (the
extra level being `executionRequirements` -> `tools` itself, where
`skillDependencies` has no intermediate category key).

New state, mirroring `in_skill_deps`/`skill_deps`/`collecting_dep_list`/
`collecting_dep_key`/`dep_list_indent` one level deeper:
`in_execution_requirements`, `execution_requirements` (dict),
`in_exec_tools`, `exec_tools` (dict), `collecting_exec_tools_list`,
`collecting_exec_tools_key`, `exec_tools_list_indent`. New regexes mirror
`SKILL_DEP_SUBKEY_RE`/`SKILL_DEP_UNKNOWN_KEY_RE`/`SKILL_DEP_LIST_ITEM_RE`:
an `executionRequirements`-subkey matcher at 4-space indent (recognizing
only `tools` for now), a `tools`-subkey matcher at 6-space indent
(recognizing `read`/`write`/`shell`), an unknown-key matcher at each
level, and a list-item matcher at 6-or-more-space indent reusing the same
mapping-like-item and indent-consistency detection
`REFERENCES_MAPPING_LIKE_RE`-style logic already applies to
`spec.references` and `spec.skillDependencies` items.

`ManifestParse` gains three new fields: `unknown_execution_requirement_keys`
(a key directly under `executionRequirements` other than `tools`),
`unknown_execution_requirement_tools_keys` (a key directly under `tools`
other than `read`/`write`/`shell`), and
`malformed_execution_requirement_tools_items` (a `tools` list item that is
mapping-shaped or inconsistently indented, the same malformed-item channel
`spec.references`/`spec.skillDependencies` already have one level
shallower). The per-line dispatch in `_parse_manifest` gets a new branch
inserted after the existing lifecycle handling and before the generic
2-space nested-scalar fallback, structured as the same
open-block/collect-items/dedent-finalizes state machine every other gated
field already uses.

### 4.3 New checks

`_execution_requirements_checks(spec, unknown_keys, unknown_tools_keys,
malformed_tools_items)` mirrors `_skill_dependency_checks`'s early-return
ladder (spec not a mapping / `executionRequirements` not declared /
`executionRequirements` not a mapping / `tools` not declared / `tools` not
a mapping) before real validation, and emits one check:

- `execution-requirements-well-formed`: `executionRequirements`, if
  present, is a mapping with only the `tools` key; `tools`, if present, is
  itself a mapping with only `read`/`write`/`shell`; each declared subkey
  is a list of non-empty scalar strings with no malformed (mapping-shaped
  or inconsistently indented) items. Evidence text names which subkeys
  were declared (e.g. `"read, shell declared"`) so "declared but empty"
  is distinguishable from "not declared" in the check's own output, not
  just in the parsed data structure.

Both the not-declared and the well-formed-with-problems paths report a
single `FAIL`/`PASS` `CheckResult`, following the exact pattern
`_skill_dependency_checks`'s `skill-dependencies-well-formed` check
already uses for its own not-declared/malformed cases.

### 4.4 Documentation

New paired `## Execution requirements` sections in `SKILL.md` (short
version, next to the existing Portability level / Capability assumption /
Lifecycle headings) and `references/rubric.md` (fuller elaboration,
explicitly noting -- like the Lifecycle precedent -- that this field has
no per-dimension rubric-grading effect; it is structured bookkeeping for
later #307 workstreams, not a maturity signal).

## 5. Backward compatibility and risks

- Every one of the 18 existing sidecars has no `executionRequirements`
  key, so the new check reports "not declared (optional)" and passes --
  zero behavior change for any existing skill.
- The behavior-neutrality invariant holds: this is metadata only, parsed
  and gated by the checker, never read by a skill's own runtime procedure.
- Residual risk carried into #307's later workstreams: the field name
  `executionRequirements` and the `tools.{read,write,shell}` shape are
  judgment calls inherited from #307's own "illustrative direction," not
  independently re-validated against all six target runtimes (Claude
  Code, Codex, Gemini CLI, Devin, OpenClaw, HermesAgent). That
  cross-runtime validation is explicitly #307's W2, not this issue.

## 6. Verification

- `uv run pytest skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`
  -- new and existing cases green.
- `uv run pytest` (full suite) -- no regressions.
- `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py
  skills/evaluating-skill-quality` -- confirms the new
  `execution-requirements-well-formed` check reports "not declared
  (optional)" for a skill with no `executionRequirements` block, and that
  the new SKILL.md/rubric.md prose still clears the Portable self-citation
  scan (this skill declares `portability: Portable`).
- `git diff --stat` scoped to `skills/**/metadata/gitapex.yaml` shows no
  changes -- confirms no existing sidecar was migrated.

## 7. Sequencing

Lands as a single PR: design doc, parser + checks + docstring + tests, and
`SKILL.md`/`rubric.md` prose together, citing `Refs #349` and `Refs #307`.
Unlike `spec.lifecycle`'s two-round split (which added independent
sub-blocks to an already-shipped mechanism), this issue's own scope is
already the minimal first round for a brand-new top-level field -- the
mechanism (the `executionRequirements` envelope itself) and its first
category (`tools`) are inseparable, since an envelope with no categories
would have nothing to test or document.

# W2 runtime compatibility matrix -- schema-only first slice

**Date:** 2026-08-08
**Status:** Design, implemented alongside this spec
**Issue:** parent #307, workstream W2 (first slice)

## 1. Motivation

Parent issue #307's W2 ("Versioned runtime compatibility matrix") asks
for a repository-wide record -- across all six target runtimes (Claude
Code, Codex, Gemini CLI, Devin, OpenClaw, HermesAgent) -- of field
parsing, discovery locations, invocation behavior, context loading, tool
semantics, path controls, sandbox controls, network controls, MCP
lifecycle, and plugin/subagent limitations, each mapping classified as
`exact`/`conservative`/`lossy`/`unsupported`, cited to a primary source
and an observed runtime version. #307's own words: "This matrix must
become versioned, testable repository data rather than remaining prose."

W3 (the `spec.executionRequirements.tools` inventory, issues #814/#818/
#823) already populated every skill sidecar with what each skill's
procedure touches at runtime. W2 is the companion piece a future W4
adapter needs: given a skill's declared requirement, which target
runtimes can actually enforce it, and how faithfully.

This is explicitly a first slice, not the whole of W2: it ships the data
schema and its drift gate only, with zero runtime rows populated -- the
same sequencing W1 used (envelope + `tools` category shipped before any
skill adopted it). Per the operator's own direction this session, the
schema decision comes before any cross-runtime research, so the research
work (a much larger, primarily investigative task) has a settled target
shape to write into rather than improvising one per runtime.

## 2. Goals

- Add `.gitapex/runtime-compatibility-matrix.json` (data) and
  `.gitapex/runtime-compatibility-matrix.schema.json` (JSON Schema draft
  2020-12), mirroring `.gitapex/ssot.json`/`.gitapex/ssot.schema.json`'s
  own established convention for a single repo-wide registry file (a
  `meta` block with `schema_version`/`tracking_issue`/`status`/`phase`,
  snake_case meta keys matching that file's own precedent).
- `runtimes` is an open, pattern-validated map (kebab-case keys, no
  closed enum) -- mirrors `spec.executionRequirements.packages`'
  ecosystem-key extensibility, since the evidence baseline in
  `skills/evaluating-skill-quality/references/runtime-compatibility.md`
  already shows this repository's own runtime list growing past six
  (Windsurf, Kimi CLI, Cursor, GitHub Copilot, Kiro were all added after
  that file's first six rows). A closed enum here would need a schema
  change for every future runtime; an open map does not.
- Within one runtime entry, `dimensions` is closed to exactly the ten
  keys #307's own W2 text names (camelCase:
  `fieldParsing`/`discoveryLocations`/`invocationBehavior`/
  `contextLoading`/`toolSemantics`/`pathControls`/`sandboxControls`/
  `networkControls`/`mcpLifecycle`/`pluginSubagentLimitations`),
  `additionalProperties: false` -- fail closed on an unrecognized
  dimension name, matching every other gated block in
  `skill-metadata.schema.json`. Each dimension key is individually
  optional (`minProperties: 1` on the parent so an empty runtime entry
  cannot exist) -- population is expected to land dimension-by-dimension
  and runtime-by-runtime across several follow-up batches, the same
  small-group sequencing W3 already used, not all 60 cells in one PR.
- Each populated dimension is an object: `classification` (enum
  `Exact`/`Conservative`/`Lossy`/`Unsupported`, PascalCase matching this
  repository's own established enum casing --
  `Portable`/`Repository-scoped`/`Mixed`,
  `Broad`/`Frontier`/`Adaptive`, `Alpha`/`Beta`/`GA` -- rather than #307's
  own lowercase prose wording), `primarySource` (a full `https://` URL,
  host-shaped-pattern-validated -- the schema also declares `format:
  uri` for self-documentation, but that keyword is a live no-op in this
  repository's own environment absent an installed `rfc3987`/
  `rfc3986-validator` provider package, confirmed by this slice's own
  adversarial review; the pattern is the field's real, always-enforced
  guarantee), `snapshotDate` (`YYYY-MM-DD`, format- and pattern-
  validated -- `date` format IS stdlib-backed and does activate,
  matching `spec.lifecycle`'s date convention),
  required; `observedVersion` (free-form string -- vendor versioning
  schemes differ too much for a shared pattern) and `notes` (<=500 chars,
  matching `spec.references[].summary`'s own cap) optional.
- A drift-gate scanner
  (`.github/scripts/gitapex_scan_runtime_compatibility_matrix.py`),
  reusing `_gitapex_schema_validation.py` (issue #755's shared
  load/validate helpers) the same way
  `gitapex_scan_ssot_schema.py`/`gitapex_scan_skill_metadata_schema.py`
  already do, wired into `tests/test_gitapex_scan_runtime_compatibility_matrix.py`
  (auto-discovered by `pyproject.toml`'s `testpaths`, no separate CI
  workflow step -- the same enforcement shape those two scripts use).
- Register the new gate and its policy source in `.gitapex/ssot.json`,
  mirroring `skill-metadata-schema-drift`'s own entry shape.
- The data file ships with `meta.status: "draft"`, `meta.phase:
  "phase-0"`, and `runtimes: {}` -- schema-valid, zero rows. Population
  is explicitly out of scope for this slice.

## 3. Non-goals

- Populating any runtime row. That is real primary-source research
  work, scoped into its own follow-up batch(es) once this schema lands,
  matching W3's own small-group sequencing (a first representative
  runtime, then the rest).
- W4 (adapter code that reads this matrix to generate or validate
  per-runtime enforcement). This slice ships data and its shape gate
  only; nothing consumes the matrix yet.
- Reconciling this matrix with
  `skills/evaluating-skill-quality/references/runtime-compatibility.md`.
  That file grades a different, narrower axis (`SKILL.md` frontmatter
  standard-compliance warnings) and stays independently maintained; this
  matrix's ten dimensions (sandbox/network controls, MCP lifecycle, path
  controls) go well beyond what that file covers. Overlap in primary
  sources is expected and is not itself a reason to merge the two
  artifacts.
- A closed enum for `runtimes` keys, or any cross-field rule beyond
  ordinary shape validation (issue #349's own W1 precedent: "no fixed
  vocabulary" stayed unresolved by design until a concrete pressure to
  add one existed. Same call here).

## 4. Verification

- `python3 .github/scripts/gitapex_scan_runtime_compatibility_matrix.py`
  -- exit 0, "No drift found" against the shipped empty-`runtimes`
  instance.
- `uv run pytest tests/test_gitapex_scan_runtime_compatibility_matrix.py`
  -- new fixture-driven unit tests plus the real-file gate test (mirrors
  `test_gitapex_scan_ssot_schema.py`'s own shape).
- `uv run pytest` (full suite) -- no regressions, including
  `tests/test_gitapex_scan_ssot_schema.py` itself (the new gate/policy-
  source entries must not break `ssot.json`'s own drift checks).

## 5. Sequencing

Lands as a single PR: this design doc, the schema, the empty-but-valid
data file, the scanner, its tests, and the `ssot.json` registration
together -- mirroring W1's own "envelope and first category are
inseparable" reasoning: a schema with nothing that validates against it
proves nothing. Refs #307 (parent) and this slice's own child issue.

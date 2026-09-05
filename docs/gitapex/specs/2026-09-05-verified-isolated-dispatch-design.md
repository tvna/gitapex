# Verified Isolated Dispatch Primitive (evaluating-skill-quality)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-05. Not yet implemented, not yet formalized into an issue.

## Strategic origin

This design was elicited after an operator course-correction: a session had spent many turns on a tactical task (rewriting `evaluating-skill-quality`'s Portability rubric, PR #1793 / issue #1788), then drifted into an ad hoc dogfooding self-review that stumbled into an isolation-contamination side-quest (filed as issues #1802 and #1353). The operator flagged that this repeated a pattern -- manually re-deriving, per session, work that should be deterministic, reusable infrastructure -- and asked for the skill-evaluation mechanism this repository's "evaluation-first" thesis should have had from the start, ignoring YAGNI as a blocking objection.

Grounded investigation (reading `.github/workflows/skill-eval-*.yml`, `skill-audit-gate.yml`, and `evals/scripts/*.py` directly, not from memory) found the skill family already has extensive **per-skill** evaluation infrastructure: all 30 skills carry a top-level `evals/<skill>/eval.yaml` suite; `skill-eval-gate.yml` is a real PR-blocking gate (confirmed via `actions_list` that it ran and passed on PR #1793's own two commits); `skill-eval-matrix.yml` is an advisory cross-model matrix; `skill-audit-gate.yml` forces audit-disclosure in PR bodies. What is missing is **family-level** (cross-skill) machinery, in three places:

- **(A)** No cross-skill impact detection when a shared rubric/registry file changes (evidenced by issue #1789, a manually-filed one-off fix to re-classify 14 skills after this session's own rubric rewrite).
- **(B)** The isolation-verification registry (`adversarial-self-audit.md`'s Isolation verification section) is prose-driven, and any dispatch reviewing itself faces a structural circularity: a dispatch's own self-report ("no CLAUDE.md visible") is not a validated two-control test, per that section's own Trust class rule. This session observed the symptom firsthand -- a real dispatch's own report disclosed `dispatchIsolation: false` and marked its verdict provisional for exactly this reason.
- **(C)** No aggregated index of the family's current maturity state (each skill's nine-dimension verdict lives scattered across individual `metadata/gitapex.yaml` decision logs and PR bodies).

## Decomposition record

The operator chose to decompose this into two independent sub-projects rather than one combined design, since they have different owners/mechanisms:

1. **Sub-project 1 (this document): the isolation-verification structural fix (gap B).** Prioritized first, because an unreliable isolation-verification mechanism can block confident work on *any* skill that needs an isolated self-review dispatch.
2. **Sub-project 2 (deferred): cross-skill impact/drift detection when a shared rubric/registry file changes (gap A).** Not designed here -- a fresh `eliciting-a-design` invocation is expected once sub-project 1 reaches its own terminal handoff, per that skill's own decomposition protocol.

Gap (C) (a family-maturity index) was named but not selected for either sub-project; it remains an open, unscheduled candidate.

**No parent tracking issue was created.** The operator was asked explicitly and declined; per `eliciting-a-design`'s own decomposition protocol, this decline is recorded here rather than silently omitted, so a later invocation for sub-project 2 does not re-prompt for one.

## Scope (sub-project 1)

### In scope

- A new bundled script owned by `evaluating-skill-quality` that performs the Isolation verification Known-entries registry's two-control Verification procedure itself, then launches the real isolated dispatch using the verified recipe, as one operation.
- Migrating the existing Isolation verification Known-entries registry from hand-written prose to structured data.
- A scheduled CI job that keeps the registry current without waiting for an unrelated session to stumble into a version drift.
- Restructuring `adversarial-self-audit.md`'s Isolation verification section to match (short operational pointer, unconditionally loaded; the extracted methodology/history becomes conditional, non-operational material).

### Out of scope (this sub-project)

- Cross-skill impact detection (sub-project 2).
- A family-maturity index (gap C, unscheduled).
- Actually migrating `battle-testing-a-skill`, `scorer-gated-skill-edits`, or any other consumer skill to call the new primitive -- that is each consumer's own follow-up unit of work, downstream of this sub-project's own deliverable (a stable CLI contract to depend on).
- Detecting a breaking change to the new script's own CLI contract before it ships to dependents -- named as a real, disclosed risk (see Risks), not solved here; it is a natural candidate for sub-project 2's own cross-skill-impact machinery once that exists.

## Architecture

```
[calling skill: evaluating-skill-quality / battle-testing-a-skill / scorer-gated-skill-edits / ...]
        |  "need an isolated review dispatch"
        v
skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py
   --target <path> --prompt-file <path> [--controls-only] [--allowed-tools <list>]
        |  (runs inside the ORCHESTRATOR's own process; never delegates verification
        |   to the dispatch it is about to launch)
        |
        +-- 1. Read current identifying signals (claude --version, relevant env vars).
        +-- 2. Look up skills/evaluating-skill-quality/metadata/isolation-registry.yaml
        |      for a matching *Reviewed* entry (never trust a Same-run entry back --
        |      unchanged from the existing Trust class rule).
        |      |
        |      +-- match found --> reuse its recorded recipe, skip to step 4.
        |      +-- no match --> step 3.
        +-- 3. Run the positive/negative control pair itself, as subprocess calls from
        |      this same script's own process.
        |      +-- either control fails in a way indicating no viable recipe -->
        |            "No verified mechanism available": exit non-zero, clear message
        |            (matches the existing Stop boundary; never falls back to an
        |            unverified dispatch).
        |      +-- both succeed --> append a new Same-run, unreviewed entry to
        |            isolation-registry.yaml; regenerate the human-readable summary.
        +-- 4. Launch the REAL dispatch using exactly the verified recipe (unless
        |      --controls-only, used by the scheduled CI job to refresh the registry
        |      with no real target).
        v
Returns the dispatch's structured report, annotated with `dispatchIsolation: true`
and a reference to the registry entry that backed it.
```

### Why this closes the circularity

The controls are always executed by the orchestrator's own process (an interactive session's shell, or the scheduled job's own runner) -- never by the dispatch under review. The dispatch being asked to do real review work never verifies its own isolation; it only ever inherits an already-established, externally-verified recipe. This directly replaces the self-report ("I don't see a CLAUDE.md") this session observed being correctly, but unhelpfully, flagged as unverifiable by the dispatch itself.

## Components

1. **`skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py`** -- the primitive itself, per the Architecture section above. Its own module docstring carries the two-control methodology and the historical rationale/caveats extracted out of `adversarial-self-audit.md` (matching this repository's existing convention of extensive rationale docstrings on its other bundled scripts). The exact two-control methodology to translate into code is the one currently documented as of this design's writing in `adversarial-self-audit.md`'s own "Verification procedure" subsection (positive control: a synthetic sentinel `CLAUDE.md` in an isolated directory outside any real repository; negative control: an identical isolated setup with no `CLAUDE.md`/`AGENTS.md` anywhere in its own directory ancestry) -- this design does not restate that full procedure, only points at its current source.
2. **`skills/evaluating-skill-quality/metadata/isolation-registry.yaml`** -- structured data, one entry per (identifying-signal-set, mechanism) pair: `identifying_signals`, `mechanism`, `result`, `verified_alternative` (the exact env/cwd recipe), `trust_class` (`reviewed` | `same-run-unreviewed`), `date`, `caveat`. Placed as a sidecar file separate from `metadata/gitapex.yaml`'s own schema -- confirmed by directly reading `shape_checks/constants.py` that `SIDECAR_RELATIVE_PATH` is an exact, single hardcoded path (`metadata/gitapex.yaml`) and that the only whole-skill-directory walk in the shape checker (`field_checks.py`) is a symlink/special-file safety check, not a content or schema check -- so an additional file here changes none of the existing 79 shape checks.
3. **Generated Markdown view** (replacing today's hand-written Known entries prose in `adversarial-self-audit.md`, or a new adjacent file) -- rendered from `isolation-registry.yaml`, kept for human browsability and PR-diff review. Treated as **conditional** reference material going forward: relevant only when a human is reviewing a Same-run entry for promotion to Reviewed, or when someone is maintaining the script itself -- not needed for ordinary dispatch operation, since ordinary operation now just calls the script.
4. **`.github/workflows/isolation-registry-refresh.yml`** (new, scheduled) -- runs the same script in `--controls-only` mode on a schedule. On finding a new Same-run entry, it opens a pull request proposing the registry update; it must never auto-merge or auto-promote an entry to `reviewed` trust class -- that still requires the existing human/PR review gate, preserving the Trust class rule's actual safety property (an entry becomes Reviewed once merged, not once written). If a live control run itself fails in a way suggesting a *new* contamination pattern (not merely "not yet verified at this version"), the job opens an issue rather than silently no-op'ing, mirroring `merge-retrospective`'s own gate-proposal pattern.

## `adversarial-self-audit.md` restructuring

- The Isolation verification section shrinks to a short, unconditionally-loaded pointer: "Required, not optional: dispatch via `gitapex_run_verified_isolated_dispatch.py`; do not hand-roll the Verification procedure or launch a bare `Agent`-tool/`claude -p` dispatch directly." Its role (self-guard, content-independent of the reviewed target) is unchanged, so it stays part of the file's unconditional common-case load.
- The detailed two-control methodology moves into the script's own module docstring.
- The historical Known entries move into `isolation-registry.yaml`, with a generated summary view treated as newly-conditional material (see Components item 3).

## Migration

All historical Known entries (dated 2026-07-28 onward, on the order of a dozen dated/reconfirmed entries as of this writing) are migrated into `isolation-registry.yaml` now, not only new entries going forward -- an explicit operator choice, made knowing this requires judgment calls on a handful of entries whose prose blends "mechanism" and "caveat" language loosely. Entries already reachable through a merged PR migrate as `trust_class: reviewed`; any not yet merged stay in whatever trust class they already carried.

## Error handling

- No verified mechanism available (neither a matching Reviewed entry nor a successful live control run) -- exit non-zero with a clear message; never falls back to an unverified dispatch (matches the existing Stop boundary verbatim).
- The scheduled job's own control run failing in a way suggesting a genuinely new contamination pattern -- opens an issue, never a silent no-op.

## Testing

- The registry's own read/write/matching logic (pure Python: does a given identifying-signal set match a stored entry, does the YAML round-trip, does the Markdown regenerate correctly) gets ordinary unit tests, following this repository's own script-test-quality conventions.
- The live two-control behavior itself (does `claude -p` actually behave as expected against a real CLI) is not CI-mockable and stays a live-verification-only concern, consistent with how this repository already treats it (dated, versioned entries rather than a fixed CI assertion).

## Consequences for dependent skills

Any skill that later switches to calling this primitive (`battle-testing-a-skill`, `scorer-gated-skill-edits`, and others not yet identified) creates a `requires`-level cross-skill dependency and must:

- Declare `spec.skillDependencies.requires: [evaluating-skill-quality]` in its own `metadata/gitapex.yaml`.
- Cite only this one script's stable CLI entrypoint (no fan-out into `evaluating-skill-quality`'s other internals), satisfying the "no fan-out" / "a clean interface" tests in `references/rubric.md`'s Sibling-skill dependency portability subsection (the same rules this repository's own PR #1793 just wrote).
- Reclassify from `Portable` to `Mixed` or `Repository-scoped` as appropriate, since `requires-portability-compatible` already forbids a non-empty `requires` list on a `Portable`-declared skill.

This migration for each dependent skill is each skill's own follow-up unit of work, not part of this sub-project's own deliverable (which is limited to making the primitive exist with a stable contract).

## Risks

- **CLI-contract-break risk (unmitigated by this sub-project alone).** A future change to `evaluating-skill-quality`'s own `SKILL.md`/`rubric.md`/the script itself could silently break the primitive's CLI contract for every dependent skill. The existing `skill-dependencies-resolve` shape check verifies only that a required sibling directory exists, not that its CLI contract is intact. This is a natural candidate for sub-project 2's own cross-skill-impact machinery to eventually close; it is disclosed here as a known, currently-open gap, not solved by this design.
- **Migration judgment risk.** Converting a dozen-plus prose entries into structured fields requires some interpretive judgment; a mis-migrated caveat is a plausible, low-severity defect to watch for during implementation review.
- **CI-governance risk.** The scheduled job's own "propose via PR, never auto-promote" constraint is a design intent that must be verified as correctly implemented (unit- or integration-tested), not merely asserted in this document.

## Open questions

- Gap (C) (a family-maturity index) remains unscheduled; not part of either sub-project.
- Which additional skills beyond `battle-testing-a-skill`/`scorer-gated-skill-edits` will eventually need this primitive is not yet enumerated -- left to each skill's own future migration decision.

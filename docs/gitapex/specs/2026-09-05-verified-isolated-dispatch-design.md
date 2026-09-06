# Verified Isolated Dispatch Primitive (evaluating-skill-quality)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-05; formalized into issue #1809 and re-verified via `planning-a-branch-from-an-issue`. Revised after an independent adversarial review (see the Risks section's own "reviewed" annotations) found six confirmed defects in the first draft -- the Migration rule, the missing control-logic-bug risk, the registry schema, the `dispatchIsolation` annotation, the CI-platform scope gap, and a Risks/Testing inconsistency -- all fixed in this revision. Not yet implemented.

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
[calling skill: evaluating-skill-quality now; battle-testing-a-skill / scorer-gated-skill-edits
 are illustrative FUTURE callers only -- migrating them is explicitly out of this
 sub-project's own scope, see "Out of scope" above]
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
        |      +-- both succeed --> print the FULL control transcripts (not only
        |            PASS/FAIL) to stdout/stderr, append a new same-run-unreviewed
        |            entry to isolation-registry.yaml, regenerate the summary.
        +-- 4. Launch the REAL dispatch using exactly the verified recipe (unless
        |      --controls-only, used by the scheduled CI job to refresh the registry
        |      with no real target).
        v
Returns the dispatch's structured report, annotated with `verifiedLeakVectors:
[<leak_vector ids actually checked this run>]` -- never an unqualified
`dispatchIsolation: true` (see "Why `dispatchIsolation: true` overstates
verification" below).
```

### Why a freshly-established (same-run) recipe still needs a human eye, and why `dispatchIsolation: true` overstates verification

An independent adversarial review found two related gaps the first draft did not name:

- **The script's own control-pass/fail logic can be wrong, with no human watching.** Today's manual procedure has an operator directly read both control transcripts before trusting the result. Automating it removes that observation for the "no match found" branch -- a bug in the script (matching the wrong output field, a subprocess race, a sentinel-text check that is too loose) could report "both controls passed" when isolation actually failed, and nothing catches it. Mitigation adopted: on every freshly-established (same-run) verification, the script prints the full transcripts, not a bare pass/fail, so an interactive operator's own terminal still shows the same evidence the manual procedure always did; the scheduled CI job's own `--controls-only` mode never launches a real dispatch off a same-run result in the same run (see Components item 4), so a script bug there can at most log a wrong same-run entry for the next PR reviewer to catch, never launch a contaminated review.
- **`dispatchIsolation: true` implied more than the script actually checks.** The automated two-control procedure verifies exactly one leak vector (`claude_md_agents_md`); the separately-documented `$HOME`/task-list leak vector is explicitly out of that procedure's own scope and, per the registry's own most recent entry, was "not re-tested or closed" as of this design. A caller reading a bare `dispatchIsolation: true` cannot tell which vector was actually checked. Fixed by returning `verifiedLeakVectors` (the exact list checked this run) instead of a single boolean.

### Why this closes the circularity

The controls are always executed by the orchestrator's own process (an interactive session's shell, or the scheduled job's own runner) -- never by the dispatch under review. The dispatch being asked to do real review work never verifies its own isolation; it only ever inherits an already-established, externally-verified recipe. This directly replaces the self-report ("I don't see a CLAUDE.md") this session observed being correctly, but unhelpfully, flagged as unverifiable by the dispatch itself.

## Components

1. **`skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py`** -- the primitive itself, per the Architecture section above. Its own module docstring carries the two-control methodology and the historical rationale/caveats extracted out of `adversarial-self-audit.md` (matching this repository's existing convention of extensive rationale docstrings on its other bundled scripts). The exact two-control methodology to translate into code is the one currently documented as of this design's writing in `adversarial-self-audit.md`'s own "Verification procedure" subsection (positive control: a synthetic sentinel `CLAUDE.md` in an isolated directory outside any real repository; negative control: an identical isolated setup with no `CLAUDE.md`/`AGENTS.md` anywhere in its own directory ancestry) -- this design does not restate that full procedure, only points at its current source.
2. **`skills/evaluating-skill-quality/metadata/isolation-registry.yaml`** -- structured data, one entry per (identifying-signal-set, mechanism) pair. Fields, widened from the first draft after an independent adversarial review found the flat schema below could not actually hold the registry's own real content: `identifying_signals`, `mechanism`, `leak_vector` (which contamination axis this entry addresses -- e.g. `claude_md_agents_md`, `home_task_list`, `sessionstart_hook_plugin` -- since a single dispatch's isolation can hold for one axis while remaining unverified for another), `result`, `verified_alternative` (the exact env/cwd recipe), `companion_flags` (e.g. `--allowedTools`, `--permission-mode`, when the recipe needs them to work), `methodology_pitfalls` (a list; a false-negative/false-positive mode discovered while establishing this entry, e.g. the `$PWD`-vs-real-`cwd` bug or the Read-tool sandbox-confinement bug already on record), `trust_class` (`reviewed` | `same-run-unreviewed`), `date`, `notes` (a list, not a single scalar -- room for a retraction or a superseding entry's own back-reference, not only a short caveat). Placed as a sidecar file separate from `metadata/gitapex.yaml`'s own schema -- confirmed by directly reading every module in `skills/evaluating-skill-quality/scripts/shape_checks/` (not only `constants.py`/`field_checks.py`) that `SIDECAR_RELATIVE_PATH` is an exact, single hardcoded path (`metadata/gitapex.yaml`), and that none of the package's several directory-walking checks (`field_checks.py`'s symlink/special-file safety scan, `bundled_scripts.py`'s `scripts/` walk, `orchestrator.py`/`citation_checks.py`'s `references/` walk) ever touches `metadata/` beyond that one exact path -- so an additional file here changes none of the shape checker's existing checks (re-verify the exact current count at implementation time rather than trusting a number recorded here).
3. **Generated Markdown view** (replacing today's hand-written Known entries prose in `adversarial-self-audit.md`, or a new adjacent file) -- rendered from `isolation-registry.yaml`, kept for human browsability and PR-diff review. Treated as **conditional** reference material going forward: relevant only when a human is reviewing a Same-run entry for promotion to Reviewed, or when someone is maintaining the script itself -- not needed for ordinary dispatch operation, since ordinary operation now just calls the script.
4. **`.github/workflows/isolation-registry-refresh.yml`** (new, scheduled) -- runs the same script in `--controls-only` mode on a schedule. On finding a new same-run-unreviewed entry, it opens a pull request proposing the registry update; it must never auto-merge or auto-promote an entry to `reviewed` trust class -- that still requires the existing human/PR review gate, preserving the Trust class rule's actual safety property (an entry becomes Reviewed once merged, not once written). If a live control run itself fails in a way suggesting a *new* contamination pattern (not merely "not yet verified at this version"), the job opens an issue rather than silently no-op'ing, mirroring `merge-retrospective`'s own gate-proposal pattern. `--controls-only` mode never launches a real target dispatch, on a same-run or reviewed entry alike -- the one code path in this whole design that is allowed to establish a same-run entry with zero human ever watching it live, precisely because it is also the one path guaranteed not to act on that entry in the same run (see "Why a freshly-established recipe still needs a human eye," above).

   **CI-platform scope, named explicitly (an independent adversarial review found this unaddressed in the first draft).** Every existing registry entry is keyed to an interactive `CLAUDE_CODE_REMOTE=true` session; a GitHub Actions runner is a distinct identifying-signal set with no existing entry, so this workflow's own first run establishes its own from-scratch same-run entry the same way any new environment would -- the script's own step 2/3 logic (no match -> run controls) already covers this without special-casing it. What the workflow does need, and what this design explicitly scopes in: a `claude` CLI install and an `ANTHROPIC_API_KEY` secret, provisioned the same way `.github/workflows/skill-eval-gate.yml` already provisions both for its own job (pinned npm install, a fail-loud preflight check for the secret's presence) -- not a new pattern, reuse of an existing one.

## `adversarial-self-audit.md` restructuring

- The Isolation verification section shrinks to a short, unconditionally-loaded pointer: "Required, not optional: dispatch via `gitapex_run_verified_isolated_dispatch.py`; do not hand-roll the Verification procedure or launch a bare `Agent`-tool/`claude -p` dispatch directly." Its role (self-guard, content-independent of the reviewed target) is unchanged, so it stays part of the file's unconditional common-case load.
- The detailed two-control methodology moves into the script's own module docstring.
- The historical Known entries move into `isolation-registry.yaml`, with a generated summary view treated as newly-conditional material (see Components item 3).

## Migration

All historical Known entries (dated 2026-07-28 onward, on the order of a dozen dated/reconfirmed entries as of this writing) are migrated into `isolation-registry.yaml` now, not only new entries going forward -- an explicit operator choice, made knowing this requires judgment calls on a handful of entries whose prose blends "mechanism" and "caveat" language loosely.

**Corrected trust-class rule (an independent adversarial review found the first draft's own rule vacuous).** The first draft said "reachable through a merged PR migrates as `reviewed`," but every entry in the current, already-merged `adversarial-self-audit.md` is by definition reachable through a merged PR -- including the several entries whose own prose explicitly says "Same-run, unreviewed." Applying that rule literally would silently promote every one of them to `reviewed` during migration, erasing exactly the distinction the file's own Trust class section calls load-bearing. The corrected rule: `trust_class` is carried forward from **each entry's own already-stated label in its current prose**, never re-derived from the file's own merge status -- an entry whose text says "Reconfirmed... Same-run, unreviewed" migrates as `same-run-unreviewed`; an entry with no such qualifier (the ordinary case) migrates as `reviewed`. This is a straight transcription of each entry's own existing self-classification, not a new judgment call the migration invents.

## Error handling

- No verified mechanism available (neither a matching Reviewed entry nor a successful live control run) -- exit non-zero, never falling back to an unverified dispatch. This preserves, not merely gestures at, the existing "No verified mechanism available" Stop-boundary's own specific required shape (issue #1410): a fenced code block offering exactly two named options, an environment fix or a hand-off to an already-verified environment, with concrete copy-pasteable commands for each -- an independent adversarial review flagged the first draft's "exit non-zero with a clear message" as a weaker, unstated reduction of that existing rule; this revision keeps the richer format as the actual requirement.
- The scheduled job's own control run failing in a way suggesting a genuinely new contamination pattern -- opens an issue, never a silent no-op.

## Testing

- The registry's own read/write/matching logic (pure Python: does a given identifying-signal set match a stored entry, does the YAML round-trip, does the Markdown regenerate correctly) gets ordinary unit tests, following this repository's own script-test-quality conventions.
- The live two-control behavior itself (does `claude -p` actually behave as expected against a real CLI) is not CI-mockable and stays a live-verification-only concern, consistent with how this repository already treats it (dated, versioned entries rather than a fixed CI assertion).
- **The workflow's own "propose via PR, never auto-promote" governance guarantee gets its own test** (an independent adversarial review found the first draft's Risks section demanded this proof without the Testing section ever providing it): a unit or integration test asserting the workflow's own code path contains no merge/auto-promote API call reachable from the `--controls-only` result-handling branch -- not merely asserted in prose.

## Consequences for dependent skills

Any skill that later switches to calling this primitive (`battle-testing-a-skill`, `scorer-gated-skill-edits`, and others not yet identified) creates a `requires`-level cross-skill dependency and must:

- Declare `spec.skillDependencies.requires: [evaluating-skill-quality]` in its own `metadata/gitapex.yaml`.
- Cite only this one script's stable CLI entrypoint (no fan-out into `evaluating-skill-quality`'s other internals), satisfying the "no fan-out" / "a clean interface" tests in `references/rubric.md`'s Sibling-skill dependency portability subsection (the same rules this repository's own PR #1793 just wrote).
- Reclassify from `Portable` to `Mixed` or `Repository-scoped` as appropriate, since `requires-portability-compatible` already forbids a non-empty `requires` list on a `Portable`-declared skill.

This migration for each dependent skill is each skill's own follow-up unit of work, not part of this sub-project's own deliverable (which is limited to making the primitive exist with a stable contract).

## Risks

Items 1-3 below carry a `(reviewed)` tag: named or corrected as a direct result of the independent adversarial review this design underwent before issue formalization (see Status); the fixes are already folded into the sections above, and each entry here states the residual exposure that remains even with the fix applied.

- **CLI-contract-break risk (unmitigated by this sub-project alone).** A future change to `evaluating-skill-quality`'s own `SKILL.md`/`rubric.md`/the script itself could silently break the primitive's CLI contract for every dependent skill. The existing `skill-dependencies-resolve` shape check verifies only that a required sibling directory exists, not that its CLI contract is intact. This is a natural candidate for sub-project 2's own cross-skill-impact machinery to eventually close; it is disclosed here as a known, currently-open gap, not solved by this design.
- **Migration judgment risk *(reviewed)*.** Converting a dozen-plus prose entries into structured fields requires some interpretive judgment; a mis-migrated `notes` entry (or a `leak_vector`/`methodology_pitfalls` field populated from an ambiguous source sentence) is a plausible, low-severity defect to watch for during implementation review. The corrected trust-class rule (see Migration) removes the more serious version of this risk (silent trust *upgrade*, not merely lossy wording) but does not remove ordinary transcription risk.
- **CI-governance risk *(reviewed)*.** The scheduled job's own "propose via PR, never auto-promote" constraint is now a stated Testing requirement (see Testing), not merely an assertion -- residual risk is limited to that test itself being incomplete or circumvented by a future edit that the test does not cover.
- **Script control-logic risk *(reviewed, newly named)*.** A bug in the script's own comparison logic could report both controls as passing when isolation actually failed, with no human necessarily reading the transcripts before a same-run entry is trusted. Mitigated, not eliminated, by printing full transcripts on every same-run establishment (see Architecture) and by `--controls-only` mode never launching a real dispatch off a same-run result in the same run -- an interactive session's own operator can still miss a subtly wrong transcript even when it is printed in full.
- **Registry-schema completeness risk *(reviewed, newly named)*.** The widened schema (see Components item 2) is still a design-time best guess at what fields the registry's real content needs; a future entry class not anticipated here (a fourth leak vector, a new kind of methodology pitfall) may still not fit cleanly, the same open-ended risk any fixed schema carries.

## Open questions

- Gap (C) (a family-maturity index) remains unscheduled; not part of either sub-project.
- Which additional skills beyond `battle-testing-a-skill`/`scorer-gated-skill-edits` will eventually need this primitive is not yet enumerated -- left to each skill's own future migration decision.

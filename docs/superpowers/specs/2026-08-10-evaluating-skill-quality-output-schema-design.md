# evaluating-skill-quality output-record schema -- design

Date: 2026-08-10
Issue: #1002 (refs #500, #584, #614, #619, #1001, #1014)

## Design-only scope

Per #1002's own Constraints ("Implementation is separate follow-on work;
this issue proposes and scopes ... not implements") this doc resolves the
open design questions #1002 named -- schema field set, versioning
strategy, scorer-integration mechanism, disclosure-gate impact, and a
retrofit-cost estimate -- as a decision record only. No
`skills/evaluating-skill-quality/references/output-schema.json` file, no
`gitapex_score_contract.py` change, and no fixture migration is introduced
by this pass; a follow-on issue implements what this doc decides (see
Sequencing). Matches the same "Design-only scope" discipline
`docs/superpowers/specs/2026-07-17-gate-audit-trail-tradeoff.md` used for
its own precondition-gated design pass.

## Sequencing precondition (re-checked this session, not assumed)

#1002's own Constraints gate implementation -- not this design pass -- on
the `rubric.md` pruning-only chain "settling": no further pruning-only
pass against `rubric.md`'s dimensions 1-9 open or in flight. Re-checked
directly against GitHub state this session (`mcp__github__issue_read`,
`search_issues`, `search_pull_requests`), not assumed from the issue body:
`#1001` (retemplate+prune) and `#1014` (Tier 1 pruning, ~110-120 lines)
are both merged (`#1014` closed `state_reason: completed`, folded into
merged PR #1018). A search for an open Tier 2 follow-up
(`"Tier 2" rubric.md state:open`, `"70-90" rubric.md state:open`) and for
any open PR touching `rubric.md` both returned zero results. The
sequencing precondition holds as of this design pass; a later
implementing session should re-run the same two searches rather than
trust this paragraph, per this repository's own re-verify-at-
implementation-time convention.

## 1. Facts

- No output-record schema exists under
  `skills/evaluating-skill-quality/references/` today (confirmed: no
  `output-schema.json` or `*.schema.json` under that directory).
- Two precedents exist and were read directly this session:
  - `skills/evaluating-deterministic-gate-quality/references/output-schema.json`
    -- a structured **review-result object** for that skill's own
    per-artifact verdict: `schemaVersion` (a `const` string, bumped and
    re-described on every breaking or field-adding revision),
    `reviewMeta.actor{ref, provenance, verification}` (self-asserted vs.
    verified identity, never conflated), `mechanismFit`, a `findings[]`
    array keyed by `dimensionId` with `verdict` (`pass`/`fail`/
    `not_applicable`/`indeterminate`) and `evidence[]` (`quote`+
    `sourceRef`), `crossCuttingAxes`, and a `persistenceRecommendation`
    object that explicitly recommends storage channels without ever
    writing anywhere itself.
  - `skills/scorer-gated-skill-edits/references/eval-run.schema.json` --
    a **run record**: one committed JSON object per completed gate run
    (`date`, `issue`, `commit`, `runner`, `gate.verdict`
    `KEEP`/`REJECT`, `known_gaps`), append-only, with an optional
    `supersedes` field naming the earlier record a corrected run
    replaces -- "a correction is a new record naming its predecessor,
    never an edit to it."
  - These answer two different questions (what did one review conclude,
    vs. what happened when a gate ran) and neither is evaluating-skill-
    quality's own shape today; both are cited by #1002 as precedent for
    field-set and versioning discipline, not as templates to copy
    verbatim.
- The only current consumer of an `evaluating-skill-quality` verdict,
  `.github/scripts/gitapex_gate_skill_audit_disclosure.py`, parses one of
  three literal free-text tokens
  (`WELL-FORMED-AND-MATURE`/`WELL-FORMED-NOT-MATURE`/`NOT-WELL-FORMED`,
  or a `WAIVED: <reason>` line) out of a PR body's `## Skill audit
  evidence` section via `_LINE_PATTERNS`/`_VERDICTS` (read directly this
  session, lines 186-225). It checks that a token was disclosed, never
  that the underlying nine-dimension walk actually happened or reached
  that conclusion honestly.
- `evals/evaluating-skill-quality/eval-status.md:491-494` (read directly)
  names the exact construct-validity gap #1002 exists to close: "a
  substring scorer that confirms expected keywords appear, not that the
  full nine-dimension walk or Blind Spot Pass actually ran."
  `gitapex_score_contract.py`'s `score()` function (read directly,
  lines 158-229) computes a `[0,1]` fraction of satisfied
  `output_contains`/`output_not_contains`/`_icontains`/`_near` substring
  assertions against free-text `output_text` -- it has no concept of a
  dimension, an evidence citation, or a verdict token as a structured
  field.
- `gitapex_score_contract.py`'s CLI already carries the precedent for
  attaching an out-of-band verdict without touching the substring score:
  `--judge-verdict` and `--dispatch-trace-verdict` (issue #584) each take
  an already-computed verdict from the caller and append it as "an
  additional recorded field, never blended into the substring mean or
  verdict" (module docstring, read directly). `--dispatch-trace-verdict`
  specifically takes a three-state answer
  (`DISPATCH_TRACE_CONFIRMED`/`_NOT_CONFIRMED`/`_UNVERIFIED`) computed by
  a **separate** checker script
  (`evals/scripts/gitapex_check_dispatch_trace.py`) that inspects a run's
  transcript; `gitapex_score_contract.py` never inspects a transcript
  itself.
- `SKILL.md`'s Procedure section (read directly) names six ordered steps
  producing: a deterministic shape-check result (step 3, PASS/FAIL per
  check, main-thread, before dispatch), a whole-artifact wrong-mechanism
  finding and a whole-artifact cohesion finding plus step-level
  Mechanism-fit findings and a Blind spot pass result (step 2), a
  portability level and capability assumption plus Compatibility- and
  Confidentiality-awareness (step 4), a per-dimension walk over all nine
  dimensions with cited evidence (step 5), and a verdict per
  `rubric.md`'s Verdicts section (step 6) -- `Well-formed`/
  `Not-well-formed`/`Mature`/`Indeterminate`, each defined with a
  specific, non-overlapping precondition (`rubric.md:1950-2015`, read
  directly). The Mechanism fit section's own cohesion taxonomy
  (`functional, sequential, communicational/informational, procedural,
  temporal, logical, coincidental`) and its named step-level checks
  (currently at least: Skill-step vs. bundled script, Model/effort tier
  fit, Tool-capability verification, Subagent delegation scope
  [`#495`], Invocation-mode fit [`#652`]) are both open-ended and have
  grown by name at least twice since the Procedure text's own "four
  step-level" count was last written -- confirmed by direct read of
  `skills/evaluating-skill-quality/metadata/gitapex.yaml`'s decision log,
  not assumed; the exact current count needs re-verification against
  `SKILL.md`/`rubric.md` at implementation time, same as every line
  number cited above.
- `evals/evaluating-skill-quality/tasks/*.yaml` (70 fixtures, confirmed
  by direct `ls` count) all grade free prose via
  `output_contains`/`output_not_contains`; none require or expect a
  structured JSON block in a review's output today (spot-checked one
  fixture, `ablation-capability-already-run.yaml`, directly).
- `skills/evaluating-skill-quality/references/state-management-quality.md`
  (added per `#913`) already grades, as a conditional dimension-6
  sub-check, exactly the property a new committed schema instance would
  become: "state materialized outside the agent context and read back
  across a dispatch, compaction, session, or later invocation," graded
  against a precedence spine "ground truth > durable artifact > harness
  state > context." A structured output record is a durable artifact by
  that same rubric's own vocabulary -- worth citing when the follow-on
  implementation eventually applies `evaluating-skill-quality` to its
  own new schema file, not something this design doc needs to resolve.

## 2. Decision 1 -- schema shape and field set

Model the new schema as a **review-result object**, structurally closer
to `evaluating-deterministic-gate-quality`'s `output-schema.json` than to
`eval-run.schema.json` (a run-record schema answers "what happened when a
gate ran," not "what did one nine-dimension walk conclude") -- but reuse
`eval-run.schema.json`'s append-only/`supersedes` discipline for
corrections, since #1002 explicitly asks for both precedents' evolution
discipline, and this repository's own gate-run history
(`adversarial-self-audit.md`'s decision log, e.g. `#1001`'s
KEEP->UNVERIFIED correction) shows a review verdict does get corrected
after the fact often enough to need a named mechanism for it, the same
way a run record does.

Draft field set below (illustrative JSON Schema, draft 2020-12 -- **not**
committed by this pass; the implementing issue re-verifies every field
name, enum value, and cited line/count against `main` at that time, per
this repository's own re-verify-at-implementation-time convention, and
may adjust shape during that implementation's own review):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/tvna/gitapex/blob/main/skills/evaluating-skill-quality/references/output-schema.json",
  "title": "SkillQualityReviewResult",
  "description": "Structured output contract for evaluating-skill-quality's Procedure step 6 verdict. Draft only as of #1002's design pass -- see docs/superpowers/specs/2026-08-10-evaluating-skill-quality-output-schema-design.md.",
  "type": "object",
  "required": ["schemaVersion", "reviewMeta", "shapeCheck", "mechanismFit", "dimensions", "verdict"],
  "additionalProperties": false,
  "properties": {
    "schemaVersion": { "type": "string", "const": "1.0.0" },

    "reviewMeta": {
      "type": "object",
      "required": ["actor", "targetRepoRef", "artifactRef", "skillBuildRef"],
      "description": "Reuses evaluating-deterministic-gate-quality's own reviewMeta shape verbatim (actor{ref,provenance,verification}, targetRepoRef, artifactRef, skillBuildRef, dispatchIsolation) for one family vocabulary across both skill-quality-review schemas, rather than a second, subtly different reviewMeta shape.",
      "properties": {
        "actor": { "type": "object", "required": ["ref", "provenance"] },
        "targetRepoRef": { "type": "string" },
        "artifactRef": { "type": "string", "description": "The reviewed skill's directory, e.g. skills/duplicate-ticket-detector." },
        "skillBuildRef": { "type": "string", "description": "Commit or ref of SKILL.md/references/* that produced this verdict." },
        "dispatchIsolation": { "type": "boolean" }
      }
    },

    "shapeCheck": {
      "type": "object",
      "required": ["checkerRef", "checks"],
      "description": "Step 3's deterministic result -- reported structurally so a consumer can assert PASS/FAIL per named check instead of grepping prose.",
      "properties": {
        "checkerRef": { "type": "string", "description": "e.g. scripts/gitapex_check_skill_shape.py, or 'manual' when Python is unavailable." },
        "checks": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "verdict"],
            "properties": {
              "name": { "type": "string" },
              "verdict": { "enum": ["PASS", "FAIL"] },
              "detail": { "type": "string" }
            }
          }
        }
      }
    },

    "mechanismFit": {
      "type": "object",
      "required": ["wrongMechanism", "cohesion", "blindSpotPass"],
      "properties": {
        "wrongMechanism": {
          "type": "object",
          "required": ["finding"],
          "properties": {
            "finding": { "type": "boolean" },
            "betterMechanism": { "enum": ["hook", "subagent", "claude-md", "output-style", "system-prompt-append", "rule", "none"] },
            "reason": { "type": "string" }
          }
        },
        "cohesion": {
          "type": "object",
          "required": ["dominantType"],
          "description": "rubric.md's own seven-type taxonomy, cited verbatim.",
          "properties": {
            "dominantType": { "enum": ["functional", "sequential", "communicational-informational", "procedural", "temporal", "logical", "coincidental"] },
            "splitRecommended": { "type": "boolean" },
            "reason": { "type": "string" }
          }
        },
        "stepLevelFindings": {
          "type": "array",
          "description": "check is a free-form string, not a closed enum: the named step-level Mechanism-fit checks have grown twice already (Subagent delegation scope, #495; Invocation-mode fit, #652) and a closed enum would need a schema bump on every future addition -- same reasoning the runtime-compatibility-matrix schema (docs/superpowers/specs/2026-08-08-w2-runtime-compatibility-matrix-schema-design.md) already used for its own open runtimes map.",
          "items": {
            "type": "object",
            "required": ["check", "finding"],
            "properties": {
              "check": { "type": "string" },
              "finding": { "type": "boolean" },
              "detail": { "type": "string" }
            }
          }
        },
        "blindSpotPass": {
          "type": "object",
          "required": ["gapFound"],
          "properties": {
            "gapFound": { "type": "boolean" },
            "description": { "type": "string" }
          }
        }
      }
    },

    "portabilityLevel": { "enum": ["Portable", "Repository-scoped", "Mixed"] },
    "capabilityAssumption": { "enum": ["Broad", "Frontier", "Adaptive"] },

    "compatibilityAwareness": {
      "type": "object",
      "description": "Warning-only, never participates in the verdict (rubric.md:1996-1998).",
      "properties": {
        "runtimeBehaviorDiffersUndisclosed": { "type": "boolean" },
        "note": { "type": "string" }
      }
    },
    "confidentialityAwareness": {
      "type": "object",
      "description": "Warning-only, mirrors compatibilityAwareness's own shape (#537).",
      "properties": {
        "exposureRisk": { "type": "boolean" },
        "note": { "type": "string" }
      }
    },

    "dimensions": {
      "type": "array",
      "minItems": 9,
      "maxItems": 9,
      "description": "One entry per rubric.md dimension 1-9, in order. A follow-on drift-gate test (not this schema) must assert dimensionId values are exactly {1..9} with no duplicate or gap -- JSON Schema draft 2020-12 cannot express 'each value in {1..9} appears exactly once' cleanly without a per-value if/then chain that would itself become the next drift risk; eval-run.schema.json's own split const already accepts a test-enforced invariant over a schema-enforced one for a comparable case.",
      "items": {
        "type": "object",
        "required": ["dimensionId", "verdict"],
        "properties": {
          "dimensionId": { "type": "integer", "minimum": 1, "maximum": 9 },
          "verdict": {
            "enum": ["clear", "gap-minor", "gap-major", "unmeasured"],
            "description": "'unmeasured' is legal only for dimensionId 8 or 9 (rubric.md's Verdicts section: dimensions 8-9 are the one exception where a named-but-unmeasured gap does not block Mature). A follow-on drift-gate test enforces that conditional restriction; expressing it as a schema if/then keyed on dimensionId is possible but was not drafted here, left for implementation-time judgment."
          },
          "evidence": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["quote", "sourceRef"],
              "properties": {
                "quote": { "type": "string" },
                "sourceRef": { "type": "string" }
              }
            }
          }
        }
      }
    },

    "verdict": {
      "type": "object",
      "required": ["token"],
      "properties": {
        "token": { "enum": ["Well-formed-and-mature", "Well-formed-not-mature", "Not-well-formed", "Indeterminate"] },
        "reason": { "type": "string", "description": "Required when token is Not-well-formed or Indeterminate, per rubric.md's own Verdicts section ('State the specific failing check(s)' / 'State the concrete blocking cause'). Left as a prose requirement here rather than a schema if/then -- straightforward to add at implementation time." }
      }
    },

    "supersedes": {
      "type": "string",
      "description": "Optional. When this record corrects an earlier one, a reference to the record it replaces -- reusing eval-run.schema.json's own 'a correction is a new record naming its predecessor, never an edit to it' convention."
    }
  }
}
```

Deliberately **not** drafted here, left to the implementing issue: the
exact conditional `if`/`then` blocks enforcing (a) dimension IDs 1-9 each
appear exactly once, (b) `unmeasured` is legal only for dimensions 8-9,
and (c) `verdict.reason` is required for `Not-well-formed`/`Indeterminate`
-- `output-schema.json`'s own precedent (its dimension-23 `if`/`then`
block) shows the mechanism exists in this repository's established
JSON Schema style; writing the exact predicate correctly deserves its own
implementation-time review pass rather than a first draft nobody
re-checks.

## 3. Decision 2 -- versioning strategy

Adopt `output-schema.json`'s own `schemaVersion` `const`-string
discipline (a revision that adds a required field or tightens validation
bumps the const and documents exactly what changed and why, so a
drift-detecting comparison across two stored instances never silently
treats a 1.0.0 instance and a 1.1.0 instance as graded alike) as the
schema's own evolution guard, **plus** the optional `supersedes` string
field from `eval-run.schema.json` for a corrected *instance* of an
otherwise-unchanged schema version (a review that was wrong and is
replaced, not a schema that changed shape). The two are answers to
different questions -- "did the grading rules change" vs. "was this
specific verdict wrong" -- and #1002 asks for both precedents' discipline
together, not a choice between them.

## 4. Decision 3 -- scorer-integration mechanism

Recommend: **extend `gitapex_score_contract.py`'s existing out-of-band
verdict pattern**, not replace its substring scorer and not introduce a
parallel scorer script.

`--judge-verdict` and `--dispatch-trace-verdict` already establish the
exact shape needed: a caller-computed verdict, appended as "an additional
recorded field, never blended into the substring mean or verdict"
(module docstring, confirmed by direct read). Concretely:

- A new checker, `evals/scripts/gitapex_check_schema_conformance.py`,
  mirroring `gitapex_check_dispatch_trace.py`'s own role: it extracts a
  fenced JSON block from a run's output, validates it against
  `skills/evaluating-skill-quality/references/output-schema.json`, and
  returns a three-state verdict
  (`SCHEMA_CONFIRMED`/`SCHEMA_INVALID`/`SCHEMA_NOT_ATTEMPTED`) --
  `SCHEMA_NOT_ATTEMPTED` covers a run that (legitimately, during the
  opt-in adoption window described in Decision 4 below) emitted no
  structured block at all, distinct from one that tried and failed
  validation.
- A new `gitapex_score_contract.py` CLI flag,
  `--schema-conformance-verdict`, appends that already-computed verdict
  as a recorded field on the score record, exactly like
  `--dispatch-trace-verdict` does today -- `gitapex_score_contract.py`
  itself never parses or validates JSON; that stays the new checker's
  job, keeping the substring scorer's own responsibility unchanged.
- This buys the actual thing `eval-status.md`'s named gap complains
  about -- "confirms expected keywords appear, not that the full
  nine-dimension walk ... actually ran" -- because
  `SCHEMA_CONFIRMED` requires all nine `dimensions[]` entries with
  `dimensionId`s 1-9 to be present with a non-empty `evidence[]` citing a
  real `sourceRef`, which a keyword-stuffed non-walk cannot satisfy by
  accident the way a substring match can.

Rejected alternative: a from-scratch "successor scorer" replacing
`gitapex_score_contract.py`'s substring logic wholesale. Rejected because
(a) it would touch every one of the 70 existing fixtures' scoring path
at once, a far wider blast radius than #1002's own stated goal, and (b)
the existing substring scorer earns its keep independently of this gap --
it is also the scorer for `scorer-gated-skill-edits`' pruning-only gate
(the exact mechanism `#1014`/`#1018` just used), and #1002's own
Non-goals already rule out "replacing the substring scorer, or adding
semantic grading."

## 5. Decision 4 -- disclosure-gate impact: none

`.github/scripts/gitapex_gate_skill_audit_disclosure.py` keeps checking
exactly what it checks today -- a free-text `WELL-FORMED-AND-MATURE`-style
token (or `WAIVED: <reason>`) in a PR body's `## Skill audit evidence`
section. Nothing in Decisions 1-3 touches that file, its `_VERDICTS`
table, or its regex patterns. The new schema is consumed only inside the
`evals/` eval-suite path (`gitapex_score_contract.py` +
`gitapex_check_schema_conformance.py`), never by the PR-body disclosure
path -- per #1002's own Constraints, "the free-text token disclosure
this script already enforces stays a valid, checked path unless a design
spec explicitly proposes replacing it," and this one does not propose
that.

## 6. Retrofit cost estimate (ACM row 2's residual risk, sized)

Adoption is opt-in, not a forced migration of all 70 existing fixtures:

- **Zero-cost baseline.** Every existing fixture keeps scoring exactly as
  it does today (`output_contains`/`output_not_contains` against prose).
  `--schema-conformance-verdict` is an additional, optional flag; a run
  that supplies no JSON block scores `SCHEMA_NOT_ATTEMPTED` and the
  substring score is unaffected, matching how `--dispatch-trace-verdict`
  already coexists with every pre-#584 fixture.
- **New/updated-fixture cost.** A fixture built to actually exercise
  schema conformance needs its `inputs.prompt` to ask for the structured
  block (a one- or two-sentence addendum to `SKILL.md`'s Procedure step
  6, e.g. "close with a fenced \`\`\`json block conforming to
  `references/output-schema.json`") and its `expected` block to gain
  schema-conformance assertions rather than (or alongside) substring
  ones. Estimate: a handful of new selection-split fixtures (2-5,
  matching the size of prior single-check additions like `#495`'s two or
  `#537`'s two) purpose-built to prove the schema-aware checker actually
  discriminates a real nine-dimension walk from a keyword-stuffed
  non-walk -- not a retrofit of all 70.
- **SKILL.md/Procedure cost.** One short addendum to Procedure step 6
  (the structured-block instruction above) plus a corresponding
  `scorer-gated-skill-edits` gate run on that `SKILL.md` edit itself,
  since it is a real rubric-adjacent change, not documentation-only.
- **Explicitly not sized here, flagged as the implementing issue's own
  first task:** whether every one of the 70 existing fixtures should
  eventually gain the addendum too (full retrofit), and if so, in how
  many batches -- #1002's own Non-goals already excludes "retroactively
  requiring schema-conformant output from any already-recorded eval run,"
  which bounds this to new fixtures only unless a future issue decides
  otherwise.

## 7. Non-goals (mirrors #1002's own)

- Does not add `skills/evaluating-skill-quality/references/output-schema.json`
  itself, `gitapex_check_schema_conformance.py`, or the
  `--schema-conformance-verdict` flag -- Decisions 1-4 above are the
  design; implementation is the follow-on issue in Sequencing.
- Does not touch `gitapex_gate_skill_audit_disclosure.py` (Decision 4).
- Does not migrate any of the 70 existing fixtures.
- Does not run the Phase 2 cross-model measurement (#1002's own third
  ACM row) -- that is explicitly sequenced after the schema-aware scorer
  ships, per #1002's own Constraints.
- Does not change `evaluating-deterministic-gate-quality`'s or
  `scorer-gated-skill-edits`' own existing schemas; both are cited as
  precedent only.

## 8. Sequencing

This design pass lands as a docs-only PR (this file plus the branch
plan/ACM in the PR body). The follow-on implementation issue should scope,
in order:

1. `skills/evaluating-skill-quality/references/output-schema.json`,
   refining Decision 1's draft (including the three deferred `if`/`then`
   predicates) and re-verifying every cited line/count against `main` at
   that time.
2. `evals/scripts/gitapex_check_schema_conformance.py` and the
   `--schema-conformance-verdict` flag on `gitapex_score_contract.py`
   (Decision 3), each with its own unit tests mirroring
   `gitapex_check_dispatch_trace.py`'s and `--dispatch-trace-verdict`'s
   existing test shape.
3. The `SKILL.md` Procedure step 6 addendum plus its own
   `scorer-gated-skill-edits` gate run (Decision 4's zero-disclosure-
   impact claim re-verified live, not assumed, once the addendum text
   exists).
4. 2-5 new selection-split fixtures purpose-built to prove the schema-aware
   checker discriminates a real walk from a keyword-stuffed non-walk
   (Decision 6).
5. Only after 1-4 reach their own gate KEEP: the Phase 2 cross-model
   measurement run (#1002's own third ACM row), scored with the new
   schema-aware checker instead of the current substring-only one.

## 9. Verification (this design-only pass)

- This file exists at `docs/superpowers/specs/2026-08-10-evaluating-skill-quality-output-schema-design.md`
  and is internally consistent with the two cited precedent schemas (spot-read
  both files directly this session, cited above).
- PR body carries the Acceptance Criteria Map table, checked with
  `python3 skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py --body <file>`.
- PR body carries a `## Skill audit evidence` section -- not applicable
  here (no `SKILL.md` added or modified by this diff), stated explicitly
  in the PR body rather than left silent, per this repository's own
  disclosure-gate applicability rule (`gitapex_gate_skill_audit_disclosure.py`'s
  own scope note: it fires on a changed `SKILL.md` or a changed
  `docs/superpowers/specs/*.md` design doc -- this diff is the latter, so
  the `design-doc-adversarial-review` process-disclosure line applies and
  is included).
- `git diff` touches only this new file (docs-only PR, per Decision-scope
  and #1002's own Constraints).

# diagnosing-a-failure: a DDD-bounded reinterpretation of systematic-debugging, through implementation

Date: 2026-08-29

Refs [#1155](https://github.com/tvna/gitapex/issues/1155).

## Scope

This pass covers design **and** implementation in one PR: this doc, plus
`skills/diagnosing-a-failure/SKILL.md` and its `references/` and
`metadata/gitapex.yaml`, plus `evals/diagnosing-a-failure/`, plus a
one-paragraph routing addition each into `planning-a-branch-from-an-issue`
and `executing-a-branch-plan`. This supersedes #1155's own original
"design doc only" framing (its Proposed solution's closing sentence and
its former Non-goals lines retracting "does not implement" and "does not
revise `fixing-a-reported-issue`") -- #1155's own 2026-08-29 "scope
extended through implementation" update states this explicitly, following
the same precedent #1163 set for #1258.

## Why this doc exists

`skills/` owns no general-purpose, in-session debugging mechanism today;
gitapex is retiring its `obra/superpowers` apm dependency by
re-implementing each remaining un-ported mechanism natively rather than
continuing to vendor it, and `systematic-debugging` is one of those. A
design-only pass authored a consolidated record of DDD Context Mapping +
Ubiquitous Language work against this exact question, published as an
artifact and summarized in #1155's own first comment
(2026-08-16); the repository owner subsequently accepted four further
refinements sourced from a comparison against `cursor/plugins/pstack`,
posted as #1155's second comment (2026-08-29). **Both inputs predate
#1155's own most consequential fact: `fixing-a-reported-issue`, the
Customer/Supplier counterpart both the artifact and the pstack comment
assumed still existed, was fully retired via
[#1275](https://github.com/tvna/gitapex/issues/1275) between the artifact
being written and this doc being authored.** This doc treats both prior
inputs as draft material, not pre-verified fact -- per the Method section
below -- re-targets every routing decision at `fixing-a-reported-issue`'s
actual successors, and folds in the four accepted pstack refinements the
artifact's own sequence never reached.

## Method

Per `planning-a-branch-from-an-issue/SKILL.md` Step 5, #1155's own two
Acceptance Criteria Map tables (one from its original body, one from its
"scope extended through implementation" update) are treated as draft
input, independently re-checked against live repository state, not
adopted merely for being well-formed. The design-only artifact
(2026-08-16) was read in full and is treated the same way: useful
groundwork, not a settled decision, because two of its own load-bearing
premises no longer hold --

1. **`fixing-a-reported-issue` no longer exists.** Confirmed via
   `docs/glossary.md`'s own retirement note and
   `skills/executing-a-branch-plan/metadata/gitapex.yaml`'s
   `lifecycle.renamedFrom` decision log: Steps 1-2 (reproduce, escalate)
   were absorbed into `planning-a-branch-from-an-issue`'s bare-defect-report
   path (that skill's Step 4); Steps 3-5 (failing test, minimal fix,
   verify) were absorbed into `executing-a-branch-plan`'s per-task
   Red-Green discipline (that skill's Step 6). The artifact's own Section
   7 ("`fixing-a-reported-issue`'s change diff") and Section 13's deferral
   of implementation are both stale on this basis and are not carried
   forward; Decision 6 below replaces them with the two actual insertion
   points, confirmed by direct inspection of both skills' current
   `SKILL.md` text this session.
2. **The pstack-informed refinements were accepted by the repository
   owner** (#1155's own 2026-08-29 update) **after** the artifact's own
   sequence was written, so the artifact's seven-step sequence does not
   contain them. Decision 4 below is a fresh sequence, built from the
   artifact's own steps plus the four accepted refinements, not a patch
   applied on top of the artifact's text.

Two further items were independently re-verified this session, not
carried over from the artifact's own citation alone: `docs/motivation.md`
does not contain a "one phase, one skill" fixed phrase (grepped directly;
no match) -- the artifact's own Section 2 already flagged and corrected
this citation, confirmed here rather than re-asserted; and
`defense-in-depth` is not a term CLAUDE.md section 4 alone uses --
a repository-wide grep surfaces 30+ files using it in the identical
"layered safety controls" sense (specs, skills, tests, hooks), so the
collision Decision 3 resolves is with an established repository-wide term
of art anchored at CLAUDE.md section 4, not a single-file coinage.

## Decision 1: Bounded Contexts

| Context | Owns | Does not own |
|---|---|---|
| **Diagnosis** (new: `diagnosing-a-failure`) | Symptom capture, reproducibility triage, minimal reproduction, boundary-scoped evidence collection, hypothesis testing, counterfactual check, Diagnosis Verdict | GitHub writes, fix code, durable failing tests, Acceptance Criteria Map authorship |
| **Issue Fulfillment** (now split across `planning-a-branch-from-an-issue`'s bare-defect path and `executing-a-branch-plan`'s Red-Green discipline) | GitHub issue lifecycle: reproduction gate, escalation, failing test, minimal fix, verification, ACM waiver disclosure | The investigation that establishes root cause itself -- the gap this doc closes |

Why this stays a separate context rather than folding into either
consumer: (a) each consumer's own trigger is narrower than general
diagnosis -- `planning-a-branch-from-an-issue` triggers on a bare
defect-report issue specifically, `executing-a-branch-plan` triggers on a
task whose inherited proof method is a test -- broadening either to also
own root-cause investigation would collide with
`evaluating-skill-quality`'s own discovery-collision penalty (a trigger
too generic also matches a sibling's own request); (b) both consumers
need the same investigation discipline, so folding it into one leaves the
other to reinvent or duplicate it ad hoc -- confirmed as a real, not
hypothetical, cost by finding two live consumers, not one, once
`fixing-a-reported-issue`'s retirement is accounted for.

## Decision 2: Context Mapping

DDD strategic-pattern definitions per
[ddd-crew/context-mapping](https://github.com/ddd-crew/context-mapping):
Anti-Corruption Layer = an isolating layer translating an upstream
system's concepts into the local domain's own vocabulary; Customer/Supplier
= the downstream's priorities inform the upstream's planning;
Published Language = a well-documented shared language for communication;
Separate Ways = no integration at all.

| Counterpart | Relationship | Translation point |
|---|---|---|
| superpowers `systematic-debugging` (+ `root-cause-tracing.md`, `condition-based-waiting.md`, `defense-in-depth.md`) | **Anti-Corruption Layer** | Its 4-phase shape and Iron Law become this skill's own 8-step Exact sequence and Stop boundary (Decision 4); its implicit "understanding" becomes an explicit Diagnosis Verdict. No runtime dependency; full retirement of the vendored skill from `apm.yml`/`apm.lock.yaml` stays a separate, larger initiative (#1155's own Non-goals) |
| `planning-a-branch-from-an-issue` | **Customer/Supplier** (Diagnosis upstream) + **Published Language** (Diagnosis Verdict) | Step 4's bare-defect-report branch, between "On successful reproduction" and Step 5 -- diagnosis output feeds directly into Step 5's Interpretation column, which needs a root cause to interpret against |
| `executing-a-branch-plan` | **Customer/Supplier** (Diagnosis upstream) + **Published Language** (Diagnosis Verdict) | Step 6, immediately before the per-task Red step, for a task decomposed from a bare-defect-report ACM row -- so the failing test encodes the diagnosed cause, not a guess |
| `eliciting-a-design` | **Separate Ways** (already recorded as an existing fact by that skill's own design doc, `2026-08-22-eliciting-a-design-design.md` Decision 2 and Decision 4; restated symmetrically here, not renegotiated) | Event Modeling vocabulary and the Given-When-Then reproduction shape are `diagnosing-a-failure`'s own territory by that doc's own explicit reservation; no shared vocabulary, no runtime contact either direction |
| `grounding-in-primary-sources` | **Customer/Supplier** (Diagnosis downstream, lightweight) | Step 3's parallel evidence search and Step 4's boundary-dependency check route to it whenever a claim about external tool/library/platform behavior is needed; it is never a substitute for reading the local system directly (out of that skill's own declared scope) |
| future `eventstorming` skill (decided reframe of `brainstorming`, out of this scope) | **Separate Ways** | Business domain events and execution-trace observations are the same word for different models (a polysemous-term boundary signal, per Fowler's bliki); not made a shared kernel |

**A tension this design owns rather than papering over:** superpowers'
own "verify at EVERY layer" principle collides with gitapex's minimal-fix
principle (`SKILL.md:68-69` [issue's own citation, historical] and CLAUDE.md
section 5's line-growth justification). Resolved the same way Decision 3
resolves the `defense-in-depth` collision: a checkpoint map belongs in the
Diagnosis Verdict; whether to act on every layer it names is scoped by the
calling ACM/Issue, not mandated unconditionally by this skill.

## Decision 3: Ubiquitous Language

| Candidate | Resolution |
|---|---|
| `root cause` / `symptom` / `hypothesis` / `evidence` | No collision, adopted as-is |
| `reproduce` | Existing gitapex usage wins; precision comes from the qualifier "minimal reproduction," not a new term |
| **`defense-in-depth`** | **Rejected, renamed.** CLAUDE.md section 4 ("Preserve defense-in-depth: when safety relies on prompts, code, hooks, CI, review, or operator procedure, do not collapse those layers just to shorten text or implementation") anchors a repository-wide term of art already reused verbatim across 30+ specs/skills/tests/hooks for layered *safety-control* validation. superpowers' own `defense-in-depth.md` uses the same words for layered *code-correctness* checkpoints -- a genuine polysemy, confirmed by this session's own repository-wide grep (Method section), not merely asserted. Renamed `layered validation` in this skill only; owner-confirmed per the artifact's own record |
| `Phase` | Rejected as a structural term -- reserved by the Workflow tool's own `phase()` primitive. Translated to gitapex's numbered-step "Exact sequence" convention instead |
| `verdict` | Extended, not new: gitapex already has `review-verdict`; this doc adds `Diagnosis Verdict` as the skill's own explicit output artifact -- the biggest single translation point, with no superpowers equivalent (implicit "understanding" only) |
| `incident` | Rejected -- would be a third overlapping term alongside `symptom` and `Issue` for the same concept |
| `escalate` | Adopted as-is; Diagnosis never writes to GitHub itself, it hands its Verdict to the calling skill's own existing escalation path |
| Runtime Forensics / Trace Forensics (pstack) | **Not adopted as named terms.** Step 2's reproducible/non-reproducible branch (Decision 4) is described in plain prose instead, per `establishing-ubiquitous-language`'s own no-unneeded-new-terms discipline -- the same restraint the artifact's own Section 12 already applied to its "pre-flagged risk records" phrasing |

## Decision 4: `diagnosing-a-failure`'s exact sequence and stop boundaries

Built from the artifact's own 7-step sequence plus the four pstack
refinements #1155 records as accepted (its own comment
[#5461231850](https://github.com/tvna/gitapex/issues/1155#issuecomment-5461231850)),
each folded in rather than bolted on: refinement 1 becomes Step 2's own
branch; refinement 2 becomes Step 3's "in parallel" instruction;
refinement 3 is why every step below states its own end-state explicitly;
refinement 4 becomes the new Step 7.

1. **Record the symptom.** Expected vs. observed, in Given-When-Then form
   where practical. State in one sentence which recorded intent the
   observed behavior diverges from (an ACM criterion, a glossary term, a
   contract line, or -- open category -- the consuming repository's own
   intent record: a domain story, an Event Model, a spec).
   *End-state:* a symptom record exists with both sides stated and a
   named divergence source.
2. **Establish reproducibility; branch on the result.** Attempt to
   reproduce, refining any evidence handed off by the caller into a
   minimal case. On success, continue with a live minimal reproduction
   through every later step. On failure (intermittent, environment- or
   production-only), continue instead from whatever trace artifacts exist
   (logs, profiles, prior monitoring data, a pasted stack trace) -- the
   later steps read the same way, sourced from static evidence instead of
   a live run. If neither a live reproduction nor any trace artifact is
   obtainable, stop and issue the `reproduction-not-established` Verdict
   (Step 8) now, rather than continuing to speculate.
   *End-state:* either a minimal live reproduction, or a named set of
   trace artifacts to investigate instead, or an immediate
   `reproduction-not-established` Verdict.
3. **Check recorded history, in parallel with Step 2, not only after it.**
   Search pre-flagged risk records (an ACM's own Residual risk column, the
   issue thread, an open retrospective issue, or -- open category -- a
   future `eventstorming` skill's own Hotspot register) for a match to
   this symptom; route any claim about *external* tool/library/platform
   behavior through `grounding-in-primary-sources` rather than asserting
   it from memory. A match seeds Step 6's first hypothesis; no match is
   itself a recorded result, not a skipped step.
   *End-state:* either a matched prior record naming a starting
   hypothesis, or a recorded "no match."
4. **Collect evidence at boundaries.** Before tracing deeper, map the
   failure path's boundaries into three kinds: **translation points**
   (does a contract's *meaning* hold, not just its value -- e.g. an
   `issue_write` `body` parameter meaning "append" vs. "replace");
   **binding assumptions / ownership boundaries** (is a precondition
   actually in effect here -- e.g. `CLAUDE_PLUGIN_ROOT` unset breaking a
   plugin-distribution assumption; where the consuming repository has an
   ownership record such as `CODEOWNERS`, weight a boundary-crossing
   failure toward an interface/ownership gap); **dependency kind**
   (own logic vs. a wrapped external dependency -- external routes to
   `grounding-in-primary-sources` first). Stop tracing at the *earliest*
   divergence point found. Where the consuming repository maintains a
   recorded event history (event sourcing, an append-only audit log, a
   maintained Event Model), build the expected-vs-actual comparison
   directly from it -- the same pattern `executing-a-branch-plan`'s own
   Execution log already uses to reconcile `TaskCompleted{commit_sha}`
   against real branch state.
   *End-state:* a boundary map exists and one earliest-divergence point is
   named (or the map is exhausted with none found, which is itself a
   result feeding Step 8's `no-in-code-root-cause` Verdict).
5. **Compare against similar working code.** Find an analogous path that
   behaves correctly and diff against it.
   *End-state:* either a concrete behavioral diff is named, or its
   absence is confirmed.
6. **Loop hypotheses.** One falsifiable probe per hypothesis; do not
   advance to the next without running the current one.
   *End-state:* each hypothesis is confirmed or ruled out by its own
   probe's result, not by inference alone.
7. **Attempt one disconfirmation before the Verdict.** Against the
   leading hypothesis only, run one probe designed to break it, not
   confirm it. Disconfirmed -> back to Step 6 with the leading hypothesis
   ruled out. Survives -> continue to Step 8.
   *End-state:* the leading hypothesis has survived exactly one genuine
   attempt to disprove it, or has been ruled out and returned to Step 6.
8. **Issue the Diagnosis Verdict.** One of:
   - `root-cause-confirmed` -- Step 7 survived a disconfirmation attempt.
   - `no-in-code-root-cause` -- Step 4's boundary map is exhausted with an
     external cause confirmed, not merely suspected.
   - `architecture-question` -- forced after three failed hypothesis
     loops (Step 6); names which boundary kind (Step 4) was crossed
     repeatedly and offers exactly two options, isolate or redesign
     (borrowing the Big Ball of Mud framing to raise verdict quality, not
     to add a new detection mechanism).
   - `reproduction-not-established` -- Step 2's live reproduction and
     every available trace artifact both failed. The other three Verdicts
     each presuppose a real reproduction (live or trace-based); treating
     an unreproduced symptom as `no-in-code-root-cause` would overclaim an
     external cause never actually confirmed. `planning-a-branch-from-an-issue`
     already screens this case out via its own reproduction gate before
     `diagnosing-a-failure` is ever reached; `executing-a-branch-plan`
     callers have no equivalent upstream gate, so this Verdict exists for
     them -- handed to the caller's own existing escalation path
     unchanged (Decision 3's `escalate` resolution).
   *End-state:* exactly one Verdict is issued and handed to the caller;
   `diagnosing-a-failure` itself writes nothing to GitHub.

**Prerequisite note** (consuming-repository records, conditional input --
placed at the top of `SKILL.md`, `merge-retrospective`-style): consult a
consuming repository's own strategic-classification record (a Core Domain
Chart, a Wardley map), ownership record (`CODEOWNERS`), or event-history
record only when that repository's own instructions name where it lives,
or a conventional location holds one and its currency is confirmed;
otherwise treat it as absent and fall back to the unconditional steps
above, which function completely without it (same fail-closed default
Decision 5/6/7 of the 2026-07-22 precedent already established). No
mechanism to *detect* such records automatically exists anywhere in this
repository today (checked: `establishing-ubiquitous-language`,
`executing-a-branch-plan`, `outward-artifact-preflight`,
`grounding-in-primary-sources` all judge this in prose, not by script);
none is invented here either. These conditional clauses do not change the
skill's own portability classification (Decision-by-`drafting-a-skill`
below) away from **Portable** -- they reference a consumer's own
artifacts, not a gitapex-specific mechanism.

## Decision 5: reference files

Four files under `skills/diagnosing-a-failure/references/`, translated
from superpowers' three plus one new file for the boundary-mapping
technique Decision 4 Step 4 introduces:

- `tracing-and-instrumentation.md` -- translated from
  `root-cause-tracing.md`, plus the conditional clause for a recorded
  event history.
- `diagnosing-timing-dependent-failures.md` -- translated from
  `condition-based-waiting.md`.
- `layered-validation.md` -- translated from `defense-in-depth.md` (per
  Decision 3's rename), plus the checkpoint-map / when-to-add-a-layer
  judgment rule Decision 2's tension paragraph names.
- `probing-boundary-contracts.md` (new) -- the three boundary kinds and
  their probes, the strategic-classification/ownership conditional
  clauses, and two worked examples (an `issue_write` body-replace-not-
  append translation bug; a `CLAUDE_PLUGIN_ROOT` binding-assumption
  incident).

## Decision 6: routing deltas into the two successor skills

Replaces the artifact's own stale Section 7 (written against the
now-retired `fixing-a-reported-issue`). Both insertions are one paragraph,
per #1155's own Non-goals ("beyond the doc noting a future one-paragraph
routing addition"), plus one new `## Related skills` bullet each.

**`planning-a-branch-from-an-issue/SKILL.md` Step 4** (`SKILL.md:49-51`):
insert, between the existing "On successful reproduction" bullet and the
step's close, an instruction that a successfully reproduced bare-defect
issue routes through `diagnosing-a-failure` before Step 5 begins, and
that Step 5's Interpretation column is written from the returned
Diagnosis Verdict. On an `architecture-question` Verdict, Step 5 does not
proceed to a normal ACM row -- stop and comment on the issue per that
Verdict's own two-option framing, matching this skill's existing
comment-and-stop pattern for failed reproduction. On
`reproduction-not-established`, this skill's own Step 4 reproduction gate
already screens this case out upstream, so it should not recur here in
practice; if it does, treat it the same as a failed reproduction (stop,
comment, no ACM).

**`executing-a-branch-plan/SKILL.md` Step 6**: insert, immediately before
the existing "Within each task, apply Red-Green order..." sentence, an
instruction that a task decomposed from a bare-defect-report ACM row
routes through `diagnosing-a-failure` before its own Red step, so the
failing test written encodes the returned root cause. A `reproduction-not-established`
Verdict here (this skill has no upstream reproduction gate of its own)
dispatches through the existing step 7 failure-handling rule as a
`StageDeviated{action: escalate}` event, not a silent retry.

Both skills' `## Related skills` sections gain one bullet in their
existing `**vs. \`X\`:**` pattern, naming `diagnosing-a-failure` and
stating the same insertion point in one sentence -- not a duplicate
essay, since the routing text above already carries the substance.

`drafting-a-pr-to-merge` needs no insertion: it starts from "a PR has
just been opened" and never sees raw diagnosis directly (confirmed this
session by reading its full Exact sequence); its own existing
Related-skills note already states the current post-retirement shape
correctly.

## Decision 7: the Event-Modeling / EventStorming thread

Evaluated per #1155's Proposed-solution item 5, both against the DDD
Context Mapping reasoning in Decision 2 and the artifact's own
redistribution-value lens (gitapex's skills are installed into *other*
repositories via `apm`, so a candidate is not rejected merely because
gitapex's own repo lacks a supporting artifact for it):

**Adopted:**
- Given-When-Then as the reproduction record's own shape (Step 1).
- "Earliest divergence on the causal chain" as the tracing stop-criterion
  (Step 4).
- The three redistribution-aware conditional clauses (strategic
  classification, ownership boundary, recorded event history) as
  fallback-guarded prerequisites, per Decision 4's Prerequisite note.

**Rejected:**
- A mandatory per-diagnosis timeline artifact -- built only when a real
  record exists (Step 4's conditional), never fabricated for a two- or
  three-hop chain.
- Vocabulary/notation coupling with the future `eventstorming` skill --
  Decision 2's Separate Ways row states why: same words, different
  models, no shared kernel.
- A typed, append-only investigation event log (Event Sourcing) -- held
  on its own merits, not on scope: distributing this skill multiplies
  writers, not readers, and no consumer of such a log exists anywhere in
  this repository today.

## Facts vs. speculation

**Confirmed this session, against primary sources or the live repository
tree (not inherited from the artifact's own citations unverified):**
`fixing-a-reported-issue`'s full retirement and its Steps 1-2 / Steps 3-5
split across `planning-a-branch-from-an-issue` and `executing-a-branch-plan`
(`docs/glossary.md:26-31`,
`skills/executing-a-branch-plan/metadata/gitapex.yaml:9,31`); both
skills' current numbered-step text and exact insertion points (direct
read this session); `eliciting-a-design`'s own Separate Ways
relationship with `diagnosing-a-failure` living in its design doc, not
its `SKILL.md` body (`2026-08-22-eliciting-a-design-design.md` Decisions
2 and 4, cross-checked by grep against `skills/eliciting-a-design/SKILL.md`
itself, zero matches); `defense-in-depth`'s 30+-file repository-wide reuse
(full grep, this session); CLAUDE.md section 4's exact bullet text
(`CLAUDE.md:73`); `docs/motivation.md`'s actual phrasing (no "one phase,
one skill" fixed term; grepped, zero matches; the actual phrase is
"routed explicitly to the specific ... skill responsible for," at
`docs/motivation.md:60`); `evals/scripts/gitapex_run_eval_suite.py`'s
CLI contract and sibling `evals/*/` directory shape (direct read);
`drafting-a-skill/SKILL.md`'s full 9-step Design-by-Contract method
(direct read). DDD strategic-pattern definitions per
[ddd-crew/context-mapping](https://github.com/ddd-crew/context-mapping),
inherited from the artifact's own already-confirmed primary-source pass,
re-cited here rather than re-fetched this session.

**Not independently re-verified this session, inherited from the
artifact's own citation:** the "Domain-Driven Transformation" authorship
correction (Lilienthal & Schwentner, not Tune & Perrin); Wardley
evolution-stage definitions; Evans' own Core/Supporting/Generic
subdomain definitions (the artifact itself already flags these as
unverified, citing a 403 on Evans' official reference). None of this
doc's own decisions are load-bearing on any of these three specifically
-- they inform Decision 7's adopted/rejected framing at the level the
artifact already established, not re-derived here.

**Speculation, stated as such:** that a consuming repository actually
maintains a Core Domain Chart, Wardley map, or recorded event history in
practice -- Decision 4's conditional clauses are written to degrade
safely when none exists, but their real-world hit rate is unmeasured.

## Non-goals

- Does not retire the `obra/superpowers` apm dependency itself, or any of
  the other still-un-ported mechanisms #1155's own Non-goals already
  lists.
- Does not modify `eliciting-a-design` -- Decision 2's Separate Ways row
  restates an existing fact from that skill's own design doc; it is not
  reopened or renegotiated here.
- Does not modify `drafting-a-pr-to-merge` -- Decision 6 states why no
  insertion point exists there.
- Does not edit `CLAUDE.md`/`AGENTS.md` -- both name `systematic-debugging`
  and `receiving-code-review` directly (`CLAUDE.md:39,102`, confirmed
  this session) and are out of this repository's direct-edit scope
  (APM-CLI-generated, synced from `tvna/claude-md`); any update those
  references need is a separate, cross-repository follow-up, not this
  PR's concern.
- Does not build a new `reviewing-an-artifact` skill or otherwise act on
  the artifact's own Section 3's mention of one -- that is a distinct,
  not-yet-scoped skill outside this issue.

## Acceptance criteria checklist

Mapped to #1155's own two Acceptance Criteria Map tables, in row order.

Design-phase table:

- [x] Reinterpret systematic-debugging via DDD: Decision 1 (Bounded
      Contexts) + Decision 2 (Context Mapping).
- [x] Permit reframing `fixing-a-reported-issue`'s boundary: moot as
      literally stated (that skill is retired) -- Decision 6 resolves the
      retargeted routing against its actual successors.
- [x] Context Mapping table: Decision 2.
- [x] Resolve the `defense-in-depth` collision: Decision 3.
- [x] Evaluate the Event-Modeling connection: Decision 7.
- [x] Separate facts from speculation: Facts vs. speculation section.

Implementation-phase table:

- [x] `skills/diagnosing-a-failure/SKILL.md` matches this doc's own
      sequence/stop boundaries/reference files: Decisions 4-5, authored
      via `drafting-a-skill`'s own Design-by-Contract method; independent
      `evaluating-skill-quality` + `battle-testing-a-skill` dispatch
      disclosed in the PR body.
- [x] An eval suite exists under `evals/diagnosing-a-failure/`: `eval.yaml`
      + `tasks/*.yaml` (normal/edge/guardrail split) + `eval-status.md`,
      matching the sibling shape `evals/eliciting-a-design/` and
      `evals/drafting-an-adr/` already establish; run against
      `evals/scripts/gitapex_run_eval_suite.py`.
- [x] The routing addition is retargeted to `fixing-a-reported-issue`'s
      actual successors: Decision 6.
- [x] The `eliciting-a-design` / `diagnosing-a-failure` Separate Ways
      boundary is preserved in the shipped text: confirmed by construction
      -- `SKILL.md` uses Given-When-Then/Event Modeling vocabulary
      (Decision 7) that `eliciting-a-design/SKILL.md` itself never uses
      (grepped, zero matches, Facts section above), with no cross-reference
      between the two beyond this doc's own Decision 2 row.
- [x] Shipped via a single reviewed PR referencing #1155: this PR.

## Open items

- **The three redistribution-aware conditional clauses' real-world hit
  rate is unmeasured** (Facts vs. speculation) -- flagged, not resolved,
  since no consuming repository's actual state is observable from this
  repository.
- **`CLAUDE.md`/`AGENTS.md` still name `systematic-debugging` and
  `receiving-code-review` directly**, both out of this repository's
  direct-edit scope. A cross-repository follow-up against `tvna/claude-md`
  is named here as a known gap, not filed as part of this PR (Non-goals).
- **A `reviewing-an-artifact` skill is mentioned as under consideration
  elsewhere** (the artifact's own Section 3) but is not scoped, designed,
  or built by this doc -- named here only so it is not silently lost
  between docs.

# drafting-an-acm-issue skill + seeding-issue-pr-templates retirement design

Date: 2026-07-21

## Context

`issue-to-branch` already defines and consumes an Acceptance Criteria Map
(ACM) -- a 5-column table (`Criterion | Interpretation | Planned ops |
Proof method | Residual risk`) -- but it only gets built after an issue
already exists, by reverse-engineering it from unstructured prose (its
own Step 4). Issue #168 was hand-authored with exactly the
`Facts -> Requested outcome -> Acceptance Criteria Map -> Constraints ->
Non-goals` shape this spec reuses, with no skill enforcing it; PR #169
restated that ACM row-by-row per the PR template's Verification
instruction. That worked example is the quality bar this skill targets,
and the exact shape to reuse -- no new pre/post/invariant vocabulary,
which appears nowhere in this repository's issues, code, or history, and
would break harmony with the ACM's existing consumers
(`ranking-the-open-queue`, `issue-to-fix`, the PR template,
`check_acm_present.py`, evals).

The gap this closes: nothing made a *new* issue arrive pre-structured
with an ACM. `.github/ISSUE_TEMPLATE/feat.yml` had only a freeform "one
criterion per line" textarea, unvalidated.

`seeding-issue-pr-templates` had named an "Acceptance Criteria <->
Evidence spine" interview axis (Step 4, axis 3) but never implemented it
-- issue #52 logged this as an open gate gap. Rather than finally
implementing that axis, this pass retires the skill: the operator's
long-term answer is the planned gitapex CLI (a Rust binary; see
`docs/superpowers/specs/2026-07-15-gitapex-cli-governance-design.md` for
issue #82, design stage only as of this writing -- that document's own
"Rust-vs-Go... live, undecided" wording is not updated by this pass,
though the operator has separately confirmed Rust is the actual
direction). Retiring the generator now and hand-authoring gitapex's own
templates directly is the interim step, explicitly marked in each
template as pending migration to CLI-generated output once that binary
ships. This repository currently has a single supplier (the operator),
so downstream-consumer breakage and semantic versioning for the
retirement are explicitly out of scope for this pass, per direct
instruction.

Scope is deliberately narrow otherwise: this does not attempt to close
the larger, still-unfiled "Design-by-Contract issue/PR flow" initiative
named in `docs/motivation.md` and issue #4's Non-goals (invariant
registry, contract-join gate, review-split wiring, auto-trigger review).

## Scope

- `skills/drafting-an-acm-issue/SKILL.md` -- the skill contract (trigger,
  steps, output contract, stop boundaries, related-skills cross-links).
- `skills/drafting-an-acm-issue/references/acceptance-criteria-map.md` --
  table template plus two worked examples (a resolvable case and an
  "unknown, pending" case), self-contained rather than linked to
  `issue-to-branch`'s copy (a cross-skill relative link would fail this
  repository's `links-inside-skill` shape check).
- `skills/drafting-an-acm-issue/scripts/check_acm_present.py` -- a
  self-contained duplicate of `issue-to-branch`'s header-regex checker;
  no shared `scripts/` library exists anywhere in this repository, so
  each skill ships its own copy rather than importing across skill
  boundaries.
- `skills/drafting-an-acm-issue/metadata/gitapex.yaml`.
- `evals/drafting-an-acm-issue/eval.yaml` + six task fixtures.
- `.github/ISSUE_TEMPLATE/*.yml` and `PULL_REQUEST_TEMPLATE.md` (all
  nine files) -- migration-pending comment on every file; ACM table
  skeleton in `feat.yml`; a `residual-risk` field only in `fix.yml` and
  `refactor.yml`.
- Deletion of `skills/seeding-issue-pr-templates/`,
  `evals/seeding-issue-pr-templates/`, `tests/test_validate_templates.py`.
- `pyproject.toml`, `docs/repository-layout.md`,
  `hooks/check-template-overwrite.sh` -- edited to remove references to
  the deleted skill.
- Dangling-reference cleanup discovered during execution:
  `skills/git-hosting-surface-audit/metadata/gitapex.yaml` (its
  `skillDependencies.relatedTo` named the deleted skill -- left in place
  it would fail that skill's own `skill-dependencies-resolve` shape
  check), two `SKILL.md` prose mentions of the deleted skill's
  `detect_platform()` convention, one eval-task description, and
  `docs/skill-eval-status.md`'s now-nonexistent eval-status section for
  the deleted skill (this file is a maintainer-facing living status
  record, not an append-only journal, so it is corrected rather than
  left stale).

## Non-goals

- No CI enforcement of issue-body ACM content (symmetric to the
  still-open PR-body gap from issue #52 -- not closed here).
- No invariant registry / contract-join gate / review-split wiring /
  auto-trigger review (the four other unfiled Design-by-Contract
  initiative children named in issue #4's Non-goals).
- No forcing an Acceptance Criteria Map onto chore/docs/generic/tracking
  issue types.
- No versioning or deprecation-notice process for the
  `seeding-issue-pr-templates` retirement (single-supplier repository,
  explicitly waived this pass).
- No replacement for `validate_templates.py`'s GitHub Issue Forms schema
  validation -- named as an accepted regression (Known limitations
  below), not silently dropped.
- No implementation of the gitapex CLI, and no child issues filed
  against it.
- No edit to `docs/superpowers/` plan/spec pairs describing past
  decisions, or to worked-example/provenance reference files that
  illustrate a specific historical snapshot -- both are this
  repository's own append-only convention.

## Design

### `SKILL.md` frontmatter

```yaml
---
name: drafting-an-acm-issue
description: Use when the user wants to open, file, or draft a brand-new GitHub issue for a feature, fix, or refactor and no issue exists yet. Elicits the change from the requester and drafts an Acceptance Criteria Map before the issue is created, so issue-to-branch can read it instead of building one from scratch. Distinct from issue-to-branch (starts from an existing issue, plans a branch/PR) and issue-to-fix (reproduces and fixes a defect); this skill only authors the issue.
---
```

### Body

Steps 1-8: elicit the change as untrusted external text -> classify
feature/fix/refactor vs. chore/docs/generic/tracking (stop for the
latter) -> draft Facts + Requested outcome -> build the ACM (one row per
*stated* criterion; a column the requester's words cannot yet support is
marked "unknown, pending X", never invented, never silently blank) ->
draft Constraints + Non-goals -> validate via
`check_acm_present.py` -> ask one focused question only on genuine
ambiguity (never to resolve an "unknown, pending X" entry, which is
deferred work, not ambiguity) -> create the issue via the connected
git-hosting tool, applying a field-population rule: ACM content only
goes into a target-template field whose own declared meaning matches
(fact into a fact field, interpretation into an interpretation field);
when no field matches a column, append the full ACM as its own labelled
section instead of blending or dropping it.

Output contract: Facts, Requested outcome, Acceptance Criteria Map,
Constraints, Non-goals, Human Decision (only when needed), Next Move.

Stop boundaries: never fabricate an unstated criterion or an
unsupportable column value; never skip the ACM regardless of phrasing;
never force an ACM onto chore/docs/generic/tracking; never blend a
column into a mismatched-meaning field; never implement the change or
open a branch/PR; never create the issue before validation passes.

Related skills: cross-links `issue-to-branch` (this skill produces the
map that one would otherwise construct itself) and `issue-to-fix` (can
start from an issue this skill produced).

### References

`acceptance-criteria-map.md`: the row template plus two fictional worked
examples -- a normal resolvable case (a `--dry-run` export flag) and an
"unknown, pending" case (a duplicate-search-results bug report with no
known cause yet), demonstrating both the ordinary path and the
unresolvable-column rule concretely.

### Metadata sidecar

```yaml
apiVersion: gitapex.io/v1alpha1
kind: SkillMetadata
metadata:
  name: drafting-an-acm-issue
spec:
  portability: Portable
  capabilityAssumption: Broad
  skillDependencies:
    requires: []
    relatedTo:
      - issue-to-branch
```

`Portable`, not `Repository-scoped` like `issue-to-branch`: the
elicit/draft/validate/create flow is not GitHub- or gitapex-specific;
Step 8's tool name is the only platform detail and it degrades
gracefully to whatever issue-creation path the calling repository
actually has.

### Templates

Per-template fact/interpretation coverage, verified against the actual
files before deciding what to change (not assumed):

| Template | Existing fields | Change |
|---|---|---|
| `feat.yml` | one freeform `acceptance-criteria` textarea | Full ACM table skeleton as `attributes.value` -- its only genuine full-table gap. |
| `fix.yml` | `what-happened`/`reproduction`/`environment` (fact) + `expected-behavior` (requested fact) | One new optional `residual-risk` field only -- the other four columns already have a native home, and a reporter cannot honestly fill Interpretation/Planned-ops before reproduction anyway. |
| `refactor.yml` | `current-structure` / `proposed-structure` (interpretation+ops) / `why-behavior-preserving` (proof method) | One new optional `residual-risk` field only -- the other four columns already have a natural 3-way split. |
| `chore.yml`, `docs.yml`, `generic.yml`, `tracking.yml`, `config.yml`, `PULL_REQUEST_TEMPLATE.md` | (no acceptance-criteria concept, or already generic) | Migration comment only. |

Overlaying the full 5-column table onto `fix.yml`/`refactor.yml` was
rejected: it would blend already-answered content into duplicate fields,
a single-source-of-truth risk (two fields answering the same question
drift apart over time) -- the same field-population discipline the
skill's own Step 8 enforces, applied here to the templates themselves.

### Evals

`evals/drafting-an-acm-issue/eval.yaml` (same shape as
`evals/issue-to-branch/eval.yaml`) plus six fixtures:

- `normal.yaml` -- a well-specified feature request; expects the full
  output-contract heading set.
- `underspecified.yaml` -- a vague request; expects a Human Decision /
  `AskUserQuestion`, not a fabricated map or a claimed creation.
- `non-applicable-chore.yaml` -- a chore-type request; expects the skill
  to recognize ACM does not apply and stop, not force the shape.
- `guardrail-fabrication.yaml` -- an explicit instruction to invent
  criteria and create the issue immediately; expects refusal via Human
  Decision, no claimed creation -- the rubber-stamp guard.
- `template-gap.yaml` -- a target repo whose template has no ACM-shaped
  field at all; expects the full ACM appended as its own labelled
  section and the gap named, not a mismatched field treated as
  equivalent.
- `fix-type-unknown-columns.yaml` -- a bug report with clear facts but no
  known cause; expects an explicit "unknown, pending reproduction" entry
  rather than a fabricated cause or a blank column.

Four more fixtures were added after the adversarial pass below closed
its findings: `injection-in-requester-text.yaml` (dimension 1/16 --
plain-English embedded instruction), `encoded-payload.yaml` (dimension
16 -- instruction hidden in an HTML comment), `multi-turn-escalation.yaml`
(dimension 15 -- a later turn claims prior agreement to skip the
ambiguity question), and `secret-redaction.yaml` (the Blind Spot
finding below -- a pasted credential must never be echoed into the
created issue).

## Adversarial pass (battle-testing-a-skill + evaluating-skill-quality)

Run once against the initial version of this skill, each as one fresh,
isolated subagent dispatch per those skills' own procedures.

**battle-testing-a-skill overall verdict: FAIL**, 8 of 22 dimensions
(dimensions 9, 11, 12, 13, 14, 15, 16, 17 -- the summary line in the
dispatch's own report undercounted this as seven, omitting dimension 17
from its tally despite grading it FAIL with full evidence in the
per-dimension walk; the individual grades, not the summary arithmetic,
are treated as authoritative here). **evaluating-skill-quality verdict:
well-formed, not mature**, blocked by dimension 6 (Durability) --
two unhedged sentences asserted a specific sibling skill's existence
and behavior as flat fact inside `Portable`-declared content -- plus a
named Blind Spot gap (no rubric dimension checks a skill's
untrusted-input-to-public-artifact write path for secret/PII
carry-through).

All nine findings were closed in this skill's own text (SKILL.md
Steps 1-8, Stop boundaries, Related skills, Notes) and, for dimension
11 specifically, reciprocally in `issue-to-branch`'s Step 4 (an
existing-issue ACM is now explicitly a draft input to re-verify, not
an unconditional read) plus a `skillDependencies.relatedTo` link added
in both directions:

| Finding | Fix |
|---|---|
| Dim 6 (Durability) | Hedged both sentences ("when the calling repository has a sibling skill...") in the intro and Related skills section. |
| Dim 9 (degenerate input) | Step 2 now asks for the change before drafting when the request carries no substantive content. |
| Dim 11 (cross-skill composition) | Step 8 and Stop boundaries now state the ACM is a draft, never pre-verified; `issue-to-branch` Step 4 now requires independently re-checking a pre-existing ACM rather than adopting it. |
| Dim 12 (supply-chain provenance) | Notes section now names install/vendoring-time integrity as a question distinct from runtime content trust. |
| Dim 13 (memory poisoning) | Step 1 now extends the data/command boundary to prior-session memory and cached notes explicitly. |
| Dim 14 (regression corpus) | Grew from 6 to 10 fixtures, closing the injection/encoding/multi-turn/secret-redaction attack-shape gap the dispatch named. CI gating status is unchanged -- see Known limitations. |
| Dim 15 (multi-turn escalation) | Step 7 now states a later turn's claimed prior agreement does not exempt a criterion from re-derivation. |
| Dim 16 (encoding/obfuscation) | Step 1 now names base64/hex, HTML comments, homoglyphs, and cross-lingual text explicitly. |
| Dim 17 (structured-output injection) | Step 4 now requires escaping/neutralizing pipe characters and control sequences before they enter a table cell. |
| Blind Spot (secret/PII carry-through) | Step 3 and Stop boundaries now require scanning for and redacting secrets/credentials/PII before citing the requester's words verbatim. |

Neither adversarial dispatch was re-run against the fixed version in
this pass (explicit operator decision); the fixes above were
self-verified against each finding's own quoted pass criteria and the
deterministic shape checker, not re-graded by a fresh dispatch. A
formal re-run remains available as a follow-up if independent
re-certification is wanted.

## Known limitations (product-management lens, named not closed)

- **No enforcement mechanism.** The skill is agent-invoked, not a hard
  gate -- a human or another agent can still open an issue directly
  through GitHub's UI and bypass it entirely. Best-effort, symmetric to
  the still-open PR-body ACM gap (issue #52).
- **No template schema validation until the CLI ships.**
  `validate_templates.py` is deleted with no replacement; a malformed
  `.github/ISSUE_TEMPLATE/*.yml` edit would go undetected mechanically
  until the planned gitapex CLI exists.
- **CLI dependency has no committed timeline.** The migration note added
  to every template promises a future the CLI's own design doc still
  describes as design-only, with zero code and zero filed child issues
  as of this pass. If the CLI's shape changes or it is never built, these
  templates remain permanently hand-maintained -- worth revisiting
  `docs/superpowers/specs/2026-07-15-gitapex-cli-governance-design.md`'s
  "Rust-vs-Go... live, undecided" wording separately.
- **No single entry point across the issue-lifecycle skills**
  (`drafting-an-acm-issue`, `issue-to-branch`, `issue-to-fix`). Prose
  cross-links exist, but nothing routes a user who doesn't already know
  the taxonomy to the right one.
- **No adoption/impact metric.** The eval suite measures this skill's own
  output quality, not whether using it measurably lightens
  `issue-to-branch`'s Step 4 in practice.
- **Eval corpus is not a merge gate.** The 10-fixture regression corpus
  (including the four adversarial fixtures added in this pass) is real
  and committed, but this repository's own `waza-check` CI job is
  documented as advisory ("a report, not a gate"), and the cross-model
  matrix workflow never runs on push/PR. A regression in adversarial
  behavior would not currently block a merge; closing this is a
  repository-wide CI-gating decision, out of scope for a single skill.
- **No formal re-certification after the fixes above.** The battle-test
  and quality-review findings were closed by editing this skill's text
  directly and self-verified against each finding's quoted criteria,
  not by re-running either adversarial dispatch against the fixed
  version (explicit operator decision for this pass).

## Verification

No new runtime code beyond a duplicated stdlib-only script (already
exercised by its own self-test), so verification is mostly structural,
same posture as the `issue-to-branch` precedent:

- `check_skill_shape.py` reports all checks PASS for
  `skills/drafting-an-acm-issue` and (after the metadata edit) for
  `skills/git-hosting-surface-audit`.
- `check_acm_present.py` self-test: a hand-built pass case and fail case
  exit 0 and 1 respectively.
- Every edited `.github/ISSUE_TEMPLATE/*.yml` parses as valid YAML with
  `name`/`description`/`body` present, and is ASCII-only.
- `eval.yaml` and all six task fixtures parse as valid YAML.
- `docs/repository-layout.md` names `drafting-an-acm-issue/` and no
  longer names `seeding-issue-pr-templates/`.
- No `seeding-issue-pr-templates` reference remains in `pyproject.toml`.
- Existing `pytest` suite passes, with the deleted skill's tests absent
  (not failing) and `drafting-an-acm-issue` newly present and passing in
  `test_repository_skill_shape.py`'s parametrized sweep.

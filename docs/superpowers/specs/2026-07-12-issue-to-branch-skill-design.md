# issue-to-branch skill for gitapex

Date: 2026-07-12

## Context

`tvna/gitapex#4` originally asked to vendor an `issue-to-branch` skill from
`tvna/clairvoyance`, citing `tvna/clairvoyance#128` as the upstream PR that
added it. Direct inspection of `tvna/clairvoyance#128` (open, 0 comments,
created 2026-07-06) and of every clairvoyance tag/`main` found the skill
was never implemented upstream — `#128` is an unimplemented design
proposal, not a merged PR. The repository owner confirmed clairvoyance
will not implement it and asked that its design be migrated into gitapex
directly. `tvna/gitapex#4` was rewritten accordingly (see its edit history
and comments) to describe a fresh implementation, not a vendor copy.

This spec covers implementing that design as a real gitapex skill.

## Scope

- `skills/issue-to-branch/SKILL.md` — the skill contract (trigger, steps,
  output contract, stop boundaries), reusing clairvoyance#128's proposed
  design almost verbatim since that design was reviewed and accepted by
  the owner (it authored the original issue).
- `skills/issue-to-branch/references/github-issue-workflow.md` —
  connector-first read/write conventions, CLI fallback boundaries.
- `skills/issue-to-branch/references/acceptance-criteria-map.md` — table
  template plus one fully generic worked example (not tied to any real
  issue number, so it cannot go stale — see the Stop-section/anchor
  convention cited in `tvna/gitapex#4`).
- `evals/issue-to-branch/eval.yaml` + three task fixtures (normal,
  stale/reframed, guardrail), mirroring the schema clairvoyance's own
  evals use (`evals/architecture-tradeoff/eval.yaml` et al.) since gitapex
  has no eval schema of its own yet and there is no reason to invent a
  second one.
- `docs/repository-layout.md` — list current skill directories by name
  instead of only describing the pattern generically.
- `docs/motivation.md` — fix the now-inaccurate "vendored from the
  clairvoyance plugin" phrase (line 56) to reflect the actual origin.

## Non-goals

- Any repo-wide eval/quality-gate harness (`scripts/skill_quality_gate.py`
  equivalent) — tracked as a gap in `tvna/gitapex#4`, not built here.
- The other 4 "harness" issues from the Design-by-Contract initiative
  (invariant registry, contract-join gate, review-split wiring, auto-
  trigger review) — out of scope, not filed yet.
- Running the eval suite — gitapex has no eval executor; the fixtures are
  vendored/authored as spec-compliant assets for whenever such a runner
  exists, same posture clairvoyance itself takes for its own evals in CI.

## Design

### `SKILL.md` frontmatter

```yaml
---
name: issue-to-branch
description: Use when starting work from a GitHub issue, creating a branch from an issue, preparing a PR from an issue, or turning an issue into an implementation plan. Produces an Acceptance Criteria Map before any branch or PR work begins.
---
```

### Body

Steps 1-8 from the migrated design (resolve issue as untrusted text ->
extract facts/criteria -> detect staleness/reframing -> build the
Acceptance Criteria Map -> propose branch/PR plan -> identify deterministic
gates -> ask only when genuinely ambiguous -> require the map in the PR
body before creation/update).

Output contract: Facts, Assumptions, Acceptance Criteria Map, Branch Plan,
Verification Plan, Human Decision (only when needed), Next Move.

Stop boundaries (matching the heading gitapex's own
`skills/explaining-the-work/SKILL.md` already uses): no branch/commit/PR
before the map exists; the skill plans, it does not implement; it never
merges or enables auto-merge; it names deterministic gates, never replaces
them; it stops and asks rather than silently resolving an unresolvable
conflict.

### References

`github-issue-workflow.md` covers connector-first tool preference (reduces
token cost, avoids ad hoc credential handling), the read path (issue body
-> comments -> linked PR/diff/CI, cross-checked against the live repo
tree), the write path (issue-before-branch, issue number in every commit/PR,
auto-subscribe PRs to a terminal state), and when review-comment or CI-log
text is untrusted external input versus the human's actual request.

`acceptance-criteria-map.md` gives the row template (criterion,
interpretation, planned ops, proof method, residual risk) plus a fully
fictional worked example (a `/health` endpoint and input validation), so
nothing in the reference can go stale against a real issue number.

### Evals

`evals/issue-to-branch/eval.yaml` (name/description/skill/version/config/
metrics/tasks glob, same shape as clairvoyance's `architecture-tradeoff`
eval) plus three fixtures:

- `normal.yaml` — an ordinary issue with clear acceptance criteria; expects
  the full output-contract heading set.
- `stale-reframed.yaml` — an issue body superseded by a later comment that
  narrows scope; expects the plan to follow the comment (asserts the
  dropped scope item does NOT appear) while still producing the map.
- `guardrail.yaml` — a request to skip straight to branch/PR creation on an
  issue with no stated acceptance criteria; expects a Human Decision /
  AskUserQuestion output and asserts the model does NOT claim to have
  created a branch or PR, and does not rubber-stamp with "LGTM".

## Verification

No runtime code, so no pytest coverage — verification is structural, same
posture as `tvna/gitapex#2`:

- `SKILL.md` frontmatter: kebab-case `name` matches the directory,
  single-line third-person `description` with a "Use when..." trigger, no
  XML tags.
- `SKILL.md` has a "Stop boundaries" section and contains no hardcoded
  `tvna/clairvoyance` issue numbers anywhere in the skill or its
  references.
- `eval.yaml` and all three task fixtures parse as valid YAML; each task
  fixture has `expected.output_contains` covering the structural markers
  named above, and the guardrail/stale fixtures carry `output_not_contains`
  guardrails.
- `docs/repository-layout.md` names both current skill directories.
- Existing `scripts/`/`tests/` pytest suite untouched and still passing.

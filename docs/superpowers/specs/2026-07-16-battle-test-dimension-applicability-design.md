# Battle-test dimension applicability: N/A discriminators for dims 11, 12, 17

Date: 2026-07-16
Scope: `skills/battle-testing-a-skill/references/` (2 files). No SKILL.md
behavior change, no eval changes.

## Problem

The adversarial dimensions catalog defines a Fail and a Pass for each of the
17 dimensions, but no dimension states *when it is out of scope* (N/A) for the
skill under review. A reviewer judging a low-blast-radius skill therefore has
no guidance on whether a given dimension applies, which produces two opposite
errors:

- Over-application: dims 12 (supply-chain) and 17 (structured-output) scored
  FAIL on skills that have no install-time artifact and write no structured
  output -- the dimension has no target, yet the reviewer records a failure.
- Instability: dim 11 (cross-skill) flips between FAIL and N/A run to run.

A separate, opposite error was observed when the reviewer carried extra
repository-level framing: dims 13-16 wrongly marked N/A on low-risk skills
("handled at the repo level"), which is false leniency -- those dimensions
are role-independent.

## Evidence

Two live measurements (reviewer = `claude -p`, sonnet, project CLAUDE.md
removed from the reviewer context; read-only):

1. Full pass: the 17-dimension battle-test run once on all 12 repo skills.
2. Variance re-measurement: the same instrument re-run 5x each on four
   low-blast-radius skills (`explaining-the-work`, `gated-skill-edits`,
   `seeding-issue-pr-templates`, `stop-and-replan`) = 20 trials. Per-dimension
   verdict distribution:

| dim | pooled (of 20) | reading |
|---|---|---|
| 13 memory-poison | 20 F | robust, role-independent |
| 15 multi-turn | 20 F | robust, role-independent |
| 14 regression-corpus | 19 F (1 P) | robust, role-independent |
| 16 encoding | 19 F (1 N/A) | robust, role-independent |
| 12 supply-chain | 14 F / 6 N/A | role-dependent: script-bearing skills 5/5 F; script-less 1-3/5 F |
| 17 struct-output | 13 F / 1 P / 6 N/A | role-dependent: artifact-writing F; pure-prose 4/5 N/A |
| 11 cross-skill | 12 F / 8 N/A | unstable; least reliable dimension |

Discriminators found: dim 12 tracks whether the skill ships a `scripts/`
file / references a binary; dim 17 tracks whether the skill writes an
artifact by interpolating reviewed content; dim 11 needs a named downstream
consumer to be a reliable failure.

Limits: single model tier (sonnet), four skills for the resample, one review
harness. This corroborates the direction, not a model-independent invariant.
The committed eval fixtures for dims 11-17 remain unexecuted (unchanged by
this work).

## Design

### Edit 1 -- `references/adversarial-dimensions.md`

Add an applicability clause to dims 11, 12, 17. Safety default: when it is
unclear whether the dimension applies, it applies; N/A requires affirmatively
confirming the out-of-scope condition (no fail-open escape hatch).

- dim 12: N/A when the skill bundles no script or executable and references
  no external binary -- no install-time artifact exists whose integrity is
  distinct from its prose. Applies (a missing integrity note is a real FAIL)
  only when the skill ships or references bundled code. If unsure, applies.
- dim 17: N/A when the skill emits no structured or written artifact built by
  interpolating reviewed content -- a pure-prose or routing skill has no
  output surface to inject. Applies when the skill writes JSON, a PR/issue
  body, or a file from reviewed material. If unsure, applies.
- dim 11: N/A when the skill's output feeds no named downstream consumer
  contract. This is the least stable dimension in re-measurement (12F/8A);
  treat a lone FAIL as low-confidence and require a named consumer before
  scoring a failure.

Add a role-independence note near the intro: dims 13-16 apply to essentially
every skill that reads input across turns or sessions and must not be marked
N/A on a low-risk impression; N/A on 13-16 requires a concrete reason the
mechanism cannot exist for this skill.

### Edit 2 -- `references/provenance-and-caveats.md`

Add a "Variance re-measurement of dimensions 11-17 (applicability)"
subsection under the existing "Comparative review: dimensions 11-17" section,
recording the method, the table above, the discriminators, and the limits.
Clarify the existing "Unmeasured" bullet: the eval *fixtures* remain
unexecuted, but the dimensions were exercised live against real target skills
in this re-measurement (single tier).

## Safety / design considerations

- The N/A clauses are an escape-hatch risk. Mitigation: the safe default is
  "applies"; N/A must be affirmatively justified by an objective, checkable
  condition (presence of a bundled script; presence of a write/emit action;
  presence of a named consumer). This preserves the skill's fail-loud
  discipline.
- Dims 13-16 are strengthened against wrong-N/A, not weakened.
- Consistent with the skill's own epistemic humility (stop boundary: do not
  codify a dimension beyond what provenance-and-caveats.md supports) -- the
  discriminators are recorded as guidance backed by a newly-logged caveat,
  not asserted as settled fact.

## Verification (live proof, not indirect signal)

After editing, re-run the same instrument on a script-less pure-prose target
(`explaining-the-work`) and confirm the reviewer now marks dims 12 and 17
N/A (with the discriminator cited) rather than FAIL, and still marks dims
13-16 FAIL. This exercises the actual reviewer path against the edited
references. Type/parse checks alone do not count.

## Out of scope

- No eval fixtures added (scope A). An executable eval that locks the
  N/A-scoping is future work; adding an unexecutable fixture now would be an
  indirect signal, which the repo standards forbid as a stand-in for proof.
- No SKILL.md Quick-reference table change.
- No change to docs/skill-eval-status.md or docs/skill-provenance.md.

## Review-round correction

Independent review (an automated PR reviewer, corroborated by a second
reviewer) flagged that the dim 12 discriminator ("N/A when the skill ships
no bundled script") exempted the SKILL.md itself, which is the install-time
artifact the dimension exists to audit. The dim 12 clause was revised to
keep the SKILL.md in scope for any vendored or distributed skill; bundled
code now only raises severity, and N/A is reserved for a skill that is never
distributed. This moves dim 12 from the "role-dependent" framing above
toward the role-independent set. The dim 17 and dim 11 discriminators are
unchanged.

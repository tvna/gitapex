# Glossary

This repository's ubiquitous-language source of truth, per
`skills/establishing-ubiquitous-language/SKILL.md` step 4. New entries and
conflict resolutions go through that skill's Elicit/Detect/Resolve/Maintain
procedure, not ad hoc.

## `Issue`

A GitHub Issue in this repository: the single term used for any tracked
unit of work regardless of kind (feature request, chore, defect report,
tracking umbrella, etc.), as already used throughout `planning-a-branch-from-an-issue`,
`merge-retrospective`, and `docs/motivation.md`.

Superseded terms: `Bug report` -- surfaced as a candidate synonym while
naming the autonomous-bug-repair skill proposed in the Fable-assisted
skill-gap analysis (2026-07-15). Resolved by the repository owner,
directly, per the Resolve step: "issue" wins, "bug report" retires as a
synonym for the same concept rather than being kept as a deliberately
narrower one. The skill in question is named `fixing-a-reported-issue`, not
`bug-report-to-fix`, on this basis (see
`docs/superpowers/specs/2026-07-15-issue-to-fix-design.md`, unrenamed --
that path is a dated design-record filename, out of scope for the
`issue-to-fix` -> `fixing-a-reported-issue` rename per #281).

## `Task`

One file-scoped, independently-committable unit of work, produced by
decomposing one or more Acceptance Criteria Map rows. Distinct from
`criterion` (the verification unit an Acceptance Criteria Map row
states): a task is a unit of *work*, a criterion is a unit of *proof* --
the two do not collapse into each other, and the mapping between them is
many-to-many, not one-to-one.

Adopted as gitapex's own term via
`skills/establishing-ubiquitous-language/SKILL.md`'s Elicit/Detect/Resolve
procedure, run against vocabulary borrowed from GSD, Superpowers, and
GitHub Spec Kit while designing `executing-a-branch-plan`
(`docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md`,
Decision 10). No existing gitapex synonym covered this specific concept,
so this is a fresh-term-minting case, not a conflict resolution.

## `Branch Plan`

The output of `planning-a-branch-from-an-issue/SKILL.md`: a branch name, commit scope,
and PR title/body outline derived from an issue's Acceptance Criteria
Map. This is the sole term for that concept in gitapex's own vocabulary.

Superseded terms: bare `plan` -- surfaced as a candidate synonym from
GSD's and GitHub Spec Kit's own vocabulary while designing
`executing-a-branch-plan`
(`docs/superpowers/specs/2026-07-22-plan-execution-handoff-design.md`,
Decision 10). Resolved per the Resolve step: `planning-a-branch-from-an-issue`'s own
Output contract already named this concept "Branch Plan" first, so that
term wins; bare "plan" retires as an ambiguous synonym in any new skill
text rather than being introduced as a second name for the same thing.

## `Evaluating-*` vs. `Auditing-*` vs. `Vetting-*` (skill-naming verb families)

Three gerund-verb families this repository's skill names split into, each
with a distinct meaning -- not interchangeable, despite all three English
words casually meaning "review." They split along two independent axes:
what the skill's *target* is (a repository-internal artifact vs. an
external-facing surface or this repository's own scope), and what its
*verdict style* is (a fixed-dimension rubric vs. a checklist/axis map vs.
concrete per-item pass/fail tests). The two axes do not always co-vary --
`Vetting-*` exists because one real skill combined an `Evaluating-*`-style
target with neither other family's verdict style.

- **`Evaluating-*`**: grades a repository-internal artifact (a `SKILL.md`,
  a deterministic gate) against a fixed-dimension quality rubric, producing
  a maturity verdict (`WELL-FORMED-AND-MATURE`, `PASS`/`FAIL` per
  dimension, etc.). Examples: `evaluating-skill-quality`,
  `evaluating-deterministic-gate-quality`.
- **`Auditing-*`**: classifies an external-facing configuration surface, or
  this repository's own scope, against a checklist or axis map, producing a
  coverage/classification report (`Covered`/`Partial`/`Gap`,
  `Documented`/`Unknown`/`Conflict`, etc.). Examples:
  `auditing-git-hosting-surface`, `auditing-agent-product-scope`.
- **`Vetting-*`**: examines an individual artifact's own design against
  concrete, per-item pass/fail tests specific to that check -- neither a
  fixed-dimension maturity rubric nor a checklist/axis map of an
  external-facing surface. Verdict vocabulary is bespoke per skill (e.g.
  `exposure-minimal`/`exposure-excess`), always reported per item, never
  as one aggregate verdict.

Surfaced as a Detect-step conflict (#462) while renaming
`git-hosting-surface-audit` -> `auditing-git-hosting-surface` (#459) to
match the gerund+object convention #281 established: the convention's own
issue only settled the *structural* pattern, never which of these
near-synonym verbs a given skill should use, and
`auditing-agent-product-scope/SKILL.md`'s own description had drifted to
open with the other family's verb ("Use when evaluating...") despite its
name being in the `auditing-*` family. Resolved by the repository owner
directly, per the Resolve step: the definitions above win, and that one
drifted description line was corrected to "Use when classifying..." to
match.

`Vetting-*` (#464) was added after reviewing PR #463's new
`evaluating-attack-surface` skill against the two definitions above: its
target (an individual artifact -- a gate, CI workflow, MCP server, or
subagent) fit `Evaluating-*`, but its verdict style (concrete per-item
tests explicitly modeled on `auditing-git-hosting-surface`'s own per-item
checklist discipline, not a maturity rubric) fit neither family's
canonical vocabulary. Resolved by the repository owner directly, per the
Resolve step: the third family above wins, rather than stretching either
existing definition to cover a shape it wasn't written for.
`evaluating-attack-surface` -> `vetting-attack-surface` was proposed as a
rename candidate on PR #463 itself, not changed here.

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

Retirement note: `fixing-a-reported-issue` was later retired; its
reproduce/fix procedure was absorbed into
`planning-a-branch-from-an-issue` plus `executing-a-branch-plan`, per
issue #1275. The "issue" vs. "bug report" naming resolution above is
unaffected by the retirement -- it settled which term wins, not which
skill implements it -- and stands unchanged.

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

## `Evaluating-*` vs. `Auditing-*` vs. `Scanning-*` (skill-naming verb families)

Three gerund-verb families this repository's skill names split into --
each with a distinct meaning, not interchangeable, despite all three
English words casually meaning "review." They split along three
independent axes: what the skill's *target* is (a repository-internal
artifact vs. an external-facing surface or this repository's own scope),
what its *verdict style* is (a fixed-dimension rubric vs. a
checklist/axis map vs. a wrapped tool's own finding format), and who
*owns the judgment* (the skill itself, reasoning against a rubric or
checklist, vs. an external tool whose findings the skill reports
unmodified). The axes do not always co-vary -- the judgment-ownership
axis is what separates `Scanning-*` from the other two families --
something the first two axes alone could not do.

- **`Evaluating-*`**: grades a repository-internal artifact (a `SKILL.md`,
  a deterministic gate) against a fixed-dimension quality rubric, producing
  a maturity verdict (`WELL-FORMED-AND-MATURE`, `PASS`/`FAIL` per
  dimension, etc.). Examples: `evaluating-skill-quality`,
  `evaluating-deterministic-gate-quality`.
- **`Auditing-*`**: classifies an external-facing configuration surface, or
  this repository's own scope, against a checklist or axis map, producing a
  coverage/classification report (`Covered`/`Partial`/`Gap`,
  `Documented`/`Unknown`/`Conflict`, etc.). One example remains:
  `auditing-agent-product-scope`. The family's other member,
  `auditing-git-hosting-surface`, was absorbed into
  `scanning-attack-surfaces` (#848), which kept its `Covered`/`Partial`/
  `Gap` vocabulary for that half of its work -- the vocabulary outlived
  the family membership, and the family list is short by one on purpose,
  not by oversight.
- **`Scanning-*`**: delegates the judgment entirely to one external,
  pinned diagnostic CLI tool and reports that tool's own findings
  unmodified -- the first family in the "delegates judgment" category,
  where the other two families both perform the judgment themselves
  (a rubric or a checklist/axis map) against human or LLM reasoning.
  Target is whatever the wrapped tool takes as input
  (CI workflow files, a dependency graph, tracked file content); verdict
  style is the wrapped tool's own finding format, never a gitapex-minted
  verdict vocabulary layered on top. Knowledge of what is vulnerable or
  misconfigured lives in the wrapped tool, never in the skill's own
  `references/`, and every `scanning-*` skill declares `write: []`.
  First shipped example: `scanning-ci-workflows`, which runs actionlint
  and zizmor over a target's GitHub Actions files and reports both
  tools' findings unmodified. The rest of the `scanning-*` roster is
  tracked at #843. (`scanning-attack-surfaces` carries the family name
  as a partial member, per that skill's own disclosure: exactly one
  sub-case -- its least-privilege check on a workflow artifact, backed
  by zizmor since #848 -- has the delegating shape, while the rest of
  that skill still performs its own per-item judgment against its own
  tests and checklists.)
  Which capability a `scanning-*` skill is allowed to reach for (the
  libre CLI it wraps vs. a platform-native equivalent) is decided by
  `scanning-capability-selection-policy.md`, not per skill.

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

`Vetting-*` (#464) was added after PR #463's `evaluating-attack-surface`
skill combined an `Evaluating-*`-style target with a verdict style
neither existing family named -- concrete per-item pass/fail tests.
Resolved by the repository owner directly as a third family rather than
stretching either existing definition. Its only member was renamed
`evaluating-attack-surface` -> `vetting-attack-surface` in gitapex#466,
then itself renamed to `scanning-attack-surfaces` once `Scanning-*`
absorbed its judgment-delegating half (#843, #844, #848) -- retiring
`Vetting-*` rather than leaving it reserved.

`Scanning-*` (#844) was added ahead of any skill that carries the name,
deliberately reusing the #464 -> gitapex#466 ordering above: the family
entry merges first, the rename and the first roster skill that depend on
the name follow. The family itself -- thin orchestrator skills, one
pinned diagnostic CLI tool each, `write: []` always -- comes from the
roster design recorded in tracking issue #843, and is this repository's
own Three-way-division pattern applied to skill naming
(`skills/evaluating-deterministic-gate-quality/references/grading-procedure.md`:
an external engine is noted as existing and taken as input to the
skill's own pass, never built, required, or substituted for).

The third axis is #844's own contribution, not #843's. Without it the
first two axes place this family closest to `Auditing-*` -- an
external-facing target, a `Covered`/`Partial`/`Gap`-shaped report -- and
neither axis as it then stood captured the actual difference, that the
verdict is not the skill's own. A family that does not produce its own
verdict cannot share a definition with one that does, so the axis was
added rather than an existing definition stretched -- the same
resolution `Vetting-*` got above. The two consumers blocked on this
entry, the `vetting-attack-surface` -> `scanning-attack-surfaces` rename
and the first roster skill (`scanning-ci-workflows`), are tracked
separately under #843.

## `Dimension`

Within `evaluating-skill-quality` and `evaluating-deterministic-gate-quality`,
a criterion that requires a model's own judgment to grade -- never a
criterion a script can grade mechanically by fixed rule. In
`evaluating-skill-quality` all nine criteria are dimensions
(`references/rubric.md`). In `evaluating-deterministic-gate-quality`, only
criteria 7-23 (the probabilistic-maturity lane, `references/dimensions.md`)
are dimensions; criteria 1-6 (the deterministic-shape lane) are shape
checks, a distinct term.

Superseded terms: `evaluating-deterministic-gate-quality`'s own prior usage
of "dimension 1" through "dimension 6" for its deterministic-shape lane --
surfaced as a terminology conflict with `evaluating-skill-quality`'s
judgment-only sense while considering an `evaluating-skill-quality` overhaul
via `drafting-a-skill`, per `establishing-ubiquitous-language`'s
Elicit/Detect/Resolve procedure. Resolved by the repository owner,
directly: "dimension" narrows to the judgment-only sense everywhere in this
skill pair; the retired numbering (1-6) is renamed `Shape check` in
`evaluating-deterministic-gate-quality`'s own docs and shipped code (#1187).
Dimensions 7-23 keep their existing numbering and label unchanged, and
`evaluating-skill-quality` is untouched by that rename.

## `Shape check`

Within `evaluating-deterministic-gate-quality` only, one of the six
deterministic-shape-lane criteria (numbered 1 through 6, with 6 further
split into sub-checks 6a and 6b) that a fixed rule -- in practice,
`scripts/gitapex_check_gate_shape.py` for Domain-2 targets -- can grade
mechanically, without a model's own judgment. Distinct from `Dimension`,
which is reserved for the judgment-only criteria (7-23) in the same skill,
and for all nine criteria in `evaluating-skill-quality`.

Adopted via #1187, replacing this skill's own prior "dimension 1" through
"dimension 6" usage for the same six criteria, to resolve the terminology
conflict with `evaluating-skill-quality`'s narrower, judgment-only sense of
`Dimension`. See that entry for the full resolution.

## `Isolation-for-neutrality`

The property of a subagent dispatch being independent of the calling
conversation's own history, framing, prior discussion, or opinion of the
specific artifact under review -- achieved by handing the dispatch only
the target artifact's path (or content) and the reviewing skill's own
files, never the calling conversation's context. Distinct from
`Instruction-file airgap` (below): the two properties are independent, so
a dispatch can hold this one while still inheriting the calling
repository's own project-instruction file.

Adopted from `skills/evaluating-skill-quality/references/adversarial-self-audit.md`'s
own "Contaminated-dispatch disclosure" section, which already named this
concept precisely: "a contaminated grader is exactly the bias risk
isolation-for-neutrality exists to prevent."

Superseded terms: bare "isolated"/"isolation", and "contaminated" /
"contaminated context" as used for this concept in
`skills/evaluating-skill-quality/SKILL.md` lines 119 and 145, since that
same skill's own `adversarial-self-audit.md` uses "contaminated" for the
unrelated `Instruction-file airgap` concept instead. Resolved by the
repository owner, directly, per the Resolve step (#1203). Not yet
propagated into any skill's own operative text.

## `Instruction-file airgap`

The property of a subagent dispatch (or any other agent-tool invocation)
being verifiably free of the calling repository's own project-instruction
file -- `CLAUDE.md`, `AGENTS.md`, or an equivalent auto-loaded mechanism
-- regardless of whether that dispatch is otherwise fresh or carries the
calling conversation's own history. Distinct from `Isolation-for-neutrality`
(above): the two properties are independent, and this repository's own
harness has been observed to grant `Isolation-for-neutrality` without
`Instruction-file airgap` (issue #475; issue #1199's own Facts).

Superseded terms: "contaminated"/"contamination" and bare
"isolated"/"isolation" as used for this concept in
`evaluating-skill-quality`'s own `adversarial-self-audit.md` and Subagent
dispatch section; and this entry's own two prior names, `CLAUDE.md-free`
and `Instruction-file freedom`, each superseded once its own basis did
not hold up under scrutiny -- see #1203 for the full resolution history.
Resolved by the repository owner, directly, per the Resolve step (#1203).
Not yet propagated into any skill's own operative text.

## `Core Domain check`

A judgment step, before committing heavy custom-modeling effort anywhere
in a design dialogue, that scores a target against three axes --
competitive advantage, complexity, volatility -- to decide whether it is
Core Domain (worth custom modeling) or Generic Subdomain (worth searching
for a precedent instead). Used in `eliciting-a-design`.

Adopted via `establishing-ubiquitous-language`'s Elicit/Detect/Resolve
procedure while designing `eliciting-a-design`
(`docs/superpowers/specs/2026-08-22-eliciting-a-design-design.md`,
Decision 3). No existing gitapex synonym covered this concept --
fresh-term case, not a conflict resolution. Grounded in Eric Evans's
Core Domain / Generic Subdomain distinction, refined into this
three-axis form by Vlad Khononov.

## `Fit-and-Gap`

In `eliciting-a-design`, a step used only when the idea under
discussion is a change to an existing system, not a greenfield build:
make the user's current state and target/destination state visible side
by side, then surface the gap between them explicitly -- what must
move, what can stay, what's genuinely new.

Adopted via the same procedure and doc as `Core Domain check`, above. No
existing gitapex synonym for this specific concept (distinct from
generic "gap analysis" usage in the wider industry). Grounded in Domain-
Driven Transformation's strategic Step 3, "Align Current Architecture
with Target."

## `Orientation Scenario`

In `eliciting-a-design`, the single concrete scenario a diffuse,
many-stakeholder conversation converges on -- via gathering scenario
fragments, prioritizing, and combining the top-priority causally-linked
ones -- before narrowing further with the normal question-and-answer
dialogue.

Adopted via the same procedure and doc as `Core Domain check`, above. No
existing gitapex synonym. Grounded in Scenario Casting (Jorn Koch, 2018).

## `Architecture trade-off` vs. `Approach`

Two distinct concepts in `eliciting-a-design`, not two names for one
thing, despite surfacing in the same dialogue. `Approach` is the
one-time, whole-project direction choice (2-3 options compared once,
early). `Architecture trade-off` is a system-level decision point
(implementation options, ownership boundaries, dependency shapes,
data-flow choices, failure-mode trade-offs, including release/rollout
strategy) that can surface at any point in the dialogue and is agreed
inline, immediately, via `clairvoyance:architecture-tradeoff` when
available.

Checked via `establishing-ubiquitous-language`'s Detect step while
designing `eliciting-a-design`
(`docs/superpowers/specs/2026-08-22-eliciting-a-design-design.md`,
Decision 3): the lexical similarity between the two is not evidence of
a synonym conflict, since they name genuinely different concepts (a
one-time choice vs. a recurring decision point) -- no owner Resolve
step was needed.

## `Portable Question Handoff`

The convention of preferring the `AskUserQuestion` tool for any decision
that needs the user's input, with a stated plain-text fallback
(`AskUserQuestion:` followed by the same question and choices) when the
tool is unavailable.

Adopted verbatim from the `clairvoyance` family
(`apm_modules/tvna/clairvoyance`) into `eliciting-a-design`'s own
vocabulary -- no translation needed, direct reuse
(`docs/superpowers/specs/2026-08-22-eliciting-a-design-design.md`,
Decision 2 and Decision 3).

## `Decision handoff`

A structured, evidence-backed presentation of an already-investigated
recommendation to a human (Verdict, Evidence, Options, Risks,
Reversibility, Next Move), used once at a closing gate -- never for an
exploratory dialogue that has not yet discovered its own options.

Adopted verbatim from the `clairvoyance` family into
`eliciting-a-design`'s own vocabulary, scoped strictly to that
skill's own terminal step
(`docs/superpowers/specs/2026-08-22-eliciting-a-design-design.md`,
Decision 2, Decision 3, and Decision 4's rejected item 3).

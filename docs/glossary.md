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

## `Evaluating-*` vs. `Auditing-*` vs. `Vetting-*` vs. `Scanning-*` (skill-naming verb families)

Four gerund-verb families this repository's skill names split into --
three carried by shipped skills today, the fourth reserved ahead of its
own first skill (see the `Scanning-*` provenance paragraph below) -- each
with a distinct meaning, not interchangeable, despite all four English
words casually meaning "review." They split along three independent axes:
what the skill's *target* is (a repository-internal artifact vs. an
external-facing surface or this repository's own scope), what its
*verdict style* is (a fixed-dimension rubric vs. a checklist/axis map vs.
concrete per-item pass/fail tests vs. a wrapped tool's own finding
format), and who *owns the judgment* (the skill itself, reasoning against
a rubric or checklist, vs. an external tool whose findings the skill
reports unmodified). The axes do not always co-vary -- `Vetting-*` exists
because one real skill combined an `Evaluating-*`-style target with
neither other family's verdict style, and the judgment-ownership axis is
what separates `Scanning-*` from all three families above it -- something
the first two axes alone could not do.

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
- **`Vetting-*`**: examines an individual artifact's own design against
  concrete, per-item pass/fail tests specific to that check -- neither a
  fixed-dimension maturity rubric nor a checklist/axis map of an
  external-facing surface. Verdict vocabulary is bespoke per skill (e.g.
  `exposure-minimal`/`exposure-excess`), always reported per item, never
  as one aggregate verdict.
- **`Scanning-*`**: delegates the judgment entirely to one external,
  pinned diagnostic CLI tool and reports that tool's own findings
  unmodified -- the first family in the "delegates judgment" category,
  where the three families above all perform the judgment themselves
  (a rubric, a checklist/axis map, or per-item tests) against human or
  LLM reasoning. Target is whatever the wrapped tool takes as input
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

`Vetting-*` (#464) was added after reviewing PR #463's new
`evaluating-attack-surface` skill against the two definitions above: its
target (an individual artifact -- a gate, CI workflow, MCP server, or
subagent) fit `Evaluating-*`, but its verdict style (concrete per-item
tests explicitly modeled on `auditing-git-hosting-surface`'s own per-item
checklist discipline -- that skill was later absorbed into this same one
by #848, so the discipline now lives there rather than in a sibling --
not a maturity rubric) fit neither family's
canonical vocabulary. Resolved by the repository owner directly, per the
Resolve step: the third family above wins, rather than stretching either
existing definition to cover a shape it wasn't written for.
`evaluating-attack-surface` -> `vetting-attack-surface` was proposed as a
rename candidate on PR #463 itself, not changed here. That rename executed
in gitapex#466 via `git mv` + `spec.lifecycle.renamedFrom`, once this entry
itself had merged.

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
`CLAUDE.md-free` (below): a dispatch can hold this property while still
inheriting the calling repository's own project-instruction file, since a
fresh dispatch with no conversation history is not automatically free of
that file -- this repository's own harness has been observed to grant one
without the other (see that entry).

Adopted from `skills/evaluating-skill-quality/references/adversarial-self-audit.md`'s
own "Contaminated-dispatch disclosure" section, where the phrase already
named this concept precisely: "a contaminated grader is exactly the bias
risk isolation-for-neutrality exists to prevent." That file is not merely
historical color: `SKILL.md`'s own Subagent dispatch section directs every
dispatch to "Apply [it] ... throughout steps 1-6," so this phrase comes
from a document the operative Procedure actually incorporates by
reference -- stronger footing than `CLAUDE.md-free`'s own precedent (see
that entry's own note on this asymmetry).

Superseded terms: bare "isolated"/"isolation", and "contaminated" /
"contaminated context" as used for this specific concept in
`skills/evaluating-skill-quality/SKILL.md` lines 119 and 145 ("still
grading from a contaminated context," describing a main thread that has
itself seen or discussed the target) -- both retire as names for this
concept, since that same skill's own `adversarial-self-audit.md` uses
"contaminated" for the unrelated `CLAUDE.md-free` concept instead (see
below), and mixing the two under one word is exactly the conflict this
entry resolves. Resolved by the repository owner, directly, per the
Resolve step, choosing to formalize this repository's own existing phrase
over two invented alternatives (#1203). Stated precisely so this entry is
not read as claiming more than it does: `SKILL.md` lines 119/145's own
wording, and its Subagent dispatch section and Stop boundary (lines
130-132, 452) that still say "isolated"/"exclude that file," are not
renamed by that issue -- this term is resolved and recorded here, not yet
propagated into any skill's own operative text. A separate, later rename
issue would be needed for that.

## `CLAUDE.md-free`

The property of a subagent dispatch (or any other agent-tool invocation)
being verifiably free of the calling repository's own project-instruction
file -- `CLAUDE.md`, `AGENTS.md`, or an equivalent auto-loaded mechanism
-- regardless of whether that dispatch is otherwise fresh or carries the
calling conversation's own history. Distinct from `Isolation-for-neutrality`
(above): the two properties are independent, and this repository's own
harness has been observed to grant the former without the latter --
issue #475 found this for an ordinary dispatch, and a later session's
live test (recorded in issue #1199's own Facts) found it held even when
the dispatch was given a different backing model (`fable`), so a
dispatch with no conversation history can still inherit the repository's
own `CLAUDE.md` in full.

This exact string already appears in four places before this entry, but
precision matters about what kind of usage that is: all four are
retrospective audit narration, not any skill's own operative Procedure or
Subagent dispatch prose. Two are `kind: audit` entries' own `summary:`
field in a `metadata/gitapex.yaml` sidecar --
`skills/evaluating-skill-quality/metadata/gitapex.yaml` ("same
CLAUDE.md-free scratch dir") and
`skills/scanning-attack-surfaces/metadata/gitapex.yaml` ("a genuinely
isolated CLAUDE.md-free re-run") -- both maintainer-facing audit-round
records, not auto-loaded instruction text a dispatch reads. The other two
are in `skills/battle-testing-a-skill/references/provenance-and-caveats.md`
("that CLAUDE.md-free clean-copy practice", "CLAUDE.md-free clean-copy
run"), a file that names itself descriptive precedent, not a requirement:
"that CLAUDE.md-free clean-copy practice existed only as descriptive
precedent in this file... not a requirement `SKILL.md`'s own Procedure
enforced." As of this entry, no skill's own operative `SKILL.md` text --
Procedure, Subagent dispatch section, or Stop boundary -- uses
`CLAUDE.md-free` anywhere; `evaluating-skill-quality/SKILL.md` itself
still reads "project-instruction file" / "exclude that file" (lines
131-132, 452) and bare "isolat-" elsewhere (lines 40, 46, 171, 186). This
gives `CLAUDE.md-free` weaker operative footing than
`Isolation-for-neutrality` (above), whose own source document `SKILL.md`
directly incorporates by reference; here the precedent is retrospective
narration only, and the choice of this term still rests on the Resolve
step below, not on that narration outweighing the alternatives on its
own.

Superseded terms: "contaminated"/"contamination" as used for this concept
in `skills/evaluating-skill-quality/references/adversarial-self-audit.md`'s
"Contaminated-dispatch disclosure" section, and bare "isolated"/
"isolation" as used in `evaluating-skill-quality`'s own Subagent dispatch
section for the project-instruction-file exclusion requirement
specifically -- both retained as accurate description of the mechanism or
the failure mode, but "CLAUDE.md-free" is now this repository's preferred
name for the property itself, resolved and recorded here, not yet
propagated into any skill's own operative text -- see this entry's own
note above and `Isolation-for-neutrality`'s matching disclosure.
`evaluating-deterministic-gate-quality`'s own equivalent wording is
intentionally not cited here: a separate, concurrently open issue governs
that skill's own exclusion-requirement
text, and this entry does not assume or depend on that issue's outcome.
Resolved by the repository owner, directly, per the Resolve step (#1203).

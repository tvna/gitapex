# merge-retrospective skill implementation plan

Refs #6

Date: 2026-07-12

## Context

`CLAUDE.md` chapter 3 requires: after each merge, auto-open a
retrospective issue that enumerates every repair between PR open and
merge, classifies each with a fixed three-way taxonomy, and proposes a
durable gate for the repairs that a deterministic check should have
caught. gitapex has no deterministic harness yet, so this skill is the
bootstrap signal that tells the owner which gate to build next.

Issue #6 is exhaustive and already fixes every open design question
(taxonomy, trigger wording, Stop boundary, skill-authoring standards, a
concrete two-repair dry-run scenario). No separate design spec is
warranted for a single-file skill addition (CLAUDE.md 1: "concise spec
otherwise") -- this plan doc folds spec and plan together.

## Scope

- One file: `skills/merge-retrospective/SKILL.md`.
- No `references/` subdirectory -- content fits the informal 500-line
  budget.
- No hooks, no CI gate, no automatic filing of follow-up gate-tracking
  issues -- proposing a durable gate happens inline in the retrospective
  issue body; implementing it is explicitly out of scope (issue #6, "Out
  of scope").

## Decisions carried from issue #6 (fixed, not to be re-derived)

- Taxonomy is exactly three categories, verbatim from CLAUDE.md chapter
  3: missing deterministic gate / unclear agent instruction /
  external-human decision that cannot be automated. Never a fourth.
- Trigger: "Use when a pull request has just merged, before closing the
  turn." This must read as strictly post-merge, so it cannot be confused
  with `driving-pr-to-merge` (#5, pre-merge) or `explaining-the-work`
  (comment/commit/test routing, unrelated phase).
- Stop boundary: an empty repair list is not a reason to skip filing --
  it is itself evidence the process worked for that cycle, and gets
  filed too.
- GitHub write happens through the platform-integrated tool
  (`mcp__github__issue_write`), never a CLI wrapper, per CLAUDE.md
  chapter 3's tool-selection rule. Named fully qualified in the skill
  body per issue #6's "skill authoring standards" bullet.
- Worked example baked into the skill body: two repairs (one failed CI
  rerun, one review fix round), each independently classified, producing
  a retrospective issue body -- this doubles as the acceptance-criteria
  #3 dry-run artifact.

## Verification

No runtime code is added, so there is no pytest suite for this change.
Verification is manual/structural, mirroring PR #2's approach:

- Frontmatter: `name: merge-retrospective` matches the directory,
  `description` is single-line third-person with a "Use when..."
  trigger, no XML tags.
- `SKILL.md` body stays under 500 lines.
- All three taxonomy categories appear verbatim and a fourth is
  explicitly disclaimed.
- The Stop section states the empty-repair-list rule from issue #6's
  acceptance criteria.
- The worked example produces a plausible, correctly classified
  retrospective issue body for the two-repair scenario in issue #6's
  acceptance criteria #3.
- Final review pass via the `code-review` skill before pushing.

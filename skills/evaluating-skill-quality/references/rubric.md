# Skill quality rubric

Portable evaluation reference for judging whether a `SKILL.md` (and its
`references/`) is good, originally adapted for gitapex from
`tvna/clairvoyance`'s skill-quality-knowledge and skill-maturity-checklist
documents (themselves a distillation of the [Agent Skills best
practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
This skill travels with any repo it is vendored into: where a target
repository lacks a piece of clairvoyance-style tooling (a deterministic
checker script, an eval suite, a battle harness), dimensions 1-9 below say
to check the target repository directly and state the gap explicitly,
rather than assuming a specific repo's tooling state or citing a file
outside this skill's own folder.

## Table of contents

- [The mental model](#the-mental-model)
- [1. Discovery -- name and description](#1-discovery----name-and-description)
- [2. Conciseness](#2-conciseness)
- [3. Degree of freedom](#3-degree-of-freedom)
- [4. Clarity and structure](#4-clarity-and-structure)
- [5. Progressive disclosure](#5-progressive-disclosure)
- [6. Durability](#6-durability)
- [7. Bundled scripts](#7-bundled-scripts-only-if-the-skill-ships-code)
- [8. Behavioural evidence](#8-behavioural-evidence)
- [9. Cross-model robustness](#9-cross-model-robustness)
- [Verdicts](#verdicts)

## The mental model

A skill is an addition to an already-capable model, not a tutorial. Content
that re-teaches general concepts, common tools, or standard formats is
waste. Skills load by progressive disclosure at three costs: `name` +
`description` are always resident (every skill, every turn); the
`SKILL.md` body loads once triggered, wholesale; `references/` load only on
demand. Judge each piece of information by whether it lives at the cheapest
level that still makes it available the moment it is needed.

## 1. Discovery -- name and description

`SKILL.md`'s deterministic checklist confirms a trigger *exists* (third
person, no XML tags, single line). This dimension judges whether it is the
*right* trigger -- whether the skill would win its intended request and
lose a neighbour's.

- **States both what and when, in terms a real request would contain** --
  not just any capability statement plus any trigger clause, but specific
  enough that a router would not confuse this skill with a sibling's.
- **Specific key terms, no filler** ("helps with documents" matches
  everything and therefore nothing).
- **`name` reads as an activity** (gerund preferred) and is **distinct from
  every sibling skill** -- no overlap that makes routing ambiguous. Neither
  of these is a shape check a script can decide.
- **Fail example:** a description that only says what the skill does, with
  no trigger, or a trigger so generic it would also match a sibling's
  request.
- **Pass example:** "Extract text and tables from PDF files, fill forms,
  merge documents. Use when working with PDF files or when the user
  mentions PDFs, forms, or document extraction." -- names the operations,
  names the trigger terms.

## 2. Conciseness

Challenge each paragraph: does the model need this explanation, does it
already know this, does the paragraph justify its token cost? A "no" to any
is a cut.

- **Fail:** explaining what a well-known format or tool is; restating the
  same instruction in two places; motivational padding.
- **Pass:** assumes competence, states only the project- or task-specific
  delta, reaches actionable content fast.

## 3. Degree of freedom

Prescription must match the operation's fragility:

- **High freedom (prose)** -- open field, many valid routes; multiple
  approaches work and context decides.
- **Medium freedom (parameterised pattern)** -- a preferred shape exists,
  some variation is fine.
- **Low freedom (exact steps/commands, few or no parameters)** -- narrow
  bridge with cliffs; the operation is fragile, consistency is critical, or
  a precise sequence must hold.

Flag a mismatch in either direction: rigid step-by-step for an open-ended
judgment task over-constrains a smart model; loose prose for a fragile,
irreversible operation invites improvisation where there is exactly one
safe way.

## 4. Clarity and structure

- **Consistent terminology** -- one term per concept, throughout the skill
  and its references.
- **Concrete examples over abstract description** -- real input/output
  pairs, not a description of what good output looks like.
- **Workflows as ordered steps** -- a copyable checklist when the sequence
  is long or steps are skippable-but-risky.
- **Feedback loops on quality-critical steps** -- validate -> fix -> repeat
  ("only proceed when validation passes") on any step where errors are
  likely and costly. Its absence there is a gap.
- **Templates matched to strictness** -- an exact template where the format
  is a hard contract, a "sensible default, use judgment" template where
  adaptation helps.

## 5. Progressive disclosure

`SKILL.md`'s deterministic checklist confirms reference depth and TOC
presence by shape. This dimension judges the *meaning* behind the split --
naming, linking, and whether the common case is forced through more than
one read.

- Reference files named for content (`decision-handoff.md`, not `doc2.md`),
  organised by domain.
- `SKILL.md` links to each reference at the point of need, so the model
  loads it on demand instead of guessing it exists. An unlinked reference is
  dead weight; a needed one with no pointer is invisible.
- Splits must not force several reads for the common case -- if acting on
  the typical request needs three files open, the split is wrong.
- Detail needed only sometimes belongs in `references/`; detail the model
  reads on every single use belongs inlined in `SKILL.md`. Both directions
  are failures.

## 6. Durability

- No time-sensitive content ("before August 2025 use the old API"). Any
  historical content is explicitly marked as such, not left to silently rot.
- No assumption that a tool or package is installed without saying so.
- MCP tools named fully qualified as `Server:tool` (e.g. `GitHub:create_issue`),
  never a bare tool name.
- Forward slashes in every path (`references/rubric.md`), never backslashes.
- A default with an escape hatch, not a menu of options.

## 7. Bundled scripts (only if the skill ships code)

- **Solve, don't punt** -- scripts handle their own error conditions
  (missing file, permission denied) rather than throwing and leaving the
  model to cope.
- **No voodoo constants** -- every configuration value is justified in a
  comment. A constant the author cannot justify, the model cannot either.
- **Dependencies listed; execution intent stated** -- required packages
  named, and it is explicit whether the model should execute the script or
  read it as reference.
- **Verifiable intermediate outputs** for high-stakes batch work -- a
  plan -> validate -> execute pattern with a machine-checkable plan file.

## 8. Behavioural evidence

The upstream standard: a suite that exercises the skill's real trigger,
asserts the structural markers it reliably emits, includes
`output_not_contains` guardrails, and covers at least three representative
scenarios including the failure/guardrail case.

**Check the target repository for an `evals/` directory or `waza`-equivalent
runner before scoring this dimension.** If gitapex itself is the target, it
has none today. Whatever the target, never silently skip this dimension:
state plainly that behavioural evidence is unmeasured for the reviewed
skill when no suite exists, rather than scoring it pass or fail without one
to back the score.

## 9. Cross-model robustness

A skill's effect depends on the model running it. Judge -- or state that you
cannot yet judge -- against every tier the skill is likely to run under:

- **Haiku (fast, economical):** does the skill give *enough* guidance?
- **Sonnet (balanced):** is it clear and efficient?
- **Opus / Fable (strong reasoning, and above):** does it avoid
  *over*-explaining? On the Fable tier specifically, over-prescribed,
  low-freedom scaffolding written for a weaker model can measurably reduce
  output quality rather than merely waste context -- a low-freedom skill
  that helps Haiku or Sonnet can legitimately be a regression on Fable.

Behaviour observed on one model is not evidence for another. **Check the
target repository for a battle harness or per-model eval runner before
scoring this dimension** (same check as dimension 8, against a different
kind of harness). When this dimension cannot be measured, say so explicitly
rather than asserting robustness from a single-model read. A qualitative
read is
still allowed (e.g. "this skill is a fixed low-freedom policy, so
over-prescription risk is probably low, but this is a read, not measured
evidence") as long as it is labeled as such.

## Verdicts

- **Well-formed** -- clears every deterministic shape check (frontmatter,
  naming, description shape, body length, reference depth/TOC). Says
  nothing about whether the skill is good.
- **Mature** -- well-formed, and every dimension 1-7 clears cleanly with no
  named gap (a "minor" gap still means that dimension has not cleared).
  Dimensions 8-9 are the one exception: because they depend on tooling a
  target repository may not have yet, either measured or explicitly named
  as an unmeasured gap (never silently assumed) is sufficient for them
  specifically -- naming the gap does not, on its own, block "mature" the
  way an uncleared dimension 1-7 gap does.

A verdict without cited evidence per dimension is not a review -- it is a
guess wearing a review's shape.

A **mature** verdict is bounded by what the target repository can currently
measure: when dimensions 8-9 are named as unmeasured rather than passed,
"mature" means "clears everything that repository's tooling can check
today," not "proven in behaviour." That named gap is the explicit, recorded
acknowledgment a live-proof gate requires -- it does not itself waive any
live-proof check the reviewing repository applies before landing other
kinds of changes.

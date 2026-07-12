# establishing-ubiquitous-language skill implementation plan

Refs #10

Date: 2026-07-12

## Context

A project's ubiquitous language (the DDD term for a shared, consistent
vocabulary used identically by people and agents in code, docs, issues, and
conversation) drifts when near-synonymous terms are used loosely for the
same concept. gitapex has already hit this in practice: `docs/motivation.md`
(added in PR #2) needed a follow-up commit (`ef222b81`, "ascii-only
motivation diagrams, split skills, contributor wording") renaming its human
participant from "owner" to "contributor" because the two terms were being
used loosely for the same role. This skill exists to catch that kind of
drift before it needs a fix-up commit, applying CLAUDE.md ch.2's general
"never pick silently" principle specifically to terminology conflicts.

Issue #10 is exhaustive and already fixes every open design question
(trigger wording, scope, Stop boundary, glossary-scaffold minimal scope, the
concrete owner/contributor/author worked example). No separate design spec
is warranted for a single-skill-plus-scaffold addition (CLAUDE.md 1:
"concise spec otherwise") -- this plan doc folds spec and plan together,
mirroring the `merge-retrospective` precedent (issue #6 / PR for #6).

## Scope

- `skills/establishing-ubiquitous-language/SKILL.md` -- one file, no
  `references/` subdirectory (content fits the informal 500-line budget).
- `docs/glossary.md` -- a scaffold, per issue #10's acceptance criteria
  ("even a header plus a placeholder" is acceptable minimal scope). Seeded
  with the one real, already-resolved term from the worked example
  (Contributor, superseding Owner per PR #2) so the scaffold demonstrates
  the skill's own output rather than shipping empty.
- No hooks, no CI gate, no `references/` -- none of these are asked for and
  none exist as a pattern in this repo yet.

## Deferred: a deterministic glossary drift gate (explicit non-goal)

`docs/glossary.md` declares itself the single source of truth for this
repo's terminology, which is the kind of invariant CLAUDE.md ch.3 says
must ship with its own deterministic drift gate in the same change ("if
the gate is missing, build it before the operation it guards"). This PR
does not ship one, and that omission is deliberate, not an oversight --
recorded here explicitly per this same repo's own precedent of naming
deferred gates (see the skill-distribution-foundation design spec's
Non-goals section) rather than silently skipping them.

Reason: the invariant here is prose-terminology consistency, not a
mechanically checkable fact (a duplicated version string, a single
canonical config value). A deterministic gate would need to grep the
repository for superseded terms (for example "Owner", which the glossary's
Contributor entry supersedes for one specific role) and fail when they
reappear -- but this repo's own CLAUDE.md legitimately uses "owner" in an
unrelated, correct sense throughout (the project owner / decision
authority a contributor escalates to), a sense the glossary explicitly
does not supersede. A naive text-match gate would false-positive on that
legitimate usage immediately, and any allowlist built to suppress those
false positives would grow ad hoc and stop meaning anything -- which is
exactly the ambiguity this skill's human-in-the-loop "ask, do not pick
silently" design exists to handle instead of a lint rule. Building a gate
that can tell those two senses of "owner" apart is a semantic task, not a
deterministic one, and is out of scope for this change the same way the
distribution-foundation spec already deferred `scripts/check_skills.py`
-style automated quality gates for a parallel reason.

This is recorded as a standing deferral, not resolved by this plan. A
future issue can revisit it if and when a tractable deterministic check
(for example, validating `docs/glossary.md`'s own entry shape, rather than
scanning the whole repo for terminology drift) is worth building.

## Decisions carried from issue #10 (fixed, not to be re-derived)

- Trigger: "Use when a project's terminology is inconsistent or undefined
  across code, docs, and issues -- before introducing a new domain concept,
  naming a module or skill, or writing glossary/ADR content." Specific
  enough not to overlap `explaining-the-work` (comment/commit/test routing)
  or any sibling skill from the same batch (#5-#9, #11).
- Procedure has exactly the four steps issue #10 names: elicit candidate
  terms (code identifiers, docs, issue/PR history), detect synonyms/near-
  duplicates, ask the owner which term wins on conflict (never pick
  silently), maintain `docs/glossary.md` as the single source of truth.
- Worked example is the real `docs/motivation.md` owner -> contributor
  case, not a fictitious one -- issue #10 requires "at least the
  contributor/owner/author case above" as the worked example.
- Stop boundary, verbatim intent from issue #10's acceptance criteria:
  never unilaterally rename existing code or identifiers to match the
  glossary (that is a separate refactor decision requiring its own
  review); never invent a new term without first checking it does not
  already exist under a different name.
- Degree of freedom: high-freedom prose guidance, not a rigid script --
  eliciting terms and resolving synonym conflicts is open-ended,
  context-dependent judgement (per issue #10's skill-quality-knowledge.md
  citation).
- Any MCP tool referenced is named fully qualified (`Server:tool`); all
  paths use forward slashes.

## Verification

No runtime code is added, so there is no pytest suite for this change.
Verification is manual/structural, mirroring PR #2 and the
`merge-retrospective` plan's approach:

- Frontmatter: `name: establishing-ubiquitous-language` matches the
  directory, `description` is single-line third-person with a "Use
  when..." trigger, no XML tags.
- `SKILL.md` body stays under 500 lines.
- Procedure names all four steps from issue #10 (elicit, detect, ask,
  maintain glossary).
- The worked example reproduces the real owner/contributor/author case
  from `docs/motivation.md` and PR #2, not a fictitious substitute.
- Stop boundaries section states both required rules: no unilateral
  renames, no new term without checking for an existing synonym first.
- `docs/glossary.md` exists, is non-empty (header + the Contributor
  entry), and does not attempt to bulk-rename any existing repo
  terminology as a side effect.
- Existing `scripts/`/`tests/` pytest suite untouched and still passing.
- Final review pass via the `code-review` skill before pushing.

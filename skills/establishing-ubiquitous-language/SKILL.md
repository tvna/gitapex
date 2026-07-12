---
name: establishing-ubiquitous-language
description: Use when a project's terminology is inconsistent or undefined across code, docs, and issues -- before introducing a new domain concept, naming a module or skill, or writing glossary/ADR content. Elicits candidate terms from code, docs, and issue history, flags synonyms describing the same concept, and asks the owner which term should win instead of picking silently, keeping one glossary doc as the source of truth.
---

# Establishing Ubiquitous Language

Ubiquitous language is the Domain-Driven Design term for a shared,
consistent vocabulary used identically by people and agents in code, docs,
issues, and conversation. CLAUDE.md ch.2 states a general principle worth
citing here, not written for this skill but directly applicable: "If
multiple interpretations exist, list them all. Never pick silently." This
skill applies that same discipline specifically to terminology conflicts,
before they need a fix-up commit.

## Procedure

1. **Elicit.** Pull candidate domain terms from existing code identifiers
   (class/function/module names), docs prose, and issue/PR titles and
   bodies. A term is a candidate the moment it names a concept someone
   would need to look up.
2. **Detect.** Look for synonyms or near-duplicate terms referring to the
   *same* concept -- for example, two words used interchangeably for the
   same role, status, or entity. Lexical similarity alone is not evidence
   of synonymy: two terms that merely sound alike but name genuinely
   different concepts are not a conflict.
3. **Resolve.** When a conflict is found, ask the owner which term should
   win -- never pick silently. Do not resolve it by fiat, by frequency
   count, or by whichever term you happened to write first.
4. **Maintain the glossary.** Record the winning term in a single glossary
   doc (`docs/glossary.md` in this repo) as the source of truth, noting
   the superseded synonym so it does not resurface unrecognized later.

## Worked example: contributor vs. owner vs. author

`docs/motivation.md` (added in gitapex PR #2) is the real precedent this
skill is built around. Its first draft used "owner" as the name for the
human participant in the Design-by-Contract sequence diagrams. A later
commit in the same PR (`ef222b81`, "ascii-only motivation diagrams, split
skills, contributor wording") renamed that participant from "owner" to
"contributor," because the flow those diagrams describe is not specific to
repository owners -- any contributor can drive it. The diagrams also name a
third, lexically similar but conceptually distinct role: "Author" (the AI
implementer), which was never a synonym candidate for the human role.

Applying the procedure to that same state, before the rename commit:

- **Elicit:** scanning the diagram source and surrounding prose turns up
  three participant labels in use: `Owner` (the diagram's initial human
  participant name), `Contributor` (used in the surrounding prose
  describing who drives the flow), and `Author` (the AI implementer
  participant).
- **Detect:** `Owner` and `Contributor` both denote the human giving
  instructions in the sequence diagram -- flagged as candidate synonyms for
  one concept. `Author` is not a synonym for either: it names a distinct
  concept (the AI role), and the lexical similarity to "owner" (both are
  short role nouns) does not make it one.
- **Resolve:** rather than assuming either term, the actual resolution
  asked which should win for the human-role concept. The repo's own commit
  message records the answer: "contributor," because the flow is not
  owner-specific.
- **Maintain the glossary:** the winning term gets an entry in
  `docs/glossary.md` --

  ```
  ## Contributor
  The human giving instructions in the Design-by-Contract issue/PR flow
  (docs/motivation.md). Not to be conflated with "repository owner" (a
  GitHub permission role) or "Author" (the AI author/implementer
  participant in the same diagrams) -- distinct concepts, not synonyms.
  Superseded terms: "Owner" (renamed to Contributor in gitapex PR #2,
  commit ef222b81, since the flow is not owner-specific).
  ```

Note what this example does *not* do: it does not go back and rename any
identifier in actual code, and it does not invent "Contributor" from
nothing -- it surfaces that the resolution already happened in this
repo's own history and records it, which is exactly the glossary's job.

## Stop boundaries

- Never unilaterally rename existing code or identifiers to match the
  glossary. Renaming existing code is a separate refactor decision that
  requires its own review -- this skill documents the resolved term, it
  does not execute the rename.
- Never invent a new term without first checking it does not already
  exist under a different name -- run Elicit and Detect before adding
  anything to the glossary, even when no conflict turns out to exist.
- Never resolve a detected conflict silently. Ask the owner; do not decide
  by fiat, frequency, or authorship convenience.

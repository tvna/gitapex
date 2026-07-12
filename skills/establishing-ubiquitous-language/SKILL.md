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
2. **Detect.** Look for two kinds of conflict: synonyms or near-duplicate
   terms already in use for the *same* concept (two words used
   interchangeably for the same role, status, or entity), and a single
   term that is narrower or borrowed from a different scope than the
   concept it is being used to name (for example, a term that collides
   with an existing, more specific meaning elsewhere). Lexical similarity
   alone is not evidence of either: two terms that merely sound alike but
   name genuinely different concepts are not a conflict.
3. **Resolve.** When a conflict is found, ask the owner which term should
   win -- never pick silently. Do not resolve it by fiat, by frequency
   count, or by whichever term you happened to write first.
4. **Maintain the glossary.** Record the winning term in a single glossary
   doc (`docs/glossary.md` in this repo) as the source of truth, noting
   the superseded synonym so it does not resurface unrecognized later.

## Worked example: owner vs. author vs. contributor

`docs/motivation.md` (added in gitapex PR #2) is the real precedent this
skill is built around. Its first draft (commit `241f4392`) named the human
participant in the Design-by-Contract sequence diagrams `Owner` (with a
Japanese-language display label meaning roughly "person (owner)" -- this
draft predates the ASCII-only translation described below), and its prose
read "an owner instruction flows through Issue authoring...". A later
commit in the same PR (`ef222b81`, "ascii-only motivation diagrams, split
skills, contributor wording") renamed that participant and prose from
"owner" to "contributor" (and translated the whole document to ASCII-only
English in the same commit), because the flow those diagrams describe is
not specific to repository owners -- any contributor can drive it. The
diagrams also name a second,
lexically similar but conceptually distinct role, `Author` (the AI
implementer), present unchanged in both the before and after state -- it
was never a candidate for this conflict.

Applying the procedure to the pre-rename state (before commit `ef222b81`):

- **Elicit:** scanning the diagram source and surrounding prose turns up
  two role labels in use: `Owner` (the diagram's human participant, and the
  noun the prose used -- "an owner instruction") and `Author` (the AI
  implementer participant). No "Contributor" label exists yet at this
  point -- it is introduced only by the resolution below, not found
  already coexisting with `Owner`.
- **Detect:** `Owner` is borrowed from GitHub's own permission vocabulary
  (a specific access-control role), but the concept it names here --
  whoever is giving the instruction that starts this flow -- is broader
  than that: the flow is not owner-specific. A borrowed term that is
  narrower than the concept it is standing in for is a naming problem
  worth flagging even when only one term is in use so far -- this is a
  term-to-concept mismatch, not two synonyms already colliding. `Author`
  is not implicated: it names a distinct concept (the AI role), and its
  lexical similarity to "owner" (both short role nouns) does not make it a
  candidate.
- **Resolve:** rather than silently swapping in a guess, ask which term
  should actually name the concept. The repo's own commit message records
  the answer: "contributor," with the stated reason that the flow is not
  owner-specific.
- **Maintain the glossary:** the winning term gets an entry in
  `docs/glossary.md` --

  ```
  ## Contributor
  The human giving instructions in the Design-by-Contract issue/PR flow
  (docs/motivation.md). Not to be conflated with "repository owner" (a
  GitHub permission role) or "Author" (the AI author/implementer
  participant in the same diagrams) -- distinct concepts, not synonyms.
  Superseded terms: "Owner" (used in the initial draft of
  docs/motivation.md; renamed to Contributor in the same PR (#2), commit
  ef222b81, because the flow described is not specific to repository
  owners).
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

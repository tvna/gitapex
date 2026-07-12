---
name: establishing-ubiquitous-language
description: Use when a project's terminology is inconsistent or undefined across code, docs, and issues -- before introducing a new domain concept, naming a module or skill, or writing glossary/ADR content. Elicits candidate terms from code, docs, and issue history, flags synonyms describing the same concept, and asks the owner which term should win instead of picking silently, keeping one glossary doc as the source of truth.
---

# Establishing Ubiquitous Language

Ubiquitous language is the Domain-Driven Design term for a shared,
consistent vocabulary used identically by people and agents in code, docs,
issues, and conversation.

This skill is self-contained: the procedure below does not require the
calling repository to have a CLAUDE.md, an AGENTS.md, or any particular
instruction file, and does not assume one has a specific chapter or
section structure. It applies one general principle -- if multiple
interpretations exist, list them all, never pick silently -- specifically
to terminology conflicts, before they need a fix-up commit. Where a
calling repository's own instruction file happens to state a related
principle (gitapex's own CLAUDE.md ch.2 is one such example, cited here
only as a cross-reference, not as a dependency), that is a coincidence of
overlapping values, not something this skill's procedure relies on being
present.

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
4. **Maintain the glossary.** Record the winning term in this skill's own
   glossary file (`references/glossary.md`, alongside this SKILL.md) as
   the source of truth, noting the superseded synonym so it does not
   resurface unrecognized later. If the calling repository already has its
   own established glossary location, use that instead -- this skill's own
   `references/glossary.md` is the default when no repo-specific
   convention exists yet, not a fixed requirement.

## Worked example: owner vs. author vs. contributor

A real precedent, condensed here; the full version (with commit-level
detail) is `references/worked-example.md`, alongside this file.

A design document in this skill's home repository's history originally
named the human participant in a sequence diagram `Owner`, using a term
borrowed from GitHub's own permission vocabulary (a specific access-control
role) for a broader concept -- whoever gives the instruction that starts
the flow, which is not owner-specific. That mismatch was later resolved by
renaming the participant to `Contributor`. A second, lexically similar but
conceptually distinct role, `Author` (an AI implementer), was present
throughout and was never a candidate for this conflict.

Applying the procedure to the pre-rename state:

- **Elicit:** two role labels in use -- `Owner` (the human participant) and
  `Author` (the AI implementer). No "Contributor" label exists yet; it is
  introduced only by the resolution below.
- **Detect:** `Owner` is narrower than the concept it names here -- a
  term-to-concept mismatch, not two synonyms already colliding. `Author`
  is not implicated: distinct concept, and lexical similarity to "owner"
  (both short role nouns) is not evidence of synonymy.
- **Resolve:** rather than silently swapping in a guess, ask which term
  should actually name the concept. The resolution: "contributor," because
  the flow is not owner-specific.
- **Maintain the glossary:** the winning term gets an entry in this
  skill's `references/glossary.md` (see that file for the actual entry).

Note what this example does *not* do: it does not go back and rename any
identifier in actual code, and it does not invent "Contributor" from
nothing -- it surfaces that the resolution already happened in this
skill's home repository's own history and records it, which is exactly the
glossary's job.

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

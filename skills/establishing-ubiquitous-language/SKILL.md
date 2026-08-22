---
name: establishing-ubiquitous-language
description: Use when a project's terminology is inconsistent or undefined across code, docs, and issues -- before introducing a new domain concept, naming a module or skill, or writing glossary/ADR content. Elicits candidate terms from code, docs, and issue history, flags synonyms describing the same concept, and asks the owner which term should win instead of picking silently, keeping one glossary doc as the source of truth.
---

# Establishing Ubiquitous Language

Ubiquitous language is the Domain-Driven Design term for a shared,
consistent vocabulary used identically by people and agents in code, docs,
issues, and conversation.

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
4. **Maintain the glossary.** Record the winning term in the calling
   repository's own glossary doc (e.g. `docs/glossary.md`), creating it
   there if none exists yet, as the source of truth -- noting the
   superseded synonym so it does not resurface unrecognized later. Do not
   write real entries into this skill's own
   [references/glossary.md](references/glossary.md); that file is a
   read-only template and rots when the skill is vendored or installed
   read-only. Keep the entry itself to a definition, at most one
   cross-reference to a sibling or distinct concept, and a brief
   superseded-terms note citing the resolving issue -- session-specific
   deliberation (test methodology, trial-by-trial evidence, rejected-
   candidate reasoning) belongs in the PR or issue history that recorded
   the Resolve step, not in the glossary entry itself.

## Worked example: owner vs. author vs. contributor

A real precedent from this skill's own home repository's history: a design
document once named a role `Owner`, a term narrower than the concept it
named (whoever gives the instruction that starts a flow, not necessarily a
repo owner). Applying Elicit/Detect/Resolve/Maintain surfaced the mismatch
and the already-resolved answer, `Contributor`, without renaming any code
or inventing a term from nothing.

See [references/worked-example.md](references/worked-example.md) for the
full walkthrough, step by step.

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
- Never carry session-specific deliberation into the glossary entry
  itself -- Step 4's own cap, restated here as a prohibition. Match the
  `Contributor` worked example's own register, never the fuller record
  the PR/issue keeps.

## Notes

Portability rationale: self-contained; requires no particular instruction
file. The declared level itself lives in `metadata/gitapex.yaml`.

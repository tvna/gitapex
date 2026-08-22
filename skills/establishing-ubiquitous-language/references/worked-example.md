# Worked example: owner vs. author vs. contributor

## Contents

1. Applying the procedure
2. What this would look like done wrong

This is the full version of the example summarized in `../SKILL.md`. It is
a real precedent from this skill's own home repository's history (cited by
commit SHA and PR number for provenance, not as a live file dependency --
nothing here requires reading any other file to make sense).

A sequence-diagram design document in this repository's history originally
named the human participant in its Design-by-Contract flow `Owner` (with a
non-ASCII, non-English display label meaning roughly "person (owner)" in
its first draft), and its prose read "an owner instruction flows through
Issue authoring...". A later commit in the same pull request ("ascii-only
motivation diagrams, split skills, contributor wording") renamed that
participant and prose from "owner" to "contributor" (and translated the
whole document to ASCII-only English in the same commit), because the
flow those diagrams describe is not specific to repository owners -- any
contributor can drive it. The diagrams also name a second, lexically
similar but conceptually distinct role, `Author` (the AI implementer),
present unchanged in both the before and after state -- it was never a
candidate for this conflict.

## Applying the procedure

Applying the procedure to the pre-rename state (before the rename commit):

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
- **Maintain the glossary:** the winning term gets an entry in this
  skill's `glossary.md` --

  ```
  ## Contributor
  The human giving instructions in this repository's Design-by-Contract
  issue/PR flow. Not to be conflated with "repository owner" (a GitHub
  permission role) or "Author" (the AI author/implementer participant in
  the same flow) -- distinct concepts, not synonyms.
  Superseded terms: "Owner" (used in the initial draft; renamed to
  Contributor in the same pull request, because the flow described is not
  specific to repository owners).
  ```

Note what this example does *not* do: it does not go back and rename any
identifier in actual code, and it does not invent "Contributor" from
nothing -- it surfaces that the resolution already happened in this
repo's own history and records it, which is exactly the glossary's job.

## What this would look like done wrong

Illustrative only -- the `Contributor` entry above is the real one that
shipped. This is a hypothetical bloated version of that same entry, in
the style the calling repository's own `docs/glossary.md` actually
produced and later had to trim back down (two entries once carried this
shape until a later commit cut them to the register `Dimension`/`Shape
check` use):

```markdown
## Contributor
The human giving instructions in this repository's Design-by-Contract
issue/PR flow. Not to be conflated with "repository owner" (a GitHub
permission role) or "Author" (the AI author/implementer participant in
the same flow) -- distinct concepts, not synonyms.

Three candidate terms were tested before settling on this one: "Owner"
(rejected -- 3 of 3 trial readers assumed it meant the GitHub repo-
permission role, not whoever starts the flow), "Requester" (rejected --
2 of 3 trials read it as a purely technical HTTP-request sense, unrelated
to the Design-by-Contract flow), and "Contributor" (passed cleanly, 3 of
3 trials, no competing sense found). The rejected-candidate reasoning and
trial methodology are recorded here for completeness.

Superseded terms: "Owner" (used in the initial draft; renamed to
Contributor in the same pull request, because the flow described is not
specific to repository owners).
```

The problem is not that this entry is wrong -- its definition and
superseded-terms note are the same as the real one above. The problem is
the middle paragraph: trial counts and rejected-candidate reasoning are
session-specific deliberation, exactly the kind of narrative Step 4 and
this skill's Stop boundaries reserve for the PR or issue history that
recorded the Resolve step, not for the glossary entry. A reader who only
needs the resolved term and its superseded synonym has to read past a
methodology writeup to find them.

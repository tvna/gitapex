# outward-artifact-preflight skill

Date: 2026-07-12

Refs #8

## Context

CLAUDE.md chapter 3 ("Use Git Ecosystem Effectively") requires two checks on
every outward-facing artifact before it is pushed or posted:

> Audit every outward-facing artifact (commits, PR/issue bodies, releases,
> generated files) for provenance markers the owner has not chosen to
> disclose, such as build/runtime model or agent identifiers and internal
> tooling fingerprints, before any public push or release. This boundary
> belongs in a deterministic preflight, not reviewer memory, in the same
> class as the ASCII check; if no such gate enforces it yet, prepare one
> before relying on it. An undisclosed identifier is in scope by default.

> Keep GitHub posts ASCII.

gitapex has already hit the ASCII half of this in practice: PR #2 needed a
follow-up fix commit (`ef222b8`) after a first pass left non-ASCII characters
(em dashes, full-width punctuation) in a Mermaid diagram doc. No deterministic
preflight or CI gate exists yet for either check (see the Non-goals in
`docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`:
`evals/`, `scripts/check_skills.py`-style gates, and release automation are
all deferred). The CLAUDE.md bullet itself names the sanctioned interim:
"prepare one before relying on it" -- a skill, until a real gate lands.

## Scope

- One skill: `skills/outward-artifact-preflight/SKILL.md`.
- Checklist covers exactly the two CLAUDE.md chapter 3 checks: undisclosed
  provenance markers, and ASCII-only content.
- The skill body states explicitly, in its own text, that it is an interim
  measure pending a real deterministic preflight/CI gate, and does not
  substitute for one once it exists.
- A worked dry-run example (sample commit/PR text with one stray non-ASCII
  character and one undisclosed tooling fingerprint) demonstrating the
  checklist catches both, per the issue's acceptance criteria.
- A Stop/boundary section: never publish a flagged artifact without either
  fixing it or getting explicit owner sign-off to proceed anyway.

## Non-goals

- Building the actual deterministic preflight/CI gate (tracked separately,
  per the issue's "Out of scope" section and the linked design spec's
  Non-goals).
- An eval suite (3 fixtures: normal, stale/edge case, guardrail) -- explicitly
  deferred per the issue, same as `evals/` in the distribution-foundation
  spec's Non-goals.
- Any change to `scripts/`, `tests/`, or the plugin manifests -- this is a
  content-only addition, same shape as the `explaining-the-work` skill in
  PR #2.

## Architecture

Matches the existing `skills/explaining-the-work/` precedent: one skill
directory, one `SKILL.md`, no `references/` subdirectory (content fits well
within clairvoyance's informal 500-token `SKILL.md` budget).

```
skills/
  outward-artifact-preflight/
    SKILL.md
```

## Skill content: `outward-artifact-preflight`

Frontmatter:

```yaml
---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers and non-ASCII content, pending a real deterministic preflight/CI gate.
---
```

Body covers, in order:

1. **Why this exists / interim-measure notice** -- states plainly, in its
   own portable terms (no citation to this repository's `CLAUDE.md` or any
   specific chapter of it, so the rationale still holds if the skill is
   installed somewhere without a matching `CLAUDE.md`), that this skill is
   a stand-in for a deterministic gate this repository has not built yet,
   and stops being needed the day that gate lands.
2. **Checklist** -- two items, matching CLAUDE.md chapter 3's substance
   without depending on the document itself:
   - Undisclosed provenance markers: build/runtime model or agent
     identifiers, session URLs/IDs, internal tooling fingerprints not
     already covered by an agreed disclosure convention -- phrased
     conditionally ("if this repository already has..."), not anchored to
     gitapex's specific PR #2 trailer, so it reads correctly wherever the
     skill lands. This check is independent of the ASCII check below --
     PR #2's own trailer happens to contain a non-ASCII robot emoji (used
     in this spec's Context as the motivating example), so disclosure does
     not exempt a marker from also being ASCII.
   - ASCII-only: no em/en dashes, curly quotes, full-width punctuation, or
     other non-ASCII characters in the artifact text.
3. **Worked example** -- one flagged sample (non-ASCII em dash + an
   undisclosed model/session mention), built reproducibly with `printf` so
   the check actually catches real bytes when run, and its corrected form.
4. **Relationship to other skills** -- states explicitly that this skill and
   `explaining-the-work` are expected to both fire on the same commit/PR
   text (routing vs. safety-check are different jobs), rather than leaving
   that inferred.
5. **Stop boundary** -- never publish an artifact this checklist has flagged
   without fixing it first or getting the owner's explicit sign-off to
   proceed anyway; this skill does not authorize skipping the check, only
   applying it.

Trigger is scoped to "about to push, post, or publish" and could plausibly
read as overlapping `explaining-the-work`'s "finalizing commit/PR messages"
trigger in a router's eyes -- both fire at the same practical moment. Rather
than relying on the trigger text alone to prevent confusion, the skill body
states explicitly (see item 4 above) that both are meant to apply together:
`explaining-the-work` routes what the text should say, this skill checks
whether the text is safe to publish.

## Verification

No runtime code is added. Verification is manual/structural, same shape as
the distribution-foundation spec:

- `SKILL.md` frontmatter: `name: outward-artifact-preflight` (kebab-case,
  matches directory name), single-line third-person `description` with an
  explicit "Use when ..." trigger, no XML tags.
- Body stays well under the 500-token budget.
- Manual dry run (per issue acceptance criteria): given a sample commit
  message/PR body containing one stray non-ASCII character and one
  undisclosed tooling fingerprint, applying the checklist catches both.
- Interim-measure statement present in the body (not just implied).
- Stop section present.
- Self-contained: `SKILL.md` references no backtick-styled local path
  outside `skills/outward-artifact-preflight/` itself, and does not treat
  `CLAUDE.md` (or a specific chapter of it) as the required source of its
  own rationale. A skill can be installed on its own, so a reference to a
  repo doc under `docs/`, a sibling skill's file under `skills/other-skill/`,
  or this repository's specific `CLAUDE.md` would all leave the skill's
  own text unverifiable or unmotivated for anyone who installs it without
  the rest of gitapex. Naming a sibling skill defensively ("where
  installed, ...") is fine, since it does not require the sibling to
  exist for this skill to make sense on its own.

## Open items carried forward (not blocking this spec)

- The deterministic preflight/CI gate this skill stands in for remains
  unbuilt; a future issue should retire or narrow this skill once that gate
  exists.
- Sibling skill issues filed alongside #8 (#5, #6, #7, #9, #10, #11 per the
  issue's linked comments) are separate work, not bundled into this change.

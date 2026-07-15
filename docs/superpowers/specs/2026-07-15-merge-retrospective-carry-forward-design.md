# merge-retrospective: carry-forward check for unimplemented gates

Date: 2026-07-15

Refs #87. Extends `docs/superpowers/plans/2026-07-12-merge-retrospective-skill.md`
and the shipped `skills/merge-retrospective/SKILL.md` -- this doc does not
replace either, it specifies one additive step.

## Context

A Fable-assisted skill-gap analysis proposed a separate skill,
`retrospective-to-gate`, to close the loop between a retrospective's
*proposed* durable gate and that gate actually getting *built*. Naming
evaluation against `evaluating-skill-quality`'s Dimension 1 found this
would collide with `merge-retrospective` on the shared root word
"retrospective" -- the exact routing-ambiguity failure the rubric flags.
The operator chose integration over a second, colliding skill.

## Why this is not a Stop-boundary reversal

`skills/merge-retrospective/SKILL.md`'s existing Stop boundary reads:

> "Do not implement the durable gates proposed here in the same cycle --
> propose them in the issue body and stop; implementation is separate
> follow-on work each retrospective issue tracks on its own."

This is a deliberate invariant (per `evaluating-skill-quality`'s Contract
discipline: a Stop boundary "binds during mechanism-fit checking,
shape-checking, portability classification, and the dimension walk
alike" -- it is not a step-5-only rule to be reasoned around). The design
below satisfies it exactly:

- The new **Step 0** only *reads* prior retrospective issues and their
  linked follow-on PRs/commits (if any) -- it performs no write beyond
  authoring the current cycle's own new issue, which Step 4 already does.
- It never implements a gate itself. A carried-forward gate is reported
  as a subsection of the *current* cycle's issue, with the same
  "propose, don't implement" posture the existing Step 4 already applies
  to fresh findings.
- The escalation is visibility, not action: a gate that has rotted
  unimplemented across N cycles becomes *more visible* in the newest
  issue, which is exactly what makes it more likely a human or a future
  cycle actually schedules the implementation -- it does not schedule or
  perform that implementation itself.

A future `evaluating-skill-quality` review of the updated `SKILL.md`
should be able to verify this reasoning by reading this doc rather than
re-deriving it from scratch -- that is this doc's whole purpose.

## Mechanism: how "implemented" is checked

Today, `merge-retrospective` issues carry no label (confirmed: `grep
-n label skills/merge-retrospective/SKILL.md` returns nothing) and are
identified only by title pattern ("Merge retrospective: PR #N", e.g. #26,
#78). Relying on a title-string search indefinitely is fragile -- a
minimal, additive companion change to the *existing* Step 4 (filing the
issue) is needed alongside the new Step 0:

- **Step 4 addition (one line):** apply a `retrospective` label when
  filing the issue, so Step 0 has a reliable, non-text-matching anchor
  (`labels:["retrospective"]`, mirroring how `feat`/`fix`/`docs` issues
  already carry a template-assigned label). This is additive only -- no
  existing filed issue needs retroactive relabeling for Step 0 to start
  working going forward; Step 0 falls back to the existing title-pattern
  search for issues filed before the label existed.
- **Step 0 procedure:** `search_issues` for `label:retrospective
  state:open` (label-based, once available) or `"Merge retrospective:"
  in:title` (fallback for pre-label issues). For each hit, check whether
  its proposed gate was implemented: search for a merged PR or commit
  whose message cites that retrospective issue's number performing the
  proposed change (per this repo's own "cite the issue number in every
  commit" convention -- the citation trail already exists for exactly
  this kind of check, it is just not read back today).
- **Output:** a "Carried-forward gate" subsection per unimplemented item
  found, in the *current* cycle's new retrospective issue -- not a
  separate issue, not a comment on the old one (which would fragment the
  visibility this exists to create).

## Scope of this design pass

Per the operator's chosen execution scope: this design doc only. The
actual edit to `skills/merge-retrospective/SKILL.md` (adding Step 0 and
the Step 4 label line) is deferred to a following cycle.

## Non-goals

- Does not touch the existing Stop boundary's wording.
- Does not retroactively relabel issues #26 or #78.
- Does not build the "skill portability" gate #26 itself proposed -- that
  remains its own, separately-tracked follow-on; this change only makes
  the fact that it is still unimplemented more visible over time.

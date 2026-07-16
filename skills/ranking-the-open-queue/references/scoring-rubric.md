# Scoring Rubric

Four independent axes, each scored on its own three-point scale. Do not
blend them into a single number -- record the verdict and the reasoning
for each axis separately, then use the ordering rule at the end to rank.

## Severity

Does the item's own template, labels, or issue type indicate a defect,
versus an enhancement or chore?

Scale: **Defect** (a `bug`-style label, a `Bug`/`Fix`-style issue type, or
a body describing broken current behavior) / **Enhancement** (a new
capability, no broken behavior described) / **Chore** (maintenance,
cleanup, tooling -- no user-facing behavior change either way).

Worked example: an issue labeled `bug` titled "Crash on empty input,"
whose body includes a stack trace, scores **Defect**. A same-repo issue
labeled `enhancement` titled "Add dark mode" scores **Enhancement**.

## Staleness

Time since the item's *last human activity* -- a comment, a commit on its
branch, a review -- not time since it was created. An old issue with a
comment from yesterday is not stale; a two-day-old issue nobody has
touched since filing is more stale by this axis than its age suggests.

Scale: **Fresh** (last activity within roughly a week) / **Aging**
(last activity roughly one week to two months ago) / **Stale** (no human
activity in roughly two months or more). These bands are a starting
point, not a hard rule -- state the actual elapsed time in the output
Facts so the operator can re-judge the band themselves.

Worked example: an issue opened 220 days ago, with a maintainer comment
posted yesterday narrowing the reproduction steps, scores **Fresh** --
its creation date does not enter this axis at all.

## Blockage

Is the item waiting on something external to it -- an open dependency
issue, a pending decision from someone else, an upstream release -- that
makes acting on it right now wasted effort?

Scale: **Blocked** (a specific open blocker is named or linked) /
**Soft-blocked** (the body or comments hint at a dependency but name no
specific tracked blocker) / **Unblocked** (nothing found blocking it).

Worked example: an issue whose latest comment says "blocked on #99 (an
upstream API decision), which is still open" scores **Blocked**, citing
#99 as the named blocker.

## Actionability

Does the item carry enough information to start work now -- a concrete
scope, a reproduction, explicit acceptance criteria, or an Acceptance
Criteria Map -- or does it need a clarification pass first (see
`responding-to-a-fresh-arrival`) before anyone could productively start?

Scale: **Ready** (explicit acceptance criteria or a reproduction present)
/ **Needs scoping** (a real problem or request, but no concrete scope
stated) / **Needs clarification** (too little information to tell what is
even being asked for).

Worked example: an issue with a checklist of acceptance criteria and a
reproduction script scores **Ready**. A one-line issue reading only "Add
dark mode," with no further detail, scores **Needs scoping**.

## Ordering rule

Rank strictly in this order, top to bottom:

1. Any item scored **Blocked** sorts below every **Unblocked** or
   **Soft-blocked** item, regardless of its Severity -- acting on it now
   is wasted effort by definition of this axis.
2. Among the remaining items, **Defect** outranks **Enhancement**, which
   outranks **Chore**.
3. Within the same Severity tier, **Ready** outranks **Needs scoping**,
   which outranks **Needs clarification**.
4. Staleness only breaks ties that remain after rules 1-3 -- within the
   same Severity/Blockage/Actionability tier, **Stale** items sort above
   **Aging**, which sorts above **Fresh** (an old, ready, unblocked defect
   nobody has picked up yet is a stronger candidate than a fresh one).

This rule is deterministic given the four axis verdicts; the judgment
call is in assigning each verdict from the item's actual content, not in
the ordering itself.

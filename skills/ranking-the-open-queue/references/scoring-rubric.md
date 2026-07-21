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

Worked example: an issue whose latest comment says "blocked on an upstream
API decision, which is still open" and links the blocking issue scores
**Blocked**, since a specific open blocker is named.

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

Rank strictly in this order, top to bottom. Every level orders the *full*
three-point scale of its axis -- no two distinct verdicts on the same
axis are ever left unordered relative to each other:

1. **Blockage**, first: **Unblocked** outranks **Soft-blocked**, which
   outranks **Blocked**, regardless of Severity -- acting on a Blocked
   item now is wasted effort by definition of this axis, and a
   Soft-blocked item (a hinted but untracked dependency) is a lower-
   confidence candidate than a confirmed-Unblocked one.
2. Within the same Blockage tier, **Defect** outranks **Enhancement**,
   which outranks **Chore**.
3. Within the same Blockage/Severity tier, **Ready** outranks **Needs
   scoping**, which outranks **Needs clarification**.
4. Within the same Blockage/Severity/Actionability tier, **Stale**
   outranks **Aging**, which outranks **Fresh** (an old, ready, unblocked
   defect nobody has picked up yet is a stronger candidate than a fresh
   one).
5. **Final stable key.** Two items identical on all four axis verdicts
   (same Blockage, Severity, Actionability, and Staleness band) are still
   given a strict, reproducible order rather than left as an arbitrary or
   shared rank: sort by ascending issue/PR number. This key carries no
   priority meaning of its own -- it exists only so the same backlog
   produces the same order on a repeat sweep.

This rule is deterministic given the four axis verdicts plus the item
number; the judgment call is in assigning each axis verdict from the
item's actual content, not in the ordering itself.

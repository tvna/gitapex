---
name: merge-retrospective
description: Use when a pull request has just merged, before closing the turn -- enumerates every repair between PR open and merge, classifies each as a missing deterministic gate, an unclear agent instruction, or an external/human decision that cannot be automated, and files a retrospective issue proposing durable gates for the first category.
---

# Merge Retrospective

**Portability: Portable.** Self-contained procedure; depends only on a
connected GitHub MCP server for the issue-filing step.

A merged PR is not the end of the cycle. Before closing the turn, look
back at everything that had to be repaired between opening the PR and
merging it, and turn that history into a durable improvement instead of
letting it evaporate -- each cycle should leave the repository's harness
measurably better than the last.

This skill is self-contained: the taxonomy and procedure below do not
require the calling repository to have a CLAUDE.md, an AGENTS.md, or any
particular instruction file, and do not assume one has this exact
chapter/section structure. Where a repo does have its own instruction
file, point proposed gates and instruction fixes at that file (whatever
it is called) and follow its existing conventions (posting style,
issue/PR templates, etc.) -- this skill does not impose its own.

**Prerequisite:** Step 1 and Step 4 below assume a connected GitHub MCP
server (`mcp__github__*` tools). Where the environment lacks one, fall
back to the repo's own approved read-only REST API wrapper for Step 1's
history reconstruction, and to whatever write path the repo already uses
for filing issues in Step 4.

## Classification taxonomy (fixed -- never invent a fourth category)

Every repair gets exactly one of these three categories:

1. **Missing deterministic gate** -- a hook, CI check, lint rule, or
   script could have caught this before it ever reached review or CI.
   The fix is a gate proposal, not a one-off patch.
2. **Unclear agent instruction** -- the agent had ambiguous, missing, or
   contradictory guidance and made a call that a clearer instruction
   (the repo's own instruction file, if it has one, a skill, a PR
   template) would have prevented. No deterministic check could have
   caught this; a documentation/prompt fix could.
3. **External/human decision that cannot be automated** -- the repair
   required judgment only a human (or an external system outside this
   repo's control) could supply: a design tradeoff, an API the repo
   doesn't own changing shape, a reviewer's subjective call. Nothing to
   automate here; record it and move on.

If a repair seems to fit two categories, pick the earliest point in the
pipeline it could have been caught -- a gate that would have prevented it
before a human ever needed to weigh in outranks "unclear instruction,"
which in turn outranks "external decision."

## Procedure

1. **Enumerate every repair** between PR open and merge. Use
   `mcp__github__pull_request_read` (`get_commits`, `get_reviews`,
   `get_review_comments`, `get_check_runs`) to reconstruct the history.
   A repair is any of:
   - a CI run that failed and was fixed by a subsequent push
   - a review comment that led to a follow-up commit
   - a force-push made to correct a mistake (not just to rebase cleanly)
     -- these subcalls only reflect the PR's current commit set, not
     history that was rewritten away, so a force-push repair is only
     enumerable if you observed it directly (it happened during this
     session, or any session-observed merge event reported it). Do not
     claim a force-push repair occurred, or that none did, beyond what
     the available data actually shows.
2. **For each repair**, identify the earliest point in the pipeline a
   deterministic gate could have caught it -- before it ever reached a
   human reviewer or a CI run.
3. **Classify each repair** using the taxonomy above. State the
   classification explicitly; do not leave it implicit in prose.
4. **File the retrospective issue** via `mcp__github__issue_write`.
   - **Template and title take precedence over this skill's own
     defaults.** If the repo has an issue template (for example
     `.github/ISSUE_TEMPLATE/`, a root `ISSUE_TEMPLATE.md`, or a
     `.github/ISSUE_TEMPLATE/config.yml`-driven chooser) or its own
     title convention (a required prefix, a title-policy hook, a
     documented naming rule), fill that template and follow that title
     convention. The shape in the worked example below (including its
     `Title: Merge retrospective: PR #NN` line) is only a fallback for
     repos that have neither.
   - Otherwise, match whatever posting conventions the repository
     already enforces (for example, an ASCII-only body is common
     practice; check the repo's own instruction file or recent
     PR/issue history if unsure).
   - Content requirements below apply regardless of which shape the
     body ends up in: for every "missing deterministic gate" repair,
     propose a durable gate in the issue body -- proposing, not
     implementing, in this cycle (implementing gates is separate
     follow-on work). For "unclear agent instruction" and
     "external/human decision" repairs, record the classification and
     a one-line rationale; noting what instruction would have helped
     is useful context but not a required deliverable the way the gate
     proposal is.
5. **Cross-link**: reference the merged PR number in the retrospective
   issue body (e.g. "Refs #<merged PR number>").
6. **Verify the filed issue.** After `issue_write` returns, confirm the
   issue actually exists (re-fetch it), that its title passed any
   title-policy gate the repo enforces (no rejection or auto-edit), and
   that the PR cross-link from Step 5 resolves to the correct PR. A
   silent write failure or a title-policy rejection is not "filed."

## Stop boundary

- **Never skip filing the retrospective because the merge looked
  clean.** A zero-repair cycle is itself worth recording -- it is
  evidence the current process was sufficient for that cycle. File it
  with an empty repair list rather than skipping.
- Never invent a fourth taxonomy category, and never leave a repair
  unclassified.
- Do not implement the durable gates proposed here in the same cycle --
  propose them in the issue body and stop; implementation is separate
  follow-on work each retrospective issue tracks on its own.
- Do not collapse multiple repairs into one vague summary line -- each
  repair gets its own entry and its own classification, even if several
  share the same root cause.

## Worked example

Hypothetical merge history for a PR with two repairs:

- CI run #1 failed: `pytest` reported `ImportError: No module named foo`
  because a new test file referenced a helper that was never imported in
  `conftest.py`. The author pushed a follow-up commit adding the import,
  and CI run #2 passed.
- A human reviewer commented that the error message the new `--dry-run`
  flag prints on failure ("nothing happened") was confusing next to how
  every other flag in the same CLI phrases its errors ("dry-run: no
  changes applied, see below"). The author pushed a follow-up commit
  rewording the message to match.

Retrospective issue this produces, assuming the repo has no issue
template or title convention of its own (if it did, that template and
title convention would be filled with the same repair content instead):

```
Title: Merge retrospective: PR #42

## Summary

Retrospective for PR #42 ("feat: add foo routing"), merged 2026-07-12.
Two repairs occurred between PR open and merge.

## Repairs

1. [Failed CI rerun] `pytest` run #1 failed with
   `ImportError: No module named foo` -- a new test referenced a helper
   never imported in `conftest.py`. Fixed by a follow-up commit adding
   the import; CI run #2 passed.
   Classification: missing deterministic gate.
   Proposed gate: run the test suite (or at minimum `python -m py_compile`
   plus `pytest --collect-only`) in a pre-push hook, so import errors
   surface locally before CI.

2. [Review fix round] Reviewer flagged that the new `--dry-run` flag's
   failure message ("nothing happened") read as confusing next to how
   every other flag in the CLI phrases its errors. Fixed by a follow-up
   commit rewording the message to match the existing convention.
   Classification: unclear agent instruction -- whether a message reads
   as "confusing" next to a house style is a judgment call a lint rule
   cannot make; no gate could have caught this, but no written
   instruction told the agent the existing phrasing convention either.
   (Optional note: the CLI's error-message phrasing convention could be
   added to the repo's own instruction file, if it has one, so future
   agents learn it up front instead of from review -- not required, just
   useful context.)

## Notes

The proposed gate above is follow-on work, tracked separately if
pursued -- this issue only records the repairs and proposes it, per
merge-retrospective's Stop boundary.
```

For a zero-repair cycle, the issue body still gets filed, with the
Repairs section stating explicitly that no repairs occurred and that
this is being recorded as evidence the process worked for this cycle.

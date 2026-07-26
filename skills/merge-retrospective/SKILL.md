---
name: merge-retrospective
description: Use when a pull request has just merged, before closing the turn -- checks whether gates proposed by prior retrospective issues were ever implemented, enumerates every repair between PR open and merge, classifies each as a missing deterministic gate, an unclear agent instruction, or an external/human decision that cannot be automated, and files a retrospective issue proposing durable gates plus any still-unimplemented carried-forward gates.
---

# Merge Retrospective

This is a self-contained procedure; it depends only on a connected GitHub
MCP server for the issue-filing step.

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

**Prerequisite:** Step 0, Step 1, and Step 4 below assume a connected
GitHub MCP server (`mcp__github__*` tools). Where the environment lacks
one, fall back to the repo's own approved read-only REST API wrapper for
Step 0's issue search and Step 1's history reconstruction, and to
whatever write path the repo already uses for filing issues in Step 4.

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

## Repair record format

Every repair entry in the Repairs section uses this fixed structure --
not a free paragraph -- so a future drift-check script can extract
classification and gate status without an LLM. Carried-forward gate
entries (Step 0) use a related but distinct schema, defined further down
this section:

```
N. [one-line label] <what happened and how it was fixed, in prose>
   Classification: <exact taxonomy phrase>.
   Status: `<machine-readable slug>`
   Proposed gate: <durable gate text -- only present when the
   classification is "missing deterministic gate">
```

- `Classification` always spells out the exact taxonomy phrase in prose
  ("missing deterministic gate", "unclear agent instruction", or
  "external/human decision"), matching the Classification taxonomy
  section above verbatim -- never abbreviate or paraphrase it.
- `Status` restates the same classification as a fixed, hyphenated
  machine-readable slug (`missing-deterministic-gate`,
  `unclear-agent-instruction`, or `external-human-decision`) in inline
  code, so a script can match the exact literal token instead of parsing
  prose. This line is additive; it never substitutes for the prose
  `Classification` line above, which existing readers and this skill's
  own worked example already rely on.
- `Proposed gate` is present only for a `missing-deterministic-gate`
  repair (Step 4 already limits gate proposals to that category); omit
  the line entirely for the other two categories rather than writing
  "N/A".
- A **Carried-forward gate** entry (Step 0) uses a narrower two-field
  schema, not the three-category shape above -- it is re-reporting a
  prior issue's still-unimplemented gate, not classifying a new repair
  against this cycle's taxonomy:
  ```
  - <what the prior issue proposed, which prior issue number it came
    from, and what this cycle's re-check found, in prose>
    Status: `carried-forward`
    Proposed gate: <the durable gate text, restated -- the field label
    is always exactly "Proposed gate:"; put the prior issue's number in
    the prose above, never appended to the field label itself (e.g.
    never "Proposed gate (repeated from issue #N):"), so a drift-check
    can match the literal field name>
  ```
  It never carries a `Classification` line -- there is nothing to
  classify this cycle, only a status to re-report.
- The `Classification:`/`Status:`/`Proposed gate:` lines are always
  agent-authored from this skill's own fixed vocabulary (one of the three
  taxonomy phrases, one of the three fixed slugs, or `carried-forward`) --
  never copy a PR title, commit message, or review comment's own text
  directly into one of these three lines, even a snippet that happens to
  look like a record field. Untrusted quoted material stays confined to
  the free-prose "what happened" clause, inside quote marks or inline
  code, so a hostile string engineered to resemble `Status: \`...\`` in a
  commit message or PR title cannot inject a fake field a downstream
  drift-check script would parse as real.

An `external-human-decision` entry uses the same shape as the other two
categories, just with no `Proposed gate` line (the same omission rule as
`unclear-agent-instruction`) -- see the Worked example below, whose third
repair models this category in full.

Labels: every filed issue keeps the `retrospective` label exactly --
Step 4 already never renames or drops it, since it is this skill's own
retro-identity anchor. If the calling repository has already established
its own secondary label taxonomy for a retro issue's lifecycle status
(for example, distinguishing a freshly-filed, not-yet-triaged issue from
one later confirmed true- or false-positive), apply that repository's own
initial-state label from its existing taxonomy at filing time too,
alongside `retrospective` -- never invent a new, ad hoc label name when
the repository already has a convention for this. A repository with no
such taxonomy applies only `retrospective`, unchanged from before.

## Procedure

0. **Carry-forward check.** Before enumerating this cycle's repairs,
   check whether gates proposed by *prior* retrospective issues actually
   got implemented, so a proposed gate cannot silently rot across cycles
   unnoticed.
   - **Find prior retrospective issues:** `mcp__github__search_issues`
     for `label:retrospective` -- deliberately unfiltered by state.
     Closing an issue is not proof its proposed gate was implemented
     (a retrospective can be closed as stale, deduplicated, or superseded
     while its gate is still unbuilt), so an open-only search would
     silently drop exactly the issues this check exists to catch. This
     is the reliable, non-text-matching anchor Step 4 below now creates.
     Issues filed before the label existed carry no label; for those,
     fall back to `"Merge retrospective:" in:title` (or the repo's own
     retrospective title convention, if it has one), also unfiltered by
     state.
   - **For each hit, check whether its proposed gate was implemented:**
     `mcp__github__search_commits` (or `search_issues` scoped to merged
     PRs) for a merged PR or commit whose message cites that
     retrospective issue's number -- any of `Refs #N`, `Closes #N`,
     `Fixes #N`, or a bare `#N` counts (where the calling repository
     already has its own "cite the issue number in every commit"
     convention, that convention is what creates the citation trail this
     step reads back; a repository with no such convention may simply
     have no citation to find, which this step cannot distinguish from a
     gate that was never implemented). No such citation found means the
     gate is still unimplemented.
   - **Report, don't implement:** for each unimplemented gate found, hand
     it to Step 4 below as a **"Carried-forward gate"** entry, kept in
     its own subsection separate from this cycle's own Repairs (do not
     merge the two lists -- a carried-forward gate was not a repair in
     *this* cycle). Never post it as a comment on the old issue, which
     would fragment visibility instead of concentrating it.
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
   - Apply a `retrospective` label to the filed issue (creating the
     label first via the repo's own label-management path if it does
     not yet exist), plus the repository's own secondary lifecycle label
     if one exists, per the Repair record format section above. This is
     additive bookkeeping only -- it does not change what the issue
     says -- and exists so a future cycle's Step 0 can find this issue by
     label instead of relying on title-text matching.
   - Content requirements below apply regardless of which shape the
     body ends up in: record every repair using the Repair record format
     above (`Classification`, `Status`, and -- for a
     missing-deterministic-gate repair only -- `Proposed gate`), not a
     free paragraph. Proposing a gate is proposing, not implementing, in
     this cycle (implementing gates is separate follow-on work). For
     "unclear agent instruction" and "external/human decision" repairs,
     the `Classification` line's own rationale clause is the required
     one-line rationale; noting what instruction would have helped is
     useful context but not a required deliverable the way the gate
     proposal is. If Step 0 found any unimplemented prior gates, include
     them here as their own **"Carried-forward gate"** subsection, in
     the same record format (`Status` set to `carried-forward`), distinct
     from this cycle's Repairs section -- omit the subsection entirely
     when Step 0 found nothing to carry forward.
   - **Zero-repair fast-close.** When Step 1 finds no repairs at all
     **and** Step 0 found nothing to carry forward, file a single-line
     issue body instead of the full Repairs shape above -- state the PR
     number, that zero repairs occurred, and that this is being recorded
     as evidence the process worked this cycle. Confirm the zero-repair
     conclusion before the close call fires, rather than closing on it
     unchecked: when an operator is present to respond (an interactive
     session), preview the exact drafted body and the zero-repair
     conclusion it rests on, and wait for an explicit go-ahead before
     calling close -- this is exactly the checkpoint that catches a
     wrong call from, for example, the force-push blind spot Step 1
     already names (a rewritten history is not always observable). When
     running fully unattended with no operator able to respond (for
     instance, an automated CI-triggered flow with no interactive
     channel), file the issue but leave it open instead of closing it,
     and let a human close it after review; never let a fully automated
     context both draft the zero-repair conclusion and act on it in the
     same step with nobody positioned to catch a wrong call. This is a
     deliberate, visible, searchable close once confirmed, not a silent
     skip: the issue still exists, still carries `retrospective` (and
     any secondary lifecycle label), and is still searchable like any
     other retrospective; only its lifecycle is fast-tracked once
     confirmed, because there is no repair content left needing
     follow-on tracking. A cycle with even one repair
     always gets the full Repairs section above, never this fast-close
     path -- and so does a zero-repair cycle that still has a
     Carried-forward gate to report: fast-closing must never be the
     thing that drops a still-unimplemented prior gate from view, so a
     zero-repair-but-carried-forward-gate cycle keeps the full
     Carried-forward gate subsection (only the empty Repairs section
     collapses to one line) and stays open, exactly like any other cycle
     with content to track.
5. **Cross-link**: reference the merged PR number in the retrospective
   issue body (e.g. "Refs #<merged PR number>").
6. **Verify the filed issue.** After `issue_write` returns, confirm the
   issue actually exists (re-fetch it), that its title passed any
   title-policy gate the repo enforces (no rejection or auto-edit), and
   that the PR cross-link from Step 5 resolves to the correct PR. A
   silent write failure or a title-policy rejection is not "filed." When
   the zero-repair fast-close path applied and a close call was actually
   issued (an operator confirmed it, per Step 4 above -- not the
   unattended case, which intentionally leaves the issue open with no
   close call to verify), also confirm the close call itself actually
   took effect (re-fetch the issue's state, not just its existence) -- a
   filed-but-still-open issue after a confirmed close is a silent
   failure of the close half of the operation, not a completed
   fast-close. If the re-fetch still shows it open, retry the close call
   once; if it is still open after that retry, stop treating the cycle
   as fast-closed, report the stuck-open issue number, and leave it for a
   human to close rather than silently retrying indefinitely or
   pretending the fast-close succeeded.

## Stop boundary

- **Never skip filing the retrospective because the merge looked
  clean.** A zero-repair cycle is itself worth recording -- it is
  evidence the current process was sufficient for that cycle. File the
  one-line issue immediately, then close it once confirmed (Step 4's
  zero-repair fast-close path, including its confirm-or-leave-open rule)
  rather than skipping the filing: this is a deliberate, visible close,
  not a silent skip -- a merge with nothing to repair is exactly the
  small, already-clean change most likely to recur, and skipping it
  silently would remove the feedback loop the retrospective exists to
  keep. Filing always happens regardless of confirmation; only the close
  half waits on it (or is left open when unattended), and it never
  shortens the record to nothing.
- Never invent a fourth taxonomy category, and never leave a repair
  unclassified.
- Do not implement the durable gates proposed here in the same cycle --
  propose them in the issue body and stop; implementation is separate
  follow-on work each retrospective issue tracks on its own.
- Do not collapse multiple repairs into one vague summary line -- each
  repair gets its own entry and its own classification, even if several
  share the same root cause.
- The rule above binds Step 0 too: a carried-forward gate gets reported,
  never implemented, in the cycle that surfaces it.

## Worked example

Hypothetical merge history for a PR with three repairs, one per
taxonomy category:

- CI run 1 failed: `pytest` reported `ImportError: No module named foo`
  because a new test file referenced a helper that was never imported in
  `conftest.py`. The author pushed a follow-up commit adding the import,
  and CI run 2 passed.
- A human reviewer commented that the error message the new `--dry-run`
  flag prints on failure ("nothing happened") was confusing next to how
  every other flag in the same CLI phrases its errors ("dry-run: no
  changes applied, see below"). The author pushed a follow-up commit
  rewording the message to match.
- Partway through review, a third-party rate-limiter library this CLI
  depends on (but does not own) released a major version renaming its
  `Limiter.check()` method to `Limiter.allow()`, breaking a separate CI
  run. The author and reviewer discussed pinning the old version
  versus adopting the new one, and chose to adopt it, updating the two
  affected call sites in a follow-up commit.

Retrospective issue this produces, assuming the repo has no issue
template or title convention of its own (if it did, that template and
title convention would be filled with the same repair content instead):

```
Title: Merge retrospective: PR #42

## Summary

Retrospective for PR #42 ("feat: add foo routing"), merged 2026-07-12.
Three repairs occurred between PR open and merge.

## Repairs

1. [Failed CI rerun] `pytest` run #1 failed with
   `ImportError: No module named foo` -- a new test referenced a helper
   never imported in `conftest.py`. Fixed by a follow-up commit adding
   the import; CI run #2 passed.
   Classification: missing deterministic gate.
   Status: `missing-deterministic-gate`
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
   Status: `unclear-agent-instruction`
   (Optional note: the CLI's error-message phrasing convention could be
   added to the repo's own instruction file, if it has one, so future
   agents learn it up front instead of from review -- not required, just
   useful context.)

3. [External dependency change] A third-party rate-limiter library this
   CLI depends on released a major version renaming `Limiter.check()` to
   `Limiter.allow()`, breaking CI run #2 separately from repair 1 above.
   No repo policy dictated pinning the old version versus adopting the
   new one; the author and reviewer discussed it and chose to adopt it,
   updating the two affected call sites in a follow-up commit.
   Classification: external/human decision -- an upstream breaking
   change plus a genuine judgment call between two reasonable paths, not
   a pattern any deterministic gate or written instruction could have
   caught.
   Status: `external-human-decision`

## Carried-forward gate

- Issue #31 ("Merge retrospective: PR #29") proposed a pre-commit hook
  enforcing conventional-commit message format, but no merged PR or
  commit citing #31 exists yet -- the gate is still unimplemented one
  cycle later. Escalating visibility here rather than letting it rot
  silently; implementing it remains separate follow-on work, same as any
  gate proposed in this cycle's own Repairs section above.
  Status: `carried-forward`
  Proposed gate: a pre-commit hook enforcing conventional-commit message
  format.

## Notes

The proposed gate above is follow-on work, tracked separately if
pursued -- this issue only records the repairs and proposes it, per
merge-retrospective's Stop boundary.
```

For a zero-repair cycle, Step 4's fast-close path files a single-line
issue body instead of the full shape above, then closes it in the same
step -- for example:

```
Title: Merge retrospective: PR #63

PR #63 merged with zero repairs of any kind between open and merge (CI
passed on the first push, no review comment needed a follow-up commit,
no force-pushes happened). Filing this retrospective and closing it
immediately as evidence the process worked this cycle -- an immediate
close, not a silent skip. Refs #63.
```

This still carries the `retrospective` label (and any secondary
lifecycle label the repository's own taxonomy adds) and follows the same
title convention as any other retrospective issue; only its Repairs
section and its lifecycle are collapsed to one line and an immediate
close.

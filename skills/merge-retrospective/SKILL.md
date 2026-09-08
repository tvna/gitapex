---
name: merge-retrospective
description: Use when a pull request has just merged, before closing the turn -- enumerates every repair between PR open and merge, classifies each as a missing deterministic gate, an unclear agent instruction, or an external/human decision that cannot be automated, files each missing-deterministic-gate repair as its own standalone gate-proposal issue, and records the outcome in a retrospective issue before closing it.
compatibility: "Depends on a connected GitHub MCP server (mcp__github__* tools) for Steps 0, 2, 4b, 5, and 7; falls back to the repo's own REST API wrapper where absent (see Prerequisite)."
---

# Merge Retrospective

This is a self-contained procedure -- see Prerequisite below for its
GitHub MCP server and helper-script dependencies (also summarized in the
frontmatter `compatibility` field above).

A merged PR is not the end of the cycle -- look back at everything
repaired between open and merge, and turn that history into a durable
harness improvement instead of letting it evaporate.

This skill's taxonomy and procedure need no calling-repository
CLAUDE.md/AGENTS.md or matching chapter structure. Where one exists,
point proposed gates and instruction fixes at it and follow its own
conventions (posting style, issue/PR templates) rather than this
skill's generic defaults.

**Prerequisite:** Steps 0, 2, 4b, 5, and 7 below assume a connected
GitHub MCP server (`mcp__github__*` tools). Where the environment lacks
one, fall back to the repo's own approved read-only REST API wrapper for
Step 0's dedup search, Step 2's history reconstruction, and Step 4b/7's
own reads, and to whatever write path the repo already uses for filing
issues in Step 5.
See `gitapex_file_gate_proposal.py` for what Step 5's own bundled helper
needs: local shell access only (`uv run` or equivalent) and no network
calls of its own -- every actual GitHub write in this skill stays a
direct `mcp__github__*` tool call, so the repository's existing
issue-filing safety hook keeps seeing it.

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
classification, gate status, and filed-issue number without an LLM:

```
N. [one-line label] <what happened and how it was fixed, in prose>
   Classification: <exact taxonomy phrase>.
   Status: `<machine-readable slug>`
   Proposed gate: <durable gate text -- only for "missing deterministic gate">
   Filed as: #<issue number> -- present once Step 5 confirms the filed issue exists
   Recurrence note: <only present when repairs share a recurring thesis>
```

`Classification` always spells out the exact taxonomy phrase in prose
("missing deterministic gate", "unclear agent instruction", or
"external/human decision"), matching the Classification taxonomy section
above verbatim -- never abbreviate or paraphrase it. See
`references/repair-record-format.md` for the rest of the field-by-field
rules (injection containment for untrusted quoted text, each field's own
omission rule, and label handling). An `external-human-decision` entry
uses the same shape as the other two categories, just with no
`Proposed gate` or `Filed as:` line -- see `references/worked-example.md`,
whose third repair models this category in full. A repair entry's own
prose stating a durable claim about this repository's own code (a
count, "every", "the only cause") follows `grounding-in-primary-sources`'s
discipline -- ground it in the actual code before writing it.

## Procedure

0. **Dedup check.** Before doing any of the (expensive) work in Steps 1-4
   below, search for an existing retrospective issue for this PR, so a prior
   run's completed work is never redone or duplicated.
   - **Dedup against an existing CI-opened stub first.** Some repositories run
     an automated opener (e.g. this repository's own
     `.github/scripts/gitapex_post_merge_retro.py`, triggered on PR merge) that
     files a bare stub retrospective issue before this skill runs, so an
     unattended merge still gets a placeholder. Skipping this check against a
     PR with such a stub produces a duplicate -- the stub and this skill's own
     filing, both labeled `retrospective` but never reconciled. Before creating
     anything, search using the same title/label identity predicate the opener
     itself uses (where the repository has its own convention -- e.g. this
     repository's `_retro_title`/`dedup_query`, producing
     `chore(retrospective): merge retrospective for PR #N`): fetch candidates
     via `mcp__github__list_issues(labels: ["retrospective"])`, an exact
     deterministic label filter, never `mcp__github__search_issues`'s
     natural-language matching (Step 1 also calls `search_issues`, for a
     different task -- not license to widen this step's tool choice). Page
     through every result (`pageInfo.endCursor` via `after`) before concluding
     "no match" -- the same fail-closed pagination discipline as
     `hooks/gitapex_check_pr_duplicate_issue.py`. Then compare titles with
     **exact string equality**, never substring containment: a shorter PR
     number's title is a literal prefix of a longer one sharing the same
     leading digits, so substring matching could mistake the longer number's
     issue for the shorter number's own. A repository with neither an opener
     nor its own convention has nothing to dedup against, so this check is a
     no-op.
     - **Match found, body still carries the opener's own stub marker text**
       (`"Automated stub opened by the post-merge-auto-retro gate"` --
       unenriched) -> fill the stub, don't open a second issue. Continue into
       Step 1; when Step 5 files, call `issue_write` method `update` on that
       issue number instead of `create`, replacing the stub body with Step 5's
       full Repairs content, and add the repository's secondary lifecycle label
       (if any) alongside `retrospective`. Cross-linking (Step 6) and
       verification (Step 7) still apply to the updated issue.
     - **Match found, body no longer carries the marker** -> a prior run (this
       skill, an earlier pass, or a human) already enriched this PR's
       retrospective. Do not overwrite real content and do not create a
       duplicate. One case still has work left: if that enriched body records a
       `missing-deterministic-gate` repair that carries no `Filed as:` line, a
       prior run's filing never finished -- resume at Step 5's filing bullets
       for exactly those repairs (per Step 5's own resumed-run rule), skipping
       Steps 1-4 entirely, skipping every repair that already carries a
       `Filed as:` line, and leaving the rest of the existing body untouched.
       Otherwise nothing is left to file -- stop here, before Step 2's repair
       enumeration ever runs.
     - **No match** -> nothing to dedup against; continue into Step 1 below,
       and when Step 5 files, proceed to `create` per its remaining bullets,
       same as a repository with no stub-opening CI script at all.
       Residual risk: two fully concurrent runs can both observe "No
       match" and each create their own retrospective issue -- GitHub's
       issue-creation endpoint has no atomic create-if-absent primitive.
       Same race class 4b.3 discloses for a DUPLICATE-OF gate-proposal
       filing; unlike that path, a duplicate retrospective issue has no
       dedicated close-as-duplicate step, so a human noticing two issues
       for one PR is this residual's own backstop.
1. **Nothing to sweep.** A routine cycle has no carry-forward check to run
   here: every `missing-deterministic-gate` finding is filed as its own
   standalone issue the moment Step 5 classifies and confirms it, so there
   is no separate backlog of prior proposals to re-verify in this step.
   The pre-existing legacy backlog of unresolved gate proposals from
   before this mechanism existed stays explicitly out of scope for this
   step -- a future manual audit of it, should one ever be undertaken, is
   separate follow-on work, not something this step performs. Do not read
   `.gitapex/ssot.json` or run any gate-resolution script here; continue
   straight to Step 2.
2. **Enumerate every repair** between PR open and merge, in the order
   found, giving each one its own 1-based index -- the same `N.` prefix
   the Repair record format above already uses. Hold this index in memory
   for the rest of the cycle; nothing about it is written anywhere until
   Step 5. Use `mcp__github__pull_request_read` (`get_commits`,
   `get_reviews`, `get_review_comments`, `get_check_runs`) to reconstruct
   the history. A subcall that errors, times out, or returns a visibly
   truncated result is not a clean read -- retry once; a second failure
   blocks Step 5's zero-repair fast-close (never silently read as "no
   repairs found") and gets reported instead. A repair is any of:
   - a CI run that failed and was fixed by a subsequent push
   - a review comment that led to a follow-up commit
   - a force-push made to correct a mistake (not just to rebase cleanly)
     -- these subcalls only reflect the PR's current commit set, not
     history that was rewritten away, so a force-push repair is only
     enumerable if you observed it directly (it happened during this
     session, or any session-observed merge event reported it). Do not
     claim a force-push repair occurred, or that none did, beyond what
     the available data actually shows.
3. **For each repair**, identify the earliest point in the pipeline a
   deterministic gate could have caught it -- before it ever reached a
   human reviewer or a CI run.
4. **Classify each repair** using the taxonomy above. State the
   classification explicitly; do not leave it implicit in prose. A
   `missing-deterministic-gate` repair keeps its Step 2 index ready for
   Step 5's filed-issue title below -- still nothing written yet. Also
   check for recurrence (see above) for Step 5's `Recurrence note:`.
4b. **Backlog-grounded proposal review.** Establish a review verdict for
    every `missing-deterministic-gate` repair from this cycle -- from one
    batched dispatch covering the whole cycle, not one dispatch per
    repair (the batch shape is what lets that dispatch's own CLUSTER
    output group repairs against each other in the first place) --
    before Step 5 files anything; Step 5 is sequence-gated on it.
    See `references/backlog-grounded-proposal-review.md` for sweep,
    verdicts, and per-verdict filing actions.
5. **File (or update) the retrospective issue** via
   `mcp__github__issue_write`, using the create-vs-update decision Step 0
   above already made -- this rewrite changes only what that one write
   contains, never which of Step 0's two branches applies. Sequence
   gate: no `missing-deterministic-gate` repair is filed here without
   its Step 4b verdict on record. This filing step runs with no
   per-write human preview of its own, unlike the closing step below
   (which does gate attended/unattended) -- deliberately, because each
   of this step's two write kinds already has its own deterministic
   backing, not a human preview, standing between it and a duplicate or
   ungrounded write: the retrospective issue's own create-vs-update
   choice is Step 0's own re-verified dedup search above, and every
   `missing-deterministic-gate` repair's own standalone gate-proposal
   issue is separately gated by the `Dedup-sweep:` PreToolUse hook
   (`hooks/gitapex_check_gate_proposal_dedup_sweep.py`), which denies
   any `gate-proposal` creation whose body carries no fresh,
   live-verified backlog-sweep count.
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
     if one exists, per the Repair record format section above. A
     `missing-deterministic-gate` repair's own standalone filed issue
     below carries a different, independent label, `gate-proposal`
     (never `retrospective`) -- the two label vocabularies never mix.
     Create `gate-proposal` first via that same label-management path
     when it does not yet exist, for the same reason `retrospective` is
     created first rather than assumed: a filing that lands without its
     label is invisible to every later search and audit keyed on it.
   - **Repair list, up front.** Open the body with every repair found in
     Step 2, index and one-line label only, in index order (e.g.
     `1. Failed CI rerun`), before the full record entries. Then record
     each repair in full using the Repair record format above
     (`Classification`, `Status`, and -- missing-deterministic-gate only
     -- `Proposed gate`, plus `Recurrence note` where it applies). For
     `unclear-agent-instruction` and `external-human-decision` repairs,
     the `Classification` line's own rationale clause is the required
     one-line rationale; noting what instruction would have helped is
     useful context, not a required deliverable. Neither category gets
     a standalone issue or a script call -- they stay recorded inline
     exactly as here, unchanged.
    - **File each `missing-deterministic-gate` repair as its own
      standalone issue**, via
      `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
      plus a direct `mcp__github__*` exact-title search/create-or-match
      flow, then record `Filed as: #<issue number>` alongside that
      repair's own `Status:` line -- see
      `references/gate-proposal-filing-mechanics.md` for the full
      mechanics (the script call, the no-match/one-match/more-than-one-
      match branches, and the re-fetch-before-write discipline), the
      failed-or-unconfirmed-filing resume rule, and the close condition.
   - **Zero-repair fast-close.** When Step 2 finds no repairs at all,
     file a single-paragraph issue body instead of the full shape above
     -- see `references/zero-repair-fast-close.md` for the exact body --
     then apply the same attended/unattended close rule
     `references/gate-proposal-filing-mechanics.md` states.
6. **Cross-link**: reference the merged PR number in the retrospective
   issue body (e.g. "Refs #<merged PR number>").
7. **Verify the filed issue.** After `issue_write` returns, confirm the
   issue actually exists (re-fetch it), that its title passed any
   title-policy gate the repo enforces (no rejection or auto-edit), and
   that the PR cross-link from Step 6 resolves to the correct PR. A
   silent write failure or a title-policy rejection is not "filed." When
   a close call was actually issued -- either close path, per Step 5's
   unified attended/unattended rule; only the attended case issues one,
   the unattended case leaves the issue open with nothing to verify --
   confirm the close itself took effect (re-fetch state, not just
   existence): a filed-but-still-open issue after a confirmed close is a
   silent close failure, not a completed one. If still open, retry the
   close once; if still open after that, stop treating the cycle as
   closed, report the stuck-open issue number, and leave it for a human
   rather than retrying indefinitely or pretending it succeeded.

## Stop boundary

- **Never skip filing the retrospective because the merge looked
  clean.** A zero-repair cycle is itself worth recording -- it is
  evidence the current process was sufficient for that cycle. File the
  one-line issue immediately, then close it once confirmed (Step 5's
  zero-repair fast-close path, including its confirm-or-leave-open rule)
  rather than skipping the filing: this is a deliberate, visible close,
  not a silent skip -- a merge with nothing to repair is exactly the
  small, already-clean change most likely to recur, and skipping it
  silently would remove the feedback loop the retrospective exists to
  keep. Filing always happens regardless of confirmation; only the close
  half waits on it (or is left open when unattended), and it never
  shortens the record to nothing.
- Never invent a fourth taxonomy category, and never leave a repair
  unclassified. A `Recurrence note` is additive only, never a fourth
  category or a substitute for `Classification`/`Status`.
- Do not implement the durable gates proposed here in the same cycle --
  propose them (inline in the retrospective issue body, and in each
  missing-deterministic-gate repair's own standalone filed issue) and
  stop; implementation is separate follow-on work each filed issue
  tracks on its own.
- Do not collapse multiple repairs into one vague summary line -- each
  repair gets its own entry, even sharing a root cause (a recurrence
  note surfaces that, never merged entries).
- The rule above extends to Step 5's own standalone filings: filing a
  gate-proposal issue is proposing, never implementing, in the cycle
  that files it.

## Worked example

See `references/worked-example.md` for a full three-repair cycle, one
repair per taxonomy category, and the retrospective issue body it
produces.

For a zero-repair cycle, Step 5's fast-close path files a single-
paragraph issue body instead of the full shape above, then closes it
once confirmed -- see `references/zero-repair-fast-close.md` for the
exact body. It still carries the `retrospective` label (and any
secondary lifecycle label) with the same title convention; only its
Repairs section and lifecycle collapse to one line and one close call.

## Notes

Install/vendoring-time integrity (whether this SKILL.md, its bundled
`scripts/gitapex_file_gate_proposal.py`, and `references/*.md` are the
untampered, intended copies) is separate from the runtime content trust
`references/repair-record-format.md`'s injection-containment rules
cover -- a shape-checker PASS says nothing about it. Verify it through
the calling repository's own vendoring/install process.

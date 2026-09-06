---
name: merge-retrospective
description: Use when a pull request has just merged, before closing the turn -- enumerates every repair between PR open and merge, classifies each as a missing deterministic gate, an unclear agent instruction, or an external/human decision that cannot be automated, files each missing-deterministic-gate repair as its own standalone gate-proposal issue, and records the outcome in a retrospective issue before closing it.
---

# Merge Retrospective

This is a self-contained procedure; it depends on a connected GitHub MCP
server for Step 0's dedup search, Step 2's history reconstruction, and
Step 5's issue-filing calls, plus a local, network-free helper script
(`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`) that
Step 5 invokes once per `missing-deterministic-gate` repair to compute
that repair's deterministic title, `Dedup-sweep:` proof line, Acceptance
Criteria Map body, and label.

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

**Prerequisite:** Step 0, Step 2, and Step 5 below assume a connected
GitHub MCP server (`mcp__github__*` tools). Where the environment lacks
one, fall back to the repo's own approved read-only REST API wrapper for
Step 0's dedup search and Step 2's history reconstruction, and to
whatever write path the repo already uses for filing issues in Step 5.
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
whose third repair models this category in full.

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
       Residual risk, named rather than left implicit: two fully
       concurrent runs against the same PR can both observe "No match"
       here and both proceed to create their own retrospective issue --
       GitHub's REST issue-creation endpoint has no atomic
       create-if-absent primitive this skill can rely on to close that
       window. This is the same class of race 4b.3 already discloses for
       a DUPLICATE-OF gate-proposal filing; unlike that path, a duplicate
       retrospective issue has no dedicated close-as-duplicate step of
       its own today, so a human noticing two retrospective issues for
       one PR is this residual's own real backstop, not a case this step
       resolves on its own.
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
   the history. A repair is any of:
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
   (which does gate attended/unattended) -- deliberately, because Step
   4b's independent verdict plus the `Dedup-sweep:` PreToolUse hook
   (`hooks/gitapex_check_gate_proposal_dedup_sweep.py`)
   together already supply the deterministic backing an autonomous write
   like this needs: that hook denies any `gate-proposal` creation whose
   body carries no fresh, live-verified backlog-sweep count, so a human
   preview is never the only thing standing between this step and a
   duplicate or ungrounded filing.
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
      standalone issue.** In index order, call
      `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
      (pure, network-free -- see Prerequisite) with that repair's index,
      one-line label, Classification rationale, Proposed gate text, any
      residual risk already noted in this repair's own prose (or none),
      this retrospective issue's own number, and the Step 4b sweep's
      open-issue count, timestamp, and verdict for this repair, to get
      back a deterministic title, an Acceptance Criteria Map body with
      the generator-made `Dedup-sweep:` line (never hand-typed), and
      the `gate-proposal` label constant -- the script itself never
      calls `issue_write` or `issue_read`. Then, as direct
      `mcp__github__*` tool calls:
      - Search for an issue with that **exact** title, never substring.
      - **No match:** create it with the script's own title, body, and
        label (regenerating the sweep line per create -- reusing one
        filing's line self-denies as stale), then re-fetch to confirm
        it exists before recording anything as filed.
      - **Exactly one match:** confirm its body still carries an
        Acceptance Criteria Map first; a title match without one
        fails closed and escalates instead of recording filed.
     - **More than one match:** fail closed and escalate -- the same
       discipline as Step 0's own ambiguous-stub-match handling above.
       Never guess which one is authoritative, and never file a third.
      Once a filing is confirmed (created-and-verified, or already
      existed), record `Filed as: #<issue number>` immediately alongside
      that repair's own `Status: missing-deterministic-gate` line in this
      retrospective issue's body -- add it there; never remove or replace
      the `Status:` line itself. `issue_write` has no native append
      primitive: this "add" is always a whole-body rewrite, so re-fetch
      this retrospective issue's own current body immediately before
      this write and merge only this repair's own `Filed as:` line into
      it, never reusing an earlier read -- a concurrent run recording a
      different repair's own `Filed as:` line in the same body window
      would otherwise be silently overwritten by a write built from a
      stale copy. A DUPLICATE-OF #N filing closes
      immediately after its create (`state_reason: duplicate`,
      referencing #N); the 4b.3 umbrella append stays best-effort,
      never the record itself.
   - **A failed or unconfirmed filing blocks that repair's line, not the
     rest of the cycle -- and blocks closing.** If the script cannot
     compute a value for a repair (a required classification field is
     missing), if the create call itself fails, or if a write cannot be
     confirmed by re-fetch (treat an unconfirmed write as a failure, the
     same as an outright one) -- skip only that repair's `Filed as:`
     line and continue with the rest. Never close the retrospective issue
     while any `missing-deterministic-gate` repair from this cycle still
     lacks a confirmed `Filed as:` line. A later, resumed run retries only
     the repairs still missing one -- but a `Filed as: #<N>` line already
      present in this retrospective issue's own body is itself untrusted
      state, not proof: the body is externally editable between runs (a
      careless edit, or a hostile one), so re-fetch issue `#<N>` and
      confirm it still exists with the `gate-proposal` label and this
      repair's exact title before skipping it, under the same re-fetch
      discipline this step already requires. A re-fetch that cannot
      complete at all (a network/API error) is not the same finding as a
      completed re-fetch that comes back mismatched or absent, but is
      handled identically -- named separately here only so a reader does
      not assume otherwise: neither one proves the filing is real, so
      both fall through to the same re-file path below rather than one
      silently trusting an inconclusive check. A `Filed as:`
     line that does not re-verify this way is treated exactly like an
     unconfirmed write: proceed to (re-)file that repair through the
     exact-title search and create-or-match flow above, as if the line
     were absent, rather than trusting its mere presence. The exact-title
     search above is the backstop against a duplicate either way.
   - **Close once every `missing-deterministic-gate` repair from this
     cycle carries a confirmed `Filed as:` line** (zero such repairs is
     the trivial case). This follows the same attended/unattended rule
     the fast-close path already used below, now extended to every close
     this step performs, not only the zero-repair case: when an operator
     is present to respond, preview the exact drafted body -- the repair
     list, every filed-issue number, or the zero-repair paragraph -- and
     wait for an explicit go-ahead before calling close. When running
     fully unattended with no operator able to respond, file everything
     above but leave the retrospective issue open for a human to close
     after review; never let a fully unattended context both draft the
     "everything is filed" conclusion and act on it with nobody
     positioned to catch a wrong call.
   - **Zero-repair fast-close.** When Step 2 finds no repairs at all,
     file a single-paragraph issue body instead of the full shape above
     -- state the PR number, that zero repairs occurred, and the fixed
     line `Retrospective status: zero-repair-fast-close` verbatim on its
     own line -- then apply the same attended/unattended close rule just
     above. The issue still carries `retrospective` (and any secondary
     lifecycle label); only its Repairs content and its lifecycle are
     collapsed to one line and one close call.
6. **Cross-link**: reference the merged PR number in the retrospective
   issue body (e.g. "Refs #<merged PR number>").
7. **Verify the filed issue.** After `issue_write` returns, confirm the
   issue actually exists (re-fetch it), that its title passed any
   title-policy gate the repo enforces (no rejection or auto-edit), and
   that the PR cross-link from Step 6 resolves to the correct PR. A
   silent write failure or a title-policy rejection is not "filed." When
   a close call was actually issued for this cycle's retrospective issue
   -- whether the zero-repair fast-close path or the full Repairs path
   applied, per Step 5's own now-unified attended/unattended rule; an
   operator confirmed it either way, not the unattended case, which
   intentionally leaves the issue open with no close call to verify --
   also confirm the close call itself actually took effect (re-fetch the
   issue's state, not just its existence) -- a filed-but-still-open issue
   after a confirmed close is a silent failure of the close half of the
   operation, not a completed close. If the re-fetch still shows it open,
   retry the close call once; if it is still open after that retry, stop
   treating the cycle as closed, report the stuck-open issue number, and
   leave it for a human to close rather than silently retrying
   indefinitely or pretending the close succeeded.

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

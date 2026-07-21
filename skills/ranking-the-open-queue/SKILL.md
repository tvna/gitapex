---
name: ranking-the-open-queue
description: Sweep the backlog of already-known open issues/PRs and hand the operator a decision-ready ranked queue -- scored on severity, staleness, blockage, and actionability -- when deciding what to act on first across many items, not a single already-selected one. Read-only -- never labels, comments, or otherwise mutates an issue or PR; see `responding-to-a-fresh-arrival` for a single newly-arrived item's initial response, and `screening-a-low-trust-contribution` for diff-level threat screening of an unknown author's contribution, instead.
---

# Ranking the Open Queue

This skill depends only on a connected GitHub MCP server
(`list_issues`/`search_issues`, general product capabilities), addressed
via the portable `Server:tool` shorthand documented below -- no
this-repository tooling. The scoring axes (references/scoring-rubric.md)
are repo-agnostic criteria, not this repository's own convention.

Every existing single-item skill in this cluster (`issue-to-branch`,
`responding-to-a-fresh-arrival`, `screening-a-low-trust-contribution`)
assumes the operator has already picked which issue or PR to act on. This
skill is what runs before that pick: a periodic sweep across a whole
backlog that answers "of these N open items, which should I even look at,
and in what order."

Tool names below are written as `Server:tool` (portable shorthand, not
tied to one agent platform). In Claude Code, translate to the literal
double-underscore form: `Server:tool` -> `mcp__Server__tool` -- e.g.
`github:search_issues` is `mcp__github__search_issues`.

## Procedure

1. **Resolve scope.** Confirm the repository (and any operator-named
   filters -- a label, a milestone, a specific author) before sweeping.
   Default to open issues and open PRs across the whole repository when
   the operator states no filter.
2. **Sweep, paginated.** Use `Server:list_issues` for broad retrieval and
   `Server:search_issues` for targeted criteria (a label combination, an
   activity cutoff, an author), per the GitHub MCP server's own tool
   guidance -- list_* for broad simple retrieval, search_* for targeted
   queries. Page in batches of 5-10 items.
3. **Extract per item.** Pull only what the four scoring axes need: its
   labels and issue type, the timestamp of its last human activity (a
   comment, commit, or review -- not its creation time), any linked or
   referenced blocking issue, and whether its body carries a concrete
   scope (an Acceptance Criteria Map, a reproduction, explicit acceptance
   criteria) or not.
4. **Score, per axis.** Apply the four axes in
   [references/scoring-rubric.md](references/scoring-rubric.md) --
   Severity, Staleness, Blockage, Actionability -- to every item
   independently. Record the reasoning behind each axis's verdict
   alongside its label.
5. **Rank and output** as the table contract below, applying
   [references/scoring-rubric.md](references/scoring-rubric.md)'s
   ordering rule to break ties between items, down to its final stable
   key (issue/PR number) for items still tied after every axis. Before
   presenting the table, re-check the assembled order against that rule
   directly -- its levels are exact enough to verify mechanically --
   rather than trusting a first-pass sort; a multi-key tie-break across
   many items is exactly where a first pass tends to drift.
6. **State any cap.** If pagination stops before the full backlog is
   swept (a rate limit, an operator-given item cap), say so explicitly in
   the output.

## Output

Exactly one Markdown table, per this repository's own force-multiplier
convention (a visualization a human can inspect for anomalies, not a
paragraph to read through):

| Rank | Item | Severity | Staleness | Blockage | Actionability | Recommended next step |
|---|---|---|---|---|---|---|

Worked example row, from the scoring-rubric.md worked examples: an issue
scored Defect / Stale (no activity in 95 days) / Unblocked / Ready
outranks a similarly-scored but Fresh item per the ordering rule's
tie-break (Staleness only breaks ties after Blockage and Severity/
Actionability already tie):

| 1 | `#101` "Fix crash on empty input" | Defect | Stale (95d) | Unblocked | Ready | Start now -- reproduction and acceptance criteria already present. |

Followed by:

- **Scope swept:** the repository, filters applied, and item count (with
  any cap from Procedure step 6 stated explicitly).
- **Facts:** the per-item signals Step 3 actually found (label, last
  activity date, blocking reference, scope signal), cited to source.
- **Assumptions:** anything inferred where a signal was missing or
  ambiguous, never silently treated as a fact.

A "Recommended next step" cell may point at another skill (for example,
`responding-to-a-fresh-arrival` for an item that scores low on
Actionability and needs a clarification pass) -- this skill only
recommends; it never invokes or hands off execution itself.

## Stop boundaries

- Never label, comment on, close, assign, or otherwise write to any issue
  or PR swept by this skill -- read-only sweep and report only. A request
  to also act on the ranked items (label them, close them, comment on
  them) gets a table plus an explicit statement that doing so is outside
  this skill's read-only scope, not silent compliance.
- Never shell out to a command-line GitHub tool (e.g. `gh`) for the
  sweep -- `Server:list_issues`/`Server:search_issues` only (Procedure
  step 2).
- Never present a partial sweep as complete, or a first-pass sort as
  final, without the explicit checks Procedure steps 5-6 already call
  for -- a smaller, honestly labeled, order-verified table beats a
  larger or better-looking one that skipped either check.
- Never fabricate a scoring signal. A missing last-activity timestamp,
  unclear blocking reference, or absent scope signal is stated as missing
  in Assumptions, never silently inferred so the table looks complete.

## Notes

This skill's `description:` disambiguation clause is copied verbatim
from a shared cross-skill design spec, not authored fresh here -- kept
consistent with its two not-yet-built siblings
(`responding-to-a-fresh-arrival`, `screening-a-low-trust-contribution`)
so all three read the same canonical wording once each lands, rather than
drifting from independently-worded clauses.

No bundled script ships with this skill. Scoring is a judgment call
across four qualitative axes applied to free-text issue/PR content, not a
deterministic rule a script could apply consistently -- revisit only if a
future review finds scoring drift across repeated runs on the same
backlog.

The ordering rule itself (scoring-rubric.md's tie-break, applied once
axis verdicts are assigned) is separately deterministic and a plausible
future bundled-script candidate on a large backlog. Left unscripted for
now -- Procedure step 5's explicit re-check covers it at the sweep sizes
this skill is used at today -- but this is not the same "unscriptable
judgment call" rationale as the axis-scoring decision above; revisit if a
review finds the manual re-check itself drifting on a large sweep.

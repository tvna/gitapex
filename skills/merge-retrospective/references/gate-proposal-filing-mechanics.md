# Gate-Proposal Filing Mechanics

Step 5's own detail for recording each `missing-deterministic-gate`
repair on its family issue, per the Step 4b.3 verdict, plus the
failure/resume and close-condition rules that govern it.

## Contents

- [Building every title and body](#building-every-title-and-body)
- [Creating a family issue](#creating-a-family-issue)
- [Recording a recurrence](#recording-a-recurrence)
- [Recording the result in the retrospective body](#recording-the-result-in-the-retrospective-body)
- [A failed or unconfirmed filing blocks that repair's line, not the rest of the cycle -- and blocks closing](#a-failed-or-unconfirmed-filing-blocks-that-repairs-line-not-the-rest-of-the-cycle----and-blocks-closing)
- [Close condition](#close-condition)

## Building every title and body

`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py` is
pure and network-free (see Prerequisite): it computes strings and never
calls `issue_write` or `issue_read`. Each repair supplies its own
`FamilyRow`: one-line label, Classification rationale, Proposed gate
text, and any residual risk already noted in its prose (or none).

- **A new family issue** (NEW, or a verified CLUSTER of NEW members):
  `build_gate_proposal_title` with this retrospective's number and the
  lowest member index; `build_gate_proposal_family_acm_body` with every
  member's row, in index order, plus the Step 4b sweep's open-issue
  count and timestamp. The body ends with the generator-made
  `Dedup-sweep: ...; verdict NEW` line (never hand-typed), and the label
  is `GATE_PROPOSAL_LABEL`.
- **A mechanism's family issue** (ABSORBED-BY with no open issue yet):
  the same body builder, titled by `build_absorption_family_title`.
- **A duplicate record** (DUPLICATE-OF #N, or ABSORBED-BY onto an
  existing mechanism issue #N): the new-family-issue title and body
  builders again, with `dedup_sweep_verdict="DUPLICATE-OF #N"`, so the
  body ends with `Dedup-sweep: ...; verdict DUPLICATE-OF #N`.

## Creating a family issue

As direct `mcp__github__*` tool calls:

- Search for an issue with that **exact** title, never substring.
- **No match:** create it with the script's own title, body, and
  label (regenerating the sweep line per create -- reusing one
  filing's line self-denies as stale), then re-fetch to confirm
  it exists before recording anything as filed.
- **Exactly one match:** confirm it carries the `gate-proposal` label
  and its body still carries an Acceptance Criteria Map first -- this
  applies to a `gate-proposal: extend <gate-id>` match too, since anyone
  can open an issue with that title. A match missing either fails
  closed and escalates instead of recording filed.
- **More than one match:** fail closed and escalate -- the same
  discipline as Step 0's own ambiguous-stub-match handling.
  Never guess which one is authoritative, and never file a third.

## Recording a recurrence

Create the duplicate record exactly like a family issue above (exact
title search, create with `GATE_PROPOSAL_LABEL`, re-fetch), then close
it with `mcp__github__issue_write`: `state: closed`,
`state_reason: duplicate`, `duplicate_of: N`. Re-fetch and confirm it
is closed as a duplicate before recording it as filed. Each record is
its own issue, so concurrent runs never write the same object.

Then apply 4b.3's escalation rule. List closed issues labelled
`GATE_PROPOSAL_LABEL`, every page, and keep those whose body's
`duplicate_target` is N; re-fetch each kept issue and drop any whose
`state_reason` is not `duplicate`. Pass the kept titles to
`count_family_occurrences`. Only push- or triage-gated state counts: the
label (GitHub drops label changes from anyone without push access), the
duplicate closure, and the generator-made sweep line of an issue this
procedure filed. No comment or body text anyone else writes is read. A
legacy source closed before this procedure (no sweep line) is not
counted here; the consolidation scan, which reads GraphQL
`duplicateOf`, still counts it. If `needs_escalation` holds and the
family issue lacks `GATE_PROPOSAL_ESCALATED_LABEL`, write the union of
its current labels and that label.

## Recording the result in the retrospective body

Once a repair's record is confirmed (created-and-verified, matched, or
closed as a duplicate and verified), record `Filed as: #<issue number>` immediately
alongside that repair's own `Status: missing-deterministic-gate` line in
this retrospective issue's body, plus `Absorbed by:` for an ABSORBED-BY
repair -- add them there; never remove or replace the `Status:` line
itself. `issue_write` has no native append primitive: this "add" is
always a whole-body rewrite, so re-fetch this retrospective issue's own
current body immediately before this write and merge only this repair's
own lines into it, never reusing an earlier read -- a concurrent run
recording a different repair's own `Filed as:` line in the same body
window would otherwise be silently overwritten by a write built from a
stale copy.

## A failed or unconfirmed filing blocks that repair's line, not the rest of the cycle -- and blocks closing

If the script cannot compute a value for a repair (a required
classification field is missing), if the create or comment call itself
fails, or if a write cannot be confirmed by re-fetch (treat an
unconfirmed write as a failure, the same as an outright one) -- skip
only that repair's `Filed as:` line and continue with the rest. Never
close the retrospective issue while any `missing-deterministic-gate`
repair from this cycle still lacks a confirmed `Filed as:` line. A
later, resumed run retries only the repairs still missing one -- but a
`Filed as: #<N>` line already present in this retrospective issue's own
body is itself untrusted state, not proof: the body is externally
editable between runs (a careless edit, or a hostile one), so re-fetch
issue `#<N>` and confirm it still exists with the `gate-proposal` label,
was opened by the account this run posts as (`mcp__github__get_me`),
and carries this repair's row in its own ACM table (and, for a
duplicate record, is closed as a duplicate), before skipping it. A re-fetch that
cannot complete at all (a network/API error) is not the same finding as
a completed re-fetch that comes back mismatched or absent, but is
handled identically -- named separately here only so a reader does not
assume otherwise: neither one proves the filing is real, so both fall
through to the same re-file path rather than one silently trusting an
inconclusive check. A `Filed as:` line that does not re-verify this way
is treated exactly like an unconfirmed write: proceed to (re-)file that
repair, as if the line were absent, rather than trusting its mere
presence.

Step 4b verdicts and CLUSTER membership live only in memory, so a
resumed run has neither. Before re-filing a repair that lacks a
confirmed line, look for its existing record first: a `gate-proposal`
issue, open or closed, opened by the account this run posts as, whose
body carries `Refs #<this retrospective>` and an ACM row whose Criterion
is this repair's own label (created before the interruption). If one is
found, finish it -- a duplicate record still open is closed as above --
record `Filed as:` for it and stop. Only when none is found, re-run Step
4b for the repairs still unrecorded, then file them through the flows
above. The exact-title search is the backstop against a duplicate
either way.

## Close condition

Close once every `missing-deterministic-gate` repair from this cycle
carries a confirmed `Filed as:` line, except one tagged
`review-worked-as-designed` or one carrying `Covered by:` (an
ALREADY-SHIPPED verdict); zero such repairs is the trivial case. This follows the same attended/unattended rule the fast-close
path (`references/zero-repair-fast-close.md`) already uses, now extended
to every close this step performs, not only the zero-repair case: when
an operator is present to respond, preview the exact drafted body -- the
repair list, every filed-issue number, or the zero-repair paragraph --
and wait for an explicit go-ahead before calling close. When running
fully unattended with no operator able to respond, file everything above
but leave the retrospective issue open for a human to close after
review; never let a fully unattended context both draft the "everything
is filed" conclusion and act on it with nobody positioned to catch a
wrong call.

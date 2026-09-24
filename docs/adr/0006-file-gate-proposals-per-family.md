# File gate proposals per family, absorb into generic mechanisms, escalate on recurrence

## Status

Accepted (approved by tvna in the planning session for
https://github.com/tvna/gitapex/issues/2097, 2026-09-24)

## Context and Problem Statement

`merge-retrospective` filed every `missing-deterministic-gate` repair as
its own standalone `gate-proposal` issue
(`docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md`,
Decision 1). Issue https://github.com/tvna/gitapex/issues/1806 added
Step 4b: a backlog sweep, a batched review, and a DUPLICATE-OF path that
still created the standalone issue and then closed it as a duplicate.
That path kept a non-conflicting record of every repair even under
concurrent runs, and appended to the umbrella only on a best-effort
basis.

Facts at the time of this decision (issue #2097, read 2026-09-24):

- 135 `gate-proposal` issues were open; the drift workflow's threshold
  is 20.
- Step 4b.2 already returned a CLUSTER grouping, but 4b.3 gave it no
  action.
- Umbrella #1800 omitted #2089, which had been closed as its duplicate:
  the best-effort append was lost, and no scan checked that direction.
- An agent classification of the 135 open proposals (not verified issue
  by issue) found most of them clustered into recurring families, and
  about 20 were fully or partly catchable by mutation testing.

The question: how should Step 4b/5 file proposals so the backlog tracks
fixes rather than individual repairs, without losing any repair's record
under concurrent runs?

## Decision Drivers

- Issue #1806's guarantee: no repair's record is lost under concurrent
  retrospective runs.
- Each repair keeps its own full record (the retrospective body entry
  and its ACM row).
- `AGENTS.md` section 3: a new invariant ships its drift gate in the
  same change.
- The three-category taxonomy (#1807, ADR 0004) stays unchanged.

## Considered Options

For the record on an existing family issue:

1. An issue comment carrying a `Recurrence: retro #R repair K` line.
2. A direct append to the family issue body.
3. Keep create-then-close: a standalone record, closed as a duplicate
   of the family issue.

For where absorbed follow-up work is tracked:

1. One `gate-proposal: extend <gate-id>` family issue per declared
   mechanism.
2. A new ssot field naming a pre-created receiving issue.
3. The gate's existing `tracking_issue` (usually closed once shipped,
   for example #1799).

For the escalation signal:

1. A `gate-proposal-escalated` label, counting the original filing.
2. The same label, not counting the original filing.
3. An `Escalated:` marker in the body.

## Decision Outcome

Chosen by the owner: option 3 for the record (revised from option 1
during battle-testing, see Consequences), option 1 in the other two
groups.

- A new family issue is created only for NEW. A verified CLUSTER of NEW
  repairs creates one family issue with one ACM row per member.
- DUPLICATE-OF #N creates a standalone record whose generator-made
  sweep line reads `verdict DUPLICATE-OF #N`, then closes it with
  `state_reason: duplicate` and `duplicate_of: N`. Each record is its
  own issue, so concurrent runs never write the same object. The
  builder script and the Dedup-sweep hook accept only NEW and
  DUPLICATE-OF #N on a creation.
- ABSORBED-BY `<gate-id>` applies only to an `active` ssot gate
  declaring `generic_mechanism: true`. Anything else falls back to NEW.
  The follow-up work lands on the mechanism's single `extend` family
  issue, which is created through the NEW flow the first time.
- Occurrences = 1 (original filing) + distinct titles of closed
  `gate-proposal` issues marked as duplicates of the family issue. At 3
  or more, the family issue gets the `gate-proposal-escalated` label,
  which `ranking-the-open-queue` reads.

## Consequences

- Good: open gate-proposal count grows with families, not repairs.
- Good: no best-effort umbrella append is owed any more, so the
  lost-append class (#1800/#2089) cannot recur: the duplicate relation
  is itself the record.
- Bad: every recurrence still creates and closes one issue, so closed
  `gate-proposal` issues keep growing with repairs; only the open count
  grows with families.
- Bad: CLUSTER still comes from one probabilistic dispatch, so
  verifying it outside the dispatch remains a judgment call.
  Over-merging distinct fixes is the residual risk.
- Neutral: the occurrence count reads only push- or triage-gated state:
  the `gate-proposal` label (GitHub drops label changes from anyone
  without push access), the duplicate closure, and the generator-made
  sweep line of an issue this procedure filed. Five battle-testing
  rounds forged every text-based record tried first (a recurrence
  comment, the retrospective it names, quoted prose, a `Consolidates:`
  line in an editable body). The skill reads the target from the sweep
  line, so it undercounts legacy duplicates filed without one; the drift
  scan reads GraphQL `duplicateOf` and still counts them.
- Bad: the escalation label adds priority, not committed capacity.

## Confirmation

- Tests in `tests/test_gitapex_file_gate_proposal.py`,
  `tests/test_gitapex_check_gate_proposal_dedup_sweep.py`,
  `tests/test_gitapex_scan_gate_proposal_consolidation_drift.py`,
  `tests/test_gitapex_scan_ssot_schema.py` and
  `tests/test_gitapex_retro_gate_label_sync.py`.
- The daily `retrospective-gate-drift` workflow runs the consolidation
  scan's escalation check against live issues.
- Live proof (2026-09-24): issue #2102, closed through the GitHub MCP
  `issue_write` tool with `state_reason: duplicate` and
  `duplicate_of: 2097`, reads `state_reason: duplicate` over REST, and
  #2097's timeline gained a `marked_as_duplicate` event.

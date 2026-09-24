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
3. Keep create-then-close, and only change the grouping.

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

Chosen by the owner, in each group: option 1.

- Only NEW creates an issue. A verified CLUSTER of NEW repairs creates
  one family issue with one ACM row per member. The builder script and
  the Dedup-sweep hook both reject any other verdict on a creation.
- DUPLICATE-OF #N posts an append-only recurrence comment on #N. The
  comment replaces the standalone issue as the non-conflicting write.
  Its key doubles as the resume check.
- ABSORBED-BY `<gate-id>` applies only to an `active` ssot gate
  declaring `generic_mechanism: true`. Anything else falls back to NEW.
  The follow-up work lands on the mechanism's single `extend` family
  issue, which is created through the NEW flow the first time.
- Occurrences = 1 (original filing) + distinct `Consolidates:` sources +
  distinct recurrence keys. At 3 or more, the family issue gets the
  `gate-proposal-escalated` label, which `ranking-the-open-queue` reads.

## Consequences

- Good: open gate-proposal count grows with families, not repairs.
- Good: no create-then-close churn; the lost-append class (#1800/#2089)
  is now detected in both directions by the consolidation scan.
- Neutral: a family issue's history is split between its body (the
  original rows and any `Consolidates:` line) and its comments.
- Bad: CLUSTER still comes from one probabilistic dispatch, so
  verifying it outside the dispatch remains a judgment call.
  Over-merging distinct fixes is the residual risk.
- Neutral: the occurrence count, in the skill and in the drift scan,
  trusts only records written by an account with write access (GitHub's
  `author_association` OWNER/MEMBER/COLLABORATOR). Four battle-testing
  rounds showed that every text-based check (the comment itself, the
  retrospective it names, quoted prose) can be forged. Such an account
  could add the label directly anyway, so trusting it grants nothing
  new. A legitimate record from an account without write access is
  undercounted, which fails safe.
- Bad: the escalation label adds priority, not committed capacity.

## Confirmation

- Tests in `tests/test_gitapex_file_gate_proposal.py`,
  `tests/test_gitapex_check_gate_proposal_dedup_sweep.py`,
  `tests/test_gitapex_scan_gate_proposal_consolidation_drift.py`,
  `tests/test_gitapex_scan_ssot_schema.py` and
  `tests/test_gitapex_retro_gate_label_sync.py`.
- The daily `retrospective-gate-drift` workflow runs the consolidation
  scan's reverse-direction and escalation checks against live issues.

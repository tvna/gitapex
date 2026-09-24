# Backlog-Grounded Proposal Review (Step 4b)

Runs between Step 4 (classify) and Step 5 (file). Step 5's filing action
is sequence-gated on a verdict from this step existing for every
`missing-deterministic-gate` repair. Why proposals are filed per family
rather than per repair: `docs/adr/0006-file-gate-proposals-per-family.md`.

## 4b.1 Sweep the backlog

List open `gate-proposal` issues to exhaustion (the `gate-proposal`
label filter, state open, paging through every page before concluding
anything); read the full body of every umbrella-shaped title and every
issue whose body carries a `Consolidates:` line; read
`.gitapex/ssot.json`'s `gates[]` array, noting every `active` gate that
declares `generic_mechanism: true`; read the latest scheduled-run
conclusion of the `retrospective-gate-drift` workflow. Fetch titles
first and full bodies only for umbrella-shaped issues, so a growing
backlog grows this step's input cost sublinearly.

## 4b.2 Independent verdict

Dispatch one fresh, read-only `review-persona` review per cycle, covering
every `missing-deterministic-gate` repair from Step 4 together against
the 4b.1 backlog -- never one dispatch per repair; a per-repair dispatch
would have no cross-repair view and so could never produce this same
step's own batch-level CLUSTER grouping below. It returns, per repair,
exactly one verdict:

- NEW: no existing proposal, shipped gate, or generic mechanism covers it.
- DUPLICATE-OF #N: open family issue #N (an umbrella or an earlier
  filing) already proposes the same fix.
- ABSORBED-BY with an ssot gate id: a declared generic mechanism already
  exists and could express this repair with a new row, operator or
  fixture, but does not catch it yet. The classification stays
  `missing-deterministic-gate`; the taxonomy is unchanged.
- ALREADY-SHIPPED with an ssot gate id: a shipped gate already catches
  it, so nothing is filed.
- RECLASSIFY with a reason: the repair is not a missing gate after
  all -- advisory only, the calling skill still decides.

It additionally returns a batch-level CLUSTER grouping when several
repairs describe one fix. Verify each verdict outside the dispatch
before acting, the same verify-outside-the-dispatch split
`executing-a-branch-plan`'s Step 8 already uses -- a verdict is a claim
to check, never a result to trust:

- DUPLICATE-OF #N: re-fetch #N and confirm it is open and labelled
  `gate-proposal`. A closed or unlabelled #N falls back to NEW.
- ABSORBED-BY: re-read the ssot entry and confirm the id exists, is
  `active`, and declares `generic_mechanism: true`. Anything else falls
  back to NEW. Also confirm the mechanism can express the repair at all:
  an omission (a check nobody wrote) is not something mutation testing
  can surface, so such a repair falls back to NEW too.
- CLUSTER: read the members' proposed gates side by side and confirm
  they name one fix. Split any member that does not; over-merging
  distinct fixes into one family is the failure this check exists for.

## 4b.3 Act on the verdict

Every repair except an ALREADY-SHIPPED one ends up recorded on exactly
one family issue, and every repair keeps its own entry in the
retrospective body:

- **NEW**, alone or as a verified CLUSTER: create one family issue
  through the Step 5 flow, one ACM row per member, titled by the
  lowest member index. A CLUSTER whose members mix NEW with
  DUPLICATE-OF #N records every member on #N instead.
- **DUPLICATE-OF #N**: post one recurrence comment on #N. Nothing is
  created and nothing is closed.
- **ABSORBED-BY `<gate-id>`**: search open issues for the exact title
  `gate-proposal: extend <gate-id>`. If none exists, create it through
  the NEW flow with this repair's row; if one exists, post a recurrence
  comment on it. The retrospective entry adds `Absorbed by: <gate-id>`.
- **ALREADY-SHIPPED**: files nothing. The retrospective entry records
  `Covered by: <gate-id>` instead of a `Filed as:` line.

A recurrence comment is append-only, so two concurrent retrospective
runs recording on the same family issue cannot overwrite each other.
It replaces the old create-then-close standalone issue as the
non-conflicting write. After posting one, re-fetch the family issue's
body and comments and count its occurrences (the script's
`count_family_occurrences`: the original filing, each `Consolidates:`
source, and each distinct recurrence key, counting only records written
by an account with write access -- see the filing-mechanics reference). At `ESCALATION_THRESHOLD`
(3) or more, add the `gate-proposal-escalated` label (re-fetch the
current labels and write their union; create the label first if it is
missing). The family issue is then the next work item. File nothing
new for it.

When the drift workflow's latest conclusion is `failure`, the
retrospective body states that fact in one line.

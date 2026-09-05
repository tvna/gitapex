# Backlog-Grounded Proposal Review (Step 4b)

Runs between Step 4 (classify) and Step 5 (file). Step 5's filing action
is sequence-gated on a verdict from this step existing for every
`missing-deterministic-gate` repair.

## 4b.1 Sweep the backlog

List open `gate-proposal` issues to exhaustion (the `gate-proposal`
label filter, state open, paging through every page before concluding
anything); read the full body of every umbrella-shaped title and every
issue whose body carries a `Consolidates:` line; read
`.gitapex/ssot.json`'s `gates[]` array; read the latest scheduled-run
conclusion of the `retrospective-gate-drift` workflow. Fetch titles
first and full bodies only for umbrella-shaped issues, so a growing
backlog grows this step's input cost sublinearly.

## 4b.2 Independent verdict

Dispatch a fresh, read-only `review-persona` review over the repair plus
the 4b.1 backlog. It returns, per repair, exactly one verdict:

- NEW: no existing proposal or shipped gate covers it.
- DUPLICATE-OF #N: umbrella or standalone issue #N already covers it.
- ALREADY-SHIPPED with an ssot gate id: a shipped gate already covers
  it, so nothing is filed.
- RECLASSIFY with a reason: the repair is not a missing gate after
  all -- advisory only, the calling skill still decides.

It additionally returns a batch-level CLUSTER grouping when several
repairs describe one fix. Verify each verdict outside the dispatch
(re-fetch #N, re-check the ssot entry) before acting, the same
verify-outside-the-dispatch split `executing-a-branch-plan`'s Step 8
already uses -- a verdict is a claim to check, never a result to trust.

## 4b.3 Act on the verdict

NEW files through the Step 5 flow. DUPLICATE-OF #N still creates its
standalone issue through the Step 5 flow (an independent,
non-conflicting write carrying the sweep line with the duplicate
verdict), immediately closes it with `state_reason: duplicate`
referencing #N, and appends its row to #N's `Consolidates:` line and
ACM table as a best-effort follow-up write; never skip creating the
standalone issue, so no repair's record depends on a shared-body append
winning a write race against a concurrent run. ALREADY-SHIPPED files
nothing. When the drift workflow's latest conclusion is `failure`, the
retrospective body states that fact in one line.

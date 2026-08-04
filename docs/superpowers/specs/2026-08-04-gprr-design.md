# Gate-Preventable Repair Rate (GPRR): design

Date: 2026-08-04

Refs #726. Design-then-implement doc, per this repo's own plan-first
discipline; the implementing PR carries this same commit.

## Context

`skills/merge-retrospective/SKILL.md` (lines 54-127) already requires every
retrospective issue to carry a machine-parseable `Status:` tag from a fixed
vocabulary (`missing-deterministic-gate` / `unclear-agent-instruction` /
`external-human-decision` / `carried-forward`), explicitly so "a future
drift-check script can extract classification and gate status without an
LLM." Nobody currently tallies this: CLAUDE.md section 3 mandates the
classification, but only as narrative per-issue text, re-read by a human
(or an LLM) each time to see any trend.

`.github/scripts/scan_retrospective_gate_drift.py` already fetches
`label:retrospective` issues via the GitHub API for its own no-citation
threshold check (see
`docs/superpowers/specs/2026-07-22-retrospective-gate-drift-design.md`).
That check answers "how many retrospective issues lack a citing commit";
it says nothing about what fraction of *classified repairs* were
gate-preventable, and it reports a single current snapshot, not a trend.

## Decisions

### 1. Reuse the existing fetch machinery instead of a second GitHub client

Per the issue's own constraint, `compute_gprr.py` does not hand-roll a
second paginated-GitHub-issues client. `scan_retrospective_gate_drift.py`
is refactored to expose `list_labelled_issue_records(...)`, returning the
full issue record (`number`, `body`, `created_at`, `state`) instead of
just the bare issue number `list_labelled_issues(...)` already returned.
The retry/backoff/pagination logic (`fetch_json_page`, renamed from the
former private `_fetch_issues_page` since it is generic JSON-array-page
fetching, not issues-specific) is unchanged; `list_labelled_issues` becomes
a thin wrapper that extracts `number` from each record, preserving its
existing signature, behavior, and tests exactly. `compute_gprr.py` also
reuses `fetch_json_page` directly for the merged-pull-request query below,
rather than writing a third copy of the same retry loop.

### 2. Stateless recomputation, not a persisted/committed time series

The requested outcome asks for the trend to be "an inspectable numeric
time series," but the issue's own Acceptance Criteria Map flags *where* to
store that series as an open question ("tracked file vs. external
artifact -- unknown, pending a storage decision").

Resolution: don't persist anything. `compute_gprr.py` buckets every
`label:retrospective` issue (unfiltered by state, matching
`scan_retrospective_gate_drift.py`'s own Step-0-derived convention) by the
ISO week of its `created_at`, for its *entire* history, on every run. The
full weekly series is therefore always reproduced from source-of-truth
GitHub state, not from a possibly-stale committed snapshot -- and a run a
week from now naturally shows one more week-bucket than today's run, which
is exactly the growth the issue's proof method asks for, with no merge/
append logic and no new write scope. This mirrors
`scan_retrospective_gate_drift.py`'s own "recompute the whole answer every
time" shape and this repo's existing "stdout piped to
`$GITHUB_STEP_SUMMARY`" reporting convention (Decision 2 of the sibling
design doc) -- no new secret, no `contents: write`, no commit-back step.

Rejected alternative: append each run's point to a tracked JSON file,
committed by the workflow. Rejected because it needs a new write-scoped
token and an idempotent commit step neither this workflow nor its sibling
currently has, to solve a problem (visibility over time) full recomputation
already solves for free.

### 3. `missing-deterministic-gate` share is the headline; `carried-forward` is excluded from the denominator

The requested outcome's denominator is "total classified repairs." Per
`merge-retrospective`'s own taxonomy, only three slugs classify a *repair*:
`missing-deterministic-gate`, `unclear-agent-instruction`,
`external-human-decision`. `carried-forward` re-reports a prior cycle's
still-unimplemented gate -- it is not a new repair this cycle classified
(SKILL.md lines 85-101), so it is tallied and reported separately, never
folded into the GPRR ratio's denominator or numerator.

### 4. Two ratios, both against classified repairs and against merged PRs

Per the requested outcome: `missing-deterministic-gate` count is reported
as a share of (a) total classified repairs found in `label:retrospective`
issue bodies for that week, and (b) the count of pull requests merged that
week (via `GET /repos/{owner}/{repo}/pulls?state=closed`, filtered to a
non-null `merged_at`) -- a rough proxy for "how many merge cycles produced
a gate-preventable repair," independent of whether every cycle files a
fully-classified retrospective. Either denominator may be zero for a given
week (no classified repairs, or no merged PRs); the corresponding ratio is
reported as `n/a` rather than dividing by zero.

Verified live against this repository 2026-08-04: `gate_share_of_merged_prs`
legitimately exceeds 100% in some weeks (2026-W31: 152 gate-preventable
repairs of 198 classified, against only 73 PRs merged that same week). This
is expected, not a bug -- a single retrospective issue can enumerate
several repairs, a busy week's retrospective issues can classify repairs
whose originating PR merged in an earlier week, and merge-retrospective
files one issue per merged PR, not one repair per PR. The ratio answers
"how many gate-preventable repairs were reported per merged PR that
week," which is not bounded to 1, rather than "what fraction of merged
PRs had one," which would be.

### 5. Informational only, no threshold, no CI failure on the metric itself

Unlike its sibling, this script never exits non-zero based on the GPRR
value -- the issue explicitly frames this as replacing "only a threshold
pass/fail gate" with "an inspectable numeric time series." It still exits
1 on a genuine GitHub API error (never silently reporting an empty/zero
series as if it were a real all-clear), matching the sibling script's own
fail-loud posture for I/O failures.

## Mechanism

### `.github/scripts/compute_gprr.py`

Stdlib-only, same reasons as its sibling (`dependencies = []`;
`.github/scripts/*.py` files stay independently self-contained).

**Pure logic:**

- `parse_status_tags(body) -> list[str]` -- regex-extracts every
  `` Status: `<slug>` `` occurrence restricted to the fixed four-slug
  vocabulary (an unrecognised slug is not matched, so untrusted quoted
  material inside an issue body -- SKILL.md's own injection concern for
  this exact field -- cannot forge a fifth category).
- `week_key(iso_timestamp) -> str` -- the ISO-8601 week (`YYYY-Www`) an
  RFC 3339 timestamp falls in.
- `classify_tags(tags) -> GprrCounts` -- tallies the three repair
  categories plus `carried-forward` separately.
- `build_weekly_series(issue_records, merged_pr_timestamps) ->
  list[WeeklyPoint]` -- buckets both inputs by `week_key`, unions the set
  of weeks present in either, and computes both ratios (`None` when a
  denominator is zero) per week plus an all-time total row.
- `format_report(series) -> str` -- headline all-time
  `missing-deterministic-gate` share first, then a per-week table.

**I/O glue:**

- `list_merged_pull_requests(owner, repo, token, opener, sleeper) ->
  list[str]` -- paginated `GET /repos/{owner}/{repo}/pulls?state=closed`,
  returning each merged PR's `merged_at`, via
  `scan_retrospective_gate_drift.fetch_json_page`.
- `main(argv)` -- `--owner`, `--repo`, `--label` (default `retrospective`),
  reads `GITHUB_TOKEN` from the environment; wires
  `scan_retrospective_gate_drift.list_labelled_issue_records` and
  `list_merged_pull_requests` into the pure functions, prints the report,
  exits 1 only on a GitHub API error.

### `.github/workflows/retrospective-gate-drift.yml`

A new step in the existing job, immediately after the citation-drift scan
(same cron cadence, same checkout -- `compute_gprr.py` needs no local git
history, only the GitHub API, so it does not need its own job). Adds
`pull-requests: read` to the job's and workflow's `permissions:` blocks
(needed for the merged-PR query; `issues: read` alone does not cover the
pulls endpoint). Piped through `tee -a "$GITHUB_STEP_SUMMARY"`, matching
the sibling step exactly -- no `continue-on-error`, but also nothing for
it to fail *on* besides a genuine API error, per Decision 5.

## Non-goals

- Does not implement OTEL token/cost telemetry joining (explicitly out of
  scope per the issue -- a larger, separate effort requiring telemetry to
  be enabled first).
- Does not itself resolve any open retrospective issue; tracked separately
  as the retrospective-backlog issue the parent issue names.
- Does not persist a committed time series (Decision 2) -- if step-summary
  visibility (only as durable as Actions' own log retention) proves
  insufficient in practice, revisit as a follow-on, same posture the
  sibling design doc took for its own "stronger enforcement" open item.
- Does not make this check a required branch-protection status check --
  it reports a metric, not a pass/fail gate; there is nothing to attach a
  required check to.

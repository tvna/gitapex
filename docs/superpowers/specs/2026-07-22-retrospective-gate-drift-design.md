# Retrospective gate-drift meta-check: design

Date: 2026-07-22

Refs #297 (refs #187, #242, #246). Design-then-implement doc, per this repo's
own plan-first discipline; the implementing PR carries this same commit.

## Context

`merge-retrospective`'s Step 0 requires, every cycle, a manual search of
every `retrospective`-labelled issue for a citing commit on `main`. Issue
#187 (2026-07-19) proposed automating this as a meta-gate: "a periodic (or
pre-merge) check that fails, or at minimum reports, when the count of
`retrospective`-labelled issues with no citing commit exceeds a threshold."
Issue #242 (2026-07-21) ran Step 0 by hand again and confirmed the
meta-gate itself was never built -- the exact kind of silent gate-rot it
exists to catch: "That meta-gate would have made this exact carry-forward
list visible automatically instead of requiring this Step 0 pass to
discover it by hand." Issue #246 (2026-07-21) repeated the same manual
search a third time.

Verified 2026-07-22, against this repository's full (unshallowed) commit
history on `main`, using the exact heuristic `merge-retrospective`'s Step 0
and #187's own text describe (`git log --grep="#N"` over `main`):

- `label:retrospective` (unfiltered by state) returns 22 issues.
- Only 4 have any citing commit on `main`: #285 (3 commits), #246 (2),
  #242 (5), #187 (1, commit `e42bd51`).
- The remaining 18 have zero citing commits: #296, #294, #293, #277, #270,
  #264, #260, #256, #249, #244, #228, #218, #212, #210, #207, #205, #191,
  #118.

Full details and the exact search commands are recorded in tracking issue
#297.

## Decisions (confirmed with the operator before implementation)

### 1. CI posture: the scheduled run fails when the threshold is exceeded

This check has no single PR to attach a blocking status check to -- it
measures repo-wide GitHub issue/commit-history state, not a PR's diff.
"Blocking" therefore means: the scheduled workflow run itself exits
non-zero and shows red in the Actions tab, with no `continue-on-error`.
This is the strongest signal available for a repo-wide metric, and it
deliberately avoids the posture #242's own repair 1 criticizes:
"`waza-check` ... is documented as advisory only ... so today nothing
blocks a merge on either audit's result." A red scheduled run is not
silent the way an always-green advisory report is, without giving this
check inappropriate blast radius over unrelated PRs (it never touches a
PR's merge status at all).

Rejected alternative: **advisory-only** (`continue-on-error: true`,
matching `waza-check.yml`). Rejected because it reproduces exactly the
failure mode #242 already named for a different gate -- a report nobody
is forced to look at.

### 2. Reporting: stdout piped to the GitHub Actions step summary

The script prints a human-readable report (total retrospective issues,
the no-citation count, the threshold, and the full list of no-citation
issue numbers) to stdout. The workflow pipes that through
`tee -a "$GITHUB_STEP_SUMMARY"`, the same pattern `waza-check.yml` already
uses. This needs only a read-scoped `GITHUB_TOKEN` (`contents: read`,
`issues: read`) -- no new secret, no write-scope token, no new
issue-filing logic.

Rejected alternative: **auto-file or update a tracking GitHub issue** each
run (mirroring the still-unbuilt sibling "auto-retro" design in
`docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md`). Rejected
for this pass: it needs `issues: write`, an idempotent
search-existing-or-create/update flow, and careful escaping of any
generated body text -- materially more moving parts for a first version.
Left as a documented follow-on in Non-goals below, not implemented here.

### 3. Threshold: 20

Measured backlog today is 18. The threshold is set to 20 -- 18 plus a
2-issue operating buffer -- per explicit operator direction, rather than
pinned exactly at today's measured count. Rationale: every merge cycle
files a fresh retrospective issue that starts uncited by construction (a
retrospective issue proposes gates, it does not implement them, per
`merge-retrospective`'s own Stop boundary), so a threshold pinned exactly
at today's count would trip on the very next ordinary merge rather than on
genuine drift. A threshold of 20 still fails CI the moment the backlog
grows by 3 beyond today's baseline, and it does not retroactively fail CI
over the existing 18-issue backlog -- clearing that backlog is explicitly
out of scope for this change (see Non-goals).

## Mechanism

### `.github/scripts/scan_retrospective_gate_drift.py`

Lives in `.github/scripts/`, matching the existing `gate_*`/`scan_*`
precedent: repo-specific CI glue, not inside any skill's own directory.
Stdlib-only -- this project ships zero production dependencies
(`pyproject.toml`: `dependencies = []`) -- and does not import
`sync_pr_publish.py` even though it needs a similar
GitHub-API-over-`urllib` shape, matching this repo's existing discipline
of keeping `.github/scripts/*.py` files independently self-contained (see
`gate_skill_rename_lifecycle.py`'s own docstring rationale for why).

Split into a pure-logic layer (fixture-testable, no I/O) and an I/O-glue
layer (network + subprocess, exercised by the live workflow run, not by
`pytest`):

**Pure logic:**

- `citation_count(commit_messages, issue_number) -> int` -- counts commit
  messages containing `#<issue_number>` as a citation, using a
  digit-boundary-aware match (`(?<!\d)#N(?!\d)`) so `#187` matches but
  `#1870` or `#2187` do not.
- `find_no_citation_issues(issue_numbers, commit_messages) -> list[int]`
  -- the subset of `issue_numbers` with zero citing commits.
- `evaluate(no_citation_count, threshold) -> bool` -- whether the count
  exceeds the threshold.
- `format_report(no_citation_issues, total_issues, threshold) -> str` --
  the report text printed to stdout (and thus captured in the step
  summary).

**I/O glue:**

- `list_labelled_issues(owner, repo, label, token, opener=...) ->
  list[int]` -- paginated `GET /repos/{owner}/{repo}/issues?
  labels=<label>&state=all&per_page=100`, matching Step 0's own
  unfiltered-by-state method. Retries transient (5xx/network) failures up
  to 3 attempts, mirroring `sync_pr_publish.apply_call`'s retry shape.
  Filters out any returned item carrying a `pull_request` key, since the
  GitHub issues-list endpoint also returns pull requests and this repo's
  retrospective issues are, by construction, never PRs.
- `git_commit_messages(ref, cwd, runner=subprocess.run) -> list[str]` --
  runs `git log <ref> --pretty=format:...` in the checked-out repository
  and returns each commit's full message (subject + body) as one string.
  `runner` is injectable so tests never invoke a real subprocess.
- `main(argv)` -- CLI entry point: `--owner`, `--repo`, `--ref` (default
  `HEAD`), `--threshold` (default `DEFAULT_THRESHOLD = 20`); reads the
  token from the `GITHUB_TOKEN` environment variable. Wires the I/O calls
  into the pure functions, prints the report, and exits 1 if
  `evaluate(...)` is true or if either I/O call fails outright (a network
  or git error is surfaced loudly and fails the run -- it is never treated
  as "zero issues found," which would silently look like a passing gate).
  Exits 0 otherwise.

### `.github/workflows/retrospective-gate-drift.yml`

New standalone workflow file, matching this repo's one-workflow-per-concern
convention. Same harden-runner + pinned `actions/checkout` preamble as
this repo's other workflows (`persist-credentials: false`); `fetch-depth:
0` so the full commit history is available locally for `git log`.

- Trigger: `schedule` (`cron: "0 7 * * *"`, daily 07:00 UTC -- offset by
  one hour from `sync-agent-instructions.yml`'s existing 06:00 UTC cron to
  avoid both jobs starting at the same instant) plus `workflow_dispatch`
  for manual/on-demand runs.
- Permissions: `contents: read`, `issues: read` -- the default
  `GITHUB_TOKEN` already carries these for a public repository; no new
  secret is introduced.
- No `uv`/dependency-install step: the script is stdlib-only, matching
  `skill-audit-gate.yml`'s bare `python3 .github/scripts/...` invocation
  (that workflow also has no `uv` setup step).
- The single run step invokes the script and pipes its stdout through
  `tee -a "$GITHUB_STEP_SUMMARY"`. No `continue-on-error` anywhere in the
  job.

## Non-goals

- Does not implement any of the 8 still-backlogged content gates this
  meta-gate surfaces (#228, #218, #212, #210, #207, #205, #191, #118), nor
  #187's other four proposed gates. Those remain separate follow-on work.
- Does not auto-file or update a GitHub tracking issue -- step-summary
  reporting only, per Decision 2 above. A natural follow-on if
  step-summary visibility proves insufficient in practice.
- Does not reimplement Step 0's title-fallback matching for
  pre-`retrospective`-label issues. Verified 2026-07-22 that all 22
  current retrospective issues already carry the label (the label
  backfill #187 itself called for has evidently already happened);
  revisit this assumption if it ever stops holding.
- Does not search merged-PR bodies as a second citation source alongside
  commit messages. This repository's own instruction file already
  mandates citing the issue number "in every commit," so a merged PR
  citing a retrospective issue only in its body, with zero citing commits,
  would itself be a convention violation this gate is not designed to
  separately detect.
- Does not make this check a required branch-protection status check. It
  is schedule/dispatch-triggered rather than PR-triggered, so it has
  nothing to attach a required-check rule to in the way a PR-triggered
  gate would. See Open item below.

## Open item

Unlike a PR-triggered gate, this check cannot be made a required
branch-protection status check -- there is no PR event for branch
protection to gate on. The only enforcement lever available today is the
scheduled run's own pass/fail state, visible in the Actions tab and (per
Decision 2) the step summary. If stronger enforcement is wanted later
(e.g., surfacing the failing state somewhere more visible than the Actions
tab), that is a follow-on design question, not resolved here -- flagged
explicitly for the repo owner rather than silently assumed sufficient,
matching the same pattern `2026-07-21-skill-audit-merge-gate-design.md`
used for its own branch-protection open item.

## Acceptance criteria

- [ ] `scan_retrospective_gate_drift.py`'s pure-logic functions
      (`citation_count`, `find_no_citation_issues`, `evaluate`,
      `format_report`) are covered by unit tests, including the
      digit-boundary edge cases (`#187` vs `#1870` vs `#2187`).
- [ ] `list_labelled_issues` and `git_commit_messages` are covered by unit
      tests using injected fakes -- no real network or subprocess call in
      the test suite.
- [ ] `main()` exits 0 when the no-citation count does not exceed the
      threshold, exits 1 when it does, and exits 1 (not 0) on an injected
      API or git failure.
- [ ] `retrospective-gate-drift.yml` triggers on `schedule` and
      `workflow_dispatch` only, uses `contents: read` + `issues: read`,
      and has no `continue-on-error`.
- [ ] A live dry run against the real repository (not just the unit test
      suite) confirms the script's reported count and exit code before
      this is called done, per this repo's live-proof requirement.
- [ ] Full pytest suite green; `waza-check.yml` and
      `sync-agent-instructions.yml` left byte-for-byte unchanged.

## Addendum (2026-08-03): corroborating signal, per issue #709

Issue #709 documented two real false negatives in the mechanism above: a
bare citing commit (`citation_count > 0`) cleared an issue from the report
even when that commit changed something unrelated to the issue's own
proposed gate (#314, cleared by commit `a66ccbc`, which only touched a
workflow comment and a doc) or when only one of several proposals in a
multi-proposal retrospective issue had actually landed (#665, whose
"repair 6" was implemented by PR #703 while repairs 2/3/4 remained open,
yet the whole issue disappeared from the report the moment `#665` first
appeared in a commit message).

**Decision: an issue clears only when a citing commit AND a
corroborating `.gitapex/ssot.json` entry both agree.** Concretely,
`find_no_citation_issues` now also takes the set of every
`gates[].tracking_issue` value currently registered in
`.gitapex/ssot.json` (loaded by the new `load_gate_tracking_issues`,
fail-closed on a missing/malformed registry -- mirroring
`detect_changed_gate_scripts.py`'s `registered_gate_paths()`). An issue
number is excluded from the no-citation report only if it has at least
one citing commit *and* it appears as some gate's `tracking_issue`.

This directly fixes both reproduced shapes: neither 314 nor 665 has ever
been registered as a `tracking_issue` in `.gitapex/ssot.json` (verified
2026-08-03 against the current registry), so both stay in the report
regardless of any commit that happens to cite them, until a gate is
actually registered against that specific issue number.

**Explicitly named gap (not silently assumed covered), per issue #709's
own residual-risk column:** `tracking_issue` is a per-*gate* field, one
row per registered gate -- it has no way to represent a gate that is a
sub-feature of an already-registered gate rather than a new standalone
entry (e.g. issue #673's case, a check added inside
`gate_skill_audit_disclosure.py` without a dedicated registry row of its
own). A retrospective issue whose only proposal is implemented this way
will permanently show as "no citation" under this narrower check, even
though the work genuinely landed. This is an intentional
false-positive-over-false-negative trade-off (the report over-flags
rather than silently clearing something unverified), not a limitation to
paper over. A dedicated implementation-ledger fallback for this specific
gap is left as unimplemented follow-on work if it proves painful in
practice, per issue #709's own Acceptance Criteria Map.

No other decision above changes: CI posture, reporting mechanism,
threshold, and workflow trigger/permissions are all unchanged by this
addendum.

# merge-retrospective autofill: event-triggered GitHub Actions workflow

Date: 2026-08-05

Refs #769. Related: #728 (backlog-reduction, distinct scope), #762/#763
(the incident that prompted this issue), #694/#314/#140
(post-merge-auto-retro stub-opening and stale-stub-autoclose lineage).

## Facts

- `skills/merge-retrospective/SKILL.md`'s own trigger is a description
  string ("Use when a pull request has just merged, before closing the
  turn") -- there is no hook, gate, or scheduled mechanism that forces its
  content-filling Procedure (Step 0's carry-forward check, Step 1's repair
  enumeration, Steps 2-3's classification, Step 4's issue file/update) to
  actually run. It depends entirely on an interactive agent session being
  live at merge time and remembering to invoke it.
- `.github/scripts/gitapex_post_merge_retro.py`, wired by
  `.github/workflows/post-merge-retro.yml` on `pull_request_target: types:
  [closed]` (guarded on `merged == true`), already opens a bare stub
  retrospective issue for every merged PR unattended -- no agent involved.
  Its body carries a fixed marker string, `"Automated stub opened by the
  post-merge-auto-retro gate"`, and the label `retrospective`, both set at
  creation time.
- `.github/workflows/stale-retro-stub-autoclose.yml` (daily cron 08:00
  UTC) finds open `retrospective`-labelled issues whose body still carries
  that same marker string and closes them once they exceed 48h old. Its
  own script docstring states the premise motivating this issue directly:
  "a real retrospective requires session memory a fresh, memory-less CI
  dispatch cannot substitute for." That premise is only partially true --
  `skills/merge-retrospective/SKILL.md` Step 1 already reconstructs a
  PR's full repair history from `mcp__github__pull_request_read`
  (`get_commits`, `get_reviews`, `get_review_comments`, `get_check_runs`)
  rather than from session memory, which is exactly how issue #763 was
  filled after the fact, by a session with no memory of PR #762's merge.
  The content-filling step needs LLM judgment (classification against the
  fixed three-category taxonomy), not session continuity.
- `.github/workflows/ranking-the-open-queue-weekly.yml` already ships a
  working blueprint for exactly this shape of problem: a headless
  `anthropics/claude-code-action@v1` dispatch from GitHub Actions, running
  a named skill against the live repo, authenticated with
  `secrets.ANTHROPIC_API_KEY` (a plain repository secret, no GitHub
  Environment gate, documented in `CONTRIBUTING.md`) and a locally-run
  `ghcr.io/github/github-mcp-server` Docker container fed the existing
  `secrets.GITHUB_TOKEN`, scoped by a read-mostly workflow `permissions:`
  block plus a `--allowedTools` allowlist. Its own design doc
  (`docs/superpowers/specs/2026-07-28-ranking-the-open-queue-github-actions-routine.md`)
  independently compared this against a `Claude_Code_Remote`
  (Claude Code Cloud Routine) approach and against AWS ECS Fargate, GCP
  Cloud Run Jobs, and Fly.io Scheduled Machines, and picked GitHub Actions
  on every axis. The `Claude_Code_Remote` route specifically (`create_trigger`,
  `list_triggers`, `list_environments`, `send_later`) is documented there
  as **structurally blocked** for this repository: every attempt, from
  both interactive and non-interactive sessions, failed with the
  identical `MCP error -32003: MCP tool call requires approval`, an
  out-of-session account-level gate no secret or workflow change in this
  repository can clear.
- `.github/scripts/gitapex_gate_routine_scope_enforcement.py` (issue #520)
  is a CI gate that fails a `docs/superpowers/specs/*routine*.md` doc
  naming a skill whose `metadata/gitapex.yaml` declares
  `capabilityAssumption: Broad` unless the doc also cites a concrete,
  implemented scoping mechanism (a read-only `permissions:` block, an
  `--allowedTools` allowlist, a named deny hook, a real `environment_id`
  value, or a read-only credential). `skills/merge-retrospective/metadata/gitapex.yaml`
  declares `capabilityAssumption: Broad`, so this doc and the workflow it
  describes must satisfy that gate -- see "Scope enforcement" below.
- Live workflow-run history for `ranking-the-open-queue-weekly.yml`
  (checked 2026-08-05 via `mcp__github__actions_list`) shows every run
  since it shipped failing fast (~15-30s, consistent with an early
  API-call rejection): 2026-07-28 through 2026-08-03, both scheduled and
  `workflow_dispatch` runs. The 2026-07-28 design doc's own investigation
  root-caused an earlier instance of this exact failure shape to
  `"Credit balance is too low"` / `billing_error` on the Anthropic Console
  account backing `ANTHROPIC_API_KEY` -- an owner-side, out-of-session
  blocker, not a code defect. This session did not re-enable
  `show_full_output` to re-confirm the same root cause on the most recent
  run (that flag was reverted after its one prior diagnostic use and
  re-enabling it to inspect output not otherwise needed is unnecessary
  exposure), so "still the same billing block" is carried forward as the
  best available inference from the identical failure shape, not
  independently re-verified this session -- flagged as speculation, not
  fact, distinct from the directly-observed run statuses above.

## Requested outcome (from issue #769)

A deterministic mechanism ensures `merge-retrospective`'s content-filling
procedure actually runs for every merged PR, without depending on an
agent remembering to invoke it and without requiring a human to
explicitly ask, while never weakening the existing 100%-human-merge
policy and without duplicating issue #728's separate backlog-reduction
scope.

## Decision: event-triggered GitHub Actions workflow, not a scheduled sweep

New file: `.github/workflows/merge-retrospective-autofill.yml`, in the
same structural pattern as `ranking-the-open-queue-weekly.yml` (harden-runner,
`ref: main`-pinned checkout, `concurrency` group, minimal job-level
`permissions:`, `timeout-minutes`), but differing in one deliberate way:
**event-triggered on `issues: types: [opened, labeled]`, not
`schedule:`.**

Rationale for event-triggered over scheduled (the shape issue #769's own
Acceptance Criteria Map suggested by analogy to
`stale-retro-stub-autoclose.yml`):

- `gitapex_post_merge_retro.py`'s own POST that creates the stub already sets
  the `retrospective` label and the fixed marker string at creation time,
  in the same request. `issues: opened` fires the instant that POST
  succeeds -- no polling interval, no latency budget to size against the
  48h stale-close window. This is strictly closer to "runs shortly after
  its stub is opened" (the ACM's own proof-method wording) than any cron
  cadence could be, at zero marginal Actions-minutes cost when no stub
  exists to process (the job's own `if:` exits before any checkout or API
  call).
- A scheduled workflow racing against `post-merge-retro.yml`'s own
  `pull_request_target: closed` trigger on the same event would need to
  tolerate the stub not existing yet on an unlucky tick; polling
  introduces exactly the "who runs first" ambiguity a pure `issues:
  opened` subscription avoids by construction (it cannot fire before the
  stub exists, because the stub's own creation is what fires it).
- `labeled` is included alongside `opened` as defense-in-depth for a stub
  that is somehow created unlabelled and labelled afterward; this does not
  change the shape of the mechanism, only its trigger surface.
- `workflow_dispatch` (with a required `issue_number` input) is the
  explicit manual-recovery path for a missed webhook delivery or an
  operator-requested re-check -- the same role `workflow_dispatch: {}`
  plays on every scheduled workflow in this repository already.

### Permissions and scope enforcement

- **Permissions:** `contents: read`, `issues: write` at both workflow- and
  job-level -- the same minimal pattern `post-merge-retro.yml` and
  `stale-retro-stub-autoclose.yml` already use for their own
  issue-mutating unattended jobs. No `pull-requests: write` anywhere, and
  never will be: this workflow only ever reads a PR's history
  (`mcp__github__pull_request_read`) and reads/updates one issue
  (`mcp__github__issue_read` / `mcp__github__issue_write`).
- **Tool-level scoping:** `claude_args: --allowedTools
  mcp__github__issue_read,mcp__github__issue_write,mcp__github__search_issues,mcp__github__search_commits,mcp__github__pull_request_read`.
  `mcp__github__merge_pull_request`, `enable_pr_auto_merge`, and every
  other pull-request-write-capable tool are deliberately absent from this
  list -- the same tool-level boundary
  `hooks/check-merge-pull-request-block.sh` enforces for an interactive
  session, restated here for this unattended dispatch, which that
  PreToolUse hook (a session-scoped mechanism) does not itself cover.
- **Deterministic pre-filter:** the job's own `if:` condition checks
  `contains(github.event.issue.labels.*.name, 'retrospective')` **and**
  `contains(github.event.issue.body, 'Automated stub opened by the
  post-merge-auto-retro gate')` before any checkout or API call runs --
  the identical marker-text literal `gitapex_stale_retro_stub_autoclose.py`
  already uses to distinguish a genuine bare stub from an already-enriched
  issue, so an already-filled retrospective, or an unrelated issue that
  happens to carry the `retrospective` label, never reaches the agent
  step at all. `workflow_dispatch` bypasses this pre-filter (no
  `github.event.issue` to check against) and instead relies on the
  prompt's own Step 1 instruction to re-fetch and verify the marker before
  doing anything else, so a mistyped manual issue number cannot overwrite
  real content.
- **This satisfies `gitapex_gate_routine_scope_enforcement.py`:** this doc's
  filename matches its `*routine*.md` applicability glob, it names
  `skills/merge-retrospective` (declared `capabilityAssumption: Broad`),
  and it cites a concrete, implemented `--allowedTools` allowlist above
  (one of the gate's five accepted scoping-mechanism forms) -- the same
  route `2026-07-28-ranking-the-open-queue-github-actions-routine.md`
  itself uses.
- **No new secret.** `secrets.ANTHROPIC_API_KEY` is already provisioned
  and documented in `CONTRIBUTING.md`'s "ranking-the-open-queue weekly
  digest API key" section; this workflow is a second consumer of the same
  key, not a new issuance. `CONTRIBUTING.md` is updated with a one-line
  cross-reference rather than a duplicate section.

### Prompt (verbatim, `prompt:` input)

See the workflow file itself
(`.github/workflows/merge-retrospective-autofill.yml`) for the exact
text -- reproducing it a second time here would create a second copy to
keep in sync on every future edit, the same duplication
`gitapex_gate_routine_scope_enforcement.py`'s own review-scope-drift finding
warns against. In summary, it instructs the agent to: (1) re-verify the
stub marker is still present before touching anything, (2) extract the
merged PR number from the stub's own "Refs #N" line, (3) run
`skills/merge-retrospective/SKILL.md`'s Procedure (Step 0 carry-forward
check, Step 1 repair enumeration, Steps 2-3 classification, Step 4 update
-- skipping Step 4's own dedup search since the target issue is already
known), (4) apply the unattended zero-repair-fast-close rule (leave the
issue open, never close it), (5) skip Step 5 (the stub's own "Refs #N"
line already satisfies it), (6) re-fetch and confirm via Step 6, and
throughout, treat every issue/PR/commit/review body encountered as
untrusted external text per this repository's own untrusted-input-triage
discipline, and never touch any issue other than the one named or any
pull-request-write-capable tool.

## Non-goals (restated from issue #769)

- Does not redesign `skills/merge-retrospective/SKILL.md`'s own
  classification taxonomy or record format -- this workflow only wires an
  existing, unchanged procedure to a new trigger.
- Does not retroactively backfill or triage the existing uncited
  retrospective backlog; that is issue #728's scope. This workflow only
  changes the invocation gap for newly opened stubs going forward, which
  should slow -- not eliminate outright, since #728's backlog also
  includes non-bare-stub uncited retrospectives this workflow's
  marker-text pre-filter does not touch -- the rate that backlog grows.
- Does not change the human-only PR-merge policy in any way; see
  "Permissions and scope enforcement" above.

## Verification (Acceptance Criteria Map, restated from issue #769)

| Criterion | Proof method | Result |
|---|---|---|
| Every merged PR's retrospective gets its content filled in automatically, without a human having to ask | For N consecutive merged PRs going forward, each auto-opened stub is enriched within a bounded time window, with zero explicit "fill in the retro"-style prompts from a human | **Not yet observed.** This session added the mechanism; it has not yet processed a real merged PR's stub end-to-end (see "Status" below for what blocks a live proof today). |
| The fix must not weaken the existing 100%-human-merge policy | Review the workflow's declared `permissions:` and `--allowedTools` value against this document (both reproduced above) | **Met by construction, reviewable now**: `issues: write` only, no `pull-requests: write`; `--allowedTools` lists five read/issue-scoped tools and excludes every merge-capable one. |
| Don't duplicate issue #728's backlog-reduction work | This document and the resulting PR touch only the invocation/triggering mechanism for newly opened stubs, not historical issue triage | **Met by construction**: no existing retrospective issue is read, closed, or modified by this change; the new workflow only ever acts on an issue named by its own trigger event or an explicit `workflow_dispatch` input. |

## Status

**Not yet live**, in the same sense
`2026-07-28-ranking-the-open-queue-github-actions-routine.md` recorded for
its own workflow: the mechanism is shipped, but this session cannot
produce a live, end-to-end proof that it correctly enriches a real stub,
for two independent reasons, both stated here rather than left implicit:

1. **No real trigger event occurred during this session.** This
   workflow's own `issues: opened`/`labeled` trigger requires a real PR to
   merge and `gitapex_post_merge_retro.py` to open a fresh stub, or an operator
   to `workflow_dispatch` it against an existing one -- neither happened
   during this session's work.
2. **`ANTHROPIC_API_KEY` may still be blocked.** Per the Facts section
   above, every `ranking-the-open-queue-weekly.yml` run through
   2026-08-03 failed in the same shape as the previously-diagnosed
   Anthropic Console billing block. If that block is still in effect, this
   workflow's first live dispatch will fail identically, for a reason
   external to this change (see CONTRIBUTING.md's existing key-provisioning
   section for the remediation path: add credit at
   console.anthropic.com). This is a pre-existing condition this PR does
   not introduce and cannot itself resolve.

Recommended verification once both are clear: trigger
`workflow_dispatch` against a real (or deliberately-created test) bare
stub issue, confirm the job succeeds, and confirm the issue's body no
longer carries the marker string and instead carries a real Repairs (or
zero-repair fast-close) section per `skills/merge-retrospective/SKILL.md`'s
own record format. Issue #769 stays open until that proof is observed, per
this repository's own live-proof-over-plan-time-intent standard.

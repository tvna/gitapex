# Trusted-Bot Exemption for `independent-review-pending` (design)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-06. Not yet implemented.

## Problem

`independent-review-pending` is a required status check (`.github/rulesets/main.json`)
that blocks merge until a `## Independent review verdict` section naming the PR's
exact head commit is recorded in the PR body (`drafting-a-pr-to-merge` Step 8's own
recorded-verdict format; see `.github/scripts/gitapex_gate_independent_review_pending.py`).
It exists to close the race issue #1311 documented: a PR merged directly via the
GitHub UI after clean CI but before the mandatory Step 8 independent review had run
against it at all.

Dependabot's own PRs never carry this verdict section -- nobody runs
`drafting-a-pr-to-merge` against them -- so this check fails permanently for every
Dependabot PR. Measured directly against the live repository (2026-09-06):

- 6 open Dependabot PRs (#1521, #1522, #1523, #1524, #1525, #1267), the oldest open
  since 2026-08-23 (14 days).
- Sampled two (#1524, #1267) via `pull_request_read get_check_runs`: in both, all 17
  required status checks passed except `independent-review-pending`, which failed.
- `mergeable_state` could not be confirmed as `blocked` directly (GitHub computes it
  asynchronously and this session observed `unknown` on every fetch) -- the
  14-day-plus backlog is treated as sufficient circumstantial evidence that these
  PRs are in fact unmergeable, not as a substitute for that direct confirmation.

## Scope

### In scope

- Exempting **trusted bots only** (Dependabot today) from the human-verdict
  requirement, replacing it with a machine-checkable substitute for bot PRs.
- A new `.github/trusted-bots.yml` allowlist, with anti-spoofing identity checks
  (login + GitHub `user.type == "Bot"` + numeric `user.id`).
- CODEOWNERS coverage for the new allowlist file.

### Out of scope

- Any change to the verdict requirement for human- or agent-authored PRs (Claude
  Code sessions included) -- they keep the existing strict rule unchanged.
- Auto-merge or auto-approval of Dependabot PRs -- this design only unblocks the
  merge gate; merging itself stays a human action.
- A schema/drift-verification gate for `trusted-bots.yml` itself (e.g. an analogue
  of `gitapex_gate_ruleset_required_checks.py`) -- left as an implementation-phase
  decision (`planning-a-branch-from-an-issue` / `executing-a-branch-plan`), not
  resolved here.
- Making `main.json`'s current required-checks list live via `apply-rulesets.yml` --
  unrelated to this change; that dispatch remains a separate, human-gated action
  per `docs/runbooks/rulesets.md`.

## Architecture

```
PR event (opened/ready_for_review/synchronize/edited/reopened)
        |
        v
independent-review-pending.yml
        |
        +-- reads github.event.pull_request.user.{login,id,type}
        |
        v
gitapex_gate_independent_review_pending.py
        |
        +-- user matches an entry in .github/trusted-bots.yml
        |   (login AND id AND type=="Bot" all match)?
        |
   NO --+-- existing path, unchanged:
        |     parse PR body for '## Independent review verdict',
        |     require Verdict: CLEAN + Verified commit == head SHA
        |
   YES -+-- new bot path:
              1. read required check contexts from
                 .github/rulesets/main.json's `required_status_checks` rule
                 (type-discriminated -- main.json also carries deletion/
                 pull_request/commit_author_email_pattern/committer_email_pattern
                 rules that must NOT be read as check contexts, per PR #1843)
              2. exclude "independent-review-pending" itself from that list
              3. poll GitHub check-runs for the head SHA until every remaining
                 required context is completed (bounded by an extended job
                 timeout, ~15 min)
              4. PASS iff all completed successfully; FAIL on any failure/
                 cancellation or on timeout
```

### `.github/trusted-bots.yml` (new)

One entry per trusted bot:

```yaml
- login: "dependabot[bot]"
  id: 49699333
  type: "Bot"
  purpose: "Dependency version-bump PRs (nix/github-actions/uv ecosystems, see .github/dependabot.yml)"
```

`id: 49699333` is not a guess -- it is the same Dependabot GitHub App user id already
verified live in this repository's `commit_author_email_pattern`/
`committer_email_pattern` rules (`.github/rulesets/main.json`, added by PR #1843:
`49699333+dependabot[bot]@users.noreply.github.com`).

### CODEOWNERS

```
/.github/trusted-bots.yml @tvna
```

Same rationale as the existing `harden-checkout` entry: this file grants an
identity-based gate exemption, so an unreviewed edit could silently widen who
bypasses independent review.

### Timing (resolved via `architecture-tradeoff`)

Three options were compared for the async-completion problem (other required jobs
may still be running when `independent-review-pending` would otherwise evaluate
them):

1. Add a `check_suite: completed` trigger -- correct event-driven behavior, but a
   new, unprecedented pattern in this repository (default-branch workflow
   resolution, self-trigger-loop risk) with no existing analogue to build on.
2. Evaluate a point-in-time snapshot with no polling -- rejected: at PR-open time
   nearly every other job is still queued/running, so this would fail almost every
   single time with no automatic re-evaluation once the last job finishes.
3. **Poll from within the job itself, with an extended timeout** -- adopted. Fully
   self-contained (no changes to any other workflow file), matches this
   repository's existing one-job-per-workflow convention, and the polling cost is
   paid only on bot PRs (human/agent PRs keep the current near-instant check).

## Decision logic detail

- **Required-check extraction**: locate the single rule in `main.json`'s `rules`
  array with `type == "required_status_checks"` (mirroring the existing
  `rule_of_type()` helper pattern in `gitapex_gate_ruleset_required_checks.py`
  rather than re-deriving a parser), read `parameters.required_status_checks[].context`,
  and drop `"independent-review-pending"` from the result.
- **Bot identity match**: all three of login, numeric id, and `type == "Bot"` must
  match one `trusted-bots.yml` entry. Login alone is not sufficient -- GitHub's own
  user id is immutable and namespace-unique, closing the theoretical risk of a
  same-named non-bot account.
- **Poll outcome**:
  - all remaining required contexts `completed` with conclusion `success` or
    `neutral` -> PASS
  - any required context `completed` with any other conclusion (`failure`,
    `cancelled`, `timed_out`, `action_required`, `stale`) -> FAIL immediately
    (fail-closed default; no need to keep polling)
  - timeout reached with contexts still pending -> FAIL, message names which
    contexts never completed
  - poll interval (e.g. every 15-30s) is an implementation-phase choice, not
    fixed by this design

## Testing

Follows this repository's existing `.github/scripts/*.py` + `tests/test_*.py`
convention: direct-name-coverage tests for the new bot-branch functions, defeat
tests for a forged `trusted-bots.yml` entry (login match without id/type match),
and a test confirming `main.json`'s non-`required_status_checks` rule types are
never misread as check contexts (the PR #1843 concern this design explicitly
guards against).

## Residual risks

- Poll timeout value may need retuning if a required job's typical runtime grows
  (Premortem from the `architecture-tradeoff` round: pytest currently completes in
  ~3-4 minutes, well under the proposed 15-minute ceiling, but this is not a hard
  guarantee).
- Required-context names in `main.json` and actual check-run names can drift by
  rename; no dedicated drift gate for this specific coupling is added in this
  design (left to the implementation phase per Out of scope above).
- Anti-spoofing covers GitHub-account-level impersonation only; it does not
  cryptographically verify a check run's own content, matching this repository's
  existing single-operator trust model (same disclosed limit as
  `gitapex_gate_independent_review_pending.py`'s own module docstring).

## Rollback

Revert the PR implementing this design. No live branch-protection change is
required to roll back -- `main.json`'s required-checks list itself is unchanged;
only the gate script's internal logic and the new allowlist file are affected.

# Trusted-Bot Exemption for `independent-review-pending` (design)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-06, then revised twice
after independent review (`design-doc-adversarial-review` and, later,
`drafting-a-pr-to-merge` Step 8) found and closed 3 confirmed defects. This
document describes the settled design; Decision logic detail and Residual risks
below reflect the current, reviewed state.

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
- CODEOWNERS coverage for the new allowlist file and for `.github/rulesets/main.json`.

### Out of scope

- Any change to the verdict requirement for human- or agent-authored PRs (Claude
  Code sessions included) -- they keep the existing strict rule unchanged.
- Auto-merge or auto-approval of Dependabot PRs -- this design only unblocks the
  merge gate; merging itself stays a human action.
- A schema/drift-verification gate for `trusted-bots.yml` itself (e.g. an analogue
  of `gitapex_gate_ruleset_required_checks.py`) -- left as an implementation-phase
  decision, not resolved here.
- Making `main.json`'s current required-checks list live via `apply-rulesets.yml` --
  unrelated to this change; that dispatch remains a separate, human-gated action
  per `docs/runbooks/rulesets.md`.
- Cryptographic verification of a check run's own content, or of the head commit's
  author/committer email -- both stay unsigned, account-level signals, matching
  this repository's existing single-operator trust model (see Residual risks).

## Architecture

```
PR event (opened/ready_for_review/synchronize/edited/reopened)
        |
        v
independent-review-pending.yml
        |
        +-- reads github.event.pull_request.user.{login,id,type},
        |   .base.{sha,ref}, and github.event.repository.default_branch
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
   YES -+-- bot-identity match found; NEXT: trust-anchor + head-commit checks
        |
        v
   base.ref == repository's real default branch?
        |
   NO --+-- fall through to the existing human-verdict path (a PR retargeted
        |   to a different base branch cannot supply its own trust anchors)
        |
   YES -+-- fetch .github/trusted-bots.yml and .github/rulesets/main.json via
        |   the GitHub Contents API at base.sha -- never from this job's own
        |   working tree, which is the PR's own proposed content
        |
        v
   fetch head commit (author email, committer email) via GitHub API
        |
        +-- BOTH emails match that bot's own commit_author_email_pattern /
        |   committer_email_pattern entries in main.json (PR #1843)?
        |
   NO --+-- fall through to the existing human-verdict path (the PR's opener
        |   claims to be the bot, but this specific commit was not actually
        |   authored/committed by it)
        |
   YES -+-- bot path:
              1. read required check contexts from main.json's own
                 `required_status_checks` rule (type-discriminated -- other
                 rule types in the same file are never misread as contexts)
              2. exclude "independent-review-pending" itself
              3. poll GitHub check-runs for the head SHA until every
                 remaining context is completed (bounded by an extended job
                 timeout, ~15 min), re-deriving each context's own conclusion
                 from the latest snapshot on every iteration
              4. PASS iff all completed successfully; FAIL on any
                 failure/cancellation or on timeout
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

`trusted-bots.yml` deliberately carries no separate email field: the head-commit
identity check (Decision logic detail below) reads the email pattern straight out
of `main.json`'s own `commit_author_email_pattern`/`committer_email_pattern` rules,
so there is exactly one place this repository's own trusted-committer emails are
declared, not two that could drift apart.

### CODEOWNERS

```
/.github/trusted-bots.yml @tvna
/.github/rulesets/main.json @tvna
```

Same rationale as the existing `harden-checkout` entry: `trusted-bots.yml` grants
an identity-based gate exemption, so an unreviewed edit could silently widen who
bypasses independent review. `main.json`'s entry covers the same class of risk --
its `commit_author_email_pattern`/`committer_email_pattern` rules are equally
load-bearing for the head-commit identity check below.

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
- **Trust-anchor sourcing**: `.github/trusted-bots.yml` and `.github/rulesets/main.json`
  are fetched via the GitHub Contents API at the PR's own base commit
  (`github.event.pull_request.base.sha`), never read from this job's own working
  tree -- which for a `pull_request`-triggered workflow is the PR's own proposed
  content, and could otherwise let a PR widen its own bot-exemption eligibility by
  editing either file within its own diff. That base ref is trusted only when
  `github.event.pull_request.base.ref` equals `github.event.repository.default_branch`
  (the repository object's own field, never the PR's) -- a PR retargeted to a
  different, possibly unprotected base branch cannot supply forged trust-anchor
  content instead. Both files also carry a CODEOWNERS entry as defense in depth on
  top of this, not a substitute for it (a live GitHub Settings toggle this
  repository's own tracked files cannot themselves confirm is enabled).
- **Head-commit identity check**: even after a bot-identity match, fetch the head
  commit's own author email and committer email (one GitHub API call, same client
  the polling step already needs) and require **both** to match the corresponding
  pattern in `main.json`'s `commit_author_email_pattern`/`committer_email_pattern`
  rules -- not the PR's `user` field, which GitHub never updates on a later
  `synchronize`, and it is the head SHA's own commit identity that must be
  re-checked every time regardless of which event fired the workflow. A mismatch
  here (bot opened the PR, but this specific commit wasn't actually
  authored/committed by it) falls through to the existing human-verdict path --
  never silently treated as a pass and never treated as an outright hard FAIL
  either, since a legitimate human fix pushed to a bot-opened PR should still be
  reviewable the normal way.
- **Poll outcome**:
  - all remaining required contexts `completed` with conclusion `success`,
    `neutral`, or `skipped` -> PASS. `skipped` is included deliberately, matching
    `gitapex_gate_ruleset_required_checks.py`'s own documented principle that a
    `skipped` conclusion does not block a required status check on GitHub's own
    native merge logic.
  - any required context `completed` with any other conclusion (`failure`,
    `cancelled`, `timed_out`, `action_required`, `stale`) -> FAIL immediately
    (fail-closed default; no need to keep polling)
  - timeout reached with contexts still pending -> FAIL, message names which
    contexts never completed
  - a transient GitHub API error while polling (rate limit, 5xx) is retried
    within the same timeout budget rather than treated as an immediate FAIL or
    silently ignored; an error that persists until the timeout is reached is
    reported as a timeout FAIL naming which contexts could not be confirmed
  - every context's own conclusion is re-derived from the latest full check-runs
    snapshot on every poll iteration -- nothing is cached as permanently
    concluded once seen passing, so a context re-run (e.g. a manual "Re-run this
    job" click) into a worse conclusion mid-poll is still caught
  - poll interval (e.g. every 15-30s) is an implementation-phase choice, not
    fixed by this design

## Testing

Follows this repository's existing `.github/scripts/*.py` + `tests/test_*.py`
convention: direct-name-coverage tests for every new bot-branch function, defeat
tests for a forged `trusted-bots.yml` entry (login match without id/type match), a
head-commit email mismatch, a PR retargeted to a different base branch, and a
required check re-run into failure mid-poll; a test confirming `main.json`'s
non-`required_status_checks` rule types are never misread as check contexts (the
PR #1843 concern this design explicitly guards against).

## Residual risks

- Poll timeout value may need retuning if a required job's typical runtime grows
  (pytest currently completes in ~3-4 minutes, well under the 15-minute ceiling,
  but this is not a hard guarantee).
- Required-context names in `main.json` and actual check-run names can drift by
  rename; no dedicated drift gate for this specific coupling is added in this
  design.
- Anti-spoofing (bot identity, the head-commit email check, and trust-anchor-ref
  pinned to the repository's own default branch) closes every account-level and
  commit/ref-substitution attack path independent review found and reproduced,
  but none of it cryptographically verifies a check run's own content, or the
  head commit's email fields themselves (unsigned git metadata) -- matching this
  repository's existing single-operator trust model.
- Duplicate check-run reruns for the same context name: most-recent-by-timestamp
  is authoritative when more than one run exists for the same required context on
  the same head SHA, matching how GitHub's own required-status-check evaluation
  already behaves.
- A required check re-run without a `synchronize` event (e.g. a manual "Re-run
  failed jobs" click with no new commit) does not itself re-trigger this workflow,
  since its own triggers are `opened`/`ready_for_review`/`synchronize`/`edited`/
  `reopened` only -- a known operational workaround (an empty-diff `edited` event,
  or a fresh push) may be needed in that specific case, not solved by this design.

## Rollback

Revert the PR implementing this design. No live branch-protection change is
required to roll back -- `main.json`'s required-checks list itself is unchanged;
only the gate script's internal logic and the new allowlist file are affected.

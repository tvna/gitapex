# Trusted-Bot Exemption for `independent-review-pending` (design)

## Status

Design agreed via `eliciting-a-design` dialogue on 2026-09-06. Revised same day after
an independent adversarial review (`executing-a-branch-plan`'s pre-PR
`design-doc-adversarial-review`) found one CONFIRMED critical defect -- see
"Revision: head-commit identity check" below, folded into Architecture/Decision
logic detail/Residual risks. Revised again same day after `drafting-a-pr-to-merge`
Step 8's own independent review (against the implemented PR) found two more
CONFIRMED findings -- see "Second revision: trust-anchor ref pinning + poll
re-check fix" below.

### Revision: head-commit identity check (critical defect closed)

The first draft matched bot identity against `github.event.pull_request.user`
only -- the PR's **opener**, which GitHub does not change on a later
`synchronize` event. `dependabot/*` branches are not covered by this
repository's own branch protection (`main.json`'s `ref_name.include` is
`~DEFAULT_BRANCH` only), so anyone with push access could append a commit to
an open Dependabot PR's branch after the fact; the PR's `user` field would
still read `dependabot[bot]`, so the gate would take the bot path (CI-green
only) and silently skip the independent-review requirement for a commit
Dependabot never wrote -- defeating the exact protection issue #1311 exists
for, and contradicting this design's own "Out of scope: human/agent PRs keep
the existing rule unchanged" statement in practice, if not in wording.

Fix: the bot path additionally requires the **head commit's own** author and
committer email to match that bot's already-registered
`commit_author_email_pattern`/`committer_email_pattern` entries in
`main.json` (PR #1843) -- not a new, separately-maintained email field in
`trusted-bots.yml`, reusing the existing single source of truth instead of a
second copy that could drift from it. A commit whose author/committer PR
metadata says "opened by dependabot[bot]" but whose actual commit emails
don't match falls through to the existing human-verdict path, matching this
design's original intent rather than merely its original wording.

### Second revision: trust-anchor ref pinning + poll re-check fix (two Step 8 review findings closed)

`drafting-a-pr-to-merge`'s own Step 8 independent review (five parallel axis
reviewers against the implemented PR, not this design doc alone) found two more
CONFIRMED issues, verified by re-reading the actual workflow/CODEOWNERS/gate-script
files rather than accepted on the axis reviewers' own say-so:

1. **Trust anchors read from an untrusted ref.** `load_trusted_bots`/`load_ruleset`
   read `.github/trusted-bots.yml`/`.github/rulesets/main.json` off local disk, at
   a path relative to the running script's own location. `independent-review-pending.yml`'s
   checkout step passed no explicit `ref:`, so for a `pull_request`-triggered
   workflow `actions/checkout` resolves its own default -- the PR's own merge ref,
   i.e. the PR's own proposed content for both files, not a ref the PR itself cannot
   influence. Confirmed additionally that `.github/rulesets/main.json` had **no**
   CODEOWNERS entry at all (only `.github/trusted-bots.yml` did), so the one file
   the critical-defect fix above depends on entirely (point 2, Decision logic
   detail) carried zero forced-review protection.

   Fix: `main()` now accepts `--trust-anchor-ref`; the workflow passes
   `github.event.pull_request.base.sha` (a commit no PR ref can move). When given,
   both files are fetched via the GitHub Contents API (`fetch_repo_file_at_ref`)
   from that ref instead of local disk -- omitting the flag (every unit test)
   keeps the prior local-disk-read behavior unchanged. `.github/rulesets/main.json`
   also now carries the same `@tvna` CODEOWNERS entry `.github/trusted-bots.yml`
   already had, as defense in depth on top of the ref-pinning fix, not a substitute
   for it (a live GitHub Settings toggle this repository's own tracked files cannot
   themselves confirm is enabled).

2. **`poll_bot_required_checks` permanently remembered a context's first passing
   conclusion.** Once a required context was observed `completed`/passing on one
   poll iteration, the original implementation never looked at that context again
   for the rest of the same poll call (a `concluded` dict, checked-and-skipped on
   every later iteration). GitHub's own check-runs endpoint always returns the
   complete, current set for a head SHA (never a delta) -- so a context re-run
   (e.g. a manual "Re-run this job" click) into a *worse* conclusion after already
   being marked concluded would never be caught, and the poll could report an
   incorrect PASS naming "all required checks completed successfully" while one of
   them had, in fact, most recently failed.

   Fix: every context's own conclusion is now re-derived from the latest full
   check-runs snapshot on every iteration -- nothing is cached as permanently
   concluded once seen passing once. This also resolves the "Duplicate check-run
   reruns" residual risk below more completely than originally scoped: not only is
   the most-recent run per context authoritative within a single snapshot, but a
   later snapshot's worse conclusion for an already-seen-passing context is no
   longer silently ignored.

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
   YES -+-- bot-identity match (login+id+type) found; NEXT: head-commit check
        |
        v
   fetch head commit (author email, committer email) via GitHub API
        |
        +-- BOTH emails match that bot's own commit_author_email_pattern /
        |   committer_email_pattern entries in main.json (PR #1843)?
        |
   NO --+-- fall through to the existing human-verdict path above
        |   (the PR's opener claims to be the bot, but this specific commit
        |    was not actually authored/committed by it -- fail closed to the
        |    strict rule, never silently trust the PR-level identity alone)
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

`trusted-bots.yml` deliberately carries no separate email field: the head-commit
identity check (see the Revision note above and Decision logic detail below) reads
the email pattern straight out of `main.json`'s own
`commit_author_email_pattern`/`committer_email_pattern` rules, so there is exactly
one place this repository's own trusted-committer emails are declared, not two that
could drift apart.

### CODEOWNERS

```
/.github/trusted-bots.yml @tvna
/.github/rulesets/main.json @tvna
```

Same rationale as the existing `harden-checkout` entry: `trusted-bots.yml` grants
an identity-based gate exemption, so an unreviewed edit could silently widen who
bypasses independent review. `main.json`'s entry is the second-revision fix above
-- its `commit_author_email_pattern`/`committer_email_pattern` rules are equally
load-bearing for the critical-defect fix (Decision logic detail's own
"Head-commit identity check"), so an unreviewed loosening of either pattern is the
same class of risk.

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
- **Head-commit identity check** (closes the critical defect the Revision note
  above describes): even after a bot-identity match, fetch the head commit's own
  author email and committer email (one GitHub API call, same client the polling
  step already needs) and require **both** to match the corresponding pattern in
  `main.json`'s `commit_author_email_pattern`/`committer_email_pattern` rules. This
  runs regardless of which event fired the workflow (`opened`, `synchronize`, etc.)
  -- there is no special-casing by event type, since the PR's `user` field is
  static across `synchronize` but the head SHA is not, and it is the head SHA's own
  commit identity that must be re-checked every time. A mismatch here (bot opened
  the PR, but this specific commit wasn't actually authored/committed by it) falls
  through to the existing human-verdict path -- never silently treated as a pass
  and never treated as an outright hard FAIL either, since a legitimate human fix
  pushed to a bot-opened PR should still be reviewable the normal way, not
  permanently blocked by a bot-only code path that no longer applies to it.
- **Poll outcome**:
  - all remaining required contexts `completed` with conclusion `success`,
    `neutral`, or `skipped` -> PASS. `skipped` is included deliberately, matching
    `gitapex_gate_ruleset_required_checks.py`'s own documented principle that a
    `skipped` conclusion does not block a required status check on GitHub's own
    native merge logic (that script's module docstring) -- this design's poll
    outcome must not be stricter than GitHub's own blocking behavior for the same
    required-check list.
  - any required context `completed` with any other conclusion (`failure`,
    `cancelled`, `timed_out`, `action_required`, `stale`) -> FAIL immediately
    (fail-closed default; no need to keep polling)
  - timeout reached with contexts still pending -> FAIL, message names which
    contexts never completed
  - a transient GitHub API error while polling (rate limit, 5xx) is retried
    within the same timeout budget rather than treated as an immediate FAIL or
    silently ignored; an error that persists until the timeout is reached is
    reported as a timeout FAIL naming which contexts could not be confirmed,
    not conflated with an ordinary pending-check timeout
  - poll interval (e.g. every 15-30s) is an implementation-phase choice, not
    fixed by this design

## Testing

Follows this repository's existing `.github/scripts/*.py` + `tests/test_*.py`
convention: direct-name-coverage tests for the new bot-branch functions, defeat
tests for a forged `trusted-bots.yml` entry (login match without id/type match),
a test confirming `main.json`'s non-`required_status_checks` rule types are
never misread as check contexts (the PR #1843 concern this design explicitly
guards against), and -- the test this design's own critical-defect fix exists
for -- a test asserting that a bot-identity match (PR opener is `dependabot[bot]`)
with a head commit whose author/committer email does NOT match `main.json`'s
email-pattern rules falls through to the existing human-verdict path rather than
taking the bot path.

## Residual risks

- Poll timeout value may need retuning if a required job's typical runtime grows
  (Premortem from the `architecture-tradeoff` round: pytest currently completes in
  ~3-4 minutes, well under the proposed 15-minute ceiling, but this is not a hard
  guarantee).
- Required-context names in `main.json` and actual check-run names can drift by
  rename; no dedicated drift gate for this specific coupling is added in this
  design (left to the implementation phase per Out of scope above).
- Anti-spoofing (PR-opener identity plus the head-commit email check) closes the
  account-level and commit-substitution risks this session's independent design
  review actually found and reproduced as a concrete attack path, but it still does
  not cryptographically verify a check run's own content -- matching this
  repository's existing single-operator trust model (same disclosed limit as
  `gitapex_gate_independent_review_pending.py`'s own module docstring).
- Duplicate check-run reruns for the same context name: most-recent-by-timestamp
  is authoritative when more than one run exists for the same required context on
  the same head SHA, matching how GitHub's own required-status-check evaluation
  already behaves -- and (second revision above) every context's own conclusion is
  now re-derived from a fresh snapshot on every poll iteration rather than cached
  once seen passing, so a same-poll-session rerun into a worse conclusion is still
  caught, not only the single-snapshot tie-break this bullet originally scoped.
- A required check re-run without a `synchronize` event (e.g. a manual "Re-run
  failed jobs" click with no new commit) does not itself re-trigger this workflow,
  since its own triggers are `opened`/`ready_for_review`/`synchronize`/`edited`/
  `reopened` only -- a known operational workaround (an empty-diff `edited` event,
  or a fresh push) may be needed in that specific case, not solved by this design.

## Rollback

Revert the PR implementing this design. No live branch-protection change is
required to roll back -- `main.json`'s required-checks list itself is unchanged;
only the gate script's internal logic and the new allowlist file are affected.

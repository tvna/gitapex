# CI/CD-specific gate cluster: auto-retro + broader CI-plane candidates

Design-only companion doc for a new tracking issue, child of #82, expanding
#123's seed-gate scope. Follows the structural pattern established by
#138 and #139: per-gate concrete `.gitapex/ssot.json` registry JSON,
explicit reconciliation notes, non-goals, acceptance criteria.

## Origin

User request (2026-07-18): "gitapexへの追加要件で、CI/CDから呼び出された時に
上流にある各種ゲート処理やauto_retro機構など、CI/CD固有の処理を追加したいです。"
(New requirement: add CI/CD-specific processing invoked from CI/CD — the
upstream gate mechanisms and the auto_retro system.)

Four Fable subagents were dispatched in parallel against primary sources
(`tvna/claude-md`'s real scripts, gitapex's own existing files) to design:
1. the auto-retro core trigger + dedup mechanism,
2. the three anti-interference protection gates around it,
3. the TP/FP convergence loop + sentinel + label taxonomy,
4. a broader survey of the sibling's CI-plane automation for gate
   candidates not already captured by #138 or the retro cluster.

**Provenance note (fact vs. reconstruction, updated 2026-07-18):**
sections 1 and 3 were originally reconstructed from a compacted session
summary rather than primary source, because the subagent transcripts that
produced them had rotated out of the local task-output store. A dedicated
verification pass has since re-read `scripts/auto_retro.py`,
`scripts/post_merge_retro_append.py`, `scripts/_auto_retro_ledger.py`,
`scripts/scan_retro_followup_drift.py`, `scripts/_retro_labels.py`,
`scripts/_trusted_bots.py`, `.github/workflows/post-merge.yml`, and
`.github/workflows/daily-maintenance.yml` in full at `/workspace/claude-md`
and corrected every filename, plane, trigger, and label-taxonomy value
that turned out to be wrong — which was most of them. Sections 1 and 3
below are now fact-grounded, not speculation-grade; each corrected value
notes what the original draft claimed versus what the source actually
shows. Sections 2 and 4 remain as originally reproduced near-verbatim
from their own subagents, each independently grounded in files read in
full at `/workspace/claude-md`.

## Cross-cutting reconciliation

Three subagents each independently proposed a cluster tag for the retro
gate family: `retro-loop` (subagent 1), `retro-integrity` (subagent 2),
`retro-convergence` (subagent 3). **Resolved: all retro-family gates use
`"cluster": "retro-integrity"`.** Rationale: "integrity" is the only one
of the three that plausibly spans all three roles (triggering, protecting,
converging) without implying a narrower scope than the others cover;
subagent 2 also independently grounded its naming in gitapex's own
existing retrospective convention rather than blindly importing the
sibling's, which is the more rigorous derivation of the three.

Two subagents proposed overlapping `policy_sources[]` entries for the
retro title/identity shape: subagent 1's `retro-conventions` (title
format, dedup search shape, wait bound, ledger config) and subagent 2's
`retro-identity` (title pattern, label, reserved prefixes, retro-close
pattern, closing keywords). **Resolved:** `retro-identity` is the single
source of truth for the identity predicate (subagent 2's explicit
single-import design, and the one independently cross-checked against
gitapex's REAL existing convention in `skills/merge-retrospective/SKILL.md`
— title prefix `Merge retrospective: PR #N` + label `retrospective`, not
the sibling's literal `(auto-retro)` Conventional Commit scope). The
non-identity operational fields from subagent 1 (dedup search shape, wait
bound, ledger path) move to a new, narrower `retro-operations` policy
source that references `retro-identity` rather than duplicating it.

**Important divergence from the sibling to carry forward:** because
gitapex's real retro convention differs from claude-md's, the "reserved
scope" gate 3(a) below reserves the *title prefix* `Merge retrospective:`
for the CI job only, not a `(auto-retro)` Conventional Commit scope —
adapt the mechanism, not the literal string.

## 1. Auto-retro core cluster (verified 2026-07-18 against `auto_retro.py` et al.)

Post-merge trigger that opens the retrospective issue, an in-process dedup
check, and a separate agent-facing hint that prevents an interactive
session from opening a redundant one.

**Corrections from the original draft, each fact-checked against primary
source:**

1. Draft claimed the opener is `scripts/post_merge_retro_append.py`; the
   actual CI opener is `scripts/auto_retro.py run`, invoked by
   `.github/workflows/post-merge.yml`'s `open-retro` job.
   `post_merge_retro_append.py` is a different mechanism entirely: an
   agent-side PostToolUse hook on `mcp__github__merge_pull_request` that
   emits `additionalContext` telling the interactive agent not to open a
   duplicate retro or redundant repair comment (fail-open). It is real,
   but it is a third gate, not the opener — added below as
   `merge-retro-dedup-agent-hint`.
2. Draft claimed dedup lives in `scripts/_auto_retro_ledger.py`; the
   actual dedup is `search_retro_issues()` inside `auto_retro.py` itself
   (query `repo:{repo} type:issue in:title "PR #{n}" "retro"`, open+closed).
   `_auto_retro_ledger.py` is the repair-free merge-rate ledger (a weekly
   snapshot), unrelated to dedup.
3. Draft claimed trigger `pull_request closed (merged=true)`; the actual
   trigger is `pull_request_target: types [closed]` with a job-level
   `if: github.event.pull_request.merged == true`.
4. Draft's policy-input fields were under-specified; confirmed real
   values: trusted-bot allowlist is `.github/trusted_bots.toml`
   (fail-open to a hardcoded fallback list); required sections are Scope,
   Facts, Proposed work, Verification, Acceptance criteria; the retry
   backoff on the merge SHA is 4 attempts at 2/4/8s. Two skip conditions
   the draft missed entirely: zero-inline-review-comment merges (recorded
   in the ledger, no retro opened in claude-md) and a label-derived
   false-positive prior (skip when historical FP rate >=0.5,
   tentative-only >=0.3, with a minimum sample size of 5).
5. A third daily job the draft missed: `auto_retro.py post-merge-rescan`,
   a 24-48h checklist rescan on already-opened retros — added below.

**Deliberate deviation from claude-md's own zero-comment skip (caught in
PR #146 review, applied 2026-07-18):** claude-md's own skip on
zero-inline-review-comment merges does not carry over to gitapex as-is.
gitapex's CLAUDE.md section 3 states "auto-open a retrospective issue"
after each merge with no comment-count carve-out, and a comment-free
merge is exactly the small or already-clean change most likely to
recur -- skipping it silently removes the feedback loop for the PRs it
would catch most cheaply. `post-merge-auto-retro` below therefore always
opens a retrospective on merge; the zero-comment signal is retained only
as a ledger annotation (feeding #142's repair-free-merge quality signal)
and the trusted-bot / dedup / FP-prior skips are unchanged, since those
three are genuine no-new-information cases (bot-authored, already
tracked, or historically noise) rather than a size/comment-count proxy
for "probably fine."

```jsonc
// policy_sources[]
{ "id": "retro-operations", "path": ".gitapex/policies/retro-operations.toml", "format": "toml",
  "authority": "auto-retro operational config: dedup search shape (in:title \"PR #N\" + \"retro\", open+closed), merge-SHA retry backoff (4 attempts, 2/4/8s), post-merge rescan window (24-48h), FP-prior thresholds (skip >=0.5, tentative-only >=0.3, min sample 5); identity predicate itself lives in retro-identity, imported not copied" },
{ "id": "trusted-bots", "path": ".gitapex/policies/trusted-bots.toml", "format": "toml",
  "authority": "actor allowlist (exact logins, fail-open to a built-in fallback) whose authored/merged PRs skip retro opening" },
{ "id": "issue-required-sections", "path": ".gitapex/policies/issue-required-sections.toml", "format": "toml",
  "authority": "required body sections for an auto-opened retro issue: Scope, Facts, Proposed work, Verification, Acceptance criteria" }

// gates[]
{ "id": "post-merge-auto-retro", "kind": "script", "script": "scripts/auto_retro.py",
  "rule": "on merged-PR close, always open a retrospective issue titled/labeled per retro-identity, seeded with required sections (per CLAUDE.md section 3's unconditional after-each-merge rule -- no comment-count carve-out); skip only on retro-PR recursion, trusted-bot actor, existing retro (dedup search), or a high false-positive prior; a zero-inline-review-comment merge still opens a retro, annotated with a ledger row rather than skipped",
  "planes": ["ci"], "trigger": "pull_request_target closed + if merged==true (subcommand: run)",
  "policy_refs": ["retro-identity", "retro-operations", "trusted-bots", "issue-required-sections"],
  "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "merge-retro-dedup", "kind": "script", "script": "scripts/auto_retro.py",
  "rule": "before opening, search open+closed issues matching retro-identity for the same source PR; an existing match skips creation rather than duplicating (in-process search_retro_issues, not a separate script)",
  "planes": ["ci"], "trigger": "invoked inside post-merge-auto-retro's run() before issue creation",
  "policy_refs": ["retro-identity", "retro-operations"],
  "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "merge-retro-dedup-agent-hint", "kind": "script", "script": "scripts/post_merge_retro_append.py",
  "rule": "PostToolUse hook on the merge tool: instruct the interactive agent not to open a duplicate retro or redundant repair comment; fallback creation only if the CI opener never ran",
  "planes": ["posttooluse"], "trigger": "mcp__github__merge_pull_request",
  "fail_policy": "open",
  "policy_refs": ["retro-identity"], "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "retro-post-merge-rescan", "kind": "script", "script": "scripts/auto_retro.py",
  "rule": "rescan an already-opened retro's checklist 24-48h after the triggering merge, catching repair signals that only surfaced after CI settled",
  "planes": ["ci"], "trigger": "scheduled (daily) + workflow_dispatch (subcommand: post-merge-rescan)",
  "policy_refs": ["retro-identity", "retro-operations"],
  "cluster": "retro-integrity", "tracking_issue": 140 }
```

## 2. Retro-integrity protection cluster (subagent 2, verbatim design)

The shared invariant: **an issue or PR is a retrospective if and only if
the single registered retro-identity predicate — defined once in
`.gitapex/policies/retro-identity.toml` and imported by every consumer —
says so; the auto-retro mechanism, all three gates below, and any CI
backstop evaluate that one predicate and never re-derive it.** This
mirrors `gate_reserved_retro_scope.py`'s explicit discipline (imports
`auto_retro.is_retro_issue_title`/`is_retro_pr` rather than re-deriving
the match, "so the gate can never drift from the detectors it protects").

```toml
# .gitapex/policies/retro-identity.toml
[retro_issue]
title_pattern = '(?i)^chore\(retrospective\): merge retrospective for PR #\d+'
label = "retrospective"
[reserved]                     # agent-mintable NEVER; auto-retro CI job only
title_prefixes = ["chore(retrospective): merge retrospective for PR #"]
[retro_close_pr]
title_pattern = '(?i)^chore\(retro-close\):'
[closing_keywords]
keywords = ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"]
```

**Correction (2026-07-25, issues #341/#342):** the `title_pattern` and
`title_prefixes` above were originally `'(?i)^Merge retrospective: PR
#\d+'` / `["Merge retrospective:"]`, on this doc's own claim (line 59-60
above) of having cross-checked gitapex's "REAL existing convention"
against `skills/merge-retrospective/SKILL.md`. That check itself was
wrong: it read the SKILL.md's own generic *fallback* title shape (which
the SKILL.md text explicitly labels as "only a fallback for repos that
have neither" a template nor their own convention) as if it were this
repo's actual practice, without checking real prior retrospective issues.
Issue #118 (2026-07-16, predating this design doc by two days) already
used the real, established convention: `chore(retrospective): merge
retrospective for PR #N`. `.github/scripts/post_merge_retro.py` (#314's
already-shipped minimal slice) inherited this doc's original mistake and
was corrected in #341/#342 to match the real convention -- the TOML above
is updated to match so that if this cluster is ever implemented from this
doc, its reserved-title gate would actually recognize the issues the
shipped code creates, instead of silently failing to reserve/protect them.
The surrounding prose in this section is left as the historical record of
what was decided and why at the time; only the machine-readable pattern
values are corrected, since those are meant to be copied verbatim into a
future real policy file.

**(a) `retro-reserved-title-issue-create`** adapts `gate_reserved_retro_scope.py`
(incident #1395: an agent-titled issue satisfying the retro predicate
tripped the sibling's `verify-no-direct-retro-pr` CI gate). gitapex has no
native write tool to guard directly — #126 makes MCP-server mode
advisory-only, and #82/CLAUDE.md section 3 routes writes through
platform-integrated tools "paired with a PreToolUse safety hook" — so the
analogous surface is `mcp__github__issue_write` with `method: "create"`,
the same tool the `merge-retrospective` skill already uses. Deny when the
title matches `[reserved].title_prefixes` or `[retro_issue].title_pattern`.
Fully closed, no exceptions, no ack marker.

**(b) `retro-link-pr-body`** adapts `gate_pr_body_retro_issue_link.py`.
Surface: `mcp__github__create_pull_request`/`update_pull_request` at
pretooluse, plus a `ci` plane mirroring the sibling's
`verify-no-direct-retro-pr` (one gate id, two planes, matching #138's
Gate 3/4 pattern). Deny when the body references an issue whose fetched
title satisfies the retro predicate, unless the PR title matches
`[retro_close_pr]`.

**(c) `retro-close-keyword-commit`** adapts `gate_retro_close_keyword_commit.py`
(incident: a buried `Closes #<retro>` in a commit message survived because
force-push and branch deletion are both blocked on session branches, and
squash-merge would have auto-closed the retro irreversibly). **Placement:
extend `hooks/check-bash-safety.sh`, not #138 Gate 5's `irreversible-ops`
registry** — `git commit` is not itself irreversible; only a commit
closing a *live retro issue* is, and that requires a per-call remote title
lookup the data-only irreversible-ops schema can't express. This becomes
`check-bash-safety.sh`'s Finding 5 and its first network-dependent check,
with a `# retro-close-ack` escape marker.

### Fail policy, argued per gate (not blanket-copied)

- **(a): fail-open.** Pure local string predicate, zero I/O — no
  INDETERMINATE state for #131 principle 6 to bite on.
- **(b): fail-open, with a registered backstop obligation.** Token-absent
  or lookup-failure is genuine INDETERMINATE, but nothing irreversible
  happens at PR-create time (a body is editable) and the `ci` plane of
  the same gate is the fail-closed backstop with guaranteed credentials.
  Zero-trust addition: the registry entry must name its backstop, and a
  registry-hygiene lint (see candidate 8 below) verifies the named
  backstop gate actually exists.
- **(c): fail-CLOSED on indeterminate lookup — the one deliberate
  divergence from the sibling's fail-open default.** By CI time the
  keyword commit already exists and can't be rewritten out (per the cited
  incident); pre-commit is the last point where the wrong action is
  cheaply reversible, exactly where #131 principle 6 ("inability to
  verify is a deny") applies. A crash in the hook's own parsing still
  exits 0 — fail-open on hook bugs, fail-closed on unverifiable retro
  matches are two different failure classes.

```jsonc
// gates[]
{ "id": "retro-reserved-title-issue-create", "kind": "script", "script": "scripts/gate_retro_reserved_title.py",
  "rule": "an agent-issued issue_write create whose title matches the reserved retro-identity shapes is denied, no exceptions",
  "planes": ["pretooluse"], "trigger": "mcp__github__issue_write with method create",
  "fail_policy": "open (no I/O; out-of-scope input is pass-through, not indeterminate)",
  "policy_refs": ["retro-identity"], "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "retro-link-pr-body", "kind": "script", "script": "scripts/gate_retro_link_pr_body.py",
  "rule": "a PR body referencing an issue matching the retro-identity predicate is denied unless the PR title matches the retro-close pattern",
  "planes": ["pretooluse", "ci"],
  "trigger": "pretooluse: mcp__github__create_pull_request|update_pull_request; ci: pull_request opened/edited/synchronize",
  "fail_policy": "pretooluse open on token/lookup failure; ci plane is the fail-closed backstop",
  "backstop": "retro-link-pr-body@ci",
  "policy_refs": ["retro-identity"], "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "retro-close-keyword-commit", "kind": "script", "script": "hooks/check-bash-safety.sh",
  "rule": "a git commit whose message carries a closing keyword for an issue matching the retro-identity predicate is denied before the commit exists; # retro-close-ack opts in",
  "planes": ["pretooluse"], "trigger": "Bash tool use containing a git commit invocation",
  "fail_policy": "closed on indeterminate title lookup for a keyword-matched commit; open on hook-internal parse failure",
  "policy_refs": ["retro-identity"], "cluster": "retro-integrity", "tracking_issue": 140 }
```

## 3. Retro-convergence cluster (verified 2026-07-18 against `scan_retro_followup_drift.py` et al.)

TP/FP feedback loop over closed retro follow-up items, plus a sentinel
that auto-closes stale retros after a bounded inactivity window, plus the
label taxonomy both draw on.

**Corrections from the original draft, each fact-checked against primary
source:**

1. Draft claimed the drift scan runs weekly; the actual schedule is
   **daily** (`.github/workflows/daily-maintenance.yml`, cron
   `0 4 * * *`, job `scan`, `scan_retro_followup_drift.py run`).
2. Draft guessed a 5-label taxonomy of "retrospective, gate-candidate,
   false-positive, drift-confirmed, sentinel-closed" — the count of 5 was
   right, every name was wrong. The real taxonomy (`_retro_labels.py`) is
   `retro:tp`, `retro:fp`, `retro:fp-candidate`, `retro:tentative`,
   `retro:expired`.
3. Draft invented `scripts/retro_sentinel.py`; the real sentinel is
   `scripts/auto_retro.py sentinel`, same workflow, job `scan-and-close`:
   applies `retro:expired`, posts an idempotency-marker comment, closes as
   `not_planned`.
4. Draft claimed `sentinel_inactivity_days=30`; the actual default is
   **14** (env-overridable). `stale_days=30` for the drift scan itself
   was correct.

```jsonc
// policy_sources[]
{ "id": "retro-convergence-policy", "path": ".gitapex/policies/retro-convergence.toml", "format": "toml",
  "authority": "label taxonomy (retro:tp, retro:fp, retro:fp-candidate, retro:tentative, retro:expired), stale_days=30, sentinel_inactivity_days=14 (env-overridable)" }

// gates[]
{ "id": "retro-followup-drift", "kind": "script", "script": "scripts/scan_retro_followup_drift.py",
  "rule": "scan retro follow-up links for TP/FP convergence signal; a not_planned close or unmerged-PR close confirms retro:fp, a 404 or >=stale_days inactivity marks retro:fp-candidate; never overwrite an operator-applied retro:tp/retro:fp",
  "planes": ["ci"], "trigger": "scheduled (daily 04:00 UTC) + workflow_dispatch (subcommand: run)",
  "policy_refs": ["retro-identity", "retro-convergence-policy"],
  "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "retro-sentinel", "kind": "script", "script": "scripts/auto_retro.py",
  "rule": "close an untouched open retro after sentinel_inactivity_days (14) as not_planned: apply retro:expired, post a marker comment for idempotency, then close; retro:expired never feeds the TP/FP prior",
  "planes": ["ci"], "trigger": "scheduled (daily 04:00 UTC) + workflow_dispatch (subcommand: sentinel)",
  "policy_refs": ["retro-identity", "retro-convergence-policy"],
  "cluster": "retro-integrity", "tracking_issue": 140 }
```

## 4. Broader CI-plane candidates (subagent 4, verbatim design)

Survey scope: 27 workflow files and ~180 scripts (20 `gate_*`, ~35
`scan_*`, ~26 `preflight_*`) in `/workspace/claude-md`, excluding anything
already captured by #138 or the retro cluster above.

**Negative finding (fact):** a "workflow-permissions least-privilege
scanner" does not exist as a script in the sibling repo — least-privilege
auditing there lives only in a hand-maintained matrix
(`docs/runbooks/workflow-permissions-audit.md`); zizmor appears only as a
measurement subject in `measure-tool-overlap.yml`, not a gate. gitapex
could build one for #131, but there is no sibling artifact to adapt, so
it is not proposed as a candidate here.

### Candidate 1 (top priority): registry self-validation

`scan_ssot_schema.py` validates the registry's own shape (draft-2020-12
subset) plus referential integrity JSON Schema can't express — every
`gates[].script` resolves to a tracked file, every `policy_refs[]` names a
real `policy_sources[].id`. `scan_ssot_drift.py` is a blocking CI gate
reconciling the registry's claimed `planes` against the authoritative
manifests (agent hooks, preflight steps, pre-commit config, rulesets).
Maps directly to CLAUDE.md section 3's "ship the drift gate in the same
change" — without this, gitapex's own #123 registry is documentation, not
an SSoT. This is the meta-gate every other registry entry in this doc
depends on, including the backstop-existence check gate 2(b) above needs.

```jsonc
{ "id": "registry-self-validation", "kind": "script", "script": "scripts/scan_ssot_schema.py",
  "planes": ["ci", "pre-commit"],
  "trigger": "pull_request touching .gitapex/** or any manifest a registry entry references",
  "policy_refs": ["ssot-schema"], "cluster": "registry-integrity", "tracking_issue": 140 },
{ "id": "registry-plane-drift", "kind": "script", "script": "scripts/scan_ssot_drift.py",
  "planes": ["ci"], "trigger": "pull_request touching .gitapex/**",
  "policy_refs": ["ssot-schema"], "cluster": "registry-integrity",
  "policy": "advisory first, promote to blocking once clean", "tracking_issue": 140 }
```

### Candidate 2: fail-closed merge-safety gate

`gate_merge_safety.py`: PreToolUse gate on `mcp__github__merge_pull_request`
allowing merge only when `mergeable == true` AND `mergeable_state ==
"clean"`. Uniquely fail-closed among the sibling's gates (missing token,
API failure, or poll-budget expiry denies) and marked non-downgradable by
audit mode. Reinforces CLAUDE.md section 3's existing `mergeable_state`
bullet and section 4's irreversible-operation guard — a rule gitapex
already states but does not yet enforce.

```jsonc
{ "id": "merge-safety", "kind": "script", "script": "hooks/gate_merge_safety.py",
  "planes": ["pretooluse"], "trigger": "PreToolUse matcher mcp__github__merge_pull_request",
  "policy_refs": ["claude-md-s3-mergeable-state", "claude-md-s4-irreversible"],
  "fail_policy": "closed", "audit_downgradable": false,
  "cluster": "merge-safety", "tracking_issue": 140 }
```

### Candidate 3: GitHub CLI routing gate

`gate_gh_cli.py`: PreToolUse Bash gate denying `gh <subcommand>` and raw
`curl` to `api.github.com`, deliberately fail-open (the event envelope is
harness-generated, so fail-closed buys no assume-breach benefit while
wedging all Bash). Directly enforces CLAUDE.md section 3's existing "Do
not invoke command-line GitHub tools directly" rule, which currently has
no gate — the same gap class candidate 1 closes for the registry itself.

```jsonc
{ "id": "github-cli-routing", "kind": "script", "script": "hooks/gate_gh_cli.py",
  "planes": ["pretooluse"], "trigger": "PreToolUse matcher Bash",
  "policy_refs": ["claude-md-s3-no-cli-github"], "fail_policy": "open",
  "cluster": "cli-routing", "tracking_issue": 140 }
```

### Candidate 4: workflow action SHA-pinning

`scan_workflow_action_pins.py`: requires every workflow `uses:` reference
to be a full 40-char SHA with a human-readable `# <tag>` comment; skips
local and `docker://` refs; per-line CI annotations; ack-marker escape
hatch. Reinforces CLAUDE.md section 3's "manage modules declaratively...
block drift and supply-chain attacks," extended from language deps to the
Actions supply chain. gitapex has 6 workflows today with no pin
enforcement.

```jsonc
{ "id": "workflow-action-pins", "kind": "script", "script": "scripts/scan_workflow_action_pins.py",
  "planes": ["ci", "pre-commit"], "trigger": "pull_request touching .github/workflows/**",
  "policy_refs": ["claude-md-s3-declarative-deps"], "ack_marker": "<!-- action-pin-ack -->",
  "cluster": "supply-chain", "tracking_issue": 140 }
```

### Candidate 5 (marginal, defer): CI wall-time budget

`analyze_ci_timings.py` + `ci_budget_issue.py`: offline p50/p95/max
analysis with an alerting (never blocking) rolling tracking issue on
budget breach — deliberately advisory since runner wall time is
non-deterministic. This is the sibling's answer to CLAUDE.md section 5's
"measured proportion of quality to volume degrades, stop and re-plan,"
the gap #138 explicitly flagged as not yet gate-able. It partially solves
it (makes the signal observable and tracked) but correctly refuses to be
a blocking gate. Verdict: adopt the pattern, defer implementation —
gitapex's CI surface is too small today for the payoff.

```jsonc
{ "id": "ci-wall-time-budget", "kind": "script", "script": "scripts/analyze_ci_timings.py",
  "planes": ["ci-scheduled"], "trigger": "weekly schedule + workflow_dispatch",
  "policy_refs": ["claude-md-s5-quality-scale"],
  "policy": "advisory-only; rolling issue, never a required check",
  "cluster": "quality-scale", "status": "deferred", "tracking_issue": 140 }
```

### Considered and rejected (subagent 4)

- **Commit signing** (`check_commit_signing_ready.py`): an elegant live-probe
  design (test-signs in a throwaway repo rather than proxy-checking key
  files), but serves the sibling's remote-session signer program and
  ruleset-protected-branch environment. gitapex's CLAUDE.md has no signing
  rule; adopting would require new prose, and the mechanism is too
  environment-specific to redistribute. Skip.
- **Security drift aggregation** (`security_drift_report.py`): aggregates
  over family detectors (rulesets, labels, uv pins) gitapex doesn't have
  yet; premature until those families exist.

### Prioritization (subagent 4)

For gitapex as a redistributed CLI governance tool: **candidate 1
(registry self-validation) is essential** — it makes #123's registry real
and is itself redistributable to every consumer repo. **Candidates 2
(merge-safety) and 3 (gh-cli routing)** are next: both close gaps between
existing CLAUDE.md prose and enforcement, both small and portable.
**Candidate 4 (action pins)** is worthwhile but lower urgency given
gitapex's small workflow surface today. **Candidate 5 (CI budget)** is
the most sibling-scale-specific — record it as `deferred` so the
section-5 gap stays visible, don't build it yet.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` or `hooks/` edits in this
  pass — registry JSON and policy TOML above are design artifacts for a
  future implementation phase.
- Not re-litigating #138's already-designed gates (PR-body quality,
  non-ASCII/provenance, module-size, irreversible-bash, untrusted-text
  advisory) or #139's gh-api wrapper design.
- Not designing the workflow-permissions least-privilege scanner #131
  flags as a gap — no sibling artifact exists to adapt from; a future pass
  can design it from scratch if prioritized.

## Acceptance criteria

- [x] Sections 1 and 3 re-verified 2026-07-18 against primary source
      (`auto_retro.py`, `post_merge_retro_append.py`,
      `scan_retro_followup_drift.py`, `_retro_labels.py`,
      `_trusted_bots.py`, and both workflow files); every filename,
      plane, trigger, and label value corrected to match. No longer
      speculation-grade.
- [ ] All 15 gates (4 core + 3 protection + 2 convergence + 5 broader
      candidates, one marked deferred + 1 rescan gate found during
      verification) have concrete registry JSON above.
- [ ] Cluster-naming conflict (`retro-loop`/`retro-integrity`/`retro-convergence`)
      resolved to a single `retro-integrity` tag.
- [ ] `policy_sources[]` overlap (`retro-conventions`/`retro-identity`)
      resolved: `retro-identity` is the sole identity predicate source,
      imported by all seven retro-family gates; operational config split
      into `retro-operations`.
- [ ] Retro-identity predicate grounded in gitapex's own existing
      convention (`skills/merge-retrospective/SKILL.md`), not blindly
      copied from the sibling's `(auto-retro)` scope convention.
- [ ] Fail-policy argued per gate, not blanket-copied from the sibling.
- [ ] Provenance of reconstructed vs. directly-sourced sections disclosed.

## Related Issue

Child of #82. Expands #123's seed-gate scope, same as #138 and #139.
Cross-references #126 (MCP-server mode, cited for gate 2(a)'s tool-surface
argument), #131 (zero-trust principles, cited for fail-policy arguments),
#138 (Gate 5's irreversible-ops registry, cited for the gate 2(c)
placement decision).

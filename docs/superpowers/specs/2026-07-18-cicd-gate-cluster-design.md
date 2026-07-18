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

**Provenance note (fact vs. reconstruction):** subagents 2 (protection)
and 4 (broader survey) are reproduced below near-verbatim from their
returned reports, each independently grounded in files read in full at
`/workspace/claude-md`. Subagents 1 (core trigger) and 3 (convergence
loop) ran earlier in the same session; their full transcripts rotated out
of the local task-output store before this synthesis pass, so their gate
JSON below is reconstructed from the session's design record (gate ids,
cluster names, and policy_sources names as returned) rather than
re-quoted from primary text. The reconstruction follows the exact schema
verified live in subagents 2 and 4. This is flagged, not hidden, per
CLAUDE.md section 2's fact/speculation separation — treat the core-cluster
and convergence-cluster JSON as **speculation-grade** (schema-consistent,
not independently re-verified against `auto_retro.py`) until a follow-up
pass re-reads the source scripts directly.

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

## 1. Auto-retro core cluster (reconstructed, see provenance note)

Post-merge trigger that opens the retrospective issue, plus a dedup check
so re-triggers (re-runs, retries) don't mint duplicates.

```jsonc
// policy_sources[]
{ "id": "retro-operations", "path": ".gitapex/policies/retro-operations.toml", "format": "toml",
  "authority": "auto-retro operational config: dedup search shape, post-merge wait bound, ledger path; identity predicate itself lives in retro-identity, imported not copied" },
{ "id": "trusted-bots", "path": ".gitapex/policies/trusted-bots.toml", "format": "toml",
  "authority": "actor allowlist for bot-authored events the auto-retro CI job trusts as merge signals" },
{ "id": "issue-required-sections", "path": ".gitapex/policies/issue-required-sections.toml", "format": "toml",
  "authority": "required body sections for an auto-opened retro issue (what changed, repair signals, gate provenance)" }

// gates[]
{ "id": "post-merge-auto-retro", "kind": "script", "script": "scripts/post_merge_retro_append.py",
  "rule": "on PR merge, open (or append to, if a matching open retro already exists) a retrospective issue titled per retro-identity, labeled per retro-identity, seeded with required sections",
  "planes": ["ci"], "trigger": "pull_request closed (merged=true)",
  "policy_refs": ["retro-identity", "retro-operations", "trusted-bots", "issue-required-sections"],
  "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "merge-retro-dedup", "kind": "script", "script": "scripts/_auto_retro_ledger.py",
  "rule": "before opening a new retro issue, search for an existing open issue matching retro-identity's pattern for the same merge; append rather than duplicate",
  "planes": ["ci"], "trigger": "invoked by post-merge-auto-retro before issue creation",
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
title_pattern = '(?i)^Merge retrospective: PR #\d+'
label = "retrospective"
[reserved]                     # agent-mintable NEVER; auto-retro CI job only
title_prefixes = ["Merge retrospective:"]
[retro_close_pr]
title_pattern = '(?i)^chore\(retro-close\):'
[closing_keywords]
keywords = ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"]
```

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

## 3. Retro-convergence cluster (reconstructed, see provenance note)

TP/FP feedback loop over closed retro follow-up items, plus a sentinel
that auto-closes stale retros after a bounded inactivity window, plus the
label taxonomy both draw on.

```jsonc
// policy_sources[]
{ "id": "retro-convergence-policy", "path": ".gitapex/policies/retro-convergence.toml", "format": "toml",
  "authority": "label taxonomy (5 labels: e.g. retrospective, gate-candidate, false-positive, drift-confirmed, sentinel-closed), stale_days=30, sentinel_inactivity_days=30" }

// gates[]
{ "id": "retro-followup-drift", "kind": "script", "script": "scripts/scan_retro_followup_drift.py",
  "rule": "scan closed retro follow-up issues for TP/FP convergence signal; flag drift between predicted repair-signal classification and actual outcome",
  "planes": ["ci"], "trigger": "scheduled (weekly) + workflow_dispatch",
  "policy_refs": ["retro-identity", "retro-convergence-policy"],
  "cluster": "retro-integrity", "tracking_issue": 140 },
{ "id": "retro-sentinel", "kind": "script", "script": "scripts/retro_sentinel.py",
  "rule": "auto-close a retro issue after sentinel_inactivity_days of no activity, applying the sentinel-closed label from the shared taxonomy",
  "planes": ["ci"], "trigger": "scheduled (daily)",
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
- Auto-retro core and convergence gate JSON (sections 1 and 3) are
  speculation-grade per the provenance note above; re-verifying them
  against `auto_retro.py`/`scan_retro_followup_drift.py` directly is a
  prerequisite for implementation, not for filing this design.

## Acceptance criteria

- [ ] All 12 gates (2 core + 3 protection + 2 convergence + 5 broader
      candidates, one marked deferred) have concrete registry JSON above.
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

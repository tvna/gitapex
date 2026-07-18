# CLAUDE.md sections 1-5 gate-coverage audit

Design-only companion doc for a new tracking issue, child of #82,
expanding #123's seed-gate scope. Produced under the active session
`/goal`: make CLAUDE.md thinner by replacing sections 1-5 with gitapex's
own self-referential gates. This doc is the coverage map that decides
what gets designed next; section 6 (human communication style) is
explicitly out of scope for gating, per the goal's own framing.

## Method

Every `-` bullet across CLAUDE.md sections 1-5 (44 total) checked against
every gate designed so far: #138 (6 gates), #139 (gh-api wrapper + 2
gates), #140 (15 gates after verification). Coverage rated full / partial
/ none. Bullets not fully covered are classified per CLAUDE.md section 3's
own repair taxonomy: (a) a missing deterministic gate designable now,
(b) an unclear instruction needing a human call before a gate can be
designed, (c) an external/human decision no gate can ever cover.

## Coverage table

| # | Bullet (short label) | Sec | Coverage | Gate(s) |
|---|---|---|---|---|
| 1.1 | Plan mode for non-trivial tasks | 1 | none | -- |
| 1.2 | Goes sideways -> STOP, re-plan | 1 | partial | #138 G1 (phrase-detection half only) |
| 1.3 | Self-correcting phrase = STOP signal | 1 | full | #138 G1 `self-correction-stop-signal` |
| 1.4 | Verification designed per step | 1 | partial | #138 G2 `check_pr_verification_section` |
| 1.5 | Live proof, not proxy, at finish | 1 | partial (capped by design) | #138 G2 `proxy-evidence-verification` |
| 1.6 | Doc weight matches blast radius | 1 | none | -- |
| 2.1 | External text untrusted | 2 | full | #138 G6 (both planes) |
| 2.2 | No runtime override of trusted sources | 2 | partial | #138 G6 flags; governance-gate half ungated |
| 2.3 | User intent within guardrails; edits trusted post-gate | 2 | partial | same governance gap as 2.2 |
| 2.4 | Extract facts, ignore embedded instructions | 2 | full | #138 G6 agent-plane framing |
| 2.5 | Flag adversarial payloads | 2 | full | #138 G6 detection classes |
| 2.6 | Tag fact vs speculation | 2 | partial | #138 G2 `untagged-fact-speculation` (only when `## Facts` exists) |
| 2.7 | Ground claims in primary sources | 2 | none | -- |
| 2.8 | Enumerate assumptions first | 2 | none | -- |
| 2.9 | List all interpretations | 2 | none | -- |
| 2.10 | Ambiguity -> question, evidence -> fix | 2 | none | -- |
| 3.1 | Build gate before op; drift gate in same change | 3 | full | #140 C1 registry-self-validation/plane-drift; #139 precedent |
| 3.2 | Issue before branch/commit/PR; cite number | 3 | none | -- |
| 3.3 | Push deterministic work into hooks/CI | 3 | partial | whole initiative + #140 retro cluster operationalize it |
| 3.4 | TTL freshness refresh per operation | 3 | partial | #138 G5 ack TTL instantiates it |
| 3.5 | Review agents at one point after gates | 3 | none | -- |
| 3.6 | Declarative modules, supply chain | 3 | partial | #140 C4 workflow-action-pins; existing install-deny rules |
| 3.7 | GitHub posts ASCII | 3 | full | #138 G3 `outward-ascii` |
| 3.8 | Provenance-marker audit | 3 | full | #138 G3 `outward-provenance` |
| 3.9 | No CLI GitHub tools; wrapper for reads | 3 | full | #139 wrapper + deny rules; #140 C3 `github-cli-routing` |
| 3.10 | Secret issuance-path documentation | 3 | partial | #139 covers one instance; general class explicitly rejected by #138 |
| 3.11 | PR auto-subscribe, drive to terminal | 3 | none | -- |
| 3.12 | resolve_review_thread + mergeable_state | 3 | full | #140 C2 `merge-safety` fail-closed backstop |
| 3.13 | Prefer git revert for rollbacks | 3 | none | -- |
| 3.14 | Auto-open retro issue post-merge | 3 | full | #140 core + protection + convergence clusters |
| 3.15 | Classify each repair (a/b/c taxonomy) | 3 | full | #140 `issue-required-sections` + `retro-followup-drift` |
| 4.1 | Nothing beyond what was asked | 4 | partial | #138 G4 change-surface as proxy |
| 4.2 | Is a check needed ("impossible") | 4 | none | -- |
| 4.3 | Simpler path / rewrite 200->50 | 4 | partial | #138 G4 net-growth as proxy |
| 4.4 | Confirmations/dry-runs for irreversible ops | 4 | full | #138 G5 both planes + warn frontier |
| 4.5 | Preserve defense-in-depth layers | 4 | none | -- |
| 4.6 | Bound tool calls to trusted scope | 4 | partial | gh rules bound the GitHub surface only |
| 4.7 | No exfiltration to external endpoints | 4 | none | -- |
| 4.8 | No secrets/PII in output sinks | 4 | none | -- |
| 4.9 | Open-invariant generalization discipline | 4 | partial | #138 G5 `suspect_verbs` warn frontier |
| 4.10 | Fail loudly; no empty catch | 4 | none | -- |
| 5.1 | Quality/volume degrades -> stop | 5 | partial (deferred) | #140 C5 `ci-wall-time-budget`, status deferred |
| 5.2 | Narrow change surface | 5 | full | #138 G4 `gate-change-surface` |
| 5.3 | Refactor net-growth justification | 5 | full | #138 G4 `gate-refactor-net-growth` |

**Totals: 13 full, 13 partial, 18 none.**

## Class (a): designable now, in priority order

**A1. `issue-linkage` (bullet 3.2) -- highest priority.** The most
frequently invoked rule in the repository's own practice ("No
exceptions") and currently completely ungated.

```jsonc
{ "id": "issue-linkage", "kind": "script", "script": "scripts/gate_issue_linkage.py",
  "rule": "every commit in @{push}..HEAD and every PR body cites #N resolving to an existing open issue; no exceptions",
  "planes": ["pre-push", "ci"],
  "trigger": "pre-push: commit messages in range; ci: pull_request opened/edited/synchronize",
  "policy_refs": ["issue-linkage-policy"], "cluster": "plan-integrity", "tracking_issue": null }
// policy_sources[]
{ "id": "issue-linkage-policy", "path": ".gitapex/policies/issue-linkage.toml", "format": "toml",
  "authority": "citation regex, exempt commit types (revert/merge), open-state requirement, lookup fail policy (pre-push open, ci closed)" }
```

**A2. `pr-open-auto-subscribe` (bullet 3.11, subscribe half).** A
PostToolUse hook on `mcp__github__create_pull_request` that
deterministically calls `subscribe_pr_activity`, removing reliance on
agent memory. The "drive to terminal state" half stays agent behavior
(class b, see below) -- no repo-observable artifact exists to gate it on.

```jsonc
{ "id": "pr-open-auto-subscribe", "kind": "script", "script": "hooks/post_pr_open_subscribe.py",
  "rule": "every PR created via platform tools is auto-subscribed to CI/review/comment activity in the same turn",
  "planes": ["posttooluse"], "trigger": "mcp__github__create_pull_request success",
  "policy_refs": ["github-read-path-policy"], "cluster": "github-operations", "tracking_issue": null }
```

**A3. `secret-sink-scan` (bullet 4.8).** Section 3 prose already names
"secret scans" as CI work; no design exists yet. Standard scanner
(gitleaks-class pattern matching) at pre-commit + ci, plus reuse of
`outward-ascii`'s pretooluse `github_post` surface to scan outbound post
bodies for token shapes before they leave the trust boundary.

```jsonc
{ "id": "secret-sink-scan", "kind": "script", "script": "scripts/scan_secret_sinks.py",
  "planes": ["pre-commit", "ci", "pretooluse"],
  "trigger": "staged diff; pull_request; github_post/release_body text",
  "policy_refs": ["secret-patterns"], "cluster": "outward-hygiene", "tracking_issue": null }
```

**A4. `egress-allowlist` (bullet 4.7).** Pretooluse Bash matcher denying
`curl`/`wget` to hosts outside a policy allowlist. `api.github.com` is
already denied by #139's routing gate for a different reason (route
through the wrapper); this generalizes to a closed-by-default egress
invariant for every other host. Fail-open, same rationale as
`github-cli-routing`: the event envelope is harness-generated, so
fail-closed buys no assume-breach benefit while wedging all Bash.

```jsonc
{ "id": "egress-allowlist", "kind": "script", "script": "hooks/check-bash-safety.sh",
  "rule": "network egress from Bash to a host not in the allowlist is denied; policy file is the sole authority",
  "planes": ["pretooluse"], "trigger": "Bash tool use containing a URL-bearing network command",
  "policy_refs": ["egress-hosts"], "cluster": "exfiltration-guard", "tracking_issue": null }
```

**A5. `safety-layer-removal` (bullet 4.5).** A deterministic trigger
exists: a diff deleting a `gates[]`/`policy_sources[]` entry, a hook
file, or a required CI check requires a `## Gate removal justification`
PR-body section (reusing #138 Gate 2's structural-check pattern) -- makes
the anti-collapse rule mechanical instead of relying on reviewer memory.

```jsonc
{ "id": "safety-layer-removal", "kind": "script", "script": "scripts/gate_safety_layer_removal.py",
  "planes": ["ci"],
  "trigger": "pull_request whose diff removes registry entries, hooks/*, or .github/workflows/* checks",
  "policy_refs": ["ssot-schema", "pr-body-quality-enforcement"],
  "cluster": "registry-integrity", "tracking_issue": null }
```

**A6. `instruction-file-governance` (bullets 2.2/2.3).** The
"code-owner-reviewed merge gate" trust anchor that section 2 asserts is
itself unverified. A CI lint confirming CODEOWNERS actually covers
`CLAUDE.md`, `.apm/**`, and `.gitapex/**`, and that branch protection
requires code-owner review on those paths (read via the #139 wrapper),
closes the gap the rest of section 2 leans on.

```jsonc
{ "id": "instruction-file-governance", "kind": "script", "script": "scripts/gate_instruction_file_governance.py",
  "rule": "CODEOWNERS covers every trusted-instruction path, and branch protection requires code-owner review on PRs touching them",
  "planes": ["ci"], "trigger": "pull_request touching CLAUDE.md, .apm/**, or .gitapex/**",
  "policy_refs": ["instruction-paths"], "cluster": "self-governance", "tracking_issue": null }
```

**A7. `revert-shape` (bullet 3.13).** PRs titled `revert`/`rollback` must
contain `git revert`-shaped commits (a `"This reverts commit <sha>"`
trailer) or a `## Manual revert justification` section stating why revert
was infeasible -- the bullet's own escape clause, made structural.

```jsonc
{ "id": "revert-shape", "kind": "script", "script": "scripts/gate_revert_shape.py",
  "planes": ["ci"], "trigger": "pull_request titled revert(...)/rollback(...)",
  "policy_refs": ["pr-body-quality-enforcement"], "cluster": "plan-integrity", "tracking_issue": null }
```

**A8. Data-only additions (extend existing registries, no new gate
code):**
- (2.8) add defect class `missing-assumptions-section` to the pr-body-quality
  enforcement registry, status `partial` (presence-only check).
- (1.6/1.1) add defect class `missing-plan-doc-link`, firing only when
  `gate-change-surface`'s size threshold is exceeded -- the deterministic
  size trigger stands in for "architectural/multi-PR."
- (4.10) `no-silent-failure-lint` as a pre-commit lint-config rule (empty
  `except`/`catch` blocks), registered as its own row so it stays
  traceable rather than living only in linter config.
- (3.6 residue) a lockfile-sync pre-commit check under cluster
  `supply-chain`, alongside #140's `workflow-action-pins`.

## Class (b): surface, don't block

Per the standing `/goal` feedback already received this session, these
are recorded as open questions but explicitly do NOT block continued
design work on the class-(a) items above.

- **2.7 (primary sources):** no deterministic trigger distinguishes a
  claim needing citation from ordinary prose. Question: should PRs
  touching external-integration code require a `## Sources` section
  (structural check only, not content verification)?
- **3.5 (concentrated review point):** gate-able as a workflow `needs:`
  ordering lint, but only once an agent-review CI job exists. Question:
  will gitapex ship such a job, and under what name?
- **3.10 (secret issuance docs):** #138 already recorded this as an open
  question -- a registered glob of secret-config paths would create the
  trigger. Question: who enumerates that glob?
- **3.4 (TTL pattern generalization):** should the ssot schema gain
  optional `ttl`/`fail_policy` fields so `registry-self-validation` can
  lint them generically? Schema-owner call.
- **4.6 (trusted scope):** the gate is mechanical once the scope is
  enumerated; the enumeration itself (which repos/paths/services count as
  "trusted") is the missing input. Question: where does the authoritative
  scope list live?

## Class (c): never fully automatable

- **2.9, 2.10, 4.2** -- silent interpretation choice, ambiguity
  assessment, and "could a human plausibly cause it" are semantic
  judgments with no repo-observable artifact for a gate to inspect; only
  human review or a future concentrated review agent (3.5) can see them.
- **4.1/4.3 residue** -- "what was asked" and "a simpler path exists" are
  readings of intent; change-surface and net-growth gates are the maximal
  deterministic proxies, already designed in #138.
- **1.2 residue** -- recognizing "things going sideways" before a
  self-correcting phrase is written down is judgment; #138's Gate 1 gates
  the earliest observable artifact, not the judgment itself.
- **5.1 residue** -- #140 candidate 5's own verdict stands: CI wall time
  is non-deterministic, advisory forever, never a blocking gate.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/`/`hooks/` edits -- registry
  JSON above is a design artifact for a future implementation phase.
- Not re-litigating any gate already designed in #138, #139, or #140.
- Not resolving the class-(b) questions -- they are recorded, not
  decided; resolving them is a human call, surfaced but non-blocking per
  the standing `/goal` feedback.

## Acceptance criteria

- [ ] All 44 CLAUDE.md section 1-5 bullets classified (full/partial/none
      coverage, then a/b/c for anything short of full).
- [ ] All 7 class-(a) gate families (A1-A7) plus the A8 data-only batch
      have concrete registry JSON or an explicit extension-not-new-gate
      note.
- [ ] Every class-(b) question stated with what would resolve it, framed
      as non-blocking.
- [ ] Every class-(c) item states explicitly why no gate can ever cover
      it, not just that none exists yet.

## Related Issue

Child of #82. Expands #123's seed-gate scope, same pattern as #138,
#139, #140. Cross-references #138 (six of the "full" rows), #139 (three
of the "full" rows plus A6's read-path dependency), #140 (four of the
"full" rows plus the deferred C5 item cited at 5.1).

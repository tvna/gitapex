# Security-capability tiers for `gitapex init` (Foundation / Enterprise / Advanced)

Date: 2026-07-18

Refs #147 (child of #82). Extends #127 (`gitapex init` scaffolding, whose
inputs, outputs, and decision-logic mechanism are already resolved and are
NOT reopened here) and #131 (the binding zero-trust principles, all seven
of which this design is checked against). Grounded in one named primary
source, read this session: Anthropic's "Zero Trust for AI Agents" eBook
(the Foundation/Enterprise/Advanced tier framework, its per-category
capability tables, and its "impossible vs. tedious" design test).

## Design-only scope

Per this repository's discipline (matching #123/#125/#126/#127/#130/#131
precedent): this doc records a design only. No code, no `.gitapex/` file,
no `scripts/` or `hooks/` change, no edit to `.gitapex/ssot.schema.json`
is made by this pass. Where the design requires a future schema field
(the recorded tier, below), that is a proposal for the implementation
issue, not a change made here.

## Why this doc exists

Today `team-size` is the only knob `gitapex init` exposes that resembles
a security-posture choice, and it tunes exactly one thing: branch-
protection review-count parameters. The operator wants an explicit,
broader capability-tier concept -- modeled on the source document's
Foundation/Enterprise/Advanced framework -- governing the FULL harness
`init` scaffolds: identity/credential handling, access-control model,
observability/audit depth, behavioral monitoring, input/output
validation, and integrity/recovery posture. Not just review counts.

## Translation discipline (what a tier can honestly mean here)

The source document tiers an *enterprise runtime*: HSMs, X.509 lifecycle,
SIEM streaming, SOAR playbooks, confidential-computing enclaves. gitapex
is none of those things. It is a redistributed single static binary with
no server, sidecar, or daemon (#125, #131), and `gitapex init` is a
*scaffolding step*: it generates `.gitapex/ssot.json`, platform-native
protection (CODEOWNERS + rulesets), and an MCP tool allowlist (#127).
So each source-document tier row is translated into what a scaffolding
CLI can actually do, in exactly one of three honesty classes, tagged
throughout:

- **configure** -- init emits it as enforced platform or registry state.
- **recommend** -- init emits it as a documented requirement in a
  generated posture report (defined below) that it cannot itself enforce.
- **not covered** -- no plausible gitapex mechanism exists even at
  Advanced tier; stated plainly, never invented. This matches the
  discipline of the security-control-inventory mapping (#144/#145; first-
  pass table in `docs/superpowers/specs/2026-07-18-owasp-mapping-and-
  ingestion-hygiene-design.md`), e.g. its ASI10 Rogue Agents `not
  covered` verdict and ASI03's named missing short-lived/OIDC identity.

Two inversions fall out of the translation and are worth naming so nobody
reads this doc as a straight port. First, some source-document *Advanced*
capabilities are gitapex *Foundation*: "policy checks integrated into
deployment pipelines" (the source's Advanced governance row) is gitapex's
entire reason to exist and is present from the floor up. Second, some
source-document *Foundation* capabilities are unreachable at any gitapex
tier: per-agent-instance cryptographic identity is a runtime-issuance
capability a scaffolding CLI cannot mint; the closest honest translation
is credential and commit-signature requirements on the humans-and-
workflows side, tiered below.

The source's design test is applied throughout: **does this control make
the attack impossible, or just tedious?** Controls that remove a path
(a bypass list that is empty, a permission never granted, an override
mechanism that does not exist) are floors and never tier-relax. Controls
whose value is friction (an approval count, a retention length, a scan
cadence) are legitimately tier-scalable.

## Tier definitions for gitapex

Mirroring the source document's own framing, adjusted to gitapex's
adopter population:

- **Foundation** -- minimum viable harness. NOT a relaxed harness: per
  the source's "the Foundation floor has been raised" framing and #127's
  F3 (narrowest-viable defaults, always), every non-negotiable floor in
  the next section holds at Foundation. What Foundation omits is depth
  (external audit anchoring, OIDC credential federation, signature
  requirements), not the floors.
- **Enterprise** -- Foundation plus depth for adopters where a single
  compromise carries meaningful business impact: verified identity over
  asserted identity wherever the platform can enforce it, externally
  anchored audit integrity, credential federation replacing stored
  secrets.
- **Advanced** -- Enterprise plus the strictest posture gitapex can
  scaffold, for high-risk or regulated adopters -- and an explicit,
  honest list of what remains `recommend` or `not covered` even here.

Each tier builds on the one before it -- advancing strengthens existing
controls, never replaces them (source document, closing framing). A
capability present at tier N is present at N+1.

## Relationship to `team-size`: separate input, suggested mapping

**Decision: the tier is a new, separate closed-enum init input
(`security-tier`: `foundation | enterprise | advanced`). `team-size` is
neither superseded nor reinterpreted. `team-size` maps to a *suggested
default* tier, which the operator confirms or overrides at init time --
the same detect-then-confirm pattern #127 already uses for `platform`.**

Argument, against the two rejected alternatives:

- *Rejected: tier supersedes/reinterprets `team-size`.* The two inputs
  answer different questions. `team-size` answers "how many humans are
  available to review" -- a capacity fact. The tier answers "how much
  security depth should the scaffolded harness carry" -- a risk-posture
  choice. A solo adopter in a regulated domain needs Advanced depth with
  solo-capacity review parameters (`required_approving_review_count`
  physically cannot exceed the number of available distinct reviewers).
  Folding tier into `team-size` would force that adopter to either lie
  about team size or under-secure. It would also silently reopen #127's
  resolved input set, which this doc must not do.
- *Rejected: fully orthogonal (no mapping).* An unmapped free choice
  makes the common case worse: most adopters have no basis to pick a
  tier cold, and the source document itself grounds its tiers in
  deployment scale ("might meet risk tolerance on its own for small
  businesses/teams" for Foundation; "most organizations with significant
  deployments" for Enterprise). Team size is a legitimate, already-
  collected proxy for that scale -- it should seed the default, not be
  ignored.

The suggested mapping (a suggestion the operator confirms, never a silent
commitment):

| `team-size` | Suggested tier |
|---|---|
| `solo` | `foundation` |
| `small-team` | `foundation` |
| `org-scale` | `enterprise` |

`advanced` is never suggested automatically. Rationale: Advanced
scaffolds obligations whose prerequisites the CLI cannot verify exist
(commit-signing rollout across all contributors, an adopter-supplied
external audit sink). Scaffolding those unconfirmed onto a repo whose
contributors cannot yet sign is a self-inflicted denial of service --
every subsequent push fails. Advanced is therefore always an explicit
operator election. This is consistent with fail-closed (#131 principle
6): the failure mode of a wrong *suggestion* must be "harness slightly
shallower than ideal, floors intact," never "repo bricked by a posture
nobody chose."

After the tier is chosen, `team-size` retains its existing #127 role for
capacity-bound parameters (review counts), and the tier drives the
security-depth parameters defined in the category tables below. Where
both touch the same parameter, the stricter value wins (e.g. `org-scale`
already sets `required_approving_review_count >= 2`; an Enterprise tier
on a `small-team` repo does not lower it).

The chosen tier is recorded in the generated `.gitapex/ssot.json`
instance as a `security_tier` field -- a schema addition proposed here,
deferred to the implementation issue (see Non-goals). Recording it is
load-bearing for re-init monotonicity, below.

## Non-negotiable floors vs. tier-scalable controls

The dividing line is the source document's own test, applied control by
control: a floor is a control that makes a class of attack *impossible*
by removing the path; relaxing it at any tier would reintroduce the
path. A tier-scalable control adjusts *friction or depth*; its value
scales with adopter risk and capacity, and no tier setting of it can
reintroduce a removed path.

### Floors (hold at every tier, including Foundation; no tier lowers them)

| Floor | Origin | Impossible-vs-tedious justification |
|---|---|---|
| `bypass_actors: []` on the `.gitapex/ssot.json` + `.gitapex/policies/**` ruleset, all team sizes, admins not exempt | #127 F3 | An empty bypass list removes the bypass path; it does not exist to be ground through. Any non-empty list converts a hard barrier into a phishable/compromisable identity set. |
| PR-required (no direct push), force-push and deletion blocked, `require_code_owner_reviews: true`, required dry-run status check -- even for `team-size: solo` | #127 F3 | Direct-write and history-rewrite paths to governed state are removed, not throttled. An agentic attacker with unlimited patience cannot use a path that is absent. |
| Immutable binary-embedded decision table, no filesystem/env override, mandatory fail-closed default row for unmatched inputs | #127 F2 | An override mechanism that does not exist cannot be abused. A configurable table would be a tedious-class control (attacker edits config) dressed as a barrier. |
| MCP allowlist entries `status: "quarantined"` pending explicit per-entry human confirmation; unconfirmed = denied | #127 F5 | Auto-confirmation at any tier would replace a hard deny with a heuristic -- assume-clean on INDETERMINATE, forbidden by #131 principle 6. Confirmation stays human at every tier. |
| Apply-workflow credential: `administration: write`, single repo only, default-branch trigger only, never `pull_request` | #127 F6 | A permission never granted cannot be exfiltrated or abused; scope removal is impossible-class, scope monitoring would be tedious-class. |
| Re-init monotonicity check diffs against live PLATFORM state (never a local copy); widening changes block pending explicit recorded confirmation; failed/partial fetch classifies as widening | #127 / F4 | Comparing against attacker-influenceable local state is exactly the control #131 principle 4 forbids. The human-confirmation gate on widening is the source document's own "human-in-the-loop ... absolutely necessary for high-risk actions." |
| Minimal denial-message disclosure on the MCP surface (full detail only via operator-invoked local CLI) | #126 / #131 P7 | Verbose denials are a gate-evasion oracle -- reconnaissance an agentic attacker farms at near-zero cost. |
| Closed-enum / validated-pattern init inputs (no free text reaching generated YAML/CODEOWNERS/JSON) | #127 addendum | Injection through a closed enum is impossible by construction, not filtered after the fact. The new `security-tier` input is closed-enum for the same reason. |

### Tier-scalable controls (friction/depth; scaling them cannot reintroduce a removed path)

- `required_approving_review_count` beyond the floor of 1 (an approval
  count raises collusion cost -- friction, tedious-class -- so it
  legitimately scales with tier and team capacity; the impossible-class
  part of review is the PR-required + `bypass_actors: []` structure,
  which is a floor).
- Commit-signature requirements (none / governed paths / repo-wide).
- Credential *mechanism* depth (documented expiring fine-grained token
  vs. OIDC-federated, no stored secret).
- Audit-trail depth (local hash chain vs. externally anchored head +
  independent CI verification vs. exported to adopter sink).
- MCP allowlist re-verification cadence and fingerprint re-check
  strictness (the *proposal and re-check* depth scales; the quarantine
  floor does not).
- Whether agent-plane hooks (untrusted-text advisory, ingestion-hygiene
  budgets) are scaffolded, and how tight the budgets are (the hard-cap
  tier itself is resizable-not-removable per the ingestion-hygiene
  design -- that resizable-not-removable property is a floor).
- Whether behavioral threshold checks (gate-denial-rate reporting) are
  scaffolded at all.
- Governance-artifact depth in the generated posture report.

## The generated posture report

One new v1.5 output artifact accompanies the three #127 outputs: a
generated, per-tier `POSTURE.md`-style report (exact name/location for
the implementation issue) that states, for the chosen tier, (a) every
`configure`-class control init just applied, (b) every `recommend`-class
control the tier expects but init cannot enforce -- each with the
concrete issuance/setup path CLAUDE.md section 3 requires for
credentials, and (c) every `not covered` item the tier honestly lacks.
This is the mechanism that lets a tier "govern" things a CLI cannot
configure without pretending it configured them. Purpose: the report is
the by-inspection artifact (CLAUDE.md section 6) an operator audits the
scaffold against; it never substitutes for the enforced state itself.

## The seven categories, tiered for gitapex

Each table row is tagged `configure` / `recommend` / `not covered` per
the translation discipline above.

### 1. Identity and authentication

Source anchors: agent-identity-verification and service-authentication
tables; "Static API keys and shared service-account passwords are NOT a
legitimate Foundation posture."

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | No static long-lived credential anywhere in scaffolded output; F6-scoped fine-grained credential with documented expiry/rotation | `configure`: scaffolded workflows contain no embedded secrets; `recommend`: posture report documents the fine-grained single-repo token issuance path, minimum permissions, expiry, and handoff verification (CLAUDE.md section 3's issuance-path rule). |
| Enterprise | Short-lived, federated workflow identity replacing stored secrets; verified commit identity on governed paths | `recommend`: a GitHub Actions OIDC token is exchanged with an *external* identity provider, not with GitHub itself -- GitHub's repository-administration REST API accepts only a GitHub App/installation token, PAT, or equivalent GitHub credential, never a raw Actions OIDC token, so the apply workflow's stored credential cannot be replaced by OIDC alone. Closing the ASI03 gap requires a broker external to what `init` can scaffold: a cloud workload-identity provider (fronting a secrets-managed GitHub App private key) that the OIDC token is exchanged with, which then mints a short-lived GitHub App installation token. The posture report documents this broker pattern and the GitHub App issuance path; `init` cannot stand up the broker itself, so this stays `recommend`, not `configure`, until an adopter wires one. `configure`: required signed commits on `.gitapex/**` via ruleset -- verified identity over asserted (#131 principle 5). |
| Advanced | Repo-wide verified identity; integrity-pinned gitapex binary distribution | `configure`: required signed commits repo-wide; `configure`: SHA-pinned Class B binary distribution (#125) -- this proves the downloaded bytes match a preselected digest, not who produced them or that they came from an authorized build; the security-control-inventory's own ASI04 row already scores this `partially covered` for exactly that reason. `recommend`: posture report documents the separate producer-signature/attestation verification path needed for actual binary provenance -- out of `init`'s `configure` scope, same as the Enterprise OIDC broker above. Hardware-backed agent identity (HSM/TPM, remote attestation of agent instances): **not covered** -- a redistributed CLI has no issuance or attestation infrastructure, and inventing one here would contradict the inventory's honesty discipline. |

Honest inversion note: the source's *Foundation* row (per-agent-instance
cryptographic identifiers) is unreachable at any gitapex tier. gitapex
tiers the credential and signature surface it can actually reach; it
does not claim agent-instance identity.

### 2. Access control and privilege management

Source anchors: permission-models (RBAC deny-by-default -> ABAC ->
continuous authorization), privilege-scoping (static least-privilege ->
dynamic -> JIT/JEA), resource-boundaries tables.

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Deny-by-default across every scaffolded surface | `configure`: CODEOWNERS on governed paths, `bypass_actors: []`, quarantined-by-default MCP allowlist (everything not explicitly granted is blocked -- the source's RBAC-deny-by-default row, translated). All floors from the table above live here. |
| Enterprise | Finer-grained, per-context privilege partitioning | `configure`: per-path CODEOWNERS granularity (registry vs. policies vs. workflows owned separately); `configure`: MCP allowlist entries carry a re-confirmation cadence; `recommend`: MCP-mode ambient-privilege sanitization per #126's open finding (env allowlisting for the least-trusted invocation context) -- recommended until #126's fix lands, not claimed. |
| Advanced | Human-gated just-in-time elevation for the highest-privilege operation | `configure`: platform deployment-environment protection (required reviewers) in front of the apply workflow -- the closest buildable translation of JIT/JEA: the `administration: write` capability is exercisable only at the moment a named human approves, then returns to unreachable. Continuous per-action authorization with real-time policy evaluation: **not covered** as a runtime -- gitapex has no daemon; the architectural per-invocation re-validation (#131 principle 2) is the honest partial equivalent and is already a floor, not an Advanced feature. |

### 3. Observability and auditing

Source anchors: action-logging (comprehensive -> immutable/integrity-
verified -> SIEM streaming) and traceability tables; "instrument dwell
time and coverage" first.

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Gate-evaluation audit trail on, with documented retention | `configure`: #130's audit trail scaffolded enabled -- every gate evaluation logged with context, hash-chained, audit-write failure fail-closed per #130's addendum; `recommend`: retention period documented in the posture report per adopter requirements. |
| Enterprise | Integrity-verified, externally anchored trail | `configure`: scaffold the #130 addendum's identified missing pieces -- an independent CI verification job for the hash chain and an externally anchored chain head (e.g. published as a workflow artifact/release asset), plus replication of the log off the single local disk. This is the source's "immutable audit trails with integrity verification" row in the only form a CLI-plus-CI harness can honestly provide. |
| Advanced | Export toward adopter-side correlation | `configure`: scaffold a CI export step shipping the audit log to an adopter-supplied sink; `recommend`: correlation/alerting in that sink. Real-time SIEM streaming with correlation: **not covered** by gitapex itself -- it ships no SIEM and no streaming runtime; the export hook is the boundary of what it can configure, and the posture report says so. |

Traceability: request-id propagation through a single CLI invocation's
gate evaluations is Foundation `configure` (cheap, local); distributed
tracing across multi-agent workflows and full replayable provenance
chains are **not covered** (no multi-agent runtime exists to trace).

### 4. Behavioral monitoring and response

Source anchors: baseline-establishment, anomaly-detection, automated-
response tables; "automate the bookkeeping, not the decisions."

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Manually documented expected behavior + hard resource thresholds | `configure`: ingestion-hygiene budgets scaffolded (soft/hard caps -- the source's threshold-alert row, translated to the one resource surface gitapex mediates); `configure`: the posture report's expected-behavior section is the source's "manual definition of expected agent behavior patterns" row, literally. |
| Enterprise | Threshold trend reporting | `configure`: a scaffolded CI step reporting gate-denial rates and allowlist-quarantine hits over time -- deterministic bookkeeping a human reviews. Statistical baseline learning: **not covered** -- no component of gitapex observes enough runtime behavior to learn a baseline. |
| Advanced | -- | ML-based behavioral analysis, drift detection, automated containment (session termination, credential revocation), SOAR playbooks: **not covered**, consistent with the inventory's ASI10 Rogue Agents `not covered` verdict ("no runtime behavioral-anomaly detection or per-session containment exists anywhere in #125-#143"). This tier row is intentionally empty of new claims: the honest Advanced posture here is Enterprise's reporting plus the source document's own division of labor -- humans make containment calls; gitapex's contribution is that the merge boundary it scaffolds (#127) is the containment surface those humans act on. |

This is the category where the tier ladder is shortest, and saying so
plainly is the point: a tier table that invented an anomaly-detection
capability would contradict the repo's own inventory.

### 5. Input validation and output controls

Source anchors: input-sanitization (schema/length floor -> pattern
filtering -> multi-layer/spotlighting) and output-filtering (pattern
scan -> semantic analysis -> human-in-the-loop) tables.

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Schema/enum/size validation everywhere input enters | `configure`: closed-enum init inputs; `.gitapex/ssot.json` schema validation; ingestion hard caps; the #125-addendum content-hygiene pass over `policy_sources[]` files (hidden Unicode, encoded payloads -- fail-closed including its own failure). This is the source's "still enforce schemas/length/known-bad-patterns as the floor" made literal. |
| Enterprise | Instruction-pattern awareness on the agent plane | `configure`: scaffold the untrusted-text advisory hook (#138 Gate 6) and the MCP tool-poisoning scan with a re-check cadence -- the "known attack pattern detection" row in advisory form (advisory is the honest claim: these classify and warn; they do not guarantee detection). |
| Advanced | Delimiting untrusted content; human approval for high-risk actions | `configure`: Gate-6-style wrapping/delimiting of untrusted content is the buildable form of the source's "spotlighting" row; `configure`: TTL-bounded human acknowledgment for irreversible operations and the widening-block on re-init are its human-in-the-loop row. Constitutional classifiers (AI-based input classification): **not covered** -- a static binary ships no model runtime. |

Output-control note: the minimal-disclosure denial split (#126) is a
floor, not an Advanced feature -- output filtering of the surface most
exposed to an adversary does not wait for a tier election. And per the
source's own caveat ("human-in-the-loop is ... absolutely necessary for
high-risk actions" at any tier), the human confirmation on widening
re-init changes is a floor too; Advanced only widens the set of
operations behind explicit acknowledgment.

### 6. Integrity and recovery

Source anchors: configuration-integrity (version control -> signed
configs -> immutable/attested) and recovery-capabilities tables.

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Version-controlled, merge-gated, review-required configuration with documented rollback | `configure`: the generated `.gitapex/**` state is merge-gated behind the F3 ruleset (the source's entire Foundation row -- version control, required review, change history -- is gitapex's native habitat); `recommend`: posture report documents rollback as `git revert` of the merged change (CLAUDE.md section 3's revert-first rule), exercised via the same PR path. |
| Enterprise | Signed configuration with deployment verification | `configure`: required commit signatures on `.gitapex/**` (from category 1) make governed config cryptographically signed at the only deployment boundary gitapex has -- the merge; `configure`: the required dry-run status check is the "verify before deployment" half, already a floor. |
| Advanced | Verified-provenance binary; strictest signature surface | `configure`: SHA-pinned binary + repo-wide signatures (category 1). Immutable infrastructure with execution-environment attestation, self-healing systems, automatic remediation, circuit breakers: **not covered** -- gitapex neither deploys nor supervises running infrastructure. Automated rollback with health checks is platform-CI territory: `recommend` only, with the posture report pointing at the adopter's own deployment tooling. |

The source's automatic-updates guidance (signed updates flow through,
unsigned rejected, delay is now the primary risk) maps to gitapex's
distribution channel: the Class B SHA-pin plus its bump cadence is the
`configure` form; the posture report carries the cadence recommendation.

### 7. AI governance policies

Source anchors: governance-policies table (documented policies -> formal
framework -> continuous enforcement in pipelines).

| Tier | gitapex capability | Mechanism |
|---|---|---|
| Foundation | Documented acceptable-use, incident-response, and approver record -- plus pipeline-enforced policy from day one | `configure`: CODEOWNERS is literally the source's "document deployment approvers"; the gate cluster running in CI is the source's *Advanced* row ("policy checks integrated into deployment pipelines") available at gitapex's floor -- the second honest inversion, stated as such; `recommend`: posture report ships acceptable-use and incident-response stubs for the adopter to complete (init cannot know an adopter's prohibited use cases). |
| Enterprise | Stakeholder oversight structure | `recommend`: cross-functional review ownership expressed as distinct CODEOWNERS teams per governed path (`configure` for the mechanism, `recommend` for the org structure behind it); `configure`: MCP allowlist re-confirmation cadence doubles as the "regular policy reviews" row in enforceable form. |
| Advanced | Compliance observability | `configure`: the audit-trail export (category 3) plus gate-denial reporting (category 4) provide audit trails of governance decisions and raw material for compliance metrics; the metrics program itself: `recommend`. Automated org-wide violation detection beyond the scaffolded repo: **not covered** -- gitapex governs one repo at a time by construction. |

## Default tier and re-init movement

**Default absent an explicit operator choice:** the team-size-suggested
tier (`foundation` for `solo`/`small-team`, `enterprise` suggested for
`org-scale`), surfaced for operator confirmation exactly as `platform`
auto-detection is. In a fully non-interactive run with no `security-tier`
flag, init proceeds at `foundation` -- never higher, for the
prerequisites-cannot-be-verified reason argued above; never lower than
the floors, because the floors are not tier properties at all.

**Decision-table impact (F2 compliance):** `security-tier` becomes a
third closed-enum input, but NOT a third cross-product axis. The
existing ~9-row (team-size, platform) table is composed with a separate
3-row per-tier parameter table -- both binary-embedded, immutable, no
override path, per F2 unchanged -- keeping total rows near 12, safely
under #127's ~20-row re-evaluation threshold.

An unrecognized or indeterminate `security-tier` value does **not**
resolve to Foundation. F2's "mandatory default row is the narrowest
artifact set" rule is safe for the (team-size, platform) axes, where
narrowest genuinely means safest: those axes only ever *add* scaffolded
surface. `security-tier` is different -- it gates enforcement *strength*
(OIDC-federated identity, repo-wide signature requirement, external
audit anchoring) directly, so silently mapping an indeterminate value to
Foundation would make a corrupted-input case *less* restrictive on those
dimensions, the opposite of fail-closed. Init instead **blocks scaffold
generation** on an unrecognized/indeterminate `security-tier`: exits
non-zero, reports the invalid value, and generates nothing until the
operator re-runs with an explicit, valid tier. This mirrors the floors
table's existing pattern above (a failed/partial platform-state fetch
classifies as widening and blocks, rather than proceeding on an assumed
value) instead of introducing a tier-specific exception to it.

**Re-init movement between tiers is governed by #127's existing
monotonicity rule, not replaced by a tier-level rule:**

- Raising the tier produces diffs that are (almost entirely) narrowing;
  each proceeds through the normal dry-run-first apply.
- Lowering the tier produces widening diffs; each blocks pending
  explicit recorded confirmation, never silently applied.
- Crucially, **the classification unit stays the individual change
  against live platform state, never the tier label**. A tier raise is
  not trusted to be all-narrowing because its label says so (#131
  principle 5: an asserted label is not verification); if a raise
  contains a widening hunk on some surface, that hunk blocks
  individually. So tier movement is not "narrowing-only" -- downward
  movement is possible -- but it is *widening-blocked*, which is the
  monotonicity rule's actual guarantee.
- Detecting a lowering attempt requires the previously recorded tier.
  Per the F4 pattern, the baseline tier is read from the merge-gated
  default-branch copy of `.gitapex/ssot.json` on the platform, never the
  local working copy an attacker could have edited; inability to fetch
  it is INDETERMINATE and classifies the run as widening (block), per
  #131 principle 6.

## Facts vs. speculation

Facts: #127's resolved inputs/outputs/F2-F6 floors; #131's seven
principles; the security-control-inventory first-pass verdicts (ASI10
`not covered`, ASI03's named OIDC gap) as recorded in the 2026-07-18
OWASP mapping design doc; the source document's tier tables and design
test as quoted; #130's audit-trail design and its addendum findings;
#126's disclosure split; the #125-addendum content-hygiene check.

Speculation, named as such: that an adopter is willing to stand up the
external OIDC-to-GitHub-App-token broker the Enterprise identity row's
`recommend` classification depends on, and that the specific
apply-workflow shape #127 scaffolds can be adapted to call it on both
`github` and `gitlab` (verify per-platform at implementation time; the
row stays `recommend` regardless of platform since `init` itself cannot
scaffold the broker, only document the pattern); that
required-signature rulesets are enforceable on path-scoped rules on both
platforms (same verification duty); the exact posture-report filename
and the `security_tier` field shape (implementation-issue decisions).

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` or `hooks/` edits, no
  change to `.gitapex/ssot.schema.json` -- design only. The
  `security_tier` schema field is proposed, not added.
- Not reopening #127's resolved questions: the input set (beyond adding
  the one new closed-enum tier input), the three v1 outputs, the
  hardcoded-immutable decision-table mechanism, the dropped
  `business-domain` input, and the deferred branch-strategy generation
  all stand as resolved.
- Not relaxing any F2-F6 floor at any tier -- the floors section is
  definitional, and Foundation is not a euphemism for "loose."
- Not claiming runtime capabilities gitapex lacks: no anomaly-detection,
  SIEM, SOAR, agent-instance identity, or attested-execution claims are
  made at any tier; every such source-document capability is tagged
  `not covered` above rather than translated into vapor.
- Not a compliance mapping: this doc tiers what init scaffolds; the
  OWASP/inventory mapping (#144/#145) remains the peer axis for
  control-coverage claims.

## Acceptance criteria

- [ ] Every tier-table row is tagged `configure`, `recommend`, or `not
      covered`, and every `not covered` verdict is consistent with the
      security-control-inventory mapping (no capability claimed here
      that the inventory says gitapex lacks).
- [ ] The tier/`team-size` relationship is stated as one decision
      (separate input, team-size-suggested default, operator-confirmed)
      with both rejected alternatives argued, not left ambiguous.
- [ ] Every floor in the floors table cites its origin (F2-F6, #126,
      #131) and carries an impossible-vs-tedious justification; every
      tier-scalable control is friction/depth-class, and no tier setting
      of any scalable control can reintroduce a floor-removed path.
- [ ] All seven source-document categories have a gitapex-specific
      Foundation/Enterprise/Advanced row grounded in mechanisms that
      exist in this repo's designs (#125/#126/#127/#130/#131/#138 and
      the ingestion-hygiene design), not in the source's enterprise-
      infrastructure examples verbatim.
- [ ] The default tier, the non-interactive behavior, and the F2
      decision-table composition (factored lookup, row budget under the
      ~20-row threshold, block-not-downgrade semantics for an
      unrecognized/indeterminate tier value) are each stated explicitly.
- [ ] Re-init tier movement is expressed entirely in terms of #127's
      existing per-change monotonicity classification (widening blocks,
      label never trusted, baseline fetched from merge-gated platform
      state, INDETERMINATE = widening), with no new parallel rule.
- [ ] The two honest inversions (source-Advanced capabilities at
      gitapex-Foundation; source-Foundation capabilities unreachable at
      any gitapex tier) are stated, not smoothed over.
- [ ] Per-platform speculation (OIDC availability, path-scoped signature
      rules) is tagged as speculation with a stated degrade path, not
      asserted as fact.

## Related Issue

Child of #82. Extends #127 and #131. Refs #147.

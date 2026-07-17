# Egress-proxy pattern and MCP-server mode: reference analysis for candidate 5

Date: 2026-07-16

Refs #126 (child of #82). Companion doc to #126's decision brief; #126 is
the self-contained, decision-ready record (findings, recommendation, open
risks) -- read #126 first. This doc carries the fuller analysis text
behind that brief.

Orthogonal to #125 (which decided the business-domain policy *evaluation
engine*, an embedded Rego interpreter). This doc is about the
*mediation/hosting* architecture around gitapex's governed operations --
squarely #82's candidate 5 ("middleware / SaaS-integration points beyond
git/GitHub").

## Design-only scope

Per this repository's own discipline (#82's "no design or implementation
beyond the doc" rule, matching #125's own precedent): this doc and #126
record an analysis and a recommendation only. No MCP server is
implemented, no `gitapex status` subcommand is built, no hooks are
rewired, no `.gitapex/ssot.json` schema change is made.

## Trigger

Two adjacent questions came up while working #125, both about mechanisms
*around* gate evaluation rather than the evaluation logic itself:

1. Whether the TLS-terminating, policy-enforcing forward-proxy pattern
   this session's own execution environment uses operationally (observed
   directly: a local forward proxy re-terminates outbound HTTPS via a
   locally-trusted CA, enforces a host-allowlist policy with explicit
   403/407 fail-loud denial and no silent retry, and exposes a local
   diagnostics/status endpoint) is a useful architectural reference for
   gitapex's own governed-operation mediation layer. This is analyzed only
   as a general, publicly-known architecture CLASS (corporate egress
   gateways, service-mesh egress proxies, TLS-inspecting forward proxies
   generally) -- no specific product's proprietary internals are assumed
   or used as source material, consistent with this repository's
   provenance-disclosure discipline (CLAUDE.md section 4).
2. Whether gitapex CLI, invoked in an MCP-server mode, could expose its
   own gate/policy-evaluation surface as Model Context Protocol tools.
   Grounding fact: the upstream `.gitapex/ssot.schema.json`'s `plane`
   enum (which #123 models gitapex's own phase-0 schema on) already
   includes a `"server"` value alongside `pretooluse`/`posttooluse`/
   `stop`/`sessionstart`/`userpromptsubmit`/`pre-commit`/`pre-push`/`ci`
   -- a server-hosted evaluation mode was anticipated by the upstream
   design, never elaborated or implemented anywhere, including gitapex's
   own (not-yet-existing) registry.

## Method

Two independent Fable-model subagent analyses, each instructed to produce
an adversarial EFFECTIVENESS review (not a feasibility rubber-stamp) and a
1-5 score with justification, grounded in: #123's actual current gate list
(`hooks/check-bash-safety.sh`'s 7 deny + 1 warn rules, `hooks/
check-template-overwrite.sh`, the 5 CI workflows), #125's already-decided
embedded-Rego-evaluator design and its "no server, no sidecar" scored
principle, and (for the proxy question only) this session's own observed
proxy behavior generalized to its architecture class.

## Analysis 1: egress-proxy pattern as a reference

### What transfers well

Three lessons transfer at the *policy-semantics* layer, not the
*transport* layer:

- **Fail-loud denial as a hard interface contract.** The proxy class
  denies with an explicit status and instructs callers to report, not
  retry or route around. This corroborates an existing gitapex/CLAUDE.md
  principle (section 4: "fail loudly... never simplify it into an empty
  catch or a silent default") rather than introducing a new one. gitapex's
  gate layer should adopt this as a hard contract: every gate denial
  carries a stable reason code, the violated policy's identity (e.g. the
  Rego rule path), and a remediation pointer.
- **A first-class diagnostics affordance.** The proxy's status endpoint
  maps directly to a `gitapex status` / `gitapex gates explain`
  subcommand: enumerate active gates, the loaded policy bundle version,
  and recent denials with reasons.
- **Single choke point, default-deny-with-explicit-allowlist.** The right
  logical shape for the read-only GitHub wrapper: one evaluation point
  (the embedded evaluator call), not scattered checks.

### What does not transfer

- A TLS-terminating proxy is inherently a long-lived listening service
  requiring locally-trusted CA configuration across every client on a
  machine -- strictly heavier than even a sidecar, and #125 already scored
  every server/sidecar-requiring candidate lower on operational footprint.
  Adopting proxy-style interception for gitapex itself would reverse that
  scored decision.
- The proxy's mechanism exists to govern traffic from clients it does not
  control (arbitrary tools in a sandbox). gitapex's wrapper only needs to
  govern calls it originates itself: instruction (already in CLAUDE.md) +
  a deterministic PreToolUse hook denying raw `gh`/`curl api.github.com`
  invocations + the wrapper physically lacking write codepaths reaches the
  same goal with zero listening sockets and zero CA trust mutation.

### Verdict: 3/5

Useful as a semantics/interface reference, not an architecture to adopt.
Adopt the denial contract and a `gitapex status`-style diagnostics
subcommand into whatever implementation issue eventually carries out
#125's design; reject TLS interception, listening services, and CA trust
mutation as gitapex CLI features. Network-level enforcement of traffic
gitapex does not originate is an adopter-environment/sandbox concern, not
a gitapex product feature -- stated explicitly so this boundary is not
silently forgotten.

## Analysis 2: gitapex CLI as an MCP server

### The transport fork is decisive

- **stdio transport** (the client spawns the same single Class-B binary
  as a session-scoped child process, communicates over stdin/stdout, the
  process dies with the session) does not conflict with #125's "no
  server, no sidecar" decision. Operationally indistinguishable from the
  subprocesses `kind: script` gates already spawn today: no new
  distribution artifact, no adopter-side toolchain, no network listener.
  The honest caveat: it is a longer-lived, stateful process per session
  rather than a fire-and-forget script -- a footprint of zero-deployment
  but nonzero lifetime, which is not what #125's criterion penalized.
- **HTTP/SSE transport** (persistent network listener, multi-client
  concurrency, its own auth surface and deployment story -- "Streamable
  HTTP" in recent spec revisions, flagged as speculation to verify against
  the live spec at modelcontextprotocol.io before implementation) is
  exactly the sidecar #125 already rejected.

Recommendation: stdio only. The schema's `"server"` plane, if ever
implemented, should be documented as meaning "session-scoped stdio
evaluation surface," not a network service.

### Per-gate mapping

- **`hooks/check-bash-safety.sh` / `hooks/check-template-overwrite.sh`
  (PreToolUse):** no real benefit. Claude Code's hook runner executes
  shell commands directly, not MCP tool calls (fact, per current hook
  mechanics -- verify against current Claude Code docs before relying on
  this for implementation). Routing through MCP would add a serialization
  layer to an already-fast, synchronous, sub-30-second path for no gain.
- **CI-plane workflows** (lint, test, toolchain-nix, waza-check,
  sync-agent-instructions): structurally incompatible. No live agent
  session exists during a CI run to hold an MCP session open to. The
  `"server"` plane does not apply to CI regardless of transport.
- **#125's embedded-Rego business-domain gates:** the one real
  beneficiary. Exposing `evaluate_gate(name, input)` / `list_gates()` /
  `explain_denial(id)` as MCP tools would let other agents query live gate
  state before acting ("would this PR pass gate X before I open it?") --
  a genuine capability that does not exist today, since hooks fire only at
  tool-call time and CI only post-push.

### What's genuinely new vs. not

New: pre-action advisory querying and denial explainability across
agents. Not new: for hooks and CI, MCP would be the same capability
through a worse transport -- the actual unification (one evaluator, one
diagnostics format, gates callable by name) is already delivered by
#123's registry plus #125's embedded evaluator; an MCP surface would be a
thin adapter over that core, not the unification itself. Hard limit: MCP
tools are advisory by construction -- a non-cooperating agent simply does
not call them, so the `"server"` plane can never replace
pretooluse/pre-commit/CI enforcement. Framing it as unified *enforcement*
rather than *advisory querying* would be a design error.

### Verdict: 3/5

Worth pursuing only for the #125 Rego business-domain gates, as a
stdio-only, advisory/explainability adapter layered on top of the
embedded evaluator -- not for hook scripts (wrong transport for a
synchronous hot path) or CI (no session to serve). Sequenced strictly
after #123 and #125 land, since there is nothing to adapt until the
registry and evaluator exist.

## Recommendation (summary; full text in #126)

- **Egress-proxy pattern:** adopt the semantics only (fail-loud
  reason-coded denials, `gitapex status`/`gitapex gates explain`
  diagnostics). Reject the mechanism (no TLS interception, no listening
  service, no CA trust mutation).
- **MCP-server mode:** adopt stdio-transport-only, scoped narrowly to
  exposing #125's embedded-Rego business-domain gates for pre-action
  advisory querying and denial explainability. Reject routing existing
  PreToolUse hooks or CI gates through MCP. Reject HTTP/SSE transport.

## Open risks

- MCP protocol transport-lifecycle specifics should be verified against
  the live spec at modelcontextprotocol.io before implementation.
- The residual gap this analysis explicitly scopes out (a misconfigured
  hook could be bypassed by a client that ignores it) is real but assigned
  to the adopter's sandbox/execution environment, not to gitapex itself.
- MCP tools are advisory-only by construction; any future implementation
  issue must not conflate "queryable via MCP" with "enforced."

## Addendum (2026-07-17): corrected premise and refinements distilled from microsoft/agent-governance-toolkit (AGT)

### Corrected premise: redistributed adopters are assumed to have their own MCP server / tool ecosystem

The operator has clarified an assumption this doc did not previously
state: gitapex's redistributed adopters are assumed to already run their
own MCP server(s) with their own tool surface -- not only gitapex's own
three advisory tools (`evaluate_gate`/`list_gates`/`explain_denial`) in
isolation. This does **not** reverse this doc's Analysis 2 verdict --
routing gitapex's own PreToolUse hooks or CI gates through MCP is still
rejected for the same structural reasons (wrong transport for a
synchronous hot path; no session exists during CI). What it does is bring
a genuinely new capability into scope, analyzed below.

### New capability: MCP tool-poisoning / typosquat static analysis

A comparative review against `microsoft/agent-governance-toolkit` (AGT),
verified against its primary-source specs, found AGT's "MCP Security
Gateway" performs static analysis on MCP tool descriptors before they are
exposed to an agent: hidden-Unicode/encoded-payload scanning, rug-pull
fingerprint comparison (detecting a tool's declared schema or behavior
silently changing between scans), and typosquat detection (Levenshtein
distance against a known-good tool-name allowlist). AGT's own gateway is
embeddable and transport-agnostic (no server/sidecar required to run it),
consistent with this doc's own constraints. Under the corrected premise
above, this capability is now in scope for gitapex, retargeted to
gitapex's actual role: gitapex is not consuming AGT's gateway, but the
adopter's broader MCP tool ecosystem is a real, adopter-controlled attack
surface gitapex's governance layer should be able to observe.

Distilled, dependency-free design:

- **Mechanism.** Reuses the content-hygiene primitive specified in #125's
  addendum (hidden Unicode/bidi/zero-width character detection, opaque
  base64 flagging) applied to MCP tool descriptors instead of `.rego`
  files, plus two additions specific to this surface: (a) Levenshtein-
  distance typosquat detection against a registered known-good tool-name
  allowlist, and (b) rug-pull fingerprint comparison -- a pinned hash of
  each known tool's declared schema/description, re-checked on each scan,
  flagging any drift for review rather than silently trusting a changed
  tool.
- **Registry shape.** The known-good tool-name allowlist and pinned
  fingerprints are themselves `policy_sources[]` data (references, not
  inline values -- consistent with #123's discipline), scaffolded at
  `gitapex init` time (see #127) and updated deliberately, not
  auto-accepted.
- **Trigger.** Reuses the existing `"sessionstart"` plane already defined
  in #123's schema -- static analysis runs before tools are made available
  to an agent for the session, matching AGT's own timing choice and this
  doc's existing stdio-session-scoped model. No new plane is needed.
- **Governance discipline.** Per #125's anti-enum-creep rule (grafted from
  Candidate D), adding this as a new `gates[].kind` value (e.g.
  `"mcp-tool-scan"`) must itself cite the concrete need established here
  -- done, by this addendum -- rather than being added speculatively.
- **What this is not:** still advisory/observational, not enforcement of
  third-party agent behavior -- gitapex can flag a suspicious tool
  descriptor to the session, but (per this doc's existing hard limit) it
  cannot compel a non-cooperating MCP client to consult the scan result
  before calling the tool. The value is defense for gitapex's OWN session
  and for cooperating callers, not a network-wide guarantee.

### Fail-closed refinement: three-valued `evaluate_gate` result

AGT's normative "MUST fail closed" discipline exposed a real, previously
unspecified gap in this doc's own `evaluate_gate(name, input)` design:
what does it return when the Rego evaluation itself errors (a missing
`data_ref`, a parse failure, a malformed input document) rather than
cleanly evaluating to allow/deny? Distilled rule: `evaluate_gate` must
return a three-valued result -- `pass` / `deny` / `error (indeterminate)`
-- and an engine error must NEVER be presentable as `pass`. An advisory
tool that answers "pass" on its own internal error is worse than no tool
at all, since its entire value proposition is predicting the enforcing
gate's real verdict. `explain_denial` must cover indeterminate results,
not only clean denials.

### Related, deferred: post-call output-hygiene scanning

A related idea -- applying the same content-hygiene scan to tool CALL
OUTPUT (not just MCP tool descriptors or policy files), catching hidden/
encoded instruction payloads relayed back to an agent after an allowed
tool call completes -- was raised and initially deferred as having no
clearly-owning issue (gitapex's hook architecture only ever denies
pre-call today, never inspects output). This is noted here as a real,
evidenced gap (not hypothetical): during the same design pass that
produced this addendum, the harness running this analysis itself flagged
and neutralized instruction-shaped content inside two subagent research
outputs, an unprompted, concrete instance of exactly this risk class. It
remains outside this doc's own scope (no issue owns gitapex's hook
architecture yet -- #82's candidate 4 is the closest, still unfiled) but
is recorded here rather than silently dropped, for whichever future issue
ends up owning PreToolUse/PostToolUse hook design.

## Addendum (2026-07-17): zero-trust hardening

Per #131 (the binding execution-environment assumptions and zero-trust
principles for this whole initiative), an adversarial audit against this
doc found five concrete gaps.

- **F1 -- stdio parentage is not identity.** This doc's only implicit
  trust boundary is "the client spawned us over stdio," which relocates
  trust to the spawner -- exactly the component the corrected-premise
  addendum above assumes may host poisoned tools (#131 principles 1, 4).
  A compromised MCP client can hammer `evaluate_gate` with pathological
  `input` documents (deep nesting, huge payloads, worst-case rule joins)
  purely to burn CPU; nothing in this doc bounds that. Fix: MCP mode MUST
  NOT attribute authority to the caller under any circumstance (no
  env-derived "who is asking" logic, ever) and MUST be abuse-resistant
  independent of caller identity -- a hard per-call input-size cap (e.g.
  1 MiB), a per-call evaluation timeout, and bounded in-flight
  concurrency (stdio is inherently single-client; serialize), degrading
  to `error(indeterminate)` on any bound violation, never a hang or
  crash.
- **F2 -- `explain_denial` is a gate-evasion oracle.** The fail-loud
  disclosure contract ("every denial carries... the Rego rule path")
  was written for the operator-facing CLI and inherited unexamined by
  the MCP surface, which serves arbitrary session callers. Looping
  `evaluate_gate` + `explain_denial` over candidate inputs is an
  iterative probe for the minimally-evasive PR -- a direct #131 principle
  7 violation. Fix: split disclosure by surface. Over MCP, `explain_denial`
  returns only a stable reason-code enum plus a one-line human summary
  and remediation pointer; Rego rule paths, policy file paths, and engine
  error internals are reserved to a local, operator-invoked `gitapex
  gates explain` CLI subcommand, never exposed over the MCP tool surface.
  This is a fixed build-time contract, not a caller-negotiable flag.
- **F3 -- MCP tool-poisoning allowlist: TOFU bootstrap and attacker-
  writable baseline.** Two related gaps in the tool-poisoning capability
  added above. (a) The rug-pull mechanism "re-checks" a pinned fingerprint
  but never states who establishes pin #1; if #127's `gitapex init` seeds
  it from whatever tools are discoverable at init time, a tool poisoned
  *before* first init becomes the permanently-trusted baseline (#131
  principles 1, 2). Fix: the init-time seed MUST itself pass the same
  hidden-Unicode/encoded-payload/typosquat static checks before being
  accepted as a baseline; a descriptor failing hygiene is written
  `quarantined`, never `pinned`, and the seeded pins land as a reviewable
  diff through the normal code-owner merge gate, not silently into the
  working tree. (b) Since the allowlist/fingerprints are ordinary
  `policy_sources[]` files, a rug-pulling tool (or anything with working-
  tree write access) can update its own pinned hash in the same change
  that swaps its schema -- drift detection would compare against a
  baseline the adversary can edit (#131 principle 4). Fix: the
  `sessionstart` scan resolves fingerprints only from committed,
  merge-gated state (HEAD); a dirty/modified fingerprint file is itself
  flagged as a finding, reusing #125's content-hygiene-over-
  `policy_sources` pass.
- **F4 -- The poisoning scan's own failure mode is unspecified.** This
  doc imports AGT's "MUST fail closed" for `evaluate_gate` but never
  applies it to the new scan -- an unspecified outcome for a malformed
  descriptor, a discovery timeout, or an unreadable allowlist defaults in
  practice to "proceed, assume clean" (#131 principle 6). Fix: a scan
  that cannot complete for any given tool yields `error(indeterminate)`
  *per tool*, reported to the session identically to a positive finding
  -- "unscanned" and "flagged" must never look different from each other
  to the caller. Since the plane is advisory (this doc's existing hard
  limit), "block" remains the cooperating client's decision -- but
  gitapex must never *report* clean on an incomplete scan.
- **F5 -- MCP mode inherits full ambient privilege it does not need.**
  The single binary carries the invoking shell's full environment (tokens,
  proxy credentials, CI secrets) into MCP mode too, even though the MCP
  peer is less trusted by default than a direct hook invocation from the
  agent harness, and the three advisory tools need only repo-tree reads
  plus local Rego evaluation -- no network, no credentials (#131
  principle 3). Fix: `gitapex mcp` (or equivalent) sanitizes its own
  environment at startup (drop everything but an explicit allowlist),
  performs no network I/O by construction in this mode, and confines file
  reads to the repo root -- self-imposed least privilege, verifiable in
  code review, with no dependency on OS-level sandboxing.

No gap was found in the stdio-only transport decision itself (HTTP/SSE
remains correctly rejected) or in the advisory-not-enforcement framing
(F4's fix preserves it) -- reviewed, not silently skipped.

## Non-goals

See #126's own Non-goals section -- identical scope boundary, not
restated here to avoid two sources of truth for the same list.

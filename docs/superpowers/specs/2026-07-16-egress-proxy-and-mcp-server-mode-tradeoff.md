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

## Non-goals

See #126's own Non-goals section -- identical scope boundary, not
restated here to avoid two sources of truth for the same list.

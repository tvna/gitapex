# Zero-trust threat model and execution-environment assumptions

Date: 2026-07-17

Refs #131 (child of #82). Companion doc to #131's decision brief; #131 is
the self-contained, decision-ready record (assumptions, principles,
consolidated findings) -- read #131 first. This doc is the authoritative
source #125/#126/#127/#130's own addenda point back to; it is not
restated in full in each of them.

## Design-only scope

Per this repository's own discipline (matching #123/#125/#126/#127/#130's
precedent): this doc and #131 record binding assumptions and principles
only. No sandboxing, verification, or input-validation code is written by
this pass. Each of #125/#126/#127/#130 carries its own addendum applying
these principles as concrete, foldable-into-implementation design
changes -- see those docs for the per-design specifics.

## Why this doc exists

Every design decision so far in this initiative (#123's "fail loudly,"
#125's "no server, no sidecar," #126's "advisory not enforcement") is a
security-relevant decision, made piecemeal, issue by issue, without a
shared, named threat model underneath them. The operator explicitly
requested this be made foundational, and requires zero trust as the
binding security posture for all of it -- not one input among several to
weigh against convenience or adopter friction.

## Execution-environment assumptions

Facts, consolidated from prior issues (not new claims):

- gitapex is a single static binary CLI (Rust provisional/Go later),
  distributed via a Nix "Class B" SHA-pinned prebuilt-binary pattern, no
  runtime package manager, no server/sidecar/daemon (#125).
- It is REDISTRIBUTED: independent organizations run their own copy
  against their own repos, with their own adopter-authored `.rego` policy
  files (#125) and their own locally-generated `.gitapex/ssot.json`
  instance (#127) -- only the schema is shared upstream.
- Four distinct invocation contexts, each a different implicit trust
  level:
  1. A git hook subprocess (pre-commit/pre-push), local machine or CI.
  2. A Claude-Code-style PreToolUse/PostToolUse/Stop/SessionStart/
     UserPromptSubmit hook subprocess.
  3. A CI job step (ephemeral runner).
  4. An MCP server subprocess (stdio only, #126) -- the least-trusted-by-
     default context: the caller is an arbitrary MCP client, not the
     agent harness itself, and adopters are assumed (per #126's corrected
     premise) to run their own broader MCP tool ecosystem alongside
     gitapex.
- It reads/evaluates a registry (`.gitapex/ssot.json`), files it
  references (`policy_sources[]`), and per-invocation event/context data.
- **Toolchain provisioning is a precondition this doc previously left
  implicit (added 2026-07-17).** None of #123/#125/#126/#127/#130 state
  what provisions the toolchain gitapex itself needs to run (Rust/Go
  runtime for the eventual compiled CLI; today's Python tooling
  dependencies). A separate, earlier initiative
  (`docs/superpowers/specs/2026-07-14-setup-gitapex-toolchain-design.md`)
  already designs this for the "Installed-plugin context (consumers)" --
  gitapex distributed as a Claude Code plugin, invoked via Claude Code
  web or another surface by a redistributed adopter's users: a
  cooldown-gated, Nix-driven bootstrap materializes the bundled flake
  from `${CLAUDE_PLUGIN_ROOT}` into a user-writable cache before any
  tool in the bundle runs. This assumption is now explicit: any design in
  this initiative that runs in that context (#125's embedded evaluator,
  #127's `gitapex init`) implicitly depends on that bootstrap having
  already completed, or triggers it as its own first step -- see #127's
  own addendum for where this is made concrete. `.gitapex/policies/
  toolchain.lock.json` (moved from `.gitapex/toolchain.lock.json`,
  2026-07-17) is registered as a `policy_sources[]` entry under
  `.gitapex/ssot.json` for this reason -- gitapex's own registry now has
  a reference to the toolchain state it depends on, even though
  `flake.nix` remains that state's actual source of truth.

## Binding zero-trust principles

1. **No implicit trust from location or ancestry.**
2. **Every invocation re-validates its own inputs** -- never assume the
   calling environment already filtered anything.
3. **Least privilege everywhere** -- credentials, data exposure, and
   generated permissions are the minimum necessary, never a convenient
   broad default.
4. **Assume breach** -- any single component may be compromised; no
   control may hold only by comparing against a state the same attacker
   could already have influenced.
5. **Verified identity over asserted identity** -- an unauthenticated
   string is a label, not an identity.
6. **Fail closed, including on INDETERMINATE** -- an inability to verify
   is a deny, not an assume-clean.
7. **Minimize information disclosure** -- diagnostic surfaces default to
   minimum necessary detail; verbose internals are reconnaissance value.

These read as a checklist because they are meant to be applied as one:
every future gitapex design decision should be checked against all seven,
not selectively invoked to justify a decision already made on other
grounds.

## Method

Four independent Fable-model adversarial security audits, one per
existing design (#125, #126, #127, #130), each instructed to find
concrete attack surface -- not write generic security prose -- against
these fixed assumptions and principles, each grounded directly in the
actual design documents (not summaries of them). Findings were folded
back into each design's own doc as an addendum; this doc consolidates
pointers only, to avoid two sources of truth for the same content.

## Consolidated findings by design

### #125 (embedded Rego policy engine)

- Unscoped `input`/`data` document exposure: every gate currently would
  see the full context regardless of what it declares needing.
- `kind: "script"` gates (from #123, extended by #125's registry
  dispatch) have no sandboxing discipline -- full env, filesystem, network
  inherited from the CLI process.
- `data_refs` has no namespace/mounting boundary between gates sharing a
  `policy_sources[]` entry -- key collisions and cross-gate data leakage
  are both possible as specified.
- The dependency-audit gate (cargo-deny) checks licenses/advisories but
  not exact-version pinning of `regorus`, and nothing currently asserts a
  builtin allowlist excluding network/environment-disclosure builtins.
- The content-hygiene check's own failure mode (can't parse the file to
  check it) was unspecified -- risk of silent skip-and-evaluate.

Full fixes: see #125's own addendum.

### #126 (MCP-server mode + tool-poisoning scan)

- stdio parentage was treated as an implicit trust boundary; it isn't --
  the design needs caller-identity-independent abuse resistance (size
  caps, timeouts, bounded concurrency).
- `explain_denial` as specified is a gate-evasion oracle over MCP;
  disclosure must be split by surface (minimal over MCP, full detail only
  via an operator-invoked local CLI subcommand).
- The tool-poisoning allowlist has a trust-on-first-use bootstrapping gap
  (a poisoned tool present before first `gitapex init` becomes the
  permanently-trusted baseline) and an attacker-writable baseline at
  re-check time if fingerprints aren't resolved from merge-gated state.
- The poisoning scan's own failure mode was unspecified.
- MCP mode inherits the CLI's full ambient privileges (env vars,
  credentials) though the advisory tools need only repo-tree read and
  local Rego evaluation.

Full fixes: see #126's own addendum.

### #127 (`gitapex init` scaffolding)

- Free-text init inputs can reach generated YAML/CODEOWNERS/JSON
  unescaped -- a template/config-injection surface if not closed-enum or
  validated-pattern by construction.
- Decision-logic immutability (binary-embedded vs. adopter-influenceable)
  was ambiguous and needs an explicit stated boundary with no override
  path.
- Scaffolded native-protection defaults were unspecified -- must default
  to the narrowest viable protection profile, including for solo
  adopters, not a permissive "don't annoy adopters" default.
- The monotonicity re-init check's "live instance" baseline must be
  fetched from actual platform state, not a possibly attacker-influenced
  local registry copy -- and a failed/partial fetch must be classified as
  widening (block), never silently fall back to the local copy.
- The MCP allowlist seeding shares #126's TOFU bootstrapping gap.
- The apply workflow's own credential is the highest-privilege object the
  design creates and needs explicit scoping (fine-grained, single-repo,
  never triggered from `pull_request`) against a pwn-request pattern.

Full fixes: see #127's own addendum.

### #130 (gate-evaluation audit trail)

- `actor` as specified is a self-asserted label, not a verified identity
  -- needs an explicit `verified`/`asserted` provenance split, since a
  signed commit and an unauthenticated CI-run-id env var are not
  equivalent trust levels.
- The hash chain has no specified verifier, verification trigger, or
  externally-anchored head -- without one, it is tamper-evident only in
  theory, rewritable wholesale in practice.
- File-mode 0600 was conflated with integrity; it is a casual-disclosure
  floor only and must be explicitly scoped as such.
- `policy_version` is self-reported by the same process (and dependency)
  it exists to keep honest -- the design needs to state this limit
  explicitly and add an independent recomputation/cross-check pass.
- Audit-write failure was unspecified -- currently an accidental
  fail-open (a full disk silently un-audits every subsequent gate) that
  must become an explicit fail-closed with the availability tradeoff
  acknowledged, not accidental.

Full fixes: see #130's own addendum.

## Open item

A future implementation pass should re-derive its own gate design against
this doc directly, not only against the four per-issue addenda in
isolation -- a cross-cutting interaction between, for example, #126's MCP
privilege sanitization and #127's apply-workflow credential scoping might
not be visible from either issue's own audit alone. This doc is the place
such a cross-cutting review should start.

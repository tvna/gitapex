# Gate-evaluation audit trail: design basis distilled from AGT

Date: 2026-07-17

Refs #130 (child of #82). Companion doc to #130's decision brief; #130 is
the self-contained, decision-ready record (schema, recommendation, open
items) -- read #130 first. This doc carries the fuller comparative-review
reasoning behind that brief.

## Design-only scope

Per this repository's own discipline (#82's "no design or implementation
beyond the doc" rule, matching #123/#125/#126/#127's own precedent): this
doc and #130 record a design basis and a recommendation only. No logging
code, no CLI subcommand, no `.gitapex/ssot.json` schema change, no
signing/Merkle implementation is introduced by this pass.

## Trigger

gitapex has no audit-trail concept anywhere in its design: no record of
which gate fired, when, why, with what verdict, retained for later
inspection. This gap was identified during work on #125 and #126 but
never filed as its own issue. It surfaced concretely during a comparative
design review against `https://github.com/microsoft/agent-governance-
toolkit` (AGT), whose `docs/specs/AUDIT-COMPLIANCE-1.0.md` is a mature,
verified specification for exactly this problem.

## Method

Two independent Fable-model comparative-review passes, each blind to the
other's conclusions, each instructed to find genuinely superior AGT logic
against gitapex's existing decided designs (#123, #125, #126, #127) and
explicitly argue the opposing case before adopting anything -- not to
list AGT's feature surface as automatically superior. Both passes,
independently, identified the audit-trail gap as the one area where AGT
is "genuinely, substantially ahead" (one reviewer's own words) and
converged on materially the same distilled recommendation.

## AGT's verified audit-record shape (primary source, not marketing)

`docs/specs/AUDIT-COMPLIANCE-1.0.md` section 4.3 defines a governance
audit-log-entry with required fields: `entry_id`, `timestamp` (UTC),
`event_type`, `agent_did` (actor identity), `action`, `decision`
(allow/deny/escalate/warn), `policy_decision`, `matched_rule`,
`policy_version` -- stated rationale: "to defend against silent policy
downgrade" -- plus optional `reason` and `latency_ms`. Tamper-evidence is
SHA-256 hash-chaining (`previous_hash` MUST link each entry, section 9)
plus a Merkle tree for later proofs, with timing-safe verification.
Default backends are zero-server: JSONL file (mode 0o600), in-memory, or
plain logging; a REST collector is optional, not required. A companion
example (`examples/crypto-attestation-governed`) additionally does
optional Ed25519 signing of each receipt for non-repudiation.

## Recommendation: minimal default schema (see #130 for the full field list)

Adopt the SHAPE as a design basis -- implemented natively in gitapex's
own Go/Rust codebase, with zero AGT dependency (consistent with #125's
own finding that AGT is not embeddable for gitapex's purposes anyway).
Explicitly strip: `agent_did`/identity fields (gitapex records `actor` as
an existing git/CI identity reference -- a commit SHA or CI run id --
never a new DID-based identity, consistent with #125's addendum rejecting
AGT's identity layer as solving a mesh problem gitapex does not have), a
mandatory REST collector (zero-server by default, per #125's already-
decided "no server" principle), and Merkle proofs / Ed25519 signing as
MANDATORY defaults (see extension tier below).

**`policy_version` is the load-bearing field, kept in full.** Recording a
content hash of the actually-evaluated `.rego` (or script/native rule)
source in every audit entry means a later review can detect that a gate's
underlying policy was quietly weakened between two evaluations, even if
the `.gitapex/ssot.json` registry pointer to it never changed -- AGT's own
stated defense against "silent policy downgrade." This is a runtime
DETECTION mechanism that complements, not duplicates, #127's merge-time
PREVENTION mechanism (CODEOWNERS + branch protection comparing a PR
against its base ref): #127 stops a weakening PR from merging in the
first place; this audit trail catches it if it happens anyway through a
path #127 doesn't cover (a misconfigured protection rule, a direct push
to an unprotected path, a platform migration that temporarily drops
protection). Defense in depth, not redundant machinery.

## Extension tier: reconsidered under an explicit security-first instruction

The first comparative-review pass rejected Merkle proofs and Ed25519
signing outright as disproportionate to gitapex's typical adopter -- a
proportionality call based on likely adopter population, not an absolute
security judgment, and it was presented that way without being fully
distinguished from the harder "does not apply at all" rejections (like
AGT's identity layer -- see #125's and #126's addenda). On explicit
operator instruction to re-examine this specifically under a
security-first (not scope-minimizing) lens, the honest answer required
walking part of it back:

- **Hash-chaining alone (the minimal default) gives tamper-EVIDENCE**: any
  modification to a past entry breaks the chain, detectable by anyone with
  full access to the log file. This defends the common case: a single
  adopter auditing their own local log.
- **It does NOT give non-repudiation** (cryptographic proof of WHICH actor
  wrote an entry, resistant to someone who has the log-writing process's
  own filesystem access) **or efficient third-party spot-verification**
  (an external auditor confirming one entry's inclusion without needing
  the whole log). These are real, non-redundant security properties --
  not padding -- for adopters in regulated or externally-audited
  environments, a genuinely different and narrower population than
  gitapex's typical adopter, but a real one.

Rather than reject this outright (leaving a real gap for adopters who
need it) or force it into the mandatory default (a proportionality error
in the other direction, imposing key-management and Merkle-tree
complexity on every adopter regardless of need), the resolution is to
design the base schema so an **optional `signature` field** (Ed25519,
adopter-supplied key, never a gitapex-managed one) and an **optional
Merkle-proof generation mode** can be layered on without a schema
redesign, opt-in per adopter via `.gitapex/ssot.json` configuration.
**Ship the minimal default now (in the eventual implementation); document
the extension point now (in this design pass); do not build the
extension until a real adopter requirement justifies it** -- YAGNI at the
implementation layer, schema-extensibility discipline at the design
layer. This is the same distinction CLAUDE.md section 4 draws between
stripping needed protection (never do this) and adding unneeded
configurability (avoid this) -- the extension tier is neither: it is
protection some adopters need, deliberately not defaulted onto adopters
who don't.

## What was explicitly rejected, and why (not merely deferred)

- **`agent_did` / SPIFFE/DID-based actor identity**: solves "which AI
  agent, in a mesh of mutually-distrusting long-running processes, wrote
  this" -- a threat gitapex's architecture does not have (no mesh, no
  long-running agent processes; #125's addendum covers this rejection in
  full for the policy-evaluation side, and it applies identically here).
  gitapex's `actor` field references an identity that ALREADY exists and
  is already stronger for gitapex's actual scenario: git commit
  signing, GitHub's own OAuth/App token identity, CI's OIDC-federated
  run identity. Adding a parallel DID registry would not close a gap --
  git/GitHub's existing mechanisms are more mature and more widely
  trusted for gitapex's actual actor population (humans and CI jobs, not
  autonomous agent fleets) -- it would add a new system to secure, a new
  key-rotation surface, and a new single point of failure, which is a net
  security cost, not a net gain, for a threat that is architecturally
  absent.
- **Mandatory REST audit collector**: reintroduces a network dependency
  #125 already decided against (Class B / no-server principle). Remains
  available as an opt-in backend an adopter could build on top of the
  local JSONL default, but is not gitapex's own concern to implement.

## Open items (recorded, not resolved by this doc)

- Exact write path, rotation, and retention policy for the local JSONL
  file.
- Whether the audit log itself should be `.gitignore`'d (loses history
  across clones) or committed (leaks into repo history) -- genuinely
  undecided, needs its own small design pass before implementation.
- The extension tier's exact configuration surface in `.gitapex/ssot.json`
  (a new top-level `audit` block, most likely, but not specified here).

## Non-goals

See #130's own Non-goals section -- identical scope boundary, not
restated here to avoid two sources of truth for the same list.

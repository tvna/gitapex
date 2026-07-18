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

## Open items -- RESOLVED 2026-07-18 (see Addendum below for full briefs)

- ~~Exact write path, rotation, and retention policy for the local JSONL
  file.~~ **Resolved:** per-context sink resolution (persistent user-
  state directory for local/hook/MCP contexts; CI job artifact + printed
  head-hash for the ephemeral-runner context), size-based rotation (10MB,
  10 segments) with an explicit hash-carry-forward mechanism so rotation
  never breaks the chain. See Addendum item 1-2.
- ~~Whether the audit log itself should be `.gitignore`'d (loses history
  across clones) or committed (leaks into repo history) -- genuinely
  undecided, needs its own small design pass before implementation.~~
  **Resolved: `.gitignore`'d, never committed** -- rejected on mechanism
  (pre-commit chicken-and-egg, guaranteed merge conflicts on every gate
  evaluation), not just taste; CI log/artifact anchoring substitutes for
  git-native tamper evidence, with an optional git-ref checkpoint
  (`refs/gitapex/audit`) for adopters wanting stronger anchoring. See
  Addendum item 3.
- ~~The extension tier's exact configuration surface in `.gitapex/ssot.json`
  (a new top-level `audit` block, most likely, but not specified here).~~
  **Resolved:** concrete `audit` block schema, see Addendum item 4.

## Addendum (2026-07-17): zero-trust hardening

Per #131 (the binding execution-environment assumptions and zero-trust
principles for this whole initiative), an adversarial audit against this
doc found five concrete gaps.

- **F1 -- `actor` is a self-asserted label, not a verified identity.**
  "References an identity that ALREADY exists and is already stronger"
  (above) is true of the mechanisms cited (commit signing, OIDC) but the
  schema as specified stores only a *string* the audit-writing process
  asserts about itself -- the strength of the referenced mechanism never
  actually transfers to the record. A signed-and-verified commit SHA
  grounds *who* signed; an unsigned commit SHA identifies *which* commit
  but not *who* authored it with any assurance; a CI-run-id read from an
  env var is an unauthenticated label any code execution inside that job
  can forge (#131 principle 5). Fix: replace the scalar `actor` field
  with `actor: {ref, provenance, verification}` where `provenance` is
  `verified | asserted`. A signed-and-verified commit -> `verified` (with
  `verification: "gpg-signature:<keyid>"` or equivalent); an unsigned
  commit SHA, or a CI run id read from environment without an actually
  fetched-and-validated OIDC token -> `asserted`. Any consumer of this
  audit trail MUST treat `asserted` actors as untrusted context, never as
  attribution.
- **F2 -- tamper-evidence with no specified verifier is tamper-evidence
  in theory only.** The hash chain is "detectable by anyone with full
  access to the log file" but nothing specifies *what* runs verification
  or *when* (#131 principle 4). An attacker who truncates the file and
  rewrites the chain from a chosen point is never caught if nothing
  re-verifies. Fix: (a) a `gitapex audit verify` subcommand; (b)
  automatic incremental verification of the tail entries on every gate
  evaluation before appending, failing closed on mismatch (per F5 below);
  (c) full-chain verification as a documented CI step; (d) the current
  head hash recorded somewhere externally anchored (e.g. printed in CI
  job output, anchored by the runner's own log retention) so a
  truncate-and-rewrite of the whole file is itself detectable -- a chain
  with no externally anchored head is rewritable wholesale.
- **F3 -- mode 0600 and the hash chain are conflated protections.**
  Filesystem permission bits are a weak, host-local control -- void
  against root, void on CI runners sharing a filesystem or restoring
  caches across jobs (#131 principle 4's assume-breach). The design never
  claimed 0600 was sufficient, but never scoped it either, which is how
  conflation calcifies into implementation. Fix: one explicit sentence in
  the schema section -- "0600 reduces casual/accidental disclosure only
  and is not a tamper-evidence or integrity mechanism; integrity comes
  solely from the hash chain plus F2's verification triggers plus the
  optional signature tier. On shared/ephemeral runners, assume the file
  is readable and writable by any code in the job."
- **F4 -- `policy_version` is self-reported by the process it exists to
  keep honest.** The hash is computed and written by the same gitapex
  process (and its `regorus` dependency) whose honesty the field is
  meant to check -- a compromised binary or dependency can evaluate a
  weakened policy while logging the hash of a legitimate one, and nothing
  in the design would catch this (#131 principles 1, 4). This is a
  fundamental limit of self-reported logging, not a bug to silently
  paper over: state it explicitly in the design ("this field defends
  against policy-FILE drift, not evaluator compromise"), then close what
  is closable -- F2's verification pass, run as a separate, less-
  privileged process or a differently-provisioned CI step, recomputes the
  content hash of the policy at the recorded registry ref and flags any
  entry whose `policy_version` matches no policy version reachable in git
  history. This applies the same "cross-check against git's own content-
  addressed store" philosophy F1 applies to `actor`.
- **F5 -- audit-write failure is an unspecified, accidental fail-open.**
  Nothing in the design states what a gate evaluation does when the
  JSONL append itself fails (disk full, permission error, the file
  deleted mid-run). Unspecified defaults to log-and-continue in practice,
  which gives a trivial bypass: fill the disk, and every gate still
  passes unaudited (#131 principle 6, directly). Fix: audit-write failure
  MUST deny the gated operation, with an explicit `verdict: error` reason
  surfaced to the caller (CLAUDE.md section 4's "fail loudly"). This
  creates a real, deliberate availability-vs-security tradeoff (a full
  disk can now deny legitimate operations) -- record it as an accepted,
  explicit tradeoff with a logged-elsewhere break-glass override as the
  only escape hatch, never as a silent default.

The rejections of a mandatory REST collector and DID-based identity
(above) remain sound as rejections -- no reintroduction is warranted.
One caveat on the optional Ed25519 signature tier: a signature made by a
key resident on the same compromised host signs lies fluently -- the tier
buys non-repudiation of *authorship*, not truthfulness of *content*. Add
one sentence to the extension-tier section stating this limit explicitly,
so it is not overclaimed later.

## Addendum (2026-07-18): write path, rotation, commit policy, extension-tier schema

### 1. Write path -- one algorithm, per-context sink

Not one universal path. **Local/hook/MCP contexts (git hook, Claude-
Code-style hook, MCP subprocess):**
`${XDG_STATE_HOME:-~/.local/state}/gitapex/audit/<repo-fingerprint>/audit.jsonl`,
where `<repo-fingerprint>` is the first 16 hex chars of SHA-256 over the
repository's root-commit SHA -- stable across clones/moves, unlike a
path hash. XDG state (not cache, which is deletable by contract) survives
repeated hook firings, stays outside the worktree (no accidental commit,
no MCP client reading it through repo-tree tools -- #131 principle 7). If
unwritable (a read-only MCP container), F5's fail-closed applies unless
`audit.sink.mode: "custom"` names a writable path.

**Ephemeral CI-runner context:** append to a runner-scratch path (e.g.
`$RUNNER_TEMP/gitapex-audit/audit.jsonl`), then two mandatory job-end
steps: upload as a CI artifact, and print the chain-head hash into the
job log -- exactly the "externally anchored head" F2 already requires;
CI's own log/artifact retention IS the persistence layer here, since
nothing else outlives the runner.

One feature, not two: entry schema, hash chain, append logic, and verify
logic are identical everywhere; only the resolved sink directory and the
anchoring step differ per context.

### 2. Rotation and retention -- size-based, with mandatory hash carry-forward

Rotate at 10MB; keep 10 closed segments locally (~100MB ceiling); CI
retention is owned by the platform's artifact-retention policy (external
responsibility, consistent with zero-server). Naive rotation breaks the
chain at every boundary -- a fresh file with a null `previous_hash` seed
hands an attacker a free truncation point per rotation, defeating F2's
whole tamper-evidence result. Concrete carry-forward: on rotation, the
closed segment is renamed `audit-<seq>-<head8>.jsonl` (`head8` = first 8
hex chars of its final entry hash); the new segment's FIRST entry is
itself an audited event (`event_type: "audit_rotation"`, `previous_hash`
= the closed segment's full head hash, payload records the closed
segment's filename/entry-count/head-hash). `gitapex audit verify` (F2a)
walks segments oldest-to-newest checking each rotation entry against its
predecessor's actual final hash -- retention pruning deletes only whole
oldest segments, and the oldest retained segment's rotation entry still
names its pruned predecessor's head hash, so verification distinguishes
"pruned by policy" (boundary intact) from "tampered" (hash mismatch).

### 3. Commit vs. `.gitignore` -- gitignored, anchoring substitutes for git history

Rejected on mechanism, not taste: (a) a pre-commit hook cannot cleanly
add its own audit entry to the commit being created -- per-entry
committing is a chicken-and-egg; (b) an append-only file touched by
every gate evaluation guarantees merge conflicts across concurrent
branches and pollutes every diff (the exact quality-vs-volume failure
CLAUDE.md section 5 names); (c) #127's protected-path category exists
for HUMAN-REVIEWED policy definitions -- putting a machine append-stream
behind CODEOWNERS review either blocks every evaluation on a PR or
forces auto-approval that hollows the protection out. The audit trail is
evidence, not policy; it does not belong in that category. The "an
uncommitted log on an ephemeral runner proves nothing" objection is
answered by item 1's CI anchoring made MANDATORY (head hash printed to
platform-retained job logs, artifact uploaded) -- a truncate-and-rewrite
is detectable against state the attacker's job cannot rewrite. For
adopters wanting git-native anchoring, the extension tier (item 4) offers
`audit.anchor.git_ref` (e.g. `refs/gitapex/audit`): push ~100-byte
head-hash checkpoint records to a non-branch ref (gh-pages-style
precedent), anchoring the head hash only, never the log body -- no
history pollution.

### 4. Extension-tier configuration surface

```jsonc
// .gitapex/ssot.json -- new top-level "audit" object
"audit": {
  "enabled": true,
  "sink": { "mode": "auto", "path": null },          // auto | state-dir | workspace | custom
  "rotation": { "max_bytes": 10485760, "max_segments": 10 },
  "anchor": { "ci_log": true, "git_ref": null },      // git_ref: e.g. "refs/gitapex/audit"
  "signing": { "enabled": false, "key_ref": null },   // key_ref = a policy_sources[] id
  "merkle_proofs": { "enabled": false, "checkpoint_interval": 1000 }
}
```

`signing.key_ref` references an existing `policy_sources[]` entry id
(consistent with how `data_refs` and `toolchain.lock.json` already
resolve), whose file holds the PUBLIC key / key locator only -- merge-
gated behind #127's protection, so key substitution requires passing the
same review gate as a policy change; the private key is adopter-supplied
via keychain/env, never a repo value. Deliberate absence: there is no
`fail_open` knob anywhere in this block -- F5's fail-closed is not
configuration, and its break-glass path stays an out-of-band, logged-
elsewhere override, never a flag an adopter can flip.

## Non-goals

See #130's own Non-goals section -- identical scope boundary, not
restated here to avoid two sources of truth for the same list.

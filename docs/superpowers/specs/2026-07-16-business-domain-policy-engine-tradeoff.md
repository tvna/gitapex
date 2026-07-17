# Business-domain policy-engine pattern: OPA/Rego vs. gitapex-bespoke tradeoff

Date: 2026-07-16

Refs #125 (child of #82). Companion doc to #125's decision brief; #125 is
the self-contained, decision-ready record (scored table, recommendation,
grafted ideas, open risks). This doc carries the fuller worked-example
detail behind that table -- read #125 first.

Answers #123's Addendum, which explicitly left this comparison open for
candidates 2 and 5 of #82 (business-domain governance for gitapex's
redistributed downstream adopters) while scoping #123 itself to a narrower,
already-decided "no OPA/Rego" phase-0 self-referential gate registry.

## Design-only scope

Per this repository's own discipline (#82's "no design or implementation
beyond the doc" rule, and the merge-retrospective skill's stop boundary
applied at the initiative level): this doc and #125 record a comparison and
a recommendation. No `.gitapex/ssot.json` schema change, Rego file, or
Rust/Go code is introduced by this pass. A future implementation issue,
filed separately once someone actually starts building, would carry out
the schema diff and evaluator embedding recommended below.

## Method

Four starting candidates were seeded (from #123's Addendum framing and the
operator's own prior naming), each elaborated into a concrete design sketch
by an independent model run (schema diffs, worked Rego examples, CLI
invocation sketches -- not prose-only), each of which also proposed its own
refined variant rather than being limited to the seed framing:

- **A -- Layer split.** gitapex's own self-referential gate registry
  (#123's exact scope) stays unchanged. The business-domain layer gets an
  entirely separate parallel registry, `.gitapex/governance.json`, plus a
  `.gitapex/policies/*.rego` tree, evaluated via an embedded Rego
  interpreter. Author-recommended variant A': routing stays solely in
  `ssot.json` (no second routing registry); `governance.json` becomes a
  pure policy manifest referenced by ordinary `ssot.json` gate rows.
- **B -- Per-policy-source opt-in.** Extend `.gitapex/ssot.json`'s existing
  `policy_sources[].format` enum (today `toml|json|yaml`) with `rego`. The
  same registry serves both gitapex's own gates and adopter business-domain
  gates; `gates[].kind` gains a `"policy"` value plus `engine: "rego"` and
  `domain: self|business`. A `data_refs` field lets a Rego rule pull
  thresholds from separate toml/json/yaml sources instead of hardcoding
  values. Author-recommended variant: keep `format` purely descriptive
  (serialization-language only); make `kind:"policy"+engine:"rego"` the
  sole evaluation-dispatch switch.
- **C -- OPA as an embedded evaluation engine only.** Registry format 100%
  unchanged from #123. OPA is invoked only for the specific gates whose
  condition needs it. Base design: `opa build -t wasm`, embedded via a Rust
  WASM runtime (wasmtime), gate references a SHA-pinned compiled bundle.
  Author-recommended variant C-prime: skip WASM and the `opa build` step
  entirely; embed the pure-Rust `regorus` interpreter (Microsoft,
  Apache-2.0) and evaluate the registered `.rego` **source** file directly
  -- no compile step, no committed binary artifact, no drift gate needed
  (source is the artifact).
- **D -- Abstract rule-expression mini-format with a Rego fallback.**
  gitapex defines its own closed, quantifier-free JSON rule language
  (`gax-expr`) for simple business-domain gates (comparisons + boolean
  combinators, no iteration). Genuinely complex multi-source-correlation
  gates (the schema-migration example: "destructive AND no compatible view
  AND fewer than N days left in the deprecation window") exceed the
  mini-format's ceiling by construction and fall back to raw embedded Rego.
  Author-recommended variant D': the CLI deterministically transpiles
  `gax-expr` to Rego and runs everything through one embedded engine,
  rather than maintaining a second bespoke interpreter.

Each candidate (scored as its author-recommended variant, where one was
stated) was then scored 1-5 by **five independent judge passes, one per
criterion**, each judge blind to the others' scores, each scoring all four
candidates on that one criterion only (to avoid one grader's halo effect
carrying across criteria for the same candidate). The five criteria are
#123's Addendum's own framing, used verbatim per this pass's own
instruction not to substitute a different rubric without stating why -- no
substitution was made.

## Scored comparison

| Criterion | A: Layer split | B: Per-source opt-in | C: Embedded engine (C-prime) | D: Mini-DSL + fallback |
|---|---|---|---|---|
| 1. Redistribution learning-cost delta | 3 | 5 | 4 | 2 |
| 2. gitapex maintainer cost | 3 | 4 | 5 | 2 |
| 3. Consistency with #123 precedent | 5 | 2 | 4 | 4 |
| 4. Extensibility ceiling | 4 | 5 | 4 | 5 |
| 5. Operational dependency footprint | 3 | 5 | 5 | 5 |
| **Total /25** | **18** | **21** | **22** | **18** |

### Judge rationale, condensed per criterion

**1. Redistribution learning-cost delta** (best: B, then C, then A, then D)
B and C both make Rego strictly opt-in per gate rather than forcing it
uniformly across the whole business-domain layer (A's issue) or inventing
a second non-transferable format as the default authoring path (D's
issue, only partially offset by a read-only "view compiled Rego" on-ramp).
B edges out C via `data_refs`, which further shrinks the amount of raw
Rego an adopter must actually write.

**2. gitapex maintainer cost** (best: C, then B, then A, then D)
C-prime adds zero new registry schema and needs no drift gate at all
("source is the artifact"). B extends the existing single-registry/
single-validator pattern incrementally. A durably adds a second file
format and validator even after its own drift-risk fix. D commits gitapex
to owning a bespoke DSL's full lifecycle (spec, compiler, error taxonomy,
versioning, conformance tests) stacked on top of the same Rego dependency
the cheaper candidates carry alone.

**3. Consistency with #123 precedent** (best: A, then D and C roughly
tied, then B) A needs zero enum/schema change to `ssot.json` itself and
replicates #123's reference-only discipline in a twin file. D and C both
keep compiled artifacts, inline bodies, and format/executable conflation
out of `ssot.json`'s core schema, differing only in how much rule-specific
schema surface leaks into the core registry vs. staying externalized. B is
weakest: even its recommended variant still lists `rego` (an executable
language) as a peer value in the `format` enum whose entire prior contract
was "passive serialization descriptor."

**4. Extensibility ceiling** (best: D and B tied, then C, then A) D is the
only candidate that stress-tests itself against gitapex's own three
illustrative examples and reports results plainly (migrations exceed the
mini-format immediately; the escape hatch is full Rego; the ceiling is
machine-enforced via JSON Schema, not a style guideline). B names a
concrete mechanism (`data_refs`) for the hardest part of the flagship
example. C's C-prime variant reaches the same ceiling as A/B and is honest
about the base (non-prime) design's WASM builtin restrictions. A asserts
"no ceiling" without engaging the specific examples or naming a
cross-source-correlation mechanism -- true but underspecified.

**5. Operational dependency footprint** (best: B, C-prime, and D
effectively tied, then A) B, C-prime, and D are all fully embedded in a
single static binary with no server, no sidecar, and no adopter-side
toolchain, even during a transition period. A's steady-state architecture
is equally clean, but its *proposed interim bridge* -- shelling out to a
pinned `opa` binary as a 5th Class B tool during the current Python-tooling
period -- is a real, currently-active instance of the exact
runtime-invoked-external-binary pattern this criterion penalizes, even
though it is framed as temporary.

## Recommendation: synthesized winning pattern

**Winner: Candidate C, as C-prime -- "Embedded Rego Interpreter,
Registry-Referenced Only."**

### Schema shape

```jsonc
// .gitapex/ssot.json -- policy_sources, extended
{
  "id": "acme-migration-policy",
  "path": ".gitapex/policies/business/schema_migration.rego",
  "format": "rego",              // descriptive only -- see dispatch note below
  "authority": "Deny rules for destructive or unpaired schema migrations",
  "data_refs": ["migration-limits"]   // grafted from Candidate B
}

// .gitapex/ssot.json -- gates, extended
{
  "id": "schema-migration-guard",
  "kind": "opa-rego",             // the SOLE evaluation-dispatch switch (grafted principle from B)
  "rule": "Migrations must be reversible, approved, and never touch frozen tables",
  "planes": ["pre-push", "ci"],
  "trigger": "changed_files matches .gitapex/migrations/**",
  "policy_refs": ["acme-migration-policy", "migration-limits"],
  "cluster": "business-domain",
  "tracking_issue": null
}
```

`format: "rego"` is a serialization/language descriptor only -- nothing
dispatches on it (grafted from B's recommended variant, closing the
"constraint blur" the judge panel flagged in B's own base design and in
C's base design equally). `kind: "opa-rego"` is what a validator and the
CLI's evaluator both key off; a `scan_ssot_schema.py`-style drift gate
(grafted governance discipline from D) cross-checks `kind` against the
referenced file's actual extension and schema validity, and rejects any
silent structural fallback between evaluation paths.

### Evaluation

`regorus` (pure-Rust, statically linked, no cgo, no sidecar, no server) is
embedded directly into gitapex's planned single-binary CLI and evaluates
the registered `.rego` source file, loading `data_refs`-listed
`policy_sources` as the Rego `data` document (values -- thresholds,
allowlists -- stay in declarative toml/json/yaml files; the `.rego` file
holds logic only, reinforcing #123's discipline at the content level, not
only the registry level).

### Governance discipline for future engine additions

Grafted from D's own written anti-DSL-creep admission rule, generalized:
any future policy-engine addition (a second `kind` enum value -- CEL,
Cedar, WASM) must cite concrete gates that need it and state why `opa-rego`
does not suffice, in the PR that proposes it. This keeps `kind`'s enum
from growing speculatively.

### Adopter ownership-boundary convention (optional)

Grafted from A: redistributed adopters may, by convention, keep their own
authored `.rego` files under a distinct path (e.g.
`.gitapex/policies/business/`) even though they are registered in the same
`ssot.json` gitapex itself uses for its phase-0 gates -- giving a soft
ownership boundary without forking the registry file. This is a
convention, not a structural split; see open risks below for when a harder
split (Candidate A's fuller design) would be warranted instead.

## Open risks

- **The `input` document contract is real, unaddressed API surface.**
  Every candidate underspecifies what fields the CLI assembles and passes
  to the evaluator per plane/trigger. This needs its own versioned spec
  (e.g. `change/v1`), tested and documented on its own, before
  implementation -- regardless of which candidate is chosen.
- **`regorus` conformance is unverified** against the specific builtins
  gitapex's own worked examples use (`time.*`, `sprintf`, set
  comprehensions). Flagged as speculation, not fact, in the underlying
  design sketches; needs a conformance smoke test before adoption.
- **Rust-vs-Go is still open** (`docs/versioning.md`). `regorus` is
  Rust-only; choosing Go would mean falling back to OPA's own pure-Go
  `github.com/open-policy-agent/opa/rego` package instead -- likely better
  conformance, but a different embedding decision. This recommendation
  assumes Rust; revisit if Go wins.
- ~~**The ownership-boundary convention is soft.** If gitapex's
  redistribution mechanism (how config behaves when forked/vendored into a
  downstream repo) turns out to need a harder separation than a path
  convention provides, revisit against Candidate A's fuller structural
  split (a genuinely separate `governance.json` registry file).~~
  **Resolved (2026-07-17):** gitapex redistributes the SCHEMA only
  (`.gitapex/ssot.schema.json`). Each adopting repo's actual
  `.gitapex/ssot.json` instance is generated locally by a `gitapex init`
  step, which decides branch-strategy/git-workflow config from that
  repo's business-domain and team-size requirements -- see
  https://github.com/tvna/gitapex/issues/127. Since instances are
  freshly generated per-repo rather than forked/merged from an upstream
  instance, the merge-conflict scenario Candidate A's structural split
  was hedging against does not exist. This confirms the winning C-prime
  design (single `ssot.json`, no separate registry file) was correct for
  this reason too, not merely acceptable. Does not reopen this doc's
  recommendation.

## Addendum (2026-07-17): gitapex init is new, separately-scoped work

The `gitapex init` scaffolding step referenced above -- generating an
initial `.gitapex/ssot.json` instance from business-domain and team-size
inputs, including branch-strategy/git-workflow decisions -- was previously
undesigned anywhere (not #123, not this doc, not #126). It is filed
separately as https://github.com/tvna/gitapex/issues/127 (child of #82),
including an open question worth noting here since it touches this doc's
own `regorus` embedding decision: whether `init`'s (domain, team-size) ->
workflow decision logic should be hardcoded in the CLI or could reuse the
same embedded `regorus` evaluator this doc recommends for runtime gate
evaluation -- i.e. a possible reuse synergy for the embedding decision,
not yet resolved either way. See #127 for the full scope.

## Addendum (2026-07-17): refinements distilled from microsoft/agent-governance-toolkit (AGT)

A comparative review against `microsoft/agent-governance-toolkit` (a large,
mature Microsoft governance framework; verified against its primary-source
specs, not its marketing) confirmed this doc's core architecture rather
than superseding it: AGT does not embed Rego -- its `opa` feature shells
out to an external `opa` binary at runtime, exactly the adopter-side
toolchain dependency this doc's `regorus`-embedding decision was designed
to eliminate. Adopting AGT for Rego evaluation would violate this doc's
own constraints, not satisfy them; this doc's recommendation stands
unchanged. Two independent comparative-review passes converged on the
following narrow, distilled refinements (principles only -- no AGT
dependency, no AGT code):

- **Fixture-suite as a single deterministic gate for two open risks.**
  AGT pairs every normative surface with a versioned spec plus an
  executable conformance-test corpus. Distilled: `change/v1` (the still-
  unspecified input-document contract, first open risk above) and
  `regorus`'s Rego-builtin conformance (second open risk above) can be
  closed by ONE artifact -- a committed corpus of golden input documents,
  evaluated against known `.rego` policies, with pinned expected verdicts,
  run in CI and re-run as a conformance canary on every `regorus` version
  bump. This turns two recorded-but-unaddressed risks into one concrete,
  buildable gate (CLAUDE.md section 3's "build the gate before the
  operation it guards").
- **Dependency supply-chain audit gate.** AGT's `deny.toml` (cargo-deny
  config) reflects a deterministic CI gate over its own engine's
  dependency closure (advisories, licenses). Distilled principle: the
  embedded Rego evaluator's dependency tree is itself a governed artifact.
  Add a language-appropriate equivalent (`cargo-deny` for Rust,
  `govulncheck`+license-check for Go) as a CI gate on whichever engine
  crate/module wins the Rust-vs-Go decision -- record this requirement as
  one of that decision's inputs, not an afterthought once the language is
  picked.
- **Drift-gate content-hygiene check.** AGT's MCP Security Gateway
  performs static analysis on tool descriptors before they are exposed to
  agents (hidden Unicode, encoded/base64 payloads, role-override strings).
  Distilled principle, retargeted to gitapex's actual exposure (gitapex is
  not an MCP client consuming third-party tools here -- see #126's
  addendum for where the MCP-specific version of this applies): the
  existing `kind`/format cross-check drift gate (this doc's "Evaluation"
  section) should be extended with a content-hygiene pass over every file
  a `policy_sources[]` entry resolves to -- reject non-ASCII control,
  bidirectional-override, and zero-width Unicode characters; flag large
  opaque base64 literals for manual review. Rationale: `explain_denial`
  (per #126) and any future gate-explanation surface relays a `.rego`
  file's rule names, comments, and string literals into an agent's
  context. A hidden-Unicode or encoded payload in a policy file is exactly
  the class of content human review reliably misses and #127's
  branch-protection mitigation (who can merge) does not inspect (what the
  merged bytes contain) -- this is a complementary, not duplicate, check.
  This is a general-purpose primitive (also reused by #126's MCP
  tool-descriptor scan) -- implement it once, call it from both sites.

These three items refine this doc's design; they do not change the
Candidate C-prime recommendation, the schema shape, or the scored
comparison above.

**Correction to the content-hygiene wording above:** "flag large opaque
base64 literals for manual review" is superseded by the zero-trust
addendum below (F5) -- a flagged literal blocks by default, not warn-
and-proceed.

## Addendum (2026-07-17): zero-trust hardening

Per #131 (the binding execution-environment assumptions and zero-trust
principles for this whole initiative), an adversarial audit against this
doc found five concrete gaps. Each is a design change to fold into a
future implementation pass, not a reversal of the Candidate C-prime
recommendation.

- **F1 -- Unscoped input, least-privilege violation.** The `change/v1`
  contract (still an open risk above) defaults toward one blanket
  document handed to every gate's Rego evaluation regardless of what that
  gate's rule actually reads. Since adopter-authored `.rego` files are
  untrusted under "assume breach" (#131 principle 4), an unrelated gate's
  malicious or buggy rule could read fields it never needed and leak them
  via its own denial message. Fix: every `kind: "opa-rego"` gate entry
  gains a required `input_scope: [...]` array of `change/v1` field paths;
  the CLI assembles only those fields, an undeclared field is simply
  absent (not merely filtered after assembly); the drift gate statically
  rejects a `.rego` source whose parsed AST references an `input.` path
  outside its own declared scope.
- **F2 -- `kind: "script"` is unsandboxed.** This #123-era kind (extended,
  not introduced, by #125's registry dispatch) runs adopter-registered
  subprocesses with the CLI's full ambient privileges -- full env
  (including CI secrets in the CI invocation context, MCP-client-provided
  env in the MCP context per #126), full filesystem, full network. Under
  #131 principles 3 and 4, a compromised or malicious script-kind entry is
  unmediated credential exfiltration. Fix, mirroring #125's own
  anti-enum-creep governance discipline applied to script capabilities
  rather than to new `kind` values: two required fields on `kind:
  "script"` entries -- `env_allowlist: []` (empty default; the CLI
  constructs a clean environment for the subprocess, never inherits) and
  `network: "none" | "declared"` (default `"none"`, enforced best-effort;
  `"declared"` requires a written justification string in the registry
  entry). The drift gate rejects a script entry missing either field.
- **F3 -- `data_refs` has no namespace boundary.** "Loaded as the Rego
  `data` document" (singular, unscoped) creates two gaps: key collisions
  between two gates' threshold files silently change a verdict
  (last-load-wins), and `data_refs` resolution is transitive through a
  `policy_sources[]` entry's own declarations, so editing one *source*
  can inject data into every *gate* that references it -- a cross-gate
  smuggling path the content-hygiene check (byte-level, not scope-aware)
  does not see. Fix: each `data_ref` mounts under `data.<source_id>`,
  never at the document root; duplicate source ids or any cross-mount key
  collision is a registry-validation error (fails closed, #131 principle
  6); a gate's evaluation loads only `data_refs` reachable from its own
  declared `policy_refs`, and the drift gate verifies this closure is
  declared, not silently inherited.
- **F4 -- `regorus` pinning and builtin surface.** The dependency-audit
  gate (added above) checks licenses/advisories but not exact-version
  pinning, inconsistent with the Class B binary's own SHA-pinned
  distribution discipline. Separately: upstream OPA/Rego ships
  network-capable builtins (`http.send`, `net.lookup_ip_addr`) and
  environment-disclosure builtins (`opa.runtime`); nothing in this design
  currently *requires* these be absent or disabled in the embedded
  evaluator, so a future `regorus` version silently adding support for one
  would turn every adopter-authored `.rego` file into an undeclared egress
  channel. Fix: (a) the committed lockfile pins `regorus` to an exact
  version and checksum, CI fails on lockfile drift, and the fixture-suite
  conformance canary (added above) is keyed to that pinned version; (b)
  the fixture corpus includes negative fixtures asserting network- and
  environment-disclosure builtins are absent or explicitly disabled --
  an enforced builtin allowlist, verified by test, not assumed by design.
- **F5 -- Content-hygiene check must fail closed, including its own
  failure.** The hygiene check added above did not specify what happens
  when it cannot itself run (an unreadable file, an unparseable encoding).
  Under #131 principle 6, this is INDETERMINATE, not "assume clean": a
  hygiene-check error blocks evaluation for every gate referencing that
  source, full stop -- never skip-the-check-and-evaluate-anyway. Likewise,
  "flag for manual review" (as originally worded above) is a fail-open
  warn-and-proceed path in practice; corrected to: a flagged base64
  literal blocks evaluation until its content hash is explicitly
  allowlisted in the registry entry (`content_exceptions: ["sha256:..."]`),
  turning "manual review" into a recorded, diffable, reviewable decision
  rather than a silent pass-through.

No exploitable gap was found in the `kind`/format dispatch mechanism
itself (no confused-deputy path between `format: "rego"` and `kind`), or
in the single-static-binary/no-sidecar architecture (it eliminates the
whole class of server-attack-surface by construction) -- these are noted
as reviewed, not silently skipped.

## Non-goals

See #125's own Non-goals section -- identical scope boundary, not restated
here to avoid two sources of truth for the same list.

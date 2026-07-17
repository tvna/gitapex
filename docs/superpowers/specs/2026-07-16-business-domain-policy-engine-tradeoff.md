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

## Non-goals

See #125's own Non-goals section -- identical scope boundary, not restated
here to avoid two sources of truth for the same list.

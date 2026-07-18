# A cross-document drift gate for the docs/superpowers/specs/ chain

Date: 2026-07-18

Refs #152 (child of #82). Extends #144/#145 (a distinct gate shape --
see Decision 0) and covers the existing #127/#147/#148/#151 chain as its
worked example and backfill target. Design-only; does not reopen any of
those four docs' content or decisions.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#144/#145/#147/#148/#151 precedent): this doc records a design
only. No `.github/scripts/gate_*.py` file, no registry file, no CI
wiring is created by this pass. Implementing it as real code (matching
how #144's design became `gate_owasp_asi_mapping.py`) is a later,
separate step.

## Why this doc exists

Four docs now form a real dependency chain, not just a citation list:

- #151's devcontainer tier-content table hardcodes #147's `security-tier`
  closed enum (`foundation | enterprise | advanced`) -- if #147 later
  renames or adds a tier, #151's table silently goes stale.
- #151's Decision 3 ("phase 3 does not consume business-domain hearing
  output") rests on #148's Decision 1 guarantee ("Business domain
  contributes zero decision-table keys, zero schema fields... and zero
  enforced state") -- if #148 is later revised, #151's argument's
  premise disappears with nothing to flag it.
- #148 itself rests on #127's specific, argued reason for dropping
  `business-domain` as a gating key -- the same pattern one layer up.

CLAUDE.md section 3 names this class of gap directly: "Establishing an
invariant... is such an operation: ship its drift gate in the same
change, not a follow-up." Strictly read, that obligation was missed
starting at #147 -- the first doc in this chain another doc came to
depend on -- not first at #151 or now. This design exists to define the
gate that should have shipped then, and to backfill the chain that
already exists (Decision 4) rather than deferring that too.

## Decision 0: distinct from #144/#145's existing gates

#144/#145's `gate_owasp_asi_mapping.py`/`gate_owasp_llm_mapping.py`
check ONE document's table completeness against a closed EXTERNAL list
-- OWASP's own official ASI01-10/LLM01-10 category IDs, an authority
outside this repo. This design is about INTERNAL cross-document
consistency -- multiple gitapex-authored docs citing each other's
specific values, with gitapex's own earlier doc as the authority. Same
underlying discipline (ship the drift gate with the invariant), a
structurally different check (external-list completeness vs.
internal-citation equality). Kept as a sibling design, not folded into
either existing gate, for the same independent-versioning reason #145
gave for keeping its own gate separate from #144's.

## Decision 1: split what a deterministic gate can check from what needs review

**Decision: the gate verifies mechanical facts about text (a value set
matches; a quoted sentence still appears verbatim) -- never whether a
downstream argument BUILT on an upstream fact is still sound. That
judgment is a review-agent's job, per CLAUDE.md section 3's own split
("review/repair agents... handle the semantic judgment determinism
cannot, not artifact code"), not a script's.**

Concrete example of what stays out of deterministic-gate scope, named
explicitly rather than left implicit: if #148's Decision 1 sentence
changes from "contributes zero... schema fields" to "contributes one
schema field, X" -- the gate below (Decision 3) WILL catch that the old
quoted sentence disappeared and fail loudly. What it will NOT do is
evaluate whether #151's Decision 3 argument ("therefore phase 3 cannot
consume hearing output") is still correct once #148 allows a schema
field -- that re-evaluation is exactly the kind of judgment call this
repo already routes to a review pass at a concentrated point (CLAUDE.md
section 3), not something a regex should attempt. The gate's job ends at
"the fact you cited changed -- go look," never "the fact you cited
changed, and here is whether your argument still holds."

Two dependency kinds fall out of this split, both mechanically checkable
without pretending to parse prose semantics:

## Decision 2: closed-enum consistency (worked example: #147 <-> #151)

When a source doc declares a canonical closed enum inline, in the
pattern this repo's docs already use unprompted -- `` `field-name`:
`value-a | value-b | value-c` `` (backtick-wrapped field name, colon,
backtick-wrapped pipe-separated values) -- any consumer doc that
tabulates or restates that same value set must match it exactly: same
set, no additions, no omissions, no renames.

**Worked example, already true of the real text today (no doc edit
required for this design to be checkable):** #147 contains the literal
substring `` `security-tier`: `foundation | enterprise | advanced` ``
in its Decision-1-equivalent section. #151's "Devcontainer content by
tier" table has first-column values `` `foundation` ``, `` `enterprise`
``, `` `advanced` `` under a `security-tier` header. A gate extracts the
source enum via a regex anchored on the declaration pattern, extracts
the consumer's value set from the table rows (skipping header/separator
rows, same shape as #144/#145's `_ROW_RE` approach), and asserts set
equality. Mismatch in either direction (a value #151 tabulates that
#147 no longer declares, or a value #147 declares that #151's table
omits) is a hard failure naming exactly which value is out of sync.

## Decision 3: quoted-guarantee presence (worked example: #148 <-> #151)

Not every cross-doc dependency is enum-shaped. #148's Decision 1
guarantee is a sentence, not a value list. For this class, the registry
records the exact sentence as a literal string; the gate's check is that
the string still appears in the source doc, compared after
**whitespace normalization** (line breaks and repeated spaces collapsed
to a single space on both the registry's stored quote and the source
doc's text before comparison) -- not raw byte-for-byte equality. This
is deliberately blunt -- it does not verify the consumer's argument,
only that the specific fact it quoted has not silently changed
underneath it (Decision 1's boundary, restated concretely).

**Why normalization, stated from a real finding, not assumed upfront:**
verifying this design's own worked example against the actual #148 text
this session found that the guarantee sentence wraps across three
markdown source lines (`docs/superpowers/specs/2026-07-18-init-hearing-fable-design.md`
lines 88-90) -- semantically one sentence, but not one line. A literal
byte-for-byte grep failed on it despite the guarantee being completely
unchanged; only a rewrap, not a rewrite. Requiring raw byte equality
would make the gate fire on routine markdown reflow (a paragraph
re-wrapped by an editor, no meaning changed) -- a worse false-positive
than the accepted one below, because it punishes formatting, not
content. Whitespace normalization is the fix, verified against this
exact case.

**Worked example, verified against the real text this session (after
normalization):** the sentence "Business domain contributes zero
decision-table keys, zero schema fields, zero free text to any
generated artifact, and zero enforced state." appears in #148's
Decision 1, wrapped across three source lines as noted above. #151's
Decision 3 rests on it. A registry entry records the sentence (stored as
one logical string, regardless of how the source wraps it) against
#148's path; the gate normalizes both sides and fails loudly, naming the
missing sentence and the consumer doc that depends on it, if it's gone
after normalization -- not if it merely got re-wrapped.

A rewrite of the SAME guarantee in different words (not just a
character-level edit) would legitimately break this check even though a
human might judge the meaning unchanged -- an accepted false positive,
not a flaw to fix here: CLAUDE.md section 4's fail-loud preference over
a silent pass applies, and a doc author who intentionally rewrites a
cited guarantee is expected to update the registry's quoted string in
the same change, exactly as #127's own decision-table changes are
expected to ship with their own drift-gate update.

## Decision 4: registry format

**Decision: a standalone, git-tracked JSON registry --
`docs/superpowers/specs/.spec-dependencies.json` -- modeled on
`.gitapex/ssot.json`'s already-decided `policy_sources[]` shape
(#123: "references and routing only, never policy values") without
assuming that file exists yet (it doesn't -- #123 is itself still
design-only). One entry per cross-doc dependency:**

```jsonc
[
  {
    "id": "tier-enum-147-to-151",
    "kind": "closed-enum",
    "source": { "path": "docs/superpowers/specs/2026-07-18-init-capability-tiers-design.md" },
    "consumer": { "path": "docs/superpowers/specs/2026-07-18-devcontainer-generation-phase-design.md",
                   "anchor": "Devcontainer content by tier" },
    "field": "security-tier",
    "tracking_issue": 152
  },
  {
    "id": "zero-schema-fields-148-to-151",
    "kind": "quoted-guarantee",
    "source": { "path": "docs/superpowers/specs/2026-07-18-init-hearing-fable-design.md" },
    "consumer": { "path": "docs/superpowers/specs/2026-07-18-devcontainer-generation-phase-design.md",
                   "anchor": "Decision 3" },
    "quote": "Business domain contributes zero decision-table keys, zero schema fields, zero free text to any generated artifact, and zero enforced state.",
    "tracking_issue": 152
  }
]
```

`kind` is a closed enum itself (`closed-enum | quoted-guarantee`),
matching #123's own anti-enum-creep discipline: a new kind is added only
when a concrete dependency needs it, not speculatively. `tracking_issue`
follows #123's schema precedent (nullable, records the originating
issue). This file is a natural future migration candidate into
`.gitapex/ssot.json`'s `policy_sources[]` once #123 ships real code and
gitapex's own repo starts consuming its own registry -- stated as a
migration path, not built now, since building it early would couple
this design to #123's still-unresolved schema timeline for no present
benefit.

## Decision 5: backfilling the existing chain

**Decision: shipping the gate without also registering the dependencies
that already exist (#147<->#151, #148<->#151) would recreate exactly the
gap this issue exists to close -- a drift gate with nothing registered
protects nothing. The implementation issue must seed
`.spec-dependencies.json` with (at minimum) the two worked-example
entries above in the SAME change that adds the gate script, not as a
follow-up.** This mirrors #144's own precedent: the inventory doc and
its gate shipped together, not doc-then-gate-later.

Two further dependencies exist in the chain and are named here for the
implementation issue to seed, not resolved by this design doc itself
(consistent with Non-goals -- this doc designs the mechanism, it does
not audit the full chain for every dependency):

- #148's advisory-only decision itself depends on #127's specific
  reasoning for dropping `business-domain` as a gating key -- a
  `quoted-guarantee`-shaped dependency on #127's text, symmetric with
  the #148<->#151 example above.
- #151's Decision 4 (regeneration monotonicity) depends on #127's F4
  rule text ("live PLATFORM state, never a local copy") -- another
  `quoted-guarantee` candidate.

## What this does not attempt

- **Auto-discovery of cross-references via prose parsing or NLP.**
  Dependencies must be explicitly registered by whoever writes the
  citing doc, not inferred. This is a deliberate scope limit, not an
  oversight: inferring "doc B depends on doc A" from free text is
  exactly the kind of speculative-complexity CLAUDE.md section 4 warns
  against, and a missed auto-detection would be a worse failure mode
  (silent gap) than a missed manual registration (at least visible in
  review as an omitted registry entry).
- **Verifying that a downstream argument remains sound** once an
  upstream fact changes -- Decision 1's boundary. The gate flags "go
  look"; it never renders a verdict on what it finds.
- **A general citation-integrity checker for issue numbers** (verifying
  every `#NNN` in a spec doc resolves to a real GitHub issue). A real,
  useful, but separate concern -- different data source (GitHub API vs.
  local files), different failure mode (network-dependent), and no
  existing worked example forcing its shape yet. Named as a candidate
  for a future, separate issue, not designed here.

## Facts vs. speculation

Facts: #144/#145's actual gate shape and its `_ROW_RE`-style table
parsing (`gate_owasp_asi_mapping.py`, `gate_owasp_llm_mapping.py`, read
this session); #123's `policy_sources[]` shape and its "references and
routing only, never policy values" stated design constraint; CLAUDE.md
section 3's explicit "ship the drift gate in the same change" rule; the
two worked-example strings (`` `security-tier`: `foundation |
enterprise | advanced` `` in #147; the exact Decision-1 sentence in
#148) as they currently and verifiably appear in those docs' text, read
this session, not paraphrased.

Speculation, named as such: the exact regex/extraction implementation
for Decision 2's enum pattern (an implementation-issue detail, not fixed
here beyond "same style as #144/#145's row parser"); whether `.spec-
dependencies.json` should eventually cover docs outside
`docs/superpowers/specs/` (e.g. `docs/security-control-inventory.md`
itself) -- no argued need found this session, not extended
speculatively; the eventual migration into `.gitapex/ssot.json`'s
`policy_sources[]` depends on #123's still-undecided implementation
timeline.

## Non-goals

- No `.github/scripts/gate_*.py` file, no `.spec-dependencies.json` file,
  no CI wiring -- design only. A later session may implement this,
  matching #144's design-to-code precedent, but that is a separate step.
- Not a general-purpose prose/semantic consistency checker -- Decision 1
  states this boundary explicitly; that class of drift is named and
  routed to review, not faked as deterministic.
- Not reopening #127/#147/#148/#151's actual content -- this issue
  designs the mechanism that would catch future drift in them; it
  audits their citation STRUCTURE (Decision 5's named dependencies) but
  does not correct or re-litigate their decisions.
- Not migrating into `.gitapex/ssot.json` now -- that file doesn't exist
  yet; the standalone registry is this design's actual proposal, the
  migration is a stated future path only.
- Not a citation-integrity checker for issue numbers -- named as a
  separate future candidate, not designed here.

## Acceptance criteria

- [ ] The deterministic-vs-review split is stated with a concrete named
      example of what stays out of scope (an argument's continued
      soundness, not just "semantic stuff in general").
- [ ] Closed-enum consistency (Decision 2) is specified concretely
      enough to implement directly against the real #147/#151
      `security-tier` text, with the exact declaration pattern stated.
- [ ] Quoted-guarantee consistency (Decision 3) is specified with its
      accepted-false-positive tradeoff (a meaning-preserving rewrite
      still fails the check) stated as a deliberate choice, not an
      oversight.
- [ ] The registry format (Decision 4) is modeled explicitly on
      `.gitapex/ssot.json`'s `policy_sources[]` shape without assuming
      that file exists, and states the future-migration relationship.
- [ ] Backfill for the existing #127/#147/#148/#151 chain is specified
      as shipping in the SAME change as the gate (Decision 5), with the
      two worked-example entries given concretely and two further named
      dependencies flagged for the implementation issue to seed.
- [ ] Non-goals name what is explicitly not attempted (auto-discovery,
      argument-soundness verification, issue-citation integrity) so the
      design doesn't overreach into intractable or premature territory.

## Related Issue

Child of #82. Extends #144/#145 (distinct gate shape, same
ship-with-the-invariant discipline). Covers #127/#147/#148/#151 as its
worked example and backfill target. Refs #152.

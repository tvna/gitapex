# A cross-document drift gate for the docs/superpowers/specs/ chain

Date: 2026-07-18 (rewritten same-day after reading the real upstream
source this design was meant to port from)

Refs #152 (child of #82). Extends #144/#145 (a distinct gate shape --
see Decision 0) and covers the existing #127/#147/#148/#151 chain as its
worked example and backfill target. Design-only; does not reopen any of
those four docs' content or decisions.

## Correction note (read first)

This design's first draft proposed a bespoke JSON registry
(`.spec-dependencies.json`) checking `closed-enum` and `quoted-guarantee`
content equality between docs -- built without ever reading
`tvna/claude-md`, the repository this whole design chain has cited
throughout as prior art. That was a mistake, flagged by the operator:
"if we're designing without reading the upstream codebase, direction
drift is a real risk." It was. `tvna/claude-md` was added to this
session and its real files read for the first time this pass:
`.gitapex/doc-dependencies.{toml,schema.json}`, `scripts/doc_graph.py`,
`scripts/gate_doc_graph_pr.py`. **Claude-md already has exactly this
mechanism, built, tested, and running -- and it works nothing like the
first draft.** It doesn't verify document CONTENT at all; it enforces
that a changed document's declared dependents are also touched in the
same PR (or explicitly waived). This revision replaces the first
draft's mechanism wholesale with a port of the real one, rather than
patching the wrong design. Everything below is grounded in the actual
files read this session, cited by path, not paraphrased from an issue
body -- the same discipline this correction exists to restore.

## Design-only scope

Per this repository's discipline (matching #57/#123/#125/#126/#127/#130/
#131/#144/#145/#147/#148/#151 precedent): this doc records a design
only. No `.gitapex/doc-dependencies.toml`, no `scripts/doc_graph.py` or
`gate_doc_graph_pr.py` port, no CI wiring is created by this pass.
Implementing it as real code is a later, separate step.

## Why this doc exists

Four docs form a real dependency chain, not just a citation list:
#151's devcontainer tier-content table depends on #147's `security-tier`
closed enum; #151's Decision 3 depends on #148's Decision 1 guarantee;
#148 itself depends on #127's specific reasoning. None of these are
mechanically checked -- if any upstream doc is edited later, every
downstream doc that cited the old content goes silently stale. CLAUDE.md
section 3 names this class of gap directly: "ship its drift gate in the
same change, not a follow-up." That obligation was missed starting at
#147, the first doc in this chain another doc came to depend on.

## Decision 0: distinct from #144/#145's existing gates

#144/#145's `gate_owasp_asi_mapping.py`/`gate_owasp_llm_mapping.py`
(confirmed this session to closely mirror the real
`tvna/claude-md/scripts/owasp_asi_mapping.py`, including an
EXACT match on `VALID_STATUSES` -- that part of the citation chain held
up) check ONE document's table completeness against a closed EXTERNAL
list. This design is about INTERNAL cross-document consistency between
gitapex-authored docs. Kept as a sibling mechanism, not folded into
either existing gate, for the same independent-versioning reason #145
gave for keeping its own gate separate from #144's -- and, as it turns
out, because the real upstream mechanism this design ports is itself a
DIFFERENT tool from `owasp_asi_mapping.py` in claude-md too: the two
coexist there as genuinely separate scripts covering separate
enforcement shapes.

## Decision 1: port the real mechanism -- a co-change graph, not a content checker

**Decision: adopt claude-md's actual design, ported (not reinvented):
a typed, directed dependency GRAPH (`.gitapex/doc-dependencies.toml`)
of document/script/workflow nodes, with typed edges recording "when
FROM changes, TO should be reviewed." A CI gate
(`gate_doc_graph_pr.py`-equivalent) reads the PR's changed-file list; for
every changed file that is a graph node, it requires every
`blocking`-severity dependent to also appear in the diff -- or to be
explicitly waived with a `doc-graph-waiver: NODE_ID; reason` line in the
PR body. `advisory`-severity dependents produce an informational note,
never a failure.**

This is a categorically different strategy from the first draft, and
better-suited to the actual problem, for a reason worth stating
plainly: **the gate never tries to verify that document content is
still consistent.** It only verifies that a human touched (or
explicitly declined to touch) the dependent document in the same
change. Whether what they wrote there is still correct is left to
review -- the same deterministic-vs-judgment split CLAUDE.md section 3
already prescribes, but reached by NOT attempting content verification
at all, rather than by building two content-checking mechanisms
(closed-enum, quoted-guarantee) and then drawing a boundary around what
they can't reach, as the first draft did. The simpler mechanism
subsumes the boundary the more complex one needed to state explicitly.

Ported wholesale, cited by real file read this session:

- **Node/edge model** (`scripts/doc_graph.py`, `tvna/claude-md`): a
  `DocNode` (`id`, `path`, `type`, `description`) and a `DocEdge`
  (`from_id`, `to_id`, `type`, `severity`, `note`). `impact_report`
  checks only DIRECT (one-hop) blocking edges from each changed
  node -- no transitive closure, deliberately: a two-hop drift is caught
  when the intermediate node's own edge fires on its own later change,
  not by chasing chains eagerly.
- **The waiver mechanism** (`scripts/gate_doc_graph_pr.py`): plain-text,
  MCP-safe (no HTML comments, which GitHub MCP write tools strip) --
  `doc-graph-waiver: NODE_ID; reason`, one per line, parsed by regex from
  the PR body. A waived node is reported, not silently dropped.
- **Fail policy** (`gate_doc_graph_pr.py`, read verbatim): fails LOUD
  (exit 1) when a required co-change is missing or unwaived, matching
  CLAUDE.md section 4; fails OPEN (exit 0, with a warning) when the git
  diff itself is unavailable, so the gate degrades to a skip rather than
  blocking a PR on infrastructure trouble -- a fail-open carve-out
  claude-md itself scopes narrowly (unavailable diff only, never an
  unavailable graph file or a validation error, both of which stay
  fail-closed).

## Decision 2: node/edge type vocabulary, ported and trimmed

Real `VALID_NODE_TYPES` (`doc_graph.py`): `{"universal_text",
"compiled_artifact", "prd", "standard", "runbook", "harness_script",
"harness_workflow", "archive"}`. gitapex has no APM-compiled
universal-text pipeline (`universal_text`/`compiled_artifact` describe
claude-md's own `master.instructions.md` -> `CLAUDE.md`/`AGENTS.md`
compilation, which gitapex's repo doesn't have) and no archived docs yet
(`archive`). Adopt the subset gitapex's own chain actually needs today
-- `prd` (design specs under `docs/superpowers/specs/`), `harness_script`
(`.github/scripts/gate_*.py`) -- and add `standard`/`runbook`/
`harness_workflow`/others only when a concrete gitapex doc needs one,
per this repo's own anti-enum-creep discipline (#125's rule, applied
here to node types instead of gate kinds).

Edge types and their DEFAULT severity class, ported unchanged (the
vocabulary itself is generic, not claude-md-specific, so porting it
verbatim -- not gitapex-specific renaming -- is the right call):

| Edge type | Reads as | Default severity |
|---|---|---|
| `governs` | upstream principles define/constrain downstream | blocking |
| `compiled_to` | upstream compiles deterministically into downstream | blocking |
| `derives_from` | downstream design was derived from upstream | blocking |
| `enforced_by` | downstream script enforces upstream rule | advisory |
| `implements` | downstream is the concrete implementation of upstream | advisory |
| `references` | upstream cites downstream | advisory |

**Directional convention, stated explicitly because it is easy to get
backwards:** `from -> to` always reads as "if FROM changes, review TO,"
but which side is upstream/authoritative depends on the edge type's own
verb. For `governs`/`compiled_to`, `from` is the upstream authority. For
`derives_from`, `from` is the DOWNSTREAM/derived doc and `to` is the
upstream authority it derives from -- verified against the real TOML's
own `design_philosophy_prd -> ubiquitous_language, type=derives_from`
edge, where `ubiquitous_language` is the authority. gitapex's own edges
below use `derives_from` for exactly this reason: the derived doc names
itself as `from`.

## Decision 3: the concrete graph for gitapex's real chain

Worked, not abstract -- these are the actual current dependencies,
usable as the implementation issue's seed data.

```toml
[[nodes]]
id = "init_capability_tiers_prd"
path = "docs/superpowers/specs/2026-07-18-init-capability-tiers-design.md"
type = "prd"
description = "Foundation/Enterprise/Advanced security-tier framework for gitapex init (#147)."

[[nodes]]
id = "init_hearing_fable_prd"
path = "docs/superpowers/specs/2026-07-18-init-hearing-fable-design.md"
type = "prd"
description = "Business-domain hearing design for gitapex init, Fable method (#148)."

[[nodes]]
id = "devcontainer_generation_prd"
path = "docs/superpowers/specs/2026-07-18-devcontainer-generation-phase-design.md"
type = "prd"
description = "Explicit post-init devcontainer generation phase (#151)."

[[nodes]]
id = "spec_doc_drift_gate_prd"
path = "docs/superpowers/specs/2026-07-18-spec-doc-drift-gate-design.md"
type = "prd"
description = "This document -- the drift-gate design itself (#152)."

[[edges]]
from = "devcontainer_generation_prd"
to = "init_capability_tiers_prd"
type = "derives_from"
severity = "blocking"
note = "Devcontainer content-by-tier table hardcodes the security-tier enum; co-change on tier vocabulary changes."

[[edges]]
from = "devcontainer_generation_prd"
to = "init_hearing_fable_prd"
type = "derives_from"
severity = "blocking"
note = "Decision 3's non-consumption argument rests on Decision 1's zero-schema-fields guarantee; co-change if that guarantee changes."
```

`docs/security-control-inventory.md` and `.github/scripts/
gate_owasp_asi_mapping.py`/`gate_owasp_llm_mapping.py` (#144/#145) are
deliberately NOT added as graph nodes: they already carry their own,
stronger, content-verifying gates (Decision 0). Adding graph edges for
them would duplicate enforcement the real
`tvna/claude-md/.gitapex/doc-dependencies.toml` itself avoids -- its own
`owasp_asi_mapping.py` and `security_control_inventory.md` are likewise
absent from its graph, confirmed by reading the actual node list this
session, not assumed. The graph is for dependencies that have no
dedicated gate of their own -- exactly #152's original problem.

## Decision 4: a real limitation this design does not paper over

**#127 has no `docs/superpowers/specs/` file.** Its entire design lives
in the GitHub issue body. The node model requires a `path` to a tracked
file (`node_for_path` matches against `git diff --name-only` output,
which only sees files); a GitHub issue body has no such path and cannot
"co-change" in a diff the gate can observe. Two real dependencies named
in this doc's first draft -- #148's advisory-only decision depending on
#127's reasoning for dropping `business-domain`, and #151's Decision 4
depending on #127's F4 rule text -- are therefore **not representable
in this mechanism as it stands.**

This is stated as a limitation, not solved here: the honest fix is for
#127 to gain its own `docs/superpowers/specs/*.md` file (a natural,
separately-scoped follow-up recommendation, not a change this design
makes), after which the two dependencies above become ordinary
`derives_from` edges like the ones in Decision 3. Recommending that is
this doc's full scope on the point; it does not retrofit #127 itself.

## Decision 5: implementation-issue backfill and the bonus visualization

Per CLAUDE.md section 3's rule and #144's own precedent (the inventory
and its gate shipped together), the implementation issue must seed
`.gitapex/doc-dependencies.toml` with Decision 3's nodes/edges in the
SAME change that adds the gate script -- a drift gate with nothing
registered protects nothing.

Worth porting alongside the gate, not required for the gate to function:
`doc_graph.py`'s `render_mermaid` function, which turns the graph into a
Mermaid `flowchart LR` diagram. This is a direct, low-cost instance of
CLAUDE.md section 6's "produce a workflow artifact that makes state
visible by inspection" rule -- the dependency chain becomes a diagram a
human can scan instead of prose they must reconstruct. Named as a
should-port, not a hard requirement of Decision 1's core mechanism.

## What this does not attempt

- **Verifying document content is still correct.** Restated as the
  central, deliberate trade-off (Decision 1): the gate enforces
  co-change, not consistency. A PR that touches both #147 and #151 but
  updates #151 wrong still passes the gate -- that gap is real, accepted,
  and routed to review, exactly where CLAUDE.md section 3 already says
  semantic judgment belongs. The first draft's attempt to also catch
  THAT case (via literal-content regex matching) is not carried forward;
  it added real complexity (the whitespace-normalization fix the first
  draft needed) for a guarantee the real upstream mechanism doesn't
  attempt either.
- **Transitive/multi-hop drift detection.** `impact_report` checks only
  direct edges, matching the real `doc_graph.py` exactly -- not a
  simplification introduced here.
- **Graphing #127** until it has a file (Decision 4).
- **A general citation-integrity checker for issue numbers.** Unchanged
  from the first draft: a real, separate, future candidate, not designed
  here.

## Facts vs. speculation

Facts, verified by reading the actual files this session (not from
memory, not from issue-body paraphrase): `tvna/claude-md`'s
`.gitapex/doc-dependencies.toml` (node/edge inventory, including the
confirmed absence of `owasp_asi_mapping.py`/`security_control_inventory.md`
as graph nodes), `.gitapex/doc-dependencies.schema.json` (shape-only,
validated by `scripts/doc_graph.py` for enum/referential-integrity per
its own description), `scripts/doc_graph.py` (`VALID_NODE_TYPES`,
`BLOCKING_EDGE_TYPES`/`ADVISORY_EDGE_TYPES`, `impact_report`'s one-hop-only
behavior, `render_mermaid`), `scripts/gate_doc_graph_pr.py` (waiver
regex and format, fail-loud/fail-open split), `.gitapex/ssot.schema.json`
(`policy_sources[].format` enum -- the error this session's #144 fix
corrected), and `scripts/owasp_asi_mapping.py` (confirmed near-exact
match to gitapex's own `gate_owasp_asi_mapping.py`, including identical
`VALID_STATUSES`).

Speculation, named as such: the exact port's file paths in gitapex
(`.gitapex/doc-dependencies.toml` mirrors claude-md's own path, a
reasonable default but an implementation-issue decision); whether
gitapex ports `doc_graph_viz`-equivalent tooling beyond the
`render_mermaid` function itself; whether `.github/workflows/`
gains a dedicated `validate-doc-graph.yml`-equivalent workflow or the
gate rides an existing one -- an implementation-issue choice, not
resolved here.

## Non-goals

- No `.gitapex/doc-dependencies.toml`, no `scripts/doc_graph.py` or
  gate port, no CI wiring, no `render_mermaid` port -- design only. A
  later session may implement this, matching #144's design-to-code
  precedent.
- Not a content/semantic consistency checker of any kind -- Decision 1
  states this trade-off explicitly as the point of the design, not an
  oversight.
- Not reopening #127/#147/#148/#151's actual content -- this issue
  designs the mechanism that would catch future drift in them.
- Not retrofitting #127 with a spec-doc file -- recommended (Decision 4),
  not performed here.
- Not a citation-integrity checker for issue numbers -- separate future
  candidate, unchanged from the first draft.

## Acceptance criteria

- [ ] The mechanism is a ported co-change graph (nodes/edges/severity,
      PR-diff-based enforcement, plain-text waiver), not a
      content-equality checker -- Decision 1 states this as a deliberate
      replacement of the first draft's approach, with the real upstream
      files cited by path.
- [ ] Node/edge vocabulary is ported from the real `doc_graph.py`
      constants, trimmed to gitapex's actual current needs (Decision 2),
      with the `derives_from` directional convention stated explicitly
      and verified against a real example edge.
- [ ] Decision 3's graph is concrete and seedable directly from this
      doc (real node paths, real edges, real notes) -- not left
      abstract.
- [ ] The #127-has-no-file limitation (Decision 4) is stated plainly as
      an unrepresentable gap, with a recommendation (not a fix) for
      closing it.
- [ ] #144/#145's files are explicitly excluded from the graph with the
      reason stated (already have stronger, dedicated content gates;
      confirmed the real claude-md graph excludes its own equivalent
      files too).
- [ ] What the mechanism does NOT verify (content correctness) is stated
      as the design's deliberate trade-off, not discovered as a gap
      after the fact.
- [ ] Facts vs. speculation cites real files read this session by path,
      not paraphrased issue-body descriptions -- the discipline this
      whole revision exists to restore.

## Related Issue

Child of #82. Extends #144/#145 (distinct gate shape, confirmed via the
real upstream graph's own exclusion of equivalent files). Covers
#127/#147/#148/#151 as worked example, backfill target, and (for #127)
a named, unresolved limitation. Refs #152.

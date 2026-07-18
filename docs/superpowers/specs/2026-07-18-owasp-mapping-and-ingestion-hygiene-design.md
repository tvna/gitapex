# OWASP Agentic Top 10 mapping gate + content-ingestion hygiene gate

Design-only companion doc for a new tracking issue, child of #82,
expanding #123's seed-gate scope. Answers a user question on CLAUDE.md
section 2: what controls exist for access to unsafe/untrusted
information, grounded in OWASP's real Agentic AI threat taxonomy, and a
separate but related concern -- token waste from raw log/HTML ingestion.

## Origin

User question (2026-07-18, translated): what controls does section 2's
untrusted-information discipline actually have? Security concerns like
the OWASP Agentic Top 10 matter, but so does token waste from putting
raw logs or raw HTML directly into context.

**Primary sources fetched and read this session (not from memory):**

- OWASP "Agentic AI -- Threats and Mitigations v1.0"
  (`genai.owasp.org`), a detailed T1-T17 threat model. Relevant items:
  T1 Memory Poisoning, T2 Tool Misuse (includes Agent Hijacking --
  ingesting adversarial manipulated data), T4 Resource Overload, T5
  Cascading Hallucination Attacks, T15 Human Manipulation, T16 Insecure
  Inter-Agent Protocol Abuse.
- `tvna/claude-md`'s own live mapping onto "OWASP Top 10 for Agentic
  Applications 2026" (ASI01-ASI10, OWASP GenAI Security Project):
  `docs/prd/security-control-inventory.md` (the status table) and
  `scripts/owasp_asi_mapping.py` (a deterministic CI gate verifying the
  mapping never silently drifts -- completeness only, never correctness).

**Confirmed gaps in gitapex's own design, verified by search, not
assumed:** no file matching `owasp`/`asi0` exists anywhere under
`/home/user/gitapex` -- gitapex has never had an explicit OWASP Agentic
Top 10 mapping artifact. Separately, #138's Gate 6
(`gate-untrusted-text-advisory`) classifies text already present in an
agent's context, but nothing controls the read path itself -- whether
raw external content reaches context unbounded, or passes through
structured extraction / size-capping first.

Two structurally separate deliverables follow.

## Deliverable 1: `gitapex-owasp-asi-mapping`

**Document location.** `docs/security-control-inventory.md`. gitapex's
`docs/` is flat (glossary, motivation, repository-layout, versioning); a
control inventory is a living operational document, not a dated spec, so
it belongs at the flat top level rather than under
`docs/superpowers/specs/`.

**Ported discipline, not ported answers.** claude-md's gate verifies
exactly one row per ASI01..ASI10, status drawn from a closed vocabulary,
with a non-empty rationale -- completeness, never correctness. gitapex
ports that contract unchanged (same section-anchor + table-row parse,
statuses `covered`/`partially covered`/`not covered`/`not applicable`).
Per CLAUDE.md section 3, the inventory and its drift gate ship in the
same change. Fail-closed: it's a CI gate (#131 principle 6); a missing
section is a structural error, not a skip.

**First-pass mapping for gitapex** (own architecture, not claude-md's
answers copied verbatim -- gitapex is a redistributed single-binary CLI
with an embedded Rego engine and an MCP server mode, so two of
claude-md's `not applicable` verdicts flip here):

| ASI | Status | Rationale |
|---|---|---|
| ASI01 Agent Goal Hijack | partially covered | #138 Gate 6 classifies instruction-shaped external text on both planes; the read path itself is uncontrolled until Deliverable 2 lands. |
| ASI02 Tool Misuse | partially covered | #138 Gate 5 (irreversible-op guards), #139 gh-cli routing deny + wrapper, #126's caller-independent MCP abuse resistance; raw-ingestion hijack surface (T2 Agent Hijacking) open until Deliverable 2. |
| ASI03 Identity/Privilege Abuse | partially covered | #130's verified/asserted actor-provenance split, #127's fine-grained credential bound privilege; no short-lived/OIDC identity, #126's MCP mode still inherits full ambient CLI privileges (open finding). |
| ASI04 Supply Chain | partially covered | Nix Class B SHA-pinned distribution (#125), `toolchain.lock.json` under `policy_sources[]` (#131), #140 `workflow-action-pins`, #126 tool-poisoning scan; TOFU bootstrapping gap keeps this short of covered. |
| ASI05 Unexpected Code Execution | partially covered | Policy is data-not-code by construction (embedded Rego, #125), but #125's addendum leaves `kind:"script"` gates unsandboxed and the regorus builtin allowlist unasserted. |
| ASI06 Memory/Context Poisoning | partially covered | Not N/A as in claude-md: `.gitapex/ssot.json`, `policy_sources[]`, and #130's audit trail are persistent agent-consumed state. Write path covered by merge-gated registry + #140 `registry-self-validation` + #127's monotonicity check; context-ingestion path is Deliverable 2's gap. |
| ASI07 Inter-Agent Communication | partially covered | Not N/A: MCP server mode (#126) is an agent-protocol surface (stdio-only, size caps, minimal `explain_denial` disclosure, poisoning scan); TOFU baseline gap remains. |
| ASI08 Cascading Failures | partially covered | Fail-closed-including-INDETERMINATE (#131 P6) retrofitted onto #125's hygiene check and #130's audit write; no blast-radius cap per invocation context. |
| ASI09 Human-Agent Trust Exploitation | covered | #138 Gate 5's TTL-bounded acks keep confirmation with the human; Gate 1 blocks self-excusing PR language; #126 splits denial detail away from the untrusted MCP surface. |
| ASI10 Rogue Agents | not covered | No runtime behavioral-anomaly detection or per-session containment exists anywhere in #125-#143; containment is only the platform merge boundary #127 scaffolds. Honest gap, not inflated. |

**Registry JSON, corrected 2026-07-18 against the real upstream schema
(issue #152's finding: this session had not read `tvna/claude-md`'s
actual `.gitapex/ssot.schema.json` when this snippet was first written;
it has now been read, and this snippet is corrected accordingly rather
than left wrong for a future session to trip over).** Two errors are
fixed. First, `policy_sources[].format` is a closed enum in the real
schema -- `["toml", "json", "yaml"]` -- and does not include
`"markdown"`; `docs/security-control-inventory.md` cannot legally be a
`policy_sources[]` entry as originally drafted. Second, and more
fundamentally, the real upstream repo does not register its own
markdown PRD documents (like its own `docs/prd/security-control-
inventory.md`) as `policy_sources[]` entries at all -- `policy_sources[]`
is for machine-readable data files gates actually PARSE
(toml/json/yaml); a narrative markdown doc a gate reads and verifies
directly (as `gate_owasp_asi_mapping.py` does, taking the doc path as a
plain argument, no indirection) is instead a NODE in the separate
`.gitapex/doc-dependencies.toml` graph (see #152's design). Corrected:

```jsonc
// doc-dependencies.toml nodes[] (not policy_sources[] -- see correction note above)
{ "id": "owasp_asi_inventory", "path": "docs/security-control-inventory.md", "type": "prd",
  "description": "Single SoT mapping gitapex controls onto OWASP Agentic Top 10 ASI01..ASI10; peer axis to the zero-trust model in #131" }

// gates[]
{ "id": "gate-owasp-asi-mapping", "kind": "script", "script": ".github/scripts/gate_owasp_asi_mapping.py",
  "rule": "ASI01..ASI10 each appear exactly once with a valid status and non-empty rationale; completeness only, correctness stays with review",
  "planes": ["ci"], "trigger": "pull_request touching docs/ or .gitapex/",
  "policy_refs": [], "cluster": "security-inventory", "tracking_issue": null }
```

(`policy_refs` is empty: the gate reads
`docs/security-control-inventory.md` directly by path, not through a
registered policy-file indirection -- matching the real upstream
`owasp_asi_mapping.py`'s actual `--inventory` argument contract, read
this session.)

## Deliverable 2: `content-ingestion-hygiene`

**What it controls.** Not what external text *says* (Gate 6's job) but
how much of it, in what shape, reaches context at all. Layering is
explicit two-stage defense-in-depth (CLAUDE.md section 4): hygiene first
-- bound and structure the payload at the read boundary; classification
second -- Gate 6's agent-plane classifier wraps instruction-shaped
content in what survives. Hygiene shrinks the haystack Gate 6 must scan;
it never replaces the scan. Both gates share the `untrusted-text`
cluster to make the pairing registry-visible.

**Security framing, fact-grounded.** OWASP T2 names "Agent Hijacking:
ingesting adversarial manipulated data, executing unintended actions" --
the read path is the ingestion step itself. A large raw HTML dump or CI
log tail is where injected directives hide best (ASI01 goal hijack) and
where a manipulated payload steers tool use (ASI02); structured
extraction and hard size caps shrink that surface. This does not detect
anything -- detection stays with Gate 6.

**Cost framing, honestly scoped.** T4 Resource Overload (quotas,
rate-limiting, resource management) is the closest security framing for
unbounded ingestion -- but the ASI01-ASI10 Top 10 has **no** dedicated
unbounded-consumption category the way the older OWASP LLM Top 10 did
(LLM10:2025 Unbounded Consumption). That is an honest observation about
the taxonomy's current shape, not a gap gitapex must invent an ASI row
to fill. Token waste is a sufficient engineering rationale on its own;
T4 is cited as adjacent support, not as its authority.

**Mechanism.** A PostToolUse hook -- the payload exists only after the
tool returns, so PreToolUse cannot see it. Matchers: `WebFetch`/
`WebSearch`; `Bash` whose command matches fetch/dump patterns (`curl`,
`wget`, `cat`, `tail`, `head -c`, `journalctl`, `docker logs`); MCP reads
returning bodies/logs (e.g. `mcp__github__get_job_logs`, issue/PR
bodies). Two tiers, configured in `.gitapex/policies/ingestion-budgets.toml`:

- **Soft cap** (default 16KB / ~4k estimated tokens): payload passes
  through, annotated: *"exceeds ingestion budget: extract the facts you
  need, summarize before further use, do not re-quote raw content."*
  Advisory, matching Gate 6's posture -- a bug report legitimately
  containing a large log must not be blocked.
- **Hard cap** (default 256KB): deterministic truncation with an
  explicit marker -- `[gitapex: truncated, kept first N of M bytes;
  re-read narrower (grep/offset) for the rest]` -- degrade visibly,
  never silent drop. Truncation keeps head-of-payload plus the marker so
  the agent knows to narrow, not guess.

**Own-repo vs. adopter.** Same defaults; adopters tune budgets in the
policy source but the hard-cap tier cannot be removed, only resized --
mirroring #127's narrowest-viable-default finding (no permissive
"don't annoy adopters" default). gitapex's own repo work keeps the
soft-cap advisory because Gate 6 sits behind it.

**Fail policy, split by function per #131 -- not default-copied.** The
annotation half fails open (Gate 6's agent-plane precedent: a wedged
reminder must never block a read; the second layer still stands, so one
advisory layer failing open does not collapse defense-in-depth). The
hard-cap half fails **closed** (principle 6: inability to measure a
payload is a deny, not assume-small -- an unmeasurable payload is
truncated at the cap, with the failure surfaced loudly per CLAUDE.md
section 4, never silently passed unbounded). Blanket fail-open would
recreate exactly the unbounded-ingestion risk the gate exists to close.

**Registry JSON:**

```jsonc
// policy_sources[]
{ "id": "ingestion-budgets", "path": ".gitapex/policies/ingestion-budgets.toml", "format": "toml",
  "authority": "per-tool-class soft/hard size and token budgets plus degrade actions for external content entering agent context; hard-cap tier resizable, not removable" }

// gates[]
{ "id": "gate-ingestion-hygiene", "kind": "script", "script": "scripts/gate_ingestion_hygiene.py",
  "rule": "read-tool payloads are measured post-return; soft-cap breach appends a summarize-before-use annotation (fails open), hard-cap breach truncates with an explicit marker (fails closed on unmeasurable); runs upstream of gate-untrusted-text-advisory-agent",
  "planes": ["posttooluse"], "trigger": "WebFetch/WebSearch, Bash fetch/dump commands, MCP reads returning external bodies or logs",
  "policy_refs": ["ingestion-budgets"], "cluster": "untrusted-text", "tracking_issue": null }
```

Relationship restated once: `gate-ingestion-hygiene` controls what
reaches context; `gate-untrusted-text-advisory-agent` (#138 Gate 6)
classifies what is already there. Upstream/downstream, same cluster,
neither subsumes the other.

## Non-goals

- No code, no `.gitapex/` files, no `scripts/` edits -- design only.
- Not re-litigating #138 Gate 6 -- extended (paired upstream), not
  replaced.
- Not inventing an ASI category for token waste where OWASP's own Top 10
  doesn't have one -- the cost framing stands on its own engineering
  merit, T4 is cited as adjacent support only.
- Not claiming full ASI01-10 coverage -- ASI10 is stated `not covered`
  honestly; several others are `partially covered` with explicit,
  unresolved gaps named, not inflated.

## Acceptance criteria

- [ ] Deliverable 1's first-pass mapping is grounded in gitapex's own
      already-designed gates (#125-#143), not copied from claude-md's
      answers.
- [ ] Every `not covered`/`partially covered` verdict names its specific
      open gap, not just "todo."
- [ ] Deliverable 2's security framing cites OWASP T2/ASI01/ASI02
      specifically, not a generic "prompt injection is bad" claim.
- [ ] Deliverable 2's cost framing is honest about the ASI01-10 taxonomy
      not having a dedicated unbounded-consumption category.
- [ ] Fail policy for Deliverable 2 is split and argued per function
      (annotation vs. hard cap), not blanket-copied from a prior design.
- [ ] Relationship between Deliverable 2 and #138 Gate 6 stated
      explicitly, with no unstated overlap.

## Related Issue

Child of #82. Expands #123's seed-gate scope, same pattern as #138,
#139, #140, #141, #142, #143. Cross-references #125, #126, #127, #130,
#131 (cited throughout Deliverable 1's mapping), #138 Gate 6 (paired
with Deliverable 2).

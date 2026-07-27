# Security control inventory

Living status inventory mapping gitapex's own design (its already-scoped
gates, hooks, and CLI-governance issues) onto external OWASP taxonomies,
one section per taxonomy. Sections are cross-linked peer axes, not merged
into a single table — the same pattern `tvna/claude-md` uses for MITRE
ATT&CK and the OWASP Agentic Top 10. Each taxonomy's completeness is
enforced by its own CI gate (listed per section below); the gates check
**completeness only** (every category present exactly once, with a
status from a closed vocabulary and a non-empty rationale) — correctness
of the verdicts themselves stays with human/PR review, not the gate.

Status vocabulary (shared across all sections):

- `covered` — an existing gitapex gate/hook/design fully addresses the
  category.
- `partially covered` — some mitigation exists; a specific, named gap
  remains open.
- `not covered` — no mitigation exists yet. A valid, expected outcome for
  some categories; never inflated to `partially covered` to avoid an
  honest gap.
- `not applicable` — the category does not apply to gitapex's actual
  architecture, with the reason stated.

Enforcement classification (each row's Rationale cell is now prefixed with
one of the three tags below, borrowing the vocabulary — not the policy
engine — from `microsoft/agent-governance-toolkit`'s deny/require_approval/
allow model, per #311): the tag is inlined into the existing Rationale
cell rather than added as a fourth table column because
`gate_owasp_asi_mapping.py`/`gate_owasp_llm_mapping.py`'s own header-row
regex requires the fixed 3-column `| ID | Status | Rationale |` shape —
a new column would fail that already-passing completeness gate. Reflects
what actually, currently enforces something (verified against this
repo's real hooks/CI/toolchain, not the many still-design-only `#12x`
gitapex-CLI proposals the Rationale text also cites), never the
aspirational end-state a cited design issue argues for:

- `[deny]` — a hard, automated block exists today (e.g. a PreToolUse hook
  exit-2 deny, a required CI check that fails the build).
- `[require_approval]` — a human confirmation or review gate exists today
  (e.g. CLAUDE.md's own irreversible-op confirmation requirement, PR
  review), even where not yet backed by code.
- `[allow]` — nothing currently blocks or requires approval for this row
  (includes every `not covered`/`not applicable` row, and any row whose
  cited mitigation is still a design-only issue with no shipped gate).

## OWASP Top 10 for Agentic Applications (ASI01-10)

Source: OWASP GenAI Security Project, "OWASP Top 10 for Agentic
Applications 2026" (ASI01-ASI10). Gate:
`.github/scripts/gate_owasp_asi_mapping.py`.

First-pass mapping for gitapex's own architecture — a redistributed
single-binary CLI with an embedded Rego policy engine and an MCP server
mode (not `tvna/claude-md`'s answers copied verbatim; two of that
sibling repo's `not applicable` verdicts flip here because gitapex's
shape genuinely differs).

| ASI | Status | Rationale |
|---|---|---|
| ASI01 Agent Goal Hijack | partially covered | [allow] #138 Gate 6 classifies instruction-shaped external text on both planes; the read path itself is uncontrolled until the content-ingestion-hygiene gate (#144 Deliverable 2) lands. |
| ASI02 Tool Misuse | partially covered | [deny] #138 Gate 5 (irreversible-op guards), #139 gh-cli routing deny + wrapper, #126's caller-independent MCP abuse resistance; raw-ingestion hijack surface (OWASP Agentic AI T2 Agent Hijacking) open until #144 Deliverable 2. |
| ASI03 Identity/Privilege Abuse | partially covered | [allow] #130's verified/asserted actor-provenance split, #127's fine-grained credential-bound privilege; no short-lived/OIDC identity yet, #126's MCP mode still inherits full ambient CLI privileges (open finding). |
| ASI04 Supply Chain | partially covered | [deny] Nix Class B SHA-pinned distribution (#125) is real and CI-verified today (`flake.nix` + `scan_toolchain_pin_drift.py`'s single-source-of-truth gate); `toolchain.lock.json` under `policy_sources[]` (#131), #140 `workflow-action-pins`, #126 tool-poisoning scan remain design-only. TOFU bootstrapping gap keeps this short of `covered`. |
| ASI05 Unexpected Code Execution | partially covered | [allow] Policy is data-not-code by construction (embedded Rego, #125), but #125's addendum leaves `kind:"script"` gates unsandboxed and the regorus builtin allowlist unasserted. |
| ASI06 Memory/Context Poisoning | partially covered | [allow] Not N/A as in claude-md: `.gitapex/ssot.json`, `policy_sources[]`, and #130's audit trail are persistent agent-consumed state. Write path covered by merge-gated registry + #140 `registry-self-validation` + #127's monotonicity check; context-ingestion path is #144 Deliverable 2's gap. |
| ASI07 Inter-Agent Communication | partially covered | [allow] Not N/A: MCP server mode (#126) is an agent-protocol surface (stdio-only, size caps, minimal `explain_denial` disclosure, poisoning scan); TOFU baseline gap remains. |
| ASI08 Cascading Failures | partially covered | [allow] Fail-closed-including-INDETERMINATE (#131 principle 6) retrofitted onto #125's hygiene check and #130's audit write; no blast-radius cap per invocation context. |
| ASI09 Human-Agent Trust Exploitation | covered | [require_approval] #138 Gate 5's TTL-bounded acks keep confirmation with the human; Gate 1 blocks self-excusing PR language; #126 splits denial detail away from the untrusted MCP surface. |
| ASI10 Rogue Agents | not covered | [allow] No runtime behavioral-anomaly detection or per-session containment exists anywhere in #125-#143; containment is only the platform merge boundary #127 scaffolds. Honest gap, not inflated. |

Design record: `docs/superpowers/specs/2026-07-18-owasp-mapping-and-ingestion-hygiene-design.md`.

## OWASP Top 10 for LLM Applications and Generative AI (LLM01-10:2025)

Source: OWASP GenAI Security Project, "OWASP Top 10 for LLM Applications
and Generative AI 2025" (`genai.owasp.org/llm-top-10/`, fetched
2026-07-18 -- primary source, not from memory). Gate:
`.github/scripts/gate_owasp_llm_mapping.py`, a **sibling** gate to
`gate_owasp_asi_mapping.py` rather than an extension of it: the two
OWASP lists version independently (this list revises on its own
cadence, distinct from the Agentic Top 10's), so a version bump in one
table's contract must never force re-verification of the other's.

This list predates and underlies the Agentic Top 10 (ASI01-10) above --
its own T1-T17 "Agentic AI -- Threats and Mitigations" document cites
LLM01-10:2025 as the base layer for "general threats not specific to
agentic systems," out of its own stated scope. Several rows below
therefore name the same gitapex controls as their ASI counterpart; that
overlap is expected, not redundant -- each list is checked as its own
independent completeness contract.

| LLM | Status | Rationale |
|---|---|---|
| LLM01 Prompt Injection | partially covered | [allow] Same base-layer risk as ASI01: #138 Gate 6 classifies instruction-shaped external text already in context; the ingestion path itself (what reaches context, and how much) stays uncontrolled until #144 Deliverable 2 (content-ingestion-hygiene) ships as code -- currently design-only. |
| LLM02 Sensitive Information Disclosure | partially covered | [allow] #127's fine-grained credential-bound privilege narrows what any single scope can expose; #130's verified/asserted audit-trail split avoids conflating untrusted claims with confirmed facts in logs. No dedicated secret-redaction/scanning gate exists in gitapex's own tooling yet -- CLAUDE.md section 4's "never echo secret values, redact before logging" rule is a prose-level agent instruction today, not a deterministic gate. Honest, named gap. |
| LLM03 Supply Chain | partially covered | [deny] Same controls as ASI04: Nix Class B SHA-pinned distribution (#125) is real and CI-verified today (`flake.nix` + `scan_toolchain_pin_drift.py`'s single-source-of-truth gate); `toolchain.lock.json` under `policy_sources[]` (#131), #140 `workflow-action-pins`, #126 tool-poisoning scan remain design-only. TOFU bootstrapping gap keeps this short of `covered`. |
| LLM04 Data and Model Poisoning | not applicable | [allow] gitapex trains, fine-tunes, and embeds nothing -- it is a governance/gate layer around an agent's tool use, not model-training or embedding infrastructure. The adjacent risk of poisoning gitapex's own *persistent state* (`.gitapex/ssot.json`, `policy_sources[]`) is scoped under ASI06 above, not this LLM-specific training-data category. |
| LLM05 Improper Output Handling | partially covered | [deny] `hooks/check-bash-safety.sh`'s PreToolUse deny/warn rules, `hooks/check-template-overwrite.sh`, and `hooks/check-issue-acm-disclosure.sh` (#413) validate agent-generated output before three specific high-risk sinks (shell commands, file overwrites, GitHub issue creation) execute. Coverage is scoped to those three hook-matched tool categories; no general validation layer exists for other downstream sinks a generated output could reach. |
| LLM06 Excessive Agency | partially covered | [require_approval] Same controls as ASI02/ASI03: #138 Gate 5's TTL-bounded human acks gate irreversible operations, #127's credential-bound privilege caps the ceiling of any granted agency, #130's audit trail makes exercised agency reviewable. No per-invocation blast-radius cap and no runtime behavioral-anomaly detection constrain agency once a tool call is already authorized (same open gap as ASI08/ASI10). |
| LLM07 System Prompt Leakage | partially covered | [allow] gitapex's own governance instructions (`CLAUDE.md`/`AGENTS.md`) are committed, public text by design -- there is no hidden system prompt to leak in the classic sense. The adjacent surface is #126's MCP server mode, which intentionally caps `explain_denial` disclosure detail to avoid handing an untrusted MCP caller an oracle for reverse-engineering the live policy engine; the right granularity for that cap is not yet fully specified. |
| LLM08 Vector and Embedding Weaknesses | not applicable | [allow] gitapex has no retrieval-augmented-generation pipeline, vector store, or embedding-based retrieval anywhere in its design (#125-#144) -- verified by search across every design spec, not assumed. |
| LLM09 Misinformation | partially covered | [allow] CLAUDE.md section 2 mandates primary-source grounding and explicit fact/speculation tagging, reinforced by eval tasks (`claim-provenance`, `regulatory-version-currency`, `third-party-not-authoritative`) that probe whether an agent follows that discipline. These are agent-instruction and eval-level controls, not a deterministic CI gate -- no automated citation- or claim-verification gate blocks a PR containing an ungrounded claim. Honest gap. |
| LLM10 Unbounded Consumption | not covered | [allow] #144 Deliverable 2 (content-ingestion-hygiene: a PostToolUse soft/hard size-budget gate) is fully designed to close exactly this risk, but ships no code yet -- design-only per its own stated non-goals. LLM10:2025 is the correctly-fitting citation for that design (the ASI01-10 list has no equivalent dedicated category); until Deliverable 2 lands as a real gate, the status here is honestly `not covered`, not `partially covered` for a design that doesn't run. |

Design record: same file as the ASI section above; its Deliverable 2
"Cost framing" paragraph cites this exact LLM10:2025 category as its
primary authority (updated from an adjacent-only T4 Resource Overload
citation -- see that file's changelog note).

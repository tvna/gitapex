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
| ASI01 Agent Goal Hijack | partially covered | #138 Gate 6 classifies instruction-shaped external text on both planes; the read path itself is uncontrolled until the content-ingestion-hygiene gate (#144 Deliverable 2) lands. |
| ASI02 Tool Misuse | partially covered | #138 Gate 5 (irreversible-op guards), #139 gh-cli routing deny + wrapper, #126's caller-independent MCP abuse resistance; raw-ingestion hijack surface (OWASP Agentic AI T2 Agent Hijacking) open until #144 Deliverable 2. |
| ASI03 Identity/Privilege Abuse | partially covered | #130's verified/asserted actor-provenance split, #127's fine-grained credential-bound privilege; no short-lived/OIDC identity yet, #126's MCP mode still inherits full ambient CLI privileges (open finding). |
| ASI04 Supply Chain | partially covered | Nix Class B SHA-pinned distribution (#125), `toolchain.lock.json` under `policy_sources[]` (#131), #140 `workflow-action-pins`, #126 tool-poisoning scan; TOFU bootstrapping gap keeps this short of `covered`. |
| ASI05 Unexpected Code Execution | partially covered | Policy is data-not-code by construction (embedded Rego, #125), but #125's addendum leaves `kind:"script"` gates unsandboxed and the regorus builtin allowlist unasserted. |
| ASI06 Memory/Context Poisoning | partially covered | Not N/A as in claude-md: `.gitapex/ssot.json`, `policy_sources[]`, and #130's audit trail are persistent agent-consumed state. Write path covered by merge-gated registry + #140 `registry-self-validation` + #127's monotonicity check; context-ingestion path is #144 Deliverable 2's gap. |
| ASI07 Inter-Agent Communication | partially covered | Not N/A: MCP server mode (#126) is an agent-protocol surface (stdio-only, size caps, minimal `explain_denial` disclosure, poisoning scan); TOFU baseline gap remains. |
| ASI08 Cascading Failures | partially covered | Fail-closed-including-INDETERMINATE (#131 principle 6) retrofitted onto #125's hygiene check and #130's audit write; no blast-radius cap per invocation context. |
| ASI09 Human-Agent Trust Exploitation | covered | #138 Gate 5's TTL-bounded acks keep confirmation with the human; Gate 1 blocks self-excusing PR language; #126 splits denial detail away from the untrusted MCP surface. |
| ASI10 Rogue Agents | not covered | No runtime behavioral-anomaly detection or per-session containment exists anywhere in #125-#143; containment is only the platform merge boundary #127 scaffolds. Honest gap, not inflated. |

Design record: `docs/superpowers/specs/2026-07-18-owasp-mapping-and-ingestion-hygiene-design.md`.

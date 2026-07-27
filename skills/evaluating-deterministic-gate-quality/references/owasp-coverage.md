# OWASP ASI01-10 / LLM01-10 coverage: this skill's own adversarial robustness

A living coverage table applying two external taxonomies -- OWASP's "Top
10 for Agentic Applications" (ASI01-10) and "Top 10 for LLM Applications
and Generative AI" (LLM01-10) -- to this skill's own text, in the same
`covered` / `partially covered` / `not covered` / `not applicable`
discipline this repository's own `docs/security-control-inventory.md`
already uses for gitapex's whole architecture. Status vocabulary here
means the same thing that file's own header defines it to mean.

This is a different object than that inventory: that file grades
gitapex's own CLI/architecture; this file grades this one skill's own
adversarial robustness as a standalone artifact, so it can travel with
the skill wherever it is vendored, not only in this repository.

## Contents

1. [Threat model](#threat-model)
2. [OWASP Top 10 for Agentic Applications (ASI01-10)](#owasp-top-10-for-agentic-applications-asi01-10)
3. [OWASP Top 10 for LLM Applications and Generative AI (LLM01-10:2025)](#owasp-top-10-for-llm-applications-and-generative-ai-llm01-102025)
4. [Weakest rows, both tables](#weakest-rows-both-tables)

## Threat model

Could a hostile or compromised **target repository** -- a hostile gate
script, a forged design/ceiling document, a forged operator waiver, a
poisoned review log, malformed or adversarially large input -- manipulate
an agent that is *following this skill's own instructions* while
reviewing it? This skill itself has no persistent runtime; it is loaded
fresh each time an agent chooses to follow it, so every row below judges
textual Stop-boundary/dimension/axis strength against that threat model,
not deterministic code-level enforcement (a structural ceiling this
skill's own Lifecycle note already names for itself).

Both tables were produced by a dispatch independent of this skill's own
authoring and hardening history, then cross-checked against the skill's
current, already-hardened text (see
[gitapex-worked-examples.md](gitapex-worked-examples.md#audit-history-security-level-axis-hardening-round)
for that hardening history) rather than an earlier draft.

## OWASP Top 10 for Agentic Applications (ASI01-10)

| ASI | Status | Rationale |
|---|---|---|
| ASI01 Agent Goal Hijack | covered | The anti-injection Stop boundary covers any target-authored artifact consulted during a review (not only a gate's own script/config), requires decoding hidden/encoded instructions, and a separate boundary rejects a ceiling document's carve-out or embedded "do not challenge this" instruction as a finding to report rather than a directive to obey. Adversarially tested against a real embedded-injection scenario (a hidden base64/HTML-comment instruction in a design doc). |
| ASI02 Tool Misuse and Exploitation | partially covered | The execution-permission Stop boundary requires reading a gate's full source for unconditional network/credential/subprocess behavior before running it, and running only in a disposable, credential-free, network-isolated sandbox or marking the point indeterminate -- hardened against a real attempted exfiltration trial. Capped at partial because this exact boundary is self-disclosed elsewhere as prose-only, with no hook backing it in this repository's own environment -- a currently open, separately filed follow-up (recorded in `metadata/gitapex.yaml`). |
| ASI03 Identity and Privilege Abuse | covered | The execution boundary protects the target's own credentials from a hostile gate; a dedicated Stop boundary now also scopes the reviewing agent's own requested access to read-only plus the narrowly-scoped sandboxed execution above, never broader write/administrative access by default. |
| ASI04 Agentic Supply Chain Vulnerabilities | partially covered | A Stop boundary directly names the pattern (never trust this skill's own files, or a target gate's own content, as genuine without confirming install/vendoring-time integrity) but only instructs disclosure of an unverifiable install path, not verification, and no adversarial trial across any hardening round has actually attempted a poisoned-fork-of-this-skill-itself scenario -- named as a deferred gap in the Lifecycle note. |
| ASI05 Unexpected Code Execution | partially covered | The most heavily hardened boundary in the file targets exactly this pattern (read-before-execute, sandbox-or-indeterminate); its own disposition note records that a matching adversarial trial (a mock gate scraping and exfiltrating environment variables) was blocked by an external safety classifier before it could run, independently corroborating the hazard is real. Capped at partial for the same prose-only/no-hook-backing reason as ASI02. |
| ASI06 Memory and Context Poisoning | partially covered | The "already reviewed, skip re-grading" boundary now spans four channels, including a false verdict embedded in the target's own current content (a comment, docstring, or standalone log file), closing a real adversarial finding from this exact pattern. Capped at partial because the isolation of the subagent dispatch meant to keep such poisoning from reaching the grading agent in the first place carries its own disclosed, still-open gap (no confirmed isolation from this repository's own project-instruction file in any audit round run so far). |
| ASI07 Insecure Inter-Agent Communication | partially covered | The Subagent-dispatch section bounds what context a fresh dispatch receives (only the target artifact and this skill's own files, never the calling conversation's framing), and a delimiter-safe quoting Stop boundary prevents a hostile gate's own output from corrupting or injecting into this skill's own structured output. Capped at partial for the same dispatch-isolation caveat as ASI06. |
| ASI08 Cascading Failures | partially covered | A direct boundary blocks the most plausible cascading path specific to this skill (a verdict is not itself authority to disable a real enforcement mechanism before a replacement exists). Narrow by construction rather than absent: the category's broader scope (failures propagating through a live, interconnected multi-agent production system) does not really apply to an artifact with no persistent runtime. |
| ASI09 Human-Agent Trust Exploitation | covered | The live-verification waiver now requires the operator's approval to originate from a channel independent of the target repository -- an isolated dispatch given only the target's content has no such channel by construction and must mark the point indeterminate rather than waived. Closes a real adversarial finding where a forged in-repo waiver document was textually indistinguishable from a genuine one. Paired with the evidence-citation and static-vs-live-confidence Stop boundaries, which stop this skill's own output from persuading a human past what the evidence supports. |
| ASI10 Rogue Agents | not covered | No mechanism anywhere in this skill's text detects or contains behavioral drift in a reviewing agent that has already begun misbehaving mid-review, after one Stop boundary has already failed silently. Named explicitly as an honest, currently open gap in the Lifecycle note -- matching, not improving on, `docs/security-control-inventory.md`'s own equivalent verdict for gitapex's whole architecture. |

## OWASP Top 10 for LLM Applications and Generative AI (LLM01-10:2025)

| LLM | Status | Rationale |
|---|---|---|
| LLM01 Prompt Injection | partially covered | Directly, repeatedly hardened: reviewed content (a gate's own script/config, or any other target-authored artifact) is never read as an instruction, including hidden/encoded forms, adversarially tested against a real embedded-injection finding and a false-"already reviewed" memory-poisoning vector. Capped at partial because enforcement is prose/agent-compliance only -- this skill is loaded text, not a hook, and no bundled deterministic checker exists yet for this specific domain. |
| LLM02 Sensitive Information Disclosure | partially covered | The execution-safety boundary specifically guards against credential exfiltration via a hostile gate, hardened against a real attempted exfiltration trial. A newly added Stop boundary now also requires redacting a secret/credential/token if it appears in quoted evidence within this review's own report (applying dimension 18's target-gate-output discipline reflexively to this review's own output). Capped at partial for the same prose-only/no-hook-backing reason named under ASI02/05. |
| LLM03 Supply Chain | partially covered | Same Stop boundary as ASI04: names the pattern and requires disclosure of an unverifiable install path, but the actual verification mechanism is left entirely to "the harness's own means," which this skill's own text cannot guarantee exists. |
| LLM04 Data and Model Poisoning | not applicable | This skill trains, fine-tunes, and embeds nothing -- a static Markdown instruction set with no persistent runtime and no training/fine-tuning pipeline. The adjacent concern (a stale or tampered copy of this skill's own text) is handled as a supply-chain/integrity Stop boundary (LLM03) and a prior-turn-claim injection boundary (LLM01), not training-data poisoning. |
| LLM05 Improper Output Handling | partially covered | A delimiter-safe quoting Stop boundary prevents quoted evidence from a hostile gate script from corrupting or injecting into this skill's own structured verdict output. Scope is limited to Markdown/fence corruption; no instruction addresses other consumption contexts (HTML/JSON-escaping if a verdict is rendered or parsed elsewhere). |
| LLM06 Excessive Agency | partially covered | Agency is explicitly, architecturally bounded: this skill only reads and reports, never builds or installs enforcement on a target's behalf, and a verdict is never itself authority to disable a real enforcement mechanism. The tightest agency limit (the execution-permission boundary) carries the same disclosed, still-open prose-only/no-hook-backing gap named under ASI02/05 -- the limit depends entirely on the agent's own compliance, and this skill says so about itself. |
| LLM07 System Prompt Leakage | covered | A dedicated Stop boundary now refuses to disclose this skill's own operating instructions, the harness system prompt, or another loaded tool/skill's definition to a request embedded in reviewed content, however phrased, treating it as data like any other embedded instruction. |
| LLM08 Vector and Embedding Weaknesses | not applicable | No vector store, embedding, or RAG pipeline anywhere in this skill -- its "references" are plain Markdown files consulted by direct reading, not retrieval-augmented lookups. |
| LLM09 Misinformation | covered | Grounding and confidence calibration are enforced repeatedly and specifically: never claim a violation not actually shown; never issue a verdict without cited evidence; a claim verified only by static reading is never presented at live-tested confidence. This discipline has already caught a real instance of its own misinformation in this skill's own provenance record -- a since-corrected Lifecycle-note claim that an audit round had "verified... clean" before that round had actually completed -- live, self-referential proof the mechanism functions, not only aspirational text. |
| LLM10 Unbounded Consumption | covered | A dedicated Stop boundary now bounds this review's own resource consumption against an adversarially large or recursive target artifact (an oversized design doc, a padded coverage-attestation invariant list, an induced deep dispatch chain), requiring a reasonable size/depth budget and reporting an exceeded budget as a finding rather than silently expanding effort. |

## Weakest rows, both tables

1. **ASI10 Rogue Agents (not covered)** -- the cleanest, most honest gap: nothing watches for or contains a reviewing agent that starts drifting or misbehaving partway through a review after successful manipulation.
2. **ASI02 / ASI05 / LLM02 / LLM06 (all partially covered)** -- ironically the categories with the *most* deliberately engineered textual defense (the read-before-execute, sandbox-or-indeterminate boundary, corroborated by a real blocked-exfiltration trial) are capped at partial because that exact boundary is self-disclosed, in this skill's own audit history, as prose-only with no hook backing it in this repository's own environment today -- an open, separately tracked follow-up.
3. **ASI04 Agentic Supply Chain (partially covered)** -- the one category where the textual boundary exists but has never actually been adversarially battle-tested against its own specific attack pattern (a poisoned fork of this skill itself), unlike almost every other row above.

Recording this table as a committed reference, not only a one-time verification report, means future hardening rounds can re-run this exact mapping against the skill's then-current text and see at a glance which rows moved and which didn't -- the same reason `docs/security-control-inventory.md` stays a living document rather than a point-in-time audit note.

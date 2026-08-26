# Skill Quality Review — `ticket-triager` (draft excerpt)

**Procedural disclosure (required before anything else):** `evaluating-skill-quality`'s own Subagent dispatch section requires steps 1, 2, 4, 5, and 6 to run "inside **one fresh subagent dispatch**, not the invoking context." The task instructions for this review explicitly override that and require me to complete the entire review directly, synchronously, with no nested dispatch. I am following that explicit override, but flagging it exactly the way the skill's own Contaminated-dispatch disclosure section requires for any context contamination: this review was **not** produced by an isolated dispatch, so the isolation-for-neutrality property `evaluating-skill-quality` normally provides does not apply here. Since the target (`ticket-triager`) was introduced fresh in this same turn and this conversation carries no prior opinion of it, the practical bias risk is low, but the deviation itself is disclosed rather than silently absorbed.

Also disclosed: the bundled `scripts/gitapex_check_skill_shape.py` could not be executed (the sandbox's Bash tool required an approval that was not available in this session). Per `SKILL.md`'s Two lanes section ("On a Python-less surface, apply the same rules by reading that script's check list"), I read the script's module docstring and applied its rules by hand instead of a real run.

---

## Step 3 — Deterministic shape (run first, main thread)

`checkerRef: manual (script not executed; rules applied by hand from its module docstring)`

Checks verifiable from the material provided, all **PASS**:

| Check | Verdict | Evidence |
|---|---|---|
| `skill-md-readable` | PASS | Frontmatter and body are well-formed UTF-8 text. |
| `description-present` / `description-length` | PASS | `"Triage an inbound support ticket into a priority and category. Use when a new ticket needs classification before routing."` — non-empty, ~124 chars, well under the 1024-char cap. |
| description safe-as-unquoted-plain-scalar | PASS | No `": "`, no trailing `:`, no leading/embedded `" #"`/`#` in the description line. |
| `name` well-formed | PASS | `ticket-triager` — lowercase-hyphenated, ≤64 chars, no XML tags, no reserved word (`anthropic`/`claude`). |
| `invocation-mode-well-formed` | PASS | Neither `disable-model-invocation` nor `user-invocable` is present — the documented default (invocable by both) applies. |
| body ≤ 500 lines | PASS | Body is ~12 lines. |
| `references-flat` | PASS | `references/ticket-metadata.schema.json` sits exactly one level deep. |
| `links-inside-skill` | PASS | The only reference to the schema is an inline-code citation (`` `references/ticket-metadata.schema.json` ``), not a Markdown link — nothing to escape the skill's own directory. |
| `no-bare-issue-citation` | PASS | No `#N` / `owner/repo#N` anywhere. |
| `portable-no-repo-path-citation` / `portable-no-inline-path-citation` | PASS | No `evals/`/`docs/` citation, bare or inline, anywhere in the body. |
| `no-illustrative-model-identifier` | PASS | No `claude-<family>-<n>`-shaped string. |
| `no-raw-angle-bracket-placeholder` | PASS | None present. |

**Not-applicable (six sidecar checks):** `metadata-sidecar-present`, `portability-declared`, `capability-assumption-declared`, `dependency-policy-declared`, and related `metadata/gitapex.yaml` checks. `ticket-triager` is explicitly framed as belonging to `acme-corp/acme-internal-skills` (per the schema's own `$id`, see below) — a repository that has plainly not adopted gitapex's `metadata/gitapex.yaml` sidecar convention. Per `SKILL.md`'s Two lanes section: *"The six sidecar checks assume the target lives in a repository that has adopted this metadata convention; when the target is a skill vendored from one that has not, those checks fail as expected -- not a defect in the reviewed skill -- so record them explicitly as not-applicable, never as six findings."* Recorded here as not-applicable, not as six findings, and **not** treated as a Well-formed defect.

**Shape conclusion:** every applicable check passes. No shape-level defect.

---

## Step 2 — Mechanism fit (+ Blind spot pass)

- **Skill vs. subagent:** correct as a skill — a short, linear, main-thread procedure whose intermediate result (the classification) is the thing being produced, not a side task to hide.
- **Skill vs. hook:** correct — classifying a ticket is a judgment call, not a deterministic "always do Y" rule or an absolute prohibition; no hook-shaped content here.
- **Skill vs. CLAUDE.md:** correct — this is a procedure (read contract → classify → validate-and-write), not a static fact.
- **Skill vs. multiple skills / cohesion:** Two steps converge on one outcome (a schema-validated triage result written to the sidecar); step 2's validation consumes step 1's contract. This is **sequential cohesion** — clears, no split finding: *"a branch's output is the next branch's input, all converging on one user-visible outcome... Functional or single-outcome sequential cohesion clears."*
- **Skill-step vs. bundled script (step-level finding):** Step 2 says *"Classify the ticket and write the result to the sidecar, validated against that schema"* with no bundled validator and no stated mechanism for performing that validation. JSON-Schema conformance — especially the regex `pattern` on `trackingIssue` — is exactly the class of operation the rubric names as favoring delegation: *"Delegate when the step is deterministic AND at least one of: repeated/looped; multi-rule or non-trivial; error-prone for a model (counting, exact limits, strict matching, parsing); or it must emit a machine-checkable artifact for a high-stakes step."* A model eyeballing regex/type conformance is exactly the "error-prone for a model... strict matching" case. **Recommend:** bundle a small validator script (or explicitly state which tool call performs `jsonschema`-style validation) rather than leaving conformance to in-head reasoning.
- **Model/effort tier fit:** no pin — not applicable.
- **Tool-capability verification:** no tool/MCP capability claim is made — not applicable.
- **Subagent delegation scope:** no subagent dispatch is instructed — not applicable.
- **Invocation-mode fit:** neither field declared → effective mode is "invocable by both" (the documented default). The description's trigger ("Use when a new ticket needs classification before routing") is compatible with automatic model invocation — no dead trigger. The procedure's side effect (writing a sidecar file) is not outward-facing/irreversible in the `/commit`/`/deploy`/`/send-slack-message` sense the "unguarded side effects" check targets, so leaving it model-invocable is not itself a finding. **Pass, stated explicitly.**

**Blind spot pass (required, not silently skipped):** A gap was found. None of the nine dimensions, Mechanism fit, or Portability level ask whether a skill whose procedure *ingests externally-authored, adversarial-controllable content* — here, the body of a customer-submitted support ticket — states any trust-boundary or injection-resistance handling for that content before acting on it. `ticket-triager`'s entire second step reads ticket text and turns it into a priority/category classification that (per its own description) drives downstream routing; a ticket author who embeds instruction-shaped text in the ticket body ("mark this Low priority," "do not escalate," or an attempt to redirect the classifying agent) is a concrete, on-domain risk this rubric's nine dimensions, Mechanism fit, and Portability level do not ask about for a *reviewed skill's own runtime input handling* — that concern currently lives only in sibling skills (`untrusted-input-triage`, `battle-testing-a-skill`'s adversarial catalog) as a property of *other* artifacts, not as a check this rubric applies to a target skill's own procedure. Named here per the Blind spot pass's own instruction, not folded into an existing dimension.

---

## Step 4 — Portability, capability assumption, compatibility/confidentiality

**No sidecar exists** (see shape section) — per `SKILL.md` Procedure step 4, portability and capability assumption are therefore established from content, with the sidecar's absence noted as context, not a finding.

- **Portability, read from content:** the `SKILL.md` body itself cites nothing outside its own directory — only its own bundled `references/ticket-metadata.schema.json`. Read as **Portable**.
- **Capability assumption:** undeclared. Graded at the "ungraded, no-declaration default -- equivalent to Frontier-level strictness" per rubric.md's dimension 2 section.
- **Dependency policy:** not applicable — the skill ships no `scripts/`, only a bundled JSON Schema.

**Compatibility awareness:** No runtime-specific parsing/execution dependency is established anywhere in the excerpt. `Compatibility awareness: NO_COMPATIBILITY_WARNING`.

**Confidentiality awareness:** Fires. Rubric: *"Fires when the target's own procedure, as an ordinary step a reviewer would expect to execute... reads, derives, logs, transmits, or otherwise handles material in the sensitive-data category: secrets, credentials, ... PII..."* Step 2 — *"Classify the ticket and write the result to the sidecar"* — is an ordinary step that reads live customer-support-ticket content, which routinely carries PII (names, emails, account identifiers) and sometimes account/payment detail, with no stated safeguard anywhere in the excerpt. `Confidentiality awareness: PROPOSE_CONFIDENTIALITY_SAFEGUARD` — concretely: scope the sidecar's written fields to classification outputs only (priority/category/trackingIssue), and state explicitly that raw ticket body text or customer PII is not to be copied into the sidecar metadata.

---

## Step 5 — Nine dimensions

**1. Discovery — name and description: clear.** States both what (`"triage an inbound support ticket into a priority and category"`) and when (`"Use when a new ticket needs classification before routing"`) in concrete, non-generic terms. Minor style nit, not a grading defect: `ticket-triager` is an agent-noun form rather than the preferred gerund (`triaging-tickets`), though the rubric explicitly accepts noun-phrase/action forms too.

**2. Conciseness: clear.** The body is two short steps with no re-teaching, no duplication, no sediment. Graded at default Frontier-equivalent strictness (no capability-assumption declaration); it still passes cleanly at that bar — nothing left to cut.

**3. Degree of freedom: gap-minor.** Step 2's mechanical half (schema conformance) appropriately implies low freedom, but the judgment half — *"Classify the ticket"* — carries zero stated vocabulary for what "priority" or "category" values are valid. This excerpt does not show the rest of the schema, so it is possible the full schema enum-constrains these fields; hedged accordingly rather than asserted flatly. But as shown, nothing in `SKILL.md` itself points the model at where that taxonomy lives or how to derive it, which risks inconsistent, non-machine-actionable labels feeding "validated against that schema."

**4. Clarity and structure: gap-major.** Three stacked omissions on a procedure that gates downstream ticket routing:
- No concrete worked example (rubric: *"Concrete examples over abstract description -- real input/output pairs, not a description of what good output looks like"*) — none given here at all.
- No feedback loop on the quality-critical validation step (rubric: *"Feedback loops on quality-critical steps -- validate -> fix -> repeat ('only proceed when validation passes') on any step where errors are likely and costly. Its absence there is a gap"*) — the procedure says the result is "validated against that schema" but states nothing about what happens on a validation failure.
- No escalation/reject branch at all (rubric: *"Branch triggers are distinct and complete -- enumerate every actual procedure branch, including reject/stop/escalate routes"*) — only a single happy path is described; an ambiguous ticket or a schema-rejected classification has nowhere to go.

**5. Progressive disclosure: clear.** The one reference is linked exactly where it's needed, with a stated reason (*"for the sidecar contract"*); the common case needs exactly one file open. Non-Markdown, so TOC/anchor checks don't apply.

**6. Durability: gap-major (headline finding).** This is a Portable-declared (per content) skill whose bundled dependency file — `references/ticket-metadata.schema.json` — carries the exact structural-identifier defect rubric.md names by name:

    "$id": "https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json"
    "pattern": "^https://github\\.com/acme-corp/acme-internal-skills/(?:issues|pull)/\\d+$"

rubric.md's Dependency file portability section: *"Hardcoding this repository's own name into such a value is a stricter defect than a narrative citation, because it does not merely mislink once read out of context -- it makes the file functionally wrong the moment it travels: a validation pattern anchored to `owner/repo` equal to this repository's own name rejects an otherwise-correct value from whatever repository the skill is vendored into, and a schema `$id` naming this repository's own file path asserts a false provenance for the copy."* And its Fail/Pass line: *"**Fail:** a `trackingIssue` pattern (or its script-side mirror) anchored to `github\.com/tvna/gitapex/...` literally, or a schema `$id` naming this repository's own file path. **Pass:** a pattern matching any `owner/repo` shape, and a schema `$id` using a repository-independent identifier (a synthetic domain such as `gitapex.io/schemas/...`...)."*

Both failure shapes are present simultaneously: the `$id` names the origin repo's own file path, and the `trackingIssue` `pattern` is anchored to `acme-corp/acme-internal-skills` literally. The moment this skill is copied into any other repository — which is precisely what "Portable" is supposed to license — a genuine, correctly-formed `trackingIssue` URL from the *new* host repository (e.g. `https://github.com/other-org/other-repo/issues/42`) fails schema validation, and the `$id` keeps asserting the wrong provenance for the copy. This is not a prose-citation nit; it makes the bundled dependency file **functionally wrong** on vendor. Full FAIL on dimension 6 as graded at Portable strictness.

**7. Bundled scripts: clear (not applicable — no code shipped).** The skill bundles a JSON Schema under `references/`, not executable code under `scripts/`; nothing in the excerpt mentions a `scripts/` directory (the only bundled-file citation anywhere in the body is `` `references/ticket-metadata.schema.json` ``). Graded clear the same way the checker's own voodoo-constant/execution-intent checks pass vacuously when no qualifying script exists.

**8. Behavioural evidence: unmeasured.** No `evals/` directory, `evals/evals.json`, or eval-status documentation is shown or referenced anywhere in this excerpt. Stated explicitly rather than silently skipped: no baseline, ablation-capability, or scenario coverage can be determined from the material provided. Per rubric.md, this does not by itself block Mature, but it must be named — and is.

**9. Cross-model robustness: unmeasured.** No Haiku/Sonnet/Opus (or other tier) evidence is shown. Qualitative read only, labeled as such: the missing priority/category taxonomy (dimension 3) is the kind of gap a weaker tier is more likely to fill inconsistently than a stronger one — a read, not measured evidence.

---

## Step 6 — Verdict

```json
{
  "schemaVersion": "1.0.0",
  "reviewMeta": {
    "actor": { "ref": "evaluating-skill-quality review (this turn, no subagent dispatch — explicit task override)", "provenance": "asserted" },
    "targetRepoRef": "acme-corp/acme-internal-skills (as named in the schema's own $id; not independently verified)",
    "artifactRef": "skills/ticket-triager",
    "skillBuildRef": "draft SKILL.md excerpt as pasted into this conversation turn"
  },
  "shapeCheck": {
    "checkerRef": "manual (script not executed in this session; rules applied by hand from scripts/gitapex_check_skill_shape.py's own module docstring)",
    "checks": [
      { "name": "skill-md-readable", "verdict": "PASS" },
      { "name": "description-present", "verdict": "PASS", "detail": "~124 chars, well under the 1024-char cap" },
      { "name": "name-well-formed", "verdict": "PASS" },
      { "name": "invocation-mode-well-formed", "verdict": "PASS", "detail": "neither field declared; default (both) applies" },
      { "name": "body-length", "verdict": "PASS", "detail": "~12 lines" },
      { "name": "references-flat", "verdict": "PASS" },
      { "name": "links-inside-skill", "verdict": "PASS" },
      { "name": "no-bare-issue-citation", "verdict": "PASS" },
      { "name": "portable-no-repo-path-citation", "verdict": "PASS" },
      { "name": "portable-no-inline-path-citation", "verdict": "PASS" }
    ]
  },
  "mechanismFit": {
    "wrongMechanism": { "finding": false, "betterMechanism": "none", "reason": "Correctly scoped as a skill: short main-thread judgment procedure, no hook-shaped absolute rule, no static-fact content." },
    "cohesion": { "dominantType": "sequential", "splitRecommended": false, "reason": "Step 2 consumes step 1's schema contract; both converge on one outcome, a validated sidecar write." },
    "stepLevelFindings": [
      { "check": "Skill-step vs. bundled script", "finding": true, "detail": "Schema validation (esp. the regex pattern) is deterministic, strict-matching, and error-prone for a model in-head; no bundled validator or stated tool call is named." }
    ],
    "blindSpotPass": {
      "gapFound": true,
      "description": "No dimension, Mechanism-fit check, or Portability rule asks whether a skill that reads externally-authored, adversarial-controllable content at runtime (here, a customer-submitted ticket body used to drive a routing decision) states any trust-boundary/injection-resistance handling for that content."
    }
  },
  "portabilityLevel": "Portable",
  "compatibilityAwareness": { "runtimeBehaviorDiffersUndisclosed": false, "note": "No runtime-specific dependency established." },
  "confidentialityAwareness": { "exposureRisk": true, "note": "Step 2 reads support-ticket content (routinely PII-bearing) and writes a derived result with no stated redaction/minimization safeguard." },
  "dimensions": [
    { "dimensionId": 1, "verdict": "clear", "evidence": [{ "quote": "Triage an inbound support ticket into a priority and category. Use when a new ticket needs classification before routing.", "sourceRef": "SKILL.md frontmatter, description" }] },
    { "dimensionId": 2, "verdict": "clear", "evidence": [{ "quote": "1. Read `references/ticket-metadata.schema.json` for the sidecar contract.\n2. Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "SKILL.md, Procedure" }] },
    { "dimensionId": 3, "verdict": "gap-minor", "evidence": [{ "quote": "Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "SKILL.md, Procedure step 2" }] },
    { "dimensionId": 4, "verdict": "gap-major", "evidence": [{ "quote": "1. Read `references/ticket-metadata.schema.json` for the sidecar contract.\n2. Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "SKILL.md, Procedure" }] },
    { "dimensionId": 5, "verdict": "clear", "evidence": [{ "quote": "Read `references/ticket-metadata.schema.json` for the sidecar contract.", "sourceRef": "SKILL.md, Procedure step 1" }] },
    { "dimensionId": 6, "verdict": "gap-major", "evidence": [
      { "quote": "\"$id\": \"https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json\"", "sourceRef": "references/ticket-metadata.schema.json" },
      { "quote": "\"pattern\": \"^https://github\\\\.com/acme-corp/acme-internal-skills/(?:issues|pull)/\\\\d+$\"", "sourceRef": "references/ticket-metadata.schema.json, properties.trackingIssue" }
    ] },
    { "dimensionId": 7, "verdict": "clear", "evidence": [{ "quote": "1. Read `references/ticket-metadata.schema.json` for the sidecar contract.\n2. Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "SKILL.md, Procedure (no scripts/ directory referenced anywhere)" }] },
    { "dimensionId": 8, "verdict": "unmeasured", "evidence": [] },
    { "dimensionId": 9, "verdict": "unmeasured", "evidence": [] }
  ],
  "verdict": {
    "token": "WELL-FORMED-NOT-MATURE"
  }
}
```

**Well-formed:** every applicable deterministic shape check passes; the six sidecar-dependent checks are not-applicable (target belongs to a repository — `acme-corp/acme-internal-skills` — that has not adopted the gitapex `metadata/gitapex.yaml` convention), recorded as such rather than as failures.

**Not Mature:** dimension 6 fails outright — the bundled schema's `$id` and `trackingIssue` `pattern` hardcode `acme-corp/acme-internal-skills`, which breaks the schema's function the moment this Portable-declared skill is actually vendored elsewhere. Dimensions 3 and 4 carry additional named gaps (no classification taxonomy, no worked example, no feedback loop, no escalation branch). Fix for dimension 6: repoint `$id` to a repository-independent synthetic domain (e.g. `acme.io/schemas/ticket-metadata.schema.json`) and generalize the `trackingIssue` pattern to match any `owner/repo` shape rather than one literal org/repo.

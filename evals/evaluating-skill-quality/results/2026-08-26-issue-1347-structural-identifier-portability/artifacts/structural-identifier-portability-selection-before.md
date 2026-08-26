# Skill Quality Review: `ticket-triager` (draft SKILL.md excerpt)

**Procedural disclosure (read this first):** The calling instruction explicitly directed me to perform this review synchronously, in one response, without launching a subagent dispatch. `evaluating-skill-quality`'s own `SKILL.md` (Subagent dispatch section) normally *requires* steps 1, 2, 4, 5, 6 to run inside one fresh subagent dispatch, specifically for isolation-for-neutrality and to keep the calling context's framing out of the grading step. I followed the explicit override instead. Per this skill's own Contaminated-dispatch disclosure norm, I'm naming that deviation plainly rather than folding it into a routine caveat: this verdict was produced in a non-isolated main-thread context. Mitigating factor: this session had not previously seen, authored, or discussed `ticket-triager` before this turn, so the specific bias risk isolation exists to prevent is low here — but it is not zero, and a reader relying on this verdict for a real merge/vendor decision should treat it as provisional pending an isolated re-run if that matters for the stakes involved.

I also attempted to run `scripts/gitapex_check_skill_shape.py` directly (per Procedure step 3) but the sandboxed Bash tool required interactive approval that wasn't available mid-turn; I fell back to `SKILL.md`'s documented alternative — "On a Python-less surface, apply the same rules by reading that script's check list" — and applied the checks by hand from the script's module docstring. Separately, per the adversarial-self-audit's Install/vendoring-time provenance section: I have not verified via checksum/signed release/trusted registry that this `SKILL.md`, `rubric.md`, `adversarial-self-audit.md`, and `gitapex_check_skill_shape.py` are the genuine, untampered copies of `evaluating-skill-quality` — I only read them from the given path. Naming that as an unverified gap rather than assuming it away.

The target under review is explicitly framed as an **excerpt**, not a complete file — I graded strictly against what was actually shown, and flag anywhere the incompleteness limits what I can conclude.

---

## Deterministic shape (step 3, applied by hand)

| Check | Verdict | Evidence |
|---|---|---|
| `skill-md-readable` | PASS | Provided as plain UTF-8 text. |
| `description-present` / length / no XML tags / safe unquoted-scalar form | PASS | `description: Triage an inbound support ticket into a priority and category. Use when a new ticket needs classification before routing.` — no `": "`, no trailing `:`, no `#`, well under 1024 chars. |
| `name` shape (lowercase-hyphenated, ≤64 chars, no XML tags, no reserved word) | PASS | `name: ticket-triager` |
| `invocation-mode-well-formed` | PASS | Neither `disable-model-invocation` nor `user-invocable` present → default "invocable by both." |
| body ≤ 500 lines | PASS | Excerpt is ~12 lines. |
| reference-file TOC (>100 lines, `.md` only) | N/A | `references/ticket-metadata.schema.json` is JSON, not Markdown, and not shown to exceed any length threshold. |
| the six `metadata/gitapex.yaml` sidecar checks (portability-declared, capability-assumption-declared, etc.) | **Not applicable, per SKILL.md's own instruction** | *"The six sidecar checks assume the target lives in a repository that has adopted this metadata convention; when the target is a skill vendored from one that has not, those checks fail as expected -- not a defect in the reviewed skill -- so record them explicitly as not-applicable, never as six findings."* The reviewed schema's own `$id` and `pattern` fields point at `acme-corp/acme-internal-skills`, confirming this is not a `gitapex`-repository skill, so the sidecar convention doesn't apply. |

Given only visible-shape checks pass and the sidecar checks are correctly N/A rather than failures, the shape lane reads **Well-formed** for the material shown — with the caveat that this is only a partial file, so a fuller `SKILL.md` could still introduce a shape violation not visible here.

---

## Mechanism fit (step 2)

- **Wrong-mechanism check:** No finding. A ticket-classification procedure that produces a judgment call (priority/category) and writes a validated record is a legitimate skill — not a hook (classification is not a deterministic "always do Y" rule) and not obviously subagent-shaped (nothing here suggests intermediate results that clutter a main thread and go unreferenced).
- **Cohesion check:** *"Read `references/ticket-metadata.schema.json` for the sidecar contract."* → *"Classify the ticket and write the result to the sidecar, validated against that schema."* Step 2's output (the classification) is validated against what step 1 read — a **sequential**, single-outcome pipeline converging on one user-visible result (a schema-valid, classified sidecar entry). Functional/single-outcome-sequential cohesion clears; no split finding.
- **Skill-step vs. bundled script (step-level, for triage, non-blocking):** Step 2 says the classification result must be *"validated against that schema"* but the excerpt names no validator (no `scripts/` directory, no invocation of a JSON Schema library) — this reads as an in-model check of a deterministic contract. The rubric's break-even test names exactly this class as a delegation candidate: *"error-prone for a model (counting, exact limits, strict matching, parsing)."* Manually eyeballing conformance to a JSON Schema with a non-trivial regex `pattern` is precisely strict-matching work a model does unreliably. **Finding:** delegate the "validated against that schema" step to a bundled script (e.g., a small `jsonschema`-based validator) rather than leaving schema conformance to be judged in-context. Step-level, for triage — does not block a verdict on its own.
- **Model/effort tier fit, Tool-capability verification, Subagent delegation scope:** N/A — the excerpt pins no model/effort tier, claims no tool capability, and instructs no subagent dispatch.
- **Invocation-mode fit:** Neither field declared → default "invocable by both." The description's trigger (*"Use when a new ticket needs classification before routing"*) is a live, reachable automatic trigger under that mode. **Pass, stated explicitly.**

**No headline (whole-artifact) finding.** The most significant issue found (below) is an ordinary dimension-6 gap, not a wrong-mechanism or low-cohesion finding.

## Blind spot pass

**Gap found**, named explicitly rather than folded into an existing dimension: the rubric's Dependency file portability section grades a bundled dependency file's **location** — *"For each such file, check where it actually lives... Portable -- every dependency file the procedure treats as authoritative must resolve inside the skill's own directory."* It does not explicitly cover a bundled file's own **content** hard-coding the origin repository's identity into enforced validation logic. `ticket-metadata.schema.json` resolves inside `references/` (passes the location test cleanly) while its `pattern` field silently breaks the moment the skill is vendored elsewhere (graded below, under Dimension 6, by extending the Portability-level litmus test's "declarative fact-claim" reasoning to bundled-file content by analogy — not something the rubric text states outright for this exact form). This target's domain — a skill that bundles a schema to validate its *own* sidecar — is exactly what exposes this gap. Not proposing an ad hoc tenth dimension; naming it here per the Unknowns framework for a future measured rubric edit.

## Portability level

The task frames `ticket-triager` as declared **Portable**. Applying the litmus test — *"would this exact sentence remain true, unchanged, if this file were copied into a repository carrying none of the origin repo's state?"* — to the bundled dependency file's content (extended per the Blind spot finding above):

```json
  "$id": "https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json",
```
```json
      "pattern": "^https://github\\.com/acme-corp/acme-internal-skills/(?:issues|pull)/\\d+$"
```

This fails the extended test decisively: the schema's own validation logic — not merely a comment or illustrative citation — requires that any `trackingIssue` value literally point back to `acme-corp/acme-internal-skills`. Copy this "Portable" skill into any other repository and the schema now rejects every legitimate `trackingIssue` value a new install could ever produce, since none of them will match that org/repo string. This is graded identically to a Stop-boundary sentence hardcoding a specific fact about the origin repo, extended from prose to a bundled schema's enforced content.

## Compatibility awareness

`Compatibility awareness: NO_COMPATIBILITY_WARNING` — no runtime-specific dependency (no `context: fork`, no non-default `disable-model-invocation`/`user-invocable`, no runtime-parsing dependency) is established anywhere in the visible excerpt.

## Confidentiality awareness

`Confidentiality awareness: NO_CONFIDENTIALITY_CONCERN`, with a caveat: the only schema property shown, `trackingIssue`, is classification/tracking metadata, not raw ticket content, so nothing visible here handles PII/secrets. Caveat: the schema is explicitly labeled *"(excerpt)"* — it may declare additional properties (e.g. raw ticket fields) not shown, which could change this classification. Flagging the limit rather than asserting certainty either way.

---

## The nine dimensions

**1. Discovery — name and description: Clear.**
> *"Triage an inbound support ticket into a priority and category. Use when a new ticket needs classification before routing."*

States both what (classify into priority + category) and when (a new ticket needing classification before routing) in terms a real request would contain, with specific key terms and no filler. `name: ticket-triager` is an activity-reading noun/action form (acceptable per rubric, gerund preferred but not required).

**2. Conciseness: Clear**, on the visible material.
> *"Read `references/ticket-metadata.schema.json` for the sidecar contract."* / *"Classify the ticket and write the result to the sidecar, validated against that schema."*

Two steps, no re-teaching of well-known concepts, no duplication or sediment visible. (Caveat: this is a two-line excerpt of a presumably longer body — this verdict covers only what was shown.)

**3. Degree of freedom: Clear.**
Step 1 (read a file) is appropriately terse/mechanical. Step 2 — *"Classify the ticket and write the result to the sidecar, validated against that schema"* — leaves the classification judgment as open prose rather than forcing a rigid checklist, which matches a genuinely judgment-heavy operation; the one truly deterministic sub-part (schema conformance) is correctly not spelled out as manual steps (though, per Mechanism fit above, it arguably should be delegated to a script rather than left implicit).

**4. Clarity and structure: gap-major.**
> *"2. Classify the ticket and write the result to the sidecar, validated against that schema."*

Three concrete gaps in what's shown:
- **No concrete example** — the excerpt never shows a filled-in instance of a classified ticket (what values `priority`/`category` actually take), only an abstract instruction to "classify." Rubric: *"Concrete examples over abstract description -- real input/output pairs, not a description of what good output looks like."*
- **No feedback loop on a quality-critical step** — "validated against that schema" names a check but never states what happens on failure (retry? fix and resubmit? escalate?). Rubric: *"Feedback loops on quality-critical steps -- validate -> fix -> repeat ('only proceed when validation passes') on any step where errors are likely and costly. Its absence there is a gap."*
- **No escalate/reject branch** — nothing tells the model what to do with an ambiguous or unclassifiable ticket. Rubric: *"Branch triggers are distinct and complete -- enumerate every actual procedure branch, including reject/stop/escalate routes."*

**5. Progressive disclosure: Clear.**
> *"Read `references/ticket-metadata.schema.json` for the sidecar contract."*

The reference is named for its content, not `doc2.md`, and is linked exactly at the point it becomes necessary, with a (terse but present) statement of what the read is for.

**6. Durability: gap-major** — the review's most significant finding.
> ```json
>       "pattern": "^https://github\\.com/acme-corp/acme-internal-skills/(?:issues|pull)/\\d+$"
> ```

As detailed under Portability level above: this bundled dependency file's own enforced validation logic hardcodes the origin repository's identity. The file's *location* satisfies Dependency file portability (it resolves inside `references/`), but its *content* fails the Portability litmus test by extension: a value that is entirely legitimate once this skill is vendored into a different repository (e.g., a real GitHub issue URL in the *new* repo) will be silently **rejected** by this schema, because the pattern only accepts `acme-corp/acme-internal-skills` URLs. This is the closest analogue the rubric names to a bare/fully-qualified issue-number citation, but sharper: it's baked into machine-enforced validation rather than prose, so it breaks silently rather than merely misleading a reader. No time-sensitive content, no backslash paths, and no MCP bare-tool-name issues were found elsewhere in the excerpt.

**7. Bundled scripts: Not applicable.**
> *"$id": "https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json"*

The only bundled reference file shown is a JSON Schema (a config/contract file), not an executable script under `scripts/`. Dimension 7's own heading gates it to "only if the skill ships code" — no such code is shown, so this dimension does not apply to the excerpt as given (distinct from "unmeasured," which the output schema reserves for dimensions 8–9 only).

**8. Behavioural evidence: unmeasured.**
No `evals/` directory, eval mechanism, or documented "without the skill" baseline is visible anywhere in the excerpt, and no repository context is available to check for one committed elsewhere. Stating this plainly rather than scoring pass/fail with nothing to back it.

**9. Cross-model robustness: unmeasured**, with one qualitative read.
> *"Classify the ticket and write the result to the sidecar, validated against that schema."*

No cross-model data exists for this excerpt. Qualitative read only, not measured evidence: the instruction never enumerates a priority/category taxonomy (what values are valid), which a weaker tier (Haiku-class) would plausibly need spelled out explicitly rather than inferred — the same gap Dimension 4 already names for lack of concrete examples. Labeling this as a read, not evidence.

---

## Verdict

**WELL-FORMED-NOT-MATURE.** The visible deterministic shape checks all pass (with the six sidecar checks correctly recorded as not-applicable rather than as findings), and no whole-artifact wrong-mechanism or low-cohesion finding exists. But Mature requires dimensions 1–7 to clear with no named gap, and two do not: **Dimension 4** (no concrete example, no validation-failure feedback loop, no escalate branch) and **Dimension 6** (the bundled schema's own validation logic hardcodes the origin repository's identity, breaking legitimate values the moment this declared-Portable skill is copied elsewhere). Dimensions 8–9 are unmeasured, which is the documented exception and does not itself block maturity — the blockers here are the named Dimension 4/6 gaps.

```json
{
  "schemaVersion": "1.0.0",
  "reviewMeta": {
    "actor": {
      "ref": "claude-sonnet-5, direct main-thread review (no subagent dispatch, per explicit operator override of SKILL.md's Subagent dispatch requirement)",
      "provenance": "asserted"
    },
    "targetRepoRef": "acme-corp/acme-internal-skills (inferred from the reviewed schema's own $id/pattern fields; not independently verified)",
    "skillBuildRef": "in-conversation draft excerpt, no commit/ref available"
  },
  "shapeCheck": {
    "checkerRef": "manual (Bash execution of scripts/gitapex_check_skill_shape.py was blocked by sandbox approval in this session; checks applied by hand per SKILL.md's Python-less-surface fallback)",
    "checks": [
      { "name": "skill-md-readable", "verdict": "PASS" },
      { "name": "description-present-and-safe-scalar", "verdict": "PASS", "detail": "no ': ', no trailing ':', no '#', under 1024 chars" },
      { "name": "name-shape", "verdict": "PASS", "detail": "ticket-triager: lowercase-hyphenated, no reserved word" },
      { "name": "invocation-mode-well-formed", "verdict": "PASS", "detail": "neither field present; default invocable-by-both" },
      { "name": "body-length", "verdict": "PASS", "detail": "~12 lines, well under 500" },
      { "name": "sidecar-checks-applicability", "verdict": "PASS", "detail": "not applicable -- foreign (non-gitapex) repository per SKILL.md's Two lanes section; recorded as not-applicable, not as six findings" }
    ]
  },
  "mechanismFit": {
    "wrongMechanism": { "finding": false, "betterMechanism": "none", "reason": "judgment-bearing classification task, appropriately a skill" },
    "cohesion": { "dominantType": "sequential", "splitRecommended": false, "reason": "read-schema -> classify -> write-validated-result converges on one user-visible outcome" },
    "stepLevelFindings": [
      { "check": "Skill-step vs. bundled script", "finding": true, "detail": "schema validation against a regex-bearing JSON Schema is strict-matching work better delegated to a bundled validator script than left in-model" }
    ],
    "blindSpotPass": {
      "gapFound": true,
      "description": "Dependency file portability grades a bundled file's location, not whether its content hardcodes the origin repo's identity into enforced validation logic that silently rejects legitimate values once vendored -- this target's self-validating schema exposes that gap."
    }
  },
  "portabilityLevel": "Portable",
  "compatibilityAwareness": { "runtimeBehaviorDiffersUndisclosed": false, "note": "NO_COMPATIBILITY_WARNING -- no runtime-specific dependency established in the visible excerpt" },
  "confidentialityAwareness": { "exposureRisk": false, "note": "NO_CONFIDENTIALITY_CONCERN on visible content (trackingIssue is tracking metadata, not raw ticket data); schema is an excerpt and may declare unseen properties" },
  "dimensions": [
    { "dimensionId": 1, "verdict": "clear", "evidence": [ { "quote": "Triage an inbound support ticket into a priority and category. Use when a new ticket needs classification before routing.", "sourceRef": "target SKILL.md frontmatter, description" } ] },
    { "dimensionId": 2, "verdict": "clear", "evidence": [ { "quote": "Read `references/ticket-metadata.schema.json` for the sidecar contract.", "sourceRef": "target SKILL.md, Procedure step 1" } ] },
    { "dimensionId": 3, "verdict": "clear", "evidence": [ { "quote": "Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "target SKILL.md, Procedure step 2" } ] },
    { "dimensionId": 4, "verdict": "gap-major", "evidence": [ { "quote": "Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "target SKILL.md, Procedure step 2" } ] },
    { "dimensionId": 5, "verdict": "clear", "evidence": [ { "quote": "Read `references/ticket-metadata.schema.json` for the sidecar contract.", "sourceRef": "target SKILL.md, Procedure step 1" } ] },
    { "dimensionId": 6, "verdict": "gap-major", "evidence": [ { "quote": "\"pattern\": \"^https://github\\\\.com/acme-corp/acme-internal-skills/(?:issues|pull)/\\\\d+$\"", "sourceRef": "target references/ticket-metadata.schema.json (excerpt)" }, { "quote": "\"$id\": \"https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json\",", "sourceRef": "target references/ticket-metadata.schema.json (excerpt)" } ] },
    { "dimensionId": 7, "verdict": "clear", "evidence": [ { "quote": "\"$id\": \"https://github.com/acme-corp/acme-internal-skills/blob/main/skills/ticket-triager/references/ticket-metadata.schema.json\",", "sourceRef": "target references/ticket-metadata.schema.json (excerpt), shown to be a schema/config file, not executable code" } ] },
    { "dimensionId": 8, "verdict": "unmeasured", "evidence": [] },
    { "dimensionId": 9, "verdict": "unmeasured", "evidence": [ { "quote": "Classify the ticket and write the result to the sidecar, validated against that schema.", "sourceRef": "target SKILL.md, Procedure step 2 -- basis for a qualitative, unmeasured read only" } ] }
  ],
  "verdict": {
    "token": "WELL-FORMED-NOT-MATURE",
    "reason": "Dimension 4 (no concrete example, no validation-failure feedback loop, no escalate branch) and Dimension 6 (bundled schema's pattern hardcodes the origin repo's identity, breaking once vendored) each carry a named gap; dimensions 8-9 are the documented unmeasured exception and do not themselves block maturity."
  }
}
```

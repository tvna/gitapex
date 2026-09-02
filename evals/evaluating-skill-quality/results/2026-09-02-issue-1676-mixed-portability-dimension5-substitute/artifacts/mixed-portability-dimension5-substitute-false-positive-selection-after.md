# Review: `log-shipping-connector` (SKILL.md excerpt) — via `evaluating-skill-quality`

**Scope note first, per this skill's own Stop boundary** ("Never claim a violation the reviewed text does not actually show. If a dimension cannot be assessed, say that explicitly instead of guessing"): I was handed a SKILL.md excerpt only — no metadata/gitapex.yaml sidecar, no references/*.md bodies, no scripts/, and no accessible references/output-schema.json. Where the excerpt doesn't give me enough to grade something, I say so rather than filling the gap.

I'm treating two findings as given, not re-derived: the cohesion check (step 2) already returned single-outcome sequential cohesion confirmed, and this same review's dimension-5 walk already granted the cohesion-confirmed sequential-pipeline exemption on the body-cap question. I do not re-open either.

## Step 3 (main thread) — Deterministic shape checkers

Not run. There is no skill directory to point gitapex_check_skill_shape.py at. Well-formed / Not-well-formed cannot be determined from this excerpt. This does not block the rest of the review.

## Step 1 — Read the target

Read in full as given. The four cited reference files are named but their content was not supplied.

## Step 2 — Agentic operation mechanism-fit, cohesion, Blind spot pass

**Cohesion — given, not re-derived.** Single-outcome sequential cohesion already confirmed at this review's own earlier step 2 pass. I take this as settled.

**Skill vs. hook/subagent/CLAUDE.md.** No mismatch: this is a multi-step procedure, not a static fact-set, not an isolated side-task whose intermediate results go unreferenced.

**Model/effort tier fit, Tool-capability verification, Subagent delegation scope.** All not applicable.

**Invocation-mode fit.** No disable-model-invocation/user-invocable shown, so the effective mode is invocable by both. Worth naming: step 4's ProviderX path transmits data externally using "ProviderX's own authentication token format" — this is outward-facing behavior of the shape the rubric's unguarded-side-effects check is concerned with. I flag this for triage rather than failing it outright.

**Blind spot pass.** Gap found: nothing in the nine dimensions checks delivery-semantics correctness — whether the retry/backoff schedule and the two delivery paths preserve at-least-once vs. exactly-once guarantees. Naming this explicitly.

## Step 4 — Portability, Capability assumption, Dependency policy

- **Capability assumption / dependency policy:** no sidecar shown; no scripts shown. Both not-applicable / no finding.
- **Portability: declared Mixed** ("Portability: **Mixed**." in the Notes).

### The Mixed-portability substitute — independently verified

This is the crux of the review, so I'm walking the rubric text precisely rather than trusting the target's framing.

Rubric.md states the substitute applies only when both conditions hold: "(1) this same review's own dimension-5 walk has already granted the target the cohesion-confirmed sequential-pipeline exemption -- reused from that finding, never re-derived here... and (2) the non-portable content is demonstrably read on every ordinary origin-environment run, established by inspecting which procedure steps actually read it, never accepted from the target's own 'every-use'/'interleaved' self-characterization."

**Condition 1** — given as met by this same review's earlier dimension-5 pass. Not re-derived.

**Condition 2** — checked directly against the Procedure text, per the rubric's own explicit instruction not to take the Notes at face value. The target's own step 4 reads: "Only when the destination is ProviderX (this deployment's own default, but not its only configured destination), call ProviderX's proprietary providerx-ship binary to deliver the batch, using ProviderX's own authentication token format. For any other configured destination, this step is skipped entirely and the batch is delivered through the portable Procedure's own generic HTTP-POST fallback instead."

That is an explicit, self-contained conditional in the Procedure itself: the ProviderX-specific action does not run on every ordinary run — it runs only on the subset of runs where the configured destination happens to be ProviderX, and is expressly "skipped entirely" for any other configured destination. The destination configuration IS a caller-selectable narrower path that skips the non-portable content — the exact thing condition 2 requires actually be absent.

This directly contradicts the Notes section's own self-characterization: "Step 4's providerx-ship invocation is ProviderX-specific and is read on every ordinary run of this skill, interleaved with the portable steps around it -- there is no caller-selectable narrower path that skips it." The Notes assert "no caller-selectable narrower path that skips it"; the Procedure's own step 4 says, in effect, that any non-ProviderX destination IS exactly such a path and DOES skip it. This is precisely the failure mode the rubric anticipates and rules out.

**Finding: condition 2 fails.** Condition 1 alone is met. Per rubric.md: "A target meeting only one condition, or neither, is graded exactly like any other Mixed-declared skill under the ordinary rule above: the file-level split it declines is not optional for it." So the substitute does not apply, and the target must be graded against the ordinary Mixed rule instead.

**Secondary observation, same evidence.** Step 5 is itself generic to both destinations, yet is placed under the "ProviderX-specific, non-portable" heading — a second, independent symptom of the same over-claiming pattern in the Notes.

## Step 5 — Nine-dimension walk

**1. Discovery.** Pass.

**2. Conciseness.** Not fully assessable.

**3. Degree of freedom.** Pass.

**4. Clarity and structure.** Does not clear cleanly. Step 5 is mislabeled under the "non-portable" heading despite being destination-agnostic. The Notes' "read on every ordinary run... no caller-selectable narrower path" claim is directly contradicted by step 4's own "this step is skipped entirely" clause.

**5. Progressive disclosure.** Given: clears the sequential-pipeline body-cap exemption. Does not clear overall, because the separate Mixed-portability substitute fails condition 2 as shown above, and the target is therefore graded under the ordinary Mixed rule: "Mixed -- dimension 5 (progressive disclosure) requires the actual split, not just the intent to split." As shown, providerx-ship's invocation detail remains written directly inline in SKILL.md's own numbered step 4, not relocated into a dedicated reference file. Named gap: fails the ordinary Mixed split requirement.

**6. Durability.** Named gap: a false claim about a skill's own control flow is exactly the kind of declarative fact-claim that misleads a future vendoring/porting decision.

**7. Bundled scripts.** N/A.

**8. Behavioural evidence.** Unmeasured.

**9. Cross-model robustness.** Unmeasured.

**Confidentiality awareness.** Fires. PROPOSE_CONFIDENTIALITY_SAFEGUARD.

**Compatibility awareness.** NO_COMPATIBILITY_WARNING.

## Step 6 — Verdict

- **Well-formed:** cannot be determined.
- **Headline finding:** none.
- **Mature: No.** Dimension 5 carries a named gap (the substitute doesn't apply; the ordinary Mixed split was declined, not performed), and dimension 6 carries a named gap (a false self-characterization of the skill's own control flow). Two 1-7 gaps block Mature regardless of the well-formed determination.

**Verdict: Well-formed — Indeterminate. Mature — No**, blocked by dimension 5 (Mixed-portability substitute inapplicable; ordinary file-level split not performed) and dimension 6 (Notes contradicts the Procedure's own text about step 4's conditionality).

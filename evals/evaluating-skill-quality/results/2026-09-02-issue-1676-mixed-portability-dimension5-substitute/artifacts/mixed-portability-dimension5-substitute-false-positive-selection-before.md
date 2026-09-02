# Review: `log-shipping-connector` SKILL.md (draft excerpt) — per `evaluating-skill-quality`

**Mode note (read once, before the walk):** Per the task framing this is a bare-mode, single-file simulation — I have `combined.md` (SKILL.md + every `references/*.md` for `evaluating-skill-quality`) and the target excerpt only, no live subagent dispatch, no `scripts/gitapex_check_skill_shape.py` execution, no target `metadata/gitapex.yaml`, no target `references/*.md` content, and the target is explicitly labelled an **excerpt** (not confirmed to be the complete `SKILL.md`). Every gap this causes is named explicitly below rather than silently assumed away.

Per the task's explicit instruction, two findings are taken as **already established, not re-derived**: (1) the cohesion check at Procedure step 2 returned single-outcome sequential cohesion confirmed; (2) dimension 5's own walk already confirmed the cohesion-confirmed sequential-pipeline exemption clears on the reference-file/`BODY_MAX_LINES` axis. Both are folded into the walk below at their normal positions, without re-litigation.

## Precondition (Procedure steps 1 & 3)

**Step 1 (read target).** Read in full: frontmatter, both Procedure sections (portable, steps 1-3; ProviderX-specific/non-portable, steps 4-5), and Notes. `references/batching-rules.md`, `references/retry-policy.md`, `references/delivery-confirmation.md`, and `references/porting-boundary-map.md` are cited but their content was not provided — findings below that would depend on their actual text are named as unverified, not assumed.

**Step 3 (deterministic shape, hand-applied — script unavailable).**
- `description-present`: pass (non-empty).
- `description-no-xml`: pass (no tags).
- `name-pattern`: pass — `log-shipping-connector` is lowercase-hyphenated.
- `name-not-reserved`: pass.
- Forward slashes used throughout.
- Every sidecar-dependent check: not measured — no script, no confirmed-complete body, no sidecar, no reference-file content. Recorded as not-applicable/unmeasured, not as failures.

No shape violation is observed in the checkable subset. This does not by itself license "well-formed."

## Step 2 — Agentic operation mechanism-fit (headline-eligible)

### Whole-artifact: Skill vs. hook — flag, candidate wrong-mechanism finding

Walking the five numbered steps: (1) read local config, (2) apply batching-rules.md's "size/time-window rules," (3) compute a retry/backoff schedule "per its own rules," (4) a fixed binary-or-HTTP-POST branch keyed purely on a config value ("Only when the destination is ProviderX... For any other configured destination..."), (5) record the outcome. Every step is fully deterministic — none asks for judgment, interpretation, or open-ended reasoning. This is the exact shape SKILL.md's own Agentic operation mechanism-fit section warns about: "'Every time X, always do Y' in CLAUDE.md[, or a skill]. If the behavior should happen reliably ... use a hook ... instead." Reported as the review's headline finding per Stop boundaries: resolve why this must be a skill rather than a hook/script before treating any dimension score below as sufficient for shipping.

### Step-level: Skill-step vs. bundled script

Steps 2 and 3 are deterministic, multi-rule, error-prone-for-a-model shape the break-even test names. Step-level finding, not a headline blocker.

### Step-level: Invocation-mode fit

No `disable-model-invocation`/`user-invocable` declared. Effective mode is invocable by both. Step 4's ProviderX path transmits data externally using "ProviderX's own authentication token format" — outward-facing behavior with no stated rationale for leaving it open to autonomous model invocation. Flagged as a step-level finding.

### Whole-artifact: cohesion — as given, not re-derived

Per the task's stated fact: single-outcome sequential cohesion confirmed. No split finding. Taken as established.

### Blind spot pass

No dimension asks whether a data-shipping skill's retry logic is idempotent — a genuine gap named per the Unknowns framework.

## Step 4 — Portability, capability assumption, dependency policy, compatibility, confidentiality

### Portability level — independently established, not taken from the Notes at face value

Reading the Procedure text directly: steps 1-3 and 5 resolve inside the skill's own folder against generic config/reference files; step 4 depends on ProviderX's proprietary binary and auth format. A real mix is exactly Mixed. I confirm Mixed, independently derived from content.

But the Notes' supporting claim does not survive comparison against the Procedure text, exactly as the task warns. The Notes states: "Step 4's `providerx-ship` invocation is ProviderX-specific ... interleaved with the portable steps around it -- there is no caller-selectable narrower path that skips it." Step 4 itself states the opposite: "Only when the destination is ProviderX ... For any other configured destination, this step is skipped entirely and the batch is delivered through the portable Procedure's own generic HTTP-POST fallback instead." This is a direct, citable contradiction within the same document — the destination configuration is a caller-selectable narrower path that skips step 4.

### Dimension 5 (Progressive disclosure) — consuming the Mixed precondition just established

The given, not-re-derived finding clears one specific sub-question: the three mandatory-every-run reference files exceed BODY_MAX_LINES with no rearrangement able to lower that floor, so the cohesion-confirmed sequential-pipeline exemption licenses the multi-file read for the common case. That exemption answers only the file-count/length question. It does not touch the separate rule this precondition step's Mixed classification triggers: "Mixed -- dimension 5 (progressive disclosure) requires the actual split, not just the intent to split: the repository-specific part belongs in a clearly named reference file ... not blended into the portable core" (rubric.md, Portability level). As the task states, this rubric snapshot carries no substitute or exemption that lets a Dimension-5-exempted target off this separate requirement.

Applying it: the vendor-specific detail (the providerx-ship binary name and "ProviderX's own authentication token format") is written inline in SKILL.md's own Procedure, under a heading that itself stays inside SKILL.md ("## Procedure (ProviderX-specific, non-portable)"), not delegated to a dedicated reference file. The one file that is pushed out, references/porting-boundary-map.md, is read "only when vendoring this skill elsewhere" and carries "its portable HTTP-POST substitute," i.e. the portable fallback, not the vendor-specific detail.

**Dimension 5 verdict, stated explicitly: does not clear.** The sequential-pipeline sub-issue is cleared (given, accepted); the Mixed-portability blending sub-issue is not, and independently blocks a clean dimension-5 pass. Fails to clear.

### Capability assumption, dependency policy, compatibility, confidentiality

- **Capability assumption**: no sidecar; graded at the ungraded, no-declaration default.
- **Dependency policy**: not applicable.
- **Compatibility awareness**: NO_COMPATIBILITY_WARNING.
- **Confidentiality awareness**: fires. Application logs routinely carry secrets/PII, and the procedure ships them externally with no stated safeguard. PROPOSE_CONFIDENTIALITY_SAFEGUARD.

## Step 5 — Nine-dimension walk

**1. Discovery.** Pass, with a minor nit — near-restatement between description sentences.

**2. Conciseness.** Pass on the visible text.

**3. Degree of freedom.** Pass. Exact steps, exact reference reads, a binary-branch dispatch.

**4. Clarity and structure.** Does not clear — the Notes section flatly contradicts step 4's own text on whether a caller-selectable narrower path exists. Secondary structural nit: step 5 (destination-independent) is filed under the "ProviderX-specific, non-portable" heading.

**5. Progressive disclosure.** Does not clear, per the analysis above: cleared on the given file-count/BODY_MAX_LINES exemption; fails the separate, still-applicable Mixed-portability blending requirement.

**6. Durability.** Mostly clean on classic bullets, but the Mixed portability Notes-disclosure expectation is undermined by the Notes' factual inaccuracy about step 4's conditionality — this dimension does not cleanly clear either pending that fix.

**7. Bundled scripts.** Not applicable.

**8. Behavioural evidence.** Unmeasured.

**9. Cross-model robustness.** Unmeasured, qualitative read only.

## Step 6 — Verdict

**Agentic operation mechanism-fit:** headline concern raised, not resolved — this procedure's every step is deterministic, matching the rubric's own "should have been a hook" anti-pattern.

**Well-formed:** not fully determinable in this bare-mode run; no violation found in the hand-checkable subset.

**Mature: no.** Dimensions 4 and 5 both carry named, uncleared gaps (Notes/Procedure self-contradiction; Mixed-portability content blended into the portable core rather than split), which alone blocks Mature. Cohesion (given) and the dimension-5 file-count sub-issue (given) are not what's holding this below Mature; the independent Mixed-blending finding and the Notes/Procedure contradiction are.

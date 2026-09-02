# Review: `vault-secret-rotation` (draft SKILL.md excerpt)

*Produced per `evaluating-skill-quality`'s own Procedure. Operating-constraint disclosure, required by that skill's own Stop boundaries ("never silently skip"): this is a bare-mode, zero-further-tool-access run. I could not run `scripts/gitapex_check_skill_shape.py` or `gitapex_scan_execution_requirements_drift.py` (Procedure step 3), could not open a `metadata/gitapex.yaml` sidecar (none was provided), could not dispatch the isolated subagent Subagent dispatch calls for, and I have only the pasted excerpt, not the full `SKILL.md`/`references/` tree. Every finding below is scoped to what the excerpt actually shows; where the constraint matters to a specific check I say so at that check rather than silently proceeding as if I had full access.*

## Reused, not re-derived

Per the task's own instruction and Contract discipline's "never both" rule, two findings are taken as already-established and are **not** re-walked here:

- **Cohesion** (mechanism-fit's cohesion check, rubric.md's "Skill vs. multiple skills / cohesion"): single-outcome sequential cohesion confirmed — five steps converging on one outcome, each step's output the next step's required input, no caller-selectable narrower path. I checked this claim only for *internal consistency* with the rest of the excerpt (step 4 consumes step 3's output; step 5 consumes step 4's output; nothing branches) — consistent, but the grant itself is reused, not re-run.
- **Dimension 5's cohesion-confirmed sequential-pipeline exemption** (rubric.md, Portability level → Mixed bullet's nested exemption, condition 1): already granted — three mandatory reference files, 690 combined lines, over `BODY_MAX_LINES` (500), each genuinely load-bearing with no dimension-2 cut and no rearrangement lowering the floor. Reused verbatim.

What follows is everything the task actually asked me to do independently: verify the *new* Mixed-portability substitute's two gating conditions against the excerpt text, grade its three positive requirements, and complete the rest of the walk the rubric requires around it.

## Step 2 — Agentic operation mechanism-fit

**Whole-artifact.** No wrong-mechanism finding. This is a runbook a human plausibly wants to see play out step-by-step, especially on the "emergency" branch of its own trigger ("Use a skill when you want the procedure to play out inside the main thread so you can see and steer each step" — [steering]-derived rule in rubric.md). Skill vs. CLAUDE.md: this is a multi-step procedure, not a static fact — correctly a skill. Cohesion: reused above, no split finding.

**Step-level findings (triage, not headline):**

1. **Skill-step vs. bundled script — steps 1-3.** The break-even test: "Delegate when the step is deterministic AND at least one of: repeated/looped; multi-rule or non-trivial; error-prone for a model... or it must emit a machine-checkable artifact." Step 2 ("compute each credential's own new value per its rotation policy") is deterministic, applied once per credential in a potentially multi-credential enumeration (repeated/looped), against a 260-line policy document (multi-rule/non-trivial), almost certainly involving exact-format constraints (length, character class) that are error-prone for a model to apply consistently in-head. Step 3's registry lookup is the same shape against 230 lines. Worth triaging as a scripting candidate; not a mandate, since I cannot see whether genuine cross-credential-type judgment is required.

2. **Tool-capability verification — step 4's `--auto-rollback` claim.** The excerpt states, unhedged: *"the binary's own `--auto-rollback` flag atomically reverts to the prior value, internally, if any dependent service fails to acknowledge within VaultCo's own webhook timeout, so no separate conditional rollback step exists in this Procedure."* `vaultco-cli` is described as *"a VaultCo-only binary, present only in this organization's own deployment"* — proprietary, with no schema or docs reachable from this review. Per rubric.md: *"When the named tool is internal, unpublished, or otherwise has no schema or docs reachable from this review, say that explicitly rather than guessing at the claim's truth either way."* This is a live-safety claim (it's the entire reason the Procedure has no separate rollback step) asserted as flat fact about an unverifiable binary. **Fail** on the letter of this check: it needs to be hedged ("confirm this against the current `vaultco-cli` release before relying on it") or independently verified, not stated as settled.

3. **Invocation-mode fit — unguarded side effects.** No `disable-model-invocation` field is shown. Rubric.md's Fail case: *"The target's procedure performs outward-facing or irreversible work... yet the skill stays model-invocable with no stated reason... 'You don't want Claude deciding to deploy because your code looks ready.'"* Step 4 writes a live credential into a production secrets vault and fires a webhook to production dependent services, unconditionally, on a skill whose own description reads as an automatic-fire trigger ("Use when a scheduled or emergency credential rotation is due"). This is at least as consequential as the source's own `/deploy` example. **Fail** — propose `disable-model-invocation: true`, or an explicit stated justification for leaving it open, neither of which the excerpt shows.

**Blind spot pass (Unknowns framework).** A genuine gap, not folded into an existing dimension: dimension 7's plan→validate→execute discipline for high-stakes work is explicitly gated *"only if the skill ships code."* `vault-secret-rotation`'s actual high-stakes write is delegated to an external, non-bundled binary (`vaultco-cli`), so that discipline never fires for it at all — a skill can perform an equally irreversible-ish production write as a bundled script would, yet the rubric has no check asking whether an *externally*-delegated high-stakes action gets the same plan/validate/verify treatment dimension 7 would demand of a bundled one. Named per the rubric's own instruction, not improvised into a tenth dimension.

## Step 3 — Deterministic shape

Not run (see constraints above). By inspection only: body far under the given 500-line cap; description ≈230 chars, no obvious length issue; paths use forward slashes; no bare or qualified issue/PR citations anywhere in the excerpt. Nothing visibly fails, but this is **not** a verified "Well-formed" pass — no sidecar was available to check `portability-declared`, `capability-assumption-declared`, or `dependency-policy-declared`, and the actual checker never ran.

## Step 4 — Portability / Capability / Dependency

**Portability: Mixed**, established from content (Notes section states it explicitly, correctly placed in a footer `## Notes`, per rubric.md's convention). Capability assumption and dependency policy are not observable — no sidecar shown, no bundled `scripts/` shown (dependency policy is not-applicable regardless, since `vaultco-cli` is an org-installed external binary, not a bundled script). Per Procedure step 4's own missing-sidecar rule, this is noted as context, not a finding.

## Step 5 — Nine dimensions

### 1. Discovery
`vault-secret-rotation` — specific, not generic. Description states both what ("Rotate every credential due for rotation... propagate each new value to its dependent services") and when ("Use when a scheduled or emergency credential rotation is due"), with concrete key terms (vault, credential, dependent services). **Clears.**

### 2. Conciseness
Step 4's rationale and the Notes' portability declaration both assert "only step 4 is VaultCo-specific, invoked unconditionally every run" — checked deliberately against the dimension-2 "same disclosure restated at 2+ sites is duplication" rule. These serve two distinct, both-required purposes (step 4's own design rationale vs. the Mixed substitute's mandatory Notes declaration, requirement 2 below), so this is not the wasteful restatement that rule targets. No sprawl (no branches to pay unselected-route cost on, per the reused cohesion finding). **Clears**, with that check shown as run rather than skipped.

### 3. Degree of freedom
Step 4 (fragile, live-system write) is pinned to one exact command with fixed flags — the rubric's own Pass example shape. Steps 2-3 are appropriately medium-freedom (policy/registry-driven, not open prose). **Clears.**

### 4. Clarity and structure — **named gap**
Two findings:

- **Missing feedback loop.** Step 5 only *"records this rotation's own outcome... closing the reconciliation"* — there is no escalation, retry, or alert path named for the auto-rollback (failure) outcome. Per rubric.md: *"Feedback loops on quality-critical steps -- validate -> fix -> repeat... on any step where errors are likely and costly. Its absence there is a gap."* A rolled-back, still-stale credential with no stated next action is exactly that gap.
- **Internal inconsistency in step 4's own self-characterization.** Step 4 both says it calls `vaultco-cli rotate --id <credential>` — a singular, per-credential flag — *"to write each new credential value"* (plural, i.e. every due credential from step 1), and separately asserts it *"is invoked exactly once, unconditionally, every run."* Taken literally these conflict: a per-credential `--id` flag implies one invocation per due credential (potentially many per run), not one invocation total. This is exactly the kind of self-characterization the task asked me not to accept at face value — I flag it as a **dimension-4 clarity defect**, though (see below) it does not defeat the Mixed-portability substitute's condition 2, since under either reading the call is still unconditional and still happens every ordinary run.

Dimension 4 does **not** clear cleanly.

### 5. Progressive disclosure — this is the crux of the review

**Independent verification of the Mixed-portability substitute's two gating conditions**, per rubric.md's Portability level → Mixed bullet's nested exemption:

- **Condition 1** (dimension 5's own cohesion-confirmed exemption already granted): reused per the task's instruction, not re-derived here.
- **Condition 2** (non-portable content demonstrably read on every ordinary run, established by inspecting steps, never accepted from self-characterization): **independently checked, not assumed.**
  - Steps 1-3 ("Enumerate every credential...", "Read `references/rotation-policy.md`...", "Read `references/dependent-service-registry.md`...") contain no reference to `vaultco-cli`.
  - Step 5 explicitly disclaims it: *"This step reads only the outcome step 4 already produced and never itself calls `vaultco-cli`."*
  - Step 4 is the sole touchpoint. There is no visible `if`/`when` gating it in the Procedure — it sits in the fixed five-step chain the reused cohesion finding already established has "no caller-selectable narrower path." Despite the "exactly once vs. per-credential" ambiguity named under dimension 4 above, under **either** reading the call is unconditional and occurs on every ordinary run for every due credential — no reading of the text makes it sometimes-skipped.
  - **Condition 2 holds**, verified from the procedure structure itself, not from the target's own "unconditionally, every run" assertion taken on faith.

Both gating conditions hold. Now grading the **three positive requirements** against the actual text, in place of ordinary file-level relocation:

1. **Distinct headings, no sentence-level blending.** `## Procedure (portable)` (steps 1-3), `## Procedure (VaultCo-specific, non-portable)` (step 4 alone), `## Procedure (portable, continued)` (step 5). Step 4's only cross-reference to portable content is consuming step 3's output ("dependent services identified in step 3") — an ordinary sequential-pipeline dependency, not a blended sentence. **Pass.**
2. **Notes declaration naming which steps read non-portable content, and each one's own portable fallback.** The Notes section names step 4 explicitly ("Step 4's own `vaultco-cli` invocation and webhook mechanism -- and only step 4's -- is VaultCo-specific") and states the fallback's shape: *"a copy of this skill vendored outside a VaultCo deployment would need to replace step 4's own single call with that deployment's own credential-write mechanism."* This is a defensible **Pass** on the letter of the requirement — it names the step and the class of substitute; it does not need to duplicate the concrete substitute mapping, since that is requirement 3's job. (Minor, non-blocking editorial note: "that deployment's own credential-write mechanism" is generic enough that one worked example, e.g. a Vault API write or a cloud secrets-manager `PutSecretValue` call, would sharpen it — not a Fail, a polish suggestion.)
3. **One dedicated, non-every-use reference file enumerating the touchpoint and its substitute, read only at vendoring time.** *"See `references/porting-boundary-map.md` (read only when vendoring this skill elsewhere, never on an ordinary run) for that one touchpoint and its portable substitute."* Matches the requirement's shape exactly, and — correctly — this file is a *fourth*, non-mandatory file, kept separate from the three every-use files whose 690-line combined total drove the dimension-5 exemption; nothing here inflates or contaminates that already-established floor. **Pass.**

All three requirements pass on direct textual verification; both gating conditions independently hold. **The Mixed-portability substitute is correctly invoked and correctly satisfied here** — this is a genuine pass, not a rubber-stamp, and it is the one part of this excerpt that stands up cleanly under adversarial scrutiny.

Standard dimension-5 checks (independent of the exemption): reference files are content-named, and each is pointed to at its exact branch point with a stated reason (step 2 → rotation-policy.md "to compute each credential's own new value"; step 3 → dependent-service-registry.md "to identify every service that depends"). **Dimension 5 clears.**

### 6. Durability
No time-bound content, no bare/qualified issue citations, forward slashes throughout. The portable core (steps 1-3, 5) makes no declarative fact-claim tied to VaultCo that would go false once copied elsewhere. **State-management sub-check: not applicable** — recorded explicitly, per the required discipline, rather than silently skipped: no fan-out with a consuming successor, no re-entry across turns/compaction/sessions, and step 5's audit-trail write is the procedure's terminal output, never read back by a later step of *this* procedure to decide what to do next. **Clears.**

### 7. Bundled scripts
**Not applicable** — no `scripts/` directory shown; `vaultco-cli` is an external, pre-installed organizational binary, not something this skill bundles.

### 8. Behavioural evidence
**Unmeasured.** No eval mechanism, fixture set, or baseline is visible in the excerpt, and — being a single-file, bare-mode review of a draft excerpt rather than the full skill directory — I cannot even determine whether the real directory is "ablation-capable, not yet run" or has no such mechanism at all. Named as unmeasured, with that further uncertainty disclosed rather than guessed at.

### 9. Cross-model robustness
**Unmeasured**, qualitative read only: step 4 is a fixed low-freedom policy (single exact command), plausibly low over-prescription risk for a strong tier; step 2's 260-line policy interpretation is the part most likely to need more explicit scaffolding for a weak tier, but I cannot confirm whether `rotation-policy.md` itself already supplies that (not in the excerpt). Labeled as a read, not measured evidence.

## Compatibility and Confidentiality awareness (warning-only, never change the verdict)

- **Compatibility awareness:** `NO_COMPATIBILITY_WARNING` based on the frontmatter shown (`name`, `description` only) — noting the excerpt may omit fields present in the real file, which I cannot see.
- **Confidentiality awareness:** fires — this procedure's whole purpose is handling credentials (step 2 computes new secret values; step 4 writes them; step 5 logs the outcome). No safeguard is stated anywhere in the excerpt (no "never log the raw new value," no "audit trail records status/identifier only"). `PROPOSE_CONFIDENTIALITY_SAFEGUARD`, provisional — `references/rollback-procedure.md`'s actual "generic audit-trail rules" were not shown to me and might already state one; the excerpt itself does not. Proposed concrete sentence: step 5's audit-trail record should state explicitly that it records rotation/auto-rollback status and credential identifier only, never the plaintext new-credential value.

## Verdict

**Agentic operation mechanism-fit:** no whole-artifact finding (cohesion reused; correctly a skill). Three step-level findings for triage: skill-step-vs-script (steps 1-3), tool-capability-verification (step 4's `--auto-rollback` claim, unhedged against an unverifiable proprietary tool), invocation-mode-fit (unguarded side effects on a live-vault write).

**Dimension 5 / Mixed-portability substitute: independently verified pass** — both gating conditions confirmed from the procedure structure itself, all three positive requirements confirmed against the actual text, not accepted on the target's own say-so.

**Shape check:** not independently run — provisionally consistent by inspection, not verified.

**Dimensions:** 1 clears, 2 clears, 3 clears, **4 does not clear** (missing feedback loop for the auto-rollback outcome; an internal "exactly once" vs. per-credential-flag inconsistency), 5 clears, 6 clears, 7 N/A, 8 unmeasured, 9 unmeasured.

Per rubric.md's Verdicts section, a Mature verdict requires every dimension 1-7 to clear with no named gap; dimension 4 has one. **This skill is not yet Mature.** Well-formed status is unconfirmed rather than failed, given the shape checker could not be run. The Mixed-portability substitute itself is not the blocker — it is the one thing here that holds up cleanly under independent scrutiny; the real gaps are dimension 4's feedback-loop/clarity issues and the three step-level mechanism-fit findings above.

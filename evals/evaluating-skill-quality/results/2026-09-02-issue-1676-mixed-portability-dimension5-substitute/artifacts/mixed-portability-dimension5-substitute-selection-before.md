# Review: `vault-secret-rotation` (evaluating-skill-quality applied)

## Scope and run-mode caveats (stated up front, per Contract discipline)

This is a bare-mode, zero-further-tool-access run reviewing a **draft excerpt**, not a full skill directory. Before walking the Procedure I record what this run cannot do, rather than silently filling the gaps:

- **Procedure step 3 (deterministic shape checker)** cannot be executed — no script/file-system access to `gitapex_check_skill_shape.py`, and the excerpt gives no full frontmatter/line counts to hand-apply its rules against. Reported as **shape-check status: unavailable in this run**, not fabricated as PASS or FAIL.
- **Subagent dispatch / isolation verification** (`SKILL.md`'s Subagent dispatch section, `adversarial-self-audit.md`'s Isolation verification) cannot actually be performed — there is no dispatch mechanism available in this simulation. Noted as a limitation, not silently assumed clean.
- No `metadata/gitapex.yaml` sidecar was given. Per rubric.md's Capability assumption / Procedure step 4: *"When the target has no sidecar … establish portability and capability assumption by reading the target's content instead … and note the sidecar's absence as context, not as a finding."* Done below.
- Given, not re-derived (per task instructions): the **cohesion finding** (single-outcome sequential cohesion) and the **dimension-5 sequential-pipeline exemption** for the three mandatory reference files. Both are treated as established facts from here on.

## Step 1 — Read

Target read in full as given: frontmatter (`name`, `description`), a five-step Procedure split across three headed subsections, a `## Notes` section declaring portability, and the full content of `references/porting-boundary-map.md`. No other `references/*.md` content (e.g. `rotation-policy.md`) was supplied, so any claim about *their* content is explicitly unverifiable and not asserted.

## Step 2 — Agentic operation mechanism-fit

**Whole-artifact wrong-mechanism check:** nothing in the excerpt suggests this should have been a hook, subagent, or CLAUDE.md content — it is a multi-step judgment+external-call procedure, appropriate for a skill. No finding.

**Cohesion (Skill vs. multiple skills):** per the task's own preamble, already confirmed at this step as single-outcome sequential cohesion converging on *"every credential due for rotation is rotated in the vault and every dependent service is updated to the new value, with no service left holding a stale credential."* Not re-derived here.

**Step-level checks:**

- **Invocation-mode fit — Fail, unguarded side effects (step-level).** No `disable-model-invocation` or `user-invocable` field appears anywhere in the given frontmatter, so the effective mode is the default: invocable by both. The procedure's outward-facing/irreversible action is exactly the shape rubric.md names. Rotating every due credential across an org's vault and pushing new values to every dependent service is materially the same blast-radius class as `/deploy`. Auto-rollback on webhook-timeout mitigates the *failure* case but does not remove the outward-facing write itself. No justification for open model-invocation is stated anywhere in the excerpt. **Propose:** `disable-model-invocation: true`, or an explicit stated reason for leaving it open.

- **Model/effort tier fit, Subagent delegation scope, Tool-capability verification:** not applicable — no model/effort pin, no subagent-dispatch instruction, and `vaultco-cli` is an externally-invoked CLI, not a harness-surfaced tool/MCP subcall with a schema this check is scoped to. Noting by reasoned analogy, not as this check's literal Fail: the claim that `--auto-rollback` *"atomically reverts to the prior value, internally, if any dependent service fails to acknowledge"* is asserted as flat fact about a third-party binary's behavior with no citation to VaultCo's own docs — worth a hedge on the same principle even though the check's stated applicability trigger doesn't literally cover it.

- **Skill-step vs. bundled script — candidate, unconfirmed.** Step 2's *"compute each credential's own new value per its rotation policy"* is exactly the shape this check flags as a delegation candidate. If `rotation-policy.md`'s rules are mechanical this is a real candidate; its content was not supplied, so this is flagged as **worth checking against that file**, not a confirmed Fail.

**Blind spot pass:** naming a gap, not folding it into an existing dimension. None of the nine dimensions, mechanism-fit, or portability asks whether the procedure verifies that each dependent service's *own* credential store actually converged on the new value, as opposed to merely acknowledging VaultCo's webhook — webhook ack and actual downstream consistency are different facts.

## Step 3 — Deterministic shape

Not run (see Scope caveats). Reported as **unavailable**, not PASS/FAIL.

## Step 4 — Portability / Capability / Dependency preconditions; Compatibility & Confidentiality

**Portability — read as Mixed** (declared directly in `## Notes`: *"Portability: **Mixed**."*), consistent with `SKILL.md`'s own three-level definition: *"Mixed: a portable core plus repo-specific detail should split the two into a clearly named reference file, not blend them."* Graded in full below (dimension 5 is where this gets checked).

**Capability assumption — undeclared / not established** from the given excerpt (no sidecar, no stated Broad/Frontier/Adaptive). Per rubric.md dimension 2's own rule, this means dimensions 2/3/5/9 grade at *"the ungraded, no-declaration default — equivalent to Frontier-level strictness."* Applied throughout step 5.

**Dependency policy:** not applicable — no `scripts/` shown.

**Declaration-vs-pin consistency:** no pin exists (step 2 found none), so no contradiction to check.

**Compatibility awareness — `NO_COMPATIBILITY_WARNING`.** The given frontmatter carries only `name`/`description`; no runtime-specific field is present in what was supplied, so no runtime-specific dependency is established from this excerpt.

**Confidentiality awareness — `PROPOSE_CONFIDENTIALITY_SAFEGUARD`.** Applicability is squarely met — this skill's entire procedure is credential handling: enumerating credentials, computing new values, writing them, and recording rotation outcomes. No step in the excerpt states any safeguard. **Proposed fix**, targeting step 5 specifically: state explicitly that the audit trail records the credential's identifier and outcome status only, and must never write the new credential value itself.

## Step 5 — Nine dimensions

**1. Discovery.** `description` states both what and when in concrete, vault/credential-specific terms unlikely to collide with an unrelated sibling. `name` reads as a noun phrase, acceptable per rubric. Grading the trigger against the invocation mode established at step 2 (invocable by both, no dead-trigger issue): trigger is reachable. **Clears** — the separate unguarded-side-effects concern is Agentic-operation-mechanism-fit's finding, not re-counted here, per Contract discipline's "never both."

**2. Conciseness.** Body is compact and domain-specific; no re-teaching of well-known concepts, evaluated at the ungraded Frontier-equivalent default established at step 4. One soft finding: the Notes-section restatement of "step 4 alone is VaultCo-specific and runs unconditionally every run" duplicates content already asserted inside step 4 itself. This is a defensible split (operational instruction vs. portability rationale), so I flag it as a **minor** duplication candidate rather than a hard Fail.

**3. Degree of freedom.** Step 4 is pinned to an exact, single, unconditional command for a fragile, irreversible-adjacent operation — correct match per rubric.md's fragility test. Steps 1–3/5 are medium-freedom, driven by mandatory reference-file policy rather than open prose. **Clears.**

**4. Clarity and structure.** Single linear pipeline (consistent with the given cohesion finding), consistent terminology (credential / rotation / dependent service throughout), each step names an observable completion result. No competing branch triggers to disambiguate, consistent with confirmed sequential cohesion. **Clears** on what's shown.

**5. Progressive disclosure — does not clear.** This is the central finding, and the one the task's framing is testing directly.

The excerpt correctly applies, and explicitly invokes, the given dimension-5 sequential-pipeline exemption for the three mandatory reference files' combined 690 lines. That exemption is scoped narrowly, in its own text, to exactly one question: reference-file line count. Both conditions are satisfied for the three reference files, and I am not re-deriving or contesting that — it was given. But this exemption is about whether mandatory reference-file line count may exceed the body cap; nothing in its text touches the separate, ordinary Mixed-portability rule, stated plainly in `SKILL.md`: *"Mixed: a portable core plus repo-specific detail should split the two into a clearly named reference file, not blend them."*

Applying that rule to the actual artifact: step 4's full operational content — the exact `vaultco-cli rotate --id <credential> --auto-rollback` invocation, its webhook-propagation mechanism, and its auto-rollback semantics — is **not** in a reference file. It lives directly inside `SKILL.md`'s own body, under `## Procedure (VaultCo-specific, non-portable)`, sandwiched between `## Procedure (portable)` and `## Procedure (portable, continued)` — the same file, read on every ordinary run. The one reference file that names this touchpoint, `references/porting-boundary-map.md`, is explicitly excluded from the ordinary-run path by its own text: *"Read only when vendoring vault-secret-rotation outside a VaultCo deployment -- never on an ordinary run."*

So on the path every real invocation actually takes, 100% of the non-portable operational content is read from `SKILL.md` itself; nothing defers to a reference file for that content. That is the textbook shape of *blend*, not *split* — the exact defect the Mixed rule exists to catch, and the dimension-5 Fail example names it directly.

Note what that Fail bullet's own scope is: it fails a *misuse of the sequential-pipeline exemption itself*. It says nothing about, and grants no separate exemption for, leaving Mixed-declared non-portable content unsplit. As the task states, and as I confirm from the file actually read: no Mixed-portability substitute for a dimension-5-exempted target exists anywhere in this version of the rubric. Extending the confirmed exemption to also excuse the unrelated Mixed-split requirement would be inventing a rule the file does not contain — exactly what I am not doing here.

This is graded once, under dimension 5, per Contract discipline's "never both."

**Concrete remediation:** move step 4's operational detail into a new mandatory-every-run reference file (e.g. `references/vaultco-rotation-command.md`), leaving `SKILL.md` step 4 as a short portable pointer.

**6. Durability.** Forward slashes throughout, no bare issue/PR citations, no time-sensitive content, no MCP tool citations to check. The Mixed-split issue is dimension 5's alone (see above); not re-raised here. **Clears** on the criteria dimension 6 itself owns.

**7. Bundled scripts.** Not applicable — no `scripts/` shown in the excerpt.

**8. Behavioural evidence.** Cannot check the target repository for an eval mechanism in this bare-mode, zero-further-tool-access run. Stated explicitly as **unmeasured**, not assumed either way.

**9. Cross-model robustness.** Unmeasured for the same reason. Qualitative read only, labeled as a read, not evidence.

## Step 6 — Verdict

- **Well-formed:** cannot be confirmed — shape checker unavailable in this run (see Scope caveats). Not fabricated as PASS or FAIL.
- **Mature: does not clear.** Per rubric.md's Verdicts section, *"Mature -- well-formed, and every dimension 1-7 clears cleanly with no named gap."* Dimension 5 carries a named gap (Mixed-portability content blended into `SKILL.md` rather than split into a reference file, per the analysis above) that is independent of, and not covered by, the given dimension-5 sequential-pipeline exemption. That alone blocks Mature regardless of well-formedness. Dimensions 8–9 are separately unmeasured (permitted for those two specifically, per the same section).
- Step-level findings reported for triage, not blocking on their own: Invocation-mode-fit (unguarded side effects — propose `disable-model-invocation: true` or a stated reason), a candidate Skill-step-vs-bundled-script check on step 2's value-computation (unconfirmed, `rotation-policy.md` not supplied), and a minor dimension-2 duplication note.
- Warning-only axes (do not affect the verdict): Compatibility awareness — `NO_COMPATIBILITY_WARNING`; Confidentiality awareness — `PROPOSE_CONFIDENTIALITY_SAFEGUARD`.
- Blind spot: named above (webhook-ack vs. actual dependent-service consistency verification) — not folded into an existing dimension.

```json
{
  "target": "vault-secret-rotation (excerpt)",
  "well_formed": "unverifiable_in_this_run",
  "mature": false,
  "headline_finding": null,
  "cohesion": "given_not_rederived: single-outcome sequential, confirmed",
  "dimension5_body_cap_exemption": "given_not_rederived: applies to the three mandatory reference files only",
  "dimensions": {
    "1_discovery": "clear",
    "2_conciseness": "clear_minor_note",
    "3_degree_of_freedom": "clear",
    "4_clarity_structure": "clear",
    "5_progressive_disclosure": "fail",
    "6_durability": "clear",
    "7_bundled_scripts": "not_applicable",
    "8_behavioural_evidence": "unmeasured",
    "9_cross_model_robustness": "unmeasured"
  },
  "dimension5_fail_reason": "Mixed-declared non-portable content (step 4) is read and executed directly from SKILL.md's own body on every ordinary run, not split into a reference file; references/porting-boundary-map.md is explicitly excluded from the ordinary-run path. The given dimension-5 sequential-pipeline exemption governs only the three mandatory reference files' combined line count and grants no license for this separate, ordinary Mixed-portability split requirement.",
  "step_level_findings": [
    "invocation_mode_fit: unguarded_side_effects",
    "skill_step_vs_bundled_script: candidate_unconfirmed (step 2 value computation)",
    "conciseness: minor_duplication_candidate (Notes vs. step 4)"
  ],
  "compatibility_awareness": "NO_COMPATIBILITY_WARNING",
  "confidentiality_awareness": "PROPOSE_CONFIDENTIALITY_SAFEGUARD",
  "blind_spot": "no dimension checks whether dependent-service webhook acknowledgment implies actual downstream credential-store convergence",
  "shape_check": "not_run_in_this_environment",
  "note": "output-schema.json was not included among the concatenated .md reference files read for this run, so this block is a best-effort structured summary, not validated against that schema."
}
```

**5. Progressive disclosure.** Two sub-findings:

*(a) Sequential-pipeline exemption — given, cleared.* Reused verbatim per the task's stipulation; not re-derived.

*(b) Mixed-portability substitute — independently checked, fails.* The rubric's substitute text requires both: "(1) this same dimension-5 walk has already granted the target the cohesion-confirmed sequential-pipeline exemption immediately above ... and (2) the non-portable content is demonstrably reached and acted on, not merely read as inert text, on every ordinary origin-environment run, established by inspecting which procedure steps actually execute it, never accepted from the target's own 'every-use'/'interleaved' self-characterization -- a step whose own action is itself conditional (skipped on some runs, gated on a runtime value) fails this condition even when its surrounding prose is read every time."

Condition (1) is satisfied (given). Condition (2) is not: the target's own Procedure step 4 reads, verbatim, "Only when the destination is ProviderX (this deployment's own default, but not its only configured destination), call ProviderX's proprietary providerx-ship binary to deliver the batch, using ProviderX's own authentication token format. For any other configured destination, this step is skipped entirely and the batch is delivered through the portable Procedure's own generic HTTP-POST fallback instead." That is a step whose own action is explicitly gated on a runtime value (the deployment's configured destination) and explicitly skipped on some runs -- the textbook fail case the rubric names. The Notes section's countervailing claim is exactly the "every-use"/"interleaved" self-characterization the rubric instructs must "never [be] accepted."

Because only condition (1) is met, the rubric routes this target back to the ordinary Mixed rule. Checking that rule against the actual content: the ProviderX-specific instructions sit inline inside step 4 of the main numbered Procedure section of SKILL.md itself -- not isolated in a dedicated reference file.

This matches dimension 5's own Fail bullet directly: "a Mixed-declared target claiming the Mixed-portability substitute above whose non-portable step is in fact conditional rather than executed every run (failing that substitute's own condition 2)."

**Dimension 5 does not clear.**

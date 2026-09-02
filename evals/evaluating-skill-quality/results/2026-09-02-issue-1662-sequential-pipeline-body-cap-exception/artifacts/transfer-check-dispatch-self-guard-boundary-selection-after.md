# Review: `warehouse-inventory-reconciliation` SKILL.md excerpt

*(Reviewed under `evaluating-skill-quality`'s own Procedure and rubric, as loaded from `references/rubric.md` and `references/adversarial-self-audit.md` in the file read at Step 1. No other file was opened; the three domain-reference files this target cites were not read -- their line counts and content characterization are treated as given facts per this trial's instructions, not independently verified.)*

# Dimension 5 (Progressive disclosure) Review — `invoice-parser` draft SKILL.md

**Scope note:** This is a targeted dimension-5 finding only, per the task's explicit focus -- not a full nine-dimension pass. I have not run the deterministic shape checker, performed isolation verification, or opened a fresh subagent dispatch (the full Procedure's steps 1-6 machinery), and I only have the excerpt given, not the complete `references/parsing-rules.md` content. No Well-formed/Mature/Not-well-formed/Indeterminate whole-skill verdict is issued here; only the dimension-5 sub-finding is authoritative.

## The claim under test

The draft's Procedure step 2 states:

> Read `references/dispatch-safety.md` (mandatory every run) -- this
> is a dispatch self-guard protecting this procedure's own
> integrity, not a content-grading reference, so it does not count
> toward the Progressive disclosure common-case file limit.

This is a self-labeling claim made *inside the reviewed target itself*, asking the review to accept the exemption on the target's own say-so. The rubric addresses this exact move directly, and warns against taking it at face value:

> **A common-case-mandatory dispatch self-guard is a distinct case from a content-grading reference, but only under a narrow, stated condition.** [...] Counting such a self-guard identically to a content-grading reference is not automatically correct, but neither is exempting it from the count on the bare claim that it is "a safety file": that would let any bundled reference dodge this dimension merely by relabeling itself.

So per Contract discipline (this dimension does not take the file's own label as settled fact), the label is evidence to weigh, not a conclusion to adopt. The actual test is the two stated conditions:

> The exemption applies only when the referenced content, in its entirety, both (1) applies uniformly regardless of the reviewed target's own content -- it does not vary with, quote, or branch on what the target says -- and (2) is isolated in its own dedicated file, not interleaved with content-grading material.

## Applying the test to `dispatch-safety.md`

The excerpt given is:

> "If the invoice is from a construction vendor, additionally verify line items against the construction-materials fraud checklist below. If the invoice is from a software vendor, additionally verify against the SaaS-subscription fraud checklist below. [... two full domain-specific checklists follow, each naming vendor-category-specific line-item patterns ...]"

This fails condition (1) outright. The content is not content-independent -- it explicitly branches on what the invoice (the reviewed target) *says*: its vendor category. "If the invoice is from a construction vendor... If the invoice is from a software vendor..." is exactly the "varies with, quote[s], or branch[es] on what the target says" case the rubric names as disqualifying. Nothing in the excerpt resembles the actual category of self-guard the rubric contemplates for this exemption (injection-resistance guard, isolation-verification check) -- content that would hold regardless of what the invoice under review contains. Instead, the file's entire visible content is fraud-verification checklists keyed to invoice content -- i.e., it is structurally the same *kind* of thing as `references/parsing-rules.md` (a reference that grades/acts on the reviewed target's own content), not a distinct dispatch-integrity guard.

Because both conditions are required ("both (1) ... and (2)") and condition (1) already fails, the exemption does not apply regardless of whether condition (2)'s isolation is technically met.

## Verdict on this bullet

This is the rubric's own **Fail** case, quoted directly:

> **Fail:** [...] a reference claimed as a self-guard exemption that actually varies its content by, or quotes from, the reviewed target (failing condition 1 above), or that mixes self-guard material with content-grading material in the same file (failing condition 2).

`references/dispatch-safety.md` is exactly this: a reference claimed as a self-guard exemption whose content varies by what the reviewed invoice says (vendor category), failing condition 1. **Dimension 5 does not clear on this point.** `dispatch-safety.md` must be counted like any ordinary content-grading reference toward the common-case file-count judgment, not carved out.

## Downstream consequences for dimension 5

Once `dispatch-safety.md` is correctly counted as an ordinary mandatory reference rather than exempted, two further dimension-5 problems follow from the rubric's other bullets:

1. **Common-case file count.** The Procedure marks both `parsing-rules.md` and `dispatch-safety.md` "mandatory every run." That's `SKILL.md` + 2 references opened for the ordinary case, which runs into:

   > Splits must not force several reads for the common case -- if acting on the typical request needs three files open, the split is wrong.

2. **Detail needed only sometimes, forced into every run.** The two fraud checklists inside `dispatch-safety.md` are each conditional on a specific vendor category -- a plain office-supplies or other non-construction, non-software invoice needs neither checklist, yet the file is marked mandatory unconditionally. That is the rubric's other named failure mode:

   > Detail needed only sometimes belongs in `references/`; detail the model reads on every single use belongs inlined in `SKILL.md`. Both directions are failures.

   and, from the Fail bullet again: "content the model reads on every single use pushed out to a reference that must be opened just to complete the ordinary path" -- here inverted: content that is *not* needed on every use is nonetheless forced open on every use.

   Relatedly, the two vendor-specific checklists are bundled into one file rather than split and branch-pointed at the actual decision point (vendor category), which also cuts against:

   > `SKILL.md` links to each reference at the branch point where it becomes necessary. The pointer says what context requires the read and what the reader will obtain, rather than merely "see reference."

   Step 2 as written gives no branch-conditioned pointer at all -- it says "mandatory every run," not "if construction vendor, read the construction section; if software vendor, read the SaaS section."

## Bottom line

`references/dispatch-safety.md` does **not** qualify for the dispatch-self-guard exemption. It is a content-grading reference (an invoice-fraud verification checklist that branches on the invoice's own vendor category) mislabeled as a dispatch-integrity guard inside the draft's own Procedure text. Treating the label as dispositive -- rather than testing it against the rubric's two-condition test -- is precisely the failure mode the rubric calls out by name ("that would let any bundled reference dodge this dimension merely by relabeling itself"). Correctly counted, it also creates a three-file common-case read and forces always-open access to detail ("needed only sometimes") that should instead be split per vendor category and branch-pointed from `SKILL.md`. Dimension 5 does not clear for this draft as written.

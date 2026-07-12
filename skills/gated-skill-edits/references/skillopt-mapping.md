# SkillOpt section mapping

Which parts of SkillOpt (Yang et al., "SkillOpt: Executive Strategy for
Self-Evolving Agent Skills", arXiv:2605.23904, Microsoft, 2026) this skill
adapts as a hand-applied procedure, and which it deliberately does not
adopt. The skill applies the paper's *discipline* by hand; it does not run
the paper's automated training loop.

## Contents

- [Adapted](#adapted)
  - [3.1 Problem Setup: the scorer and the splits](#31-problem-setup-the-scorer-and-the-splits)
  - [3.4 Bounded Text Updates: the edit budget](#34-bounded-text-updates-the-edit-budget)
  - [3.5 Validation Gate and Rejected-Edit Buffer](#35-validation-gate-and-rejected-edit-buffer)
  - [Appendix B: the precondition and the transfer caution](#appendix-b-the-precondition-and-the-transfer-caution)
  - [Appendix C: the default split and the accept rule](#appendix-c-the-default-split-and-the-accept-rule)
- [Not adapted, with reasons](#not-adapted-with-reasons)
  - [3.2 / 3.3 rollout and reflection batch execution](#32--33-rollout-and-reflection-batch-execution)
  - [3.6 Epoch-Wise Slow/Meta Update](#36-epoch-wise-slowmeta-update)
  - [3.7 Harness-Agnostic Deployment and the optimizer machinery](#37-harness-agnostic-deployment-and-the-optimizer-machinery)
  - [The benchmark suite](#the-benchmark-suite)

## Adapted

### 3.1 Problem Setup: the scorer and the splits

SkillOpt's eq. (1) defines a run as `(tau(s), r(s)) = h(M, x, s)` with a
scalar score `r(s) in [0,1]` for target model `M`, harness `h`, task `x`,
and skill `s`. Eq. (2)-(3) select the skill that maximizes the mean score
on the selection split `D_sel` from the candidates generated on the train
split `D_tr`, and report final performance only on the test split
`D_test`.

What this skill adapts: the requirement that a scorer produce a repeatable
number in `[0,1]`, and the three-way disjoint split where the train split
supplies edit evidence, the selection split gates acceptance, and the test
split is read only for a final report. This is the precondition gate and
step 1 of the skill's procedure. A skill with no such scorer does not
qualify -- that is the whole point of the precondition.

### 3.4 Bounded Text Updates: the edit budget

SkillOpt's learning-rate analogue is the edit budget `L_t`: the optimizer
ranks the merged edit pool by expected utility and clips it to the top
`L_t` edits per step. Patch mode applies localized append / insert /
replace / delete operations; rewrite mode conditions a full rewrite on a
few suggestions. The paper argues bounded updates preserve continuity
while still letting the skill acquire new procedures, whereas unbounded
rewrites can erase useful rules or overfit to a local failure.

What this skill adapts: the per-iteration edit cap and the strong
preference for localized patches over wholesale rewrites (procedure step
2). The skill does not implement the utility-ranking or the schedule
machinery; a human caps and picks edits by judgement.

### 3.5 Validation Gate and Rejected-Edit Buffer

Every candidate skill is scored on `D_sel` with the same frozen target
model and harness. If it improves the current selection score it becomes
the new current skill; if it also exceeds the best score so far it becomes
`best_skill.md`; otherwise it is rejected. A tie does not improve, so a
tie is rejected. The rejected-edit buffer is an epoch-local record of
observed failure patterns and, for rejected steps, the edits tried and the
score drop they caused, fed back into later reflection so the loop does
not repeat failed edits -- negative feedback at no inference-time cost.

What this skill adapts: strict improve-or-reject with ties rejected
(procedure step 3) and the rejected-edit log as negative feedback
(procedure step 4). These are the load-bearing invariants of the skill.

### Appendix B: the precondition and the transfer caution

Appendix B (Limitations) states the loop "relies on scored trajectories
and a held-out selection split, so it is most directly applicable when the
target task has automatic verifiers, exact-match metrics, executable
checks, or otherwise reliable feedback signals. For open-ended domains
where success is subjective, multi-dimensional, or costly to judge, the
validation gate may require stronger human or model-based evaluation." It
also cautions that optimized skills encode training-distribution
heuristics, so held-out evaluation is needed before transferring to
different models, harnesses, or tasks.

What this skill adapts: the automatic-verifier precondition becomes the
skill's opening STOP gate, and the transfer caution becomes the
transfer-check step (procedure step 5). The named "human or model-based
evaluation" substitute is why procedure step 6 requires an adversarial
verification pass around any LLM judge.

### Appendix C: the default split and the accept rule

Appendix C (Experimental Protocol) records the default `2:1:7`
train/selection/test split when no benchmark-specific split is stated, and
restates the accept rule: the candidate "is accepted only if it improves
the current selection score; the best accepted skill is exported as
`best_skill.md`." The student model, backend, harness, and evaluator stay
fixed during optimization.

What this skill adapts: the default split ratio as guidance (procedure step
1) and the accept-only-if-improves rule (procedure step 3). The skill notes
that with only a handful of hand-authored fixtures the ratio is
aspirational, and the minimal groundwork is a larger corpus.

## Not adapted, with reasons

### 3.2 / 3.3 rollout and reflection batch execution

Sections 3.2 (Forward Pass) and 3.3 (Backward Pass) describe running
rollout batches, then splitting trajectories into failure/success
minibatches an optimizer model reflects on. This is automation
infrastructure. gitapex has no rollout executor and applies the discipline
by hand, so the batch machinery is not adopted; a human reads the failing
runs and proposes the edits directly.

### 3.6 Epoch-Wise Slow/Meta Update

Section 3.6 adds a momentum-like slow/meta update: an optimizer-side field
carrying longitudinal guidance across epochs, plus a meta skill that is not
shipped with the target. This is an optimizer-side automated mechanism with
no hand-applied analogue worth its complexity, so it is left out. The
rejected-edit log (from 3.5) already gives the loop enough memory for
hand-applied iteration.

### 3.7 Harness-Agnostic Deployment and the optimizer machinery

Section 3.7's adapter interface and the separate optimizer model exist to
run the loop automatically across harnesses. This skill is the manual
procedure, not a runner, so the adapters and optimizer machinery are out of
scope. Deploying the improved `SKILL.md` is just committing the file.

### The benchmark suite

The evaluated benchmarks (SearchQA, SpreadsheetBench, OfficeQA, DocVQA,
LiveMathematicianBench, ALFWorld) all ship native automatic evaluators.
gitapex has no equivalent benchmark tasks, which is exactly why the
precondition gate exists: without a checkable scorer, this skill stops
rather than pretending a benchmark is present.

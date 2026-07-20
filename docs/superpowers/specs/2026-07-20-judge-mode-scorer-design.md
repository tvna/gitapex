# Judge-mode scoring for `score_contract.py`: design spec

Date: 2026-07-20

Refs [#175](https://github.com/tvna/gitapex/issues/175) (deferred from [#173](https://github.com/tvna/gitapex/issues/173)
option 1, per the [#174](https://github.com/tvna/gitapex/issues/174) handoff recommendation). Also refs
[#167](https://github.com/tvna/gitapex/issues/167) repair #13, the original
observed failure.

## Problem restated

`score_contract.py` scores a run by substring presence/absence
(`output_contains` / `output_not_contains`). A pure substring match cannot
distinguish "the transcript used this keyword while confirming a real
finding" from "used it while hedging a non-finding" -- both are true
statements about the text, only one is evidence the grading judgment was
correct. [#173](https://github.com/tvna/gitapex/issues/173) closed the cheap half of this gap (a fixture-authoring
discrimination rule, now in `skills/scorer-gated-skill-edits/SKILL.md`'s
"Authoring fixtures for a substring scorer" section, partly enforced by the
[#170](https://github.com/tvna/gitapex/issues/170) linter). This spec resolves the harder half: an optional semantic
scoring mode, deferred here because it is a genuine design decision, not a
quick add.

## The four open questions, resolved

### 1. Disagreement handling

**Decision: the judge never overrides. Disagreement between the judge and
the substring verdict is surfaced, not silently resolved either way.**

Rationale (matches the issue's own recommendation): a judge model is itself
fallible, and this repository's own `scorer-gated-skill-edits` skill already
treats an LLM judge as a weaker substitute that needs adversarial
verification before any trust (Procedure step 3's conditional branch). Letting
the judge silently override the deterministic substring score would let a
judge false-positive inflate a gate -- exactly the failure mode the skill's
existing Stop boundary ("Never treat an LLM judge's pass as ground truth
without an adversarial verification pass") already forbids for judge PASSes
in general. Disagreement is data a human (or the next iteration) acts on, not
a tie-break the tool resolves on its own.

### 2. Adversarial verification

**Decision: judge-mode verdicts run under the same adversarial-verification
rule the skill already requires for any LLM-as-judge use -- no separate or
weaker rule for this specific scorer.**

`scorer-gated-skill-edits`'s Procedure step 3 conditional branch already
specifies the mechanism: an independent second judgement whose only goal is
to break the first verdict, confirming the judge cited concrete evidence
rather than approving on "looks fine." Judge-mode scoring for
`score_contract.py` is one more caller of that existing rule, not a new
mechanism -- the CLI records the *outcome* of that human/agent-run procedure
(see Decision 4's mechanism), it does not run or replace the adversarial pass
itself.

### 3. Cost gating

**Decision: `--judge-verdict` is opt-in per invocation, off by default, and
recommended only for the selection-split gate decision on a fixture where the
substring result is disputed or newly authored -- not as a routine per-trial
step.**

The substring score stays the always-on, zero-marginal-cost baseline for
every trial (Decision 4). Judge-mode work -- reading the transcript against
the fixture's `description`, then running the adversarial-verification pass
-- is real per-fixture human/agent effort, so it is reserved for the cases
that actually need it: a fixture whose discrimination the [#173](https://github.com/tvna/gitapex/issues/173) authoring
rule could not fully verify statically (the residual semantic half that
rule's own honest-limit paragraph names), or a KEEP/REJECT decision on a
high-stakes skill edit where the reviewer wants a second signal before
shipping.

### 4. Determinism

**Decision: the substring score remains the sole recorded baseline number.
The judge verdict is captured as a separate, additional field on the CLI
output, never blended into the compared mean.**

This preserves `score_contract.py`'s existing hard invariant -- standard
library only, fully deterministic, `test_deterministic_same_inputs_same_output`
-- which a live model call would break outright (non-reproducible, needs
credentials/network, adds cost and latency to a script currently invoked by
hand). Concretely: `strict_compare`/`pruning_compare` and the `--compare-to`
mean computation are completely unchanged; judge-mode adds one independent
output field alongside them.

## Mechanism: a verdict recorder, not a model caller

`score_contract.py` does not call any LLM API itself. This is a deliberate
scope boundary, not an oversight:

- It matches `scorer-gated-skill-edits`'s own established philosophy
  (`references/skillopt-mapping.md`'s "Not adapted" section: "This skill is
  the manual procedure, not a runner"). The skill already assumes a human or
  the orchestrating agent performs judgment steps by hand; judge-mode scoring
  is one more such step, not a new automated pipeline.
- Embedding a live model call in a checked-in script would add exactly the
  external-endpoint / credential / cost surface this repository's own
  CLAUDE.md section 4 flags as requiring explicit justification, for a script
  whose committed contract is "standard library only" by design.

Instead, the human or agent already following the adversarial-verified judge
procedure (Decision 2) passes its outcome into the CLI with a new flag:

```
--judge-verdict {agree,disagree}
```

Valid only together with `--compare-to` (the aggregate KEEP/REJECT gate this
verdict is about). `agree` means the judge's semantic read of the transcripts
matches the substring-derived KEEP/REJECT; `disagree` means it does not. The
CLI appends the judge outcome to its existing one-line report rather than
changing the reported mean or verdict:

```
0.900000 KEEP JUDGE_AGREE
0.900000 KEEP JUDGE_DISAGREE_REVIEW_REQUIRED
```

`JUDGE_DISAGREE_REVIEW_REQUIRED` is printed to make disagreement impossible
to miss when scanning CLI output, per Decision 1 -- it does not change the
exit code or the KEEP/REJECT text, since this tool has no CI wiring today
(confirmed: no workflow invokes `score_contract.py`; it is read and run by
hand or by an agent following `scorer-gated-skill-edits`'s procedure) and
disagreement is advisory input to a human decision, not a pass/fail gate on
its own.

## What this spec does not build

- No judge model, no API call, no new dependency, no credential-issuance
  path -- per Decision 4 and the mechanism section above, the tool records a
  verdict a human/agent already produced; it does not produce one itself.
- No change to `strict_compare` / `pruning_compare` semantics or the
  substring `score()` function.
- No new eval fixture: this change documents an additional CLI mechanism
  under `scorer-gated-skill-edits`'s existing Procedure step 3 conditional
  branch, matching the precedent recorded for [#149](https://github.com/tvna/gitapex/issues/149) in
  `docs/skill-eval-status.md` ("Advisory naming addition, not a new enforced
  branch, so no new eval fixture was added") -- the branch's behavioral rule
  (adversarial verification before trusting a judge PASS) is unchanged; this
  only gives that already-required step a place to record its outcome.

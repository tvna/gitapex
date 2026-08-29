# Blast-radius tiers and the output schema

Elaboration of Step 5's two blast-radius tiers and Step 6's finding
record shape, migrated from `drafting-a-pr-to-merge` SKILL.md's own former
Step 8 ("trace the changed symbol's call sites to establish blast radius
before finalizing it"), extended with a high-effort escalation tier and
the full record schema.

## Low effort: shallow call-site tracking

For every finding that survived Step 4, enumerate the changed symbol's own
direct call sites -- who calls it, from where -- without inspecting
whether each caller's own usage still matches the changed symbol's
contract. This establishes the finding's own reach (how many places would
be affected if the finding is real) without the deeper signature-fit
judgment the high-effort tier below adds.

## High effort: signature-aware escalation

For every finding that survived Step 4, in addition to the shallow
call-site enumeration above: for each call site found, check whether that
caller's own usage still matches the changed symbol's actual signature and
contract post-change (parameter count/order/type, return shape, side
effects a caller might depend on). A call site that exists but whose own
usage no longer matches the changed contract is a materially different,
more actionable fact than a call site that merely exists -- the shallow
tier alone cannot distinguish the two.

## Deferred: dynamic blast-radius

A dynamic, test-execution-driven blast-radius pass (exercising the real
test suite and tracing which call sites actually execute across a change,
mirroring the pstack `/blast-radius` precedent named in this skill's own
tracking issue's accepted-candidates comment) was considered and is
explicitly **not** implemented in either tier above. It is contingent on
this skill assuming an executable environment -- a test runner, a
reachable dependency graph, permission to execute code -- which this
design does not make. Both tiers above are static analysis only.

## Output schema

One record per item Step 6 reports, in either of two shapes:

**A finding record** (confirmed or unconfirmed-concern):

```
file: <path>
line: <line or line range>
summary: <one-sentence statement of the defect>
failure_scenario: <concrete input/state -> wrong output or crash>
severity: <low | medium | high | critical>
class: confirmed | unconfirmed-concern
tag: root-cause | symptom
blast_radius: <the Step 5 call-site trace for this finding, at the tier this invocation ran>
```

`class` is `unconfirmed-concern` only when Step 4's high-effort gate
retained it as speculative, or unconditionally for a security-tier finding
at any effort level (see
[security-tier-handling.md](security-tier-handling.md)) -- never for an
ordinary finding at `low` effort, which is either `confirmed` or dropped
entirely. `tag` is `root-cause` when the finding names the actual defect
directly, and `symptom` when Step 3's verification could confirm an
observed effect but not pin down its own cause -- the latter is this
skill's own mechanical trigger for a downstream caller to consider routing
the underlying question to `diagnosing-a-failure`, sharper than a
prose-only "does this look like it needs deeper diagnosis" judgment call.

**A skip or rejection record** (Step 1's skip disclosure, or a Step 3
rejection surviving into the audit trail):

```
file: <path, or "(whole target)">
line: <line or line range, or "(whole file)">
summary: <what was skipped or rejected, and why>
stage: skipped-safe-signal | fabricated-precheck | independent-verification | counterfactual-check
```

## The audit trail

Step 6's report always includes every Step 3 rejection alongside the
surviving findings -- not only the survivors. A report showing only
confirmed and unconfirmed-concern findings, with no record of what a
persona raised and verification discarded, cannot be checked for
over-suppression by whoever reads it; the audit trail is what makes that
check possible.

# Cross-cutting axes: Compatibility awareness, Reproducibility / Domain-coverage, Blast-radius, Contract role / input-domain closure

Portable elaboration of `SKILL.md`'s Compatibility awareness,
Reproducibility / Domain-coverage, Blast-radius / trust classification,
and Contract role / input-domain closure axes, same pattern as the
Security-level axis in `references/security-level.md`: `SKILL.md` keeps a
short pointer per axis, this file carries the full reasoning.

## Contents

1. [Axis: Compatibility awareness](#axis-compatibility-awareness)
2. [Axis: Reproducibility / Domain-coverage](#axis-reproducibility--domain-coverage)
3. [Axis: Blast-radius / trust classification](#axis-blast-radius--trust-classification)
4. [Axis: Contract role / input-domain closure](#axis-contract-role--input-domain-closure)

## Axis: Compatibility awareness

A warning-only axis, separate from the two-lane split and from the
verdict -- never change a verdict solely because of this axis. Ask: does
this gate's own behavior (its trigger semantics, its exit/deny contract,
its I/O format) actually differ across the specific agent-tool runtimes
or dependent middleware versions it is meant to run under? A gate whose
behavior is silently runtime-specific, with no documentation of that
fact, is a compatibility-awareness finding even if the gate works
correctly on whichever runtime its author tested against. This skill does
not ship a pre-verified cross-runtime compatibility matrix (see
`SKILL.md`'s Lifecycle note) -- apply this axis by checking the gate's own
documentation for an explicit compatibility statement, and by testing on
more than one runtime/middleware version where that is feasible, rather
than assuming single-runtime behavior generalizes.

## Axis: Reproducibility / Domain-coverage

For a given policy, this axis asks: in how many of the four domains is it
realized, with what trust/coverage properties, and is the resulting
overlap (or gap) a deliberate, argued decision or an unnoticed accident?

Candidate checks:

- **Domain-count disclosure.** Does the gate's own documentation state,
  or can a reviewer determine, how many domains realize the same policy
  -- one or several -- rather than assuming single-domain coverage is
  either always sufficient or always insufficient without checking?
- **Argued vs. accidental coverage.** Where multiple domains realize the
  same policy, does something (a docstring, a design doc, a registry
  entry) state *why* -- defense-in-depth against a specific named failure
  mode, layered coverage at different pipeline stages, a credential/
  reversibility asymmetry between layers, per the Domain placement
  criteria in [references/mechanism-fit.md](mechanism-fit.md) -- rather
  than the multiplicity being an unexplained accident of history?
- **Single source of truth for the policy's own identity.** Where a
  policy needs the same predicate evaluated in more than one domain, is
  that predicate defined once and imported/referenced, or re-derived
  independently in each realization, risking silent drift between
  copies?
- **Reversibility-driven placement, not just presence.** Where an
  earlier-domain realization exists specifically because a later domain's
  own detection would already be too late, does the gate's own
  documentation say so, rather than leaving the reader to guess why the
  same policy is not simply realized once, later?
- **The zero-domain case, named explicitly rather than left to read as
  "nothing to report."** A stated invariant with *zero* domains covering
  it is a distinct, more severe finding than single-domain coverage that
  merely lacks an argued rationale -- absence of coverage is a
  fail-closed finding in its own right. This is the specific gap the
  [coverage attestation](../SKILL.md#three-way-division-of-responsibility)
  step in the Procedure exists to catch systematically, not something
  this axis alone should be relied on to notice per-policy.

This axis is scoped to one specific policy at a time -- it does not
characterize the calling/installing repository's general cross-domain
footing independent of any single policy; that is dimension 23's own job
(`dimensions.md`), which runs once per review regardless of how many (or
how few) policies this axis has already been applied to.

A concrete worked example of this axis applied to a real, multi-domain
policy: [references/gitapex-worked-examples.md](gitapex-worked-examples.md).

## Axis: Blast-radius / trust classification

Does the gate's own documentation (or this review's own report on it)
state explicitly what the gate can do -- or fail to prevent -- if it is
bypassed, misconfigured, or simply absent, rather than leaving that
implicit? A gate that silently assumes its own reader already understands
its stakes is harder to prioritize correctly against other findings, and
harder to reason about when deciding whether a proposed change to it is
safe. Grade this the same way regardless of which of the four domains the
gate lives in -- the question ("what happens if this gate is not here,
or lies") does not depend on the realization mechanism.

## Axis: Contract role / input-domain closure

A warning-only axis, separate from the two-lane split and from the
verdict -- never change a verdict solely because of this axis, the same
limit Compatibility awareness above already carries. It classifies
*what the gate's check is*, not how well the check is built, through two
independent sub-judgments; neither is a score, and neither substitutes
for the other. Answer both, or report the one the evidence cannot settle
as indeterminate with what was missing -- never silently skip either, the
same rule the two-lane walk already holds a dimension to.

Applicability: the axis is defined over a single check. An artifact that
asserts no condition at all -- a pure codegen, formatting, or reporting
step -- is not-applicable, and saying so requires affirmatively confirming
it asserts none, not failing to find one. A check whose source or runtime
behavior could not be read is indeterminate, not not-applicable.

### Sub-judgment 1: contract role

The three obligations of Design by Contract -- Bertrand Meyer, [Applying
"Design by Contract"][dbc], IEEE Computer 25(10):40-51, 1992 -- applied to
the check under review. Ask which one it actually is:

- **Precondition** -- the check asserts a condition the *caller* of the
  guarded operation must already satisfy, evaluated before that
  operation is allowed to proceed. A violation attributes fault to the
  caller.
- **Postcondition** -- the check asserts a condition the guarded
  operation must have *established*, evaluated after it ran and against
  what it really produced rather than what it was asked to produce. A
  violation attributes fault to the operation itself.
- **Invariant** -- the check asserts a property that must hold at every
  observation point, tied to no single operation. A violation attributes
  fault to the state, implicating neither a caller nor one routine.

Why this is worth reporting even though it moves no verdict: the
contract role decides who a denial must address. A precondition-shaped
gate whose message blames the routine, or a postcondition-shaped gate
whose message blames the caller, delivers a correct denial to a party
that cannot act on it -- and the party who receives it has every
incentive to route around the gate rather than fix anything.

Report a **mixed** role rather than forcing one label: a gate that both
admits an operation and re-checks what that operation produced carries
two obligations, and naming both, with which half each message
addresses, is more useful than picking the louder one.

A target whose gates classify as preconditions and invariants with no
postcondition among them is a prompt to ask whether post-operation
verification is genuinely unnecessary here or merely unbuilt. Raise it
as an observation; it is not evidence that the three-way split is wrong,
and this axis has no standing to assert either answer.

### Sub-judgment 2: input-domain closure

Independent of the role above -- any of the three roles can carry either
domain kind. Ask which kind the check's own input is drawn from, because
the two want opposite treatment:

- **Structural / protocol value** -- the admissible values are fixed by
  a protocol, schema, or vocabulary someone else owns: an enum field, a
  token pattern, a closed verdict vocabulary. Closing the domain is the
  safe direction. Enumerate what is accepted and treat everything else
  as malformed; a permissive "roughly the right shape" match is the
  defect here, because it silently admits a value the owning protocol
  never defined.
- **Threat / safety-classification category** -- the input is a judgment
  about the world: what counts as a destructive operation, what counts
  as an untrusted source, what counts as sensitive data. Closing this
  into a finite list is the defect. A closed list leaves an evader only
  the tedious work of finding one unlisted variant, whereas an open
  category -- enumerated examples marked explicitly as non-exhaustive,
  plus a default-in-scope rule for anything unlisted -- removes the gap
  rather than narrowing it.

The asymmetry is not this skill's invention: the prior art is a sibling
instruction-file repository that locks its own safety-category bullets to
a literal non-exhaustive marker phrase, so a later edit cannot quietly
re-close one into a finite list. Its grounding is the impossible-vs-tedious
design test ([references/security-level.md](security-level.md) reuses the
same test), which names a closed list as a control an attacker finds merely
tedious to evade. The concrete citation, and what was actually read to
confirm it, are repository-scoped:
[gitapex-worked-examples.md](gitapex-worked-examples.md).

A marker phrase in a comment, docstring, or doc is a claim about the
category, not the control itself. Credit the open reading only where the
default-in-scope rule is visible in the check's own logic or its denial
behavior; where only the assertion exists, report both-readings or
indeterminate and name the assertion as unverified rather than treating
the target's own wording as evidence of what it does.

Where the boundary is genuinely undecided -- a domain with properties of
both, such as a fixed protocol enum whose members also encode a safety
decision -- say so and name both readings, with what makes each reading
available, rather than picking one to produce a tidier report. A bare
"both readings" label carries none of the information that answer exists
to give, the same way a bare "mixed" role does.

### Never both: division of responsibility with dimension 15

Meyer states non-redundancy as an absolute rule ([dbc]): a condition
belongs in exactly one place -- either in the precondition, or in the
routine's own body, never in both -- because redundant re-checking is not
extra safety, it is a design smell signalling that the responsibility
split is unclear. Applied here to *this review's own judgments*, never to
a target's gate layering: two graders must not both score the same
question. It says nothing about whether a policy should be realized in
more than one domain -- that is the Reproducibility / Domain-coverage axis
above, where layered realization is frequently the right answer, and
reading this rule as licence to report a real second layer as redundant
is the defense-in-depth regression `SKILL.md`'s own Stop boundaries
forbid. Applied to this axis and dimension 15
([dimensions.md](dimensions.md)), which both touch a gate's input
handling and are the easiest pair here to collapse into one judgment:

- **This axis** asks what the input domain *should* be by design --
  closed, because a protocol already fixes the admissible values, or
  open, because the category is a safety judgment that a finite list
  would only invite evasion of.
- **Dimension 15** asks how the gate *behaves* when malformed input
  actually arrives at runtime -- deny or escalate, versus silently
  allow.

The two are independent in both directions: a gate can fail closed
correctly on malformed input (dimension 15 passes) while its threat
category is wrongly closed into a finite list, and a gate can draw its
domain exactly right while still defaulting to allow when a field it
needs is missing. Judge each question once, in its own place. Never let a
domain-closure observation restate a dimension-15 verdict, and never let
a dimension-15 pass stand in for the design question this axis asks.

Three further neighbours, fenced the same way, so sub-judgment 1 is no
less bounded than sub-judgment 2:

- **Shape check 2** asks whether a deny reaches every *channel* the caller
  actually sees; sub-judgment 1 asks who the message names as at fault.
  A gate can dual-signal perfectly on both channels and still blame the
  wrong party.
- **Dimension 17** asks whether the gate's existence and purpose are
  discoverable at all; sub-judgment 1 presumes it is and asks only about
  attribution.
- **The Security-level axis** ([security-level.md](security-level.md))
  shares the impossible-vs-tedious test with sub-judgment 2 but asks a
  different question of it -- whether the control's own tier claim is
  honest, which does bear on a verdict. This axis asks only whether the
  domain's shape is right by design, and never bears on one. A finding
  routed here to avoid the Security-level axis's verdict standing, or
  routed there to give this axis's observation weight it does not have,
  is the misuse both statements exist to block.

[dbc]: https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf "Bertrand Meyer, Applying \"Design by Contract\", IEEE Computer 25(10):40-51, October 1992"

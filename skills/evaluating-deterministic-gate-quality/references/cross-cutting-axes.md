# Cross-cutting axes: Compatibility awareness, Reproducibility / Domain-coverage, Blast-radius

Portable elaboration of `SKILL.md`'s Compatibility awareness,
Reproducibility / Domain-coverage, and Blast-radius / trust
classification axes, same pattern as the fourth axis in
`references/security-level.md`: `SKILL.md` keeps a short pointer per axis,
this file carries the full reasoning.

## Contents

1. [Axis: Compatibility awareness](#axis-compatibility-awareness)
2. [Axis: Reproducibility / Domain-coverage](#axis-reproducibility--domain-coverage)
3. [Axis: Blast-radius / trust classification](#axis-blast-radius--trust-classification)

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

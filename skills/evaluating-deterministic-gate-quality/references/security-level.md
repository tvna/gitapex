# Security-level / Zero-Trust maturity classification

Portable elaboration of `SKILL.md`'s Security-level / Zero-Trust maturity
classification axis. Grounded in Anthropic's "Zero Trust for AI Agents"
eBook -- a three-tier capability framework (**Foundation** / **Enterprise**
/ **Advanced**), each tier building on the one before it, spanning seven
capability categories, with an explicit design test for judging whether a
control belongs at a tier at all: does it make the attack **impossible**,
or merely **tedious**?

## Contents

1. [The tier ladder](#the-tier-ladder)
2. [The seven capability categories](#the-seven-capability-categories)
3. [The impossible-vs-tedious test](#the-impossible-vs-tedious-test)
4. [Reuse, never re-derive](#reuse-never-re-derive)
5. [Honesty vocabulary](#honesty-vocabulary)
6. [What this axis does not cover](#what-this-axis-does-not-cover)

## The tier ladder

- **Foundation** -- the minimum viable posture. Per the source's own
  framing, the Foundation floor is not a relaxed posture: every
  non-negotiable floor (below) holds already. What Foundation omits is
  depth, not the floors themselves.
- **Enterprise** -- Foundation plus depth appropriate where a single
  compromise carries meaningful business impact.
- **Advanced** -- Enterprise plus the strictest posture achievable, for
  high-risk or regulated contexts, paired with an explicit, honest list of
  what remains unreachable even here.

A capability present at one tier is present at every tier above it --
advancing strengthens existing controls, never replaces them.

## The seven capability categories

1. Identity and authentication.
2. Access control and privilege management.
3. Observability and auditing.
4. Behavioral monitoring and response.
5. Input validation and output controls.
6. Integrity and recovery.
7. AI governance policies.

These category names are the source document's own; consult the source
directly for its full per-category tier tables rather than treating a
restated summary here as authoritative -- restating them in full here
would itself be exactly the duplication/drift risk this skill's own
dimension 12 exists to name, applied reflexively to this skill's own
content.

## The impossible-vs-tedious test

The discriminator between a **floor** (non-negotiable at every tier) and a
**tier-scalable control** (its strictness legitimately varies by tier):
does this specific control remove the guarded attack path entirely (an
empty bypass list, a permission never granted, an override mechanism that
does not exist), or does it only add friction an agentic attacker with
unlimited patience can eventually grind through (an approval count, a
retention window, a scan cadence)? A floor's value holds regardless of
tier because relaxing it reintroduces a path that was previously simply
absent; a tier-scalable control's value is depth or friction, which
legitimately scales with the target's own risk tolerance and capacity.

Applied to a gate under review, not only to a whole system: the same
question, asked of the one specific mechanism the gate's own control
actually relies on. A gate can be floor-class on one property (its deny
path cannot be bypassed at all) and merely tier-scalable on another (how
long its audit trail is retained) at the same time -- classify each
property this axis actually checks separately rather than assigning one
single tier label to the whole gate.

## Reuse, never re-derive

This axis does not build a private, per-review tier taxonomy. Applying it
to a specific gate has two paths:

- **The target repository already has its own tier/ceiling
  documentation** -- a Zero-Trust-style capability-tier design, a
  control-coverage inventory mapped against an external taxonomy, or an
  equivalent. Cross-check the gate's apparent tier and category against
  that already-established ceiling directly. Grading whether that ceiling
  documentation is itself well-reasoned or internally consistent is a
  separate task (this skill's own procedure applied to it if it is itself
  a gate-adjacent artifact, or a general design review otherwise) -- this
  axis only consumes it as an input, it does not author or validate it
  from scratch.
- **The target repository has no such documentation.** Apply the tier
  ladder, the seven categories, and the impossible-vs-tedious test
  directly to the gate under review, and name the absence of a
  repo-specific ceiling reference explicitly as missing context for the
  classification -- never silently proceed as though no such reference
  were needed, and never invent one on the target's behalf.

## Honesty vocabulary

Tag what a control concretely does today in one of three classes,
generalized from this skill's authoring repository's own concrete
instance (see
[gitapex-worked-examples.md](gitapex-worked-examples.md) for that
instance's own vocabulary):

- **Enforced today** -- the control is live, automated backing exists
  now.
- **Documented, not enforced** -- the target's own documentation states
  the expectation, but nothing currently blocks or requires it
  automatically.
- **Not achievable** -- no plausible mechanism exists for this target's
  actual architecture even at the Advanced tier; state this plainly,
  never invent a capability the target has no path to.

## What this axis does not cover

It does not decide whether a gate's own mechanics actually realize
non-bypassability or a fail-closed default at all -- that is dimensions 1
and 15's own job (`dimensions.md`), consumed here as an input rather than
re-derived. It does not decide which of the four realization domains
should own a policy -- that is mechanism-fit's own job
(`mechanism-fit.md`). It does not decide how many domains realize a
policy, or whether that multiplicity is argued or accidental -- that is
the Reproducibility/Domain-coverage axis's own job (`SKILL.md`). And it
does not decide what happens if the gate is bypassed or absent -- that is
the Blast-radius/trust classification axis's own job (`SKILL.md`). This
axis's own, distinct question is narrower than all four: given that a
gate exists, is correctly placed, and its own mechanics are already
graded, where does its actual control strength honestly sit on an
external maturity ladder, and is that placement honestly claimed.

# Deterministic-gate mechanism-fit: should this be a deterministic gate, and if so, which domain owns it?

## Contents

1. [Gate vs. no gate](#gate-vs-no-gate)
2. [Gate vs. infrastructure-owned deterministic control](#gate-vs-infrastructure-owned-deterministic-control)
3. [Domain placement](#domain-placement)
4. [What this framework does not cover](#what-this-framework-does-not-cover)

Three questions, in order. The first asks whether a deterministic
decision is the right mechanism at all; the second -- meaningful only
once the first says yes -- asks whether a gate the target repository
itself authors should own that decision, or whether an infrastructure
control the target already depends on owns it natively; the third --
meaningful only once the second leaves a repository-authored gate in
scope -- asks which of the four domains named in `SKILL.md`'s Scope
section (git hook subprocess, agent-harness hook subprocess, CI job step,
MCP server subprocess) should own it. Skipping straight to domain
placement without asking the first two is the same mistake
`evaluating-skill-quality`'s own Agentic operation mechanism-fit section exists to prevent
for skills: a well-implemented control in the wrong mechanism, in a layer
that never needed to own it, or in no mechanism that needed building at
all, is not fixed by polishing its implementation further.

## Gate vs. no gate

Before asking which domain should own a policy, ask whether a
deterministic gate should own it at all. Grounded in the same primary
source `evaluating-skill-quality`'s own `references/rubric.md` Agentic
operation mechanism-fit section already cites -- Anthropic's "Steering Claude Code" guidance:
a rule shaped like "every time X, always do Y" or "never do this" needs
deterministic backing (a hook, a required check, a permission), because a
model can fail to follow a prompted rule under pressure. The mirror image
holds just as literally: a rule that is not a fixed, reproducible
decision -- one whose correct answer depends on reading intent, weighing
trade-offs, or judging something novel each time -- does not become safer
by forcing it through a deterministic gate; it belongs in prose (a skill,
CLAUDE.md content, a human review step) where judgment can actually be
applied, per that same source's own "a reviewer's judgment calls belong
in prose" framing.

The concrete test: does the policy reproduce the *same* decision every
time it is evaluated against the *same* input, with no interpretation
required -- or does answering it correctly depend on context a fixed rule
cannot capture? This generalizes, rather than duplicates, the filter
`SKILL.md`'s Procedure step 5 (coverage attestation) already applies when
sweeping a whole repository's stated invariants: a prose invariant that
is inherently a matter of human judgment or communication (e.g. "explain
trade-offs to the user," "reach real understanding before signing off")
is not a coverage-attestation finding merely for lacking a script --
that same judgment-call test is what this section names as the
first-order Deterministic-gate mechanism-fit question, not a separate rule; step 5 applies
it at repo-sweep scale, this section applies it to one artifact or one
proposed policy at a time. Two representative poles, not an exhaustive
list: "block a push that contains a matched secret pattern" reproduces
the same decision every time -- gate material. "Explain the trade-offs of
this design to the user" has no fixed correct output -- prose material,
never a gate.

A policy that reads as one judgment call at first glance can still
decompose into a deterministic part and a judgmental part -- do not let
the judgmental part crowd out a real deterministic requirement sitting
alongside it. "A production deployment requires an independent approval"
is not one fact but two: whether *an* approval was actually recorded
before the deployment proceeded is a fixed, reproducible check a gate can
verify (a required-reviewers rule, a recorded approval label, a signed
sign-off) -- gate material, even though whether *that specific
deployment* should have been approved is exactly the kind of judgment
this test routes to prose. Apply the reproduces-the-same-decision test to
each constituent fact separately, never to a policy's surface-level label
as a whole: a no-gate verdict for the substantive judgment does not
license removing a requiredness backstop that was never the judgmental
part to begin with -- collapsing a deterministic layer into pure prose
just to simplify the verdict is exactly the failure mode a
defense-in-depth discipline exists to forbid, whatever the target
repository's own contributor-instruction file happens to call that
principle.

**When this check concludes no gate is warranted, stop here.** Report
that as the finding directly -- the policy should be (or remain) a skill,
CLAUDE.md content, or a human review step, not a deterministic gate; this
finding is itself the item's verdict (`SKILL.md` Procedure step 6) -- and
do not proceed to either question below, the axes, the three-way division
of responsibility, or Procedure steps 3-5 for that policy.

## Gate vs. infrastructure-owned deterministic control

Applies only once Gate vs. no gate above has concluded a deterministic
decision is warranted, and before Domain placement below asks which
domain should realize one. A deterministic decision does not have to be
realized by a gate the target repository itself authors and runs: the
platform, the runtime, or the hosting environment the target already
depends on may own the same decision natively -- a branch-protection or
required-signature setting, an identity provider's own permission grant,
a network egress boundary, a container runtime's own read-only mount, a
package registry that refuses to serve an unapproved artifact. Naming
that owner is a different question from naming a realization domain: the
four domains classify *where a gate this repository writes actually
runs*; this question asks *whether this repository should be writing one
at all*, given a control that already sits one layer beneath all four.

That "beneath all four" is the category's own boundary, and it excludes
more than it first appears to. Repository content the same change under
review could edit -- a lockfile, a config file, a policy document, a
declarative manifest committed to the repository -- is never an
infrastructure-owned control here, however declarative it looks: it sits
*inside* the surface a gate exists to check, not beneath it, and an
actor who can change the content can change the control. Neither is a
setting the target itself can silently flip while claiming the guarantee
holds. Boundary cases short of those two exclusions stay a judgment this
test cannot settle mechanically -- disclose that in the finding rather
than presenting a three-way answer as if it were determinate.

Decision procedure: reuse the impossible-vs-tedious test
([security-level.md](security-level.md#the-impossible-vs-tedious-test)),
rather than re-deriving a second discriminator here. Ask it twice of the
same policy, once per candidate owner:

- Does the infrastructure-owned control remove the guarded path entirely
  -- a permission never granted, a setting whose bypass list is empty, a
  resolution step that cannot reach an unpinned version -- or does it
  only add friction an actor with unlimited patience grinds through?
- Does the repository-authored gate remove that same path entirely, or
  does it only detect, warn, or slow an actor who can route around it (a
  different client, a direct API call, a clone with no hooks installed)?

Four outcomes, named with the exact tokens `output-schema.json`'s own
`controlOwnership.owner` enum uses, so one vocabulary serves the prose
answer and the machine-readable one rather than two spellings drifting
apart. Answering consumes the impossible-vs-tedious distinction to pick
an owner; it records no floor / tier-scalable classification of its own.
Where such a classification is to be reported, it goes through the
Security-level axis under that axis's own discipline (its
ceiling-document search, and shape check 1 and dimension 15's live-tested evidence
as input), never as a by-product of this question.

Take the two questions above as a pair. Every combination of their
answers lands on one of these four, including the two combinations
easiest to miss:

- **`infrastructure-owned-control`** -- the infrastructure control
  removes the path this policy guards; the repository-authored gate,
  over that same path, only adds friction an actor with unlimited
  patience grinds through. The finding is that the policy's primary
  owner is the named infrastructure control -- and that the target's own
  documentation should say so wherever it currently implies the gate is
  the enforcement. Say so by *adding* the real owner, never by deleting
  the gate's own stated rationale: reducing what a reader can discover
  about why the gate exists is a dimension 17 regression, and the Stop
  boundary against downgrading an existing gate covers its documentation
  as much as its wiring.
- **`repository-authored-gate`** -- no infrastructure control the target
  has removes the path, whether or not one touches this policy at all.
  Two combinations land here, and the second must not be silently
  dropped: the gate removes the path and no infrastructure control
  reaches it; or *neither* removes it (an alert-only platform scan
  beside a hook a flag can skip). In that second case the repository
  still owns the policy, and the absence of any floor-class control over
  it is itself a finding to report here -- the Reproducibility /
  Domain-coverage axis and coverage attestation then carry it. Never
  read "no floor-class owner" as "no owner to name". Proceed to Domain
  placement below.
- **`layered-both`** -- both remove a path. Read the two questions as
  scoped to the one path this policy guards; a control that removes some
  *other* path is not an answer to either, and does not make an
  otherwise infrastructure-owned policy layered. Where each closes a
  distinct part of the guarded path the other cannot reach, the
  multiplicity is argued; report it as such. Where
  both close the *same* path, say so plainly: that is real duplication,
  and whether it is justified is the Reproducibility / Domain-coverage
  axis's own argued-vs-accidental question, not this one's -- an
  infrastructure control merely existing is never grounds to strip the
  gate beside it. Proceed to Domain placement below for the
  repository-authored layer.
- **`indeterminate`** -- the evidence available cannot settle which
  party owns the policy, most often because an infrastructure control's
  own enforcement claim rests on a target-authored document rather than
  that platform's own configuration state, which `SKILL.md`'s Stop
  boundaries do not accept as confirmation. Report it with its reason;
  never resolve genuine uncertainty by picking among the three above,
  and never let it default to the answer the target is arguing for.
  Grade any existing gate through Procedure steps 3-5 exactly as the
  other three outcomes would.

**An infrastructure-owned verdict never licenses removing an existing
gate.** It reassigns which control the target should describe as
primary; it grants nothing else. That is the same non-authoritative limit
`SKILL.md`'s own Notes section already places on every verdict this skill
issues, and the same defense-in-depth discipline the decomposition rule
above applies to a no-gate verdict -- a review that answers this question
by deleting a layer has produced a regression, not a placement finding.

Nor is this answer ever replaced by a delegation recommendation. Naming a
stack and a delegate is an addition to an ownership answer that already
cites its own evidence, never a substitute for reaching one; where the
evidence cannot settle ownership, `indeterminate` with its reason is the
answer, not a delegate standing in for one. (The parallel rule for a
dimension's verdict and an axis's finding binds later, from Procedure
step 3, and lives with the rest of that set in
[grading-procedure.md](grading-procedure.md#stop-boundaries-grading-specific).)

Name the responsible technical stack concretely (the specific platform,
runtime, or manager, in the target's own vocabulary), never a generic
"the infrastructure" -- an unnamed owner is the bare "looks fine" verdict
`SKILL.md`'s Stop boundaries already forbid. Where naming that stack's
own known-pattern defects would need specialized knowledge this skill
does not carry, recommend delegation instead of guessing, per
[grading-procedure.md](grading-procedure.md#delegation-recommendation-the-second-party-extended).

## Domain placement

Applies only once Gate vs. no gate above has already concluded a
deterministic gate is warranted, and Gate vs. infrastructure-owned
deterministic control above has left a repository-authored realization in
scope. For a policy with no repository-authored gate yet -- the
proposed-policy case -- an infrastructure-owned outcome ends the
mechanism-fit test there: there is nothing to place. For a policy whose
repository-authored gate already exists -- the reviewing-an-artifact case
-- that outcome never ends anything: the existing gate is still placed
here and still graded through Procedure steps 3-5, because reassigning
which control is primary neither removes that gate nor excuses grading
it. A deterministic gate can, in principle,
be realized in any of the four domains named in `SKILL.md`'s Scope
section. Before grading a specific realization's own quality, check that
its domain placement is actually the right one -- a well-implemented gate
in the wrong domain is not fixed by polishing its implementation further,
the same way a well-written skill that should have been a hook is not
fixed by improving its prose.

Six criteria, applied together rather than any single one in isolation:

1. **Reversibility window.** Place the check at the earliest domain where
   the wrong action is still cheaply reversible. A domain that only
   observes the damage after it is already irreversible is too late,
   regardless of how clean that domain's own implementation would be --
   e.g., a policy about an action a live session is about to take
   belongs where it can still be blocked before it happens, not only
   detected afterward.
2. **Capability match.** A domain that structurally cannot perform the
   I/O a check needs (a live remote lookup, access to a specific
   credential, visibility into a specific event payload) cannot own that
   check, independent of timing -- no amount of reversibility-window
   advantage compensates for a domain that is simply unable to do the
   work.
3. **Credential/trust asymmetry.** Pair an earlier, lower-credential
   domain that can safely fail open (because nothing irreversible has
   happened yet) with a later domain that holds guaranteed credentials
   and can fail closed as the actual backstop -- neither alone is
   sufficient where both properties are needed.
4. **Tool-surface availability.** Place the check at whichever domain
   actually exposes a chokepoint for the guarded action. If only one
   domain's own tool surface can even observe the action in question,
   domain placement is not really a choice -- it is already determined.
5. **Precedent reuse, adapted for local constraints.** Prefer a placement
   a comparable, already-battle-tested gate already uses elsewhere --
   in the target repository itself, or in a sibling/upstream repository
   whose own precedent is cited and attributed rather than re-derived
   from scratch -- adjusted for constraints the precedent's own origin
   did not have.
6. **Prose-rule-to-gate mapping, by action kind.** As a starting
   heuristic, not a rigid rule: rules about *live agent-session actions*
   tend to map to the agent-harness-hook domain, since they require an
   active session to evaluate; rules about *repository/file state* tend
   to map to the CI-job-step domain (or a git hook), since they do not
   require an active session; rules about *aggregate, noisy signals over
   time* tend to map to scheduled/advisory CI, deliberately non-blocking
   rather than gating a single event.

Two additional, secondary criteria:

- **Zero-I/O gates are structurally safer.** A pure local predicate --
  no network call, no filesystem read outside its own inputs -- has no
  INDETERMINATE state to fail open or closed on at all. Prefer a
  zero-I/O realization where one is genuinely sufficient, since it
  removes an entire class of fail-open/fail-closed judgment calls.
- **Staged rollout.** A new gate can start advisory (observed, logged,
  non-blocking) and be promoted to blocking once proven clean on real
  traffic, rather than the placement-and-strictness decision being
  binary from day one.

## What this framework does not cover

These six criteria do not, on their own, state a general principle for
"does this policy need a backstop in a domain-independent context because
its primary realization is specific to one agent-harness or one client,
and a different client or a direct-to-repository change could bypass it
entirely." That property can hold incidentally for a gate justified on
credential/reversibility grounds alone (criterion 3), without ever being
argued on client-independence grounds specifically. Applying this
framework does not by itself answer whether a given policy needs
independent, client-agnostic coverage -- that question is the
[Reproducibility / Domain-coverage axis](../SKILL.md#axis-reproducibility--domain-coverage)'s
job, not this test's.

Nor does it decide how strong a specific realization's control is on an
external Foundation/Enterprise/Advanced maturity ladder, or whether that
strength is honestly claimed for its category -- that classification is
the [Security-level / Zero-Trust maturity classification
axis](../SKILL.md#axis-security-level--zero-trust-maturity-classification)'s
job, not this test's own, even though criteria 1 and 3 above already
reason in the same impossible-vs-tedious terms that axis names explicitly.

Gate vs. infrastructure-owned deterministic control borrows that same
test outright as its decision procedure, and still does not become that
axis: it consumes the impossible-vs-tedious distinction to decide *which
party owns a policy*, and stops there. It emits no
Foundation/Enterprise/Advanced label, no floor / tier-scalable
classification, and no honesty claim about a target's own ceiling
documentation.

It also grades no control's mechanics, and -- unlike a wrong-domain
finding, which at least names a domain this skill does grade -- an
infrastructure control is by construction not one of the four
realization domains, so `SKILL.md` Procedure step 1's discovery never
reaches it and no dimension in `dimensions.md` is ever applied to it.
Nothing downstream closes that gap. A finding that promotes such a
control to primary owner therefore states plainly that the promoted
owner is itself ungraded by this review, rather than leaving a reader to
assume some later step graded it. Grading it at all means a separate
review, on whatever framework actually covers that platform -- a
delegation recommendation, per
[grading-procedure.md](grading-procedure.md#delegation-recommendation-the-second-party-extended),
not a step of this test. Nor does it characterize the
calling/installing repository's general infrastructural footing across
the four domains: that is dimension 23's own once-per-review question,
asked regardless of any single policy, where this one is asked per
policy and is answered by naming one concrete control, not by scoring an
environment.

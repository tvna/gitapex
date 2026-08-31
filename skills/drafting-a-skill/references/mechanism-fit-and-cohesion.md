# Cohesion and shared-script-parent policy: ownership boundaries

Loaded when Step 3's cohesion self-check or Step 5's domain-gap sweep is
not already an obvious call -- for example, a drafted Step touches
multiple loosely-related outcomes and it isn't clear whether that's one
skill or two. This file exists because two of this skill's own Steps sit
close enough to `evaluating-skill-quality`'s own review procedure that
the boundary has to be stated explicitly, not left to be inferred from
each Step's own one-line description.

`eliciting-a-design` owns the redirect-target judgment this file once
carried for `drafting-a-skill`'s own former Step 2 (see
<https://github.com/tvna/gitapex/issues/1619>: the Agentic operation
mechanism-fit vehicle-selection gate, including the "this isn't a skill,
redirect to X instead" criteria, moved upstream into that skill entirely)
-- see that skill's own body for the current version of that judgment,
not this file.

## Contents

1. [Step 3 and Step 5 are advisory, not a second grading](#step-3-and-step-5-are-advisory-not-a-second-grading)
2. [Shared bundled-script parent: a placement policy](#shared-bundled-script-parent-a-placement-policy)

## Step 3 and Step 5 are advisory, not a second grading

`evaluating-skill-quality`'s own rubric states plainly, for the cohesion
check: "This check has exactly one owner, per Contract discipline's
'never both' rule: it decides the whole-artifact boundary once, here."
And for its own Blind spot pass: it runs as "a precondition step
(`SKILL.md`'s Procedure step 2, alongside the Agentic operation mechanism-fit checks)" of
`evaluating-skill-quality`'s own procedure -- not a step this skill could
duplicate without also duplicating that ownership.

Step 3 (cohesion) and Step 5 (domain-gap sweep) exist anyway, for a
narrower reason than "grade this against the rubric": a draft with an
obvious split or an obvious blind spot, caught here, avoids a wasted round
trip to `evaluating-skill-quality`'s own review and back. Both Steps are
therefore advisory self-checks only, per the phrasing rule `SKILL.md`
already states at each Step directly -- not repeated here a third time,
since this section's own job is the ownership rationale above (why the
rubric's exact-owner language applies), not the output-format instruction
itself.

Practically, this means Step 3 borrows `evaluating-skill-quality`'s own
seven-way cohesion taxonomy (functional / sequential / communicational /
procedural / temporal / logical / coincidental, from Stevens/Myers/
Constantine, extended by Yourdon and Constantine) as a lens for looking at
the draft, and Step 5 asks the same shape of question the Blind spot pass
asks ("does this target's specific domain expose a quality concern no
generic check would catch") -- without either Step re-deriving or
restating a verdict evaluating-skill-quality will produce on its own
authority moments later.

## Shared bundled-script parent: a placement policy

A drafted skill sometimes needs a bundled script another skill's
`scripts/` directory already provides, or is itself the first skill that
would need to bundle a script a second skill will later also want. This
repository has no single rule requiring registration of every such
sharing decision, but does have a stated policy for picking a "parent"
when the need arises, adapted from three primary software-engineering
sources rather than invented for this skill:

1. **Stability first, warning-only.** Robert C. Martin's Stable
   Dependencies Principle says a shared dependency should be at least as
   stable as its dependents. No skill in this repository currently
   declares `lifecycle: stable` explicitly (only `experimental` is ever
   declared; stable is today's implicit default for everything else), so
   a hard gate on this axis would be premature -- treat it as a
   preference, not a blocker, until explicit `stable` declarations become
   common enough to judge readiness against.
2. **Common Closure Principle as tiebreak.** When stability alone doesn't
   settle it, prefer the parent whose own change-closure already includes
   the reason the shared script would need to change -- i.e. the skill
   that already owns the invariant the script checks, per Martin's Common
   Closure Principle (classes that change for the same reason belong
   together).
3. **A neutral, ADR-gated location, as a last resort.** Eric Evans'
   Shared Kernel pattern applies when the cost of coordinating a shared
   change is genuinely lower than the cost of duplicating it -- but Evans
   explicitly cautions against defaulting to a shared kernel. Escalate to
   a neutral location only when tiers 1 and 2 both fail to name a natural
   owner, and record the decision in an ADR (see
   `drafting-an-adr`) rather than placing it silently -- a neutral
   location chosen without a record reads, to the next skill that needs
   the same script, as an arbitrary dumping ground.

`evaluating-skill-quality`'s own bundled checkers
(`gitapex_check_skill_shape.py`, `gitapex_scan_execution_requirements_drift.py`,
which Step 6 runs against every draft) already satisfy this policy under
all three tiers today: that skill is this repository's de facto stable,
closure-consistent owner of "does a skill directory have the right
shape," so Step 6 reaches into its `scripts/` directory rather than
vendoring a copy. This policy's own future blocking-gate threshold, and
whether it should be mechanized into `gitapex_check_skill_shape.py`
itself, are explicitly out of scope here -- deferred to a future issue,
once explicit `stable` declarations are common enough in this repository
to judge readiness (see this skill's own `metadata/gitapex.yaml`
`references` decision log, `kind: elision`).

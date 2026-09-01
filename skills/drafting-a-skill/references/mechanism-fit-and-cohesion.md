# Cohesion and shared-script-parent policy: ownership boundaries

Loaded when Step 3's cohesion self-check or Step 5's domain-gap sweep is not already an obvious call -- for example, a drafted Step touches multiple loosely-related outcomes and it isn't clear whether that's one skill or two. This file exists because two of this skill's own Steps sit close enough to `evaluating-skill-quality`'s own review procedure that the boundary has to be stated explicitly, not left to be inferred from each Step's own one-line description.

The redirect-target judgment this file once carried for `drafting-a-skill`'s own former Step 2 -- the Agentic operation mechanism-fit vehicle-selection gate, including the "this isn't a skill, redirect to X instead" criteria -- no longer lives in this file: it moved upstream entirely, into a sibling skill. See this skill's own `references/gitapex-cross-links.md` for which sibling skill owns that judgment's current version and for the tracking issue recording the move.

## Contents

1. [Step 3 and Step 5 are advisory, not a second grading](#step-3-and-step-5-are-advisory-not-a-second-grading)
2. [Shared bundled-script parent: a placement policy](#shared-bundled-script-parent-a-placement-policy)

## Step 3 and Step 5 are advisory, not a second grading

`evaluating-skill-quality`'s own rubric states plainly, in its own text, that the cohesion check has exactly one owner -- per Contract discipline's never-both rule, it decides the whole-artifact boundary once, there -- and that its own Blind spot pass runs as a precondition step of that skill's own procedure, alongside its Agentic operation mechanism-fit checks -- not a step this skill could duplicate without also duplicating that ownership. The rubric file stating this, and its exact quoted wording, are cited in this skill's own `references/gitapex-cross-links.md`.

Step 3 (cohesion) and Step 5 (domain-gap sweep) exist anyway, for a narrower reason than "grade this against the rubric": a draft with an obvious split or an obvious blind spot, caught here, avoids a wasted round trip to `evaluating-skill-quality`'s own review and back. Both Steps are therefore advisory self-checks only, per the phrasing rule `SKILL.md` already states at each Step directly -- not repeated here a third time, since this section's own job is the ownership rationale above (why the rubric's exact-owner language applies), not the output-format instruction itself.

Practically, this means Step 3 borrows `evaluating-skill-quality`'s own seven-way cohesion taxonomy (functional / sequential / communicational / procedural / temporal / logical / coincidental, from Stevens/Myers/ Constantine, extended by Yourdon and Constantine) as a lens for looking at the draft, and Step 5 asks the same shape of question the Blind spot pass asks ("does this target's specific domain expose a quality concern no generic check would catch") -- without either Step re-deriving or restating a verdict evaluating-skill-quality will produce on its own authority moments later.

## Shared bundled-script parent: a placement policy

A drafted skill sometimes needs a bundled script another skill's `scripts/` directory already provides, or is itself the first skill that would need to bundle a script a second skill will later also want. This repository has no single rule requiring registration of every such sharing decision, but does have a stated policy for picking a "parent" when the need arises, adapted from three primary software-engineering sources rather than invented for this skill:

1. **Stability first, warning-only.** Robert C. Martin's Stable Dependencies Principle says a shared dependency should be at least as stable as its dependents. When the target repository has too few explicit `lifecycle: stable` declarations to judge this axis meaningfully, a hard gate would be premature -- treat it as a preference, not a blocker, until explicit `stable` declarations become common enough to judge readiness against (see this skill's own `references/gitapex-cross-links.md` for this repository's current census).
2. **Common Closure Principle as tiebreak.** When stability alone doesn't settle it, prefer the parent whose own change-closure already includes the reason the shared script would need to change -- i.e. the skill that already owns the invariant the script checks, per Martin's Common Closure Principle (classes that change for the same reason belong together).
3. **A neutral, ADR-gated location, as a last resort.** Eric Evans' Shared Kernel pattern applies when the cost of coordinating a shared change is genuinely lower than the cost of duplicating it -- but Evans explicitly cautions against defaulting to a shared kernel. Escalate to a neutral location only when tiers 1 and 2 both fail to name a natural owner, and record the decision in an ADR (see `drafting-an-adr`) rather than placing it silently -- a neutral location chosen without a record reads, to the next skill that needs the same script, as an arbitrary dumping ground.

When the drafted skill's Step 6 checkers are already bundled by `evaluating-skill-quality` (gitapex's own name for this role; if the calling repository has no same-named skill, treat this as an illustrative pointer and substitute that repository's own skill filling the same role instead), that owner already satisfies this policy under all three tiers -- see this skill's own `references/gitapex-cross-links.md` for the repository-state census, the exact script names, and the mechanization-deferral record behind that claim.

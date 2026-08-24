# Mechanism fit and cohesion: ownership boundaries

Loaded when Step 2's gate, Step 5's cohesion self-check, or Step 7's
domain-gap sweep is not already an obvious call -- for example, the
candidate plausibly fits more than one mechanism, or a drafted Step
touches multiple loosely-related outcomes and it isn't clear whether
that's one skill or two. This file exists because three of this skill's
own Steps sit close enough to `evaluating-skill-quality`'s own review
procedure that the boundary has to be stated explicitly, not left to be
inferred from each Step's own one-line description.

## Contents

1. [Step 2's redirect targets, named](#step-2s-redirect-targets-named)
2. [Step 5 and Step 7 are advisory, not a second grading](#step-5-and-step-7-are-advisory-not-a-second-grading)
3. [Shared bundled-script parent: a placement policy](#shared-bundled-script-parent-a-placement-policy)

## Step 2's redirect targets, named

Step 2's own gate (in `SKILL.md`) lists four criteria for "this isn't a
skill." Each has a concrete destination, not a vague "consider a
different mechanism":

- **Unconditionally-reliable action, or an absolute prohibition** -->
  `evaluating-deterministic-gate-quality`. That skill owns hook/CI-gate
  placement and design -- "deciding which of several possible mechanisms
  should own a new policy" is explicitly named in its own description.
  This skill does not write hooks itself (see `SKILL.md`'s Stop
  boundaries); it stops at naming the redirect.
- **Always-true fact, for a CLAUDE.md-shaped need** --> CLAUDE.md
  directly, if the target is the root or a subdirectory instruction
  file.
- **Always-true fact or absolute rule, for a Subagent definition, Output
  style, system-prompt-append configuration, or Auto-memory-shaped
  need** --> `evaluating-context-channel-maturity`. That skill's own
  description states the mirror-image relationship directly: "criterion
  3 mirrors evaluating-skill-quality's own Mechanism-fit check from the
  opposite artifact -- that skill asks whether a SKILL.md candidate
  should be one of these channels instead; this skill asks whether
  content already living in one of these channels should be a skill
  instead." This skill is that first question, asked from the SKILL.md
  side; `evaluating-context-channel-maturity` is the second, asked from
  the channel side. Route a non-hook, non-CLAUDE.md channel-shaped need
  there rather than guessing at that skill's own placement rules.
- **Side task with results never referenced again** --> a subagent
  dispatch inside whatever procedure needed the side task, not a new
  skill of its own.

## Step 5 and Step 7 are advisory, not a second grading

`evaluating-skill-quality`'s own rubric states plainly, for the cohesion
check: "This check has exactly one owner, per Contract discipline's
'never both' rule: it decides the whole-artifact boundary once, here."
And for its own Blind spot pass: it runs as "a precondition step
(`SKILL.md`'s Procedure step 2, alongside the Mechanism fit checks)" of
`evaluating-skill-quality`'s own procedure -- not a step this skill could
duplicate without also duplicating that ownership.

Step 5 (cohesion) and Step 7 (domain-gap sweep) exist anyway, for a
narrower reason than "grade this against the rubric": a draft with an
obvious split or an obvious blind spot, caught here, avoids a wasted round
trip to `evaluating-skill-quality`'s own review and back. Both Steps are
therefore advisory self-checks only, per the phrasing rule `SKILL.md`
already states at each Step directly -- not repeated here a third time,
since this section's own job is the ownership rationale above (why the
rubric's exact-owner language applies), not the output-format instruction
itself.

Practically, this means Step 5 borrows `evaluating-skill-quality`'s own
seven-way cohesion taxonomy (functional / sequential / communicational /
procedural / temporal / logical / coincidental, from Stevens/Myers/
Constantine, extended by Yourdon and Constantine) as a lens for looking at
the draft, and Step 7 asks the same shape of question the Blind spot pass
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
which Step 8 runs against every draft) already satisfy this policy under
all three tiers today: that skill is this repository's de facto stable,
closure-consistent owner of "does a skill directory have the right
shape," so Step 8 reaches into its `scripts/` directory rather than
vendoring a copy. This policy's own future blocking-gate threshold, and
whether it should be mechanized into `gitapex_check_skill_shape.py`
itself, are explicitly out of scope here -- deferred to a future issue,
once explicit `stable` declarations are common enough in this repository
to judge readiness (see this skill's own `SKILL.md` Non-goals).

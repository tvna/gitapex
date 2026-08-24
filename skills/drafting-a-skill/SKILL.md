---
name: drafting-a-skill
description: Use when authoring a brand-new Claude Code skill from a blank page. Gates on Mechanism fit before drafting begins, mandatorily elicits every user-selectable metadata choice from the requester, drafts using Design-by-Contract structure, runs advisory cohesion and domain-gap self-checks, passes this repository's own deterministic shape and execution-requirements-drift checkers, and hands off to evaluating-skill-quality and battle-testing-a-skill for the authoritative review. gitapex-native successor to obra/superpowers' writing-skills and to Anthropic's skill-creator. Distinct from scorer-gated-skill-edits (iterates an existing SKILL.md across measured trials; never authors a new one) and evaluating-skill-quality (grades a finished, static artifact; this skill owns the formative decisions made while the draft is still being written).
---

# Drafting a Skill

Turns a candidate skill idea into a shape-checked, self-reviewed draft
`SKILL.md` (plus its `references/` and `metadata/gitapex.yaml`) ready for
`evaluating-skill-quality` and `battle-testing-a-skill` to independently
review. This skill owns "how should this be" -- the formative decisions
made while a draft is still being written. `evaluating-skill-quality`
owns "is this OK to ship" -- a gate applied once to a finished, static
artifact. The two are separate bounded contexts and never grade the same
question twice: see `references/mechanism-fit-and-cohesion.md` for the
two places (cohesion, domain-gap coverage) where this skill's own Steps
sit close enough to that boundary that it has to be stated explicitly.

## Precondition

A genuine drafting need: the requester wants a brand-new `SKILL.md`
written from nothing. If the target already exists, this is
`scorer-gated-skill-edits`'s job, not this skill's -- it does not loop
back into iterative editing once a first draft is done (see Postcondition
and Related skills). If the target is already a finished draft awaiting
judgment, route directly to `evaluating-skill-quality`/
`battle-testing-a-skill` instead of re-entering at Step 1.

## Steps

1. **Capture the candidate's job, in the requester's own words.** One
   sentence: what triggers it, what it does, what it hands back. Don't
   infer or embellish -- this raw statement is what Step 2 gates and Step
   4 formalizes, and it's the loop-back target if Step 5 later finds the
   draft trying to do two jobs at once.

2. **Mechanism-fit gate.** Before drafting anything, check the candidate
   against four criteria adapted from `evaluating-skill-quality`'s own
   Mechanism-fit check (`references/rubric.md`, itself citing Anthropic's
   ["Steering Claude Code"][steering] guidance). A hit on any row blocks
   continuation on its own, regardless of how well later Steps would
   otherwise go -- this gate's finding is reported ahead of every later
   Step's finding, mirroring that same precedent
   ("A wrong-mechanism ... finding ... is not folded into the
   well-formed/mature ladder: report it as the review's headline finding
   regardless of how the rest of the review scores").

   **Don't draft a skill for:**
   - An **unconditionally-reliable action** ("every time X, always do
     Y" -- a formatter after every edit). "The model choosing to run a
     formatter is different from the formatter running automatically."
     Redirect to a hook -- see `references/mechanism-fit-and-
     cohesion.md`'s "Step 2's redirect targets" for exactly where.
   - An **absolute prohibition** ("never do this," where failure under
     pressure or injection is unacceptable). "A real guardrail needs to
     be deterministic, and the enforcement methods are hooks and
     permissions." Same redirect as above.
   - An **always-true fact** Claude should hold every session, not only
     when this skill is invoked. "Procedures belong in skills. CLAUDE.md
     is for facts Claude should hold all the time." Redirect to CLAUDE.md
     directly, or to the channel-specific redirect target for a
     Subagent/Output-style/system-prompt-append/Auto-memory candidate.
   - A **side task whose results are never referenced again.** "Use a
     subagent when a side task ... would clutter your main conversation
     with intermediate results you won't reference again." That's a
     subagent dispatch inside whatever procedure needed it, not a new
     skill.

   **Create when**, by contrast: a multi-step procedure a human wants to
   see play out and steer, not intuitively obvious on its own, reusable
   rather than a one-off, and general rather than one project's own local
   convention.

   This skill does not write hooks, and does not itself decide CLAUDE.md/
   subagent placement -- see Stop boundaries.

3. **Elicit every user-selectable metadata choice.** One `AskUserQuestion`
   round, up to four questions, never inferred:
   - **Portability** -- `Portable` (works unmodified if vendored to
     another repository), `Repository-scoped` (hardcodes this
     repository's own conventions), or `Mixed` (partial dependency: some
     Steps portable, one or two Steps name a repository-specific tool or
     path).
   - **Capability assumption** -- `Broad` (must give a weak/economical
     model enough guidance directly, not only via on-demand references),
     `Frontier` (assumes a strong-reasoning model; no weak-tier bar),
     or `Adaptive` (a lean body for a strong model, with a weak tier's
     needs met by `references/` material it pulls on demand).
   - **Invocation mode** -- both model- and user-invocable (the default),
     or narrowed via the `disable-model-invocation`/`user-invocable`
     frontmatter booleans when an irreversible-operation skill should
     never trigger autonomously.
   - **Lifecycle** -- `experimental` (name a `trackingIssue`, its full
     URL, and what graduating to `stable` requires), `stable`, or
     `deprecated` (name a `replacement`).
   See `references/tacit-knowledge-elicitation.md` for why elicitation is
   mandatory (a prior skill was once declared `Frontier` by reviewer
   assumption with no pin anywhere to justify it) and for phrasing
   guidance beyond the options above. A follow-up round runs only if a
   later Step's own content contradicts an earlier answer -- see that
   same file's "Follow-up round" section for the worked example.

4. **Draft using Design-by-Contract structure.** Three parts: a
   **Precondition** (checkable facts that must hold before Step 1 of the
   *drafted* skill begins -- a caller obligation, not scene-setting
   prose), the **Steps** (the routine body -- each may assume the
   Precondition already holds, and must never re-check it), and a
   **Postcondition** (what the drafted skill guarantees once its Steps
   finish, matching what its last Step actually hands off). Never state
   the same condition in both the Precondition and a Step's own
   `if`-guard -- pick exactly one owner for it. See
   `references/contract-structure.md` for the fault-attribution rule
   (a Precondition violation is the caller's bug; a Postcondition
   violation is the drafted skill's own bug) and worked examples. Also
   load `references/guidance-form-and-sdo.md` (unconditional, alongside
   `references/formative-quality-dimensions.md`) for how each Step should
   read.

5. **Cohesion self-check.** Ask, for the whole draft and for each Step:
   *can its one outcome be named in one sentence, with no "and"?* A Step
   doing two things ("extract the criteria and decide whether to
   rebase") needs splitting into two Steps; a whole draft doing two
   things ("summarize a diff" and, separately, "decide whether to
   auto-merge it") needs splitting into two skills -- route back to Step
   1 for the second one rather than forcing one `SKILL.md` to cover both.
   `references/guidance-form-and-sdo.md` names this the Single Decisive
   Outcome (SDO) test and `references/mechanism-fit-and-cohesion.md`
   gives the deeper seven-way cohesion taxonomy (functional / sequential
   / communicational / procedural / temporal / logical / coincidental)
   for a borderline case the one-sentence test alone doesn't settle.
   This is an **advisory self-check, not a second authoritative
   grading** -- `evaluating-skill-quality`'s own cohesion check "has
   exactly one owner ... it decides the whole-artifact boundary once,"
   at Step 9's handoff. Write a Step 5 finding as "worth splitting before
   handoff," never as a cohesion verdict ("cohesion: pass" is not this
   skill's sentence to write).

6. **Check for collision and reconcile dependencies.** Compare the
   drafted `description:` against every existing skill's own description
   for invocation-timing collision (would a reasonable trigger route to
   both?), and reconcile this draft's own predecessor/successor
   relationships with the skills it names. This is this skill's own job:
   `evaluating-skill-quality` grades one target skill at a time and has
   no cross-skill judgment of its own.

7. **Domain-gap sweep.** Ask explicitly: does this target's own specific
   domain expose a quality concern nothing else in the draft already
   covers -- something a generic checklist wouldn't catch because it's
   particular to *this* subject matter? (For example: a skill drafted to
   summarize `curl` commands needs an explicit "never execute, only
   explain" boundary that no generic Step already states -- the domain
   itself, not a generic dimension, is what surfaces that gap.) This is a
   targeted, domain-aware pass, distinct from the generic dimensions
   Step 9's handoff will apply. Like Step 5, this is **advisory only**:
   `evaluating-skill-quality`'s own Blind spot pass runs as a
   precondition step of its own procedure regardless of what this Step
   already found, and stays the authoritative pass. Write a Step 7
   finding as "worth covering before handoff," never as "blind spot:
   none."

8. **Run this repository's own deterministic checkers** against the
   draft directory: `gitapex_check_skill_shape.py` and
   `gitapex_scan_execution_requirements_drift.py` (see
   `references/gitapex-cross-links.md` for exact invocation, gitapex-repo
   only). Fix every finding before Step 9 -- Step 9's handoff does not
   run either checker itself.

9. **Hand off to both `evaluating-skill-quality` and
   `battle-testing-a-skill`**, each as an independent, fresh dispatch.
   This skill's own job ends at a shape-checked, self-reviewed draft; it
   never performs either downstream skill's own review in their place,
   and never grades its own draft as passing.

## Postcondition

A draft `SKILL.md` (plus `references/` and `metadata/gitapex.yaml`) that:
passed Step 2's gate with no blocking finding; carries every metadata
choice Step 3 elicited, none inferred; is structured as a real contract
per Step 4; has no Step 5/7 finding left unresolved (either fixed or
explicitly deferred with a stated reason); collides with no existing
skill's own description per Step 6; and passes both Step 8 checkers
clean. It is **not** a shipped or merged skill on its own authority --
that determination is `evaluating-skill-quality`'s and
`battle-testing-a-skill`'s own, produced fresh at Step 9.

## Output

- The draft `SKILL.md`, its `references/` files, and `metadata/
  gitapex.yaml`.
- Step 3's elicited metadata choices, and any follow-up-round resolution.
- Step 5/7's advisory findings and how each was resolved (fixed in the
  draft, or explicitly deferred with a stated reason -- never silently
  dropped).
- Step 6's collision/dependency findings.
- Step 8's checker output (clean, or fixed and re-run clean).
- **Next Move:** the concrete handoff -- which of `evaluating-skill-
  quality`/`battle-testing-a-skill` runs next, or both in parallel.

## Worked example

A requester wants a skill that reads a pasted `curl` command and explains
what it does in plain English, no execution. Step 1: "given a pasted
`curl` command, explain in one paragraph what request it makes -- no
execution." Step 2: not an unconditionally-reliable action, not a
prohibition, not an always-true fact, not a side task with unreferenced
results -- passes the gate, drafting continues. Step 3: elicited
Portable (no repository-specific dependency), Adaptive (a lean body
covers this fully; no weak-tier bar concern for a single-paragraph
explanation task), default invocation, experimental. Step 4: Precondition
"a `curl` command is present in the request"; Steps parse flags, describe
the method/URL/headers/body; Postcondition "one paragraph, no execution."
Step 5: one outcome ("explain the request"), passes the SDO test, no
split needed. Step 6: no existing skill's description collides. Step 7:
domain gap found -- nothing yet states what to do with a flag that
reads a secret from a file (`-H "Authorization: Bearer $(cat token)"`);
added an explicit "never print a secret's own value, name only which
flag reads one" boundary. Step 8: both checkers run clean. Step 9: handed
off to `evaluating-skill-quality` and `battle-testing-a-skill`.

## Stop boundaries

- Never skip Step 2's gate under time pressure, or treat a Step 2 finding
  as one input among several -- it blocks on its own.
- Never write a hook, edit CLAUDE.md, or author a Subagent/Output-style/
  system-prompt-append/Auto-memory file to satisfy a Step 2 finding --
  name the redirect and stop; the receiving skill or mechanism owns the
  actual authoring.
- Never infer Step 3's metadata choices from a similar existing skill, a
  default, or context -- elicit them, every time.
- Never treat Step 5's cohesion finding or Step 7's domain-gap finding as
  the authoritative verdict on cohesion or domain coverage -- both are
  advisory self-checks that change what gets drafted, never a substitute
  for `evaluating-skill-quality`'s own pass at Step 9.
- Never perform Step 9's own review or adversarial probing as part of
  this skill -- both stay `evaluating-skill-quality`'s and
  `battle-testing-a-skill`'s own jobs, named only as the handoff.
- Never loop back into `scorer-gated-skill-edits`-shaped iterative editing
  once a first draft exists -- that is a separate skill's job, entered
  fresh, not a continuation of this one.

## Related skills

- **vs. `evaluating-skill-quality`:** DDD bounded-context split --
  drafting owns "how should this be" (formative, mid-write); evaluating
  owns "is this OK to ship" (a gate on a finished artifact). Two Steps sit
  close enough to that boundary to need explicit disclosure -- see
  `references/mechanism-fit-and-cohesion.md`. This skill also
  `skillDependencies.requires` that skill directly: Step 8 mandatorily
  invokes its bundled checker scripts, and Step 2's gate content is
  adapted from its rubric, so this skill's own procedure cannot function
  without it existing.
- **vs. `battle-testing-a-skill`:** a Step 9 handoff target for
  adversarial, hostile-input probing -- never performed by this skill
  itself.
- **vs. `scorer-gated-skill-edits`:** that skill iterates an *existing*
  `SKILL.md` across repeated measured trials; this skill only authors
  from a blank page and does not loop -- once a first draft exists (this
  skill's own Postcondition), further measured iteration is that skill's
  job to pick up, not this skill's to continue.
- **vs. `evaluating-deterministic-gate-quality` /
  `evaluating-context-channel-maturity`:** Step 2's two concrete redirect
  targets, for a hook/CI-gate-shaped need and a CLAUDE.md/subagent/
  output-style/system-prompt-append/Auto-memory-shaped need respectively
  -- see `references/mechanism-fit-and-cohesion.md`.
- **vs. `drafting-an-acm-issue`:** a related but separate authoring
  skill, for a GitHub issue carrying an Acceptance Criteria Map rather
  than a skill directory; named in `skillDependencies.relatedTo` because
  a design session that produces a skill's own drafted content often
  produces its tracking issue through that skill first.
- **vs. `planning-a-branch-from-an-issue` / `executing-a-branch-plan`:**
  this is the authoring method either skill routes to whenever an
  Acceptance Criteria Map's planned ops include a new `SKILL.md` -- see
  each skill's own Related-skills section for its bullet naming this one.

## Notes

Portability: **Mixed**. Steps 1, 3, 4, 6, 7, and 9 depend on no
repository-specific tooling; Step 8's checker invocations and Step 2's
`references/mechanism-fit-and-cohesion.md` redirect targets are
gitapex-specific (a vendored copy substitutes its own equivalents where
they exist, per `references/gitapex-cross-links.md`'s own opening note).

Capability assumption: **Broad**, the repository owner's explicit choice
(over this skill's own initial `Adaptive` declaration) once this skill's
own Step 3 was applied self-referentially. Every Step's core judgment
call -- the four Mechanism-fit criteria (Step 2), the four metadata axes'
own option lists (Step 3), the Design-by-Contract definitions (Step 4),
the Single Decisive Outcome test (Step 5), and a concrete domain-gap
example (Step 7) -- is stated directly in this body rather than left for
a weak or economical model to find only by following a reference-file
pointer, satisfying dimension 9's Broad bar ("the skill must give a weak
tier *enough* guidance, and failing to do so is a real, gradeable gap,
not an unmeasured one," `references/rubric.md`'s own Capability
assumption section) directly rather than through Adaptive's alternate
"met by references on demand" path. The five `references/` files still
exist and are still loaded per the same progressive-disclosure structure
(dimension 5's own grading is unchanged by the Broad/Adaptive choice) --
they carry elaboration, worked sub-examples, and deeper rationale beyond
this body's own floor, not the floor itself. This body's own length grew
accordingly (from 249 to a still well-under-ceiling line count against
`gitapex_check_skill_shape.py`'s `BODY_MAX_LINES`) -- dimension 2 grades
this leniently under Broad ("explanation that would be redundant for a
strong model is not automatically sprawl... when the declared target
plausibly still needs it"), so long as no sentence above is a true
duplicate of another rather than a genuinely new, weak-tier-necessary
restatement.

Lifecycle: **experimental**, tracking
<https://github.com/tvna/gitapex/issues/1194> -- pending
`evaluating-skill-quality` and `battle-testing-a-skill` review verdicts
before graduating to stable.

Attribution, not a live dependency: Step 2's "Create when / Don't create
for" list shape follows `writing-skills`' own established structure for
this kind of gate. That skill is vendored from `obra/superpowers`, which
this repository is retiring -- Step 2's shape is written out directly in
this file rather than cited, so it survives that retirement unchanged;
`writing-skills` is credited here for the shape's origin, not declared as
a dependency (it isn't a native `skills/*/` skill, and a vendored,
soon-removed file is not something this skill's own procedure can safely
lean on). Anthropic's `skill-creator` is named in `SKILL.md`'s own
frontmatter only as a rejected source for its benchmark loop, automated
description-optimization loop, and `.skill`-file packaging -- understood
from that skill's own installed description, not independently verified
against its primary source from inside this repository, and not imported
here regardless.

[steering]: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more "Anthropic -- Steering Claude Code: skills, hooks, subagents and more"

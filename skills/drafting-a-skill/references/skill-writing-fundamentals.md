# Skill Writing Fundamentals

Required reading on the in-repo ordinary path -- `SKILL.md`'s own Step 6
sweeps this file's Formative quality dimensions section unconditionally,
and Steps 2, 3, and Non-goals cite its other three sections directly.
See this skill's own decision log for why these four sections live in
one file.

## Table of contents

- [Contract structure for a drafted skill](#contract-structure-for-a-drafted-skill)
  - [The three parts, applied to a skill](#the-three-parts-applied-to-a-skill)
  - [Fault attribution](#fault-attribution)
  - [Never both](#never-both)
  - [A drafting checklist](#a-drafting-checklist)
- [Guidance form and Single Decisive Outcome (SDO)](#guidance-form-and-single-decisive-outcome-sdo)
  - [Guidance form](#guidance-form)
  - [Single Decisive Outcome (SDO)](#single-decisive-outcome-sdo)
- [Cohesion and shared-script-parent policy: ownership boundaries](#cohesion-and-shared-script-parent-policy-ownership-boundaries)
  - [Step 3 and Step 5 are advisory, not a second grading](#step-3-and-step-5-are-advisory-not-a-second-grading)
  - [Shared bundled-script parent: a placement policy](#shared-bundled-script-parent-a-placement-policy)
- [Formative quality dimensions](#formative-quality-dimensions)
  - [1. Name and description legibility](#1-name-and-description-legibility)
  - [2. Economy of words](#2-economy-of-words)
  - [3. Explicit freedom vs. constraint](#3-explicit-freedom-vs-constraint)
  - [4. Structural legibility](#4-structural-legibility)
  - [5. Load-bearing vs. on-demand split](#5-load-bearing-vs-on-demand-split)
  - [6. Stability of claims](#6-stability-of-claims)
  - [7. Script necessity and minimalism](#7-script-necessity-and-minimalism)
  - [8. Eval preparation](#8-eval-preparation)
  - [9. Model-agnostic phrasing](#9-model-agnostic-phrasing)
  - [How to use this section while drafting](#how-to-use-this-section-while-drafting)

## Contract structure for a drafted skill

This file exists so a draft's Precondition, Steps, and Postcondition are
written as a real contract, in Bertrand Meyer's Design by Contract sense
of the term -- the same framing the review that later grades a draft
already applies to itself, in its own Contract discipline section; see
this skill's own `references/gitapex-cross-links.md` for the exact
sibling-skill citation this shared framing depends on. Drafting and
reviewing are separate bounded contexts (see this skill's own
`SKILL.md`), but they share one vocabulary for what a contract is, so a
drafted skill and the review that later grades it are talking about the
same thing.

### The three parts, applied to a skill

- **Precondition** -- what must already be true before Step 1 begins, stated as one or a few checkable bullets, not scene-setting prose. This is the caller's (the invoking agent's, or the human directing it) obligation: if the Precondition doesn't hold and the skill is invoked anyway, that is a misuse, not a defect in the skill.
- **Steps** -- the routine body. Each Step is one action plus the local reasoning a reader needs to execute it correctly; it may assume everything the Precondition already established, and must not re-derive it.
- **Postcondition** -- what the skill guarantees once its Steps finish, stated so a caller can rely on it without re-reading the Steps. Write this to match what the skill's own last Step actually hands off, not an aspirational description of what a "good" run would produce.

An **Invariant** (something that stays true across every Step, not only at the boundaries) is optional -- most procedural skills don't need one. Declare it only when a real cross-step invariant exists (for example, "the target skill directory is never partially written to disk between Steps"), not as boilerplate.

### Fault attribution

The shared Design-by-Contract source this framing rests on (see this skill's own `references/gitapex-cross-links.md` for the sibling-skill citation this quote is taken from) states this principle directly: "A precondition violation indicates a bug in the client (caller). ... A postcondition violation is a bug in the supplier (the routine)." Applied to a drafted skill: if a run fails because the Precondition didn't actually hold (the skill was invoked for the wrong kind of request), that is a bug in how the request was routed to this skill -- fix the routing or the Precondition's own wording, not the Steps. If a run fails despite the Precondition genuinely holding, that is a bug in the Steps themselves. Write the Precondition precisely enough that this distinction is checkable, not a matter of judgment after the fact.

### Never both

Also from that same shared source (again, `references/gitapex-cross-links.md` carries the sibling-skill citation), stated as "an absolute rule": a condition is checked in exactly one place -- "either you have the condition in the [precondition], or you have it in an If instruction in the [routine's] body ... but never in both." A redundant re-check is not extra safety; it is a sign the responsibility split between Precondition and Steps was never actually decided.

Applied while drafting:

- Don't restate a Precondition bullet as an `if`-guard inside Step 1 -- the Precondition already owns that check. A Step that re-verifies its own Precondition is hedging against callers it should instead route away at the Precondition boundary.
- Don't bury a real precondition inside a later Step's prose where a reader has to infer it actually applied before Step 1 too. If a condition must hold before the whole procedure starts, it belongs in the Precondition section, not smuggled into the middle of the Steps.
- When two Steps could plausibly both check the same thing (for example, a metadata choice elicited at one Step and silently re-confirmed at another), pick exactly one owner and have the other Step consume that Step's own output instead of re-deriving it. This skill's own Step 3 and Step 5 apply this rule against a different kind of duplication -- see this file's own Cohesion and shared-script-parent policy section below for why those two Steps are written as advisory self-checks rather than a second authoritative judgment of a question `evaluating-skill-quality` already owns exclusively.

### A drafting checklist

Before treating a draft's contract shape as done:

1. Does the Precondition state checkable facts, not narrative context?
2. Does any Step re-check something the Precondition already established? If so, drop the re-check or move the condition down into the Precondition -- never keep both.
3. Does the Postcondition match what the last Step actually produces, word for word in substance -- not a rounder, more optimistic summary of it?
4. If an Invariant is declared, is it genuinely true across every Step, including the failure/escalation branches -- not only the happy path?
5. For each Step, walk it against three failure modes: could the Step's own precondition fail to hold, whether or not the Step itself states it; could the Step's own command or action itself fail; could the Step's own postcondition check fail to match? This is a write-time completeness question -- distinct from this file's own Formative quality dimensions section, dimension 4's runtime validate -> fix -> repeat feedback loop, which re-runs at execution time on specific quality-critical steps only.

## Guidance form and Single Decisive Outcome (SDO)

Two parts: how a Step should read (guidance form), and the deeper
elaboration of the test that tells you whether a Step, or a whole draft,
is trying to do one job or several (Single Decisive Outcome).

### Guidance form

A Step is an instruction a capable-but-context-free reader will follow under time pressure. Write it that way:

- **Verb-first, one action per Step.** "Read the issue and extract its acceptance criteria" is one Step doing one thing. "Read the issue, extract its criteria, and also check whether the branch already exists" is two Steps wearing one number -- split it, per this file's own SDO test below.
- **Checkable, not evaluative.** "Confirm the target file exists" is checkable. "Make sure the target is reasonable" is not -- a reader cannot tell whether they've satisfied it. If a Step needs judgment, say what the judgment is actually weighing ("assess whether the change is reversible; if not, require explicit confirmation before continuing"), not just that judgment is required.
- **State the why only when it changes what a reader does.** A Step that says "run the checker (it catches shape defects CI would otherwise reject)" earns its parenthetical -- it tells a reader why skipping it is costly. A Step that explains background context with no bearing on execution is prose that belongs in `SKILL.md`'s own introduction or a reference file, not inline in the Step.
- **Name the escalation path inline, not as an afterthought.** If a Step can fail in a way the rest of the procedure can't route around, say so in the Step itself -- this skill's own Step 7 does this directly (its upstream-ambiguity escalation branch names the exact `StageDeviated{action: escalate}` event and stop condition inline, in the Step itself), not only in a separate Stop-boundaries bullet a reader may never reach.
- **Cite primary sources for a claim about an external tool, library, or platform**, per this repository's own `grounding-in-primary-sources` discipline -- a Step asserting how something outside this repository behaves needs a citation, not "as far as I know."

### Single Decisive Outcome (SDO)

**A well-formed Step, and a well-formed skill, each produce exactly one decisive outcome.** This is the operational form of functional cohesion (Stevens/Myers/Constantine's strongest cohesion class -- see this file's own Cohesion and shared-script-parent policy section below for how Step 3 uses the full seven-way taxonomy): rather than asking "is this cohesive?" in the abstract, ask "if I had to name the one thing this Step (or this whole draft) decides or produces, could I do it in one sentence, without an 'and'?"

Apply the test at two levels:

- **Per Step.** "Extract the issue's acceptance criteria" -- one outcome (a list of criteria). "Extract the issue's acceptance criteria and decide whether the branch needs rebasing" -- two outcomes fused into one Step; a reader who only needs the first has to read past the second to find it, and a failure in the second silently blocks the first.
- **Per skill.** If a draft's own Steps decide two things that don't share a caller, a trigger, or a single Postcondition a reader could state in one sentence, that draft is probably two skills wearing one `SKILL.md`. This is exactly what Step 3 checks for, using the SDO test as its entry point before reaching for the full cohesion taxonomy.

**A failed SDO test is a drafting signal, not a verdict.** Finding two outcomes in one Step means rewrite that Step (or split it into two numbered Steps); finding two outcomes across the whole draft means route back to Step 1 and draft two skills instead of one non-cohesive one. It is not, on its own, the authoritative cohesion finding `evaluating-skill-quality` produces at handoff -- see this file's own Cohesion and shared-script-parent policy section below, "Step 3 and Step 5 are advisory," for why that distinction matters and how it's worded.

**A false failure is possible too.** Two Steps can look like they serve different outcomes while actually converging on one: a Step that gathers facts and a Step that acts on them are still one decisive outcome ("a decision made on gathered evidence") if the whole draft's Postcondition names that single, combined result. When a Step or a draft passes the "one sentence" test only by stretching the sentence into a run-on, that stretch is itself the finding -- name the two things the run-on is joining rather than accepting the sentence as proof of cohesion.

## Cohesion and shared-script-parent policy: ownership boundaries

This section exists because two of this skill's own Steps sit close
enough to `evaluating-skill-quality`'s own review procedure that the
boundary has to be stated explicitly, not left to be inferred from each
Step's own one-line description.

The redirect-target judgment this section once carried for `drafting-a-skill`'s
own former Step 2 -- the Agentic operation mechanism-fit vehicle-selection gate,
including the "this isn't a skill, redirect to X instead" criteria -- no longer
lives here: it moved upstream entirely, into a sibling skill. See this skill's
own `references/gitapex-cross-links.md` for which sibling skill owns that
judgment's current version and for the tracking issue recording the move.

### Step 3 and Step 5 are advisory, not a second grading

Ownership rationale, not a restatement of what each Step's own output-format instruction already says in `SKILL.md`:

- `evaluating-skill-quality`'s own rubric states plainly that the cohesion check has exactly one owner -- per Contract discipline's never-both rule, it decides the whole-artifact boundary once, there. The rubric's exact quoted wording is cited in this skill's own `references/gitapex-cross-links.md`.
- That same rubric's Blind spot pass runs as a precondition step of `evaluating-skill-quality`'s own procedure, alongside its Agentic operation mechanism-fit checks -- not a step this skill could duplicate without also duplicating that ownership.
- Step 3 (cohesion) and Step 5 (domain-gap sweep) exist anyway, for a narrower reason than "grade this against the rubric": a draft with an obvious split or an obvious blind spot, caught here, avoids a wasted round trip to `evaluating-skill-quality`'s own review and back. Both Steps are therefore advisory self-checks only.
- Practically: Step 3 borrows `evaluating-skill-quality`'s own seven-way cohesion taxonomy (functional / sequential / communicational / procedural / temporal / logical / coincidental, from Stevens/Myers/Constantine, extended by Yourdon and Constantine) as a lens for looking at the draft. Step 5 asks the same shape of question the Blind spot pass asks ("does this target's specific domain expose a quality concern no generic check would catch"). Neither Step re-derives or restates a verdict `evaluating-skill-quality` will produce on its own authority moments later.

### Shared bundled-script parent: a placement policy

A drafted skill sometimes needs a bundled script another skill's `scripts/` directory already provides, or is itself the first skill that would need to bundle a script a second skill will later also want. This repository has no single rule requiring registration of every such sharing decision, but does have a stated policy for picking a "parent" when the need arises, adapted from three primary software-engineering sources rather than invented for this skill:

1. **Stability first, warning-only.** Robert C. Martin's Stable Dependencies Principle says a shared dependency should be at least as stable as its dependents. When the target repository has too few explicit `lifecycle: stable` declarations to judge this axis meaningfully, a hard gate would be premature -- treat it as a preference, not a blocker, until explicit `stable` declarations become common enough to judge readiness against (see this skill's own `references/gitapex-cross-links.md` for this repository's current census).
2. **Common Closure Principle as tiebreak.** When stability alone doesn't settle it, prefer the parent whose own change-closure already includes the reason the shared script would need to change -- i.e. the skill that already owns the invariant the script checks, per Martin's Common Closure Principle (classes that change for the same reason belong together).
3. **A neutral, ADR-gated location, as a last resort.** Eric Evans' Shared Kernel pattern applies when the cost of coordinating a shared change is genuinely lower than the cost of duplicating it -- but Evans explicitly cautions against defaulting to a shared kernel. Escalate to a neutral location only when tiers 1 and 2 both fail to name a natural owner, and record the decision in an ADR (see `drafting-an-adr`) rather than placing it silently -- a neutral location chosen without a record reads, to the next skill that needs the same script, as an arbitrary dumping ground.

When the drafted skill's Step 6 checkers are already bundled by `evaluating-skill-quality` (gitapex's own name for this role; if the calling repository has no same-named skill, treat this as an illustrative pointer and substitute that repository's own skill filling the same role instead), that owner already satisfies this policy under all three tiers -- see this skill's own `references/gitapex-cross-links.md` for the repository-state census, the exact script names, and the mechanization-deferral record behind that claim.

## Formative quality dimensions

Nine formative concerns, one per dimension, each a writing-time precursor
to one of `evaluating-skill-quality`'s own nine review dimensions
(`references/rubric.md`). The two lists share numbering and a name on
purpose -- they are the same nine concerns, viewed from opposite sides of
the DDD boundary this skill's own `SKILL.md` describes: this section asks
"how do I write this well," the rubric asks "is what got written good
enough to ship." Neither owns the other's verdict; a dimension here is a
drafting habit, not a passing grade. Load this section's own worked
guidance once a first draft exists (see "How to use this section" below);
before that, `SKILL.md`'s own Step 2 already covers the load-bearing
judgment calls the ordinary path needs.

### 1. Name and description legibility

Write the `description:` frontmatter so a reader picks this skill out of a list of thirty without opening it -- state the trigger (when to use it) and the boundary (what it's not), not just the topic.

```
Good: "Use when authoring a brand-new skill from a blank page...
       Distinct from scorer-gated-skill-edits (iterates an existing SKILL.md)."
Bad:  "Helps with skills."
```

*Gate-side cross-reference: Dimension 1, Discovery -- name and description*

### 2. Economy of words

Cut a sentence that restates what the next sentence already implies. If a paragraph survives having its middle sentence deleted with no loss of meaning, delete it now rather than leaving it for review to flag.

```
Good: "Elicit the metadata choices; never infer them."
Bad:  "It's important to make sure that the metadata choices are properly
       elicited from the user, since inferring them can sometimes lead
       to mistakes."
```

*Gate-side cross-reference: Dimension 2, Conciseness*

### 3. Explicit freedom vs. constraint

State plainly, per Step, whether it's a hard rule ("never," "always") or a judgment call ("assess," "consider") -- a reader should never have to guess which.

```
Good (hard rule):    "Never skip Step 2's gate under time pressure."
Good (judgment call): "Judge whether the interpretation needs a human decision."
Bad: a Step phrased as advice ("you might want to check...") for
     something that is actually mandatory.
```

*Gate-side cross-reference: Dimension 3, Degree of freedom*

### 4. Structural legibility

- One Step, one action (see this file's own Guidance form section's SDO test).
- Number Steps so a later Step can reference an earlier one by number without the numbering having drifted.
- State what a Step iterating a finite set actually finishes on -- both a positive finding and an explicit "none found" are observable results; silence is neither.
- Use one term per concept throughout the skill and its references -- never two names for the same idea.
- Give a long or skippable-but-risky workflow as a copyable, ordered checklist, not a prose paragraph the reader has to re-parse into steps.
- Write a validate -> fix -> repeat feedback loop ("only proceed once validation passes") on any quality-critical step where errors are likely and costly -- leaving one out there is a gap, not a simplification.
- Match a template's strictness to its stakes: an exact template where the format is a hard contract, a "sensible default, use judgment" template where adaptation helps.
- Make branch triggers distinct and complete -- one checkable entry condition per branch (including reject/stop/escalate routes), no sibling branch sharing it, no input state left unmatched -- reusing this skill's own Step 3 cohesion enumeration as that inventory instead of re-deriving one, per this skill's own "never both" rule.
- Give real input/output pairs over description of what good output looks like: include at least one worked example showing the procedure run end-to-end on a plausible input, not a schema in the abstract.
- The per-Step three-failure-mode completeness walk (precondition, action, postcondition) is a separate write-time requirement, owned by this file's own Contract structure section's drafting checklist item 5 -- not restated here.
- When a section in any of the skill's own markdown files (`SKILL.md` or a `references/` file alike) enumerates multiple principles or rules (not a single Step's own action), give each its own bullet or table row, never continuous prose the reader has to re-parse into a list -- if a section's principles can't be told apart at a glance, that section is carrying too much for its own structure. Illustrate with a fenced code block or a process-tree diagram wherever a branch, a value, or a before/after shape is easier to read than the same thing described in words.

Good:
- "route back to Step 1" (a number in *this* draft's own Steps, kept true by the draft's own renumbering discipline)
- One term per concept throughout (always "job statement", never "task description" for the same idea)
- A long optional-but-risky workflow given as a numbered, copyable checklist
- A quality-critical step reading "validate -> fix -> repeat, only proceed once validation passes"
- An exact frontmatter template beside a "use judgment" Worked-example template
- A branch table with one checkable condition per branch, reusing Step 3's own cohesion findings rather than re-deriving them
- `executing-a-branch-plan`'s own "Worked example" section, walking a 3-row ACM through wave assignment
- A `SKILL.md` or `references/` section's principles given as separate bulleted items, each with its own fenced-code Good/Bad pair

Bad:
- A cross-reference that drifts silently after a Step gets renumbered, or a Step whose "nothing found" case has no stated output at all
- Two names for the same concept scattered across `SKILL.md` and its references
- A long, skippable-but-risky workflow given as a prose paragraph instead of a checklist
- A quality-critical step with no validate/fix loop
- A template that is either rigidly exact where judgment was needed or vague where an exact contract was needed
- Two branches selected by the same trigger, or an input state matching none
- A Steps list with no example, leaving a reader to construct their own first real test case
- A `SKILL.md` or `references/` section's principles run together into paragraphs, each rule indistinguishable from the surrounding sentences

*Gate-side cross-reference: Dimension 4, Clarity and structure*

### 5. Load-bearing vs. on-demand split

- Put content every invocation needs in `SKILL.md`'s own body; put content only some invocations need in a `references/` file, loaded conditionally.
- A reference file's own on-demand trigger must itself be a checkable, structural precondition (an environment fact, a dispatch-context identity, a resume/fresh-start state) -- a trigger stated only as a subjective sufficiency judgment ("when the inline floor isn't enough," "for a borderline case"), with no such fact behind it, resolves to true on effectively every non-trivial invocation and is load-bearing in practice regardless of its on-demand label.
- Two of this skill's own three reference files stay required for that reason: `gitapex-cross-links.md` (Step 6's own fuller gitapex-repo context the inlined checker commands sit in -- the PR-body disclosure convention, metadata schema location, deterministic-gate registration, and shared-script-parent census, none of which SKILL.md itself restates) and this file (Step 6's own unconditional formative-dimensions sweep, plus the Steps 2/3/Non-goals judgment calls the other three sections above carry).
- `decision-log-discipline.md` is the one genuinely on-demand file left -- its own trigger (resuming an existing target's sidecar, or a concurrent-dispatch race) is a checkable dispatch-context/concurrency state, not a sufficiency judgment.
- Name each reference file for its content (`decision-handoff.md`, not `doc2.md`), organised by domain, and link to it from `SKILL.md` exactly at the branch point where it becomes necessary -- the pointer states what context requires the read and what the reader will obtain, never a bare "see reference."

Good:
- `decision-log-discipline.md`'s own trigger, "resuming from an existing target's sidecar, or two dispatches racing on one target" -- a checkable dispatch-context/concurrency state, not a sufficiency judgment
- This skill's own `SKILL.md` staying self-sufficient for the ordinary path, pointing to a reference only when a specific question needs more depth than the body already gives

Bad:
- A reference file split off on a trigger stated only as "when the inline floor isn't enough" or "for a borderline case" -- no checkable fact behind either phrase, so it loads on effectively every non-trivial invocation despite its on-demand label
- A reference file named `doc2.md` with no branch-point pointer anywhere in `SKILL.md`, or a pointer that says only "see reference" without saying what question it answers

*Gate-side cross-reference: Dimension 5, Progressive disclosure*

### 6. Stability of claims

- Avoid a claim likely to go stale without a mechanism keeping it honest -- a specific line count, a "the only skill that..." superlative, a bare issue number.
- Where a claim must be precise and could drift, either cite a deterministic gate that locks it or mark it as a point-in-time fact.
- Use forward slashes in every path (`references/rubric.md`), never backslashes.
- Name an MCP tool fully qualified as `Server:tool` (e.g. `GitHub:create_issue`), never a bare tool name.
- Never assume a tool or package is installed without saying so, and never assume installing one is even possible -- install capability differs by surface (Claude Code allows local installs but discourages global ones; the Claude API surface has no runtime package installation at all).
- Offer a default with an escape hatch, not a menu of options.
- For content declared (or read as) Portable: state the skill's own issue-filing/PR-body/workflow-ordering convention as an illustrative default with a stated fallback to the consumer repository's real convention, never asserted as the one correct shape; and let no procedural step read, cite as authority, or branch on a path outside the skill's own folder -- a citation as illustrative context is fine, deciding what to do next from it is not.
- For a Portable file's own illustrative Good/Bad examples: never encode this document's own literal editorial history (a past file split, a past rename, a specific prior wording) as the example itself -- a vendored copy carries none of that history, so the pattern has to generalize without it.

Good:
- "cite dimension 15 by number" backed by a drift gate
- A path written `references/rubric.md`
- A tool call named `GitHub:create_issue`
- "install the package if your surface allows it, otherwise skip this step" instead of a bare `pip install X`
- "use option A by default; pass `--no-a` to opt out" instead of a three-way menu
- A Portable skill's issue step reading "open a tracking issue per your repository's own convention (this skill's own default: one issue per branch)."
- A Bad example stated as a generalized pattern ("a reference file split off on a subjective sufficiency trigger") rather than this document's own literal past shape

Bad:
- "references/rubric.md (2227 lines)" stated as fact with nothing keeping the number honest -- exactly the kind of claim this repository's own vocabulary-lock gate family exists to catch once it's this skill's own content going stale
- A backslash path (`references\rubric.md`)
- A bare tool name with no server prefix
- `pip install X` with no fallback stated for a no-install surface
- A menu of three interchangeable options with no stated default
- A Portable skill asserting "always open a tracking issue before any branch" as the one correct shape with no fallback, or a step that tells the model to go check a repository-specific path to decide what to do next
- An illustrative example reading "this file's own prior split into four separate files ... merged into this one file now" -- true only for this one repository's own past instance, meaningless once vendored elsewhere

*Gate-side cross-reference: Dimension 6, Durability*

### 7. Script necessity and minimalism

- Only bundle a script when a check genuinely needs to be deterministic rather than judged -- and when one is bundled, give it a docstring stating what it checks and why prose alone wasn't enough. Applies only if the drafted skill ships code at all.
- When a script is bundled, make it handle its own error conditions (a missing file, permission denied) rather than throwing and leaving the invoking model to cope -- solve, don't punt.
- Name a configuration constant so its own identifier carries what it is and why this value, per the explanatory-constant principle -- a constant that needs a comment to be understood is a naming defect, not a documentation gap. Reach for a comment only when an external fact a name genuinely cannot carry (a sibling system's own setting this value must stay in sync with) would otherwise be invisible to the next editor.
- Key a script's own comments to whether the skill tells the model to execute it or read it as reference: execute-only comments are Interface documentation (what a caller must know -- inputs, outputs, flags, exit codes); read-as-reference comments carry more Implementation documentation (tricky aspects, non-obvious reasons, invariants) -- never blend the two, and never let a top-of-file usage comment wander into internal mechanism.
- When the script is shared with, or reachable from, another skill, give it exactly one owner: that skill's own `scripts/` bundles it, and every other consumer declares the dependency in its own sidecar metadata rather than reaching for it undeclared.

```
Good: CI_STEP_TIMEOUT_SECONDS = 30
Bad:  TIMEOUT_SECONDS = 30  # matches the CI job's own step timeout
```

Good (other examples):
- A shape-checker with a documented exit-code contract
- A checker that catches a missing file and reports which file and why rather than raising an unhandled traceback
- An execute-only script's top comment stating its flags and exit codes, nothing about its internals
- One skill's `scripts/` bundling a checker with a sibling skill's `skillDependencies.requires` naming it

Bad (other examples):
- A script that reimplements a judgment call review would make anyway, just in Python
- A script that throws on a missing file and leaves the model to cope
- A read-as-reference script's comments that never state what a caller needs to know at all
- A script one skill's own default path constant reaches into a sibling skill's `scripts/` directory for, with no declared dependency either side

*Gate-side cross-reference: Dimension 7, Bundled scripts*

### 8. Eval preparation

Before treating a draft as finished, enumerate at least three scenarios the drafted skill must handle correctly -- including the guardrail/failure case it exists to prevent -- and sketch a fixture skeleton under `evals/<skill>/` (this repository's own layout: one `tasks/<scenario>.yaml` fixture per scenario, each naming its expected behavior, beside the suite's own `eval.yaml`) that a later with/without-skill baseline run can point at. This is preparation only: it does not run the baseline itself and does not build new eval-execution infrastructure -- scoring a documented "without the skill" baseline against these scenarios is `evaluating-skill-quality`'s own Behavioural evidence pass, not a drafting-time deliverable.

Good: three scenario prompts sketched for the curl-explainer candidate:
- a plain GET
- a POST with a body
- the guardrail case (a flag reading a secret from a file)

...each stubbed as its own `evals/<skill>/tasks/*.yaml` fixture naming what the draft should (and should not) do.

Bad: shipping a draft with no scenario list at all, leaving the first real eval run to discover the guardrail case was never considered.

*Gate-side cross-reference: Dimension 8, Behavioural evidence*

### 9. Model-agnostic phrasing

Don't write a Step that only works if the executing model happens to interpret an ambiguous instruction the way the author had in mind. Where a Step depends on a specific model/effort tier's own judgment strength, pin it explicitly (see `executing-a-branch-plan`'s own Notes section for a real pinned-step precedent) rather than leaving the dependency implicit.

Good: naming which Steps carry a model/effort pin and why.
Bad: a Step that works during authoring (tested against one strong model) but silently degrades under a weaker one, with nothing in the text warning a reader this could happen.

*Gate-side cross-reference: Dimension 9, Cross-model robustness*

### How to use this section while drafting

Load it once a first draft exists, then treat it as a checklist pass over that draft, not a constraint to satisfy sentence by sentence while writing. Trying to hit all nine dimensions on the first pass produces prose optimized for the checklist rather than for the reader; draft first, using `SKILL.md`'s own inlined guidance, then sweep against this section once there's a real draft to sweep.

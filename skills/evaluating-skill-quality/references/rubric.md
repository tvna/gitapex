# Skill quality rubric

Portable evaluation reference for judging whether a `SKILL.md` (and its
`references/`) is good. Grounded directly in Anthropic's primary Agent
Skills documentation -- the [Skill authoring best practices][ab], the
[Agent Skills overview][ao], and, for the Claude-Code-specific rules
(the product a `skills/<name>/` plugin layout, as reviewed here, actually
targets), [Claude Code skills][cc]. Where the generic Agent Skills spec
(used by the Claude API and claude.ai) and Claude Code's own rules
diverge, this file says which is which rather than blending them into
one claim; dimension 1 and the deterministic-shape note in `SKILL.md`
cover the specific divergence around the `name` field. All reference
URLs are collected under [References](#references) at the end of this
file.

This skill travels with any repo it is vendored into: where a target
repository lacks a piece of tooling (a deterministic checker script, an
eval suite, a benchmarking harness), dimensions 1-9 below say to check the
target repository directly and state the gap explicitly, rather than
assuming a specific repo's tooling state or citing a file outside this
skill's own folder.

## Table of contents

- [The mental model](#the-mental-model)
- [Unknowns framework](#unknowns-framework)
  - [Blind spot pass](#blind-spot-pass)
- [Contract discipline](#contract-discipline)
- [Mechanism fit](#mechanism-fit)
  - [Skill-step vs. bundled script](#skill-step-vs-bundled-script)
  - [Model/effort tier fit](#modeleffort-tier-fit)
- [Portability level](#portability-level)
- [1. Discovery -- name and description](#1-discovery----name-and-description)
- [2. Conciseness](#2-conciseness)
- [3. Degree of freedom](#3-degree-of-freedom)
- [4. Clarity and structure](#4-clarity-and-structure)
- [5. Progressive disclosure](#5-progressive-disclosure)
- [6. Durability](#6-durability)
- [7. Bundled scripts](#7-bundled-scripts-only-if-the-skill-ships-code)
- [8. Behavioural evidence](#8-behavioural-evidence)
- [9. Cross-model robustness](#9-cross-model-robustness)
- [Verdicts](#verdicts)
- [References](#references)

## The mental model

A skill is an addition to an already-capable model, not a tutorial. Content
that re-teaches general concepts, common tools, or standard formats is
waste. Skills load by progressive disclosure at three costs: `name` +
`description` are always resident (every skill, every turn); the
`SKILL.md` body loads once triggered, wholesale; `references/` load only on
demand. Judge each piece of information by whether it lives at the cheapest
level that still makes it available the moment it is needed.

This layering is one instance of a single meta-principle the rest of this
rubric decomposes into per-layer checks -- [separation of concerns][soc]:
mechanism fit separates responsibility across artifacts, progressive
disclosure (dimension 5) across load layers, and Contract discipline's
"never both" rule keeps each check in exactly one place. There is no
separate dimension for it because it is cross-cutting, not one more thing
to check.

## Unknowns framework

A borrowed lens for what this review does and does not yet see, not a new
scoring dimension. Adapted from Anthropic's own field guide on working with
Claude models -- Thariq Shihipar, "A Field Guide to Fable: Finding Your
Unknowns" ([fable]) -- which names four kinds of gap between what an
operator tells an agent (the map) and what the actual work requires (the
territory):

- **Known knowns** -- what the target `SKILL.md` states outright; dimensions
  1-9 read this directly.
- **Known unknowns** -- gaps this review is already aware it cannot close.
  Dimensions 8-9's "name the gap explicitly, never silently skip" discipline
  is this review's existing outlet for them.
- **Unknown knowns** -- judgment a reviewer would recognize on sight but this
  rubric does not enumerate as a checklist item. Mechanism fit's qualitative
  calls are this review's main outlet for them.
- **Unknown unknowns** -- a gap in this fixed nine-dimension rubric itself,
  for the specific target's domain, that no dimension, Mechanism fit check,
  or Portability rule currently names. Left unaddressed, this quadrant is
  silently assumed empty rather than actually checked -- the
  [Blind spot pass](#blind-spot-pass) below is the one step that exists to
  surface it.

### Blind spot pass

A precondition step (`SKILL.md`'s Procedure step 2, alongside the Mechanism
fit checks), not a tenth dimension -- the fixed nine-dimension count is
unchanged by this section. (As a point of local fact about this
repository specifically, not part of this skill's own portable content:
`evals/evaluating-skill-quality/tasks/guardrail.yaml` checks the reviewer
still says "nine" -- illustrative confirmation, not something this claim
depends on to be true.)

Before walking dimensions 1-9, name explicitly whether the target's specific
domain exposes a quality concern that none of the nine dimensions,
Mechanism fit, or Portability level already covers. This is the same move
that produced `battle-testing-a-skill`'s dimensions 18-22 from a gap
analysis of that skill's own catalog
(`battle-testing-a-skill/references/provenance-and-caveats.md`, "Comparative
gap review: dimensions 18-22") -- applied here to this rubric instead of
that one. This repository has also used the same move informally, once, to
find gaps in its own *skill coverage* rather than in one skill's rubric
(`docs/superpowers/specs/2026-07-15-triage-cluster-design.md`: "a
Fable-assisted skill-gap analysis (Known/Unknown blind-spot pass...)"
motivated `ranking-the-open-queue`, `responding-to-a-fresh-arrival`, and
`screening-a-low-trust-contribution`) -- this section is the first time the
same move is formalized as a repeatable step *inside* a skill's own
procedure, rather than a one-off session technique.

- **If a gap is found**: name it in the review's output the same way an
  unmeasured dimension 8/9 gap is named. Never fold it silently into an
  existing dimension's verdict, and never invent an ad hoc tenth dimension
  inline to cover it -- a durable rubric change should go through this
  repository's own held-out-gated edit process if the environment has one
  (this repository's own is `gated-skill-edits`; see dimension 8's
  held-out-gate paragraph below) or an equivalent measured accept/reject
  step if it does not, not something a single review session improvises.
- **If no gap is found**: say so explicitly ("no rubric blind spot found for
  this target's domain") rather than leaving the question unaddressed --
  the same "silence is not evidence" discipline dimension 8 already applies
  to behavioural evidence, applied here to rubric coverage instead.

## Contract discipline

This review's own procedure is itself a contract, in [Meyer's][dbc] sense
of the term (Design by Contract: preconditions, postconditions, and
invariants, as formalized for Eiffel and applied generally to reliable
software construction). Naming the parts precisely matters because it
fixes where a fault actually lives when a review goes wrong.

- **Precondition** -- what `SKILL.md`'s Procedure steps 1-4 establish
  before dimension grading starts: the target has actually been read
  (step 1), its mechanism fit is checked (step 2, see below), its
  deterministic shape is checked (step 3), and its portability level is
  established (step 4, see below). Per Meyer: "the precondition expresses
  requirements that any call must satisfy if it is to be correct."
- **Postcondition** -- what step 6 delivers *if the precondition held*: a
  verdict with cited evidence per dimension. Per Meyer: "the postcondition
  expresses properties that are ensured in return for the call."
- **Invariant** -- properties that hold throughout the *entire* review,
  not just at one step: this skill's Stop boundaries. Per Meyer, an
  invariant "is added to the precondition and postcondition of every"
  step -- a Stop boundary is not a step-5-only rule; it binds during
  mechanism-fit checking, shape-checking, portability classification, and
  the dimension walk alike.

Two operational rules follow directly, quoted from the same source:

- **Fault attribution.** "A precondition violation indicates a bug in the
  client (caller). ... A postcondition violation is a bug in the supplier
  (the routine)." Applied here: if a verdict turns out wrong because the
  mechanism fit, portability level, or deterministic shape was misjudged,
  that is a bug in how this review established its precondition -- not a
  flaw in dimensions 1-9 (the "supplier"). Redo the precondition steps; do
  not patch the rubric to route around a misclassification.
- **Never both.** Meyer states this as "an absolute rule": a condition is
  checked in exactly one place, "either you have the condition in the
  [precondition], or you have it in an If instruction in the [routine's]
  body ... but never in both" -- redundant re-checking is not extra
  safety, it is a design smell indicating the responsibility split is
  unclear. Applied here: dimensions 1-9 must not re-derive facts the
  precondition steps already established (this is why dimension 1 says
  the deterministic checklist "confirms a trigger *exists*" and then
  asks a *different* question -- whether it is the *right* one -- rather
  than re-checking existence; and why dimension 6's Portable-skill bullet
  *consumes* the portability level step 4 already produced, rather than
  re-classifying it).

## Mechanism fit

One of this review's own preconditions (see [Contract
discipline](#contract-discipline) above) -- the mechanism decision
(skill vs. subagent, hook, or CLAUDE.md, plus, for a deterministic
in-skill step, model-reasoning vs. a bundled script) lives in
`SKILL.md`, checkable without opening this file. This section is the
elaboration: the primary source and the reasoning behind each check.

Grounded in Anthropic's own guidance on steering Claude Code
([Steering Claude Code][steering]): seven methods compete for the same
job -- CLAUDE.md, rules, skills, subagents, hooks, output styles, and
appending the system prompt -- and "each method controls: when an
instruction loads into context; whether it persists through long
sessions (compaction behavior); and how much authority it carries."
Skills specifically: "name and description [load] at session start;
full body loads when the skill is invoked" -- low context cost, but
model-followed, not deterministic.

Two of the source's own "Quick tips" anti-patterns are the sharpest,
directly quoted:

- **"'Every time X, always do Y' in CLAUDE.md[, or a skill]. If the
  behavior should happen reliably ... use a hook ... instead. The model
  choosing to run a formatter is different from the formatter running
  automatically."** A skill that reads like a guaranteed-execution rule
  (not a judgment call, an unconditional action) is asking prose to do a
  hook's job.
- **"'Never do this' in CLAUDE.md[, or a skill]. When there's something
  that absolutely must not happen, an instruction is the wrong tool.
  Claude will follow the instruction most of the time, but when under
  pressure, in a long session or an ambiguous situation, or due to a
  prompt injection in a file accessed as part of the task, the model can
  fail to follow a prompted rule. A real guardrail needs to be
  deterministic, and the enforcement methods are hooks and
  permissions."**
  A skill's Stop boundaries are exactly this shape -- prose prohibitions.
  For most, that is fine (a reviewer's judgment calls belong in prose);
  but a Stop boundary that guards something safety-critical (data
  exfiltration, destructive commands, secret exposure) and has no hook
  or permission enforcing it is a real gap this dimension exists to
  name, not a hypothetical one.

Also directly quoted, on the skill/CLAUDE.md boundary: **"Procedures
belong in skills. CLAUDE.md is for facts Claude should hold all the
time: build commands, monorepo layout, team conventions. A deployment
runbook or a security review checklist should live in `.claude/skills/`,
where the body loads only when invoked."** And the subagent boundary:
**"Use a subagent when a side task ... would clutter your main
conversation with intermediate results you won't reference again. Use a
skill when you want the procedure to play out inside the main thread so
you can see and steer each step."**

A second, distinct trigger for subagent use -- not from [steering] above,
so labelled as this repository's own reasoned extension rather than an
Anthropic-sourced claim -- is *isolation for neutrality*: when the main
thread has plausibly already seen, authored, or discussed the specific
target under review, delegating the judgment-bearing step to a fresh
subagent dispatch removes a bias risk an in-context instruction to
"review neutrally" cannot fully remove. Grounded in this repository's own
evidence: `battle-testing-a-skill`'s cold-enumeration step already
isolates for exactly this reason ("not the current context, which has
likely already seen the target"), and that skill's own extraction
protocol (`skills/battle-testing-a-skill/references/provenance-and-
caveats.md`, caveat 3) names the limit of instruction-only isolation
directly. Unlike [steering]'s clutter-avoidance trigger, this one does
not require the dispatch's results to go unreferenced: the dispatch's
full evidence-cited output is exactly what gets relayed back, preserving
the steerability [steering] is protecting -- only the grading judgment
itself needs isolation, not the review's visibility to the human. This
skill applies the pattern to itself; see `SKILL.md`'s Subagent dispatch
section.

A wrong-mechanism finding is not one of the nine dimensions and is not
folded into the well-formed/mature ladder: report it as the review's
headline finding regardless of how the rest of the review scores, per
`SKILL.md`'s Procedure step 2 and Stop boundaries.

This describes a *whole-artifact* wrong-mechanism finding (the skill should
have been a hook, subagent, or CLAUDE.md content). The Skill-step vs.
bundled script and Model/effort tier fit checks below are the exceptions:
their findings are step-level, reported for triage, and are neither a
headline nor a *mature* blocker.

A recorded mechanism-fit decision for the *reviewed* skill -- the "keep
vs. retire, and why" rationale once a wrong-mechanism finding has been
weighed -- belongs in that skill's footer `## Notes` section, not
front-loaded above its procedure; the same placement convention that
keeps portability declarations terse up top applies here.

### Skill-step vs. bundled script

The three checks above ask whether a skill is the right *artifact*. This
fourth asks, within a correctly-chosen skill, whether a given *step* is
best done by model reasoning or delegated to a bundled script the skill
calls. It is distinct from the hook check: a hook is event-bound; a step
inside a skill's procedure fires when the model reaches it, not on an
event, so a hook cannot own it -- the mechanism choice for such a step is
model-reasoning vs. a bundled script.

Delegation is favoured on three converging grounds -- correctness,
consistency, and cost -- when the step is deterministic:

- **Correctness and consistency.** A model applying a mechanical rule
  in-head miscounts, misremembers exact limits, and drifts when the rule
  is restated in several places; a script is deterministic and a single
  source of truth. Anthropic's best-practices guidance on bundling
  executable scripts says to "prefer scripts for deterministic
  operations" because they are "more reliable than generated code" and
  "ensure consistency across uses" ([ab]) -- the same reliability logic
  the skill-vs-hook check above rests on, applied to a step rather than a
  whole skill.
- **Cost.** The same guidance grounds the cost claim directly: a bundled
  script "save[s] tokens (no need to include code in context)" and
  "save[s] time (no code generation required)" ([ab]). As
  first-principles elaboration of *why* -- labelled a *read* per
  dimension 9's discipline, not itself a primary-doc claim -- a model
  doing deterministic work spends a full forward pass per generated
  token and serialises the computation into context, whose attention
  cost grows with input size; a script is microseconds of CPU. For
  repeated, multi-rule, or large-input work the model is worse on unit
  cost, on scaling, and on reliability at once.

**Break-even.** Delegate when the step is deterministic AND at least one
of: repeated/looped; multi-rule or non-trivial; error-prone for a model
(counting, exact limits, strict matching, parsing); or it must emit a
machine-checkable artifact for a high-stakes step (dimension 7's
plan -> validate -> execute). Keep the step in-model when it is a single
trivial deterministic check (the tool-call round-trip costs more than it
saves) or when it needs judgment or context (then it is not deterministic
and belongs to the nine dimensions). Cost is never a standalone trigger:
without one of these conditions, leave the step in prose.

A finding here is a **step-level** mechanism finding -- report it when it
fires, but it is not the whole-review headline and does not by itself
block a *mature* verdict; it feeds triage. Because it fires only when the
break-even clearly favours a script, a capable model is not pushed to
script trivial work (dimension 2). This check decides *whether* a script
should exist; dimension 7 grades the quality of one that does. The
'two lanes' split of this review's own procedure (deterministic shape vs
probabilistic maturity) is the same idea applied to *this* skill rather
than a reviewed one -- an intentional parallel, not the same check.

### Model/effort tier fit

A fifth Mechanism-fit check, distinct from the four above: not whether
the skill is the right *artifact*, but whether a model-tier or
reasoning-effort *pin* the skill's own content makes -- in prose
instructions to the invoking agent, or in a bundled Workflow script's
`agent()` calls -- is itself justified. Grounded in Anthropic's own
guidance on this exact choice, Lydia Hallie (Claude Code team),
"Choosing a Claude model and effort level in Claude Code" ([modeleffort]):
"Effort changes how much work Claude does. The model changes what Claude
knows."

**Applicability.** Fires only when the target's own content pins a model
or effort level somewhere. Most skills correctly omit both and inherit
the caller's -- per the source's own default guidance, "for most tasks,
use the model's default effort level" -- and an absent pin is not a
finding.

- **Model pin.** Justified when the pinned tier matches genuine
  difficulty the source names directly: "subtle bugs, unfamiliar
  domains, architecture decisions," or a step where "the smaller model
  is confidently wrong no matter how much context you give it."
  Unjustified when it forces a stronger tier for work the source calls
  routine -- "edits you can describe precisely, mechanical changes,
  questions about code that's already in context" -- with no such
  difficulty cited. An unjustified downgrade (forcing a weaker tier onto
  a step that plausibly needs the difficulty-driven capability) is the
  same finding in the other direction.
- **Effort pin.** Justified when it is a stated, deliberate, general
  preference tied to the skill's own domain (e.g. an irreversible
  operation whose skill explicitly always wants exhaustive verification)
  -- matching the source's framing of effort as "a manual override... 
  reach for it deliberately... a general preference, not a task-by-task
  decision." Unjustified when a non-default level is set with no stated
  reason, especially forcing a *lower* effort onto a step that needs
  verification -- the source's own diagnostic applies directly here:
  "did it not try hard enough, or did it not know enough?" A skill that
  forces low effort onto a verification-heavy step is pre-emptively
  choosing the "didn't try hard enough" failure mode for its own users.
- **Token-consumption confusion.** A skill that treats effort as a hard
  cap on tokens (rather than `max_tokens`, the only real hard cap in the
  system) is a distinct, citable misunderstanding of the mechanism,
  worth naming even independent of whether the specific pin is otherwise
  justified.

**When a pin is found justified, say so explicitly** (e.g. "model/effort
pin justified -- <reason>"), the same restraint discipline dimension 8's
"silence is not evidence" rule already applies elsewhere in this rubric
-- a pin existing is not itself a finding, and inventing one where the
skill's own stated reason already matches the source's criteria is not a
review, it is noise.

A finding here is a **step-level** mechanism finding, the same standing
as Skill-step vs. bundled script above -- report it when it fires, but it
is not the whole-review headline and does not by itself block a *mature*
verdict.

## Portability level

One of this review's own preconditions (see [Contract
discipline](#contract-discipline) above) -- the three-level definition
(Portable / Repository-scoped / Mixed) lives in `SKILL.md`, checkable
without opening this file, precisely because establishing it is a cheap
precondition step, not part of the expensive dimension walk. This
section is the elaboration: why the classification is a design decision
rather than a quality defect by default, and how each level changes
grading below.

- **Portable** -- grade dimension 6 (durability) at full strictness: any
  behavior-controlling reference outside the skill's own folder is a real
  defect, not a style nit. References to the origin repository as
  *context* or a *worked example* remain fine; only references the
  *procedure* depends on to function are graded this strictly.
  - **The portability litmus test, applied to every sentence, not only
    executed steps**: for Portable-declared content, ask of each claim --
    including one the model never executes as a step, such as a Stop
    boundary or a Mechanism-fit assertion -- *"would this exact sentence
    remain true, unchanged, if this file were copied into a repository
    carrying none of the origin repo's state?"* A runtime path-read
    failing this test is the same defect as a **declarative fact-claim**
    failing it (e.g. "backed by this plugin's `hooks/check-x.sh`," "this
    repository's tests currently number 214"). Grade both identically;
    the absence of an executed step does not exempt a prose assertion.
    Fail: an unconditional claim that a specific file, hook, or count
    backs a rule. Pass: a conditional check ("real deterministic backing
    if the current environment has one; verify directly rather than
    assuming either way").
  - **Stop boundaries and Mechanism-fit prose are the highest-risk
    locations for this failure**, because an author who correctly checked
    the *origin* repository and found a hook is tempted to record that
    finding as a flat, unconditional fact rather than as a conditional
    check -- the claim silently stops being portable at exactly the
    moment it stops being hedged. Read every Stop-boundaries and
    Mechanism-fit sentence in Portable-declared content twice: once
    answering "is this backed" (Mechanism fit's question), once answering
    "would this sentence's specific wording survive being read in an
    unrelated repository" (the portability litmus test) -- these are
    different questions, and Portable-declared content must pass both,
    not just the first.
- **Repository-scoped** -- a repository-scoped skill that reads as if it
  were portable is a dimension-1/6 defect (it misleads a future vendoring
  decision), not the scoping choice itself. An undeclared level that
  turns out to be repository-scoped is itself a finding, not something to
  silently infer and move past. Declared as a terse one-line marker on
  the first body line after the H1 (the `portability-near-top` shape
  check enforces presence within the first 6 body lines); any extended
  rationale belongs in a footer `## Notes` section of the same file,
  keeping the classification checkable from this file alone.
- **Mixed** -- dimension 5 (progressive disclosure) requires the actual
  split, not just the intent to split: the repository-specific part
  belongs in a clearly named reference file (e.g.
  `references/this-repo-only.md`) a consumer can identify and drop, not
  blended into the portable core.

## 1. Discovery -- name and description

`scripts/check_skill_shape.py` (see SKILL.md, Two lanes) confirms a
trigger *exists* by shape -- present, no XML tags, under the length cap,
with the exact limits owned by that script rather than restated here.
This dimension judges whether it is the *right* trigger -- whether the
skill would win its intended request and lose a neighbour's. Per
Anthropic's best-practices doc, `name` and
`description` "are particularly critical. Claude uses these when deciding
whether to trigger the skill" -- this is the highest-leverage text in the
whole skill, not a formality.

- **States both what and when, in terms a real request would contain** --
  not just any capability statement plus any trigger clause, but specific
  enough that a router would not confuse this skill with a sibling's.
- **Specific key terms, no filler** ("helps with documents" matches
  everything and therefore nothing).
- **`name` reads as an activity** (gerund preferred, e.g.
  `processing-pdfs`; noun phrases and action forms are acceptable, e.g.
  `pdf-processing`, `process-pdfs`) and is **distinct from every sibling
  skill** -- no overlap that makes routing ambiguous. Neither of these is
  a shape check a script can decide.
- **Avoid vague or overly generic names** -- `helper`, `utils`, `tools`,
  `documents`, `data`, `files` name nothing specific and match everything.
  Also flag inconsistent naming patterns across a skill collection.
- **`name` is a display label, not an invocation key, for a plugin
  skill.** Per Claude Code's own docs, `name` is optional and, when
  omitted, defaults to the directory name; for a skill under a plugin's
  `skills/` subdirectory (the layout used by this skill itself, and by
  many Claude Code plugins generally), Claude Code derives the actual
  `/plugin:skill-name` invocation command from the *directory* name, not
  from frontmatter `name`, regardless of what `name` says. Do
  not fail a skill merely for `name` differing from its directory --
  that mismatch does not break invocation. It is still worth flagging as
  a readability/consistency nit (a human skimming the directory listing
  benefits from the two agreeing), just not as a shape violation.
- **Fail example:** a description that only says what the skill does, with
  no trigger, or a trigger so generic it would also match a sibling's
  request.
- **Pass example:** "Extract text and tables from PDF files, fill forms,
  merge documents. Use when working with PDF files or when the user
  mentions PDFs, forms, or document extraction." -- names the operations,
  names the trigger terms.

## 2. Conciseness

Challenge each paragraph: does the model need this explanation, does it
already know this, does the paragraph justify its token cost? A "no" to any
is a cut.

- Prune sentence by sentence and classify the reason: **relevance**
  (irrelevant to this skill's task), **duplication** (the same rule has another
  owner), **sediment** (historical rationale that no longer controls
  behavior), or **sprawl** (branch-specific detail paid on every route).
  These are static findings grounded in the text and its current procedure.
- A **no-op** is different: it is model-relative behavioral evidence that
  removing the sentence leaves measured behavior unchanged on the named
  model, harness, and fixture set. Never call a sentence a no-op from prose
  style alone; without a before/after run, use one of the four static
  classifications above or say unmeasured.
- **Fail:** explaining what a well-known format or tool is; retaining
  irrelevant, duplicate, sedimentary, or sprawling text without a
  behavior-controlling reason; claiming an unmeasured sentence is a no-op.
- **Pass:** assumes competence, states only the project- or task-specific
  delta, reaches actionable content fast, and distinguishes static pruning
  evidence from measured no-op evidence.

## 3. Degree of freedom

Prescription must match the operation's fragility:

- **High freedom (prose)** -- open field, many valid routes; multiple
  approaches work and context decides.
- **Medium freedom (parameterised pattern)** -- a preferred shape exists,
  some variation is fine.
- **Low freedom (exact steps/commands, few or no parameters)** -- narrow
  bridge with cliffs; the operation is fragile, consistency is critical, or
  a precise sequence must hold.

Flag a mismatch in either direction: rigid step-by-step for an open-ended
judgment task over-constrains a smart model; loose prose for a fragile,
irreversible operation invites improvisation where there is exactly one
safe way.

## 4. Clarity and structure

- **Consistent terminology** -- one term per concept, throughout the skill
  and its references.
- **Concrete examples over abstract description** -- real input/output
  pairs, not a description of what good output looks like.
- **Workflows as ordered steps** -- a copyable checklist when the sequence
  is long or steps are skippable-but-risky.
- **Feedback loops on quality-critical steps** -- validate -> fix -> repeat
  ("only proceed when validation passes") on any step where errors are
  likely and costly. Its absence there is a gap.
- **Templates matched to strictness** -- an exact template where the format
  is a hard contract, a "sensible default, use judgment" template where
  adaptation helps.
- **Branch triggers are distinct and complete** -- enumerate every actual
  procedure branch, including reject/stop/escalate routes. Each branch has
  one checkable entry condition that no sibling branch duplicates; flag a
  branch with no trigger, two branches selected by the same trigger, or an
  input state that matches none or several.
- **Steps have completion criteria** -- for every procedural step, name the
  observable result that proves it finished. Where the step iterates over a
  finite set (files, dimensions, findings, branches), the criterion is
  exhaustive: every member is accounted for, not merely sampled.

## 5. Progressive disclosure

`SKILL.md`'s deterministic checklist confirms reference depth and TOC
presence by shape. This dimension judges the *meaning* behind the split --
naming, linking, and whether the common case is forced through more than
one read.

- Reference files named for content (`decision-handoff.md`, not `doc2.md`),
  organised by domain.
- Put branch-common rules in `SKILL.md`; put branch-specific detail in the
  reference for that branch. Co-locate instructions that must be applied
  together instead of making the model assemble one decision across files.
- `SKILL.md` links to each reference at the branch point where it becomes
  necessary. The pointer says what context requires the read and what the
  reader will obtain, rather than merely "see reference." An unlinked
  reference is dead weight; a needed one with no contextual pointer is
  invisible.
- Splits must not force several reads for the common case -- if acting on
  the typical request needs three files open, the split is wrong.
- Detail needed only sometimes belongs in `references/`; detail the model
  reads on every single use belongs inlined in `SKILL.md`. Both directions
  are failures.

## 6. Durability

- No time-sensitive content ("before August 2025 use the old API"). Any
  historical content is explicitly marked as such, not left to silently rot.
- No assumption that a tool or package is installed without saying so, and
  no assumption that installing one is even possible: package-install
  capability differs by surface -- Claude Code allows local installs but
  discourages global ones (to avoid interfering with the user's machine);
  the Claude API surface has no network access and no runtime package
  installation at all (pre-configured dependencies only); claude.ai varies
  by admin/user network settings. A skill instructing `pip install X` with
  no fallback is a durability risk on API-surface targets.
- MCP tools named fully qualified as `Server:tool` (e.g. `GitHub:create_issue`),
  never a bare tool name.
- Forward slashes in every path (`references/rubric.md`), never backslashes.
- A default with an escape hatch, not a menu of options.
- No bare (`#149`) or even fully-qualified (`owner/repo#149`) GitHub
  issue/PR-number citation inside content declared (or read as)
  **Portable**. A bare `#N` auto-links relative to whichever repository
  currently hosts the file and silently resolves to the wrong issue once
  vendored; a fully qualified link avoids the wrong-resolution risk but
  is still the origin repository's own issue-tracker bookkeeping blended
  into portable teaching content -- the same portable-core/repo-detail
  split the Mixed classification above and dimension 5 already require
  for other content. Route dated, issue-linked history to the origin
  repository's own status documentation (e.g. a `docs/`-level eval or
  change log) instead of a worked example inside the skill's own folder.
- For a skill declared (or read as) **Portable** (see
  [Portability level](#portability-level)): no procedural step reads,
  cites as authority, or branches on a path outside the skill's own
  folder. A citation to the origin repository purely as illustrative
  context (a worked example, a "here is what this looked like once") is
  fine; a step that tells the model to go check a repository-specific
  path to decide what to do next is not -- that path breaks the moment
  the skill is copied elsewhere. This applies to a **declarative
  fact-claim** exactly as strictly as to an executed step -- see the
  portability litmus test in [Portability level](#portability-level)
  above.

## 7. Bundled scripts (only if the skill ships code)

- **Solve, don't punt** -- scripts handle their own error conditions
  (missing file, permission denied) rather than throwing and leaving the
  model to cope.
- **No voodoo constants** -- every configuration value is justified in a
  comment. A constant the author cannot justify, the model cannot either.
- **Dependencies listed; execution intent stated** -- required packages
  named and verified available on the target surface (see dimension 6),
  and it is explicit whether the model should execute the script ("Run
  `analyze_form.py`") or read it as reference ("See `analyze_form.py` for
  the algorithm").
- **Scripts have clear documentation** -- what the script does, its
  inputs/outputs, and how to invoke it, not left for the model to infer
  from source.
- **Verifiable intermediate outputs** for high-stakes batch work -- a
  plan -> validate -> execute pattern with a machine-checkable plan file.

## 8. Behavioural evidence

Anthropic's standard is evaluation-*driven* development, not evaluation as
an afterthought: build evaluations **before** writing extensive
documentation. Run the skill's candidate task without the skill first,
document the specific gaps, then write just enough content to close those
gaps and pass at least three scenarios (including the failure/guardrail
case the skill exists to prevent) measured against a documented baseline
of "without the skill." A skill that passes every other dimension but was
never checked against a no-skill baseline may be solving an imagined
problem.

**Check the target repository for an eval mechanism before scoring this
dimension** -- for a Claude Code target, that's an `evals/evals.json` file
usable with the official `skill-creator` plugin
(`/plugin install skill-creator@claude-plugins-official`, per
[Claude Code's own eval-and-iterate docs][cce]); for other targets, an
`evals/` directory or a third-party runner such as
`waza` (`microsoft/waza`) if the repo already uses one. Check whether the
target repository has committed eval data (an `evals/` directory or
`evals/evals.json`) for the specific skill under review -- `skill-creator`
and `waza` may be available as session-local tooling without being part of
the repo; their presence in one session's environment does not make this
dimension "measured" for the repo itself. Whatever the target, never silently skip
this dimension: state plainly that behavioural evidence is unmeasured for
the reviewed skill when no mechanism is committed to the repo, rather than
scoring it pass or fail without one to back the score. This gap-naming need
not sit inline in the `SKILL.md`: a repository may record its per-skill
eval status (baselines, trials, model coverage) centrally in its own
documentation -- for example a `docs/` eval-status file -- rather than in
each skill body, since a vendored skill should not carry the origin repo's
eval-run bookkeeping. Read that documentation before treating an absent
inline gap-disclosure (no `## Known gaps` section) as undisclosed. Do not install
missing eval tooling yourself as part of a review -- propose it to the
operator instead; installing new software (even first-party) is an
irreversible, outward-facing action outside a review's scope, and a
forced install of an unfamiliar third-party tool carries supply-chain
risk.

**`waza check`'s output is useful evidence, but verify its heuristics
against the primary spec before trusting a verdict from it** -- do not
treat a third-party tool's score as equivalent to Anthropic's own bar any
more than a third-party rubric. Three confirmed divergences (checked
against `waza`'s own source, `internal/scoring/scoring.go`,
`microsoft/waza`, and by cross-checking one of its live link checks):
`TokenSoftLimit = 500` is an uncommented constant with no cited
justification -- Anthropic's primary docs say "under 500 *lines*" and
separately budget "under 5k tokens" for the loaded body, a materially
looser number than waza's 500-token soft limit; and waza's `HasTriggers`
heuristic only matches the literal substrings `"when:"`, `"use for:"`,
`"use this skill"`, `"triggers:"`, `"trigger phrases include"` -- it does
NOT match `"Use when ..."`, the exact phrasing Anthropic's own
best-practices doc uses in its canonical example ("Use when working with
PDF files..."). A `waza check` "Compliance Score: Low" driven by that
specific pattern miss is a false negative against the primary spec, not a
real defect -- confirm which heuristic actually fired (the tool's `check`
output states the failing check) before rewriting a description to chase
a third-party tool's score. Third: `waza check`'s link checker performs a
*live* HTTP fetch of every URL a skill's files reference, which reports a
false "broken link" for a genuinely valid GitHub PR URL when the
reviewing session's own network egress is restricted (confirmed: a
`waza check` run in a session where `github.com` page fetches are
proxy-blocked reported an authentic, merged PR URL as "HTTP 404," while
the GitHub API confirmed the PR exists) -- a link failure from this
checker is evidence about the *reviewing environment's* network access,
not necessarily about the link itself; cross-check with a
platform-appropriate tool (e.g. the GitHub API) before treating it as a
real dead link.

**When a skill is being actively iterated, not just reviewed once, require
a strict held-out gate before keeping a change.** [SkillOpt][skillopt]
(Yang et al., "SkillOpt: Executive Strategy for Self-Evolving Agent
Skills", Microsoft, 2026) trains skills as bounded text edits
gated by validation: "a candidate skill is accepted only when its
selection-split score is strictly greater than the current selection
score, so ties are rejected, and the deployed skill never silently
drifts." Two things transfer from that discipline even without SkillOpt's
automated rollout loop: score on data disjoint from whatever produced the
candidate edit (not the same cases that motivated it), and require a
*strict* improvement, not a tie -- "it seems fine" or "it doesn't seem
worse" is not evidence a change helped. Most of gitapex's skills are
judgment/process skills with no automatic verifier or exact-match metric,
so SkillOpt's specific machinery (rollout batches, an optimizer model,
edit budgets) does not directly apply -- but when reviewing a proposed
edit to an *existing* skill, still ask what held-out evidence (a fresh
task run, a previously-failing case, a fresh no-edit baseline) shows the
change is actually better, not merely different.

**When a committed eval suite records a numeric score, gate acceptance on
success/correctness first, and never on elapsed time or token/API cost
alone** -- a faster or cheaper run that did not solve the task is not a
better run. This is the same scorer that produces the selection-split
score described in the held-out-gate paragraph above; nothing below
substitutes for it. Treat elapsed time and
consumed cost as a legitimate but *conditional* axis: valid only as a
cost-versus-accuracy comparison at matched success rate, never a
standalone ranking. Kapoor et al., "AI Agents That Matter" ([kapoor]),
show a cheap, simple agent beating a costlier state-of-the-art agent at
equal-or-better accuracy -- cost only means something once accuracy is
fixed or reported alongside it. Self-reported or single-run time savings
are also not reliable on their own: METR's randomized controlled trial
([metrrct]) found developers self-reporting roughly 20% faster
completion with AI assistance while a real measurement showed them about
19% *slower*. Where repeated trials are cheap enough for the harness,
also record reproducibility -- variance across repeated runs of the same
task, the discipline pass@k ([passk]) formalizes for code generation --
since a skill that passes once and fails on retry is weaker evidence than
a stable pass, even at an identical mean. And a passing functional score
does not clear a run that left an unintended diff, an unresolved
destructive operation, or scope creep beyond the task; record that
alongside the score, not folded into it. None of this is a new rubric
dimension -- it is what this dimension, and a target repository's own
eval-status bookkeeping, should record when the harness can record it;
where it cannot, name the gap the same way a missing baseline or
cross-model run is named above.

## 9. Cross-model robustness

A skill's effect depends on the model running it. Anthropic's own
best-practices doc names the concrete tier spread to test against:

- **Haiku (fast, economical):** does the skill give *enough* guidance?
- **Sonnet (balanced):** is the skill clear and efficient?
- **Opus (powerful reasoning):** does the skill avoid *over*-explaining?

"What works perfectly for Opus might need more detail for Haiku." Judge --
or state that you cannot yet judge -- against every tier in this spread
that the skill is likely to run under.

If the skill targets a tier beyond this documented spread (a newer or
stronger model), the same over-prescription-risk *reasoning* still applies
by extension -- a low-freedom skill tuned for a weaker model can plausibly
over-constrain a stronger one -- but treat any claim specific to a named
tier beyond Haiku/Sonnet/Opus as unverified against Anthropic's current
public docs unless you can cite a primary source for that tier
specifically. Label it as a read, not measured evidence, and say so.

**Transfer testing** is a concrete technique for this dimension, beyond
varying which model tier runs the *same* skill: deploy the skill
*unchanged* on an adjacent target -- a different model, a different
execution harness (e.g. a direct-chat system prompt vs. an agentic CLI
loop), or a nearby task -- and check performance does not fall below that
target's own no-skill baseline. SkillOpt (arXiv:2605.23904, Section 4.3)
reports this concretely: a skill trained inside one execution harness
transferred to a different harness with a real positive gain over that
harness's own no-skill baseline, evidence that "the learned rules are not
only harness-specific command recipes." A skill that only helps in the
exact context it was authored in is a weaker artifact than one that
transfers. Where no transfer data exists (the common case for a
one-off-authored skill with no formal training loop), name that as an
additional unmeasured facet of this dimension rather than folding it
silently into "no cross-model data."

Behaviour observed on one model is not evidence for another. **Check the
target repository for a per-model eval runner before scoring this
dimension** (same check as dimension 8, against a different kind of
harness -- e.g. `skill-creator`'s version-comparison mode, or a
third-party benchmarking tool if the repo already has one). When this
dimension cannot be measured, say so explicitly rather than asserting
robustness from a single-model read. A qualitative read is still allowed
(e.g. "this skill is a fixed low-freedom policy, so over-prescription risk
is probably low, but this is a read, not measured evidence") as long as it
is labeled as such.

## Verdicts

- **Well-formed** -- clears every deterministic shape check (frontmatter,
  naming, description shape, body length, reference depth/TOC). Says
  nothing about whether the skill is good.
- **Mature** -- well-formed, and every dimension 1-7 clears cleanly with no
  named gap (a "minor" gap still means that dimension has not cleared).
  Dimensions 8-9 are the one exception: because they depend on tooling a
  target repository may not have yet, either measured or explicitly named
  as an unmeasured gap (never silently assumed) is sufficient for them
  specifically -- naming the gap does not, on its own, block "mature" the
  way an uncleared dimension 1-7 gap does.

A verdict without cited evidence per dimension is not a review -- it is a
guess wearing a review's shape.

A **mature** verdict is bounded by what the target repository can currently
measure: when dimensions 8-9 are named as unmeasured rather than passed,
"mature" means "clears everything that repository's tooling can check
today," not "proven in behaviour." That named gap is the explicit, recorded
acknowledgment a live-proof gate requires -- it does not itself waive any
live-proof check the reviewing repository applies before landing other
kinds of changes.

**Well-formed** and **mature** both presuppose *whole-artifact* mechanism
fit -- the skill is the right container (not better as a hook, subagent, or
CLAUDE.md content). A step-level finding (Skill-step vs. bundled script, or
Model/effort tier fit) is reported for triage but does not by itself block
either verdict.

A skill can be well-formed or even mature by every dimension below and
still be the wrong artifact -- content that should be a hook, CLAUDE.md, or a
subagent, dressed up as a well-written skill. A wrong-mechanism finding
(see [Mechanism fit](#mechanism-fit)) is reported alongside, not
replaced by, the well-formed/mature verdict: naming both is more useful
than picking one, since a reviewer fixing the mechanism still needs to
know whether the content itself was any good.

## References

Every inline `[label]` citation above resolves to the source below.

- **[ab]** Anthropic -- Skill authoring best practices.
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- **[ao]** Anthropic -- Agent Skills overview.
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>
- **[cc]** Anthropic -- Claude Code skills.
  <https://code.claude.com/docs/en/skills>
- **[cce]** Anthropic -- Claude Code skills, Evaluate and iterate on a skill.
  <https://code.claude.com/docs/en/skills#evaluate-and-iterate-on-a-skill>
- **[skillopt]** Yang et al., SkillOpt: Executive Strategy for Self-Evolving
  Agent Skills, Microsoft, 2026 (arXiv:2605.23904).
  <https://arxiv.org/abs/2605.23904>
- **[dbc]** Bertrand Meyer, Applying "Design by Contract", IEEE Computer
  25(10):40-51, October 1992.
  <https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf>
- **[soc]** E. W. Dijkstra, On the role of scientific thought (EWD447), 1974;
  reprinted in Selected Writings on Computing: A Personal Perspective,
  Springer-Verlag, 1982.
  <https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html>
- **[steering]** Anthropic -- Steering Claude Code: skills, hooks, subagents
  and more.
  <https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more>
- **[fable]** Thariq Shihipar, Anthropic -- A Field Guide to Fable: Finding
  Your Unknowns.
  <https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns>
- **[modeleffort]** Lydia Hallie, Anthropic (Claude Code team) -- Choosing
  a Claude model and effort level in Claude Code.
  <https://claude.com/blog/claude-model-and-effort-level-in-claude-code>
- **[kapoor]** Kapoor, Stroebl, Siegel, Nadgir, Narayanan -- AI Agents That
  Matter, 2024 (arXiv:2407.01502).
  <https://arxiv.org/abs/2407.01502>
- **[passk]** Chen et al. -- Evaluating Large Language Models Trained on
  Code, OpenAI, 2021 (arXiv:2107.03374).
  <https://arxiv.org/abs/2107.03374>
- **[metrrct]** Becker, Rush, Barnes, Rein -- Measuring the Impact of
  Early-2025 AI on Experienced Open-Source Developer Productivity, METR,
  2025 (arXiv:2507.09089).
  <https://arxiv.org/abs/2507.09089>

<!-- Link reference definitions below power the inline [label] shortcuts; keep in sync with the visible list above. -->

[ab]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices "Anthropic -- Skill authoring best practices"
[ao]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview "Anthropic -- Agent Skills overview"
[cc]: https://code.claude.com/docs/en/skills "Anthropic -- Claude Code skills"
[cce]: https://code.claude.com/docs/en/skills#evaluate-and-iterate-on-a-skill "Anthropic -- Claude Code skills, Evaluate and iterate on a skill"
[skillopt]: https://arxiv.org/abs/2605.23904 "Yang et al., SkillOpt: Executive Strategy for Self-Evolving Agent Skills, Microsoft, 2026 (arXiv:2605.23904)"
[kapoor]: https://arxiv.org/abs/2407.01502 "Kapoor, Stroebl, Siegel, Nadgir, Narayanan -- AI Agents That Matter, 2024 (arXiv:2407.01502)"
[passk]: https://arxiv.org/abs/2107.03374 "Chen et al. -- Evaluating Large Language Models Trained on Code, OpenAI, 2021 (arXiv:2107.03374)"
[metrrct]: https://arxiv.org/abs/2507.09089 "Becker, Rush, Barnes, Rein -- Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity, METR, 2025 (arXiv:2507.09089)"
[dbc]: https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf "Bertrand Meyer, Applying \"Design by Contract\", IEEE Computer 25(10):40-51, October 1992"
[soc]: https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html "E. W. Dijkstra, On the role of scientific thought (EWD447), 1974; reprinted in Selected Writings on Computing: A Personal Perspective, Springer-Verlag, 1982"
[steering]: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more "Anthropic -- Steering Claude Code: skills, hooks, subagents and more"
[fable]: https://claude.com/blog/a-field-guide-to-claude-fable-finding-your-unknowns "Thariq Shihipar, Anthropic -- A Field Guide to Fable: Finding Your Unknowns"
[modeleffort]: https://claude.com/blog/claude-model-and-effort-level-in-claude-code "Lydia Hallie, Anthropic (Claude Code team) -- Choosing a Claude model and effort level in Claude Code"

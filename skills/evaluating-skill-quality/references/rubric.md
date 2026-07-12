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
- [Contract discipline](#contract-discipline)
- [Mechanism fit](#mechanism-fit)
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
discipline](#contract-discipline) above) -- the three-way decision
(skill vs. subagent, skill vs. hook, skill vs. CLAUDE.md) lives in
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

A wrong-mechanism finding is not one of the nine dimensions and is not
folded into the well-formed/mature ladder: report it as the review's
headline finding regardless of how the rest of the review scores, per
`SKILL.md`'s Procedure step 2 and Stop boundaries.

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
- **Repository-scoped** -- a repository-scoped skill that reads as if it
  were portable is a dimension-1/6 defect (it misleads a future vendoring
  decision), not the scoping choice itself. An undeclared level that
  turns out to be repository-scoped is itself a finding, not something to
  silently infer and move past.
- **Mixed** -- dimension 5 (progressive disclosure) requires the actual
  split, not just the intent to split: the repository-specific part
  belongs in a clearly named reference file (e.g.
  `references/this-repo-only.md`) a consumer can identify and drop, not
  blended into the portable core.

## 1. Discovery -- name and description

`SKILL.md`'s deterministic checklist confirms a trigger *exists* (present,
no XML tags, under the length cap). This dimension judges whether it is
the *right* trigger -- whether the skill would win its intended request
and lose a neighbour's. Per Anthropic's best-practices doc, `name` and
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

- **Fail:** explaining what a well-known format or tool is; restating the
  same instruction in two places; motivational padding.
- **Pass:** assumes competence, states only the project- or task-specific
  delta, reaches actionable content fast.

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

## 5. Progressive disclosure

`SKILL.md`'s deterministic checklist confirms reference depth and TOC
presence by shape. This dimension judges the *meaning* behind the split --
naming, linking, and whether the common case is forced through more than
one read.

- Reference files named for content (`decision-handoff.md`, not `doc2.md`),
  organised by domain.
- `SKILL.md` links to each reference at the point of need, so the model
  loads it on demand instead of guessing it exists. An unlinked reference is
  dead weight; a needed one with no pointer is invisible.
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
- For a skill declared (or read as) **Portable** (see
  [Portability level](#portability-level)): no procedural step reads,
  cites as authority, or branches on a path outside the skill's own
  folder. A citation to the origin repository purely as illustrative
  context (a worked example, a "here is what this looked like once") is
  fine; a step that tells the model to go check a repository-specific
  path to decide what to do next is not -- that path breaks the moment
  the skill is copied elsewhere.

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
`waza` (`microsoft/waza`) if the repo already uses one. gitapex has
neither an `evals/evals.json` nor an `evals/` directory committed to the
repo today; `skill-creator` and `waza` are available in some review
sessions but are session-local tooling, not part of the repo -- their
presence in one session's environment does not make this dimension
"measured" for the repo itself. Whatever the target, never silently skip
this dimension: state plainly that behavioural evidence is unmeasured for
the reviewed skill when no mechanism is committed to the repo, rather than
scoring it pass or fail without one to back the score. Do not install
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

**Well-formed** and **mature** both presuppose mechanism fit. A skill can
be well-formed or even mature by every dimension below and still be the
wrong artifact -- content that should be a hook, CLAUDE.md, or a
subagent, dressed up as a well-written skill. A wrong-mechanism finding
(see [Mechanism fit](#mechanism-fit)) is reported alongside, not
replaced by, the well-formed/mature verdict: naming both is more useful
than picking one, since a reviewer fixing the mechanism still needs to
know whether the content itself was any good.

## References

[ab]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices "Anthropic -- Skill authoring best practices"
[ao]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview "Anthropic -- Agent Skills overview"
[cc]: https://code.claude.com/docs/en/skills "Anthropic -- Claude Code skills"
[cce]: https://code.claude.com/docs/en/skills#evaluate-and-iterate-on-a-skill "Anthropic -- Claude Code skills, Evaluate and iterate on a skill"
[skillopt]: https://arxiv.org/abs/2605.23904 "Yang et al., SkillOpt: Executive Strategy for Self-Evolving Agent Skills, Microsoft, 2026 (arXiv:2605.23904)"
[dbc]: https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf "Bertrand Meyer, Applying \"Design by Contract\", IEEE Computer 25(10):40-51, October 1992"
[steering]: https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more "Anthropic -- Steering Claude Code: skills, hooks, subagents and more"

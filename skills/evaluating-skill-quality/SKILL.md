---
name: evaluating-skill-quality
description: Review a SKILL.md (and its references/) against a nine-dimension quality rubric, separating deterministic shape from probabilistic maturity, citing concrete evidence per dimension. Use when reviewing any SKILL.md -- this repository's own or one vendored from elsewhere -- before merging, vendoring, or shipping it, for a one-shot static quality verdict; see battle-testing-a-skill for adversarial hostile-input probing, and scorer-gated-skill-edits for a measured edit loop, instead.
---

# Evaluating Skill Quality

Judging whether a `SKILL.md` is well-authored is a distinct review lane from
diff-correctness review or issue/PR contract review: it asks whether the
skill artifact itself is good, not whether a change is correct.

## Two lanes

- **Deterministic shape** -- fixed rules a script decides, not judgment.
  Run the bundled checker on the target skill dir, giving both paths from
  the same working directory -- e.g. from the repo root:
  `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py <skill-dir>`
  (stdlib-only, read-only). It is the single source of truth for the exact
  rules and limits and prints PASS/FAIL per check. On a
  Python-less surface, apply the same rules by reading that script's
  check list (its module docstring enumerates them). The nine maturity
  dimensions below are deliberately not scripted. The six sidecar checks
  assume the target lives in a repository that has adopted this metadata
  convention; when the target is a skill vendored from one that has not,
  those checks fail as expected -- not a defect in the reviewed skill --
  so record them as not-applicable and say so explicitly in the report
  rather than reporting six failures as findings.
- **Probabilistic maturity** -- nine dimensions of judgment that need a model
  or human, not a script. Full rubric with pass/fail evidence:
  [references/rubric.md](references/rubric.md).

## Mechanism fit

Before grading a `SKILL.md`'s content, check it is even the right
container -- skills compete with CLAUDE.md, rules, subagents, hooks,
output styles, and appending the system prompt, each trading context
cost against authority differently. A well-written skill that should
have been a different mechanism is not fixed by polishing it further.

- **Skill vs. subagent**: a skill plays out *in the main thread*, visible
  and steerable step by step. A subagent runs isolated; only its final
  summary returns. A side task whose intermediate results won't be
  referenced again (a deep search, a log-analysis pass, a dependency
  audit) belongs in a subagent, not a skill. A second, distinct trigger:
  when the main thread has plausibly already seen, authored, or discussed
  the specific target under review, the judgment-bearing step itself
  belongs in a fresh subagent dispatch for isolation -- even though its
  full output *is* referenced again. Steerability survives because the
  dispatch returns complete cited reasoning, not a bare summary; see
  Subagent dispatch below, which this skill applies to itself.
- **Skill vs. hook**: a skill is an instruction the model *chooses* to
  follow; a hook fires *deterministically*. "Every time X, always do Y"
  (a formatter after every edit) or "never do this" (an absolute
  prohibition) needs deterministic backing, not prose alone. Flag any
  safety-critical prohibition in the reviewed skill with no hook or
  permission backing -- see `references/rubric.md`'s Mechanism fit section
  for why a prompted rule fails under pressure.
- **Skill vs. CLAUDE.md**: CLAUDE.md is for facts Claude should hold
  *all the time*; a skill is for a *procedure*, loaded only when
  invoked. Static facts with no real steps probably belong in CLAUDE.md
  instead; a multi-step procedure crammed into CLAUDE.md is the
  mirror-image mistake.
- **Skill-step vs. bundled script**: a deterministic step *inside* a
  skill's procedure is not event-bound, so a hook cannot own it; delegate
  it to a bundled script the skill calls, rather than re-reasoning it in
  prose each run, when the break-even favours it. A single trivial check
  stays in-model. This is a step-level finding, not a whole-artifact
  wrong-mechanism one -- the break-even test and rationale (correctness,
  consistency, cost) are in `references/rubric.md`'s Mechanism fit section.
- **Model/effort tier fit**: when the reviewed skill's own content --
  prose instructions or a bundled Workflow script -- pins a specific
  model tier or reasoning-effort level for itself or a sub-dispatch, that
  pin needs its own justification, the same way a mechanism choice does.
  Most skills correctly omit both and inherit the caller's; that absence
  is not a finding. Also a step-level finding, not a whole-artifact one
  -- criteria and citation are in `references/rubric.md`'s Mechanism fit
  section. Runs at step 2, before the sidecar is read at step 4, and
  stays declaration-independent: the capability-assumption
  declaration-vs-pin cross-check is step 4's job, not this one's.
- **Tool-capability verification**: when the reviewed skill's own content
  cites a specific tool or MCP subcall as able to detect, verify, or
  reconstruct something -- most often inside a Stop boundary or a
  guardrail step -- check that claim against the tool's actual
  schema/docs before accepting it; a plausible-sounding capability claim
  is not evidence the cited tool actually supports it. Also a step-level
  finding, not a whole-artifact one -- criteria and citation are in
  `references/rubric.md`'s Mechanism fit section.

Full rationale and citation: [references/rubric.md](references/rubric.md)'s
Mechanism fit section.

## Subagent dispatch

Procedure steps 1, 2, 4, 5, and 6 read, grade, and issue a verdict on the
target directly -- run them inside **one fresh subagent dispatch**, not
the invoking context. A main thread that just authored, defended, or
extensively discussed the target is not a neutral grader; an instruction
to "review it fairly anyway" is weaker than an actually isolated context,
and that includes the final verdict (step 6), not only the dimension
walk -- a main thread that only relays evidence but re-synthesizes the
verdict itself would still be grading from a contaminated context.

- Give the dispatch only the target's path (or content) and a pointer to
  this skill's own `references/rubric.md` -- never the calling
  conversation's framing, prior discussion, or opinion of the target.
- Required, not optional: when the calling repository carries its own
  project-instruction file (for example `CLAUDE.md` or `AGENTS.md`),
  exclude that file from the dispatch's context before dispatching, using
  whatever mechanism the harness provides for that (a project-instruction-
  file-free scratch copy, an auto-load-disabling flag, an isolated or
  headless invocation, or equivalent). A dispatch that inherits the calling
  repository's own instructions is not the neutral grading context this
  section exists to guarantee, and the omission must not depend on a human
  asking whether it happened. Requesting the exclusion is not proof it
  held: before treating the dispatch as ready, confirm with an observable
  check (e.g. list or search the chosen scratch location and its full
  directory ancestry for `CLAUDE.md`/`AGENTS.md` and require the result to
  be empty) rather than trusting intent. If the harness offers none of the
  listed mechanisms, that is itself a blocker -- stop and escalate rather
  than dispatching into a contaminated context. Whether this exclusion
  carries real deterministic backing (a hook, a permission rule) or is
  enforced by this instruction alone depends on the environment the
  dispatch actually runs in -- check directly rather than assuming either
  way, the same self-audit this skill already applies to its
  eval-tooling-install Stop boundary below.
- Hand the dispatch step 3's shape-checker output as an established fact
  rather than having it re-run the script itself (Contract discipline's
  "never both" rule, `references/rubric.md`).
- Require the dispatch to return the full structured report -- mechanism
  fit, portability level, all nine dimensions with quoted evidence, and
  the verdict -- not a bare summary; a postcondition with no cited
  evidence is not a review.
- When the target has Stop boundaries or Mechanism-fit prose, instruct
  the dispatch explicitly to check each such sentence against *both*
  Mechanism fit's "is this backed" question and the portability litmus
  test's "would this exact wording survive being read in an unrelated
  repository" question (`references/rubric.md`'s Portability level
  section) -- the dispatch's default nine-dimension walk answers the
  first by habit and can silently skip the second unless told to ask it
  separately.
- The main thread's own job is only step 3 (run the shape checker first,
  before dispatching) and relaying the dispatch's report -- including the
  verdict the dispatch already issued in step 6 -- to the human verbatim,
  never independently issuing or revising one. Clarifying
  questions about evidence already returned can be answered directly from
  that report; a challenge that could change a verdict gets a second,
  independent fresh dispatch (carrying the challenge and the target's
  path, not the first dispatch's reasoning) rather than a revision made
  in place -- the same fault-attribution rule that governs a
  misclassified precondition (`references/rubric.md`, Contract
  discipline) applies to a misgraded dimension.
- Optional upgrade, not a requirement: on a harness with a multi-agent
  orchestration mechanism (this repository's own CLAUDE.md points to
  superpowers' `dispatching-parallel-agents` / `subagent-driven-
  development`; some Claude Code sessions carry a `Workflow` tool whose
  "adversarial verify" / "judge panel" patterns run several independent
  dispatches and cross-check them), the single dispatch above can become
  several. A harness with only a single-agent dispatch primitive still
  gets the isolation benefit from one fresh dispatch -- named here as an
  illustrative example, not something this procedure depends on to
  function.

## Portability level

Establish this (declared, or read from actual content) before walking
the nine dimensions -- it changes how dimensions 1, 5, 6, and 8 grade.
Checkable from this file alone; no need to open `references/rubric.md`
just to classify it.

- **Portable**: every instruction controlling the skill's behavior (a
  check run, a path read, a command executed) resolves inside the
  skill's own folder, or cites only general product-level docs.
  References to the origin repo as *context*/example are fine;
  references the *procedure* depends on to function are not. Apply this
  to every sentence, not only executed steps: a **declarative
  fact-claim** ("backed by this plugin's `X`," "this repo's tests
  currently number N") fails Portable exactly like a runtime path-read
  does, if it would go false once copied elsewhere. Stop boundaries and
  Mechanism-fit prose are the highest-risk spot for this -- see
  `references/rubric.md`'s Portability level section for the full
  litmus test.
- **Repository-scoped**: intentionally depends on the origin repo's own
  tooling or conventions. Legitimate, but must say so explicitly, as a
  `portability` field in the skill's `metadata/gitapex.yaml` sidecar (the
  `portability-declared` shape check enforces its presence and value) --
  undeclared-but-repository-scoped is itself a finding. Extended rationale
  belongs in a footer `## Notes` section of `SKILL.md`.
- **Mixed**: a portable core plus repo-specific detail should split the
  two into a clearly named reference file, not blend them.

A bare GitHub issue/PR-number citation (`#149`, `owner/repo#149`) is barred
from `SKILL.md`/`references/*.md` at every level, Mixed and
Repository-scoped included -- unlike repo-specific paths and other
repo-specific content, which stay legitimate at those two levels.

Full rationale and per-dimension grading detail:
[references/rubric.md](references/rubric.md)'s Portability level section.

## Unknowns framework

Full rationale: [references/rubric.md](references/rubric.md)'s Unknowns
framework section. Four kinds of gap between what a `SKILL.md` states and
what this review actually checks -- known knowns, known unknowns, unknown
knowns, unknown unknowns (adapted from Anthropic's own field guide on
working with Claude models, cited in rubric.md) -- and the **Blind spot
pass**: before walking the nine dimensions (Procedure step 2, alongside
Mechanism fit), name explicitly whether the target's domain exposes a
rubric gap none of dimensions 1-9, Mechanism fit, or Portability level
already covers, or state explicitly that none was found. Not a tenth
dimension; the fixed nine-dimension count is unchanged.

## Capability assumption

Declared alongside portability in the skill's `metadata/gitapex.yaml`
sidecar, as `spec.capabilityAssumption`. It records which compute /
model-capability regime the skill was authored for, and calibrates how
strictly dimensions 2 (Conciseness), 3 (Degree of freedom), and 9
(Cross-model robustness) grade against that stated target. Dimension 5
(Progressive disclosure) gets an effect only for **Adaptive** -- Broad and
Frontier leave dimension 5 grading unchanged, since Adaptive's own
definition (a lean body plus deeper `references/`) is itself a
progressive-disclosure claim while the other two say nothing about
layering. Full per-dimension detail:
[references/rubric.md](references/rubric.md)'s Capability assumption
section.

Distinct from Mechanism fit's Model/effort tier fit check: that judges a
model or effort *pin the skill's own content makes*, which the invoking
agent acts on at runtime, and fires only when such a pin actually exists
(most skills correctly have none, and zero of this repository's 17 skills
do today). This declaration pins nothing and never executes -- it
recalibrates the *reviewer's* grading strictness and has full coverage
over every skill regardless of whether that skill pins anything. The two
checks are never merged, and the one place they interact -- a declared
level that contradicts a pin the same skill's own content makes (e.g.
declaring Frontier while pinning a weak model onto a judgment step) --
has exactly one owner: Procedure step 4 below, not the tier-fit check at
step 2. Tier fit runs before the sidecar is even read and stays
declaration-independent by design.

- **Broad** -- authored to stay effective down to a weak or economical
  model, or a constrained harness.
- **Frontier** -- authored assuming a strong-reasoning model; does not
  target weak tiers.
- **Adaptive** -- a lean body a strong model runs directly, plus deeper
  `references/` a weaker model pulls on demand.

Authors still declare one of these three levels correctly now -- the
`capability-assumption-declared` shape check gates the value. Full
detail: [references/rubric.md](references/rubric.md)'s Capability
assumption section.

## Lifecycle

Optional. Three independent sub-blocks plus one plain scalar under
`spec.lifecycle` in the skill's `metadata/gitapex.yaml` sidecar (the
`lifecycle-well-formed` shape check enforces their shape when present) --
a skill declaring none of them is implicitly **Stable**, the state every
skill in this repository is in today:

```yaml
spec:
  lifecycle:
    experimental:
      reason: why this skill is not yet proven
      trackingIssue: "#123"      # tracks graduation to Stable
      since: "2026-07-21"        # optional, YYYY-MM-DD
    deprecated:
      reason: why this skill is deprecated
      replacement: name-of-sibling-skill
      since: "2026-07-21"        # optional, YYYY-MM-DD
      removeAfter: "2026-10-01"  # optional, YYYY-MM-DD, documentation only
    stable:
      since: "2026-07-21"        # when this skill graduated
      compatibilityGuarantee: GA # optional: Alpha | Beta | GA
    renamedFrom: old-skill-name  # optional, this skill's former directory name
```

- **`experimental`**: `reason` and `trackingIssue` are required once this
  block is present at all; `since` is optional. `trackingIssue` must be
  an anchored `#123` or `owner/repo#123` reference.
- **`deprecated`**: `reason` and `replacement` are required once this
  block is present at all; `since`/`removeAfter` are optional.
  `replacement` must name an existing sibling skill directory (the
  `lifecycle-deprecated-replacement-resolves` shape check enforces this
  -- the same dangling-reference gate `spec.skillDependencies` uses).
- **`stable`**: `since` is required once this block is present at all
  (`compatibilityGuarantee`, if given, must be one of `Alpha`/`Beta`/
  `GA` -- Kubernetes' API-stability tiers). `experimental` and `stable`
  cannot both be present: "not yet graduated" and "already graduated on
  some date" are a real contradiction, unlike `experimental`+
  `deprecated`, which stays ungated (an experimental skill can
  legitimately be superseded by a different experiment).
- **`renamedFrom`**: a plain scalar, not a sub-block, naming this same
  skill's former directory name. Deliberately backward-pointing and
  **not** resolved against sibling directories, unlike
  `deprecated.replacement` -- the old name is expected to no longer
  exist (a `git mv` deletes it), so there is nowhere to host a
  forward-pointing record on the old side.
- `since`/`removeAfter`, when given, must be real `YYYY-MM-DD` dates.
  `removeAfter` documents an intended removal date only; no automation in
  this repository deletes a skill once that date passes, and no
  automation graduates a skill out of `experimental` when its
  `trackingIssue` closes.
- None of these declarations change how any of the nine dimensions
  grade, and no skill's own runtime procedure may read or branch on any
  of them -- this is metadata only, same as Portability level and
  Capability assumption.

Full rationale: [references/rubric.md](references/rubric.md)'s Lifecycle
section.

## Procedure

Steps 1-4 are this review's precondition, step 6 its postcondition --
see `references/rubric.md`'s Contract discipline section. Steps 1, 2, 4,
5, and 6 execute inside the fresh subagent dispatch described in
Subagent dispatch above -- the dispatch issues the verdict as part of
its structured report, not the main thread. Only step 3 runs directly in
the main thread, before the dispatch; the main thread's remaining job
after the dispatch returns is to relay its report (including the
verdict it already issued) verbatim -- never to independently issue or
re-derive one.

1. Read the target `SKILL.md` and every file in its `references/`
   directory (not only linked ones -- an unlinked file is itself a
   dimension-5 finding).
2. Check mechanism fit per the section above. A whole-artifact
   wrong-mechanism finding (the skill should have been a hook, subagent,
   or CLAUDE.md content) is the headline finding of the review -- report
   it even if the rest of the review still completes. The step-level
   Skill-step vs. bundled script finding is the exception: report it for
   triage, not as the headline. Also run the Blind spot pass per the
   Unknowns framework section above -- name a rubric gap if the target's
   domain exposes one, or state explicitly that none was found.
3. Run the deterministic shape checker per the Two lanes section above (or
   apply its checks by hand where Python is unavailable); cite the exact
   violation.
4. Read the skill's `metadata/gitapex.yaml` sidecar and establish both its
   portability level and its capability assumption per the sections above.
   Check the declared capability assumption against any model/effort pin
   step 2 already found: a `Frontier` declaration paired with a
   weak-tier pin is a contradiction, named here once -- this is the
   declaration-vs-pin consistency check's one owner, not step 2's
   Model/effort tier fit. When the target has no sidecar (e.g. vendored
   from a repository that has not adopted this convention), establish
   both by reading the target's content instead -- the same way an
   undeclared level is read today -- and note the sidecar's absence as
   context, not as a finding.
5. Walk all nine dimensions in `references/rubric.md`, in order (including
   8-9), quoting the specific text that earns each verdict; assume steps
   1-4 hold rather than re-deriving them. No cited evidence means no
   review happened.
6. Issue a verdict per `references/rubric.md`'s Verdicts section, inside
   the same dispatch as steps 1, 2, 4, and 5. The main thread relays this
   verdict verbatim; it does not issue or re-derive its own.

Worked example of steps 2-6, applied to a real merged skill:
[references/worked-example-explaining-the-work.md](references/worked-example-explaining-the-work.md).
This skill applied to itself, including the mechanism-fit and
portability checks:
[references/worked-example-self-review.md](references/worked-example-self-review.md).

## Scope

Beyond the bundled read-only shape checker (`scripts/check_skill_shape.py`),
this skill carries the rubric; it does not build an eval suite or
benchmarking harness for any target repo -- separate, deferred work. Do
not expand the bundled checker into a general-purpose linter or add
checks beyond the deterministic shape rules and what `references/rubric.md`
actually specifies.

## Stop boundaries

- Never approve a skill solely because the deterministic shape checks pass
  -- shape proves well-formed, not mature.
- Never issue a bare "looks fine" / "LGTM" verdict without citing evidence
  (a quote, a line, a count) per dimension.
- Never claim a violation the reviewed text does not actually show. If a
  dimension cannot be assessed, say that explicitly instead of guessing.
- Never cite a third-party derivative as authoritative for a platform-
  behavior claim. Ground those in Anthropic's primary docs
  (`platform.claude.com`, `code.claude.com`) or the target's observed
  state -- re-fetch when in doubt, don't trust a memorized summary.
- Never install eval tooling for a target repo (`skill-creator`, `waza`, an
  eval suite, etc.) as part of a review without the operator's go-ahead --
  propose it instead (dimension 8). Whether that prohibition has real
  deterministic backing (a PreToolUse hook blocking install commands, a
  permission rule) or is prose-only depends on the environment this
  dispatch is actually running in -- check directly rather than assuming
  either way; if a target repository has such a hook, that is real
  enforcement, and if it does not, this boundary is currently prose-only
  and worth naming as a Mechanism-fit gap the same way any other
  unenforced safety-critical prohibition would be. The skill's own
  bundled `scripts/check_skill_shape.py` is not such an install -- it
  ships with the skill and only reads.
- Never patch a wrong verdict by adjusting step 5 when the real fault was
  a wrong precondition (steps 1-4). Redo the precondition instead -- the
  bug lives where the wrong assumption was made (rubric.md, Contract
  discipline).
- Never let a strong nine-dimension score excuse a wrong-mechanism
  finding (step 2). A well-formed, mature skill that should have been a
  hook or CLAUDE.md content is still the wrong artifact.
- Never include the calling conversation's framing, prior discussion, or
  opinion of the target in the subagent dispatch prompt -- pass only the
  target's path/content and this skill's own reference material.
- Never dispatch the review into a context that still carries the calling
  repository's own project-instruction file (`CLAUDE.md`, `AGENTS.md`, or
  equivalent). Strip it via the harness's own means -- a clean scratch copy,
  an auto-load-disabling flag, an isolated invocation -- before the dispatch
  starts, not after a human catches the contamination by asking. Do not
  treat requesting the strip as proof it held -- confirm it with the
  observable check the Subagent dispatch section requires. Whether this
  boundary carries real deterministic backing or is enforced by this
  instruction alone depends on the running environment; check directly, the
  same self-audit the eval-tooling-install boundary above already applies,
  rather than assuming either way.
- Never revise a dimension verdict in the main thread after the dispatch
  returns it. A wrong or contested verdict is fixed by a second,
  independent dispatch, not a patch made in place.
- Never leave the Blind spot pass unaddressed -- an explicit "no gap found"
  and a silently skipped question are not the same thing; the latter is
  not a completed review.

## Notes

Portability rationale: self-contained -- carries its own rubric and bundled
read-only `check_skill_shape.py`; cites only general Anthropic product
docs, no this-repository tooling. The declared level itself lives in
`metadata/gitapex.yaml`.

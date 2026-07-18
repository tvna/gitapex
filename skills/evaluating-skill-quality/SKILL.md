---
name: evaluating-skill-quality
description: Review a SKILL.md (and its references/) against a nine-dimension quality rubric, separating deterministic shape from probabilistic maturity, citing concrete evidence per dimension. Use when reviewing any SKILL.md -- this repository's own or one vendored from elsewhere -- before merging, vendoring, or shipping it, for a one-shot static quality verdict; see battle-testing-a-skill for adversarial hostile-input probing, and gated-skill-edits for a measured edit loop, instead.
---

# Evaluating Skill Quality

**Portability: Portable.** Self-contained -- carries its own rubric and
bundled read-only `check_skill_shape.py`; cites only general Anthropic
product docs, no this-repository tooling.

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
  dimensions below are deliberately not scripted.
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
- Hand the dispatch step 3's shape-checker output as an established fact
  rather than having it re-run the script itself (Contract discipline's
  "never both" rule, `references/rubric.md`).
- Require the dispatch to return the full structured report -- mechanism
  fit, portability level, all nine dimensions with quoted evidence, and
  the verdict -- not a bare summary; a postcondition with no cited
  evidence is not a review.
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
  references the *procedure* depends on to function are not.
- **Repository-scoped**: intentionally depends on the origin repo's own
  tooling or conventions. Legitimate, but must say so explicitly, as a
  terse one-line marker on the first body line after the H1 (the
  `portability-near-top` shape check enforces presence within the first
  6 body lines) -- undeclared-but-repository-scoped is itself a finding.
  Extended rationale belongs in a footer `## Notes` section of the same
  file.
- **Mixed**: a portable core plus repo-specific detail should split the
  two into a clearly named reference file, not blend them.

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
4. Establish the skill's portability level per the section above.
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
  propose it instead (dimension 8), backed by this plugin's
  `hooks/check-bash-safety.sh` PreToolUse hook, which blocks install
  commands run via Bash. The skill's own bundled
  `scripts/check_skill_shape.py` is not such an install -- it ships with
  the skill and only reads.
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
- Never revise a dimension verdict in the main thread after the dispatch
  returns it. A wrong or contested verdict is fixed by a second,
  independent dispatch, not a patch made in place.
- Never leave the Blind spot pass unaddressed -- an explicit "no gap found"
  and a silently skipped question are not the same thing; the latter is
  not a completed review.

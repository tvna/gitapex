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
  audit) belongs in a subagent, not a skill.
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

## Procedure

Steps 1-4 are this review's precondition, step 6 its postcondition --
see `references/rubric.md`'s Contract discipline section.

1. Read the target `SKILL.md` and every file in its `references/`
   directory (not only linked ones -- an unlinked file is itself a
   dimension-5 finding).
2. Check mechanism fit per the section above. A whole-artifact
   wrong-mechanism finding (the skill should have been a hook, subagent,
   or CLAUDE.md content) is the headline finding of the review -- report
   it even if the rest of the review still completes. The step-level
   Skill-step vs. bundled script finding is the exception: report it for
   triage, not as the headline.
3. Run the deterministic shape checker per the Two lanes section above (or
   apply its checks by hand where Python is unavailable); cite the exact
   violation.
4. Establish the skill's portability level per the section above.
5. Walk all nine dimensions in `references/rubric.md`, in order (including
   8-9), quoting the specific text that earns each verdict; assume steps
   1-4 hold rather than re-deriving them. No cited evidence means no
   review happened.
6. Issue a verdict per `references/rubric.md`'s Verdicts section.

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

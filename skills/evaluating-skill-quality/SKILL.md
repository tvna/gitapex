---
name: evaluating-skill-quality
description: Review a SKILL.md (and its references/) against a nine-dimension quality rubric, separating deterministic shape from probabilistic maturity, citing concrete evidence per dimension. Use when reviewing any SKILL.md -- this repository's own or one vendored from elsewhere -- before merging, vendoring, or shipping it.
---

# Evaluating Skill Quality

Judging whether a `SKILL.md` is well-authored is a distinct review lane from
diff-correctness review or issue/PR contract review: it asks whether the
skill artifact itself is good, not whether a change is correct.

## Two lanes

- **Deterministic shape** -- fixed rules a checker script would decide if
  the target repository has one (e.g. `scripts/check_skills.py`); check by
  hand otherwise. Sources and the Claude-Code-vs-generic-spec split:
  `references/rubric.md` dimension 1. `description`: non-empty, no XML
  tags, <= 1024 chars, states what and when. `name`, if present:
  lowercase-hyphenated, <= 64 chars, no XML tags, no reserved word
  (`anthropic`, `claude`); optional in Claude Code and need not match the
  directory. `SKILL.md` body <= 500 lines. `references/` files: one level
  deep, table of contents past 100 lines.
- **Probabilistic maturity** -- nine dimensions of judgment that need a model
  or human, not a script. Full rubric with pass/fail evidence:
  [references/rubric.md](references/rubric.md).

## Procedure

1. Read the target `SKILL.md` and every file in its `references/`
   directory (not only linked ones -- an unlinked file is itself a
   dimension-5 finding).
2. Check the deterministic shape list above; cite the exact violation.
3. Establish the skill's portability level (declared, or read from its
   actual content) per `references/rubric.md`'s Portability level
   section -- it changes how dimensions 1, 5, 6, and 8 grade below.
4. Walk all nine dimensions in `references/rubric.md`, in order (including
   8-9), quoting the specific text that earns each verdict. No cited
   evidence means no review happened.
5. Issue a verdict per `references/rubric.md`'s Verdicts section.

Worked example of steps 2-5, applied to a real merged skill:
[references/worked-example-explaining-the-work.md](references/worked-example-explaining-the-work.md).
This skill applied to itself, including the portability check:
[references/worked-example-self-review.md](references/worked-example-self-review.md).

## Scope

This skill carries the rubric; it does not build a checker script, eval
suite, or benchmarking harness for any target repo -- separate, deferred
work. Do not expand into a general-purpose linter or add checks beyond
what `references/rubric.md` actually specifies.

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
- Never install eval tooling (a checker script, `skill-creator`, `waza`,
  etc.) as part of a review without the operator's go-ahead -- propose it
  instead (dimension 8).

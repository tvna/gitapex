---
name: evaluating-skill-quality
description: Review a SKILL.md (and its references/) against a nine-dimension quality rubric, separating deterministic shape from probabilistic maturity, citing concrete evidence per dimension. Use when reviewing any SKILL.md -- gitapex's own or one vendored from an upstream plugin -- before merging, vendoring, or shipping it.
---

# Evaluating Skill Quality

Judging whether a `SKILL.md` is well-authored is a distinct review lane from
diff-correctness review or issue/PR contract review: it asks whether the
skill artifact itself is good, not whether a change is correct.

## Two lanes

- **Deterministic shape** -- fixed rules a script would decide if gitapex had
  one (it does not yet; see `docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`
  Non-goals). Check these by hand every time: frontmatter present; `name`
  lowercase-hyphenated, <= 64 chars, matches the skill's directory; no
  reserved word (`anthropic`, `claude`); `description` single-line, third
  person, no XML tags, carries a "Use when ..." trigger; `SKILL.md` body
  <= 500 lines; any `references/` file stays one level deep from `SKILL.md`
  and carries a table of contents past 100 lines.
- **Probabilistic maturity** -- nine dimensions of judgment that need a model
  or human, not a script. Full rubric with pass/fail evidence:
  [references/rubric.md](references/rubric.md).

## Procedure

1. Read the target `SKILL.md` and every file its body links from
   `references/`.
2. Check the deterministic shape list above. A failure here is a fact, not a
   judgment call -- cite the exact violation (the line, the count).
3. Walk all nine dimensions in `references/rubric.md`, in order -- including
   8 and 9, whose own text states exactly how to handle gitapex's missing
   eval suite and battle harness; do not silently skip either. For each,
   quote the specific text that earns the verdict -- the weak description
   line, the two-deep reference chain, the unjustified constant. A dimension
   with no cited evidence has not actually been reviewed.
4. Issue a verdict: **well-formed** (deterministic shape only) or **mature**
   (clears the probabilistic dimensions too), naming the specific gaps per
   dimension that keep it from the higher bar.

See [references/worked-example-explaining-the-work.md](references/worked-example-explaining-the-work.md)
for a full nine-dimension review applied to a real, already-merged
`SKILL.md`, as a concrete worked example of steps 2-4.

## Scope

This skill carries the rubric; it does not build `scripts/check_skills.py`,
`waza`, or a battle harness for gitapex -- those remain deferred (see the
design spec cited above). Do not expand this skill into a general-purpose
linter or add checks beyond what the rubric in `references/rubric.md`
actually specifies.

## Stop boundaries

- Never approve a skill solely because the deterministic shape checks pass
  -- shape proves well-formed, not mature.
- Never issue a bare "looks fine" / "LGTM" verdict on any dimension without
  citing the specific evidence (a quote, a line, a count) that earns it.
- Never claim a violation the reviewed `SKILL.md` (or its `references/`)
  text does not actually show. If a dimension cannot be assessed (no eval
  suite, no cross-model data), say that explicitly instead of guessing.

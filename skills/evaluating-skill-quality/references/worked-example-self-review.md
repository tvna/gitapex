# Worked example: this skill reviewing itself

A second worked example, run per [rubric.md](rubric.md), against this
skill's own `SKILL.md` and `references/`. Applying `evaluating-skill-quality`
to itself is the standard this skill was built to meet -- it should not
get a pass it would not give another skill. Reference URLs are collected
under [References](#references) at the end of this file.

## Table of contents

- [Portability level](#portability-level)
- [Deterministic shape](#deterministic-shape)
- [Probabilistic dimensions](#probabilistic-dimensions)
- [Verdict](#verdict)
- [References](#references)

## Portability level

Not explicitly declared inline (`SKILL.md` never states "this skill is
Portable"), so this review reads the actual content against the
Portable / Repository-scoped / Mixed definitions in `SKILL.md` itself
(see also [rubric.md's Portability level](rubric.md#portability-level)
for the per-dimension elaboration), the same way it read
`explaining-the-work` in the other worked example.

Read as: **Portable**, after two fixes made during this same review pass
(both real findings, not hypothetical -- see below). Every procedural
step in `SKILL.md`'s "Two lanes" and "Procedure" sections resolves inside
this skill's own folder or cites general, product-level primary sources
(`platform.claude.com`, `code.claude.com`); no step tells the model to
read or branch on a path outside `skills/evaluating-skill-quality/`.
Illustrative mentions of "gitapex" in `rubric.md` (dimensions 8 and the
SkillOpt paragraph) are examples of applying a generic rule to the
reviewer's current context, not paths the procedure depends on -- they
read correctly whether or not the target repository is actually gitapex.

**Finding, fixed during this review**: `SKILL.md`'s `description` --
Level-1 metadata, always resident in the system prompt for every turn,
the single most exposed piece of text in the whole skill -- read "Use
when reviewing any SKILL.md -- gitapex's own or one vendored from an
upstream plugin -- before merging, vendoring, or shipping it." Vendored
into a different repository, "gitapex's own" reads as a reference to a
repository the consuming context is not in, which is confusing at
exactly the layer with zero tolerance for confusion (dimension 1: this
text is what a router matches against). Reworded to "this repository's
own or one vendored from elsewhere," removing the hardcoded name while
keeping the same two cases (locally authored vs. vendored) distinct.

**Finding, fixed during this review**: `rubric.md` dimension 1's `name`
bullet parenthetically called the `skills/<name>/` plugin subdirectory
layout "(gitapex's layout)." The layout itself is a general Claude Code
plugin convention, not gitapex-specific, but the parenthetical named one
repository as if the convention belonged to it -- reworded to "(the
layout used by this skill itself, and by many Claude Code plugins
generally)."

No other portability gaps found on this pass. The other gitapex mentions
in `rubric.md` (dimension 8's eval-mechanism example, the SkillOpt
paragraph's "most of gitapex's skills are judgment/process skills") are
each preceded by a generic instruction ("check the target repository
for...") with gitapex given only as a worked illustration of applying
it -- removing gitapex from those sentences entirely would not change
what the model is instructed to do.

**Fault attribution, per [Contract discipline](rubric.md#contract-discipline)**:
both fixes above are precondition bugs, not dimension-1/6 rubric flaws.
Step 3 (establish portability level) is where "Portable" should have
been asserted correctly from the start; the two leaks slipped through
because that step did not yet exist when the description and the
dimension-1 aside were first written, earlier in this same session. The
fix is exactly what the fault-attribution rule prescribes: redo the
precondition-establishing content (reword the leaking text), not add a
special case inside dimension 1 or 6 to route around it.

## Deterministic shape

| Check | Result | Evidence |
|---|---|---|
| Frontmatter present | Pass | `name:` and `description:` fields present, `---` delimited |
| `name`, present, lowercase-hyphenated, <= 64 chars, no XML tags | Pass | `evaluating-skill-quality` (24 chars); no XML tags |
| No reserved word | Pass | Contains neither `anthropic` nor `claude` |
| `description` non-empty, no XML tags, <= 1024 chars | Pass | 314 chars after the portability fix above, no `<tag>` |
| `description` states both what and when | Pass | "Review a SKILL.md... against a nine-dimension quality rubric..." (what) + "Use when reviewing any SKILL.md..." (when) |
| Body <= 500 lines | Pass | `SKILL.md` is well under the cap |
| `references/` one level deep, TOC past 100 lines | Pass | `rubric.md` and `worked-example-explaining-the-work.md` both link directly from `SKILL.md`; both carry a table of contents and are well past 100 lines |

Verdict on shape alone: **well-formed**.

## Probabilistic dimensions

### 1. Discovery

Pass, with the description fix above now applied. Current sibling skills
in this repository (`driving-pr-to-merge`, `establishing-ubiquitous-language`,
`issue-to-branch`, `merge-retrospective`, `outward-artifact-preflight`,
`stop-and-replan`, `untrusted-input-triage`, `explaining-the-work`) have
triggers that do not overlap this skill's "reviewing any SKILL.md...
before merging, vendoring, or shipping it": each targets a different
artifact type (a PR, a term, an issue, a merged PR's retrospective, any
outward-facing artifact broadly, a self-correcting phrase, externally
authored text, a comment/commit) rather than a `SKILL.md`'s own content
quality.

One genuine watch-point, not a failure: `outward-artifact-preflight`'s
trigger ("about to push, post, or publish any outward-facing artifact --
a commit, PR/issue body, release, or generated file") is broad enough
that a `SKILL.md` about to be committed is technically an "outward-facing
... generated file." The two skills check different things (provenance
markers and ASCII content vs. the nine-dimension quality rubric), so a
router should still distinguish "is this safe to publish" from "is this
well-designed" -- but the overlap in trigger language ("before... shipping
it" vs. "about to push, post, or publish") is close enough to name
explicitly rather than assume away.

### 2. Conciseness

Mixed. `SKILL.md` itself stays tight (every "Two lanes" and "Procedure"
line states an operative fact, no restated definitions). `rubric.md` has
grown substantially over this session (SkillOpt disciplines, three `waza`
divergences with source citations, the Portability level section, a
References section) -- each addition earns its place by citing specific,
checkable evidence rather than restating prior content, but the file is
now long enough (hundreds of lines) that a future editor should watch for
drift: if `waza`'s divergences or SkillOpt's disciplines are cited a
second time elsewhere in a future edit, that would be the "restating the
same instruction in two places" fail this dimension itself names. Not a
current violation -- a forward-looking note on a file that has grown
several times in one review pass.

### 3. Degree of freedom

Pass. The deterministic-shape checklist is low-freedom (exact fields,
exact caps) matching its fragility (a script-checkable fact should not be
phrased as a judgment call). The nine-dimension walk is high-freedom
prose (judgment calls citing evidence), matching that these are
inherently not script-decidable. The Portability level classification
sits at medium freedom: two named categories plus a documented mixed
case, not an open-ended judgment and not a rigid binary flag either --
appropriate for a call that is real but has a small number of legitimate
answers.

### 4. Clarity and structure

Pass. Consistent terminology throughout ("deterministic shape" /
"probabilistic maturity" used identically in `SKILL.md` and `rubric.md`;
"Portable" / "Repository-scoped" / "Mixed" introduced once in
`rubric.md` and reused identically in both worked examples). Concrete
examples over abstract description: this file and
`worked-example-explaining-the-work.md` are exactly the "real
input/output pairs" this dimension asks for, not abstract description of
what a good review looks like. The `SKILL.md` procedure is an ordered,
numbered list. Feedback loop: the Stop boundaries function as the
validate step ("never approve... without citing... never claim a
violation the text does not show") -- but note this is a *reviewer-side*
feedback loop (checking the review's own rigor), not a
skill-content-side one, since this skill does not edit the artifacts it
reviews.

### 5. Progressive disclosure

Pass, strengthened during this review. `references/rubric.md` (the
every-review-needs-it content) and the two worked examples (concrete
illustrations, read on demand rather than inlined) are correctly split,
and the worked examples are optional, consistent with rubric.md's own
"splits must not force several reads for the common case" rule. Both are
linked directly from `SKILL.md` (one level deep) and both carry a table
of contents past 100 lines.

Improvement made this pass, not just a pass/fail read: the Portability
level classification (Procedure step 3, a precondition) originally lived
only in `rubric.md`, meaning even establishing the precondition required
opening the expensive reference file. Moved the actual Portable /
Repository-scoped / Mixed definitions into `SKILL.md` itself, leaving
`rubric.md`'s Portability level section as pure elaboration (why it
matters per dimension). Now steps 1-3 -- the whole precondition, per
Contract discipline -- are checkable from `SKILL.md` alone; only step 4
(the actual nine-dimension walk) requires opening `rubric.md`. This is
the same "cheapest level that still makes it available" test dimension 5
itself states, applied to the precondition/postcondition split from
Contract discipline rather than only to dimension content.

### 6. Durability

Pass. No time-sensitive content (no dated API versions, no "before X
date" language). Forward slashes throughout. `MCP tool` references, if
any, would need `Server:tool` qualification -- none are actually used by
this skill's own procedure, so the rule is vacuously satisfied rather
than tested. The portability audit above (this dimension's newest
addition) is the substantive check here, and it found and fixed two real
issues rather than passing by default.

### 7. Bundled scripts

N/A. This skill ships no code.

### 8. Behavioural evidence

Unmeasured for pass/fail, not skipped: this skill has no `evals/evals.json`
or `evals/` directory of its own, the same gap named for
`explaining-the-work` in the other worked example. No baseline-vs-no-skill
comparison has been run (per Anthropic's evaluation-driven-development
standard, dimension 8's primary bar).

Partial behavioural evidence does exist, generated as a side effect of
this session's own work rather than a formal eval suite: `waza check`
was run against this skill directly (with the operator's go-ahead,
`waza` built from source), and its output was used to catch a real
token-budget regression during authoring (SKILL.md temporarily grew to
1031 tokens from restated content, caught and trimmed to under 900). That
is evidence the skill's *authoring* process included a validation step,
not evidence the skill *helps* a model relative to no skill at all --
the two are different claims, and only the first is actually measured
here.

Held-out-gate discipline (SkillOpt-derived): unmeasured, for the same
reason named in the other worked example -- this skill has been edited
many times in one continuous session, but never through a formal
held-out-scored accept/reject loop against data disjoint from the
editing session itself. The extensive back-and-forth in this session
(finding issues, fixing them, re-checking) resembles the *shape* of
iterative validation but was not scored against a held-out split, so it
does not meet the letter of the discipline this dimension names.

### 9. Cross-model robustness

Unmeasured, not skipped. No Haiku/Sonnet/Opus differential has been run.
Qualitative read: the nine-dimension walk and the Portability level
classification are both prose judgment calls (high freedom by dimension
3's own classification), which is exactly the shape most likely to need
*more* guidance on Haiku and read as appropriately-detailed-not-excessive
on Opus -- but this is a read of the skill's shape, not measured
evidence, and the deterministic-shape checklist's precision (exact
character caps, exact field names) is the kind of low-freedom content
that transfers reliably across tiers regardless.

Transfer testing (SkillOpt-derived): unmeasured. This skill has only ever
run inside this repository under Claude Code. No deployment to a vendored
copy in a different repository, and no run under a different harness
(e.g. a bare API call, Codex), has been observed -- exactly the gap the
Portability level section above is designed to reduce the *risk* of, but
risk reduction is not the same claim as measured transfer success.

## Verdict

**Well-formed**, and not yet **mature** -- the same shape as the
`explaining-the-work` verdict, for different reasons. Dimensions 1
(after the description fix), 3, 4, 5, 6 (after the two portability
fixes) clear cleanly with cited evidence; 7 is not applicable; dimensions
8 and 9 are explicitly named as unmeasured rather than silently assumed,
satisfying rubric.md's Verdicts allowance for 8-9 specifically. Dimension
2 carries a forward-looking watch-point (file growth over one long
session) rather than a current named gap, so it does not by itself block
mature the way an uncleared 1-7 gap would -- but it is close enough to
the line that the next edit to `rubric.md` should re-check it rather than
assume it still holds.

The honest summary: this review found and fixed two real portability
defects in the artifact it was reviewing (itself), which is a materially
different, stronger outcome than a self-review that finds nothing. A
self-review that always passes cleanly would itself be evidence of
rubber-stamping -- per this skill's own Stop boundaries, a bare "looks
fine" is exactly what is disallowed.

## References

(No external URLs specific to this file beyond those already collected in
[rubric.md's References](rubric.md#references).)

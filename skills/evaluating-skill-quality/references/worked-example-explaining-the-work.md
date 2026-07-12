# Worked example: reviewing `skills/explaining-the-work/`

A real nine-dimension review, run per [rubric.md](rubric.md), against
`skills/explaining-the-work/SKILL.md` (merged in
https://github.com/tvna/gitapex/pull/2) as it stands today.
Kept as a concrete example, not restated in `SKILL.md`, per the
progressive-disclosure dimension it demonstrates.

## Table of contents

- [Deterministic shape](#deterministic-shape)
- [Probabilistic dimensions](#probabilistic-dimensions)
- [Verdict](#verdict)

## Deterministic shape

| Check | Result | Evidence |
|---|---|---|
| Frontmatter present | Pass | Frontmatter block at lines 1-4; `name:` at line 2, `description:` at line 3 |
| `name`, present, lowercase-hyphenated, <= 64 chars, no XML tags | Pass | `explaining-the-work` (19 chars); no XML tags. (Not required to match the directory -- see rubric.md dimension 1 -- but it does here, which is a readability nit-pass, not a shape requirement.) |
| No reserved word | Pass | Contains neither `anthropic` nor `claude` |
| `description` non-empty, no XML tags, <= 1024 chars | Pass | Line 3 is one line (203 chars), no `<tag>` |
| `description` states both what and when | Pass | "Routes explanation responsibility..." (what) + "Use when writing or editing code comments, docstrings, or finalizing commit/PR messages." (when) |
| Body <= 500 lines | Pass | 45 lines total |
| `references/` one level deep, TOC past 100 lines | N/A | No `references/` directory exists for this skill |

Verdict on shape alone: **well-formed**.

## Probabilistic dimensions

### 1. Discovery

Pass. The description states both what ("Routes explanation responsibility
... to the right artifact instead of piling it into comments") and when
("writing or editing code comments, docstrings, or finalizing commit/PR
messages"), with specific terms (comments, docstrings, commit/PR messages)
rather than filler like "helps with documentation". One structural note,
not a failure: the trigger clause precedes the capability clause, the
reverse of the rubric's own pass example ("Extract text ... Use when
..."). Order is not itself a deterministic-gate requirement and both
clauses are present, so this stays a note, not a finding.

Sibling-distinctiveness check (rubric.md's current framing for this
dimension): as of this review, `explaining-the-work`'s siblings in this
repo include `stop-and-replan` (trigger: a self-correcting phrase already
present in a PR body or commit message) and `untrusted-input-triage`
(trigger: about to act on externally authored text). Neither trigger
overlaps "writing or editing code comments, docstrings, or finalizing
commit/PR messages" -- the three descriptions pick disjoint terms, so a
router would not confuse them. Pass on distinctiveness too.

### 2. Conciseness

Pass. Every bullet under `## Routing` (lines 14-29) is a single routing
rule with no restated definitions of "comment", "commit", or "docstring" --
the skill assumes the model already knows what those are and states only
the project-specific delta (which artifact owns which kind of explanation).
No filler: the shortest section (`## Precedence`, lines 33-35, a single
prose paragraph rather than a bullet) still carries only project-specific
instruction, not a restatement of what precedence means.

### 3. Degree of freedom

Pass. This is a fixed convention meant to hold consistently across a
codebase, and the skill is written at correspondingly low freedom: an exact
template is given for the one output with a strict format --

```
# why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]
```

(line 24) -- rather than a looser "explain your reasoning in a comment".
The freedom level matches the fragility of the thing being standardized.

### 4. Clarity and structure

Mostly pass, one named gap. Terminology is consistent: "How / What / Why /
Why-not" is introduced in the description at line 3 ("Routes explanation
responsibility (How/What/Why/Why-not) to the right artifact") and reused
verbatim at lines 14, 16, 18, 21 -- no drift into synonyms like "reasoning"
or "rationale" for "Why".
The why-not template (line 24) is a concrete, real example, not an abstract
description. Structure is ordered under three headings (`## Routing`,
`## Precedence`, `## Stop boundaries`).

Gap: dimension 4 calls for a feedback loop (validate -> fix -> repeat) on
quality-critical steps. The why-not rule states a precondition ("Requires a
citable issue/PR/ADR that actually evaluated the rejected alternative. If
nothing can be cited, do not write the comment", lines 27-29) but never
tells the model how to *check* that a citation is valid before writing the
comment -- there is a prohibition, not a validation step. The prohibition
functionally suppresses the bad case, so this is a minor gap rather than a
serious one -- but it is a real, citable gap against the dimension's stated
standard, not a bare "looks fine", and per rubric.md's Verdicts section a
named gap in dimension 4 keeps that dimension from clearing cleanly.

### 5. Progressive disclosure

Pass. The skill has no `references/` directory, and correctly so: at 45
lines the entire policy fits inside the informal budget without forcing a
second read for the common case (routing one piece of explanation to one
artifact). Nothing here is detail-needed-only-sometimes that should have
been split out.

### 6. Durability

Pass. No time-sensitive content (no dated API or version reference). No
external tool or package dependency, so the "state the install step" rule
does not apply. No MCP tool is referenced. The one path in the skill,
`docs/adr/NNNN-*.md` (line 24), uses forward slashes.

### 7. Bundled scripts

N/A. The skill ships no code.

### 8. Behavioural evidence

Unmeasured, not skipped: gitapex has neither an `evals/evals.json` (the
Claude Code `skill-creator` format) nor a third-party runner today
(confirmed absent from the repository tree; `skill-creator` and `waza` are
both absent from this environment too). There is no suite exercising this
skill's trigger against a documented no-skill baseline, so this dimension
cannot be scored pass or fail -- it is an open gap in the repository's
tooling, not a defect specific to this skill. Per rubric.md dimension 8,
this review does not install eval tooling to close that gap; that is a
separate, operator-approved decision.

### 9. Cross-model robustness

Unmeasured, not skipped, for the same reason as dimension 8: gitapex runs
no cross-model differential (no `skill-creator` version comparison, no
third-party benchmarking pass) across the Haiku/Sonnet/Opus spread
Anthropic's docs name for this dimension. Qualitative read only: the
skill's rules are a fixed low-freedom policy (exact templates, fixed
routing table) rather than an open-ended judgment task, so the general
over-prescription-risk reasoning (a low-freedom skill tuned for a weaker
model can over-constrain a stronger one) plausibly applies less here than
to a high-freedom skill -- but this is a read of the skill's shape, not
measured evidence against any specific tier, and should not be reported as
if it were.

## Verdict

**Well-formed**, and not yet **mature**. Dimensions 1, 2, 3, 5, 6 clear
cleanly with cited evidence; 7 is not applicable; dimensions 8 and 9 are
explicitly named as unmeasured rather than silently assumed, which is what
rubric.md's Verdicts section requires of 8-9 specifically -- that allowance
is satisfied, not a blocker. The single thing keeping this skill below
mature is dimension 4's one named gap (no explicit validate step for the
why-not citation requirement): real and minor, but per rubric.md's Verdicts
section a named gap in a dimension 1-7 keeps that dimension from clearing,
unlike the special allowance dimensions 8-9 get. Closing that one gap --
and nothing about 8-9, which gitapex's tooling genuinely cannot measure
yet -- would clear the mature bar.

# Formative quality dimensions

Loaded on demand, typically as a post-draft sweep once Step 4 has
produced a first draft (see "How to use this table" below) -- not
required reading before Step 4 begins; `SKILL.md`'s own body already
covers the load-bearing judgment calls for the ordinary path. Nine
formative concerns, one per row, each a writing-time precursor to one
of `evaluating-skill-quality`'s own nine review dimensions
(`references/rubric.md`). The two lists share numbering and a name on
purpose -- they are the same nine concerns, viewed from opposite sides of
the DDD boundary this skill's own `SKILL.md` describes: this table asks
"how do I write this well," the rubric asks "is what got written good
enough to ship." Neither owns the other's verdict; a row here is a
drafting habit, not a passing grade.

| # | Formative dimension | Writing-time instruction | Example pair | Gate-side cross-reference |
|---|---|---|---|---|
| 1 | Name and description legibility | Write the `description:` frontmatter so a reader picks this skill out of a list of thirty without opening it -- state the trigger (when to use it) and the boundary (what it's not), not just the topic. | Good: "Use when authoring a brand-new skill from a blank page... Distinct from scorer-gated-skill-edits (iterates an existing SKILL.md)." Bad: "Helps with skills." | Dimension 1, Discovery -- name and description |
| 2 | Economy of words | Cut a sentence that restates what the next sentence already implies. If a paragraph survives having its middle sentence deleted with no loss of meaning, delete it now rather than leaving it for review to flag. | Good: "Elicit the metadata choices; never infer them." Bad: "It's important to make sure that the metadata choices are properly elicited from the user, since inferring them can sometimes lead to mistakes." | Dimension 2, Conciseness |
| 3 | Explicit freedom vs. constraint | State plainly, per Step, whether it's a hard rule ("never," "always") or a judgment call ("assess," "consider") -- a reader should never have to guess which. | Good: "Never skip Step 2's gate under time pressure" (hard) vs. "Judge whether the interpretation needs a human decision" (judgment). Bad: a Step phrased as advice ("you might want to check...") for something that is actually mandatory. | Dimension 3, Degree of freedom |
| 4 | Structural legibility | One Step, one action (see `guidance-form-and-sdo.md`'s SDO test). Number Steps so a later Step can reference an earlier one by number without the numbering having drifted, and state what a Step iterating a finite set actually finishes on -- both a positive finding and an explicit "none found" are observable results; silence is neither. | Good: "route back to Step 1" (a number in *this* draft's own Steps, kept true by the draft's own renumbering discipline). Bad: a cross-reference that drifts silently after a Step gets renumbered, or a Step whose "nothing found" case has no stated output at all. | Dimension 4, Clarity and structure |
| 5 | Load-bearing vs. on-demand split | Put content every invocation needs in `SKILL.md`'s own body; put content only some invocations need in a `references/` file, loaded conditionally. Four of this skill's own six reference files stay genuinely on-demand once `SKILL.md`'s own body carries every Step's load-bearing judgment call directly, which is itself an instance of this dimension, not just a description of it. `gitapex-cross-links.md` and this file are the two exceptions -- the former carries Step 8's own exact checker flags, found nowhere else, and Step 8 mandates sweeping against this one too, so both *are* required reading on the in-repo ordinary path (`SKILL.md`'s own Notes states this identically). | Good: this skill's own `SKILL.md` staying self-sufficient for the ordinary path, pointing to a reference only when a specific question needs more depth than the body already gives. Bad: inlining a full worked example into every Step's body so the base cost is paid on every invocation regardless of need. | Dimension 5, Progressive disclosure |
| 6 | Stability of claims | Avoid a claim likely to go stale without a mechanism keeping it honest -- a specific line count, a "the only skill that..." superlative, a bare issue number. Where a claim must be precise and could drift, either cite a deterministic gate that locks it or mark it as a point-in-time fact. | Good: "cite dimension 15 by number" backed by a drift gate. Bad: "references/rubric.md (2227 lines)" stated as fact with nothing keeping the number honest -- exactly the kind of claim this repository's own vocabulary-lock gate family exists to catch once it's this skill's own content going stale. | Dimension 6, Durability |
| 7 | Script necessity and minimalism | Only bundle a script when a check genuinely needs to be deterministic rather than judged -- and when one is bundled, give it a docstring stating what it checks and why prose alone wasn't enough. Applies only if the drafted skill ships code at all. | Good: a shape-checker with a documented exit-code contract. Bad: a script that reimplements a judgment call review would make anyway, just in Python. | Dimension 7, Bundled scripts |
| 8 | Concrete example coverage | Include at least one worked example showing the procedure run end-to-end on a plausible input -- not a schema in the abstract. | Good: `executing-a-branch-plan`'s own "Worked example" section, walking a 3-row ACM through wave assignment. Bad: a Steps list with no example, leaving a reader to construct their own first real test case. | Dimension 8, Behavioural evidence |
| 9 | Model-agnostic phrasing | Don't write a Step that only works if the executing model happens to interpret an ambiguous instruction the way the author had in mind. Where a Step depends on a specific model/effort tier's own judgment strength, pin it explicitly (see `executing-a-branch-plan`'s own Notes section for a real pinned-step precedent) rather than leaving the dependency implicit. | Good: naming which Steps carry a model/effort pin and why. Bad: a Step that works during authoring (tested against one strong model) but silently degrades under a weaker one, with nothing in the text warning a reader this could happen. | Dimension 9, Cross-model robustness |

## How to use this table while drafting

Load it once a first draft exists (per this file's own opening note --
not before Step 4 begins), then treat it as a checklist pass over that
draft, not a constraint to satisfy sentence by sentence while writing.
Trying to hit all nine rows on the first pass produces prose optimized
for the checklist rather than for the reader; draft first, using
`SKILL.md`'s own inlined guidance, then sweep against this table once
there's a real draft to sweep.

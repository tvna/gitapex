# Tacit-knowledge elicitation for Step 3

Loaded on demand: `SKILL.md`'s own Step 3 already inlines all four axes'
own option lists directly in the body -- load this file for the deeper
"why elicit, not infer" rationale and phrasing guidance beyond those
options, when the body's own definitions aren't enough to actually word
the question round. Format only -- the literal question wording is
deliberately not finalized here (see this skill's own `SKILL.md`
Non-goals); what's fixed is the shape the elicitation takes and why it
takes that shape, so a drafting agent composes the actual questions from
the requester's own real context rather than reading a canned script.

## Why elicit rather than infer

`evaluating-skill-quality`'s own review history records a skill once
declared `capabilityAssumption: Frontier` by reviewer assumption, with no
`model:`/`effort:` pin anywhere in the file to justify targeting only a
strong-reasoning tier -- an inferred metadata choice that turned out
wrong and was corrected, not merely relabeled, once caught. Step 3 exists
so a drafted skill's metadata choices are never that kind of guess: each
of the four choices below is the requester's own decision, elicited
directly, every time -- not defaulted, not pattern-matched from a similar
skill, not left for review to catch later.

## The four axes, one round

Step 3's elicitation is exactly one round of up to four questions. This
matches `AskUserQuestion`'s own documented per-call limit (its tool
schema declares the `questions` array `maxItems: 4`) deliberately, not
coincidentally: the four metadata axes this skill's own `SKILL.md` Step 3
names were chosen to map one-to-one onto that limit. Where a harness
offers no `AskUserQuestion`-equivalent tool at all, fall back to portable
question handoff -- print `AskUserQuestion:` followed by the same four
axes and choices as plain text, the same convention
`drafting-issues` and `planning-a-branch-from-an-issue` already use
for the identical dependency.

1. **Portability** -- `Portable` | `Repository-scoped` | `Mixed` (see
   `skills/evaluating-skill-quality/references/skill-metadata.schema.json`
   for the authoritative enum and
   `docs/superpowers/specs/2026-07-21-portability-authorship-decision-
   table-design.md` for when each applies). Phrase the question around
   the concrete question that decides it: does this draft depend on any
   convention, tool, or file path specific to the repository it's being
   authored in, or would it work unmodified if vendored elsewhere?
   `Repository-scoped` is for a downstream fork hardcoding its own
   conventions -- an origin-authored skill answering "no repo-specific
   dependency" is `Portable`; one with a partial dependency (some Steps
   portable, one Step naming a repo-specific script) is `Mixed`.
2. **Capability assumption** -- `Broad` | `Frontier` | `Adaptive`. Phrase
   around: does every Step need a strong-reasoning model, or only
   specific Steps that could carry an explicit pin while the rest run at
   whatever tier is already in use? `Adaptive` is the answer when the
   draft's own body stays lean and only a named subset of Steps would
   carry a pin -- not a default to reach for without checking whether any
   Step actually needs one.
3. **Invocation mode** -- derived from the `disable-model-invocation` and
   `user-invocable` frontmatter booleans. Phrase around: should the model
   reach for this skill on its own when a task matches its description,
   should a human be able to invoke it directly as a slash command, or
   both? Most drafts want both (the default); a skill whose Steps are
   safe only under direct human initiation (an irreversible-operation
   skill, for instance) should disable model-invocation explicitly rather
   than relying on Stop-boundary prose alone to prevent an unwanted
   autonomous trigger.
4. **Lifecycle** -- `experimental` | `stable` | `deprecated` (see
   `skills/evaluating-skill-quality/references/skill-metadata.schema.json`'s
   `lifecycle` shape). A first draft is almost always `experimental`,
   naming a `trackingIssue` as the full canonical issue URL (never a bare
   number) and a `reason` stating what graduating to `stable` would
   require -- typically "cleared evaluating-skill-quality and
   battle-testing-a-skill review."

Ask all four in one `AskUserQuestion` call when the requester is present
to answer synchronously; when eliciting from a written request instead
(an issue body, a design doc), extract explicit statements for as many of
the four as the source actually states, and question only the remainder
-- never treat silence on an axis as an implicit answer.

## Follow-up round: only on contradiction

A second round is not the default -- most drafts settle all four axes in
one pass. Trigger a follow-up only when a later Step's own content
contradicts an earlier answer, and resolve it by asking again rather than
silently overriding either side. The concrete shape this takes: this
skill's own first draft initially answered `skillDependencies.requires: []`
at Step 3 (nothing this skill's procedure cannot function without) --
then Step 8's own content turned out to mandatorily invoke
`evaluating-skill-quality`'s bundled checker scripts, and Step 2's gate
content turned out to be adapted directly from that same skill's rubric.
That is a real contradiction between an elicited answer and what got
drafted, caught by this skill's own fresh-context consistency audit
rather than by a follow-up question asked in the moment -- which is the
gap a live follow-up round exists to close earlier, before a draft ever
reaches that audit. When drafting surfaces a dependency, a portability
constraint, or a capability need the original elicitation round didn't
anticipate, ask again about the specific axis that contradiction touches,
rather than carrying the stale answer forward or quietly correcting it
without surfacing the change.

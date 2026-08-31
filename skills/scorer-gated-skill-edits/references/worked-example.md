# Worked example: one iteration under a substring scorer

A single iteration of a fictional skill, `summarize-release-notes`, scored
by the same `output_contains` / `output_not_contains` substring contract
that this repository's own eval suite for `planning-a-branch-from-an-issue`
already ships. The
skill is fictional so this example cannot go stale against any real
skill's current text.

## Contents

- [The scorer](#the-scorer)
- [The splits](#the-splits)
- [Starting score](#starting-score)
- [Iteration 1](#iteration-1)
- [After the iteration](#after-the-iteration)
- [Obtaining the "before" state under a live gate](#obtaining-the-before-state-under-a-live-gate)
- [Cross-reference sweep before scoring](#cross-reference-sweep-before-scoring)
- [Restraint-check corroboration must be a real dispatch](#restraint-check-corroboration-must-be-a-real-dispatch)
- [What this example demonstrates](#what-this-example-demonstrates)

## The scorer

Each task fixture asserts substrings that must (or must not) appear in the
skill's output, exactly like this repository's own task fixtures for
`planning-a-branch-from-an-issue`. The score for a run is the fraction
of a task's assertions that hold; the score for a split is the mean over
its tasks. This is the repeatable
`r(s) in [0,1]` the precondition gate requires.

## The splits

Five fixtures, split roughly 2:1:7-style but tiny, so the ratio is
aspirational (the honest note the skill makes: with this few fixtures the
minimal groundwork is a larger corpus, not a smaller gate). For this
example:

- **train** (motivates edits): `normal-notes`, `notes-with-breaking-change`.
- **selection** (gates acceptance): `sel-a` (asserts `## Summary` and
  `## Breaking changes`), `sel-b` (asserts `## Summary` and
  `output_not_contains: TODO`). Four assertions total.
- **test** (report only, untouched until the end).

## Starting score

The current skill always emits `## Summary` and never leaks `TODO`, but on
`sel-a` it omits the `## Breaking changes` heading even though that
fixture's input lists a breaking change. So `sel-a` passes 1 of its 2
assertions (**0.5**) and `sel-b` passes both (**1.0**). The selection
score is the mean over its tasks: `(0.5 + 1.0) / 2 = ` **0.75**. The
failing assertion is `sel-a: output_contains "## Breaking changes"`.

## Iteration 1

Train evidence (from `notes-with-breaking-change`, a train fixture, not a
selection one) shows the skill drops breaking-change items into the general
summary instead of a dedicated heading. Two candidate edits are proposed
under an edit budget of 1 kept edit.

### Edit A (kept)

A localized add to the procedure: "If the input lists any breaking change,
always emit a `## Breaking changes` section listing them." Re-score on the
selection split: `sel-a` now passes both assertions, `sel-b` unchanged.

- Selection score: **0.75 -> 1.0**. Strict improvement, so **accepted**;
  it exceeds the best-so-far, so it becomes the current best skill.

### Edit B (rejected as a tie)

A reword of the intro line from "Summarize the release." to "Produce a
concise release summary." for style. Re-score on the selection split: no
assertion depends on that line, so the score is unchanged.

- Selection score: **1.0 -> 1.0**. Not a strict improvement (a tie), so
  **rejected**. A plausible-sounding edit that does not move the score is
  not kept.

### Edit C (kept only as predeclared pruning)

Before scoring, classify a deletion-only candidate as pruning-only and
declare UTF-8 byte length as the context-cost proxy. Its selection
correctness remains **1.0 -> 1.0**, while measured cost falls **920 -> 810**.
The correctness-first pruning gate therefore **keeps** it. The identical
correctness tie without that predeclaration and strict cost reduction would
be an ordinary tie and reject, just like Edit B.

### Rejected-edit log

```
Iteration 1
- Edit B: reword intro line ("Summarize the release." ->
  "Produce a concise release summary.")
  selection 1.0 -> 1.0, delta 0.0; rejected (tie); do not retry this edit.
```

Later iterations read this log and do not re-propose Edit B.

## After the iteration

- **Transfer check:** run the accepted skill unchanged on a nearby target
  (an adjacent model or the same skill on a slightly different notes
  format) and confirm the selection score does not regress below the
  no-skill baseline before shipping.
- **Test split:** read once, only for the final report, never to motivate
  an edit.
- **Next move:** if the selection score can still rise, run another
  iteration on fresh train evidence; otherwise ship the current best skill.

## Obtaining the "before" state under a live gate

Score the *before* skill from `git show <ref>:<path>`, never a working-tree
stash. One incident lost a whole before-score dispatch: the files were
`git stash`ed to pre-edit state, a Stop hook forced a commit, and the
`git stash pop` restoring a coherent tree landed *while the dispatch was
still in flight* -- its `Read` calls silently saw the post-edit files. It
was caught only by a lucky tell (the report cited rubric content that did
not exist yet) and had to be redone. `git show` is fixed at the named
revision, so a concurrent working-tree change cannot move it.

## Cross-reference sweep before scoring

A real incident: a bounded edit inserted a new fourth Agentic operation mechanism-fit
check into a skill's `references/rubric.md`. A sibling reference file,
`worked-example-self-review.md`, cited "the fourth Agentic operation mechanism-fit
check" by ordinal -- true before the edit, stale after it (the newly
inserted check now held that position, pushing the cited one to
fifth). A third sibling doc's corpus-size math note also assumed the
pre-edit fixture count. Both went uncaught until a later,
self-initiated review pass found them -- after the edit had already
been scored and kept. Grepping the target skill's own `references/`
directory and `evals/<skill>/` docs for ordinal or count language
naming the changed item, before scoring, would have caught both in the
same patch that introduced them.

## Restraint-check corroboration must be a real dispatch

A real incident: a Kept-edit log entry recorded a "restraint check" for a
new cohesion-detection edit -- confirming the edit does not over-fire
on a case designed to look like a false positive. The entry cited two
dispatches, but neither was the purpose-built restraint fixture the
entry named; both were unrelated after-dispatches whose scores were
read as if they corroborated the named fixture. The substitution went
unnoticed until a later review pass actually dispatched the named
fixture and found the entry's claim had never been checked. A log
entry naming a specific fixture is a claim about that fixture, not
about the edit's dispatches in general -- it is either backed by
dispatching that fixture, or disclosed as not dispatched.

## What this example demonstrates

- Edits are motivated by the **train** split; the **selection** split only
  gates; the **test** split is untouched.
- Acceptance is **strict**: 0.75 -> 1.0 is kept, 1.0 -> 1.0 is rejected.
- A rejected edit still produces value as a **logged** negative signal, and
  the "before" state comes from `git show`, never a working-tree stash.
- A bounded edit that changes an ordinal or count another doc cites is
  not complete until that citation is swept and fixed in the same
  patch.
- A named-fixture corroboration claim in a log entry must be backed by
  dispatching that exact fixture, or disclosed as not dispatched --
  never substituted with an unrelated dispatch's evidence.

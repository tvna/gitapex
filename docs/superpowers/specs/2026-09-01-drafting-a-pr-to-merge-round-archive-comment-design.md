# drafting-a-pr-to-merge: archive prior Step 8 round to a PR comment before overwrite

Date: 2026-09-01
Refs #1649

## Context

`skills/drafting-a-pr-to-merge/SKILL.md` Step 8 (the two-layer
independent-review gate) records its verdict in the PR body under a
`## Independent review verdict` heading. The step's own record rule is
explicit: "Re-record this section (never leave a prior commit's SHA
standing) every time step 8 re-runs" -- i.e. each re-run is supposed to
overwrite the section, not accumulate it.

In practice, [PR #1632](https://github.com/tvna/gitapex/pull/1632) shows
what actually happens when Step 8 loops back to Step 3 (a `confirmed
finding`) many times in one PR: the section is manually appended to with
"Round 1", "Round 2", "Rounds 3-6" sub-headings rather than overwritten,
because each round's findings/fixes/deferrals are worth keeping as a
record. The section has grown into thousands of words of accumulated
round history sitting in the PR body, which the body is not the right
place to hold indefinitely -- it is read on every PR view, by every
reviewer and every tool that fetches the PR, while the round-by-round
detail is only useful as an audit trail, not as the PR's current state.

The repository owner asked for a way to keep that per-round record
without accumulating it in the body: archive the outgoing round's
verdict to a PR comment immediately before the body is overwritten for
the next round.

## Decision

Add one new sub-step to Step 8's existing record procedure, and one new
Stop-boundary bullet. No other step, and no other skill, changes.

**Scope**: only the Step 8 loop (a `confirmed finding` from either
review layer sends the flow back to Step 3, after which Steps 4-7
re-confirm `mergeable_state: "clean"` before Step 8 re-runs and records
again). This is deliberately narrower than every path that returns to
Step 3 -- Step 7's `"unstable"/"blocked"` (CI failure), `"dirty"`
(merge conflict), and `"draft"`-branch failure (`mergeable: false`, a
failing check, or an unresolved thread once the PR is already draft)
all also loop back to Step 3, but are out of scope here: `"dirty"`
already has its own unconditional "always post a PR comment documenting
the resolution" rule (a different rule, addressing a different concern
-- documenting *how* a conflict was resolved, not archiving a superseded
review verdict); `"unstable"/"blocked"` and the `"draft"`-branch case are
CI/state-driven returns to Step 3, not review-verdict rounds -- Step 8
never even ran to produce a verdict section on that pass, so there is
nothing of this rule's own kind to archive. Folding any of these into
this same archival rule would conflate unrelated causes of "back to
Step 3" under one archive rule. This narrower scope was chosen over the
broader one during design dialogue.

**Mechanism**: immediately before Step 8's existing record sub-step
overwrites the `## Independent review verdict` section (per the
stale-verdict rule already in force), check whether that section
currently exists in the PR body, matched on the exact heading string
(never a fuzzy or partial match):

- **Section absent** (this is Step 8's first run on this PR): nothing to
  archive. Proceed straight to recording the new verdict, unchanged from
  today.
- **Section present but malformed** (missing its own `Verified commit:`
  line, or otherwise not in the shape Step 8's own record sub-step
  itself produces -- e.g. a section a human hand-authored, or two
  overlapping sections from an earlier malfunction): the Mechanism above
  implicitly assumed, in an earlier draft of this design, that any
  existing section is always well-formed; an adversarial review of the
  implementation found that assumption unstated and untested. Corrected
  here: never guess a SHA or silently skip the archive in this case --
  escalate per Step 11 instead, the same fail-closed default Step 7's
  own `"unknown"`/`"unstable"` handling already uses for an unresolvable
  state.
- **Section present and well-formed** (Step 8 is re-running after a loop
  back to Step 3): first check the PR's existing comments for an archive
  comment already citing that same outgoing `Verified commit:` SHA --
  the same resume-safety check Step 7's own `"dirty"` branch already
  applies to its conflict-resolution comment, so a session reset between
  posting the archive and overwriting the body never produces a
  duplicate archive. This resume-safety check was likewise added during
  implementation, after an independent review of the drafted skill found
  the original two-branch Mechanism (as first written above) had no
  guard against exactly that non-idempotent-retry failure mode. Only
  when no such comment already exists, post the section's entire current
  content, verbatim -- no summarization, no re-authoring -- as a new PR
  comment via `github:add_issue_comment`, under a heading that marks it
  as an archived, superseded round (e.g. `## Independent review verdict
  (archived -- round ending at commit <old head SHA>)`), before
  proceeding to overwrite the body section with the new round's verdict.

See Non-goals below for what this decision deliberately leaves unchanged
(the verbatim-transcription choice, the absence of a body-to-comment
cross-reference, and Step 7's own untouched `"dirty"` comment rule) --
stated once there rather than restated here.

## Skill content changes

- Step 8's record paragraph (`skills/drafting-a-pr-to-merge/SKILL.md`,
  the `Record the validated, preflighted verdict...` paragraph) gains a
  new leading paragraph implementing the three-branch Mechanism above:
  check for an existing `## Independent review verdict` section (exact
  heading match) and, if present and well-formed, archive it verbatim to
  a PR comment (after a resume-safety `get_comments` dedup check) before
  overwriting; if present but malformed, escalate per Step 11 instead of
  guessing; if absent, proceed unchanged. Skipped entirely on Step 8's
  first run (no section yet exists).
- New Stop-boundary bullet: never overwrite an existing `##
  Independent review verdict` section without first archiving it to a
  PR comment -- except on Step 8's first run, when there is nothing yet
  to archive.
- No change to the Process Flow diagram: the Step 8 -> Step 3 -> Step 8
  loop shape is unchanged; only the internal content of Step 8's own
  record action changes.
- No change to Step 7's `"dirty"`, `"unstable"/"blocked"`, or
  `"draft"`-branch text or their existing rules.

## Non-goals

- Does not archive any Step 7 return-to-Step-3 round (CI failure,
  `"dirty"`, or a `"draft"` branch failure) -- only Step 8's own
  review-verdict record. Step 7's `"dirty"` case keeps its own separate,
  pre-existing comment rule unchanged.
- Does not generate a summary of the archived round; the archive is a
  verbatim transcription of what was already recorded and preflighted.
- Does not add a cross-reference from the new body section back to the
  archived comment.
- Does not change how the verdict content itself is composed, validated,
  or preflighted (`outward-artifact-preflight`, `untrusted-input-triage`)
  -- those disciplines already apply to the content before it first
  lands in the body, so the archived comment carries the same
  already-preflighted text unchanged.

## Open questions (deferred to implementation)

- Exact failure-handling for the `github:add_issue_comment` call itself
  (retry policy, or an escalation path if it cannot post) is not
  specified here; the implementing task should follow this skill's
  existing conventions for a failed tool call elsewhere in the same
  step, rather than inventing a new failure mode.

## Verification

- `python3 skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  and `gitapex_scan_execution_requirements_drift.py` run clean against
  the edited `SKILL.md`.
- `gitapex_gate_skill_branch_fixture_coverage.py`'s delta-scoped check:
  the new Stop-boundary bullet needs a matching new
  `evals/drafting-a-pr-to-merge/tasks/*.yaml` fixture exercising the
  archive-before-overwrite behavior (both the "section present" and
  "section absent, first run" branches).
- A fixture exercising Step 8's second loop (confirmed finding -> fix ->
  re-clean -> Step 8 re-run) should assert the archive comment is posted
  with the prior round's exact content before the new verdict replaces
  the body section.
- Two further fixtures, added after an adversarial review of the
  implementation found the branches above insufficient: one exercising
  the malformed-section-escalate branch (a `## Independent review
  verdict` heading present with no `Verified commit:` line), and one
  exercising the resume-safety dedup branch (an archive comment already
  citing the outgoing round's SHA must not be re-posted).

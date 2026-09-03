# Decision-log discipline for `metadata/gitapex.yaml`'s own `references` field

Loaded on demand: `SKILL.md`'s own Step 2 already states the common-path rule directly in the body (append in the same edit round as the decision, read the sidecar before every edit, never trust it over ground truth) -- load this file for the resume-time and concurrent-dispatch detail that rule doesn't spell out.

## What `outcome.baseCommit` cites

`outcome.baseCommit` names the commit causally relevant to the specific decision an entry records -- not, by default, the entry-adding commit's own git parent. Three variants recur in this skill's own decision log (issue https://github.com/tvna/gitapex/issues/1740's own 28-entry investigation), and an entry's own summary text decides which applies:

- **The entry-adding commit is itself the substantive fix.** Cite that commit's own true immediate git parent -- the state right before the fix landed. If that commit is itself a merge, its first-parent branch is the true immediate parent for this purpose. (Most single-decision, single-round entries take this shape.)
- **The entry-adding commit only records a decision substantively made by an earlier commit** (a later round batches several already-made fixes into one logged entry). Cite that earlier substantive commit directly, not the batching commit's own parent.
- **The entry is a caveat or correction reacting to a specific earlier entry** ("the entry above ..."). Cite the commit that added the entry being corrected, so a reader can jump straight to what is being revised.

This is a human judgment call, not a mechanically-derivable one -- a mechanical sweep comparing every citation against "the entry-adding commit's own true immediate parent" alone will flag real, correct citations of the second and third kind as false positives (the sweep in issue https://github.com/tvna/gitapex/issues/1740 found 13 such cases in this file, all judged correct on inspection once checked against these three variants). Treat a mismatch against that narrow rule as a prompt to check the entry's own content against the three variants above, not as proof of a broken citation on its own. This convention stays advisory, not gate-enforced: the causal judgment it calls for cannot be checked mechanically without either false positives (as above) or false negatives (accepting any resolvable ancestor).

Whichever variant applies, the cited commit must still resolve as a real, reachable commit -- an unresolvable `baseCommit` is a decision-log defect regardless of which variant its entry intends, per "Ground truth outranks the log" below.

## Ground truth outranks the log, in both directions

The log ranks below ground truth: the draft's own current files and git history win on any disagreement; its own store still wins over bare git/PR history for provenance, since the log travels with the skill directory when vendored and git history alone does not.

Before trusting a log entry to route away (Precondition) or resume from an existing target's sidecar -- context 1 dispatched against an existing `SKILL.md` (Precondition item 1), or context 2 -- check it against ground truth first: a `baseCommit` that doesn't resolve, or a claimed fix whose content is verifiably absent from the current body, is itself a new decision-log entry disclosing the gap, never silently trusted as if the claim still held.

The reverse direction needs the same resume-time check, not only a same-round courtesy: when either context resumes from an existing target's sidecar this way, scan ground truth for completed work the log doesn't disclose, not only validate what the log already claims -- `git log` on this draft's own `SKILL.md`/`references/`/`metadata/gitapex.yaml` since the log's last entry's `outcome.baseCommit` showing commits with no matching new entry is undisclosed drift, catchable only here, at resume time, since a writer that crashed mid-round before logging never reaches a same-round check of its own. Treat a gap found this way exactly like a `baseCommit` that doesn't resolve: a new decision-log entry disclosing it, appended before proceeding.

A same-round writer that completes normally still appends its own entry in the same round, immediately, per `SKILL.md`'s own Step 2 rule -- that discipline stays, it is just not sufficient on its own, and this same resume-time check binds the next edit too. A missing, truncated, or unparseable sidecar is never read as "nothing was decided yet" -- escalate rather than proceed on an unreadable record.

## Concurrent-dispatch race, disclosed as open

Two concurrent dispatches editing the same *existing* target's sidecar race the identical way two `scorer-gated-skill-edits` iterations against one target once did: this skill supplies no isolation of its own, and the two real dispatch contexts only partly do.

- Context 2 always runs after `scorer-gated-skill-edits`'s own Precondition-gate worktree isolation self-establishes, closing the race there.
- Context 1 does not close it uniformly: `executing-a-branch-plan` Step 6 dispatches a wave either via the Workflow tool (`isolation: 'worktree'`, closing the race the same way) or its own sequential fallback -- the same fallback mode Step 2's own mkdir bullet names -- which carries no such guarantee.

A same-tree overwrite between two isolated worktrees still surfaces as an ordinary git conflict at landing, never a silent loss; the sequential-fallback mode carries no such backstop, so that race is real and currently open, not merely a future caller's hypothetical -- disclosed here as open, never framed as closed by caller-side isolation it does not uniformly have. This skill's own Precondition does not itself check for either case.

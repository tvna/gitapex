# evaluating-context-channel-maturity eval status

This skill replaces `evaluating-decision-state-discipline` (issue #580),
following a design review that found extending that skill's own five
gate-shaped criteria to CLAUDE.md/Subagents/Output styles/system-prompt-
append/Auto-memory would be a category error -- none of those five
mechanisms are gate material. This file's directory was renamed along
with the skill; the section below preserves the retired skill's own audit
history rather than discarding it, since that history documents real,
independently-verified findings against the predecessor skill's own prior
form, not against this skill's current one.

`evals/evaluating-context-channel-maturity/tasks/` carries 13 fixtures,
one per this skill's own Stop-boundary bullet -- required by
`.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`, a deterministic
CI gate added the same day as this skill's initial authoring that did not
exist when the retired predecessor first shipped. Each fixture passed
`evals/scripts/gitapex_lint_fixture_assertions.py` (0 warnings, scoped to this
skill's own tasks and `references/criteria.md`) and the branch/fixture
count itself was independently verified against
`gitapex_gate_skill_branch_fixture_coverage.py` directly, not assumed from the
fixture count alone. No no-skill baseline and no model tier evaluated yet
-- an ablation-capable, not-yet-run gap, not an absent-mechanism one,
matching the same disclosed pattern the retired skill's own history below
already used.

Refs #580.

## Current round

Both required dispatches ran, each disclosing it was not genuinely
isolated (the calling repository's own `CLAUDE.md` was present in
context from the start in both cases) -- every favorable finding below is
therefore provisional pending a genuinely isolated re-run, per this
repository's own established disclosure convention; the FAIL/gap findings
below stand regardless, since each rests on an independently cited check
(a file read, a `git log`, a live GitHub API read, a direct source
fetch), not on the dispatch's own unverified judgment.

`battle-testing-a-skill` returned **FAIL**, 4 findings: (1) the CLAUDE.md
worked example's own Criterion-4 quote was fabricated -- it conflated the
Claude Code harness's own universal git-safety tool instructions with
this repository's actual `CLAUDE.md` content, which does not contain the
quoted phrases (independently re-verified: `grep` against the real file
found no match). (2) Criterion 5 requires a commit-history/harness-config
check the privilege-scope Stop boundary never authorized (it named only
criteria 1 and 4). (3) `AGENTS.md`, a real, near-identical sibling to
root `CLAUDE.md` in this repository, had no defined handling under the
precondition's channel list. (4) The Subagent dispatch section carried no
`CLAUDE.md`/`AGENTS.md` exclusion or isolation-verification requirement,
unlike both sibling skills. All four fixed in commit `14f5802`.

A companion `evaluating-skill-quality` dispatch, run against the fixed
candidate, returned **WELL-FORMED-NOT-MATURE**, 4 findings: (1) the
worked example's own Criterion-1 evidence overstated a single
`chore: sync agent instructions` commit (paired with its own PR-merge
commit) as a "recurring pattern," when `CLAUDE.md`'s own 12-commit
history contains exactly one such commit, independently re-counted via
`git log --follow`. (2) A commit history showing PR-merge-shaped commits
is weaker evidence for enforced review than the Stop boundaries implied
-- it shows a PR was used, not that branch protection required an
independent approval. (3) A genuine Blind spot: Auto-memory has no
on-disk artifact representation the other four channels share, and the
Precondition never said what a reviewer should actually read for it. (4)
The Scope section's own wording on the retired skill's lineage was
ambiguous enough to misread as "this skill now covers that sub-case,"
the opposite of its own intent. All four fixed: the worked example's
evidence corrected to the real commit count, plus a branch-protection
hedge; a representation-confirmation step added to the Precondition for
Auto-memory (and recorded as an open worked-example gap, since no
representation was available to build a third worked example against);
the Scope wording tightened to state the sub-case is an unowned gap, not
absorbed.

## Open follow-up

A post-fix confirmation round of both `evaluating-skill-quality` and
`battle-testing-a-skill`, ideally under genuine isolation this time, has
not yet run -- tracked in `metadata/gitapex.yaml`'s own
`lifecycle.experimental.reason` rather than assumed clean without it.

## History: evaluating-decision-state-discipline (retired)

Preserved for provenance; describes audit rounds run against the retired
predecessor skill's own prior form, not this skill.

No `evals/evaluating-decision-state-discipline/` suite existed for that
skill either. There was no committed task corpus, no no-skill baseline,
and no model tier evaluated. Building one was out of scope for that
skill's initial authoring pass and was left as follow-up work, the same
disclosed-gap pattern this file's sibling entries use (see
`evals/auditing-agent-product-scope/eval-status.md`) rather than a
silent omission -- an ablation-capable, not-yet-run gap, not an
absent-mechanism one.

A fresh `battle-testing-a-skill` dispatch against the initial candidate
returned overall **FAIL**, concentrated in Stop-boundary gaps relative to
the sibling `evaluating-deterministic-gate-quality` skill: no foreclosure
of a target artifact's own self-asserted "verification already waived"
claim; the precondition's "state not capturable" branch had no
evidence-citation mandate (a lazy reviewer could stop the whole review
there on an unsupported assertion); the execution-safety boundary claimed
parity with the sibling's but was a materially weaker paraphrase, dropping
the "synthetic input does not make an environment safe" and "never
execute with real credentials/a live service/mutating state" clauses; no
delimiter-safe quoting requirement; no install/vendoring-time provenance
boundary; no cross-session/memory-poisoning or multi-turn-escalation
coverage; no handling for the target's own source being missing or
unreadable (as distinct from an empty state store, which the skill
already handled well); and no anti-carryover boundary against this
skill's own illustrative worked examples. All findings were fixed:
`SKILL.md` gained a mirrored waiver-spoofing boundary, an evidence-citation
requirement on both precondition branches, a strengthened execution-safety
boundary matching the sibling's in full, delimiter-safe quoting, install/
vendoring-integrity and memory-poisoning/multi-turn boundaries, a new
check-0 branch for an unreadable target source, and an anti-carryover
boundary for its own worked examples.

A companion `evaluating-skill-quality` dispatch rated the same candidate
**WELL-FORMED-NOT-MATURE**, citing: criterion 2's own text and the
frontmatter description both overclaimed zero overlap with the sibling
skill's dimension 15 (a real, if partial, overlap the audit confirmed by
direct comparison); the one reference file was linked only in the
SKILL.md footer, not at the "five criteria" section where a reader
actually needs it; the precondition's dependency on a sibling skill's
prior Mechanism-fit verdict had no stated evidentiary bar; two
safety-critical Stop boundaries lacked the enforcement-status hedge the
sibling skills consistently carry; and the lifecycle note's "no eval
mechanism" framing was less precise than "this repository's own eval
mechanism has simply not been pointed at this skill yet." All fixed:
criterion 2 and the frontmatter now state precisely what is added beyond
dimension 15 rather than claiming zero overlap; an inline pointer to the
worked-examples file was added at the "five criteria" section; the
precondition now states what counts as evidence of "already applied
elsewhere"; the two Stop boundaries gained the enforcement-status hedge;
and the lifecycle note was reworded for precision and made to defer to
`metadata/gitapex.yaml` as its single source of truth (closing a separate
refactor-pass finding that the two files' deferred-item lists had
drifted out of sync with each other).

A separate, independent smoke test (given only `SKILL.md` and
`metadata/gitapex.yaml`, withholding the worked-examples file) applied
this skill to a real target already in this repository -- the git-
worktree-cleanup-after-merge-back open item disclosed in
`skills/executing-a-branch-plan/references/execution-and-dispatch.md` --
and found the precondition itself cannot-be-assessed (the Workflow tool's
own cleanup implementation is not present in this repository to read),
correctly refusing to force a PASS/FAIL verdict. This disagreed with the
worked-examples file's own original text, which had claimed the
precondition cleared; a separate adversarial code review independently
caught the same worked example inventing a fifth verdict label ("FAIL,
live-tested required, not yet performed") for an untested criterion, and
a second BLOCKING finding elsewhere (a synthetic worked example claiming
"live-tested" for a script that was never written or run). All three
findings were fixed by rewriting the real-target worked example to match
the smoke test's own more rigorous, evidence-cited walk (cannot-be-
assessed / not-applicable throughout, no forced verdict) and by removing
the synthetic example's unsupported live-tested claim.

A five-round primary-source-grounding effort (issue #576, PR #579) then
ran against this skill -- adding citations for the five gate-shaped
criteria, correcting `capabilityAssumption` from an unintentional
`Adaptive` to `Broad`, and fixing a trigger-wording overclaim -- before
the design review recorded at the top of this file found the whole
gate-shaped framing itself was the wrong target for the requester's
follow-up direction. PR #579 was closed without merging and issue #576
closed as not planned; see this repository's PR #579 and issue #576 for
that round's own full detail, preserved on GitHub rather than repeated
here.

Refs #547, #576, #579.

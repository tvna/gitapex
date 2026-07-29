# evaluating-decision-state-discipline eval status

No `evals/evaluating-decision-state-discipline/` suite exists yet for this
newly authored skill (issue #547). There is no committed task corpus, no
no-skill baseline, and no model tier evaluated. Building one is out of
scope for this skill's initial authoring pass and is left as follow-up
work, the same disclosed-gap pattern this file's sibling entries already
use (see `evals/auditing-agent-product-scope/eval-status.md`) rather than
a silent omission -- an ablation-capable, not-yet-run gap, not an
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

Refs #547.

## Second round (#576): primary-source grounding added

Adds `references/primary-sources.md`, grounding the five criteria in real,
independently fetched and verified primary sources, mirroring
`evaluating-skill-quality/references/rubric.md`'s own citation convention.
This also serves as the post-fix confirmation round the prior "Open
follow-up" section below named as still outstanding.

A fresh `evaluating-skill-quality` dispatch against the round-2 candidate
returned **WELL-FORMED-NOT-MATURE**: 2 findings. Dimension 6 (durability)
-- `SKILL.md`'s Notes section claimed the new file was "fully portable...
cites no path or fact specific to this skill's own authoring repository,"
which the new file's own Blocking-posture-justification section
contradicted at the time (a repo-specific issue URL and "this
repository's four gate-realization domains" aside). Dimension 2
(conciseness) -- each of the five new sections opened with a "The
criterion: ..." restatement of `SKILL.md`'s own criterion text, nearly
verbatim, a duplication the body is the one correct owner of. A
non-blocking Blind-spot-pass finding was also raised: the Procedure did
not state whether the five-criteria walk repeats once per distinct state
source when a single decision reads more than one, each with a
potentially different discipline.

A fresh `battle-testing-a-skill` dispatch (disclosing it had no isolated
subagent-dispatch tool available and was itself running inside a context
carrying this repository's own CLAUDE.md -- graded per that skill's own
contamination-disclosure Stop boundary, PASS verdicts provisional,
FAIL findings standing on their own cited evidence) returned **FAIL**: the
same portability overclaim (independently confirmed); no Stop boundary
foreclosing a reviewer citing the new file's grounding as if it were
target-specific evidence (the existing anti-carryover boundary named only
`gitapex-worked-examples.md`); no stated requirement to scan a newly
fetched external quote for a hidden/encoded instruction before trusting it
into this always-loaded file (confirmed currently inert -- no such content
actually present); and `metadata/gitapex.yaml`'s `relatedTo` omitting
`grounding-in-primary-sources`, the sibling skill whose discipline the new
file already follows. Five of the file's twelve citations were
independently re-fetched and diffed against the quoted text by this
dispatch and confirmed genuine, including one source's own grammatical
typo faithfully reproduced -- evidence against fabrication.

All findings fixed in the same change: the repo-specific aside removed
from `references/primary-sources.md` (the same decision was already
recorded, once, in `metadata/gitapex.yaml`'s own `spec.references`, so
nothing was lost); the five duplicated criterion restatements replaced
with a one-line pointer by criterion number; the anti-carryover Stop
boundary extended to name `references/primary-sources.md` explicitly; an
authoring-time instruction-scan requirement added to the new file's own
intro paragraph; `grounding-in-primary-sources` added to `relatedTo`; and
the Procedure's step 3/4 clarified to walk the five criteria once per
distinct state source when more than one feeds the same decision.
Re-verified after fixes: `check_skill_shape.py` 40/40, full suite 1368
passed, ASCII-only, no reintroduced control-theory vocabulary, and no
repository-specific path or fact remaining in `references/primary-
sources.md`.

Refs #576.

## Open follow-up

A third, post-fix confirmation round of both `evaluating-skill-quality`
and `battle-testing-a-skill` against the round-2 fixes above has not yet
run -- tracked in `metadata/gitapex.yaml`'s own
`lifecycle.experimental.reason` rather than assumed clean from the fixes
alone. `battle-testing-a-skill`'s own round-2 dispatch also flagged that
its result is single-trial and context-contaminated (no isolated
subagent-dispatch tool was available to it) rather than the full
three-trial isolated protocol that skill's own Procedure calls for; a
genuinely isolated re-run is still outstanding.

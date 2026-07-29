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

## Third round (#576): unified the five criteria with their grounding

A requester review judged the second round's own split itself
structurally wrong: `references/primary-sources.md` was pure citation/
historical explanation, disconnected from the five criteria's full
definitions (which stayed in `SKILL.md`) -- exactly the decision-state-
discipline thinness this skill exists to catch, now present in its own
construction, unlike `evaluating-skill-quality/references/rubric.md`,
which unifies its own nine dimensions' full substantive content with
their citations in one file.

`references/primary-sources.md` deleted; `references/criteria.md` added,
merging the five criteria's full definitions (moved out of `SKILL.md`)
with their primary-source grounding into one elaboration per criterion.
`SKILL.md`'s own "The five criteria" section was first shrunk to a bare
pointer (naming the five criteria, no definitions at all), mirroring how
`SKILL.md` treats `rubric.md`'s nine dimensions.

A fresh `battle-testing-a-skill` dispatch (again disclosing context
contamination and no isolated-dispatch tool -- see Open follow-up)
returned **FAIL** on that bare-pointer draft: dimension 14's regression-
corpus gap (pre-existing, already disclosed, not new); and a real,
newly-introduced regression -- `evaluating-skill-quality` declares this
skill's own `capabilityAssumption: Adaptive`, whose own dimension-5 rule
requires `SKILL.md`'s body to complete the common case with no forced
reference read; stripping the five criteria's definitions out of the body
entirely broke that contract (rubric.md's identical file-split is exempt
only because `evaluating-skill-quality` itself declares `Broad`, not
`Adaptive`). A companion `evaluating-skill-quality` dispatch returned
**WELL-FORMED-NOT-MATURE**: the same regression corpus gap; a confirmed
dimension-2 duplication (the four-gate-realization-domains sentence
repeated near-verbatim in both `SKILL.md` and `criteria.md`); and a
non-blocking Blind-spot finding (one shared, mutable state source feeding
multiple distinct gate decisions with potentially conflicting discipline
requirements -- not addressed this round, named for visibility). Both
dispatches also independently found `eval-status.md` (this file) stale --
still describing the deleted `primary-sources.md` as current, with no
round-2b entry -- which this section itself is the fix for.

Fixed: `SKILL.md`'s "The five criteria" section restored each criterion's
full core definition (2-4 sentences: the question plus one canonical-
failure example), keeping the body self-sufficient for the Adaptive
declaration's strong-model common case; `references/criteria.md` no
longer restates those definitions, instead assuming them known and moving
straight into per-domain notes and grounding -- genuine layered depth,
not duplicated prose. The four-gate-realization-domains sentence now
lives only in `SKILL.md`; `criteria.md`'s own intro no longer repeats it.
Re-verified: `check_skill_shape.py` 40/40, full suite 1368 passed,
ASCII-only, no reintroduced control-theory vocabulary, no repository-
specific path or fact in `criteria.md`, and the four-domain sentence
confirmed present in exactly one file.

Refs #576.

## Fourth round (#576): capabilityAssumption correction, description rewrite

Two further requester findings, independent of the structural criticism
above. First: `spec.capabilityAssumption: Adaptive` was never an
intentional declaration for this skill -- corrected to `Broad`, matching
`evaluating-skill-quality`'s own declaration (the skill whose
`SKILL.md`/`references` split this skill mirrors). This resolves the
round-3 tension at its root: `Broad` does not carry Adaptive's own
stricter dimension-5 rule (body must complete the common case alone), so
the round-3 fix (full criterion definitions inline in `SKILL.md`) no
longer rests on that stricter rule alone. A fresh round-4
`evaluating-skill-quality` dispatch confirmed independently that
dimension 5's own plain (non-Adaptive) rule already requires exactly this
placement regardless of capability declaration ("detail the model reads
on every single use belongs inlined in `SKILL.md`") -- keeping full
definitions inline is the only correct placement under the ordinary
rule, not a leniency `Broad` merely permits; an earlier draft of this
entry understated this as "optional," corrected here. Second: the
frontmatter `description` did not state an explicit invocation trigger (a
"Use when" clause) the way `evaluating-skill-quality`'s own description
does -- rewritten to add one, keeping the five named points and
sibling/distinct disambiguation.

The same round-4 dispatch found the initial "Use when" wording ("once
evaluating-deterministic-gate-quality's Mechanism-fit test has concluded
the artifact is gate material") overclaimed a strict precede-me
sequencing that `SKILL.md`'s own Procedure step 1 explicitly relaxes (a
first-time reviewer may apply that sibling test directly, as a disclosed
exception) -- fixed by rewording to "already applies (or applies here,
for a first review)". It also found the shared-state-source-feeding-
multiple-decisions Blind-spot item (named in this file's own "Open
follow-up" section since the third round) was missing from
`metadata/gitapex.yaml`'s own `lifecycle.experimental.reason`, the field
`SKILL.md`'s Notes section calls "the current, full list of deferred
items" -- a real drift between what `SKILL.md` promises and what that
field actually lists. Fixed by adding it as deferred item (5).

A further, non-blocking dimension-9 (cross-model robustness) finding from
the same dispatch: two classification judgments -- distinguishing
"aggregate/noisy" state from "a single sharp fact" in precondition check
2's routing branch, and the not-applicable-vs-cannot-be-assessed
distinction generally -- lack the same dedicated worked-example
treatment the five criteria themselves get, a named but unverified
weak-tier risk. Not addressed this round; named here for visibility
rather than silently dropped, since this repository's own eval corpus
for this skill (dimension 8's own disclosed gap, unchanged) is the
correct place to eventually measure it, not a documentation fix alone.

Re-verified: `check_skill_shape.py` 40/40 (`capability-assumption-
declared`: `Broad`; `description-length`: 1015/1024 chars;
`description-yaml-safe`: safe after replacing two colon-space sequences
introduced by the rewrite with the repository's own `--` convention, a
real YAML-plain-scalar-breaking pattern the shape checker caught before
this ever reached CI), full suite 1368 passed, ASCII-only, no
reintroduced control-theory vocabulary.

Refs #576.

## Fifth round (#576): trigger-precision and citation-evidence fixes

A fresh `battle-testing-a-skill` dispatch against the fourth round's own
candidate independently confirmed the same trigger-precision defect
(dimension 3) a companion `evaluating-skill-quality` dispatch also found:
the description's "once evaluating-deterministic-gate-quality's
Mechanism-fit test has concluded..." reads as a strict precede-me
sequencing gate that `SKILL.md`'s own Procedure step 1 explicitly relaxes
(a first-time reviewer may apply that sibling test directly). Fixed
already, in the same edit that produced the candidate this dispatch
reviewed -- reworded to "already applies (or applies here, for a first
review)".

The same dispatch also raised a PLAUSIBLE (not confirmed) dimension-2
finding: Procedure step 1's "a citation to a prior review's own recorded
verdict" evidence bar does not itself require fetching and confirming
that citation actually states a gate-material verdict for the specific
artifact under review, rather than merely existing in a citation-like
shape. Fixed: step 1 now states this explicitly ("fetch or open that
citation and confirm it actually states a gate-material verdict for this
specific artifact; a citation-shaped string that does not resolve to one
... is the same as no citation").

A further, out-of-lane observation (not one of `battle-testing-a-skill`'s
22 dimensions, named per its own Blind Spot Pass): `SKILL.md`/`criteria.md`
cite the sibling skill's own dimensions and criteria by bare number
("dimension 15," "dimension 10," "Domain placement criterion 6"), all
independently re-verified as currently correct, but no deterministic gate
protects these bare-number cross-skill citations against silently going
stale if the sibling skill's own dimensions are ever renumbered --
`check_skill_shape.py`'s `cross-skill-citation-resolves` check only
covers the file+heading citation shape, not bare numeric ones. This is a
shape-checker tooling gap, not a deferred item of this skill's own
content, so tracked here rather than added to
`metadata/gitapex.yaml`'s `lifecycle.experimental.reason` (which that
field's own char budget also could not currently absorb) -- named for
visibility, not implemented this round.

Re-verified: `check_skill_shape.py` 40/40, full suite 1368 passed,
ASCII-only, no reintroduced control-theory vocabulary.

Refs #576.

## Open follow-up

A sixth, post-fix confirmation round of both `evaluating-skill-quality`
and `battle-testing-a-skill` against this round's fixes has not yet run
-- tracked in `metadata/gitapex.yaml`'s own `lifecycle.experimental.reason`
rather than assumed clean from the fixes alone. Every `battle-testing-a-
skill` dispatch against this skill so far has flagged that its result is
single-trial and context-contaminated (no isolated subagent-dispatch tool
was available to it) rather than the full three-trial isolated protocol
that skill's own Procedure calls for; a genuinely isolated re-run is
still outstanding. Two named, non-blocking gaps remain deliberately
unaddressed rather than silently dropped: the third round's Blind-spot
finding (one shared state source feeding multiple decisions with
potentially conflicting discipline requirements, tracked in
`metadata/gitapex.yaml`'s own deferred-item list), and this round's
bare-numeric cross-skill-citation drift-gate gap (tracked only here, per
the distinction explained above).

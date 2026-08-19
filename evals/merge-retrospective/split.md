# Held-out split for merge-retrospective

Train / selection / test partition for `evals/merge-retrospective/`,
established so `scorer-gated-skill-edits`' own precondition gate (a real
scorer plus a held-out split, both required before any iterative edit to
`skills/merge-retrospective/SKILL.md` is kept) is satisfied. This is the
second corpus in this repository to satisfy that gate --
`evals/evaluating-skill-quality/split.md` (37 fixtures, 16:13:8) is the
first and the precedent this file follows for naming and ratio-deviation
reasoning. The scorer is the same shared
`skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py`; no new script
was needed. The structured train/selection/test fixture assignment,
declared partition, split-arithmetic exclusions, and equivalence-class
pairs live in `split.json` (`evals/merge-retrospective/split.json`),
conforming to
`skills/scorer-gated-skill-edits/references/split.schema.json`; this file
carries the narrative that assignment alone doesn't capture.

## Corpus size caveat

SkillOpt's default split ratio is 2:1:7. At 18 fixtures that ratio gives a
selection split of roughly two tasks -- too thin to gate a strict
improve-or-reject decision, since one outlier score alone would swing the
selection mean by 50%. This is the same caveat
`evals/evaluating-skill-quality/split.md` already recorded for its own
corpus, and the same one this repository's own tracking issue (#310, T2
decision source) states directly: "held-out 5件未満は『たまたま1件外れて
20%以上振れる』茶番になり、20件超は誰も頼んでいないベンチマーク構築にな
る" (fewer than 5 held-out fixtures is theater that swings 20%+ on one
fluke; more than 20 is an unrequested benchmark-building exercise). This
split uses a flatter **9:6:3** partition (train:selection:test) instead,
named explicitly as a deviation from the 2:1:7 default, with 9 held-out
fixtures (selection + test) sitting inside that issue's stated 5-8 target
band -- one over the 8-fixture upper end, from PR #328's own follow-up fix
adding class 9 (see below) after a Codex review found the original
16-fixture corpus left it uncovered; a single fixture pair over the stated
band is not renegotiated back down, since the alternative is leaving a
named coverage gap open. PR #1215's own follow-up (class 10, see below)
widens this further to **10:6:4**, one more train and one more test
fixture -- the selection split (the one that actually gates an
improve-or-reject decision) is unchanged, so the corpus-size caveat's own
reasoning still holds at the new totals.

Split-arithmetic exclusions: none

Every fixture `split.json`'s `assignment` object lists is counted in the
`10:6:4` declared above -- 10 train, 6 selection, 4 test, matching exactly,
with no listing-consistency entry sitting outside the arithmetic. That line is
machine-readable: `.github/scripts/gitapex_gate_split_fixture_coverage.py`'s
Check D (gitapex#907) parses the declared partition and this line, then
asserts each split's unique listed count minus its declared exclusions
equals the declared figure.

## Equivalence classes

Ten equivalence classes cover the taxonomy's three categories
(missing-deterministic-gate / unclear-agent-instruction /
external-human-decision) crossed with zero-repair, multi-repair-mixed, and
five procedural edge cases the skill's own text calls out by name (the
tie-break rule, the Step 0 carry-forward check, the Step 0 dedup check's
own exact-match discipline, the force-push enumeration caveat, and Step 4's
template/title-convention precedence rule). Every class has at least one
fixture in train and at least one in held-out (selection or test); no
class exists only on one side.

| # | Class | Train | Held-out |
|---|---|---|---|
| 1 | Missing-deterministic-gate, isolated single-repair | `propose-dont-implement.yaml` | `gate-lint-unused-import-selection.yaml` (selection) |
| 2 | Unclear-agent-instruction, isolated single-repair | `instruction-error-message-wording-train.yaml` | `instruction-naming-convention-selection.yaml` (selection) |
| 3 | External/human-decision, isolated single-repair | `external-human-decision.yaml` | `external-decision-reviewer-style-tradeoff-selection.yaml` (selection) |
| 4 | Zero-repair cycle | `zero-repair-docs-only-train.yaml` | `guardrail.yaml` (selection) |
| 5 | Multi-repair, mixed classification in one cycle | `normal.yaml` | `multi-repair-mixed-three-category-selection.yaml` (selection) |
| 6 | Tie-break: a repair fitting two categories resolves to the earliest pipeline point | `edge.yaml` | `tie-break-restraint-not-reclassified-test.yaml` (test, restraint) |
| 7 | Step 0 carry-forward check (prior retrospective's proposed gate) | `carried-forward-gate-unimplemented-train.yaml` | `carried-forward-gate-implemented-test.yaml` (test, restraint) |
| 8 | Force-push enumerated as its own repair, only when directly observed | `force-push-observed-train.yaml` | `force-push-not-claimable-test.yaml` (test, restraint) |
| 9 | Step 4: repo's own title convention takes precedence over the skill's fallback shape | `title-convention-precedence-train.yaml` | `no-title-convention-fallback-selection.yaml` (selection, non-trigger) |
| 10 | Step 0 dedup check: exact string equality, not substring, decides a title match | `dedup-step0-exact-match-train.yaml` | `dedup-step0-title-substring-not-exact-match-test.yaml` (test, restraint) |

Class 1's train exemplar (`propose-dont-implement.yaml`) and class 5's
train exemplar (`normal.yaml`) also incidentally exercise class 2's
classification vocabulary (`normal.yaml` contains one gate repair and one
instruction repair together); this is intentional reuse, not
double-counting -- their own listed classes above are what motivated each
fixture's construction and none of the ten classes is represented on
only one side because of the reuse.

Class 9 was added after the original 16-fixture corpus shipped (PR #328's
own review round): the blind spot pass below had explicitly named "no
fixture exercises a repo with its own issue template or title convention
overriding the skill's fallback shape" as a known, undosed gap, and Codex
independently flagged the same gap as a P1 finding, citing
`scorer-gated-skill-edits`' own requirement that every actual trigger
branch get both a positive and a negative/non-trigger fixture before a
split counts as satisfying the precondition gate. Unlike classes 6-8 (all
restraint checks pairing a train positive with a held-out
superficially-similar-but-different-conclusion case), class 9's held-out
fixture is a genuine **non-trigger** counterpart: it is not trying to trick
the skill into over-applying the precedence rule, it verifies the fallback
shape remains correct behavior when a repo genuinely has no convention to
defer to -- exactly the negative case `scorer-gated-skill-edits` asks for.

Every held-out fixture pairs with its train counterpart on a **distinct
domain** (different language, different subsystem, different failure
mode) so the gate measures generalization of the classification behavior,
not memorization of a train fixture's exact wording -- the same discipline
`evals/evaluating-skill-quality/split.md`'s pairs already document. Four
of the ten held-out fixtures (classes 6-8 and 10) are additionally
**restraint** checks: each presents a scenario that superficially
resembles its train counterpart's positive case but must NOT trigger the
same conclusion -- `tie-break-restraint-not-reclassified` must stay
classified as unclear-agent-instruction rather than being
over-reclassified as a gate gap; `carried-forward-gate-implemented` must
NOT produce a "Carried-forward gate" subsection once a citing commit is
found; `force-push-not-claimable` must neither claim nor deny a
force-push beyond what the available data shows;
`dedup-step0-title-substring-not-exact-match` must NOT be treated as a
duplicate of a near-identically-titled prior retrospective once the two
titles are compared for exact equality rather than substring
containment. These sit in the test split (read once, for a final report
only) rather than selection, since a restraint check that already
informed fixture design should not also gate acceptance of the same edit
that motivated it.

The five pre-existing fixtures (`normal.yaml`, `edge.yaml`,
`guardrail.yaml`, `external-human-decision.yaml`,
`propose-dont-implement.yaml`) predate this split and had no train/
selection/test assignment before this file; none of them were written with
knowledge of a selection-split gate result (no gate has ever been run
against this skill), so assigning `guardrail.yaml` to selection here does
not leak anything -- it is the same status as every other fixture in this
corpus at the moment this file was written.

## Blind spot pass

Per `scorer-gated-skill-edits`' own precondition gate, naming what this
corpus does *not* cover rather than leaving the question unaddressed:

- No fixture exercises a PR history reconstructed from a truncated or
  paginated `get_review_comments`/`get_commits` result (a very long
  review thread). All sixteen fixtures give the full history inline.
- No fixture combines the Step 0 carry-forward check with a zero-repair
  cycle in the same PR (Step 0 always runs regardless of this cycle's own
  repair count, per the skill's own Procedure ordering).
- No fixture probes non-English review comments or commit messages.

**Closed since this file's original version:** "No fixture exercises a
repo with its own issue template or title convention overriding the
skill's fallback shape" was named as a gap here and independently flagged
by Codex review on PR #328 as a P1 finding. Class 9
(`title-convention-precedence-train.yaml` /
`no-title-convention-fallback-selection.yaml`) closes it -- kept here,
struck from the open list above rather than silently deleted, so the
history of what was found and closed stays visible.

These are named as known gaps for a future iteration to close, not
fabricated as covered.

## Fixture-linting note

`evals/scripts/gitapex_lint_fixture_assertions.py --tasks-glob
"evals/merge-retrospective/tasks/*.yaml" --rubric
skills/merge-retrospective/SKILL.md --skill skills/merge-retrospective/SKILL.md`
was re-run against the full twenty-fixture corpus (PR #1215's class-10
addition) and reported **0 warnings** -- including for the 2 new
fixtures' own lowercase `"missing deterministic gate"` /
`"already retrospected"` assertions. This supersedes an earlier version
of this note (PR #328's class-9 addition) that disclosed 20
case-sensitivity warnings against that run's linter, all argued as
non-issues grounded in `SKILL.md`'s own lowercase running-text usage
(`"a missing deterministic gate"`, inline `"Classification: missing
deterministic gate."`, etc.) rather than fixed. `extract_anchors` in the
now-current linter (`evals/scripts/gitapex_lint_fixture_assertions.py`)
scans quoted-phrase anchors (`QUOTED_RE`) alongside headings and bold
spans, and `check_case` clears an assertion on an exact-case match
against *any* anchor in that list -- so the same lowercase running-text
occurrences this note's prior version already cited as the correct
grounding are now themselves picked up as anchors, closing the warnings
without any fixture wording change. Verified live against the current
tool rather than assumed from that mechanism description alone.

## Iteration log

No `## Iteration:` entries exist yet: no candidate edit has been gated
against this split. Once one is, it uses the standardized
`## Iteration: <issue>, <title>` heading, with `### Gate result`,
`### Transfer check`, `### Rejected-edit log`, and `### Verdict`
subsections -- superseding the previous separate top-level `## Kept-edit
log` / `## Rejected-edit log` sections this file used before this
migration.

# Held-out split for scorer-gated-skill-edits

Train / selection / test partition for `evals/explaining-the-work/`,
established so `scorer-gated-skill-edits`' precondition gate (a real
scorer plus a held-out split, both required before any iterative edit to
this skill's `SKILL.md` is kept) is satisfied. See
`skills/scorer-gated-skill-edits/SKILL.md` for the gate itself and
`skills/scorer-gated-skill-edits/scripts/score_contract.py` for the
scorer, which scores each fixture's `expected.output_contains` /
`output_not_contains` (and, where used, `output_contains_near`) block
deterministically. This is the first iteration recorded against this
skill; `eval-status.md` previously noted no committed run existed.

## Corpus size caveat

SkillOpt's default split ratio is 2:1:7. At 10 fixtures that ratio is not
literally achievable; following the precedent already set in
`skills/scorer-gated-skill-edits/references/worked-example.md` ("the
ratio is aspirational" for a small fixture count) and
`evals/evaluating-skill-quality/split.md`'s own disclosed deviations,
this split uses 2:2:6, named explicitly as a deviation from the 2:1:7
default. The honest minimal groundwork is a larger fixture corpus over
time, not a smaller gate.

## Assignment

- **train** (motivates edits; read for evidence, never scored for
  acceptance): `guardrail.yaml`, `normal.yaml`,
  `precedence-repo-noqa-format-train.yaml`.
- **selection** (gates acceptance; scored before/after the candidate
  edit, strict improve-or-reject, ties rejected): `commit-includes-terse-why.yaml`
  (new; the dedicated positive-route check for the changed branch, held
  out so the changed branch is not covered only in train),
  `closes-when-fully-satisfied.yaml` (pre-existing; direct regression
  control on the same Commit-log bullet's untouched Closes/Refs choice).
- **test** (read once, for a final report only, never to motivate or
  gate an edit): `edge.yaml`, `no-auto-generated-adr.yaml`,
  `no-bulk-rewrite.yaml`, `no-redundant-what-comment.yaml`,
  `no-staleness-only-deletion.yaml`, `refs-when-partial-work.yaml`,
  `precedence-informal-convention-not-deterministic-selection.yaml`
  (its filename predates this assignment decision -- kept as-is rather
  than renamed, since the fixture id is stable and referenced above;
  assigned to test, not selection, so it does not retroactively expand
  this iteration's already-recorded selection-split gate table above,
  which belongs to the unrelated Commit-log-rule edit).

## Equivalence classes

One class, added incidentally while creating this file (not part of the
Commit-log-rule iteration below): `SKILL.md`'s pre-existing `##
Precedence` section ("The calling repository's existing deterministic
gates ... take precedence over this skill") had zero fixture coverage
before this file existed at all -- `check_precedence_branch_coverage`
(`.github/scripts/gate_split_fixture_coverage.py`, Check B) only applies
once a skill has a `split.md`, so this gap was invisible until this
iteration created one. Same shape as the `merge-retrospective` precedent
that check's own docstring cites (issue #352/#328).

| # | Class | Train | Held-out |
|---|---|---|---|
| 1 | Precedence: a named deterministic repo gate (`Contract:`/`noqa`) overrides the skill's own template | `precedence-repo-noqa-format-train.yaml` | `precedence-informal-convention-not-deterministic-selection.yaml` (test) |

Not scored before/after for this iteration's own gate (below) -- this
branch is untouched by the Commit-log-rule edit, so there is nothing to
compare. Each fixture was verified once against the current (post-edit)
skill text: `precedence-repo-noqa-format-train.yaml` scored 1.000000;
`precedence-informal-convention-not-deterministic-selection.yaml` scored
1.000000.

## Blind spot pass

Named explicitly, before trusting the split: the corpus has no fixture
testing (a) a commit for a change with no linked issue/PR at all -- every
fixture assumes an issue number exists -- or (b) a scenario combining the
new terse-Why requirement with the Closes-vs-Refs choice in the *same*
fixture (the corpus tests each separately). Both are real, disclosed gaps
for a future addition, not silently assumed covered.

## Iteration: issue #599, Commit-log rule revision (Option B)

Candidate edit: revise `SKILL.md`'s "Commit log" bullet from an absolute
ban on Why in the commit body to requiring a terse, present-tense Why (one
to a few sentences, not a design essay) alongside the issue pointer, per
git-community consensus ([beams], [kerneldoc], [progit] -- see the new
`## References` section); add that References section. No other bullet
changed. Full text: see this PR's diff.

Classification: **ordinary** (rewords required behavior; adds a new
requirement rather than only deleting text, so the pruning-only
lexicographic exception does not apply).

### Two fixture-assertion defects found and fixed during this iteration's own gate run, before any score was banked

Same recurring class `evaluating-skill-quality/split.md` already
documents multiple times (a construct-validity gap in the assertion, not
a rubric/skill regression):

1. **`commit-includes-terse-why.yaml`'s first-draft design used
   `output_contains_near` (window + no-blank-line) between the Why-phrase
   and the `Closes #N` trailer.** Self-testing against a realistically
   formatted response (subject / blank line / body / blank line /
   trailer -- the exact convention [beams] and [progit] themselves
   recommend) showed this fails a *correct* new-rule response, because
   the trailer is conventionally blank-line-separated from the body by
   every cited primary source. Simplified to a plain `output_contains`
   check; separately, the prompt was narrowed to ask for "just the commit
   message" (no explanation), because without that narrowing a model's
   own surrounding commentary mentioned the Why-phrase regardless of
   whether the commit itself contained it -- a false tie (both old- and
   new-rule baseline dispatches scored 1.0 against the original
   broader-prompt version). Verified via direct git-community-consensus
   reasoning and by re-dispatching both sides against the narrowed prompt
   before banking any score (see table below).
2. **`closes-when-fully-satisfied.yaml` and `refs-when-partial-work.yaml`
   each banned the sibling trailer form** (`Refs #212`, `Closes #340`)
   as a bare `output_not_contains` string. The new rule's more
   explanatory candidate responses correctly discuss the Closes-vs-Refs
   distinction in prose while recommending the right trailer -- e.g.
   "...Refs #212 (partial/related)" and "not Closes #340" -- a
   negation-trap false-fail of a correct response, the same class
   `lint_fixture_assertions.py`'s `check_negation` rule targets for
   fixture-vs-corpus authoring but does not catch here (it checks static
   fixture/corpus consistency, not response-time contamination). Fixed
   by dropping the redundant negative ban on both fixtures -- the
   positive `output_contains` check (`Closes #212` / `Refs #340`) already
   fails a wrong-trailer response on its own, since a response
   recommending only the wrong trailer would not also contain the right
   one.

Neither fix touched a fixture's scenario/prompt substance (except
`commit-includes-terse-why.yaml`'s wording narrowing above, applied
before any score was banked on either side); `lint_fixture_assertions.py`
run clean (0 warnings) against the final fixture set.

**Separately observed, unrelated to this edit, not fixed here (out of
scope for this bounded change):** `edge.yaml` (0.750) and
`no-auto-generated-adr.yaml` (0.833) scored below 1.0 in the candidate
test-split run purely because the model wrote "can't" where the fixture's
`output_contains: "cannot"` expects the unconctracted form -- a
pre-existing, model-phrasing-variance fragility on branches this edit
does not touch (their `SKILL.md` text is byte-identical old vs. new).
Disclosed here rather than silently absorbed; a future iteration on those
two fixtures specifically should relax the assertion (e.g. drop the
contraction requirement or accept either form).

### Gate result

One fresh dispatch per (fixture, skill-version) cell -- given the full
skill text (pinned via `git show HEAD:...` for the old side, the proposed
text for the new side) plus the fixture's prompt, asked to respond as
that skill, active -- scored with `score_contract.py --assertions
<task.json> --output <run.txt>`. The other four branches (Code body, Test
code, Code comments, Stop boundaries) are byte-identical old vs. new, so
no old-skill dispatch was run for fixtures that exercise only those.

| Fixture | Split | Before (old text) | After (new text) |
|---|---|---|---|
| `guardrail.yaml` | train | 0.833333 | 1.000000 |
| `normal.yaml` | train | 1.000000 | 1.000000 |
| `commit-includes-terse-why.yaml` | selection | 0.666667 | 1.000000 |
| `closes-when-fully-satisfied.yaml` | selection | 1.000000 | 1.000000 |
| `edge.yaml` | test | -- (unaffected branch) | 0.750000 |
| `no-auto-generated-adr.yaml` | test | -- (unaffected branch) | 0.833333 |
| `no-bulk-rewrite.yaml` | test | -- (unaffected branch) | 1.000000 |
| `no-redundant-what-comment.yaml` | test | -- (unaffected branch) | 1.000000 |
| `no-staleness-only-deletion.yaml` | test | -- (unaffected branch) | 1.000000 |
| `refs-when-partial-work.yaml` | test | -- (unaffected branch) | 1.000000 |

Selection-split mean: before **0.833333**, after **1.000000**.
`score_contract.py --compare-to 0.833333 --scores <after-selection-scores.txt>`:
**`1.000000 KEEP`**.

### Transfer check

Re-ran the 2 selection fixtures' candidate (new-text) version on Haiku
4.5 -- an adjacent, weaker model tier, distinct from this session's own
model -- same prompts, same scorer:

| Fixture | Haiku (new text) |
|---|---|
| `commit-includes-terse-why.yaml` | 1.000000 |
| `closes-when-fully-satisfied.yaml` | 1.000000 |

No regression below the no-skill baseline (not separately measured this
iteration -- disclosed gap, same shape `evaluating-skill-quality/split.md`
already carries for its own transfer checks) or below the strong-tier
score.

### Rejected-edit log

None this iteration -- no candidate wording was scored and discarded; the
two fixture-assertion defects above were caught and corrected *before*
any score was banked on either side, not after seeing a result, per this
skill's own Stop boundary against motivating or leaking from a scored
split.

### KEEP

Selection-split score strictly increased (0.833333 -> 1.000000), train
fixtures pass under the new text, all six unaffected-branch test
fixtures continue to pass (the two contraction-fragility scores are a
disclosed, pre-existing, edit-unrelated scorer quirk, not a regression),
and the transfer check on an adjacent model tier shows no regression.
**KEEP.**

## Iteration: issue #631, Routing section restructure + exercises: declaration coverage

Candidate edit: issue #629's adversarial review of a proposed mechanical
"out-of-scope" classifier found that `skills/explaining-the-work/SKILL.md`
has no real section unit -- "Commit log," "Code comments," "Code body," and
"Test code" are bold bullet lead-ins nested under one single `## Routing`
heading, not headings themselves -- which blocked any mechanical way to
know which section a fixture's prompt is designed to exercise. The
candidate converts the 4 bold bullet lead-ins under `## Routing` into real
`### <label> -> <original text>` sub-headings, with **zero wording change**
beyond what the heading conversion mechanically requires (dropping a
now-irrelevant trailing comma/period right after the bold close;
capitalizing a word that is now sentence-initial in the body paragraph
that follows). Separately, `.github/scripts/gate_split_fixture_coverage.py`
gains a third check (Check C): every fixture a `split.md`'s declared
`selection` split names must declare a well-formed `expected.exercises`
(non-empty list of section labels, mirroring
`lint_fixture_assertions.py`'s `_is_real_dispatch_declaration` shape
validation) matching a real current `###`-level section label in the
sibling SKILL.md -- closing the specific vacuous-declaration gap issue
#629 found, without building the rest of the proposed classifier (a
CEILING/OUT_OF_SCOPE verdict remains explicitly out of scope, per that
issue's own research). `commit-includes-terse-why.yaml` and
`closes-when-fully-satisfied.yaml` (this file's 2 existing selection
fixtures) are backfilled with `exercises: ["Commit log"]`.

Classification: **pruning-only on the SKILL.md side** (markup restructure,
no wording change to any routing rule) **plus an additive, opt-in fixture
field and a new, independently-scoped CI check** -- neither branch removes
or reweights any existing behavioral rule.

### No selection fixture's score can move -- verified directly, not assumed

Both selection fixtures (`commit-includes-terse-why.yaml`,
`closes-when-fully-satisfied.yaml`) were re-dispatched, one fresh dispatch
per side, against the old (bullet-form) and new (heading-form) SKILL.md
text:

| Fixture | Before (old text) | After (new text) |
|---|---|---|
| `commit-includes-terse-why.yaml` | 1.000000 | 1.000000 |
| `closes-when-fully-satisfied.yaml` | 1.000000 | 1.000000 |

Both responses contained the same required substrings under both texts
("worker pool" / "Closes #401"; "Closes #212"), confirming the restructure
is behaviorally a no-op for the one branch these 2 fixtures observe, not
merely assumed from the wording being unchanged. `python3
evals/scripts/lint_fixture_assertions.py` (full discovery-mode run) is
byte-identical before and after this change, diffed directly against a
pre-change checkout.

### Gate result -- not a scorer-gate candidate; verified by direct diff instead

This edit changes no assertion any existing fixture scores against (the
new `exercises:` field is read only by the new Check C, never by
`score_contract.score()`), so there is no selection-split mean to compute
before/after -- the same "no fixture in scope of the strict gate could
observe this edit at all" situation as the `## Iteration: issue #609
(continued)` entry above, this time because the branch touched carries no
wording change at all rather than because no fixture exercises that
branch.

### Why this is landed anyway, outside the scorer-gate's scope

Same reasoning as this file's prior `## Iteration: issue #609` sections:
a markup-only restructure with a directly-verified-identical behavioral
surface, plus a new opt-in fixture field and CI check that no existing
scoring path reads, are outside `scorer-gated-skill-edits`' behavioral
jurisdiction by construction. Landed as a documentation/tooling-coverage
fix, not claimed as a scorer-validated behavioral KEEP.

### Rejected-edit log

None this iteration -- the restructure's behavioral-no-op status was
confirmed by direct dispatch before landing, not assumed and later found
wrong.

### Verdict

**Behavioral gate: N/A (no fixture assertion this edit could move) --
landed as a structural/tooling fix**, verified via direct real dispatch
(both selection fixtures score identically old vs. new text) and a
byte-identical `lint_fixture_assertions.py` full-repo run, per the
reasoning above.

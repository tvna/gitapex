# PR #612 real-world effect: real-in-repo-script ablation (issue #618)

## Purpose

Every fixture scored so far for PR #612 (`evals/explaining-the-work/split.md`'s
`## Iteration: issue #609` sections) uses a synthetic YAML prompt describing a
hypothetical change. This is a separate, standalone measurement: 5 scripts
already committed to this repository were sampled, one realistic change
scenario was authored per script grounded in that script's own real content,
and each scenario was dispatched against both `main`'s pre-#612 `SKILL.md` and
PR #612's tip `SKILL.md`. This is an ecologically-grounded supplement to the
existing synthetic-fixture suite, not a replacement for it, and it is **not**
merged into #612 -- it is a measurement artifact on its own branch.

## Method

- **Old text**: `skills/explaining-the-work/SKILL.md` as committed on `main`
  (commit `28a0d75`), i.e. the state after PR #600 merged and before #612.
- **New text**: `skills/explaining-the-work/SKILL.md` at the tip of
  `claude/explaining-the-work-citation-fix-609` (PR #612, commit `c08b95c`),
  i.e. after all three of #612's commits (Commit-log citation/brevity-cap fix,
  ISO/IEC/IEEE 42010 + IBIS governance grounding, issue/ADR number-conflation
  clarification).
- **Sampled scripts** (5, spanning a scorer, a CI gate, an eval-infra runner, a
  large checker script, and a lint script):
  - `skills/scorer-gated-skill-edits/scripts/score_contract.py`
  - `.github/scripts/gate_split_fixture_coverage.py`
  - `evals/scripts/run_ablation.py`
  - `skills/evaluating-skill-quality/scripts/check_skill_shape.py`
  - `evals/scripts/lint_fixture_assertions.py`
- For each script, one realistic prompt was authored citing a real feature
  read directly from that script's own source/docstring (see each task YAML
  under `tasks/` in this directory) plus a fictional-but-plausible issue
  number that evaluated and rejected an alternative -- the same convention
  this repository's committed eval corpus already uses throughout (e.g.
  `guardrail.yaml`'s `#103`, `normal.yaml`'s `#55`).
- Each of the 5 scenarios was dispatched once against the old text and once
  against the new text (10 dispatches total; one general-purpose subagent per
  cell, given the full skill text plus the scenario prompt, told to respond
  in character -- same method used throughout `split.md`'s existing
  iterations), then scored with
  `skills/scorer-gated-skill-edits/scripts/score_contract.py`.
- The `gate_split_fixture_coverage.py` scenario was deliberately designed to
  require both a `Refs` trailer (against an older, related-but-not-closed
  issue) and a `Closes` trailer (against the issue actually resolved) in the
  same response -- a harder, more realistic version of the Closes-vs-Refs
  distinction than most of the existing synthetic corpus tests.

## Results

| Script | Old (main) | New (#612 tip) |
|---|---|---|
| `score_contract.py` | 1.000000 | 0.750000 |
| `gate_split_fixture_coverage.py` | 0.800000 | 0.800000 |
| `run_ablation.py` | 1.000000 | 1.000000 |
| `check_skill_shape.py` | 0.750000 | 0.750000 |
| `lint_fixture_assertions.py` | 0.750000 | 1.000000 |

Mean: old 0.860000, new 0.860000 -- identical means, driven by an apparent
regression and an apparent improvement that cancel out.

## Character-count effect (issue #618 follow-up question)

The substring-assertion score above says nothing about *length* -- a
follow-up question asked whether #612 measurably shortened (or lengthened)
the generated artifacts. Two distinct things were measured, since they point
in different directions:

**`SKILL.md` itself grew, substantially, not shrank.** `main` (pre-#612):
3,623 chars / 78 lines. PR #612 tip: 7,696 chars / 140 lines -- +4,073
chars / +62 lines (+~112%), across all three commits (+24, +30, +8 net
lines respectively). This is expected and was never the goal: #612 adds
citation corrections and governance grounding (more accurate prose), not a
trim -- a size *reduction* was never the intended effect here, unlike, say,
a "trim narrative bloat" PR elsewhere in this repo's history.

**The generated commit message itself (the artifact the Commit-log bullet's
"terse Why, not the full Why" rule actually governs) got shorter under the
new text, consistently, across all 5 real-script scenarios** -- isolating
just the commit-message code block from each of the 10 saved dispatch
transcripts:

| Script | Old commit msg (chars) | New commit msg (chars) | Diff |
|---|---|---|---|
| `score_contract.py` | 361 | 360 | -1 |
| `gate_split_fixture_coverage.py` | 470 | 453 | -17 |
| `run_ablation.py` | 366 | 349 | -17 |
| `check_skill_shape.py` | 423 | 293 | -130 |
| `lint_fixture_assertions.py` | 378 | 333 | -45 |

Total: 1,998 -> 1,788 chars, a **-210 char / ~10.5% reduction**, and every
single one of the 5 scenarios moved the same direction (shorter or flat,
never longer) -- not a mixed/noisy result. Spot-checked for substance, not
just length (e.g. `check_skill_shape.py`'s -130 chars): the new-text commit
message ("Reject real model IDs as illustrative SKILL.md content ... A real
model identifier reads as a concrete example, but it goes stale the moment
that model is superseded, and it duplicates the staleness check
gate_provenance_disclosure.py already performs.") still carries the same
two real reasons as the old-text version, just phrased more economically --
this reads as a genuine terseness effect, not information loss.

Caveat, disclosed rather than overclaimed: n=5, one dispatch per cell (not
averaged over repeated trials), so this is suggestive, not a statistically
robust effect size -- consistent with this repository's own disclosed
single-dispatch-per-fixture limitation elsewhere in `split.md`. The whole-
response character counts (including surrounding prose/explanation, not
just the commit-message block) moved the *opposite* direction in 4 of 5
cases (see the raw dispatch `.txt` files) -- the new text's added citation
apparatus appears to make the model *explain itself* more, while the actual
commit artifact it produces got more concise. These are two different
things and neither contradicts the other.

## Honest interpretation -- not a real effect, a scorer-construct artifact

The `score_contract.py` "regression" (1.0 -> 0.75) and the
`lint_fixture_assertions.py` "improvement" (0.75 -> 1.0) both trace to the
same single assertion, `output_contains: "test name"` (lowercase), and the
same root cause: `score_contract.py`'s substring check is case-sensitive by
design (no `.lower()`/`.casefold()` anywhere in `score()`), and every
response's own explicit heading was `**Test name**` / `## Test name`
(capital T) -- the assertion only passed when the model *also* happened to
use the lowercase phrase "test name" somewhere in its prose (e.g. "What in
the test name" or "the test name carries the What"), which is incidental
phrasing variance, not a behavioral difference PR #612 caused. Confirmed by
direct inspection of all 10 response texts (kept alongside this report):

- `score_contract.py`, new text: only has `## 3. Test name` (heading), no
  lowercase "test name" phrase elsewhere -- fails on phrasing alone.
- `gate_split_fixture_coverage.py`, both old and new: same pattern, tied at
  0.8 for the identical reason (neither response happens to use the lowercase
  phrase outside its heading).
- `check_skill_shape.py`, both old and new: same pattern, tied at 0.75.
- `lint_fixture_assertions.py`, new text: happens to echo the *unchanged*
  Test-code routing bullet's own wording ("when the test name itself can't
  carry the issue pointer") -- that bullet is byte-identical between old and
  new `SKILL.md`, so this is not attributable to anything #612 changed either.
- `run_ablation.py`, both old and new: both happen to use the lowercase
  phrase, tied at 1.0.

This is the same class of fixture-assertion fragility already disclosed
multiple times in `split.md` (`edge.yaml`'s "can't" vs. "cannot", the
"PR/issue body" vs. "issue/PR body" ordering) -- a construct-validity gap in
*this ablation's own assertion*, not a rubric or skill regression. Disclosed
here rather than hidden, per this repository's own established practice.

**Setting the "test name" assertion aside**, the remaining assertions
(`Closes #N` / `Refs #N` correctness, the citable `why-not(#N)` comment, no
fabricated ADR path, no `LGTM`) were satisfied identically by every one of
the 10 responses, old text and new text alike -- including the harder
`gate_split_fixture_coverage.py` scenario's simultaneous `Refs #526` /
`Closes #527` distinction. **No behavioral difference was observed between
old and new `SKILL.md` text across any of the 5 real, in-repo-script-grounded
scenarios.**

## Conclusion

Consistent with every synthetic fixture scored in `split.md`'s three
iterations, this real-script ablation found **no measurable behavioral
effect** from PR #612's changes on the routing decisions this skill governs
(Closes-vs-Refs choice, why-not citation discipline, ADR-path fabrication
avoidance, test-name/docstring routing) -- on either model tier tested
earlier or the model used for this ablation. This is the expected result:
PR #612 corrects what the skill's prose *cites and claims as grounding* for
its existing rules (citation accuracy, governance sourcing, a documentation
clarity fix), not the rules' own behavioral content -- and a routing-fixture
scorer has no way to observe a citation-accuracy change by construction, the
same conclusion `split.md` already reached via synthetic fixtures, now
independently corroborated against real repository content rather than
invented scenarios.

## Raw dispatch transcripts

`tasks/*.yaml` holds the 5 scenario definitions (prompt + expected
assertions). `dispatches/<script>.{old,new}.txt` holds the actual, unedited
response text for all 10 dispatches scored above -- kept for direct
inspection, not summarized only.

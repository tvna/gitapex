# Effectiveness-corpus methodology (issue #1143)

This document is the "define and record the labeling methodology first"
step issue #1143's own Acceptance Criteria Map requires before building
the corpus itself (row 1). It is the methodology for the corpus at
[`effectiveness-corpus.json`](effectiveness-corpus.json) (shape pinned by
[`effectiveness-corpus.schema.json`](effectiveness-corpus.schema.json)),
and for the end-to-end wiring
[`gitapex_run_effectiveness_correlation.py`](gitapex_run_effectiveness_correlation.py)
performs against it, feeding
[`gitapex_compute_rank_correlation.py`](gitapex_compute_rank_correlation.py).

## Scope: what this issue decides, and what it explicitly does not

Issue #1143 is sub-task 2 of #1137, building the tooling that a future,
separate, contingent piece of work (#1137's own sub-task 3) needs before it
can ask "does waza's body-structure / negative-delta-risk advisory predict
real skill quality?" This document, and the corpus it describes, answer
only:

- What counts as an "independently labeled" quality outcome for a skill in
  this repository (this section).
- Which skills are in the corpus, and how each one's real outcome would be
  obtained.
- How the three pieces (corpus, `gitapex_run_eval_suite.py` as the
  measurement mechanism, the correlation utility) plug together.

It deliberately does **not**:

- Reach a real correlation verdict. That needs a live, credentialed model
  run (`gitapex_run_eval_suite.py`'s `subprocess_executor`, real
  `ANTHROPIC_API_KEY`), which is not available in the environment that
  built this tooling -- the same disclosed precondition every other
  `evals/scripts/*.py` module in this repository already names for itself.
  This remains true even with the real x-metrics wired in (issue #1144):
  a `--dry-run` proves the plumbing, never a real verdict.
- Port body-structure or negative-delta-risk into `evaluating-skill-quality`'s
  rubric. That is #1137 sub-task 3's (issue #1144's) own contingent,
  correlation-gated decision -- this document and its corpus only build
  and describe the measurement tooling that decision depends on.

Issue #1144 closed the one gap this document's own first revision left
open: computing a real, native, waza-independent x-metric (previously a
disclosed placeholder, `SKILL.md` body line count). See "End-to-end
wiring" below for what is measured now.

## What "independently labeled" means here

Issue #1143's own Acceptance Criteria Map named this "unknown, pending a
decision." This document makes that decision explicitly, rather than
leaving it silent:

**A skill's quality-outcome label must come from a mechanism structurally
incapable of reading waza's own advisory output.** Not "differently
worded evidence that happens to agree with waza," but a different code
path with no dependency on `waza` anywhere in it -- so a future
correlation between that label and a waza-derived x-metric is measuring a
real relationship, not restating one input as if it were two.

This repository's own `gitapex_run_eval_suite.py` (issue #1132) already
provides exactly such a mechanism: it loads a skill's real `SKILL.md` into
a real model invocation (`--append-system-prompt-file`) and scores the
result against that skill's own committed task fixtures
(`expected.output_contains`/`output_not_contains`, plus any declared
`graders:`), producing a `mean_score` in `[0, 1]`
(`eval-scores.schema.json`'s own shape). Nothing in that path reads,
shells out to, or otherwise depends on `waza` -- it is a behavioral
measurement (does the skill, when actually loaded and run, produce the
expected output), not a static-text pattern match over the skill's own
prose the way waza's advisories are. This is the mechanism this corpus
adopts as its label source, matching Acceptance Criteria Map row 3's own
naming of `gitapex_run_ablation.py`/`gitapex_run_eval_suite.py` as "the
measurement mechanism."

Concretely: a skill's quality-outcome label is its most recent real
`mean_score` from running `gitapex_run_eval_suite.py` against that
skill's own `evals/<skill>/eval.yaml` and `skills/<skill>/SKILL.md`. No
live credentialed run happened as part of building this issue's own
tooling (disclosed precondition, see Scope above), so
[`effectiveness-corpus.json`](effectiveness-corpus.json) does not carry a
fabricated number for every skill. Where a real, already-committed
`eval-scores.schema.json`-conformant result file exists for a skill (today:
one -- `evaluating-skill-quality`, see its own `known_prior_result` entry),
the corpus cites it, by path, for provenance and cross-reference only --
it is informational, not the value the wiring script feeds into the
correlation tool (see "End-to-end wiring" below: that value is always
computed fresh). Every other entry simply names where its own real label
would come from once a credentialed run happens; there is no
`unmeasured` sentinel value baked into computed correlations, because no
placeholder number is ever substituted for a real one.

## Held-out split

Issue #1143's own Facts section names
`skills/scorer-gated-skill-edits/references/split.schema.json`'s
train/selection/test concept as "may be a reusable shape... not
necessarily reusable content." This corpus reuses the *shape* (a `split`
field per entry, using that schema's own `selection`/`test` vocabulary)
but not a full three-way partition: unlike `scorer-gated-skill-edits`,
this corpus does not gate an *edit* (there is no candidate patch being
motivated by a `train` split here), so `train`'s specific role does not
apply. Two splits only:

- `selection` -- the split any future decision about porting waza's
  advisories into the rubric (#1137 sub-task 3) must be based on.
- `test` -- read once, for a final report only; never used to motivate or
  gate that decision.

**Assignment rule (deterministic, so it is reviewable and was not
cherry-picked after seeing any outcome):** sort every skill name
alphabetically, zero-index it, and assign `test` to every 5th skill
(index mod 5 == 0), `selection` to the rest -- a fixed 20%/80% split. With
23 skills total this is 4 `test` / 19 `selection`. This is a small corpus
either way (23 skills total, the same "roughly 25-26 skills" limitation
issue #1143's own residual-risk column already names) -- `SMALL_N_THRESHOLD`
and `MODERATE_N_THRESHOLD` in `gitapex_compute_rank_correlation.py` disclose
the resulting power caveat directly in that tool's own output, not only
here.

## End-to-end wiring

`gitapex_run_effectiveness_correlation.py` is the "documented procedure"
Acceptance Criteria Map row 3 asks for, made runnable rather than only
described in prose:

1. Load and schema-validate `effectiveness-corpus.json`.
2. Filter to one split (`--split selection`, the default, or `test`/`all`).
3. For each entry, call `gitapex_run_eval_suite.run_eval_suite(eval_yaml,
   skill_md, executor=...)` to obtain a fresh `y` (`mean_score`) -- the
   real measurement mechanism, injectable per
   `gitapex_run_ablation.py`'s own established `Executor` dependency-
   injection type. A stub executor (no live credentials, no real model
   call) proves the plumbing without the credentialed-execution
   precondition; the real `subprocess_executor` is what a future live run
   would pass instead, with no code change.
4. Compute two real, native, waza-independent `x` metrics via
   [`gitapex_compute_waza_advisory_metrics.py`](gitapex_compute_waza_advisory_metrics.py)
   against the skill's own `SKILL.md` body (frontmatter stripped):
   `x_negative_delta_risk` (`count_constraint_signals` -- sentence/bullet/
   numbered-list-initial `Must`/`Never`/`Always` occurrences) and
   `x_body_structure` (`count_body_structure_signals` -- 0/1/2, a
   `## Worked example`/`## Examples` heading and/or a `## Error handling`/
   `## Troubleshooting` heading). Both are this repository's own fresh,
   corpus-calibrated operational definitions of waza's advisory concepts,
   not a reverse-engineered copy of waza's own undisclosed counting
   algorithm -- see that module's own docstring for the calibration
   rationale (a literal shouting-case/literal-"Examples" reading is a
   constant zero across the real corpus, which would make a correlation
   mathematically undefined). Every result this script prints carries an
   explicit `x_metric_caveat` string disclosing this, so a reader of the
   JSON output does not mistake either metric for a reproduction of
   waza's own (undisclosed) algorithm.
5. Feed the resulting `(x_negative_delta_risk, y)` and `(x_body_structure,
   y)` pairs into `gitapex_compute_rank_correlation.compute_correlation`
   -- separately, once per metric, since a possible rubric port for each
   is an independent decision, never a package deal (this session's own
   resolved scope) -- and print the full result for each (rho, CI, power
   caveat) alongside the shared per-entry pairs and any skipped entries
   with their reason (see "Failure handling" below).

Example (dry run, no credentials needed):

```shell
uv run --frozen python3 evals/scripts/gitapex_run_effectiveness_correlation.py \
    --corpus evals/scripts/effectiveness-corpus.json --split selection --dry-run
```

Once live credentials exist in a given environment, dropping `--dry-run`
switches step 3 to the real `subprocess_executor` -- the only thing that
changes; the corpus, the split discipline, and the correlation tool are
identical in both modes.

**Failure handling.** Twenty-four real, independently-authored `eval.yaml`
suites vary in size and are maintained for their own skill's purposes, not
for this corpus's -- a suite that `gitapex_run_eval_suite.py` cannot run
(a malformed declaration, an empty `tasks:` glob) is a fact about that one
suite, not a reason to abort every other skill's measurement. Such an
entry is recorded in the result's own `skipped` list with its reason
(loud, visible in the tool's own output) and excluded from the correlation
input for that run; it is never silently dropped.

## Adding a real measurement later

Nothing about a future, real, credentialed run requires touching this
corpus's shape or its x-metrics: point `gitapex_run_effectiveness_correlation.py`
at a real executor (the default, when `--dry-run` is omitted) with
`ANTHROPIC_API_KEY` allowlisted the same way `gitapex_run_ablation.py`'s
own hermetic environment already does. Both x-metrics are already real
and native (issue #1144) -- a live run changes only `y` (from a dry-run
stub score to a real `mean_score`), nothing about how `x` is computed.
Recording that run as a `scorer-gated-skill-edits`-style run record
(`eval-run.schema.json`) at that point is a natural fit, but is that
future change's own responsibility, not retrofitted here for a run that
never happened. Whether the resulting correlation is strong enough to
port either metric into `evaluating-skill-quality`'s rubric (Dimension 3
for negative-delta-risk, Dimension 4 for body-structure, per this
session's own resolved scope -- never a new dimension) is issue #1144's
own next, still-open decision.

# Load test: score_semantic_rationale.py's mechanism at scale (issue #625)

## Purpose

`evals/score-semantic-rationale-demo/report.md` showed the mechanism working
on a single, hand-picked pair (n=2). This load test scales that same
typed-extraction + schema-constrained-comparison pipeline to 8 real,
this-session-verified repository sources x 3 candidate variants (genuine,
wrong-reason, wrong-citation) x a 3-sample judge-consistency recheck, using
the Workflow tool's own `agent(prompt, {schema})` dispatch with the exact
same `_DECISION_RECORD_SCHEMA` / `_VERDICT_SCHEMA` the committed script
defines. Full case definitions: `load-test.workflow.js` (the actual script
run). Full raw results: `results.json`.

## Two attempts -- the first failed completely, disclosed rather than hidden

- **Attempt 1** (32 agents): 100% failure. Every `agent({schema})` call hit
  `StructuredOutput retry cap (5) exceeded`, at a real cost of **1,169,223
  tokens and 160 tool calls for zero usable results**. Reading
  `journal.jsonl` (only `started`/error entries for a fully failed run, no
  richer diagnostic) surfaced one concrete, fixable defect: a
  backslash-escaped-backtick sequence inside a JS template literal in one
  case's `sourceText`, which parses to a literal stray backslash rather
  than the intended single backtick -- cosmetic, and its exact causal
  relationship to the 100% failure rate was never confirmed, but it was the
  only defect found.
- **Attempt 2** (59 agents, same script with that string fixed to use plain
  single quotes instead of backtick-escaping): **100% success. 0 failures**,
  2,223,131 tokens, 168 tool calls.
- **Total real cost across both attempts: ~3.39M tokens** for the evidence
  below. Disclosed in full rather than only reporting the successful run.

## Method

8 cases (`load-test.workflow.js`'s `CASES`), each a faithful paraphrase of a
real committed file's actual docstring/behavior verified earlier this
session (`gate_split_fixture_coverage.py`, `run_ablation.py`,
`check_skill_shape.py`, `lint_fixture_assertions.py`,
`gate_skill_branch_fixture_coverage.py`,
`gate_transfer_check_disclosure.py`, `gate_retro_title_convention_citation.py`,
`score_contract.py`). For each case, three candidate why-not comments were
generated and independently extracted + compared against the same
extracted source record:

- **genuine**: the case's own true `reason` and `citation`.
- **wrongReason**: the case's own `citation`, but the *next* case's
  `reason` (round-robin) -- same citation string, fabricated cause.
- **wrongCitation**: the case's own `reason`, but the *next* case's
  `citation` -- same cause, fabricated citation.

## Aggregate result

| Variant | n | mean score | fabrication_detected rate |
|---|---|---|---|
| genuine | 8 | 0.458 | 100% |
| wrongReason | 8 | **0.083** | 100% |
| wrongCitation | 8 | 0.458 | 100% |

`falseNegatives: []` -- across all 16 wrong-variant dispatches, **zero**
fabricated candidates were missed. This is the safety-relevant number: no
fabricated rationale slipped through undetected.

## Honest finding #1: a real confound in the genuine-vs-wrongCitation comparison

Read at face value, `genuine` and `wrongCitation` scoring identically
(0.458 both) looks like the mechanism can't tell a swapped citation from a
correct one. It cannot support that reading, because of a flaw in this
load test's own construction, not the scorer: **6 of the 8 `sourceText`
strings never state their own citation number in prose** (their extracted
`cited_ref` is `null`). For those 6 cases, *any* asserted citation --
whether the candidate's true one or a swapped one -- registers as a
mismatch against `null` for the same structural reason, so `genuine` and
`wrongCitation` are indistinguishable on the `cited_ref` field by
construction, not because the judge failed to notice a swap.

**The one case built correctly** --
`gate_split_fixture_coverage_check_a`, whose `sourceText` does embed its
real citation ("issue #191, repair 1") -- shows the mechanism actually
works as intended once the confound is removed:

| Variant | rejected_alt | reason | cited_ref | score | note |
|---|---|---|---|---|---|
| genuine | match | **no match** | match (#191) | 0.667 | candidate added an unverifiable elaboration clause |
| wrongReason | no match | no match | match (#191) | 0.333 | same citation, unrelated decision -- correctly flagged |
| wrongCitation | match | match | **no match** (#583 vs #191) | 0.667 | citation swapped, content intact -- correctly flagged on exactly that field |

This single unconfounded case cleanly separates "same citation, wrong
content" from "same content, wrong citation" -- exactly the distinction
the mechanism exists to make, and the only case in this run where the test
construction let it demonstrate that cleanly.

## Honest finding #2: the clean, unconfounded positive result

`wrongReason` (fabricated causal reasoning, same citation string as
`genuine`) scored **0.083 vs. genuine's 0.458** -- roughly a fifth --
with 100% correct fabrication detection and typically more severe verdicts
(0/3 or 1/3 fields matching, vs. genuine's usual 2/3). This comparison is
not subject to the citation-embedding confound above (both sides share the
same citation, so the `cited_ref` field behaves identically for both) and
is this load test's core, working-as-intended result: swapping in an
unrelated but plausible-sounding reason, while keeping everything else
fixed, collapses the score and is caught every time.

## Honest finding #3: a real extraction-layer limitation

`run_ablation_bare_mode`'s **genuine** case scored **0**, not because of
the citation confound but a genuine extraction error: the candidate
comment's reason clause ("`--bare` explicitly disables the very
skill-discovery mechanism a staged directory depends on") is worded
without explicitly naming which option was rejected. The extraction model
inverted it -- naming `--bare` itself (the option actually *chosen*) as
the `rejected_alternative`, the reverse of the truth (a staged
`.claude/skills/` directory was rejected). This is a real, disclosed
limitation: extraction accuracy depends on the candidate text explicitly
separating "what was rejected" from "why" -- which real one-line why-not
comments often do not do explicitly, since the code they annotate already
shows what was chosen.

## Honest finding #4: genuine cases are not immune from over-strict flagging

All 8 `genuine` cases were flagged `fabrication_detected: true` (the same
100% rate as the two intentionally-wrong variants), and none scored a
perfect 1.0. Beyond the citation-null confound above, several `genuine`
candidates included a reasoning clause slightly more elaborated than what
the paraphrased `sourceText` states outright (this load test wrote each
case's `reason` field independently of its `sourceText`, so the two are
not always a tight match) -- the judge treated that added detail as
unverifiable-from-source and flagged it. This shows the boolean
`fabrication_detected` flag is a strict, low-tolerance signal (any
unverified elaboration trips it, not only outright invention); the
0-1 `score` -- which `score_semantic_rationale.py`'s own design
deliberately leaves independent of that boolean (see the script's
docstring) -- is what actually carries the graded severity difference
between "mostly right, one added clause" (genuine, ~0.46 mean) and
"substantively different decision" (wrongReason, ~0.08 mean).

## Consistency recheck

3 (candidate, source) pairs -- all `wrongReason` variant, chosen by the
script before results were known -- were compared twice independently.
All 3 gave identical `fabrication_detected` verdicts and near-identical
per-field verdicts across both dispatches.

One recheck (`check_skill_shape_no_illustrative_model_id`, wrongReason)
surfaced a notable extra data point: the judge's explanation independently
named the *real* citation for the short-word-collision check
(`lint_fixture_assertions.py`) as **#218** -- matching this session's own
earlier-established fact -- even though neither the candidate record
(`#470`, fictional) nor the given source record (`cited_ref: null` for
this unrelated case) mentioned it. This is a strong corroborating signal
that the judge is reasoning about real repository content, not just
pattern-matching the two JSON blobs handed to it -- but it also means the
comparison step in this environment is **not proven to be strictly
closed-book**: if the dispatched subagent has file-read/grep access to
the actual repository (workflow subagents are not restricted from it by
default in this session), it may be drawing on ground truth beyond the
two records it was explicitly given, rather than reasoning from them
alone. This wasn't controlled for in this load test's design and is worth
disclosing as an open methodological question, not quietly treated as
extra proof of accuracy.

## What this does and does not prove

- **Proven, with real evidence from 59 successful dispatches**: the
  mechanism reliably distinguishes a fabricated causal reason from a
  genuine one when the citation is held fixed (finding #2, unconfounded,
  n=8 vs n=8); it can also correctly separate a swapped citation from
  swapped content once a source actually states its citation (finding #1,
  the one clean case); it caught 16/16 intentionally-wrong candidates with
  zero false negatives.
- **Not proven, and now disclosed rather than glossed over**: that
  `genuine` vs. `wrongCitation` differ in general (6/8 cases are
  confounded by this test's own source-text construction); that the
  `fabrication_detected` boolean alone is a reliable severity signal
  (it fires at 100% across all three variants -- the `score` is the
  signal that actually differentiates); that extraction is robust to
  candidate text which doesn't explicitly separate "what was rejected"
  from "why" (one clear counterexample, finding #3); or that the
  comparison step is closed-book (the #218 data point argues it may not
  be, in an environment where the dispatched agent can read the real
  repo).
- **A concrete next-iteration fix, not done here**: rebuild the 8 cases so
  every `sourceText` states its own citation explicitly (as
  `gate_split_fixture_coverage_check_a` already does), which would let all
  8 cases -- not just 1 -- cleanly separate `genuine` from
  `wrongCitation`.

## Files

- `load-test.workflow.js` -- the exact Workflow script run (attempt 2,
  post-fix).
- `results.json` -- full extracted results: aggregate `summary`, all 24
  `allResults` entries (case, variant, verdict, score), the 8-entry
  `falsePositives` list, the empty `falseNegatives` list, and all 3
  `consistency` recheck pairs with both verdicts' full explanations.

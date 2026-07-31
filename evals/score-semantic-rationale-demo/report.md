# Live demonstration: score_semantic_rationale.py's mechanism (issue #625)

## Purpose

`evals/scripts/score_semantic_rationale.py` cannot be run live end-to-end in
this environment (`claude --bare -p ...` returns an authentication error --
`ANTHROPIC_API_KEY` is unset, confirmed by direct invocation), the same
already-disclosed precondition `run_ablation.py` (issue #583) carries. To
still gather real, live evidence that the mechanism actually distinguishes
semantic correctness from a fabricated citation -- not merely a claim that it
should work -- this session dispatched the same three-call pipeline (typed
extraction of a candidate, typed extraction of a real source, schema-
constrained semantic comparison) via the Workflow tool's own schema-validated
subagent dispatch, using the exact same JSON Schemas the committed script
defines (`_DECISION_RECORD_SCHEMA`, `_VERDICT_SCHEMA`).

## Method

Two candidate why-not comments were compared against the same real source
text (`gate_split_fixture_coverage.py`'s own module docstring for Check A,
read directly from the committed file):

- **Scenario "correct"**: `# why-not(#527): requiring full-superset coverage
  would break the single-fixture recheck-dispatch convention` -- the
  candidate from this session's earlier real-script ablation (issue #618),
  intended as the "accurate" control.
- **Scenario "fabricated"**: `# why-not(#527): requiring full-superset
  coverage was rejected because it made the CI job run too slowly on large
  repos` -- same citation number, a deliberately invented, plausible-sounding
  but false reason (nothing in the source discusses CI runtime).

## Result

| | rejected_alternative_match | reason_match | cited_ref_match | fabrication_detected | score |
|---|---|---|---|---|---|
| Scenario "correct" | true | true | **false** | true | 0.667 |
| Scenario "fabricated" | true | **false** | false | true | 0.333 |

Full extracted records and judge explanations: `dispatches/scenario-correct.json`,
`dispatches/scenario-fabricated.json` (raw, unedited subagent output).

## Honest finding -- the mechanism caught something not deliberately planted

The "correct" scenario was *not* actually fully accurate: `#527` is a
fictional issue number invented for issue #618's earlier ablation study
(explicitly disclosed there as "a fictional-but-plausible issue number,"
the same convention this repo's own committed fixtures use, e.g.
`guardrail.yaml`'s `#103`). The *real* `gate_split_fixture_coverage.py`
docstring attributes Check A to `issue #191, repair 1` -- a different number
entirely. The semantic judge caught this mismatch on `cited_ref` for **both**
scenarios, correctly, even though only one scenario was designed to test
citation fabrication. This is stronger evidence than a clean pass/fail on a
single planted defect would have been: the mechanism did not merely pattern-
match an obviously-wrong answer, it caught a citation discrepancy this
report's own author did not consciously design in.

What the two scenarios *do* cleanly separate is the `reason` field --
exactly the axis `score_contract.py`'s substring scoring cannot see at all.
Both candidates contain the literal string `why-not(#527)`; a substring
check (`output_contains: "why-not(#527)"`) would score both 1.0, identically,
regardless of whether the stated reason is true. The semantic judge instead
scored them 0.667 and 0.333 respectively, correctly identifying that the
fabricated scenario's stated reason ("CI job run too slowly") has no support
in the real source, while the "correct" scenario's stated reason (breaking
the single-fixture recheck-dispatch convention) is a faithful paraphrase of
what the source actually says. The judge's own explanation states this
plainly: "Nothing in the source mentions CI runtime, job speed, or
large-repo performance... This is an unsupported, fabricated reason."

## What this does and does not prove

- **Proven, with real evidence from this session**: the typed-extraction +
  semantic-comparison mechanism can and did distinguish a real, accurate
  causal claim from a fabricated one sharing the identical surface citation
  string -- the exact blind spot this issue set out to close.
- **Not proven**: that this generalizes across a large, diverse sample (n=2
  here, both against the same source text); that the mechanism is robust to
  adversarial candidates specifically crafted to fool the judge; or that
  using this mechanism to *generate* rather than only *evaluate* rationale
  artifacts would help (deliberately out of scope -- see the script's own
  docstring on why generation is left unconstrained).
- **A residual construct-validity note, disclosed rather than smoothed
  over**: the "correct" scenario's own citation number was itself inaccurate
  relative to the real source (see above) -- a future iteration of this
  demo should pair the candidate's citation number with the source's actual
  citation before calling a scenario a clean "should-match" control.

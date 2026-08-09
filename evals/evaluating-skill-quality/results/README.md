# Results

Structured, machine-readable measurement data for `evaluating-skill-quality`'s
eval suite -- distinct from `eval.yaml`/`tasks/*.yaml` (what to run) and
`split.md` (the scorer-gated-skill-edits held-out gate's own train/selection/
test partition and edit-acceptance log). This directory holds what actually
happened when a suite (or a subset of it) was run: raw per-fixture scores,
per model, per run.

This file is the only README under any `evals/*/results/` directory, and the
layout it declares is not scoped to this one skill -- every `results/`
directory in the repository follows it. Until issue #926 that was a claim in
prose with nothing checking it, and the corpus drifted:
`.github/scripts/gitapex_scan_eval_results_schema.py` now enforces it, wired
in through `tests/test_gitapex_scan_eval_results_schema.py` inside
`.github/workflows/test.yml`'s pytest step and registered in
`.gitapex/ssot.json` as `eval-results-schema-drift`. Read that scanner's
module docstring for the rules' own reasoning; this file states the layout a
run author has to follow.

## Layout

One directory per run, never overwritten -- each run is a permanent,
dated record:

```
results/
  <date>-issue-<N>-<label>/
    manifest.json                    -- run provenance AND all scores
    <full-model-id>.json             -- one file per model actually run
    artifacts/*.md                   -- raw prompts and model outputs only
```

- `<date>` is the run's real calendar date (`YYYY-MM-DD`), not a
  relative git-log position.
- `<N>` is the GitHub issue this run's measurement was done for.
- `<label>` is a short, lowercase, hyphen-separated slug for the run's
  scope (e.g. `phase1`, `full-corpus`, `haiku-only-regression-check`).
- Each model file is named by its **full, current model ID** (e.g.
  `claude-haiku-4-5-20251001.json`, `claude-sonnet-5.json`), never a
  short alias -- an alias like `haiku` can resolve to a different
  underlying model over time, but a run's own record must stay pinned to
  exactly what was actually invoked.
- The run directory root holds `manifest.json` and `*.json` score files
  only. Raw prompts and verbatim model output go under `artifacts/`, so
  the root stays the machine-readable surface. Before issue #926, 13 `.md`
  files sat in run roots instead, outside this declared layout and
  referenced by no manifest.

## Each fact has exactly one home

- **`manifest.json`** owns run provenance *and* every score.
- **`artifacts/`** owns raw prompts and verbatim model output, and carries
  no score or provenance value of its own.

Before issue #926 this was not true in either direction: per-fixture scores
existed both in a manifest's `results` key and inside its `.md` files, while
one run's manifest omitted `models` entirely and only its `.md` files
recorded which model had run. Which file held a given fact varied per run.

## `manifest.json`

Every manifest states, at minimum: `date`, `issue` (full GitHub issue URL --
a bare number resolves only inside the repository that minted it), `commit`
(the exact commit the graded content was read at), `fixture_set` (which
fixtures, and where their definitions live), `trials_per_fixture`, `models`
(alias -> full model ID map), `dispatch_mechanism` (how isolation was
achieved), `scorer` (what produced the numbers), `known_gaps` (disclosed
scope limits -- never omit this even when empty; state "none known"
explicitly rather than silently dropping the key), and `headline_pattern` (a
short prose summary of the run's main finding, for a reader who will not
open every per-model file).

Two further keys are required, both added by issue #926:

- **`artifacts`** -- every file in the run directory other than
  `manifest.json` itself, as paths relative to the manifest, score files
  included. The scanner checks this against the filesystem in *both*
  directions: a listed file that does not exist is a dangling reference,
  and a file present but unlisted is an orphan. One reachability list, not
  two, so nothing can sit beside a record unreachable from it.
- **`record_contract`** -- which contract this record is written under.
  `"gate-run"` or `"pre-contract"`; there is no third value and no default.

### `record_contract: "gate-run"`

A `scorer-gated-skill-edits` gate run. The manifest is validated in full
against `skills/scorer-gated-skill-edits/references/eval-run.schema.json`,
and each file its `score_files[]` points at against
`.../eval-scores.schema.json`. Both schemas ship inside that skill (issue
#932) so the contract travels with `SKILL.md` when the skill is installed
elsewhere; this repository reads them and never authors a local fallback.

That schema requires two things beyond the minimum above: `runner` (the
runner binary's own reported name and version) and `gate` (a KEEP/REJECT
verdict with the two means that produced it). A new run performed by
following that skill's Procedure captures both, so a new run declares
`gate-run`.

### `record_contract: "pre-contract"`

A record written before that contract existed. Every one of the eight
records committed here today is one: they were measurement and audit sweeps
driven by `claude -p` subprocesses, not gate runs, so no runner version was
captured and no verdict was reached. Neither is recoverable, and issue #926
forbids reconstructing a value by inference -- `eval-run.schema.json`'s own
description draws the same line from the other side ("a repository migrating
pre-existing records onto this contract is doing its own work, not being
retro-graded by this file").

A `pre-contract` record is held to the structural rules above and exempt
from the gate-run schema, and must carry a `known_gaps` entry naming
`record_contract` and stating which contract fields were never captured. The
exemption is a disclosure, not a silence.

Declaring the key is mandatory precisely so this exemption cannot be reached
by omission: an undeclared record is a finding, not a `pre-contract` one.

### A missing value is recorded as missing, never reconstructed

`commit` may be `null`, and a null must be accompanied by a `known_gaps`
entry naming `commit`. Two records here have no commit; one could be guessed
from their date and issue number, and must not be. An undisclosed null would
read as a satisfied declaration -- the failure mode issue #631 blocker 2
already documented for `expected.exercises`.

`commit` is checked for hex shape, not for resolving on a remote: a shallow
clone cannot resolve a historical object name, and a gate that failed on a
property of the clone rather than of the record would be worse than none.

## Per-model file schema

```json
{
  "model_id": "claude-haiku-4-5-20251001",
  "n_fixtures": 23,
  "mean_score": 0.824586,
  "scores": [
    {"fixture_id": "evaluating-skill-quality-edge", "score": 0.8}
  ]
}
```

`scores` is sorted by `fixture_id` for a stable diff across runs. This is
`eval-scores.schema.json`'s shape; a `gate-run` record's score files are
validated against it.

## Convention for a new run

1. Create a new `<date>-issue-<N>-<label>/` directory -- never edit or
   overwrite a prior run's directory, even to "fix" a number; a
   correction is a new record naming its predecessor via `supersedes`,
   keeping the historical record intact.
2. Write `manifest.json` first, with every field above, including
   `record_contract` and `artifacts`.
3. Write one JSON file per model actually run, named by full model ID.
4. Put raw prompts and verbatim model output under `artifacts/`, and list
   every one of them (plus the score files) in `artifacts`.
5. Add a short summary + a link to this run's directory in the skill's own
   `eval-status.md` -- that file holds the narrative and the pointer; this
   directory holds the data. Never embed a full per-fixture score table in
   `eval-status.md` itself.
6. Run the scanner before committing:
   `uv run --frozen python3 .github/scripts/gitapex_scan_eval_results_schema.py`.

## What the gate does not check

A schema pins a manifest's shape, not the truthfulness of its values. A run
recording a model it did not invoke still passes, and so does an `artifacts`
entry pointing at a real but semantically unrelated file. The best existing
counter-practice in this corpus is
`untrusted-input-triage/results/2026-08-01-issue-645-battle-test`'s own
manifest, which distinguishes `tester_model_requested` from
`tester_model_observed` and states that the latter is a self-report rather
than verified runtime metadata -- a three-way shape a two-key `models` map
cannot express.

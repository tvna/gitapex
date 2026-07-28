# Results

Structured, machine-readable measurement data for `evaluating-skill-quality`'s
eval suite -- distinct from `eval.yaml`/`tasks/*.yaml` (what to run) and
`split.md` (the scorer-gated-skill-edits held-out gate's own train/selection/
test partition and edit-acceptance log). This directory holds what actually
happened when a suite (or a subset of it) was run: raw per-fixture scores,
per model, per run.

## Layout

One directory per run, never overwritten -- each run is a permanent,
dated record:

```
results/
  <date>-issue-<N>-<label>/
    manifest.json                    -- run provenance (see below)
    <full-model-id>.json             -- one file per model actually run
```

- `<date>` is the run's real calendar date (`YYYY-MM-DD`), not a
  relative git-log position.
- `<N>` is the GitHub issue this run's measurement was done for.
- `<label>` is a short, free-form slug for the run's scope (e.g.
  `phase1`, `full-corpus`, `haiku-only-regression-check`).
- Each model file is named by its **full, current model ID** (e.g.
  `claude-haiku-4-5-20251001.json`, `claude-sonnet-5.json`), never a
  short alias -- an alias like `haiku` can resolve to a different
  underlying model over time, but a run's own record must stay pinned to
  exactly what was actually invoked.

## `manifest.json` schema

Every run's manifest states, at minimum: `date`, `issue` (full GitHub
issue URL), `commit` (the exact commit the target `SKILL.md`/`rubric.md`
were read at), `fixture_set` (which fixtures, and where their definition
lives), `trials_per_fixture`, `models` (alias -> full model ID map for
that run), `dispatch_mechanism` (how isolation was achieved), `scorer`
(what produced the numbers), `known_gaps` (disclosed scope limits --
never omit this even when empty; state "none known" explicitly rather
than silently dropping the key), and `headline_pattern` (a short prose
summary of the run's main finding, for a reader who will not open every
per-model file).

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

`scores` is sorted by `fixture_id` for a stable diff across runs.

## Convention for a new run

1. Create a new `<date>-issue-<N>-<label>/` directory -- never edit or
   overwrite a prior run's directory, even to "fix" a number; a
   correction is a new run (or a `correction` note referencing the old
   one), keeping the historical record intact.
2. Write `manifest.json` first, with every field above.
3. Write one JSON file per model actually run, named by full model ID.
4. Add a short summary + a link to this run's directory in
   `evals/evaluating-skill-quality/eval-status.md` -- that file holds the
   narrative and the pointer; this directory holds the data. Never embed
   a full per-fixture score table in `eval-status.md` itself.

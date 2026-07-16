# Skill eval status (known gaps)

Maintainer-facing record of each skill's evaluation provenance: whether a
committed eval suite exists, whether a no-skill baseline / with-skill-vs-
no-skill comparison has been run, trials per task, and which models have
been evaluated. This is repository eval bookkeeping, not skill behavior, so
it lives here rather than in each `SKILL.md` body (a vendored skill should
not carry this repository's own eval-run status). The `evaluating-skill-
quality` rubric's dimensions 8-9 read this file for a skill's named eval
gaps rather than expecting them inline.

Update this file whenever a skill's eval suite gains a baseline run, an
additional model tier, or more trials per task.

## Cross-model matrix scaffolding (issue #106)

The harness to *measure* the repo's cross-model consistency concept now
exists; the measurement itself does not yet. Concretely, as of issue #106:

- All 12 `evals/*/eval.yaml` declare `trials_per_task: 3` (was 1), so each
  task is sampled 3 times per run rather than once. (waza's docs describe
  bootstrap confidence intervals at trials > 1; that behavior is not verified
  here, since this environment cannot run waza.)
- `evals/scripts/set_config_model.py` rewrites a suite's `config.model` for a
  given tier (waza 0.38.0 has no `--model` flag), and
  `.github/workflows/waza-eval-matrix.yml` fans that over a model list on
  manual `workflow_dispatch`. It is advisory, never a merge gate.
- No result files are committed, and the change that added this scaffolding
  ran in an environment that could not execute waza (no nix/waza binary), so
  it produced no measurement. The workflow also cannot run until the owner
  provisions the copilot-sdk endpoint secrets (`COPILOT_BASE_URL` /
  `COPILOT_PROVIDER_BASE_URL`); it fails loudly at preflight otherwise.

So every per-skill "only `claude-sonnet-4.6` has been evaluated; cross-model
behavior is currently unmeasured" line below still holds: the trials count is
a config declaration, and single-tier / single-run statements describe the
*executed* provenance, which stays as recorded until a credentialed dispatch
of the matrix workflow commits results. Do not read the scaffolding as a run.

## driving-pr-to-merge

The eval suite (`evals/driving-pr-to-merge/`) has no committed no-skill
baseline run, and only `claude-sonnet-4.6` has been evaluated -- cross-model
behavior is currently unmeasured.

## battle-testing-a-skill

The committed eval suite (`evals/battle-testing-a-skill/`) has no committed
no-skill baseline run, and only `claude-sonnet-4.6` has been evaluated --
cross-model behavior is currently unmeasured (dimensions 11-17's own
cross-model spread is unmeasured for the same reason, per
`references/provenance-and-caveats.md`). Named gap specific to this skill's
subagent-dispatch procedure: the committed eval tasks assert on final
output content (`output_contains`/`output_not_contains` substrings), not on
tool-call or dispatch traces, so they cannot confirm a fresh subagent
dispatch actually occurred for Procedure steps 1-3 or step 5's re-run --
that mechanism was exercised by one manual live run during the change that
introduced it, not by the committed suite.

## establishing-ubiquitous-language

The committed eval suite (`evals/establishing-ubiquitous-language/`) runs
the Elicit/Detect/Resolve/Maintain tasks but has no committed no-skill
baseline run, so gap-closure is mechanized but unmeasured. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is a
qualitative read (medium-freedom judgment procedure, low over-prescription
risk), not measurement.

## evaluating-skill-quality

The committed eval suite (`evals/evaluating-skill-quality/`) has no
committed no-skill baseline run, and only `claude-sonnet-4.6` has been
evaluated -- cross-model behavior is currently unmeasured. Named gap
specific to this skill's subagent-dispatch procedure: the committed eval
tasks assert on final output content, not on tool-call or dispatch traces,
so they cannot confirm the nine-dimension walk (Procedure steps 1, 2, 4, 5)
actually ran inside a fresh subagent dispatch rather than the invoking
context -- that mechanism was exercised by one manual live run during the
change that introduced it, recorded in
`skills/evaluating-skill-quality/references/worked-example-self-review.md`,
not by the committed suite.

A held-out train/selection/test split now exists for this suite
(`evals/evaluating-skill-quality/split.md`), covering the 9 original
fixtures plus 2 fixtures added specifically to gate scoring-axis edits to
dimension 8. It exists to satisfy `gated-skill-edits`' precondition gate
before any iterative edit to `references/rubric.md` is kept; it is not a
no-skill baseline and does not close the gap named above.

## explaining-the-work

The committed eval suite (`evals/explaining-the-work/`) has no committed run
at its now-declared 3 trials per task and no committed no-skill baseline, so
its metric is not yet evidence of gap-closure. Only `claude-sonnet-4.6` has
been evaluated;
cross-model behavior is currently unmeasured.

## gated-skill-edits

The committed eval suite (`evals/gated-skill-edits/`) has no committed
with-skill vs. no-skill score comparison, and only `claude-sonnet-4.6` has
been evaluated -- cross-model behavior is currently unmeasured.

## issue-to-branch

Only `claude-sonnet-4.6` has been evaluated in `evals/issue-to-branch/`;
cross-model behavior is currently unmeasured.

## merge-retrospective

The committed eval suite (`evals/merge-retrospective/`) has no committed
no-skill baseline run for the three core scenarios, so it currently
measures compliance, not gap-closure. Only `claude-sonnet-4.6` has been
evaluated; cross-model behavior is currently unmeasured. The Step 0
carry-forward check (added to `SKILL.md`, Refs #108) has zero committed
eval coverage -- none of the five task files exercise a prior
retrospective issue, a `retrospective` label, or a "Carried-forward
gate" subsection; a task covering that path is unwritten follow-on work.

## outward-artifact-preflight

The eval suite (`evals/outward-artifact-preflight/`) is committed and runs
the checklist tasks, but no baseline or with-skill-vs-no-skill results are
committed alongside it -- treat dimension 8 as mechanism-present,
results-unmeasured until a run is recorded. Only `claude-sonnet-4.6` has
been evaluated; cross-model behavior is currently unmeasured.

## ranking-the-open-queue

The committed eval suite (`evals/ranking-the-open-queue/`) runs a single
trial per task with no committed no-skill baseline. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is a
qualitative read (four simultaneous per-item qualitative axis judgments
applied across a whole backlog -- moderate under-guidance risk on a
faster/cheaper tier), not measurement.

## seeding-issue-pr-templates

The committed eval suite (`evals/seeding-issue-pr-templates/`) has no
committed run at its now-declared 3 trials per task and no committed
without-skill baseline. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

## stop-and-replan

The committed eval suite (`evals/stop-and-replan/`) has no committed run at
its now-declared 3 trials per task and no committed no-skill baseline. Only
`claude-sonnet-4.6` has been
evaluated; cross-model behavior is a qualitative read (low-freedom policy,
low over-prescription risk), not measurement.

## untrusted-input-triage

The committed eval suite (`evals/untrusted-input-triage/`) has no documented
without-skill baseline and no committed run at its now-declared 3 trials per
task. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

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

## driving-pr-to-merge

The eval suite (`evals/driving-pr-to-merge/`) has no committed no-skill
baseline run, and only `claude-sonnet-4.6` has been evaluated -- cross-model
behavior is currently unmeasured.

## establishing-ubiquitous-language

The committed eval suite (`evals/establishing-ubiquitous-language/`) runs
the Elicit/Detect/Resolve/Maintain tasks but has no committed no-skill
baseline run, so gap-closure is mechanized but unmeasured. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is a
qualitative read (medium-freedom judgment procedure, low over-prescription
risk), not measurement.

## explaining-the-work

The committed eval suite (`evals/explaining-the-work/`) runs a single trial
per task with no committed no-skill baseline, so its metric is not yet
evidence of gap-closure. Only `claude-sonnet-4.6` has been evaluated;
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
evaluated; cross-model behavior is currently unmeasured.

## outward-artifact-preflight

The eval suite (`evals/outward-artifact-preflight/`) is committed and runs
the checklist tasks, but no baseline or with-skill-vs-no-skill results are
committed alongside it -- treat dimension 8 as mechanism-present,
results-unmeasured until a run is recorded. Only `claude-sonnet-4.6` has
been evaluated; cross-model behavior is currently unmeasured.

## seeding-issue-pr-templates

The committed eval suite (`evals/seeding-issue-pr-templates/`) runs a single
trial per task with no committed without-skill baseline. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

## stop-and-replan

The committed eval suite (`evals/stop-and-replan/`) runs a single trial per
task with no committed no-skill baseline. Only `claude-sonnet-4.6` has been
evaluated; cross-model behavior is a qualitative read (low-freedom policy,
low over-prescription risk), not measurement.

## untrusted-input-triage

The committed eval suite (`evals/untrusted-input-triage/`) has no documented
without-skill baseline and runs a single trial per task. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is currently
unmeasured.

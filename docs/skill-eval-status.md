# Skill eval status (index)

Maintainer-facing index of each skill's evaluation provenance: whether a
committed eval suite exists, whether a no-skill baseline / with-skill-vs-
no-skill comparison has been run, trials per task, and which models have
been evaluated. This is repository eval bookkeeping, not skill behavior, so
it lives here (and in `evals/<skill>/eval-status.md`, one per skill) rather
than in each `SKILL.md` body -- a vendored skill should not carry this
repository's own eval-run status. The `evaluating-skill-quality` rubric's
dimensions 8-9 read a skill's own `evals/<skill>/eval-status.md` for its
named eval gaps rather than expecting them inline.

As of issue #499, each skill's own detailed narrative lives in
`evals/<skill-name>/eval-status.md`, co-located with that skill's
`eval.yaml`/`split.md`/`tasks/` -- this file stays a thin index plus any
genuinely cross-cutting content that is not about one specific skill.
Update the relevant `evals/<skill>/eval-status.md` whenever that skill's
eval suite gains a baseline run, an additional model tier, or more trials
per task; update the index below only when a skill's suite is added or
removed.

## Cross-model matrix scaffolding (issue #106)

The harness to *measure* the repo's cross-model consistency concept now
exists; the measurement itself does not yet, for the repository's suites
in aggregate. Concretely, as of issue #106:

- All 12 `evals/*/eval.yaml` declare `trials_per_task: 3` (was 1), so each
  task is sampled 3 times per run rather than once. (waza's docs describe
  bootstrap confidence intervals at trials > 1; that behavior is not verified
  here, since this environment cannot run waza.)
- `evals/scripts/set_config_model.py` rewrites a suite's `config.model` for a
  given tier (waza 0.38.0 has no `--model` flag), and
  `.github/workflows/waza-eval-matrix.yml` fans that over a model list on
  manual `workflow_dispatch`. It is advisory, never a merge gate.
- No result files are committed by that workflow, and the change that added
  this scaffolding ran in an environment that could not execute waza (no
  nix/waza binary), so it produced no measurement. The workflow also cannot
  run until the owner provisions the copilot-sdk endpoint secrets
  (`COPILOT_BASE_URL` / `COPILOT_PROVIDER_BASE_URL`); it fails loudly at
  preflight otherwise.

So every per-skill "only `claude-sonnet-4.6` has been evaluated; cross-model
behavior is currently unmeasured" line in each skill's own
`evals/<skill>/eval-status.md` still holds unless that skill's own file says
otherwise: the trials count is a config declaration, and single-tier /
single-run statements describe the *executed* provenance, which stays as
recorded until a credentialed dispatch of the matrix workflow (or an
equivalent alternative mechanism, disclosed in that skill's own file) commits
results. Do not read the scaffolding as a run. `evaluating-skill-quality`
(issue #500) is the first skill with an actual measured cross-model data
point via such an alternative mechanism -- see its own
`evals/evaluating-skill-quality/eval-status.md`.

## Index

| Skill | Eval status |
| --- | --- |
| `auditing-agent-product-scope` | [evals/auditing-agent-product-scope/eval-status.md](../evals/auditing-agent-product-scope/eval-status.md) |
| `auditing-git-hosting-surface` | [evals/auditing-git-hosting-surface/eval-status.md](../evals/auditing-git-hosting-surface/eval-status.md) |
| `battle-testing-a-skill` | [evals/battle-testing-a-skill/eval-status.md](../evals/battle-testing-a-skill/eval-status.md) |
| `drafting-an-acm-issue` | [evals/drafting-an-acm-issue/eval-status.md](../evals/drafting-an-acm-issue/eval-status.md) |
| `driving-pr-to-merge` | [evals/driving-pr-to-merge/eval-status.md](../evals/driving-pr-to-merge/eval-status.md) |
| `establishing-ubiquitous-language` | [evals/establishing-ubiquitous-language/eval-status.md](../evals/establishing-ubiquitous-language/eval-status.md) |
| `evaluating-deterministic-gate-quality` | [evals/evaluating-deterministic-gate-quality/eval-status.md](../evals/evaluating-deterministic-gate-quality/eval-status.md) |
| `evaluating-skill-quality` | [evals/evaluating-skill-quality/eval-status.md](../evals/evaluating-skill-quality/eval-status.md) |
| `executing-a-branch-plan` | [evals/executing-a-branch-plan/eval-status.md](../evals/executing-a-branch-plan/eval-status.md) |
| `explaining-the-work` | [evals/explaining-the-work/eval-status.md](../evals/explaining-the-work/eval-status.md) |
| `fixing-a-reported-issue` | [evals/fixing-a-reported-issue/eval-status.md](../evals/fixing-a-reported-issue/eval-status.md) |
| `grounding-in-primary-sources` | [evals/grounding-in-primary-sources/eval-status.md](../evals/grounding-in-primary-sources/eval-status.md) |
| `merge-retrospective` | [evals/merge-retrospective/eval-status.md](../evals/merge-retrospective/eval-status.md) |
| `outward-artifact-preflight` | [evals/outward-artifact-preflight/eval-status.md](../evals/outward-artifact-preflight/eval-status.md) |
| `planning-a-branch-from-an-issue` | [evals/planning-a-branch-from-an-issue/eval-status.md](../evals/planning-a-branch-from-an-issue/eval-status.md) |
| `ranking-the-open-queue` | [evals/ranking-the-open-queue/eval-status.md](../evals/ranking-the-open-queue/eval-status.md) |
| `responding-to-a-fresh-arrival` | [evals/responding-to-a-fresh-arrival/eval-status.md](../evals/responding-to-a-fresh-arrival/eval-status.md) |
| `scorer-gated-skill-edits` | [evals/scorer-gated-skill-edits/eval-status.md](../evals/scorer-gated-skill-edits/eval-status.md) |
| `screening-a-low-trust-contribution` | [evals/screening-a-low-trust-contribution/eval-status.md](../evals/screening-a-low-trust-contribution/eval-status.md) |
| `stop-and-replan` | [evals/stop-and-replan/eval-status.md](../evals/stop-and-replan/eval-status.md) |
| `untrusted-input-triage` | [evals/untrusted-input-triage/eval-status.md](../evals/untrusted-input-triage/eval-status.md) |
| `vetting-attack-surface` | [evals/vetting-attack-surface/eval-status.md](../evals/vetting-attack-surface/eval-status.md) |

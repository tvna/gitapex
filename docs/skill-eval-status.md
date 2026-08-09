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
- `evals/scripts/gitapex_set_config_model.py` rewrites a suite's `config.model` for a
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

## A declaration is not a run record (issue #925)

Issue #925 measured 23 of the 24 committed `evals/*/eval.yaml` declaring
`config.model: claude-sonnet-4.6`, a model confirmed retired on 2026-06-15,
and rewrote all of them to `claude-sonnet-5`. **That rewrite changed intent,
not history.** No suite was re-run, no result file was added, and no
`eval-status.md` claim about which model a skill was evaluated on became
truer or falser because of it.

The rule this makes explicit, and which
`.github/scripts/gitapex_gate_eval_declared_model.py` restates in its own
docstring next to the check that enforces the allowlist:

- `eval.yaml`'s `config.model` states which model a suite *asks* to be run
  against. It is a declaration, and it is demonstrably not a record of what
  ran: `evals/untrusted-input-triage/results/2026-08-01-issue-645-behavioral-eval/`
  documents a run that silently substituted a different model because the
  declared one was retired.
- The only trustworthy source for "this skill was evaluated on model X" is
  a run record, `evals/<skill>/results/*/manifest.json`.

So the per-skill lines quoted in the previous section still describe the
*executed* provenance and still hold verbatim, even though the file they
sit beside now declares a different model. Reading `config.model` as
evidence of an executed run is the mistake; the gate grades that field as a
declaration only and never reports it as provenance. Reconciling the prose
in each `evals/<skill>/eval-status.md` against its own run records is
deliberately out of scope for issue #925 (its own Non-goals) and is tracked
separately.

## Dispatch-trace verification scaffolding (issue #584)

A mechanism now exists to confirm, from a live transcript's own tool-call
trace, that a fresh subagent dispatch actually occurred for a fixture --
not only that the fixture's final output text matches expected substrings.
`evals/scripts/gitapex_check_dispatch_trace.py` (offline `check-transcript`
subcommand plus a live `run` orchestrator using the isolated `claude -p`
recipe from `skills/evaluating-skill-quality/references/
adversarial-self-audit.md`), a new optional fixture key
(`expected.requires_fresh_dispatch`), a non-blending
`gitapex_score_contract.py --dispatch-trace-verdict` flag, and a new blocking lint
check in `gitapex_lint_fixture_assertions.py` (check 9) together close this gap
for `evaluating-skill-quality` and `battle-testing-a-skill`, the two
skills that disclosed it.

This is opt-in per fixture, not a suite-wide re-run: as of issue #584,
only each skill's own `normal.yaml` and a new
`dispatch-required-negative-control.yaml` fixture declare
`requires_fresh_dispatch`. Do not read this as "these two suites now
fully verify dispatch" -- see each skill's own `eval-status.md` for the
live proof, the disclosed feasibility-spike findings (the dispatch tool's
real name had to be confirmed live, not assumed; the real Skill's organic
auto-trigger works but the resulting nested-dispatch chain is too slow for
a routine proof run), and the residual scope gap (most fixtures in both
suites still assert on final text only).

## Index

| Skill | Eval status |
| --- | --- |
| `auditing-agent-product-scope` | [evals/auditing-agent-product-scope/eval-status.md](../evals/auditing-agent-product-scope/eval-status.md) |
| `auditing-git-hosting-surface` | [evals/auditing-git-hosting-surface/eval-status.md](../evals/auditing-git-hosting-surface/eval-status.md) |
| `battle-testing-a-skill` | [evals/battle-testing-a-skill/eval-status.md](../evals/battle-testing-a-skill/eval-status.md) |
| `drafting-an-acm-issue` | [evals/drafting-an-acm-issue/eval-status.md](../evals/drafting-an-acm-issue/eval-status.md) |
| `drafting-an-adr` | [evals/drafting-an-adr/eval-status.md](../evals/drafting-an-adr/eval-status.md) |
| `drafting-a-pr-to-merge` | [evals/drafting-a-pr-to-merge/eval-status.md](../evals/drafting-a-pr-to-merge/eval-status.md) |
| `establishing-ubiquitous-language` | [evals/establishing-ubiquitous-language/eval-status.md](../evals/establishing-ubiquitous-language/eval-status.md) |
| `evaluating-context-channel-maturity` | [evals/evaluating-context-channel-maturity/eval-status.md](../evals/evaluating-context-channel-maturity/eval-status.md) |
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
| `scanning-attack-surfaces` | [evals/scanning-attack-surfaces/eval-status.md](../evals/scanning-attack-surfaces/eval-status.md) |
| `scanning-ci-workflows` | [evals/scanning-ci-workflows/eval-status.md](../evals/scanning-ci-workflows/eval-status.md) |
| `scorer-gated-skill-edits` | [evals/scorer-gated-skill-edits/eval-status.md](../evals/scorer-gated-skill-edits/eval-status.md) |
| `screening-a-low-trust-contribution` | [evals/screening-a-low-trust-contribution/eval-status.md](../evals/screening-a-low-trust-contribution/eval-status.md) |
| `setup-gitapex-toolchain` | [evals/setup-gitapex-toolchain/eval-status.md](../evals/setup-gitapex-toolchain/eval-status.md) |
| `stop-and-replan` | [evals/stop-and-replan/eval-status.md](../evals/stop-and-replan/eval-status.md) |
| `untrusted-input-triage` | [evals/untrusted-input-triage/eval-status.md](../evals/untrusted-input-triage/eval-status.md) |

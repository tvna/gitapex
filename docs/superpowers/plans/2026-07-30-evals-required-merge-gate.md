# Branch plan: evals-required-merge-gate (issue #582)

Produced by `planning-a-branch-from-an-issue`, executed by
`executing-a-branch-plan`. Design source: issue #582's own Acceptance
Criteria Map, re-verified against the actual workflow files and GitHub's
documented required-status-check semantics before this plan was written.

## Acceptance Criteria Map (re-verified)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `evals/` suite execution must be a required merge gate, not advisory | `waza-eval-matrix.yml` (issue #124's cross-model-matrix scope) is left unmodified. A new workflow actually executes each touched skill's `evals/` suite on push/PR. Promoting the new job to a branch-protection *required* status check is an owner-only Settings action this session's tools cannot perform, and is deliberately deferred until issue #124's credentials are provisioned (doing it before then would produce exactly the "worse than advisory" outcome the issue's own residual risk names) | New `.github/workflows/waza-eval-gate.yml`: broad `pull_request` trigger (no top-level `paths:` filter, so a required check on this job never enters GitHub's "Pending forever" state for unrelated PRs -- confirmed against GitHub's own documented behavior: a job-level skip reports `skipped`, which does not block a required check, but a workflow that never triggers at all leaves the check `Pending` indefinitely) + `workflow_dispatch`. A new step computes touched skills from a diff and only runs `waza run <skill>` for skills whose `evals/<skill>/**` changed (excluding `evals/scripts/`). Diff-to-skill-name logic lives in a new, unit-tested `.github/scripts/detect_touched_eval_skills.py` (same "git diff stays in the workflow step, script only transforms the path list" pattern as `skill_description_diff.py`). No `config.model` override (uses each suite's own committed default, unlike the cross-model matrix). Preflight fails loud (not silently skips) when `COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL` are both unset AND at least one skill was touched, citing issue #124 for the provisioning path. `waza-check.yml`'s header comment gets a short addendum noting the new workflow's existence, so its own "no such gate exists" claim does not go stale the moment this merges | Local: unit tests for `detect_touched_eval_skills.py` (normal + adversarial defeat-cases), YAML syntax check, full `uv run pytest -q`. Not locally provable: an actual GitHub Actions dispatch (this session has no live GH Actions execution capability) and the post-required-promotion skip-does-not-block behavior -- disclosed as residual risk in the PR body, not silently assumed | Promotion to a *required* check is explicitly out of scope for this PR (no tool access; sequenced after #124). The broad (unfiltered) trigger adds a small checkout+Nix-install cost to every PR, accepted as the price of being required-check-safe from day one |

## Task list (1 task, 1 wave, no worktree isolation -- single task, no concurrent write to guard against)

### Task 1 -- add the eval-execution gate workflow

Satisfies the ACM row above in full.

Files:
- `.github/workflows/waza-eval-gate.yml` (new)
- `.github/scripts/detect_touched_eval_skills.py` (new)
- `tests/test_detect_touched_eval_skills.py` (new)
- `.github/workflows/waza-check.yml` (header comment addendum only)

Steps:
1. Write `detect_touched_eval_skills.py`: given a list of changed file paths, return the sorted, deduped set of touched skill names under `evals/<skill>/...`, excluding `evals/scripts/`, validating each name against `^[A-Za-z0-9_-]+$` (raise on an invalid name, matching `skill-audit-gate.yml`'s existing convention rather than silently dropping it).
2. Write `tests/test_detect_touched_eval_skills.py`: normal cases (single skill, multiple skills, no matches), `evals/scripts/` exclusion, nested paths under a skill's own `evals/<skill>/tasks/...`, and at least one adversarial defeat-case targeting the detection logic itself (e.g. a path shaped to look like it is inside a skill's `evals/` dir but is actually `evals/scripts/`-prefixed, or a skill name containing characters outside the allowed class).
3. Write `.github/workflows/waza-eval-gate.yml`: harden-runner + checkout (`fetch-depth: 0`, `persist-credentials: false`) + Nix install (mirroring the pinned actions already used in `waza-eval-matrix.yml`), a diff step feeding `detect_touched_eval_skills.py`, a preflight step (`if:` guarded on "at least one skill touched") requiring `COPILOT_BASE_URL`/`COPILOT_PROVIDER_BASE_URL`, and a run step (`if:` guarded the same way) invoking `nix run .#waza -- run <skill>` per touched skill, writing a job-summary table, failing the job if any suite fails.
4. Add a short addendum to `waza-check.yml`'s header comment noting `waza-eval-gate.yml` now executes touched skills' suites on push/PR (not yet a required check), so the existing "no such gate exists" sentence there does not read as stale/contradicted immediately after this merges.

Proof method: `uv run pytest -q tests/test_detect_touched_eval_skills.py` plus the full suite; a YAML-validity check of the new workflow file. Not a live GitHub Actions dispatch (disclosed residual risk above).

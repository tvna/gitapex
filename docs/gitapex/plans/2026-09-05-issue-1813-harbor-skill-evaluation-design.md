# Branch Plan: issue-1813-harbor-skill-evaluation-design

Issue: https://github.com/tvna/gitapex/issues/1813
Base: main
Branch: issue-1813-harbor-skill-evaluation-design (created, tracks origin/main)

## Acceptance Criteria Map

Per-ACM-row re-verification against #1813's own facts (2026-09-05T10:24:16Z,
marker on the issue): all four rows hold; the only correction applied was
adding the missing Residual risk column the ACM gate bot flagged.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Conditional reference exists and is gated | `evaluation-via-harbor.md` read only under Docker+harbor precondition; fallback unchanged | Edit `skills/evaluating-skill-quality/SKILL.md` dispatch section (1-2 lines) + new `references/evaluation-via-harbor.md` | Shape checker 79/79 still green; manual read-through of both branches | Wording could accidentally create a control dependency on repo-root files (Portable demotion); guarded by optional-only phrasing |
| Harbor dataset runs green locally | 2 tasks, oracle + opencode/free-model | New `evals/evaluating-skill-quality/harbor/` tree (`dataset.toml`, `portability-spot-check/`, `battle-testing-trial/`) | `harbor run` reward 1.0, 0 exceptions; artifacts stay session-local | Free-model availability window; in-container apt egress variance |
| Runner is thin and safe | No grading logic; no secret handling | New `skills/evaluating-skill-quality/scripts/run_harbor_eval.py` + pytest | Unit tests; grep for secret-adjacent patterns | Scope creep into grading/aggregation |
| Harbor is a uv dependency | New optional group, pinned | Edit `pyproject.toml` + `uv.lock` | `uv sync --group harbor && uv run --group harbor harbor --version` | 0.22.0 yank/deprecation; lockfile drift |

## Task Decomposition

Four tasks, one wave (distinct files, no shared state; sequential main-thread
fallback is acceptable, parallel dispatch optional):

### Task 1: Conditional reference + SKILL.md routing

Source ACM row: 1.

Concrete ops:

1. New `skills/evaluating-skill-quality/references/evaluation-via-harbor.md`:
   Harbor procedure, precondition (`docker ps`, `harbor --version`), scope,
   expected duration, model-connection requirements. Strictly optional
   language throughout -- repo-root eval files are input-source, never
   control dependencies (condition-(b)/trigger-3 guard).
2. `skills/evaluating-skill-quality/SKILL.md` Subagent dispatch section:
   1-2 line route to the new reference under the live precondition;
   otherwise unchanged.

Proof: `gitapex_check_skill_shape.py` 79/79 against the skill; read-through
of both branches.

### Task 2: Harbor dataset (2 starter tasks)

Source ACM row: 2.

Concrete ops:

1. `evals/evaluating-skill-quality/harbor/dataset.toml` (identity, version,
   member tasks).
2. `portability-spot-check/`: three targets (Portable /
   Mixed-via-bundled-convention / sibling fan-out), expected levels asserted
   in tests (fan-out mismatch asserted as designed, not a failure).
3. `battle-testing-trial/`: injection-resistance trial, verdict shape check.
4. Dockerfiles: `node:24-bookworm-slim` + curl (measured apt-egress mitigation).

Proof: oracle pass on both tasks, then opencode + free model pass
(reward 1.0, 0 exceptions). `jobs/` artifacts deleted after recording results.

### Task 3: Thin runner script + tests

Source ACM row: 3.

Concrete ops:

1. `skills/evaluating-skill-quality/scripts/run_harbor_eval.py`: arg parsing
   (`--tasks`, `--agent`, `--model`, timeout multipliers), preflight
   (Docker + harbor presence, exit 2 with guidance, no traceback),
   `uv run --group harbor harbor run ...` exec. No grading, no secrets.
2. pytest additions for preflight paths.

Proof: pytest green; grep finds no secret-adjacent handling.

### Task 4: uv dependency group

Source ACM row: 4.

Concrete ops:

1. `pyproject.toml`: `[dependency-groups] harbor = ["harbor==0.22.0"]`
   with measured-pin comment. Independent group (not `dev`) to keep the
   heavy tree opt-in.
2. `uv.lock` regeneration via `uv sync --group harbor`.

Proof: `uv sync --group harbor && uv run --group harbor harbor --version`
reports 0.22.0.

## Skill-file edit routing

Task 1 edits a `SKILL.md` (routing lines) -- `drafting-a-skill`'s dispatch
routing applies to that row; the remaining tasks touch `references/`,
`evals/`, `scripts/`, and `pyproject.toml` only.

## Execution mode

Sequential main-thread fallback (single session, no wave/run boundary),
matching the single-wave decomposition above. `executing-a-branch-plan`
consumes this plan next.

## Known blocker (owner action)

Commits are currently impossible from this environment: the configured GPG
signing key expired 2026-08-13 and `commit.gpgsign=true`. The betterleaks
gate itself passes under `nix develop`. Execution may stage all work but
must stop before commit until the key is renewed/extended, or the owner
commits directly. This is recorded here rather than discovered mid-run.

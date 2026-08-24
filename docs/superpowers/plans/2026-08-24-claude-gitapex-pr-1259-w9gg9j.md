# Add a non-Claude HTTP executor for the HF Gemma 4 eval-matrix lane (issue #1259)

**Goal:** Add an argv-adapter HTTP executor (`evals/scripts/gitapex_run_http_executor.py`,
backed by the official `openai` SDK) behind `gitapex_run_ablation.py`'s
existing `Executor` DI type, wire it into `gitapex_run_eval_suite.py` via an
explicit `--executor {claude-cli,http}` opt-in flag, and cut
`waza-eval-matrix.yml`'s `eval-matrix-hf-gemma4` job over from
`nix run .#waza -- run` to that runner -- without changing the job's model
target, its advisory/manual-only posture, or `gitapex_run_ablation.py`'s
existing hermetic-by-default guarantee for the Claude-CLI path. Source:
https://github.com/tvna/gitapex/issues/1259.

**Design doc:** `docs/superpowers/specs/2026-08-23-hf-gemma4-http-executor-design.md`,
elicited via `eliciting-a-design` across a multi-round dialogue with the
repository owner and explicitly approved this session. Issue #1259's own
body was updated this session (via `planning-a-branch-from-an-issue`) with
the Acceptance Criteria Map this plan decomposes below -- read directly from
the issue, not re-derived here.

**File-ownership check (mechanized):**
`gitapex_check_file_ownership_conflicts.py` against the 3 tasks' file lists
below -> no conflicts (disjoint files).

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 7 changed paths ->
`pyproject.toml`/`uv.lock` (task-1) match `dependency-manifest`;
`.github/workflows/waza-eval-matrix.yml` (task-3) matches `workflow`; the
remaining 4 paths (`evals/scripts/gitapex_run_http_executor.py`,
`tests/test_gitapex_run_http_executor.py`,
`evals/scripts/gitapex_run_eval_suite.py`,
`tests/test_gitapex_run_eval_suite.py`) are `no-match`. A `no-match` is not
a clearance; full per-task screening (`screening-a-low-trust-contribution`
checks 2-8) still runs against every task's own diff regardless, per the
script's own docstring -- task-1 and task-3 additionally carry the
dependency-addition and workflow-edit hard-flag categories by design, so
their own screening pass gets particular attention (dependency-identity
verification for `openai` on task-1; workflow-permission/trigger-shape
re-check for task-3).

**Interface-dependency edges:**
- task-2 (`--executor` flag on `gitapex_run_eval_suite.py`) calls task-1's
  own exported executor-factory function -- sequenced after task-1.
- task-3 (`waza-eval-matrix.yml` job rewrite) invokes task-2's own
  `--executor http` flag and reads the exact environment-variable names
  (`HTTP_EXECUTOR_BASE_URL`/`HTTP_EXECUTOR_API_KEY`) task-2 defines --
  sequenced after task-2.

This is a strict linear chain (task-1 -> task-2 -> task-3); no two tasks
share a wave.

**Execution mode:** sequential main-thread fallback (`Workflow` tool not
invoked -- no separate, explicit user opt-in for multi-agent orchestration
in this session; invoking `executing-a-branch-plan` itself is not read as
that opt-in, matching the identical precedent already recorded in
`docs/superpowers/plans/2026-08-19-claude-pr-1231-prep-8pya3o.md`). This is
also the natural fit here independent of that precedent: the task graph is
a strict 3-node chain with no wave ever containing more than one task, so
`Workflow`'s own parallel-dispatch value is not exercised regardless of
which path runs it. Tasks run strictly in dependency order -- task-1, then
task-2, then task-3 -- directly in the main thread, one task per turn, no
worktree isolation. Step 8's refactor and adversarial-review passes still
use the `Agent` tool (a single subagent dispatch each, not the gated
`Workflow` multi-agent orchestration tool) for the independence that stage
requires, each at a stronger-reasoning tier and this session's
default-or-higher effort per that stage's own model/effort pin.

**Irreversibility classification:** none of the three tasks are
irreversible -- a new module, a new CLI flag defaulting to the prior
behavior, a new production dependency declaration, and a rewrite of one
advisory/manual-only CI job are all ordinary, git-revertible edits; no live
API write, no data deletion, no schema narrowing. No task requires a fresh
per-task authorization confirmation beyond the branch-plan-wide one
recorded below.

**Authorization record (step 1):** in-session explicit confirmation from
the human operator. No approval comment exists on issue #1259 (confirmed
via a fresh `github:issue_read get_comments` call this session -- zero
comments). Across this same session, the operator gave unambiguous,
non-hedged approval at each design decision point (a sequence of
`AskUserQuestion` selections, then "ok" approving the written design doc,
then "issueにACMを反映して" approving the ACM write-back, then, most
recently and directly responsive to this specific Branch Plan/ACM,
"マージ直前まで進める" ("progress this to right before merging") --
matching the identical approval-language precedent already recorded for
issue #1231's own plan file. No embedded instruction anywhere in this
chain attempted to redirect this gate.

## Task 1 -- HTTP executor module: `evals/scripts/gitapex_run_http_executor.py`

**Cites ACM row:** "A second Executor implementation reaching an arbitrary
OpenAI/Copilot-compatible chat endpoint."

**Quoted Planned ops (verbatim from issue #1259's ACM):** "Add
`evals/scripts/gitapex_run_http_executor.py`; add `openai` to
`pyproject.toml`."

**Files:** `evals/scripts/gitapex_run_http_executor.py`,
`tests/test_gitapex_run_http_executor.py`, `pyproject.toml`, `uv.lock`.

**Steps:**
1. Add `openai` to `pyproject.toml`'s `[project]` `dependencies` (currently
   `[]`); run `uv lock` to update `uv.lock`.
2. Implement `parse_claude_argv(argv: Sequence[str]) -> ParsedInvocation`
   (a small dataclass/named tuple: `prompt: str`, `system_prompt:
   str | None`, `model: str`) extracting the element following `-p`, the
   file contents at the path following `--append-system-prompt-file` (when
   present), and the element following `--model`. Missing `--model` raises
   `ValueError` (a configuration error). Unrecognized flags (`--bare`,
   `--tools`, `""`) are ignored, not rejected.
3. Add a pydantic `HttpExecutorConfig` (`base_url: str`, `api_key: str`)
   with a `field_validator` on `base_url` requiring scheme+host and
   rejecting raw control characters/embedded whitespace in the host --
   mirroring `.github/scripts/gitapex_check_copilot_endpoint_configured.py`'s
   `_CopilotEndpointURL` validator (reuse that module's validation logic
   directly if it can be imported cleanly without pulling in that script's
   own CLI/argparse surface; otherwise mirror the same checks locally with
   a comment citing the source).
4. Implement `build_http_executor(config: HttpExecutorConfig) ->
   gitapex_run_ablation.Executor`: returns a closure `(argv, timeout) ->
   str` that calls `parse_claude_argv(argv)`, constructs an
   `openai.OpenAI(base_url=config.base_url, api_key=config.api_key)`
   client, calls `client.chat.completions.create(model=parsed.model,
   messages=[...system message if present..., {"role": "user", "content":
   parsed.prompt}], timeout=timeout)`, and returns
   `response.choices[0].message.content`. Every `openai` SDK exception
   (auth, connection, timeout, non-2xx status) is caught and re-raised as
   `RuntimeError(str(exc))` -- matching `gitapex_run_ablation.subprocess_executor`'s
   own contract, so `gitapex_run_ablation.redact_executor_failure_reason`'s
   existing type-based dispatch (`RuntimeError`/`TimeoutExpired` ->
   redacted; everything else -> passed through) covers this path with zero
   new code in that module.

**Proof method:** `tests/test_gitapex_run_http_executor.py` --
`parse_claude_argv` against a real `build_command()`-shaped argv (prompt,
system-prompt-file, model all present; each individually absent where
valid; `--model` absent raising `ValueError`); `HttpExecutorConfig`
rejecting a schemeless/hostless/control-character base URL (same cases
`test_gitapex_check_copilot_endpoint_configured.py` already exercises);
`build_http_executor`'s returned callable against a mocked `openai.OpenAI`
client (`unittest.mock.patch` or a fake client class) for both a
successful call (correct `model`/`messages`/`timeout` passed through,
response content returned) and a simulated SDK exception (asserts
`RuntimeError`, never lets the original exception type escape). No live
HF/OpenAI credentials required or assumed anywhere in this test file.

## Task 2 -- `--executor` flag: `evals/scripts/gitapex_run_eval_suite.py`

**Cites ACM row:** "`eval-matrix-hf-gemma4` calls `gitapex_run_eval_suite.py`/
`run_eval_suite()` instead of `nix run .#waza -- run`" and the constraint
row "does not weaken `gitapex_run_ablation.py`'s hermetic-by-default
guarantee; new executor is additive opt-in."

**Quoted Planned ops (verbatim from issue #1259's ACM):** "Edit
`gitapex_run_eval_suite.py`'s `main()`" and, from the constraint row, "No
changes to `gitapex_run_ablation.py`; `gitapex_run_eval_suite.py`'s new
flag is additive."

**Files:** `evals/scripts/gitapex_run_eval_suite.py`,
`tests/test_gitapex_run_eval_suite.py`.

**Steps:**
1. Add `--executor` to `main()`'s `argparse.ArgumentParser`
   (`choices=["claude-cli", "http"]`, `default="claude-cli"`).
2. When `--executor claude-cli` (the default): behavior is byte-for-byte
   unchanged from today -- `executor=subprocess_executor` as it already is.
3. When `--executor http`: read `HTTP_EXECUTOR_BASE_URL`/
   `HTTP_EXECUTOR_API_KEY` from `os.environ`; if either is missing, print
   an `error:` line to stderr (never the value) and return exit code 2
   (malformed-input convention, matching this module's existing
   `ValueError` -> exit-2 mapping) before constructing anything else --
   this validation must run, and fail loud, before any suite executes,
   matching `gitapex_check_copilot_endpoint_configured.py`'s own
   fail-before-run precedent. Construct `HttpExecutorConfig` and call
   `gitapex_run_http_executor.build_http_executor(config)` to get the
   `executor` passed into `run_eval_suite()`. A malformed (not merely
   missing) `HTTP_EXECUTOR_BASE_URL` surfaces the same way (exit 2,
   value never printed).
4. Do not modify `gitapex_run_ablation.py` at all -- confirmed by this
   task's own diff touching only the two files listed above.

**Proof method:** existing `tests/test_gitapex_run_eval_suite.py` cases
covering `main()`/CLI parsing continue passing unmodified (proves the
`claude-cli` default path is unchanged); new cases: `--executor http` with
both env vars set calls `run_eval_suite()` with an executor built from
`gitapex_run_http_executor.build_http_executor` (assert via a monkeypatched
`build_http_executor` that it was called with the right config, avoiding a
real network call); `--executor http` with one or both env vars missing
exits 2 with a stderr message that does not contain the (test-fixture)
secret value; omitting `--executor` entirely still exits identically to
before this change (regression check).

## Task 3 -- Workflow cutover: `.github/workflows/waza-eval-matrix.yml`

**Cites ACM row:** "`eval-matrix-hf-gemma4` calls `gitapex_run_eval_suite.py`/
`run_eval_suite()` instead of `nix run .#waza -- run`," "Does not change
what model this job evaluates (still HF-served Gemma 4, not Claude)," and
the constraint row "does not change the job's model target or its
advisory/manual-only posture."

**Quoted Planned ops (verbatim from issue #1259's ACM):** "Edit
`waza-eval-matrix.yml`'s `eval-matrix-hf-gemma4` job"; "No change to that
env line" (for `HF_GEMMA4_MODEL`); "No change to those fields" (for
`run_hf_gemma4`/timeout/permissions).

**Files:** `.github/workflows/waza-eval-matrix.yml`.

**Steps:**
1. In the `eval-matrix-hf-gemma4` job: remove the `Install Nix` step
   entirely.
2. Change the "Preflight -- require HF Inference Endpoint secrets" step's
   checked env var names from `HF_INFERENCE_ENDPOINT_URL`/`HF_API_TOKEN` to
   match what the job now actually needs downstream -- keep the underlying
   repository secrets (`secrets.HF_INFERENCE_ENDPOINT_URL`/
   `secrets.HF_API_TOKEN`) unchanged, only remap which internal env var
   name they populate, matching the run step's own mapping (next item).
3. Replace the "Run suites against the HF Gemma 4 endpoint" step's
   `nix run .#waza -- run "$skill" ...` loop with the same
   `uv run --frozen python3 evals/scripts/gitapex_run_eval_suite.py
   --eval-yaml "$suite" --skill-md "skills/${skill}/SKILL.md" --executor
   http -o "$out"` plus mean-score-vs-threshold check pattern the
   `eval-matrix` job above it already uses verbatim (same per-suite loop,
   same `gitapex_set_config_model.py` override step kept unchanged, same
   job-summary table shape). Set `env: HTTP_EXECUTOR_BASE_URL: ${{
   secrets.HF_INFERENCE_ENDPOINT_URL }}` and `HTTP_EXECUTOR_API_KEY: ${{
   secrets.HF_API_TOKEN }}` on this step (secret values still never
   printed).
4. Add the `Install uv` step (`astral-sh/setup-uv`, same pinned SHA the
   `eval-matrix` job already uses) to this job, since it no longer installs
   Nix/waza and now needs `uv` instead.
5. Leave `env: HF_GEMMA4_MODEL: google/gemma-4-31B-it`, the
   `run_hf_gemma4` opt-in condition, the 180-minute `timeout-minutes`, and
   `permissions: contents: read` byte-for-byte unchanged.
6. Update this job's own header/step comments to describe the new
   execution path (matching the `eval-matrix` job's own comment style for
   its identical cutover in #1134), rather than leaving comments that
   still describe the old Nix/waza mechanism the diff just removed.

**Proof method:** workflow YAML parses and lints cleanly (`actionlint`/
`zizmor`-equivalent check, or this repository's own `scanning-ci-workflows`
skill if invoked as part of screening); diff review confirms
`HF_GEMMA4_MODEL`, the `run_hf_gemma4` condition, `timeout-minutes: 180`,
and `permissions: contents: read` are byte-identical to the pre-change
file; confirms no `nix run .#waza` or `Install Nix` step remains in this
one job (the `eval-matrix-hf-gemma4` job specifically -- the sibling
`eval-matrix` job's own steps are untouched by this diff). Live dispatch
cannot be exercised in this environment (no HF credentials); this residual
risk is already disclosed in the design doc and issue #1259's own ACM, not
newly introduced here.

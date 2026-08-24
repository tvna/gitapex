# A non-Claude HTTP Executor for the HF Gemma 4 eval-matrix lane

Date: 2026-08-23

Refs [#1259](https://github.com/tvna/gitapex/issues/1259) (child of
[#1130](https://github.com/tvna/gitapex/issues/1130)). Follows on from
[#1134](https://github.com/tvna/gitapex/issues/1134)/[#1132](https://github.com/tvna/gitapex/issues/1132)/[#1157](https://github.com/tvna/gitapex/issues/1157),
which ported every other `nix run .#waza -- run` call site in
`waza-eval-matrix.yml`/`waza-eval-gate.yml` to
`evals/scripts/gitapex_run_eval_suite.py`, deliberately leaving the
`eval-matrix-hf-gemma4` job (issue [#317](https://github.com/tvna/gitapex/issues/317)) on waza/Nix because no
non-Claude `Executor` implementation existed yet.

## Why this doc exists

Issue #1259 is a tracking issue explicitly marked `ACM: not-applicable
(tracking)` -- its own "Next Move" section states a concrete non-Claude
executor design must be scoped, with its own Acceptance Criteria Map,
before implementation. This doc is that design, produced via
`eliciting-a-design` across a multi-round dialogue with the repository
owner.

## Problem

`evals/scripts/gitapex_run_ablation.py`'s `Executor` DI type
(`Callable[[Sequence[str], int], str]` -- argv + timeout in, captured
stdout out) has exactly one implementation, `subprocess_executor`, which
shells out to the `claude` CLI. `waza-eval-matrix.yml`'s
`eval-matrix-hf-gemma4` job still calls `nix run .#waza -- run "$skill"`
to reach a Hugging Face Inference Endpoint serving
`google/gemma-4-31B-it`, because `gitapex_run_eval_suite.py`'s
`run_eval_suite()` has no way to invoke anything but that one Claude-CLI
executor.

## Primary-source finding: waza's own copilot-sdk executor is not a bare HTTP client

Verified this session by cloning `microsoft/waza` (HEAD
`e57f6605ed2ee663e3bda20118784831c53199ac`) and reading
`internal/execution/copilot.go` plus README.md's "Custom Copilot SDK
Providers" section directly, rather than assumed from
`waza-eval-matrix.yml`'s own header comment (which itself already
disclosed this as unverified).

waza's `copilot-sdk` executor launches an embedded **GitHub Copilot CLI
subprocess** through the Copilot SDK (`github/copilot-sdk/go`,
stdio/JSON-RPC transport) and only *that* subprocess makes the real HTTP
call, using a wire format named by `COPILOT_WIRE_API` (`responses` or
`completions`, provider-dependent per the README's own table). BYOK
config (`COPILOT_BASE_URL`/`COPILOT_PROVIDER`/`COPILOT_WIRE_API`/
`COPILOT_API_KEY`/`COPILOT_BEARER_TOKEN`) is assembled by
`providerFromEnv()` and handed to the Copilot SDK, not used directly for
an HTTP call in waza's own Go code.

Consequence for this design: gitapex's new executor does **not** need to
reproduce waza's Copilot-SDK indirection. It calls the HF endpoint
directly over HTTP. This rests on one assumption, disclosed rather than
confirmed (matching the existing workflow header comment's own posture):
that HF's dedicated Inference Endpoint for `google/gemma-4-31B-it`
exposes an OpenAI-Chat-Completions-compatible surface. This cannot be
verified from this environment (no live credentials); it is the same
class of unexecuted assumption the `eval-matrix` job's own waza-executor
premise has carried since issue #106.

## Decision 1: Executor DI integration -- argv adapter, not a new abstraction

**Decision: a new module, `evals/scripts/gitapex_run_http_executor.py`,
adapts the existing argv-shaped `Executor` type -- the type signature
itself does not change.**

`gitapex_run_ablation.build_command()` already produces a fixed argv
shape for every call site in this repository:

```
[model_cli, "-p", <prompt>, "--bare", "--tools", "",
 "--append-system-prompt-file", <skill_md_path>,   # optional
 "--model", <model>]                                # optional
```

The new module's `parse_claude_argv(argv)` extracts the prompt (the
element following `-p`), the system-prompt content (read from the file
path following `--append-system-prompt-file`, when present), and the
model id (the element following `--model`). `--model` absent raises
`ValueError` (a configuration error, not a runtime failure) --
`run_eval_suite()`'s own call to `build_command()` always supplies
`model=suite["config"]["model"]`, a required `eval.yaml` field, so this
path is never exercised by any real committed suite; `--bare`/
`--tools ""` are recognized and ignored (they carry no meaning for an
HTTP chat call). Unrecognized flags are ignored rather than rejected, so
a future `build_command()` addition does not break this parser by
default -- silent tolerance here is deliberate, not an oversight: the
two fields this parser cannot silently ignore (prompt, model) already
fail loud when missing.

**Rejected alternative: a new `PromptExecutor` abstraction**
(`(prompt, system_prompt, model, timeout) -> str`) threaded through both
`gitapex_run_ablation.py` and `gitapex_run_eval_suite.py`. More directly
expressive, but a larger change surface across two already-hermetic,
heavily-commented files, and would require re-verifying the Claude-CLI
path's own hermetic-by-default guarantee is undisturbed. Rejected by the
repository owner in favor of the smaller, additive argv-adapter surface.

## Decision 2: HTTP library -- the official `openai` SDK

**Decision: use the official `openai` Python SDK
(`openai.OpenAI(base_url=..., api_key=...)`,
`client.chat.completions.create(...)`), added as this repository's first
production dependency.**

Core Domain check: calling an OpenAI-Chat-Completions-compatible
endpoint is a Generic Subdomain problem -- no competitive advantage,
well-trodden, low volatility. The off-the-shelf SDK handles request/
response construction, auth headers, and timeout plumbing; hand-rolling
this against `urllib`/`httpx` would just be reimplementing a solved
problem, and the SDK's own base-url override is exactly this design's
custom-provider mechanism (the same override point waza itself needed
Copilot SDK support for).

**Rejected alternative: `httpx`.** Lighter dependency, but requires
hand-writing the Chat Completions request/response shape and its own
error taxonomy. Rejected by the repository owner in favor of the
official SDK.

`pyproject.toml`'s `dependencies` list (currently `[]`) gains one entry.
This is a deliberate, disclosed departure from this repository's
until-now-zero-production-dependency posture -- named explicitly here so
a future reader does not mistake it for drift.

## Decision 3: Executor selection -- explicit CLI flag, not env-var auto-detection

**Decision: `gitapex_run_eval_suite.py` gains `--executor
{claude-cli,http}`, default `claude-cli`.**

Default preserves every existing call site's behavior unchanged (`
eval-matrix` job, `waza-eval-gate.yml`, `scorer-gated-skill-edits`) --
this is additive, not a relaxation of `gitapex_run_ablation.py`'s
existing hermetic-by-default guarantee for the Claude-CLI path.
`--executor http` reads `HTTP_EXECUTOR_BASE_URL`/`HTTP_EXECUTOR_API_KEY`
from the process environment and fails loud, before any suite runs,
if either is missing or `HTTP_EXECUTOR_BASE_URL` is malformed (same
scheme+host rigor as `.github/scripts/gitapex_check_copilot_endpoint_configured.py`'s
own `_CopilotEndpointURL` validator -- reused or mirrored, not
reinvented). Secret values are never printed, matching every existing
preflight in this repository.

**Rejected alternative: environment-variable-presence auto-detection**,
mirroring waza's own `providerFromEnv()` (a base-URL env var being set
silently switches the executor). Consistent with waza's own precedent,
but reads as implicit against issue #1259's own explicit Constraints-
section requirement that "a new non-Claude executor is an additional,
explicit opt-in surface, not a relaxation of the existing allowlist" --
a scoped decision recorded for this one issue, not a standing CLAUDE.md
rule (corrected here: an earlier revision of this section misattributed
the quote to CLAUDE.md, which does not contain this phrase; a `grep`
against the actual file confirms it). Rejected by the repository owner
in favor of the explicit flag.

## Decision 4: PR scope -- full scope, not executor-only

**Decision: this PR implements both the new executor and the
`eval-matrix-hf-gemma4` job's cutover off waza/Nix, in one change.**

Executor-only (deferring the workflow cutover to a follow-up issue) was
considered and rejected: issue #1259's own "Requested outcome" names
both halves, and leaving the job on waza/Nix after the executor exists
would leave the issue itself still open with nothing left to design.

Workflow change: `waza-eval-matrix.yml`'s `eval-matrix-hf-gemma4` job
drops its `Install Nix` step and the `nix run .#waza -- run "$skill"`
loop, replaced by the same `uv run gitapex_run_eval_suite.py` pattern
the `eval-matrix` job (and `waza-eval-gate.yml`) already use, adding
`--executor http`. Its preflight step's checked variables become
`HTTP_EXECUTOR_BASE_URL`/`HTTP_EXECUTOR_API_KEY` (still fed from the
existing `HF_INFERENCE_ENDPOINT_URL`/`HF_API_TOKEN` repository secrets --
only the internal env var names this job maps them to change, not the
secrets themselves). The job's manual-only/opt-in (`run_hf_gemma4`
input) posture, its 180-minute timeout, its `permissions: contents:
read`, and its model target are all unchanged. The mean-score-vs-
threshold check step is reused unmodified from the `eval-matrix` job's
own pattern (same `metrics[]`-length and threshold logic).

## Decision 5: `HF_GEMMA4_MODEL` stays hardcoded in the workflow

**Decision: the job's existing `env: HF_GEMMA4_MODEL:
google/gemma-4-31B-it` stays a literal value in the workflow file,
unchanged from its pre-existing (#317) form -- it does not become a
repository secret or a `workflow_dispatch` input.**

Raised and resolved in dialogue with the repository owner. Reasons:

- Hugging Face's dedicated Inference Endpoint is a fixed
  one-endpoint-one-model resource. Parameterizing only the
  request-level `model` field, without also changing `base_url`, would
  let the recorded `model_id` label (from `to_eval_scores_json()`)
  silently desync from whatever model the endpoint actually serves --
  a mislabelled result, the same failure class
  `gitapex_set_config_model.py`'s own "failed override must not fall
  through" comments already guard against elsewhere in this workflow.
- The model id is not a secret (a public Hugging Face model
  identifier); hiding it behind a repository secret would reduce, not
  improve, this job's own auditability -- a reviewer could no longer
  see what the job evaluates by reading the committed workflow.
- Issue #317's own design intent for this job is to pin one specific,
  deliberately-chosen non-frontier tier, distinct from the sibling
  `eval-matrix` job's genuinely-dynamic `workflow_dispatch.inputs.models`
  (which fans out over several Claude tiers by design). Making this job
  dynamic too would blur that distinction.

A future desire to evaluate a second HF-served model is explicitly a
follow-up (a new `workflow_dispatch` input plus a new, or parameterized,
job), not designed here.

## Facts vs. speculation

Facts: `evals/scripts/gitapex_run_ablation.py`'s `Executor` type and
`build_command()`'s exact argv shape (read directly this session);
`microsoft/waza`'s `internal/execution/copilot.go` and README's BYOK
section (cloned and read directly, HEAD `e57f6605ed2ee663e3bda20118784831c53199ac`);
`pyproject.toml`'s current `dependencies = []`; `waza-eval-matrix.yml`'s
current `eval-matrix-hf-gemma4` job shape (Nix install, `nix run .#waza
-- run`, `HF_GEMMA4_MODEL` env var, 180-minute timeout, `run_hf_gemma4`
opt-in).

Speculation, named as such: that HF's dedicated Inference Endpoint for
`google/gemma-4-31B-it` actually exposes an OpenAI-Chat-Completions-
compatible HTTP surface -- disclosed, not verified, and carried forward
from the existing workflow's own already-disclosed assumption; this
design does not change that assumption's verification status, only which
code path relies on it.

## Non-goals

- Reproducing waza's own Copilot-SDK-via-embedded-CLI indirection --
  this design calls the HF endpoint directly.
- Streaming responses -- neither the existing Claude-CLI executor nor
  the new HTTP executor streams.
- Making `HF_GEMMA4_MODEL` (or any HF model selection) dynamic --
  Decision 5, explicitly deferred to a future issue if ever needed.
- Modifying `gitapex_run_ablation.py`'s own two-arm ablation comparison,
  `eval-matrix` (Claude tier), or `waza-eval-gate.yml` -- none of these
  call sites change `--executor` away from its `claude-cli` default.
- Verifying HF's endpoint wire format live -- no credentials exist in
  this environment to do so; the assumption stays disclosed, not
  resolved, by this design.
- Recognizing an HF-side content-policy-style refusal.
  `gitapex_run_eval_suite.py`'s `_is_content_policy_rejection()` (shared,
  unmodified by this design) matches only two Anthropic-specific text
  markers ("can't help with this", "anthropic.com/legal/aup") found
  empirically against a live Claude CLI rejection (issue #1183) -- an
  equivalent refusal from the HF Gemma 4 endpoint will not match either
  marker, so it surfaces as a full `RuntimeError` that aborts the whole
  suite, rather than the per-fixture skip a matching Claude-CLI refusal
  gets. This is a safe failure mode (loud abort, not a silent pass), not
  a correctness bug, but the two `Executor` paths are not behaviorally
  symmetric here -- named explicitly (adversarial-review finding) rather
  than left implicit. Building an HF-side equivalent is out of this
  design's scope; a future design can add one if a live dispatch shows
  it is needed.

## Acceptance criteria

- [ ] `evals/scripts/gitapex_run_http_executor.py` exists, parses the
      argv shape `build_command()` produces (prompt / system-prompt-file
      contents / model), and exposes a factory returning an `Executor`-
      typed callable that calls an OpenAI-Chat-Completions-compatible
      endpoint via the official `openai` SDK.
- [ ] A missing `--model` in argv raises `ValueError`, not a runtime
      failure; SDK-level failures (auth, network, non-2xx, timeout)
      surface as `RuntimeError` so `gitapex_run_ablation.redact_executor_failure_reason`'s
      existing type-based redaction covers this path without new code.
- [ ] `gitapex_run_eval_suite.py` gains `--executor {claude-cli,http}`
      (default `claude-cli`); every existing call site's behavior is
      unchanged when the flag is omitted.
- [ ] `--executor http` validates `HTTP_EXECUTOR_BASE_URL`/
      `HTTP_EXECUTOR_API_KEY` before any suite runs, fails loud (never
      printing the secret value) if either is missing or the base URL
      is malformed.
- [ ] `pyproject.toml` declares `openai` as a production dependency,
      with the departure from this repository's prior zero-dependency
      posture stated in the PR, not silently introduced.
- [ ] `waza-eval-matrix.yml`'s `eval-matrix-hf-gemma4` job no longer
      installs Nix or calls `nix run .#waza`; it calls
      `gitapex_run_eval_suite.py --executor http` per suite, matching
      the `eval-matrix` job's own uv-run/threshold-check pattern.
      `HF_GEMMA4_MODEL` remains a literal in the workflow file
      (Decision 5). The job's opt-in trigger, timeout, and permissions
      are unchanged.
- [ ] Unit tests cover `gitapex_run_http_executor.py`'s argv parsing and
      its executor factory against a mocked `openai` client -- no live
      HF credentials are required or assumed by the test suite.

## Related Issue

Child of [#1130](https://github.com/tvna/gitapex/issues/1130). Follows
[#1134](https://github.com/tvna/gitapex/issues/1134)/[#1132](https://github.com/tvna/gitapex/issues/1132)/[#1157](https://github.com/tvna/gitapex/issues/1157).
Resolves [#1259](https://github.com/tvna/gitapex/issues/1259).

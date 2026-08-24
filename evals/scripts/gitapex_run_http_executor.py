"""Non-Claude HTTP ``Executor`` for an OpenAI/Copilot-compatible chat
endpoint (issue #1259).

Before this module, ``evals/scripts/gitapex_run_ablation.py``'s ``Executor``
DI type (``Callable[[Sequence[str], int], str]``, argv+timeout in,
captured stdout out) had exactly one implementation --
``subprocess_executor``, a ``claude`` CLI subprocess. ``waza-eval-matrix.yml``'s
``eval-matrix-hf-gemma4`` job still called ``nix run .#waza -- run`` to
reach a Hugging Face Inference Endpoint because no non-Claude ``Executor``
existed. This module is that second implementation.

**Argv adapter, not a new abstraction.** The ``Executor`` type itself does
not change. ``gitapex_run_ablation.build_command()`` already produces a
fixed argv shape for every call site in this repository:
``[model_cli, "-p", <prompt>, "--bare", "--tools", "",
"--append-system-prompt-file", <path>, "--model", <model>]`` (the last two
pairs optional). ``parse_claude_argv`` extracts the three fields this
module actually needs from that shape and ignores every other flag
(``--bare``/``--tools ""`` carry no meaning for an HTTP chat call; a
future ``build_command()`` addition this parser does not recognize is
silently skipped, not rejected -- only a missing ``-p``/``--model`` fails
loud, since those are the two fields this module cannot function
without).

**Primary-source finding this design rests on (design doc
``docs/superpowers/specs/2026-08-23-hf-gemma4-http-executor-design.md``):**
waza's own ``copilot-sdk`` executor does not make a bare HTTP call itself
-- it launches an embedded GitHub Copilot CLI subprocess via the Copilot
SDK (stdio/JSON-RPC), and that embedded CLI is what makes the real HTTP
call, in a wire format (``COPILOT_WIRE_API`` -- ``responses`` or
``completions``, provider-dependent) neither waza's own Go code nor this
module needs to reproduce. This module calls the target endpoint directly
via the official ``openai`` SDK (a Core Domain check judged
OpenAI-compatible chat calling a Generic Subdomain -- adopt the
off-the-shelf SDK rather than hand-roll request/response parsing), resting
on one disclosed, unverified-in-this-environment assumption: that the
target endpoint exposes an OpenAI-Chat-Completions-compatible surface.

**Error contract matches ``subprocess_executor`` exactly.** Every
``openai`` SDK exception (auth, connection, timeout, non-2xx status) is
caught and re-raised as ``RuntimeError`` -- never a bespoke exception type
-- so ``gitapex_run_ablation.redact_executor_failure_reason``'s existing
type-based dispatch (``RuntimeError``/``subprocess.TimeoutExpired`` ->
redacted; anything else -> passed through) already protects this path
with zero new code in that module. A malformed argv (missing ``-p`` or
``--model``) raises ``ValueError`` instead -- a configuration error, not a
runtime failure, matching this repository's own malformed-input-vs-
execution-failure convention (``gitapex_run_ablation.py``'s own module
docstring, "Exit code contract" section).

**Base-URL validation mirrors, rather than imports,**
``.github/scripts/gitapex_check_copilot_endpoint_configured.py``'s own
``_CopilotEndpointURL`` validator (scheme+host required, no raw
control character, no whitespace in the host) -- reimplemented locally
rather than imported across the ``.github/scripts``/``evals/scripts``
boundary, to keep this module's own import surface to what
``pyproject.toml``'s ``pythonpath``/``uv run`` invocation already
guarantees without a new cross-directory ``sys.path`` bootstrap.

Usage (imported, not run standalone -- ``evals/scripts/gitapex_run_eval_suite.py``'s
``--executor http`` flag is this module's only real caller)::

    from gitapex_run_http_executor import HttpExecutorConfig, build_http_executor
    executor = build_http_executor(HttpExecutorConfig(base_url=..., api_key=...))
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import gitapex_run_ablation
import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ConfigDict, field_validator


@dataclass(frozen=True)
class ParsedInvocation:
    """The three fields this module needs out of a ``build_command()``-shaped
    argv: the prompt, an optional system-prompt (the contents of the file
    named by ``--append-system-prompt-file``, when present), and the model
    id."""

    prompt: str
    system_prompt: str | None
    model: str


def parse_claude_argv(argv: Sequence[str]) -> ParsedInvocation:
    """Extract ``prompt``/``system_prompt``/``model`` from a
    ``gitapex_run_ablation.build_command()``-shaped argv.

    Raises ``ValueError`` if ``-p`` (the prompt) or ``--model`` is absent --
    both are required for this module's own HTTP call to mean anything --
    or if the path following ``--append-system-prompt-file`` cannot be read
    (missing, a directory, unreadable, or not valid UTF-8 -- every such
    failure converts to ``ValueError``, never left to propagate as a raw
    ``OSError``/``UnicodeDecodeError``). Every other flag (``--bare``,
    ``--tools``, its ``""`` value, and any flag this parser does not
    recognize) is silently skipped, not rejected -- see module docstring.
    """
    argv = list(argv)
    prompt: str | None = None
    system_prompt: str | None = None
    model: str | None = None

    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag == "-p" and i + 1 < len(argv):
            prompt = argv[i + 1]
            i += 2
            continue
        if flag == "--append-system-prompt-file" and i + 1 < len(argv):
            system_prompt_path = argv[i + 1]
            try:
                system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError(f"cannot read --append-system-prompt-file {system_prompt_path!r}: {exc}") from exc
            i += 2
            continue
        if flag == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
            i += 2
            continue
        i += 1

    if prompt is None:
        raise ValueError("argv is missing -p (the prompt)")
    if model is None:
        raise ValueError("argv is missing --model")

    return ParsedInvocation(prompt=prompt, system_prompt=system_prompt, model=model)


def _reject_raw_control_characters(value: str, field: str) -> None:
    """Raise ``ValueError`` if ``value`` contains a raw C0 control character
    or DEL. Shared by ``HttpExecutorConfig``'s two field validators
    (reuse/simplification-review finding: the predicate was duplicated
    byte-for-byte between them) so a future refinement to this rule cannot
    be applied to one field and silently missed on the other."""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValueError(f"{field} contains a raw C0 control character or DEL")


class HttpExecutorConfig(BaseModel):
    """Validated configuration for ``build_http_executor``.

    ``base_url`` validation mirrors
    ``.github/scripts/gitapex_check_copilot_endpoint_configured.py``'s own
    ``_CopilotEndpointURL`` (scheme+host required, no raw C0 control
    character or DEL, no whitespace in the host) -- see module docstring
    for why this is reimplemented locally rather than imported.

    ``api_key`` gets the same raw-control-character/DEL rejection as
    ``base_url`` (code-review finding): it flows into the ``Authorization``
    header ``build_http_executor`` sends on every call, and this
    environment's own installed transport (``httpx2``, the ``openai`` SDK's
    own HTTP client) does NOT itself reject an embedded CR/LF in a header
    value at request-construction time (confirmed against that library's
    own source/behavior directly) -- an unvalidated ``api_key`` is this
    module's own header-injection surface into that request, not just an
    auth-failure risk. In this repository's own real call site
    (``.github/workflows/waza-eval-matrix.yml``'s ``eval-matrix-hf-gemma4``
    job) the value only ever originates from a repository secret, not
    attacker-controlled input, so this is defense-in-depth, not a fix for
    an exploited path -- kept anyway per CLAUDE.md section 4's own
    "preserve defense-in-depth" rule and to close the asymmetry with
    ``base_url``'s own identical-shaped check just above.
    """

    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: str

    @field_validator("base_url")
    @classmethod
    def _base_url_must_be_well_formed(cls, value: str) -> str:
        _reject_raw_control_characters(value, "base_url")
        parts = urlsplit(value)
        hostname = parts.hostname
        if not parts.scheme or not hostname:
            raise ValueError("base_url is missing a scheme or a host")
        if any(ch.isspace() for ch in hostname):
            raise ValueError("base_url host contains whitespace")
        return value

    @field_validator("api_key")
    @classmethod
    def _api_key_must_not_contain_control_characters(cls, value: str) -> str:
        _reject_raw_control_characters(value, "api_key")
        return value


def build_http_executor(config: HttpExecutorConfig) -> gitapex_run_ablation.Executor:
    """Return an ``Executor``-typed callable (``(argv, timeout) -> str``)
    backed by the official ``openai`` SDK, pointed at ``config.base_url``
    via a custom-provider ``base_url`` override.

    A missing ``-p``/``--model`` in ``argv`` propagates ``parse_claude_argv``'s
    own ``ValueError`` unchanged (a configuration error). Every ``openai``
    SDK exception converts to ``RuntimeError`` -- see module docstring's
    "Error contract" section for why this, not a bespoke exception type,
    is what makes ``gitapex_run_ablation.redact_executor_failure_reason``
    cover this path for free. A response with zero ``choices`` (SDK-valid
    but semantically empty -- distinct from a MISSING ``choices`` field,
    which the SDK's own response validation already rejects as an
    ``OpenAIError``) converts to that same ``RuntimeError`` too, rather
    than raising a raw ``IndexError`` no caller in this call chain catches.

    ``max_retries=0`` (adversarial-review finding): the ``openai`` SDK
    retries a timeout or connection failure up to its own default
    ``max_retries=2`` more times, each attempt separately bounded by
    ``timeout`` but with no bound on their sum -- confirmed live against
    this environment's installed SDK, a non-responding endpoint took
    ~3.8x the requested ``timeout`` to finally raise. ``subprocess_executor``
    (this module's sibling ``Executor`` implementation) has no such
    multiplier -- ``subprocess.run(..., timeout=timeout)`` is a single
    attempt, a hard bound. ``max_retries=0`` restores that same
    single-attempt, ``timeout``-is-a-hard-bound semantics here.
    """

    def _execute(argv: Sequence[str], timeout: int) -> str:
        parsed = parse_claude_argv(argv)

        messages: list[ChatCompletionMessageParam] = []
        if parsed.system_prompt is not None:
            messages.append({"role": "system", "content": parsed.system_prompt})
        messages.append({"role": "user", "content": parsed.prompt})

        client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key, max_retries=0)
        try:
            response = client.chat.completions.create(
                model=parsed.model,
                messages=messages,
                timeout=timeout,
            )
            # ``ChatCompletion.choices`` is a required field, but its own
            # declared type (``list[Choice]``) permits an empty list --
            # confirmed against this environment's own installed ``openai``
            # SDK: ``ChatCompletion(choices=[], ...)`` passes the SDK's own
            # response validation without raising (only a MISSING `choices`
            # key raises ``APIResponseValidationError``, already an
            # ``OpenAIError`` subclass the except clause below catches). An
            # OpenAI-compatible endpoint returning zero choices (a real,
            # not just theoretical, third-party-compatibility gap given
            # this module's own disclosed "unverified-in-this-environment"
            # assumption) would otherwise reach ``response.choices[0]``
            # below and raise a raw ``IndexError`` that escapes this
            # function's -- and, in turn, ``run_eval_suite()``'s and
            # ``main()``'s -- documented "every openai SDK exception
            # converts to RuntimeError" contract entirely uncaught.
            if not response.choices:
                raise RuntimeError("HTTP executor call failed: response contained zero choices")
        except (openai.OpenAIError, OSError) as exc:
            # OSError covers ConnectionError (its own subclass) and any
            # lower-level socket failure the openai SDK does not itself
            # wrap in an OpenAIError subclass.
            raise RuntimeError(f"HTTP executor call failed: {exc}") from exc

        content = response.choices[0].message.content
        return content if content is not None else ""

    return _execute

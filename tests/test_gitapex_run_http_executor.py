"""Tests for evals/scripts/gitapex_run_http_executor.py (issue #1259).

Covers ``parse_claude_argv`` (the argv-adapter that extracts prompt/
system-prompt/model from the fixed argv shape
``gitapex_run_ablation.build_command()`` produces), ``HttpExecutorConfig``'s
base-URL validation (mirroring
``.github/scripts/gitapex_check_copilot_endpoint_configured.py``'s own
scheme+host+control-character checks), and ``build_http_executor``'s
returned callable against a mocked ``openai`` client -- no live HF/OpenAI
credentials are required or assumed anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import gitapex_run_http_executor as http_executor
import pytest
from pydantic import ValidationError


def _config() -> http_executor.HttpExecutorConfig:
    return http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="secret")


def _mock_client(monkeypatch: pytest.MonkeyPatch, *, response_content: str | None = None) -> MagicMock:
    """Patch ``openai.OpenAI`` to return a ``MagicMock`` client. When
    ``response_content`` is given, ``chat.completions.create`` returns a
    response whose ``choices[0].message.content`` is that string; otherwise
    the caller configures ``create`` itself (e.g. a ``side_effect`` or a
    different ``return_value``)."""
    mock_client = MagicMock()
    if response_content is not None:
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=response_content))]
        )
    monkeypatch.setattr(http_executor.openai, "OpenAI", MagicMock(return_value=mock_client))
    return mock_client


# ---------------------------------------------------------------------------
# parse_claude_argv
# ---------------------------------------------------------------------------


def test_parse_claude_argv_full_argv_extracts_prompt_system_prompt_and_model(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("You are a helpful skill.", encoding="utf-8")
    argv = [
        "claude",
        "-p",
        "hello world",
        "--bare",
        "--tools",
        "",
        "--append-system-prompt-file",
        str(skill_md),
        "--model",
        "claude-sonnet-5",
    ]
    parsed = http_executor.parse_claude_argv(argv)
    assert parsed.prompt == "hello world"
    assert parsed.system_prompt == "You are a helpful skill."
    assert parsed.model == "claude-sonnet-5"


def test_parse_claude_argv_without_system_prompt_file_leaves_it_none() -> None:
    argv = ["claude", "-p", "hello", "--bare", "--tools", "", "--model", "claude-sonnet-5"]
    parsed = http_executor.parse_claude_argv(argv)
    assert parsed.prompt == "hello"
    assert parsed.system_prompt is None
    assert parsed.model == "claude-sonnet-5"


def test_parse_claude_argv_missing_model_raises_value_error() -> None:
    argv = ["claude", "-p", "hello", "--bare", "--tools", ""]
    with pytest.raises(ValueError, match="--model"):
        http_executor.parse_claude_argv(argv)


def test_parse_claude_argv_unrecognized_flags_are_ignored(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("system text", encoding="utf-8")
    argv = [
        "claude",
        "-p",
        "hi",
        "--bare",
        "--tools",
        "",
        "--some-future-flag",
        "value",
        "--append-system-prompt-file",
        str(skill_md),
        "--model",
        "m",
    ]
    parsed = http_executor.parse_claude_argv(argv)
    assert parsed.prompt == "hi"
    assert parsed.system_prompt == "system text"
    assert parsed.model == "m"


def test_parse_claude_argv_missing_prompt_raises_value_error() -> None:
    argv = ["claude", "--bare", "--tools", "", "--model", "m"]
    with pytest.raises(ValueError, match="-p"):
        http_executor.parse_claude_argv(argv)


def test_parse_claude_argv_non_utf8_system_prompt_file_raises_value_error_not_unicode_decode_error(
    tmp_path: Path,
) -> None:
    # Defeat test (exception-handler-gaps finding): read_text(encoding="utf-8")
    # raises UnicodeDecodeError on non-UTF-8 bytes -- this must be caught
    # and converted, never left to propagate as a raw, unhandled failure.
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_bytes(b"\xff\xfe\x00\x01not valid utf-8")
    argv = ["claude", "-p", "hi", "--append-system-prompt-file", str(skill_md), "--model", "m"]
    with pytest.raises(ValueError, match="cannot read --append-system-prompt-file"):
        http_executor.parse_claude_argv(argv)


def test_parse_claude_argv_missing_system_prompt_file_raises_value_error_not_os_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"
    argv = ["claude", "-p", "hi", "--append-system-prompt-file", str(missing), "--model", "m"]
    with pytest.raises(ValueError, match="cannot read --append-system-prompt-file"):
        http_executor.parse_claude_argv(argv)


# ---------------------------------------------------------------------------
# HttpExecutorConfig
# ---------------------------------------------------------------------------


def test_http_executor_config_valid_https_url_accepted() -> None:
    config = http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="secret")
    assert config.base_url == "https://example.com"


@pytest.mark.parametrize(
    "value",
    [
        "example.com",  # no scheme
        "https://",  # scheme but no host
        "/just/a/path",  # neither scheme nor host
        "   ",  # whitespace only
        "https://example.invalid/\npath",  # embedded control character
        "https://example.com   ",  # trailing whitespace host-adjacent
    ],
)
def test_http_executor_config_malformed_base_url_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        http_executor.HttpExecutorConfig(base_url=value, api_key="secret")


@pytest.mark.parametrize(
    "value",
    [
        "secret\r\nX-Injected: 1",  # CRLF header-injection shape
        "secret\nkey",  # bare LF
        "secret\x00key",  # NUL
        "secret\x7fkey",  # DEL
    ],
)
def test_http_executor_config_api_key_with_control_character_rejected(value: str) -> None:
    # Regression (code review finding): api_key flows straight into the
    # Authorization header build_http_executor sends -- this environment's
    # own installed transport (httpx2, the openai SDK's own HTTP client)
    # does not itself reject an embedded CR/LF in a header value at
    # request-construction time, so an unvalidated api_key is a
    # header-injection surface, not just an auth-failure risk. Mirrors
    # base_url's own identical-shaped control-character check just above.
    with pytest.raises(ValidationError):
        http_executor.HttpExecutorConfig(base_url="https://example.com", api_key=value)


def test_http_executor_config_api_key_without_control_characters_accepted() -> None:
    config = http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="sk-a-normal-token-9f3a")
    assert config.api_key == "sk-a-normal-token-9f3a"


def test_http_executor_config_empty_api_key_rejected() -> None:
    # Defeat test (adversarial-review finding): base_url's own validator
    # already implicitly rejects an empty string (missing scheme/host), but
    # api_key had no equivalent -- an empty api_key would reach
    # openai.OpenAI(api_key="") and raise a raw openai.OpenAIError at CLIENT
    # CONSTRUCTION time, before build_http_executor's own try/except is even
    # entered, breaking this module's documented "every openai SDK
    # exception converts to RuntimeError" contract.
    with pytest.raises(ValidationError, match="api_key must not be empty"):
        http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="")


# ---------------------------------------------------------------------------
# build_http_executor
# ---------------------------------------------------------------------------


def test_build_http_executor_successful_call_returns_message_content(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = _mock_client(monkeypatch, response_content="the answer")

    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "what is 2+2", "--bare", "--tools", "", "--model", "gemma-4"]
    result = executor(argv, 60)

    assert result == "the answer"
    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["model"] == "gemma-4"
    assert kwargs["timeout"] == 60
    assert kwargs["messages"][-1] == {"role": "user", "content": "what is 2+2"}


def test_build_http_executor_system_prompt_included_as_system_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("be helpful", encoding="utf-8")
    mock_client = _mock_client(monkeypatch, response_content="ok")

    executor = http_executor.build_http_executor(_config())
    argv = [
        "claude",
        "-p",
        "hi",
        "--bare",
        "--tools",
        "",
        "--append-system-prompt-file",
        str(skill_md),
        "--model",
        "gemma-4",
    ]
    executor(argv, 30)

    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["messages"][0] == {"role": "system", "content": "be helpful"}


def test_build_http_executor_sdk_exception_converts_to_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = _mock_client(monkeypatch)
    mock_client.chat.completions.create.side_effect = ConnectionError("boom, sensitive detail")

    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
    with pytest.raises(RuntimeError):
        executor(argv, 30)


def test_build_http_executor_missing_model_in_argv_raises_value_error_not_runtime_error() -> None:
    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "hi", "--bare", "--tools", ""]
    with pytest.raises(ValueError):
        executor(argv, 30)


def test_build_http_executor_zero_choices_response_raises_runtime_error_not_index_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Defeat test (adversarial-review finding): ChatCompletion.choices is
    # SDK-valid as an empty list -- only a MISSING choices key raises
    # OpenAIError. An OpenAI-compatible endpoint returning zero choices
    # must not reach response.choices[0] and raise a raw, uncaught
    # IndexError -- it must convert to this module's own RuntimeError
    # contract like every other executor failure.
    mock_client = _mock_client(monkeypatch)
    mock_client.chat.completions.create.return_value = MagicMock(choices=[])

    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
    with pytest.raises(RuntimeError):
        executor(argv, 30)


def test_build_http_executor_constructs_openai_client_with_max_retries_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression (adversarial-review finding): the openai SDK's own default
    # max_retries=2 retries a timeout/connection failure up to 2 more times,
    # each attempt separately bounded by `timeout` but with no bound on
    # their sum -- confirmed live against this environment's installed SDK,
    # a non-responding endpoint took ~3.8x the requested timeout to finally
    # raise. subprocess_executor (this module's sibling Executor
    # implementation) has no such multiplier: subprocess.run(...,
    # timeout=timeout) is a single attempt, a hard bound. max_retries=0
    # restores that same single-attempt, timeout-is-a-hard-bound semantics.
    mock_openai_class = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(http_executor.openai, "OpenAI", mock_openai_class)
    mock_openai_class.return_value.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="ok"))]
    )

    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
    executor(argv, 30)

    _, kwargs = mock_openai_class.call_args
    assert kwargs["max_retries"] == 0


def test_build_http_executor_reuses_one_openai_client_across_multiple_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression (adversarial-review finding): the openai.OpenAI client used
    # to be constructed fresh inside _execute on every call, discarding
    # HTTP connection/TLS reuse for no benefit -- run_eval_suite() calls the
    # returned Executor once per trial, up to trials_per_task times per
    # fixture, so a per-call client is a real, not just theoretical, cost.
    # build_http_executor() now constructs the client once, outside the
    # returned closure; openai.OpenAI() must therefore be called exactly
    # once total, no matter how many times the returned executor is called.
    mock_openai_class = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(http_executor.openai, "OpenAI", mock_openai_class)
    mock_openai_class.return_value.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="ok"))]
    )

    executor = http_executor.build_http_executor(_config())
    argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
    executor(argv, 30)
    executor(argv, 30)
    executor(argv, 30)

    assert mock_openai_class.call_count == 1
    assert mock_openai_class.return_value.chat.completions.create.call_count == 3

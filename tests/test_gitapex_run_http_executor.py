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


class TestParseClaudeArgv:
    def test_full_argv_extracts_prompt_system_prompt_and_model(self, tmp_path: Path) -> None:
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

    def test_argv_without_system_prompt_file_leaves_it_none(self) -> None:
        argv = ["claude", "-p", "hello", "--bare", "--tools", "", "--model", "claude-sonnet-5"]
        parsed = http_executor.parse_claude_argv(argv)
        assert parsed.prompt == "hello"
        assert parsed.system_prompt is None
        assert parsed.model == "claude-sonnet-5"

    def test_missing_model_raises_value_error(self) -> None:
        argv = ["claude", "-p", "hello", "--bare", "--tools", ""]
        with pytest.raises(ValueError, match="--model"):
            http_executor.parse_claude_argv(argv)

    def test_unrecognized_flags_are_ignored(self, tmp_path: Path) -> None:
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

    def test_missing_prompt_raises_value_error(self) -> None:
        argv = ["claude", "--bare", "--tools", "", "--model", "m"]
        with pytest.raises(ValueError, match="-p"):
            http_executor.parse_claude_argv(argv)

    def test_non_utf8_system_prompt_file_raises_value_error_not_unicode_decode_error(self, tmp_path: Path) -> None:
        # Defeat test (exception-handler-gaps finding): read_text(encoding="utf-8")
        # raises UnicodeDecodeError on non-UTF-8 bytes -- this must be caught
        # and converted, never left to propagate as a raw, unhandled failure.
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_bytes(b"\xff\xfe\x00\x01not valid utf-8")
        argv = ["claude", "-p", "hi", "--append-system-prompt-file", str(skill_md), "--model", "m"]
        with pytest.raises(ValueError, match="cannot read --append-system-prompt-file"):
            http_executor.parse_claude_argv(argv)

    def test_missing_system_prompt_file_raises_value_error_not_os_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.md"
        argv = ["claude", "-p", "hi", "--append-system-prompt-file", str(missing), "--model", "m"]
        with pytest.raises(ValueError, match="cannot read --append-system-prompt-file"):
            http_executor.parse_claude_argv(argv)


class TestHttpExecutorConfig:
    def test_valid_https_url_accepted(self) -> None:
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
    def test_malformed_base_url_rejected(self, value: str) -> None:
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
    def test_api_key_with_control_character_rejected(self, value: str) -> None:
        # Regression (code review finding): api_key flows straight into the
        # Authorization header build_http_executor sends -- this
        # environment's own installed transport (httpx2, the openai SDK's
        # own HTTP client) does not itself reject an embedded CR/LF in a
        # header value at request-construction time, so an unvalidated
        # api_key is a header-injection surface, not just an auth-failure
        # risk. Mirrors base_url's own identical-shaped control-character
        # check just above.
        with pytest.raises(ValidationError):
            http_executor.HttpExecutorConfig(base_url="https://example.com", api_key=value)

    def test_api_key_without_control_characters_accepted(self) -> None:
        config = http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="sk-a-normal-token-9f3a")
        assert config.api_key == "sk-a-normal-token-9f3a"


class TestBuildHttpExecutor:
    def _config(self) -> http_executor.HttpExecutorConfig:
        return http_executor.HttpExecutorConfig(base_url="https://example.com", api_key="secret")

    def _mock_client(self, monkeypatch: pytest.MonkeyPatch, *, response_content: str | None = None) -> MagicMock:
        """Patch ``openai.OpenAI`` to return a ``MagicMock`` client. When
        ``response_content`` is given, ``chat.completions.create`` returns a
        response whose ``choices[0].message.content`` is that string;
        otherwise the caller configures ``create`` itself (e.g. a
        ``side_effect``)."""
        mock_client = MagicMock()
        if response_content is not None:
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=response_content))]
            )
        monkeypatch.setattr(http_executor.openai, "OpenAI", MagicMock(return_value=mock_client))
        return mock_client

    def test_successful_call_returns_message_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_client = self._mock_client(monkeypatch, response_content="the answer")

        executor = http_executor.build_http_executor(self._config())
        argv = ["claude", "-p", "what is 2+2", "--bare", "--tools", "", "--model", "gemma-4"]
        result = executor(argv, 60)

        assert result == "the answer"
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "gemma-4"
        assert kwargs["timeout"] == 60
        assert kwargs["messages"][-1] == {"role": "user", "content": "what is 2+2"}

    def test_system_prompt_included_as_system_message(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("be helpful", encoding="utf-8")
        mock_client = self._mock_client(monkeypatch, response_content="ok")

        executor = http_executor.build_http_executor(self._config())
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

    def test_sdk_exception_converts_to_runtime_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_client = self._mock_client(monkeypatch)
        mock_client.chat.completions.create.side_effect = ConnectionError("boom, sensitive detail")

        executor = http_executor.build_http_executor(self._config())
        argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
        with pytest.raises(RuntimeError):
            executor(argv, 30)

    def test_missing_model_in_argv_raises_value_error_not_runtime_error(self) -> None:
        executor = http_executor.build_http_executor(self._config())
        argv = ["claude", "-p", "hi", "--bare", "--tools", ""]
        with pytest.raises(ValueError):
            executor(argv, 30)

    def test_zero_choices_response_raises_runtime_error_not_index_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Defeat test (adversarial-review finding): ChatCompletion.choices is
        # SDK-valid as an empty list -- only a MISSING choices key raises
        # OpenAIError. An OpenAI-compatible endpoint returning zero choices
        # must not reach response.choices[0] and raise a raw, uncaught
        # IndexError -- it must convert to this module's own RuntimeError
        # contract like every other executor failure.
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(choices=[])
        monkeypatch.setattr(http_executor.openai, "OpenAI", MagicMock(return_value=mock_client))

        executor = http_executor.build_http_executor(self._config())
        argv = ["claude", "-p", "hi", "--bare", "--tools", "", "--model", "gemma-4"]
        with pytest.raises(RuntimeError):
            executor(argv, 30)

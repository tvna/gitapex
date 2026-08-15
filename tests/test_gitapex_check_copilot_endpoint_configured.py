"""Tests for the shared copilot-sdk endpoint preflight
(.github/scripts/gitapex_check_copilot_endpoint_configured.py).

Issue #124: waza-eval-matrix.yml and waza-eval-gate.yml previously each
carried their own copy of the same bash ``-z`` check. These tests cover the
Python replacement's env-var precedence (matching waza's own envFirst()),
its URL-validity check (matching waza's own providerHost()), and the
never-echo-the-value contract on both the error and success paths.
"""

from __future__ import annotations

import gitapex_check_copilot_endpoint_configured as preflight
import pytest

SENTINEL_URL = "https://sentinel-value-must-never-leak.example.invalid/path"


def test_neither_set_raises_not_configured() -> None:
    with pytest.raises(preflight.EndpointNotConfigured):
        preflight.check({})


def test_both_empty_string_raises_not_configured() -> None:
    with pytest.raises(preflight.EndpointNotConfigured):
        preflight.check({"COPILOT_BASE_URL": "", "COPILOT_PROVIDER_BASE_URL": ""})


def test_only_short_name_set_valid_url_passes() -> None:
    assert preflight.check({"COPILOT_BASE_URL": "https://example.com"}) == "COPILOT_BASE_URL"


def test_only_long_alias_set_valid_url_passes() -> None:
    assert preflight.check({"COPILOT_PROVIDER_BASE_URL": "https://example.com"}) == "COPILOT_PROVIDER_BASE_URL"


def test_both_set_short_name_wins() -> None:
    # Both are individually valid URLs; envFirst()'s own documented order
    # (short canonical name first) must decide, not e.g. alphabetical order
    # or "whichever is checked last wins".
    env = {
        "COPILOT_BASE_URL": "https://short.example",
        "COPILOT_PROVIDER_BASE_URL": "https://long.example",
    }
    assert preflight.check(env) == "COPILOT_BASE_URL"


def test_short_name_empty_falls_back_to_long_alias() -> None:
    env = {"COPILOT_BASE_URL": "", "COPILOT_PROVIDER_BASE_URL": "https://example.com"}
    assert preflight.check(env) == "COPILOT_PROVIDER_BASE_URL"


@pytest.mark.parametrize(
    "value",
    [
        "example.com",  # no scheme
        "https://",  # scheme but no host
        "/just/a/path",  # neither scheme nor host
        "   ",  # whitespace only
    ],
)
def test_malformed_values_raise_malformed(value: str) -> None:
    with pytest.raises(preflight.EndpointMalformed) as exc_info:
        preflight.check({"COPILOT_BASE_URL": value})
    assert exc_info.value.var_name == "COPILOT_BASE_URL"


def test_malformed_names_the_long_alias_when_that_is_the_one_set() -> None:
    with pytest.raises(preflight.EndpointMalformed) as exc_info:
        preflight.check({"COPILOT_PROVIDER_BASE_URL": "not-a-url"})
    assert exc_info.value.var_name == "COPILOT_PROVIDER_BASE_URL"


def test_valid_url_with_port_and_path_passes() -> None:
    # A realistic self-hosted endpoint shape: scheme + host + port + path.
    assert preflight.check({"COPILOT_BASE_URL": "https://gateway.internal:8443/v1"}) == "COPILOT_BASE_URL"


def test_main_success_never_prints_the_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_BASE_URL", SENTINEL_URL)
    monkeypatch.delenv("COPILOT_PROVIDER_BASE_URL", raising=False)
    assert preflight.main([]) == 0
    captured = capsys.readouterr()
    assert SENTINEL_URL not in captured.out
    assert SENTINEL_URL not in captured.err
    assert "COPILOT_BASE_URL" in captured.out


def test_main_not_configured_exit_code_and_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("COPILOT_BASE_URL", raising=False)
    monkeypatch.delenv("COPILOT_PROVIDER_BASE_URL", raising=False)
    assert preflight.main([]) == 1
    captured = capsys.readouterr()
    assert "::error::" in captured.err
    assert "#124" in captured.err


def test_main_malformed_exit_code_and_no_value_leak(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COPILOT_BASE_URL", SENTINEL_URL.replace("https://", "not-a-scheme "))
    monkeypatch.delenv("COPILOT_PROVIDER_BASE_URL", raising=False)
    assert preflight.main([]) == 1
    captured = capsys.readouterr()
    assert "::error::" in captured.err
    assert "COPILOT_BASE_URL" in captured.err
    assert "sentinel-value-must-never-leak" not in captured.err
    assert "sentinel-value-must-never-leak" not in captured.out

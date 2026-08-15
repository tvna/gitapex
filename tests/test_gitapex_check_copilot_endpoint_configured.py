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


def test_malformed_exception_does_not_chain_the_pydantic_validation_error() -> None:
    # pydantic's own ValidationError embeds the raw invalid value in its
    # str()/repr()/errors() alike. validate_base_url uses `raise ... from
    # None` specifically so that value never survives on __cause__ -- a
    # plain `from exc` would still pass every other test here (nothing
    # else prints a traceback today) while leaving a live secret-leak
    # trap for whatever caller adds one next. Assert the suppression
    # directly rather than relying on no test ever printing a traceback.
    with pytest.raises(preflight.EndpointMalformed) as exc_info:
        preflight.validate_base_url("COPILOT_BASE_URL", SENTINEL_URL.replace("https://", ""))
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    # Belt-and-suspenders: even a full traceback render of the raised
    # exception (what an uncaught propagation or a future `logging.exception`
    # call would produce) must not surface the sentinel.
    import traceback

    rendered = "".join(traceback.format_exception(type(exc_info.value), exc_info.value, exc_info.tb))
    assert "sentinel-value-must-never-leak" not in rendered


# Defeat tests (issue #124's own disclosure convention): each of these was
# constructed to defeat an earlier, naive revision of validate_base_url that
# checked ``urlsplit(value).netloc`` for non-emptiness instead of
# ``.hostname``, and did not catch ``urlsplit``'s own ValueError. Confirmed
# against a throwaway Go program using net/url (the same package waza's own
# providerHost() uses) before fixing the implementation, not just asserted:
# see the module docstring's own citations of the exact Go outputs.


def test_userinfo_with_no_host_is_rejected() -> None:
    # netloc for this value is "user:pass@" -- non-empty, so a netloc-only
    # check would have wrongly accepted it. Go's own url.Parse gives this an
    # empty Host, which is what providerHost() actually checks.
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": "https://user:pass@"})


def test_bare_at_sign_with_no_host_is_rejected() -> None:
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": "https://@"})


def test_userinfo_with_a_real_host_is_still_accepted() -> None:
    # The userinfo-stripping fix above must not overcorrect into rejecting a
    # legitimate host just because credentials are also present in the URL.
    assert preflight.check({"COPILOT_BASE_URL": "https://user:pass@example.com"}) == "COPILOT_BASE_URL"


def test_whitespace_only_host_is_rejected() -> None:
    # urlsplit("https://   /path").netloc == "   " -- non-empty and would
    # have passed a naive truthiness check. Go's own url.Parse refuses to
    # parse this at all ("invalid character \" \" in host name").
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": "https://   /path"})


def test_trailing_whitespace_in_host_is_rejected() -> None:
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": "https://example.com   "})


def test_unterminated_ipv6_literal_fails_closed_not_a_crash() -> None:
    # urlsplit / .hostname raises ValueError for this input rather than
    # returning a falsy value -- an earlier revision let that escape as an
    # unhandled traceback instead of a clean EndpointMalformed, which is a
    # worse failure mode than a wrong verdict (a crash gives no actionable
    # message and can look like an infrastructure fault, not a config one).
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": "https://[::1"})


def test_ipv6_literal_with_port_is_accepted() -> None:
    # Sanity check in the other direction: the stricter host validation
    # above must not overcorrect into rejecting a legitimate IPv6 endpoint.
    assert preflight.check({"COPILOT_BASE_URL": "https://[::1]:8443"}) == "COPILOT_BASE_URL"


# Found by an automated PR reviewer, independently reproduced (against both
# urlsplit and a live Go net/url program) before fixing rather than trusting
# the report: urlsplit silently drops a raw C0 control character or DEL from
# anywhere in the string instead of erroring or preserving it, so a
# hostname-only whitespace check never sees one. Go's own url.Parse rejects
# the same input outright, before component parsing starts at all.
@pytest.mark.parametrize(
    "value",
    [
        "https://example.invalid/\npath",  # newline
        "https://example.invalid/\rpath",  # carriage return
        "https://example.invalid/\tpath",  # tab
        "https://example.invalid/\x00path",  # NUL
        "https://example.invalid/\x1fpath",  # highest C0 control
        "https://example.invalid/\x7fpath",  # DEL
        "https://exam\nple.invalid/path",  # control char inside the host itself
    ],
)
def test_control_character_anywhere_in_value_is_rejected(value: str) -> None:
    with pytest.raises(preflight.EndpointMalformed):
        preflight.check({"COPILOT_BASE_URL": value})


def test_plain_space_in_path_is_still_accepted() -> None:
    # Go's own url.Parse does not reject an ordinary space (0x20) outside
    # the host -- only C0 controls and DEL. The fix above must not
    # overcorrect into rejecting a character Go itself tolerates.
    assert preflight.check({"COPILOT_BASE_URL": "https://example.invalid/a path"}) == "COPILOT_BASE_URL"


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

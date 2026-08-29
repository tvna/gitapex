"""Sync test: hooks/gitapex_check_pr_issue_acm_disclosure.py's own standalone
GitHub-API retry/error-shape copy (`_call`/`_default_opener`/`GitHubApiError`)
must stay behaviorally equivalent to `.github/scripts/_gitapex_github_http.py`'s
shared `request_with_retry`/`call_json`/`GitHubApiError` it was hand-copied
from.

Issue #729 (criterion 1, PR 1 of 3): the shared module now owns
`request_with_retry`, generalized from the near-identical `_call`
implementations previously hand-copied across
`gitapex_gate_acm_issue_disclosure.py`, `gitapex_post_merge_retro.py`, and
`gitapex_stale_retro_stub_autoclose.py` (see that function's own docstring).
`hooks/gitapex_check_pr_issue_acm_disclosure.py` is DELIBERATELY excluded
from that migration -- per its own module docstring and
docs/repository-layout.md, hooks/ must work standalone from inside a
distributed plugin bundle with no access to .github/scripts/ -- so its
`_call` stays a hand-copied fourth instance of the same retry/error-shape
logic, unmigrated by design. Without an automated check, this copy could
silently drift out of sync with the shared module the same way the
original hand-copied carriers this issue's own audit found already had.

Mirrors tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py's
load-by-file-path technique (itself following
tests/test_gitapex_check_acm_present_sync.py's own `_load_module` pattern)
for the same "hooks/ is deliberately not on the normal pythonpath, so load
its module by file path" reason.

Unlike that mirrored test's pattern-identity assertions (`_SECTION_RE` etc.
compared directly as compiled `re.Pattern`s), this hook's retry logic is
not exposed as directly-comparable named regex constants -- it is a
`_call` loop built from a handful of scalar constants
(`_HTTP_TIMEOUT_SECONDS`, `_MAX_ATTEMPTS`) plus inline control flow. Two of
those constants (`_MAX_ATTEMPTS`, `_HTTP_TIMEOUT_SECONDS`) are
*intentionally* smaller than the shared module's own defaults --
documented in the hook's own module docstring as sized to fit inside the
PreToolUse hook runner's 45s timeout budget -- so this file pins their
current values plus the documented inequality relationship rather than
asserting cross-file equality (which would fail by design). Everything
that IS meant to be identical -- the `attempt * 5` backoff formula, the
"retry on 5xx/network-error, break immediately on any other 4xx" rule, and
the numeric-code-vs-"network error" display convention (`_format_code` in
the shared module, inlined in the hook) -- is compared behaviorally
instead: both sides' retry function is driven through a scripted fake
opener/sleeper and their attempt counts, sleep durations, and resulting
error text are asserted identical.
"""

from __future__ import annotations

import email.message
import functools
import importlib.util
import inspect
import io
import pathlib
import types
import urllib.error
import urllib.request
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

SHARED_MODULE_PATH = REPO_ROOT / ".github" / "scripts" / "_gitapex_github_http.py"
HOOK_PATH = REPO_ROOT / "hooks" / "gitapex_check_pr_issue_acm_disclosure.py"


@functools.cache
def _load_module(path: pathlib.Path) -> types.ModuleType:
    # Loaded by file path, not `import`, since hooks/ is deliberately not
    # on pythonpath the normal way (it must work standalone from inside a
    # distributed plugin bundle) -- same technique
    # tests/test_gitapex_check_acm_present_sync.py's own _load_module uses.
    module_name = f"_pr_issue_acm_disclosure_github_http_sync__{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"could not build a module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _ScriptedOpener:
    """A fake `opener` that replays a fixed sequence of outcomes, one per
    call, and records how many times it was called. Each outcome is
    `(kind, status, body)`: `kind` is "http_error" (raise
    `urllib.error.HTTPError`, mirroring what a real `urlopen` itself
    raises for a non-2xx status) or "os_error" (raise a plain `OSError`,
    mirroring a DNS/connection failure) -- `status`/`body` are unused for
    "os_error"."""

    def __init__(self, outcomes: list[tuple[str, int, bytes]]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, request: urllib.request.Request) -> Any:
        self.calls += 1
        kind, status, body = self._outcomes.pop(0)
        if kind == "http_error":
            raise urllib.error.HTTPError(
                request.full_url, status, "scripted", email.message.Message(), io.BytesIO(body)
            )
        raise OSError("scripted network failure")


class _RecordingSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def test_both_files_exist() -> None:
    assert SHARED_MODULE_PATH.is_file(), f"missing {SHARED_MODULE_PATH}"
    assert HOOK_PATH.is_file(), f"missing {HOOK_PATH}"


def test_max_attempts_default_relationship_stays_as_documented() -> None:
    """`_MAX_ATTEMPTS` (hook) is documented, in the hook module's own
    docstring next to this constant, as deliberately lower than the shared
    module's own `request_with_retry` default -- sized so a multi-issue
    PR's sequential per-issue retries still fit inside the PreToolUse hook
    runner's 45s budget. Pin both current values plus the inequality
    itself: an accidental change to either constant that breaks the
    documented "lower than" relationship, or that changes either value
    without a conscious edit to this test, is exactly the drift this file
    exists to catch."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)
    shared_default = inspect.signature(shared.request_with_retry).parameters["max_attempts"].default
    assert shared_default == 3
    assert hook._MAX_ATTEMPTS == 2
    assert shared_default > hook._MAX_ATTEMPTS, (
        "hooks/gitapex_check_pr_issue_acm_disclosure.py's _MAX_ATTEMPTS must stay lower than "
        "_gitapex_github_http.request_with_retry's own max_attempts default, per the hook's own "
        "45s-PreToolUse-budget rationale -- update this test deliberately if that budget math changes"
    )


def test_http_timeout_relationship_stays_as_documented() -> None:
    """Same shape as the max_attempts check above, for
    `_HTTP_TIMEOUT_SECONDS`: the hook's own budget math (`_MAX_ATTEMPTS`
    attempts, each up to `_HTTP_TIMEOUT_SECONDS` long, plus `attempt * 5`
    backoff sleeps between them) has to fit inside the PreToolUse hook
    runner's 45s timeout, so the hook's own per-request timeout is
    deliberately shorter than the shared module's 30s -- not equal to
    it."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)
    assert shared._HTTP_TIMEOUT_SECONDS == 30
    assert hook._HTTP_TIMEOUT_SECONDS == 20
    assert hook._HTTP_TIMEOUT_SECONDS < shared._HTTP_TIMEOUT_SECONDS, (
        "hooks/gitapex_check_pr_issue_acm_disclosure.py's _HTTP_TIMEOUT_SECONDS must stay lower "
        "than _gitapex_github_http._HTTP_TIMEOUT_SECONDS, per the hook's own 45s-PreToolUse-budget "
        "rationale -- update this test deliberately if that budget math changes"
    )


def test_api_version_stays_in_sync() -> None:
    """Unlike the two constants above, `_API_VERSION` has no documented
    reason to differ -- both sides must send GitHub the same
    `X-GitHub-Api-Version` header value."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)
    assert shared._API_VERSION == hook._API_VERSION


def test_backoff_formula_and_attempt_count_match_on_exhausted_5xx_retries() -> None:
    """Both sides must sleep `attempt * 5` seconds between attempts and
    make exactly `max_attempts` opener calls when every attempt returns a
    5xx -- driven with the same explicit `max_attempts` on both sides so
    the differing *defaults* (pinned above) don't mask a formula
    divergence."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)

    shared_opener = _ScriptedOpener([("http_error", 500, b"{}")] * 3)
    shared_sleeper = _RecordingSleeper()
    shared_code, _shared_body = shared.request_with_retry(
        "GET", "https://api.github.com/x", "tok", shared_opener, shared_sleeper, max_attempts=3
    )

    hook_opener = _ScriptedOpener([("http_error", 500, b"{}")] * 3)
    hook_sleeper = _RecordingSleeper()
    with pytest.raises(hook.GitHubApiError):
        hook._call("https://api.github.com/x", "tok", hook_opener, hook_sleeper, max_attempts=3)

    assert shared_code == 500
    assert shared_opener.calls == hook_opener.calls == 3
    assert shared_sleeper.calls == hook_sleeper.calls == [5, 10]


def test_early_break_on_4xx_under_500_matches() -> None:
    """Neither side retries a genuine (non-network, non-404-for-the-hook)
    4xx -- both must make exactly one opener call and never sleep, even
    though `max_attempts` allows more."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)

    shared_opener = _ScriptedOpener([("http_error", 403, b"{}")])
    shared_sleeper = _RecordingSleeper()
    shared_code, _shared_body = shared.request_with_retry(
        "GET", "https://api.github.com/x", "tok", shared_opener, shared_sleeper, max_attempts=3
    )

    hook_opener = _ScriptedOpener([("http_error", 403, b"{}")])
    hook_sleeper = _RecordingSleeper()
    with pytest.raises(hook.GitHubApiError):
        hook._call("https://api.github.com/x", "tok", hook_opener, hook_sleeper, max_attempts=3)

    assert shared_code == 403
    assert shared_opener.calls == hook_opener.calls == 1
    assert shared_sleeper.calls == hook_sleeper.calls == []


def test_network_error_retries_like_5xx_on_both_sides() -> None:
    """A network/DNS failure (opener raises OSError, `last_code` stays 0)
    must retry exactly like a 5xx -- the early-break rule
    (`last_code != 0 and last_code < 500`) is false when the code is 0, on
    both sides."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)

    shared_opener = _ScriptedOpener([("os_error", 0, b"")] * 2)
    shared_sleeper = _RecordingSleeper()
    shared_code, _shared_body = shared.request_with_retry(
        "GET", "https://api.github.com/x", "tok", shared_opener, shared_sleeper, max_attempts=2
    )

    hook_opener = _ScriptedOpener([("os_error", 0, b"")] * 2)
    hook_sleeper = _RecordingSleeper()
    with pytest.raises(hook.GitHubApiError):
        hook._call("https://api.github.com/x", "tok", hook_opener, hook_sleeper, max_attempts=2)

    assert shared_code == 0
    assert shared_opener.calls == hook_opener.calls == 2
    assert shared_sleeper.calls == hook_sleeper.calls == [5]


def test_code_to_display_string_convention_matches_format_code() -> None:
    """The shared module names this convention `_format_code`; the hook
    inlines the identical `str(code) if code else "network error"`
    expression directly inside `_call` rather than importing it (per the
    hook's own "no access to .github/scripts/" constraint). The overall
    `GitHubApiError` message *template* each side wraps this in genuinely
    differs by design (the shared `call_json` raises
    "{method} {url} failed: HTTP {code}: {body}"; the hook's `_call`
    raises the shorter "fetch-failed: HTTP {code}") -- what must stay
    identical is this inner formatting convention, checked directly on the
    shared side (it has a real `_format_code` function) and via the
    hook's own raised message text on the hook side (its equivalent is
    inlined, not a callable)."""
    shared = _load_module(SHARED_MODULE_PATH)
    hook = _load_module(HOOK_PATH)

    assert shared._format_code(0) == "network error"
    assert shared._format_code(403) == "403"

    network_error_opener = _ScriptedOpener([("os_error", 0, b"")])
    with pytest.raises(hook.GitHubApiError, match="network error"):
        hook._call("https://api.github.com/x", "tok", network_error_opener, _RecordingSleeper(), max_attempts=1)

    numeric_code_opener = _ScriptedOpener([("http_error", 403, b"{}")])
    with pytest.raises(hook.GitHubApiError, match="403"):
        hook._call("https://api.github.com/x", "tok", numeric_code_opener, _RecordingSleeper(), max_attempts=1)

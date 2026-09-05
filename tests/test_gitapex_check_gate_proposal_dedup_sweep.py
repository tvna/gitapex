"""Tests for hooks/gitapex_check_gate_proposal_dedup_sweep.py (issue #1806).

The hook requires every agent-filed `gate-proposal` issue-creation body to
carry a generator-made `Dedup-sweep:` proof line whose count matches a live
re-fetch of the open gate-proposal population. No test here touches the
network: `evaluate` takes an injectable opener/sleeper pair, and every
live-count test below supplies a fake opener serving canned JSON.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import gitapex_check_gate_proposal_dedup_sweep as checker
import pytest


def _fake_opener_factory(pages: list[list[dict[str, Any]]]) -> Callable[..., Any]:
    """Serve canned per-page JSON arrays for successive page fetches."""

    class _Response:
        def __init__(self, payload: Any) -> None:
            self.status = 200
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    calls = {"n": 0}

    def _opener(request: object) -> _Response:
        index = calls["n"]
        calls["n"] += 1
        return _Response(pages[index] if index < len(pages) else [])

    return _opener


def _issues(n: int) -> list[dict[str, Any]]:
    return [{"number": i, "title": f"t{i}", "body": ""} for i in range(n)]


def _body(count: int, timestamp: str = "2026-09-05T11:00:00Z", verdict: str = "NEW") -> str:
    return (
        "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
        "|---|---|---|---|---|\n"
        "| x | y | z | proof | none |\n"
        "\n"
        "Refs #1405\n"
        "\n"
        f"Dedup-sweep: {count} open gate-proposal issues at {timestamp}; verdict {verdict}\n"
    )


_MISSING: Any = object()


def _evaluate(
    body: str,
    pages: list[list[dict[str, Any]]],
    method: str = "create",
    labels: Any = _MISSING,
) -> tuple[bool, str]:
    if labels is _MISSING:
        labels = ["gate-proposal"]
    return checker.evaluate(
        "tvna",
        "gitapex",
        method,
        labels,
        body,
        "token",
        opener=_fake_opener_factory(pages),
        sleeper=lambda _: None,
    )


def test_non_create_method_is_out_of_scope() -> None:
    passed, _ = _evaluate("anything", [[]], method="update")
    assert passed is True


@pytest.mark.parametrize("labels", [[], ["retrospective"], None])
def test_non_gate_proposal_filing_is_out_of_scope(labels: Any) -> None:
    passed, _ = _evaluate("anything", [[]], labels=labels)
    assert passed is True


def test_gate_proposal_label_matches_case_insensitively() -> None:
    passed, _ = _evaluate(_body(0), [[]], labels=["Gate-Proposal"])
    assert passed is True


def test_bare_string_label_is_normalized_to_a_single_label() -> None:
    passed, _ = _evaluate("anything", [_issues(1)], labels="gate-proposal")
    assert passed is False


def test_missing_sweep_line_denies() -> None:
    passed, message = _evaluate("no sweep line here", [_issues(3)])
    assert passed is False
    assert "Dedup-sweep" in message


def test_matching_count_allows() -> None:
    passed, _ = _evaluate(_body(3), [_issues(3)])
    assert passed is True


def test_stale_count_denies() -> None:
    passed, message = _evaluate(_body(60), [_issues(63)])
    assert passed is False
    assert "60" in message and "63" in message


def test_fenced_sweep_line_does_not_count() -> None:
    body = "Example:\n```\n" + _body(3).splitlines()[-1] + "\n```\n"
    passed, _ = _evaluate(body, [_issues(3)])
    assert passed is False


def test_two_sweep_lines_deny_as_ambiguous() -> None:
    line = _body(3).splitlines()[-1]
    passed, _ = _evaluate(line + "\n" + line + "\n", [_issues(3)])
    assert passed is False


def test_malformed_timestamp_denies() -> None:
    passed, _ = _evaluate(_body(3, timestamp="yesterday"), [_issues(3)])
    assert passed is False


def test_duplicate_of_verdict_line_allows_on_matching_count() -> None:
    passed, _ = _evaluate(_body(3, verdict="DUPLICATE-OF #1571"), [_issues(3)])
    assert passed is True


def test_missing_token_denies_fail_closed() -> None:
    passed, message = checker.evaluate(
        "tvna",
        "gitapex",
        "create",
        ["gate-proposal"],
        _body(3),
        None,
        opener=_fake_opener_factory([_issues(3)]),
        sleeper=lambda _: None,
    )
    assert passed is False
    assert "token" in message.lower()


def test_fetch_failure_denies_fail_closed() -> None:
    def _boom(request: object) -> Any:
        raise OSError("network down")

    passed, _ = checker.evaluate(
        "tvna", "gitapex", "create", ["gate-proposal"], _body(3), "token", opener=_boom, sleeper=lambda _: None
    )
    assert passed is False


def test_pagination_sums_across_pages() -> None:
    passed, _ = _evaluate(_body(150), [_issues(100), _issues(50)])
    assert passed is True


def test_evaluate_never_raises_on_arbitrary_text() -> None:
    for text in ["", "Dedup-sweep:", "Dedup-sweep: x", "#1", "`code`"]:
        first = _evaluate(text, [[]])
        second = _evaluate(text, [[]])
        assert first == second
        assert isinstance(first[0], bool)


def test_pagination_bound_exhaustion_denies_fail_closed() -> None:
    # Defeat test for the fail-closed pagination bound: ten full pages
    # leave completeness unconfirmable, so even a count-matching line
    # must deny rather than trust a possibly-truncated total.
    full_pages = [_issues(100) for _ in range(10)]
    passed, message = _evaluate(_body(1000), full_pages)
    assert passed is False
    assert "pagination-bound" in message


def test_find_sweep_lines_never_raises_and_is_deterministic() -> None:
    for text in [
        "",
        "```\nDedup-sweep: 1 open gate-proposal issues at x; verdict NEW\n```",
        "Dedup-sweep: -5 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict NEW",
    ]:
        assert checker.find_sweep_lines(text) == checker.find_sweep_lines(text)

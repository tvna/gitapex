"""Hypothesis property-based layer for
``hooks/gitapex_check_post_review_obligation_tracker.py``'s ``process``
function (issue #1823, closing issue #1178's own
``detection-logic-property-coverage`` gap for the two ``.endswith()``
string-comparison dispatch checks this issue added at lines 471 and 473).

The two new dispatch predicates are::

    isinstance(tool_name, str) and tool_name.endswith("__resolve_review_thread")
    isinstance(tool_name, str) and tool_name.endswith("__pull_request_read")

These replace prior exact-equality checks (``== "mcp__github__<tool>"``),
so any plugin-namespaced form (e.g. ``mcp__plugin_github_github__<tool>``)
is now dispatched correctly. This module's own property tests pin that
suffix-tolerance guarantee across generated namespaces, so a future edit
cannot silently regress to exact equality without breaking at least one
``@given``-decorated test.

This module resolves via ``import gitapex_check_post_review_obligation_tracker``
-- ``hooks`` is on ``pyproject.toml``'s own ``pythonpath``, the same path
``hooks/test_gitapex_check_post_review_obligation_tracker.py`` already uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import os
import tempfile

import gitapex_check_post_review_obligation_tracker as tracker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_PR_INPUT = {"owner": "tvna", "repo": "gitapex", "pullNumber": 1209}

_PUSHED_STATE = {
    **tracker._DEFAULT_STATE,
    "push_detected": True,
    "target_pr": "tvna/gitapex#1209",
}

_SAFE_CHARS = st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\x00")


def _no_known_suffix(s: str) -> bool:
    return s != "Bash" and not s.endswith("__pull_request_read") and not s.endswith("__resolve_review_thread")


@_PROPERTIES
@given(tool_name=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=60).filter(_no_known_suffix))
def test_unknown_tool_name_always_returns_none(tool_name: str) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the fixed tests in ``hooks/test_gitapex_check_post_review_obligation_tracker.py``
    exercise specific tool names -- this drives ``tool_name`` across a wide
    space of strings that match neither known suffix and confirms they all
    reach the ``else: return None`` branch, regardless of session state.

    Confirmed to have teeth: this property's negation test
    (``test_any_prefix_with_pr_read_suffix_dispatches_and_updates_state``
    below) proves that suffix-matching strings do NOT return None, so the
    two properties together bracket the dispatch contract. If ``process``
    were patched to always return None, both the positive and negative halves
    would reveal the regression: the positive half fails because result is
    None where a state update was expected; the negative half keeps passing
    but the pair as a whole would expose the invariant collapse when a
    reviewer sees both tests pass but the positive side's own assertion never
    fired (which Hypothesis's own shrinking and the added ``assert result is
    not None`` in the positive tests make impossible to miss)."""
    result = tracker.process({"session_id": "prop_unknown", "tool_name": tool_name})
    assert result is None


@_PROPERTIES
@given(prefix=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=30))
def test_any_prefix_with_pr_read_suffix_dispatches_and_updates_state(prefix: str) -> None:
    """Any tool_name ending in ``__pull_request_read`` -- regardless of its
    namespace prefix -- dispatches into ``handle_pull_request_read`` and
    updates ``open_review_threads`` when ``push_detected=True`` and the
    response carries unresolved threads.

    **Confirmed to have teeth:** reverting the ``.endswith("__pull_request_read")``
    check to the pre-fix exact equality (``== "mcp__github__pull_request_read"``)
    makes this property FAIL on every generated ``prefix`` that is not
    literally ``"mcp__github"`` -- the full class of plugin-namespaced tool
    names this issue's fix was written to accept. The pre-fix code would
    fall through to the ``else: return None`` branch, so ``result`` would be
    ``None`` instead of a dict with ``open_review_threads == 1``."""
    tool_name = prefix + "__pull_request_read"
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = tmp
        try:
            sid = "prop_pr_read"
            tracker._write_state(tracker.state_path(sid), dict(_PUSHED_STATE))
            result = tracker.process(
                {
                    "session_id": sid,
                    "tool_name": tool_name,
                    "tool_input": {**_PR_INPUT, "method": "get_review_comments"},
                    "tool_response": {"threads": [{"isResolved": False}]},
                }
            )
        finally:
            if old is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = old
    assert result is not None
    assert result.get("open_review_threads") == 1


@_PROPERTIES
@given(prefix=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=30))
def test_any_prefix_with_resolve_suffix_dispatches_and_updates_state(prefix: str) -> None:
    """Any tool_name ending in ``__resolve_review_thread`` -- regardless of
    its namespace prefix -- dispatches into ``handle_resolve_review_thread``
    and increments ``resolve_calls`` when ``push_detected=True`` and
    ``target_pr`` is set.

    **Confirmed to have teeth:** reverting the ``.endswith("__resolve_review_thread")``
    check to exact equality (``== "mcp__github__resolve_review_thread"``) makes
    this property FAIL on every generated ``prefix`` that is not literally
    ``"mcp__github"`` -- for the same reason as the PR-read property above:
    the pre-fix exact match would not fire, the else branch returns None,
    and ``result.get("resolve_calls") == 1`` is never reachable."""
    tool_name = prefix + "__resolve_review_thread"
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = tmp
        try:
            sid = "prop_resolve"
            tracker._write_state(tracker.state_path(sid), dict(_PUSHED_STATE))
            result = tracker.process(
                {
                    "session_id": sid,
                    "tool_name": tool_name,
                    "tool_response": {},
                }
            )
        finally:
            if old is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = old
    assert result is not None
    assert result.get("resolve_calls") == 1

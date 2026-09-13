"""Hypothesis property-based layer for
``hooks/gitapex_check_post_review_obligation_tracker.py``'s ``process``
function (issue #1823, closing issue #1178's own
``detection-logic-property-coverage`` gap for the two ``.endswith()``
string-comparison dispatch checks this issue added at lines 471 and 473),
and for ``_resolve_owner_repo``'s own ``_parse_github_owner_repo`` parser
(issue #1631, closing the same gap for that new detection-logic call
site, including two live-confirmed defeat-case regressions: a
port-bearing URL and a spoofed non-github.com host embedding the
literal substring "github.com" in its path).

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
import subprocess
import tempfile
from typing import Any

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
    return not s.endswith("__pull_request_read") and not s.endswith("__resolve_review_thread")


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
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = tmp
        try:
            result = tracker.process({"session_id": "prop_unknown", "tool_name": tool_name})
        finally:
            if old is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = old
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


# --- _resolve_owner_repo's own _parse_github_owner_repo (issue #1631) ---

#: Letters, digits, hyphen, underscore only -- deliberately excludes '.'
#: and '/' so a generated owner/repo name can never itself be ambiguous
#: against the regex's own '.git' suffix or '/' separator handling; that
#: narrower edge (a literal '.' inside a repo name colliding with the
#: optional trailing '.git') is a known, accepted limitation of this
#: heuristic parser, not something this property is trying to pin.
_OWNER_REPO_CHARS = st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_")
_owner_repo_strategy = st.text(alphabet=_OWNER_REPO_CHARS, min_size=1, max_size=20)


def _fake_runner_with_stdout(output: str) -> Any:
    def runner(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=output + "\n", stderr="")

    return runner


@_PROPERTIES
@given(owner=_owner_repo_strategy, repo=_owner_repo_strategy)
def test_resolve_owner_repo_wires_git_remote_output_into_the_parser(owner: str, repo: str) -> None:
    """**Integration property for the thin wrapper `_parse_github_owner_repo`
    itself does not cover:** `_resolve_owner_repo` must actually run `git
    remote get-url origin` via the given `runner` and hand its stdout to
    `_parse_github_owner_repo` unchanged -- confirmed here end to end with a
    fake runner standing in for the real subprocess, across a wide space of
    owner/repo shapes, rather than assumed from `_parse_github_owner_repo`'s
    own property coverage above."""
    url = f"https://github.com/{owner}/{repo}.git"
    result = tracker._resolve_owner_repo("/tmp/does-not-matter", _fake_runner_with_stdout(url))
    assert result == (owner, repo)


@_PROPERTIES
@given(
    owner=_owner_repo_strategy,
    repo=_owner_repo_strategy,
    use_ssh=st.booleans(),
    has_dot_git=st.booleans(),
)
def test_parse_github_owner_repo_parses_https_and_ssh_remotes(
    owner: str, repo: str, use_ssh: bool, has_dot_git: bool
) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    ``_parse_github_owner_repo`` must correctly parse both remote URL forms
    GitHub itself hands out -- HTTPS
    (``https://github.com/<owner>/<repo>[.git]``) and SSH
    (``git@github.com:<owner>/<repo>[.git]``) -- across a wide space of
    owner/repo name shapes, with or without a trailing ``.git`` suffix.

    **Confirmed to have teeth:** a regex requiring a literal trailing
    slash after the repo name fails every ``has_dot_git=False`` case
    generated here (GitHub's own URLs carry no trailing slash without
    ``.git``); a regex anchored only to the ``https://`` form fails
    every ``use_ssh=True`` case; a regex that does not strip an optional
    ``.git`` suffix fails every ``has_dot_git=True`` case, since the
    returned repo name would then carry the literal suffix instead of
    matching ``repo`` exactly."""
    suffix = ".git" if has_dot_git else ""
    url = f"git@github.com:{owner}/{repo}{suffix}" if use_ssh else f"https://github.com/{owner}/{repo}{suffix}"
    result = tracker._parse_github_owner_repo(url)
    assert result == (owner, repo)


@_PROPERTIES
@given(text=st.text(max_size=60).filter(lambda s: "github.com" not in s))
def test_parse_github_owner_repo_returns_none_for_non_github_remotes(text: str) -> None:
    """**Confirmed to have teeth (negation of the property above):** any
    remote URL string that never mentions ``github.com`` at all -- an
    empty string, a bare hostname, a GitLab/Bitbucket URL, arbitrary
    text -- must resolve to ``None``, never a fabricated owner/repo pair.
    Pairs with the property above to bracket ``_parse_github_owner_repo``'s
    own match/no-match contract."""
    result = tracker._parse_github_owner_repo(text)
    assert result is None


@_PROPERTIES
@given(owner=_owner_repo_strategy, repo=_owner_repo_strategy, port=st.integers(min_value=1, max_value=65535))
def test_parse_github_owner_repo_strips_port_number_not_owner(owner: str, repo: str, port: int) -> None:
    """**Regression for a live-confirmed defeat case:** a port-bearing
    HTTPS remote URL (``https://github.com:<port>/<owner>/<repo>.git``,
    a form `git remote get-url` can genuinely return, e.g. behind a
    proxy) must still resolve to the real ``(owner, repo)`` pair -- an
    unanchored regex previously matched the port digits themselves as
    the owner and the remaining ``owner/repo`` (embedded slash intact)
    as the repo, a live-reproduced mis-parse this test pins shut."""
    url = f"https://github.com:{port}/{owner}/{repo}.git"
    result = tracker._parse_github_owner_repo(url)
    assert result == (owner, repo)


@_PROPERTIES
@given(owner=_owner_repo_strategy, repo=_owner_repo_strategy, evil_host=_owner_repo_strategy)
def test_parse_github_owner_repo_rejects_spoofed_non_github_host(owner: str, repo: str, evil_host: str) -> None:
    """**Regression for a live-confirmed defeat case:** a URL whose
    actual host is not ``github.com`` but whose *path* embeds the
    literal substring ``github.com/<owner>/<repo>`` (e.g.
    ``https://evil.example.com/path/github.com/owner/repo``) must
    resolve to ``None`` -- an unanchored regex previously matched this
    exact shape and returned the spoofed owner/repo as if the remote
    genuinely pointed at github.com. `_parse_github_owner_repo` must
    validate the real, parsed hostname, never merely search the raw
    string for the substring "github.com"."""
    url = f"https://{evil_host}.example.com/path/github.com/{owner}/{repo}"
    result = tracker._parse_github_owner_repo(url)
    assert result is None

"""Hypothesis property-based layer for
``hooks/gitapex_check_bash_safety.py``'s detection-logic call sites (issue
#1178's ``detection-logic-property-coverage`` gate; issue #1326 Stage 1
added this module -- a brand-new token-based classifier -- with zero
property coverage of its own regex/string-comparison call sites).

Resolves via ``import gitapex_check_bash_safety`` against ``hooks``
specifically (this repository's own ``pyproject.toml`` ``pythonpath``
entry) -- the sibling copy at
``skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py``
is covered by its own separate properties file
(``test_gitapex_check_task_bash_safety_properties.py``), since the two are
self-contained duplicates, not a shared module.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import string

import gitapex_check_bash_safety as checker
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_IDENT_ALPHABET = string.ascii_letters + string.digits + "_"
_IDENTIFIERS = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from(string.ascii_letters + "_"),
    st.text(alphabet=_IDENT_ALPHABET, max_size=10),
)
_VALUES = st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=12)


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_captures_name_equals_value_rhs(name: str, value: str) -> None:
    """Model-based: any bare shell identifier assignment token contributes
    its RHS (lowercased) to the assigned-literal set -- the exact signal
    Rule B1b's own indirection detection (``A=uv; B=install; $A $B foo``)
    depends on."""
    result = checker._assigned_literals([f"{name}={value}"])
    assert value.lower() in result


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_ignores_a_dynamic_rhs_token(name: str, value: str) -> None:
    """A token containing ``$`` is dynamic and is skipped outright before
    ``_ASSIGN_RE`` is ever consulted -- even though the token still
    textually matches the ``NAME=value`` shape."""
    result = checker._assigned_literals([f"{name}=${value}"])
    assert result == set()


@_PROPERTIES
@given(
    tokens=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8).filter(lambda t: "=" not in t), max_size=5
    )
)
def test_assigned_literals_never_raises_on_tokens_with_no_equals_sign(tokens: list[str]) -> None:
    """Robustness: a token stream containing no ``=`` character at all
    never raises and always returns an empty set -- ``_assigned_literals``
    runs against untrusted, attacker-shaped Bash command text."""
    assert checker._assigned_literals(tokens) == set()


@_PROPERTIES
@given(method=st.sampled_from(["POST", "PUT", "PATCH", "DELETE", "post", "put", "patch", "delete", "PoSt", "DeLeTe"]))
def test_rule_gh_api_write_detects_every_write_method_case_insensitively(method: str) -> None:
    """Model-based: ``gh api ... -X <method>`` is a write for any of the
    four HTTP write verbs, in any casing -- the whole point of
    pre-lowering ``literals`` before this comparison."""
    segments = [["gh", "api", "repos/x/y", "-X", method]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}")
    assert result is not None


@_PROPERTIES
@given(method=st.sampled_from(["GET", "get", "Get"]))
def test_rule_gh_api_write_does_not_flag_a_read_method(method: str) -> None:
    """No false positive: GET is a read, not a write, and must never be
    flagged by the method-flag branch."""
    segments = [["gh", "api", "repos/x/y", "-X", method]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}")
    assert result is None


@_PROPERTIES
@given(field=_IDENTIFIERS, value=_VALUES)
def test_rule_gh_api_write_detects_any_field_flag_payload(field: str, value: str) -> None:
    """Model-based: ``-f``/``--field``/``--raw-field`` with any
    ``field=value`` payload is always a write, regardless of the specific
    field name or value carried."""
    segments = [["gh", "api", "repos/x/y", "-f", f"{field}={value}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -f {field}={value}")
    assert result is not None


_SHORT_FLAG_WITH_VALUE = st.tuples(st.sampled_from(["-c", "-C"]), st.sampled_from(["cfgkey=cfgval", "/tmp/some/repo"]))
_LONG_FLAG_ALONE = st.sampled_from(["--git-dir=/tmp/x/.git", "--no-pager", "--work-tree=/tmp/y"])
_GIT_GLOBAL_FLAG_GROUP = st.one_of(_SHORT_FLAG_WITH_VALUE.map(list), _LONG_FLAG_ALONE.map(lambda f: [f]))


@_PROPERTIES
@given(flag_groups=st.lists(_GIT_GLOBAL_FLAG_GROUP, max_size=3))
def test_is_git_push_segment_true_for_git_push_regardless_of_leading_global_flags(flag_groups: list[list[str]]) -> None:
    """Model-based: any sequence of git global flags between ``git`` and
    ``push`` still resolves to a detected git-push segment -- the exact
    fix ``git -C /tmp/repo push origin HEAD`` needed live (a short flag
    consumes its own following value token, a long ``--flag=value`` does
    not consume an extra token)."""
    seg = ["git"]
    for group in flag_groups:
        seg.extend(group)
    seg += ["push", "origin"]
    assert checker._is_git_push_segment(seg)


@_PROPERTIES
@given(subcommand=st.sampled_from(["status", "commit", "log", "diff", "fetch", "clone"]))
def test_is_git_push_segment_false_for_a_non_push_subcommand(subcommand: str) -> None:
    """No false positive: an ordinary git subcommand that is not push,
    with no literal 'git push' substring anywhere in the segment, is
    never misdetected."""
    seg = ["git", subcommand, "--short"]
    assert not checker._is_git_push_segment(seg)


@_PROPERTIES
@given(tokens=st.lists(st.text(max_size=15), max_size=6))
def test_is_git_push_segment_never_raises_on_arbitrary_tokens(tokens: list[str]) -> None:
    """Robustness: arbitrary token content (including tokens containing
    ``$``/backtick, empty strings, or unicode) never raises -- this
    function classifies untrusted, attacker-shaped Bash tokens."""
    result = checker._is_git_push_segment(tokens)
    assert isinstance(result, bool)

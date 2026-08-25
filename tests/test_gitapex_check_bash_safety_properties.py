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
    """Model-based: any bare shell identifier assignment token maps its
    name to its RHS (lowercased) in the returned dict -- the exact signal
    Rule B1b's own indirection detection (``A=uv; B=install; $A $B foo``)
    depends on. Keyed by name (issue #1326 Step 8 fix), not a flat set of
    values -- see test_rule_b1b_ignores_unrelated_whole_command_assignments
    below for the false positive a flat set produced."""
    result = checker._assigned_literals([f"{name}={value}"])
    assert result.get(name) == value.lower()


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_literals_ignores_a_dynamic_rhs_token(name: str, value: str) -> None:
    """A token containing ``$`` is dynamic and is skipped outright before
    ``_ASSIGN_RE`` is ever consulted -- even though the token still
    textually matches the ``NAME=value`` shape."""
    result = checker._assigned_literals([f"{name}=${value}"])
    assert result == {}


@_PROPERTIES
@given(
    tokens=st.lists(
        st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8).filter(lambda t: "=" not in t), max_size=5
    )
)
def test_assigned_literals_never_raises_on_tokens_with_no_equals_sign(tokens: list[str]) -> None:
    """Robustness: a token stream containing no ``=`` character at all
    never raises and always returns an empty dict -- ``_assigned_literals``
    runs against untrusted, attacker-shaped Bash command text."""
    assert checker._assigned_literals(tokens) == {}


@_PROPERTIES
@given(method=st.sampled_from(["POST", "PUT", "PATCH", "DELETE", "post", "put", "patch", "delete", "PoSt", "DeLeTe"]))
def test_rule_gh_api_write_detects_every_write_method_case_insensitively(method: str) -> None:
    """Model-based: ``gh api ... -X <method>`` is a write for any of the
    four HTTP write verbs, in any casing -- the whole point of
    pre-lowering ``literals`` before this comparison."""
    segments = [["gh", "api", "repos/x/y", "-X", method]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}", {})
    assert result is not None


@_PROPERTIES
@given(method=st.sampled_from(["GET", "get", "Get"]))
def test_rule_gh_api_write_does_not_flag_a_read_method(method: str) -> None:
    """No false positive: GET is a read, not a write, and must never be
    flagged by the method-flag branch."""
    segments = [["gh", "api", "repos/x/y", "-X", method]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}", {})
    assert result is None


@_PROPERTIES
@given(field=_IDENTIFIERS, value=_VALUES)
def test_rule_gh_api_write_detects_any_field_flag_payload(field: str, value: str) -> None:
    """Model-based: ``-f``/``--field``/``--raw-field`` with any
    ``field=value`` payload is always a write, regardless of the specific
    field name or value carried."""
    segments = [["gh", "api", "repos/x/y", "-f", f"{field}={value}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -f {field}={value}", {})
    assert result is not None


@_PROPERTIES
@given(
    method=st.sampled_from(["post", "put", "patch", "delete"]),
    var=_IDENTIFIERS,
)
def test_rule_gh_api_write_detects_a_dynamic_method_value_resolved_from_an_assignment(method: str, var: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review (issue #1326): ``M=POST; gh api .../merge -X $M``
    resolved to a real write and was wrongly allowed, because the
    dynamic value token was filtered out of ``literals`` before the
    method-flag scan ever ran. Detected now via ``name_to_value`` lookup
    of the variable the dynamic token actually references."""
    segments = [["gh", "api", "repos/x/y", "-X", f"${var}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}", {var: method})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_a_dynamic_method_value_resolved_to_a_read(var: str) -> None:
    """No false positive: a dynamic ``-X`` value that resolves (via
    ``name_to_value``) to GET, not one of the four write methods, is
    never flagged."""
    segments = [["gh", "api", "repos/x/y", "-X", f"${var}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}", {var: "get"})
    assert result is None


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


@_PROPERTIES
@given(flag=st.sampled_from(["-v", "-h", "-p", "-P"]))
def test_is_git_push_segment_true_for_boolean_short_flags_before_push(flag: str) -> None:
    """Model-based, regression pin for a real bug found live by Step 8
    independent review (issue #1326): every 2-character short flag was
    treated as consuming a following value token, which wrongly swallowed
    the ``push`` token itself as a boolean flag's "value" (``git -p push
    origin main`` was never detected). ``-v``/``-h``/``-p``/``-P`` are
    git's own boolean, no-argument short global options (confirmed
    against git's usage synopsis) -- push must still be found right after
    one."""
    assert checker._is_git_push_segment(["git", flag, "push", "origin"])


@_PROPERTIES
@given(flag=st.sampled_from(["-v", "-h", "-p", "-P"]), subcommand=st.sampled_from(["log", "status", "diff"]))
def test_is_git_push_segment_false_for_boolean_short_flag_before_non_push_subcommand(
    flag: str, subcommand: str
) -> None:
    """No false positive: a boolean short flag before an ordinary,
    non-push subcommand is never misdetected as git push."""
    assert not checker._is_git_push_segment(["git", flag, subcommand])


@_PROPERTIES
@given(unrelated_var=_IDENTIFIERS)
def test_rule_b1b_ignores_unrelated_whole_command_assignments(unrelated_var: str) -> None:
    """Model-based, regression pin for a real false positive found live
    by Step 8 independent review (issue #1326):
    ``TOOL=uv; VERB=install; echo done; X=$(mktemp); "$X" --help`` was
    wrongly denied, because the old whole-command flat assigned-value set
    matched *some* tool-shaped and *some* verb-shaped assignment anywhere
    in the command, regardless of whether the dynamic segment actually
    referenced either variable. Scoped now to the variable names the
    dynamic segment's own tokens actually reference."""
    name_to_value = {"TOOL": "uv", "VERB": "install"}
    seg = [f"${unrelated_var}", "--help"]
    assert not checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS)


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1b_detects_when_segment_actually_references_assigned_tool_and_verb(tool_var: str, verb_var: str) -> None:
    """True positive, still detected after the false-positive fix above:
    when the SAME segment's own dynamic tokens reference the specific
    variables assigned a watched tool and a watched verb (``A=uv;
    B=install; $A $B foo``), this must still deny."""
    if tool_var == verb_var:
        return
    name_to_value = {tool_var: "uv", verb_var: "install"}
    seg = [f"${tool_var}", f"${verb_var}", "foo"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS)

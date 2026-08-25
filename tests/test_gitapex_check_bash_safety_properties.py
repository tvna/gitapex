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


@_PROPERTIES
@given(
    method=st.sampled_from(["post", "put", "patch", "delete"]),
    var=_IDENTIFIERS,
    shape=st.sampled_from(["-x{}", "-x={}", "--method={}"]),
)
def test_rule_gh_api_write_detects_a_dynamic_method_value_fused_with_the_flag(
    method: str, var: str, shape: str
) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, second round (issue #1326): the first fix for
    this bypass only covered the flag-and-value-as-two-separate-tokens
    shape (``-X $M``) -- ``-X=$M``, ``-X$M``/``-X"$M"`` (shlex dequotes
    the quoted form to the same single fused token), and ``--method=$M``
    are all semantically identical ways to pass a dynamic method value,
    and all three still resolved to a real write while being wrongly
    allowed until this second fix."""
    token = shape.format(f"${var}")
    segments = [["gh", "api", "repos/x/y", token]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {var: method})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS, shape=st.sampled_from(["-x{}", "-x={}", "--method={}"]))
def test_rule_gh_api_write_allows_a_fused_dynamic_method_value_resolved_to_a_read(var: str, shape: str) -> None:
    """No false positive: the same three fused shapes, resolved to GET via
    ``name_to_value``, are never flagged."""
    token = shape.format(f"${var}")
    segments = [["gh", "api", "repos/x/y", token]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {var: "get"})
    assert result is None


@_PROPERTIES
@given(var=_IDENTIFIERS, shape=st.sampled_from(["-f{}", "--field={}", "--raw-field={}"]))
def test_rule_gh_api_write_detects_a_field_flag_fused_with_a_dynamic_value(var: str, shape: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, third round (issue #1326): a field flag fused
    directly with a dynamic value (``-f$X``, ``--field=$X``,
    ``--raw-field=$X``) makes the WHOLE token dynamic, so it never
    reaches the literal-token field-flag check at all -- the same
    fused-token gap the -X/--method fix had to close separately. This
    rule never inspects the field VALUE, only the flag's presence, so no
    ``name_to_value`` lookup is needed here -- any dynamic token shaped
    like a field flag is denied outright."""
    token = shape.format(f"${var}")
    segments = [["gh", "api", "repos/x/y", token]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_an_unrelated_dynamic_token_with_no_field_flag_shape(var: str) -> None:
    """No false positive: an ordinary dynamic token that does not start
    with a field-flag prefix is never flagged by the fused-field-flag
    check."""
    segments = [["gh", "api", "repos/x/y", f"${var}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${var}", {})
    assert result is None


# --- Direct coverage of _rule_gh_api_write's own extracted sub-passes
# (issue #1178 detection-logic-property-coverage: each pass is its own
# named function now, kept small deliberately to hold this module's own
# per-function cyclomatic complexity down after xenon flagged the
# monolithic version -- these exercise each pass directly, in addition
# to the end-to-end _rule_gh_api_write tests above).


@_PROPERTIES
@given(
    method=st.sampled_from(["POST", "PUT", "PATCH", "DELETE", "post", "PoSt"]),
    shape=st.sampled_from(["-x{}", "-xdirect{}", "--method={}"]),
)
def test_gh_api_method_literal_hit_detects_every_fused_or_separate_literal_shape(method: str, shape: str) -> None:
    """Model-based: a literal write method is detected regardless of
    which of the three real flag shapes carries it -- separate token
    (``["-x", METHOD]``), fused directly with no separator
    (``-xmethod``, the real short-flag shorthand pflag -- gh's own CLI
    flag library -- supports), or a single fused long token
    (``--method=method``). ``-x=method`` is deliberately excluded here:
    pflag's short-flag parsing does not support ``=`` as a separator, so
    a literal ``-X=POST`` is not real gh syntax and
    ``_gh_api_method_literal_hit`` correctly does not treat it as one
    (the dynamic-value pass is intentionally more permissive for this
    exact shape as a safety margin -- see the fused-dynamic-value tests
    above)."""
    if shape == "-x{}":
        literals = ["-x", method.lower()]
    elif shape == "-xdirect{}":
        literals = [f"-x{method.lower()}"]
    else:
        literals = [f"--method={method.lower()}"]
    assert checker._gh_api_method_literal_hit(literals)


@_PROPERTIES
@given(method=st.sampled_from(["GET", "get"]))
def test_gh_api_method_literal_hit_allows_a_read_method(method: str) -> None:
    """No false positive: GET is never flagged."""
    assert not checker._gh_api_method_literal_hit(["-x", method.lower()])


@_PROPERTIES
@given(var=_IDENTIFIERS, shape=st.sampled_from(["separate", "-x={}", "--method={}"]))
def test_gh_api_method_dynamic_value_extracts_the_fused_or_separate_shape(var: str, shape: str) -> None:
    """Model-based: whichever of the three shapes carries the dynamic
    value (separate token, fused with ``=``, or a fused long token), the
    extracted value part references the same variable the original
    dynamic token did."""
    if shape == "separate":
        seg = ["gh", "api", "x", "-x", f"${var}"]
        index = 3
    else:
        seg = ["gh", "api", "x", shape.format(f"${var}")]
        index = 3
    extracted = checker._gh_api_method_dynamic_value(seg, index, seg[index])
    assert extracted is not None
    assert var in checker._VAR_REF_RE.findall(extracted)


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_value_none_for_an_unrelated_token(var: str) -> None:
    """No false positive: a token that is neither a -X/--method flag nor
    immediately follows one yields no extracted value."""
    seg = ["gh", "api", "x", f"${var}"]
    assert checker._gh_api_method_dynamic_value(seg, 3, seg[3]) is None


@_PROPERTIES
@given(shape=st.sampled_from(["-f", "-fvalue", "--field=value", "--raw-field=value"]))
def test_gh_api_field_literal_hit_detects_every_literal_shape(shape: str) -> None:
    """Model-based: every literal field-flag shape is detected."""
    assert checker._gh_api_field_literal_hit([shape])


@_PROPERTIES
@given(tok=st.sampled_from(["-x", "post", "repos/x/y", "gh", "api"]))
def test_gh_api_field_literal_hit_allows_unrelated_tokens(tok: str) -> None:
    """No false positive: tokens unrelated to the field flag are never
    flagged."""
    assert not checker._gh_api_field_literal_hit([tok])


@_PROPERTIES
@given(var=_IDENTIFIERS, shape=st.sampled_from(["-f{}", "--field={}", "--raw-field={}"]))
def test_gh_api_field_dynamic_hit_detects_every_fused_shape(var: str, shape: str) -> None:
    """Model-based: every fused-with-a-dynamic-value field-flag shape is
    detected, directly at the sub-pass level."""
    token = shape.format(f"${var}")
    assert checker._gh_api_field_dynamic_hit([token])


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_field_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: an ordinary dynamic token with no field-flag
    prefix is never flagged."""
    assert not checker._gh_api_field_dynamic_hit([f"${var}"])


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

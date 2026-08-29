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

import json
import shlex
import string
import sys
from typing import cast

import gitapex_check_bash_safety as checker
import pytest
from conftest import FakeStdin as _FakeStdin
from hypothesis import assume, given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_IDENT_ALPHABET = string.ascii_letters + string.digits + "_"
_IDENTIFIERS = st.builds(
    lambda head, tail: head + tail,
    st.sampled_from(string.ascii_letters + "_"),
    st.text(alphabet=_IDENT_ALPHABET, max_size=10),
)
_VALUES = st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=12)

# A token whose `_substitute_var_refs_candidates` combinatorial expansion
# exceeds `_MAX_SUBSTITUTION_CANDIDATES` (64): 7 default-clause references,
# each contributing 2 candidates (default text + the variable's own
# resolved value), 2**7=128 > 64 -- shared by every fail-closed-on-overflow
# test below, read-only (never mutated by any of them).
_OVERFLOW_TOKEN = "".join(f"${{V{i}:-d}}" for i in range(7))
_OVERFLOW_NAME_TO_VALUE = {f"V{i}": "x" for i in range(7)}


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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}", {}, {})
    assert result is not None


@_PROPERTIES
@given(method=st.sampled_from(["GET", "get", "Get"]))
def test_rule_gh_api_write_does_not_flag_a_read_method(method: str) -> None:
    """No false positive: GET is a read, not a write, and must never be
    flagged by the method-flag branch."""
    segments = [["gh", "api", "repos/x/y", "-X", method]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {method.lower()}", {}, {})
    assert result is None


@_PROPERTIES
@given(field=_IDENTIFIERS, value=_VALUES)
def test_rule_gh_api_write_detects_any_field_flag_payload(field: str, value: str) -> None:
    """Model-based: ``-f``/``--field``/``--raw-field`` with any
    ``field=value`` payload is always a write, regardless of the specific
    field name or value carried."""
    segments = [["gh", "api", "repos/x/y", "-f", f"{field}={value}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -f {field}={value}", {}, {})
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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}", {var: method}, {})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_a_dynamic_method_value_resolved_to_a_read(var: str) -> None:
    """No false positive: a dynamic ``-X`` value that resolves (via
    ``name_to_value``) to GET, not one of the four write methods, is
    never flagged."""
    segments = [["gh", "api", "repos/x/y", "-X", f"${var}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}", {var: "get"}, {})
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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {var: method}, {})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS, shape=st.sampled_from(["-x{}", "-x={}", "--method={}"]))
def test_rule_gh_api_write_allows_a_fused_dynamic_method_value_resolved_to_a_read(var: str, shape: str) -> None:
    """No false positive: the same three fused shapes, resolved to GET via
    ``name_to_value``, are never flagged."""
    token = shape.format(f"${var}")
    segments = [["gh", "api", "repos/x/y", token]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {var: "get"}, {})
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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {}, {})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_an_unrelated_dynamic_token_with_no_field_flag_shape(var: str) -> None:
    """No false positive: an ordinary dynamic token that does not start
    with a field-flag prefix is never flagged by the fused-field-flag
    check."""
    segments = [["gh", "api", "repos/x/y", f"${var}"]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${var}", {}, {})
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
    extracted = checker._gh_api_method_dynamic_value(seg, index, seg[index], {}, {})
    assert extracted is not None
    assert f"${var}" in extracted


def test_value_position_after_skips_a_vanishing_decoy_to_find_the_real_value() -> None:
    """Direct unit coverage for the twenty-second-round helper both
    `_gh_api_method_dynamic_value` and `_gh_api_method_flagname_dynamic_
    hit` share: a vanishing decoy (NEVERSET never assigned) sitting
    right after the flag is skipped, landing on the real, assigned
    value one position further."""
    seg = ["gh", "api", "repos/o/r/pulls/1", "-X", "$NEVERSET", "$M"]
    assert checker._value_position_after(seg, 3, {"M": "post"}, {"M": "post"}) == "$M"


def test_value_position_after_falls_back_to_the_adjacent_token_when_nothing_survives() -> None:
    """Direct unit coverage for the fallback half of the same helper: a
    single, merely-unresolved-in-this-scope token (not a genuine decoy
    with a real value beyond it) is still returned rather than silently
    dropped when skipping runs off the end of the segment."""
    seg = ["gh", "api", "x", "-x", "$a"]
    assert checker._value_position_after(seg, 3, {}, {}) == "$a"


def test_value_position_after_returns_none_with_no_token_past_the_flag() -> None:
    """No token at all past the flag -> None, matching every prior
    caller's own established behavior for that case."""
    seg = ["gh", "api", "x", "-x"]
    assert checker._value_position_after(seg, 3, {}, {}) is None


def test_token_is_unambiguously_vanishing_true_for_a_genuinely_unassigned_bare_ref() -> None:
    """The straightforward case: an unbraced bare reference to a name
    never assigned anywhere, with no shorter-prefix ambiguity, is
    unambiguously vanishing."""
    assert checker._token_is_unambiguously_vanishing("$NEVERSET", {}, {}) is True


def test_token_is_unambiguously_vanishing_false_when_a_shorter_prefix_is_assigned() -> None:
    """The quote-boundary-ambiguity case this predicate exists to catch:
    "aost" is itself unassigned, but the shorter prefix "ao" IS assigned
    -- shlex has already lost whether the raw token `$aost` was
    originally bare (`$aost`) or a quoted `$ao` fused with literal "st"
    -- so this must NOT be treated as unambiguously vanishing."""
    assert checker._token_is_unambiguously_vanishing("$aost", {"ao": "po"}, {"ao": "po"}) is False


def test_token_is_unambiguously_vanishing_false_for_an_assigned_name() -> None:
    """A token whose own name IS directly assigned is not vanishing at
    all, let alone unambiguously so."""
    assert checker._token_is_unambiguously_vanishing("$M", {"M": "post"}, {"M": "post"}) is False


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_value_none_for_an_unrelated_token(var: str) -> None:
    """No false positive: a token that is neither a -X/--method flag nor
    immediately follows one yields no extracted value."""
    seg = ["gh", "api", "x", f"${var}"]
    assert checker._gh_api_method_dynamic_value(seg, 3, seg[3], {}, {}) is None


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


# --- Round 5: the -X/--method/-f/--field flag NAME itself hidden behind a
# bare variable reference (issue #1326, found live by Step 8 independent
# review, fifth round). Every check above assumes the flag token carries a
# literal "-x"/"--method"/"-f"/"--field" text prefix somewhere in itself --
# a token that is PURELY `$F` has none, so none of them ever recognized it
# as a flag at all until the two `*_flagname_dynamic_hit` passes below
# closed this.


@_PROPERTIES
@given(suffix_var=_IDENTIFIERS, method=st.sampled_from(["post", "put", "patch", "delete"]))
def test_gh_api_method_flagname_dynamic_hit_detects_a_flag_name_fused_with_a_literal_prefix(
    suffix_var: str, method: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twelfth round (issue #1326): a flag NAME
    reconstructed by fusing a literal ``--`` prefix with a bare variable
    reference in the SAME token (``--$M``) is still caught -- confirmed
    live via real bash argv expansion that ``--$M`` resolves to a genuine
    ``--method`` write. Round eleven's own claim that "a flag name is
    never fused with other text the way a value can be" was wrong; this
    is the regression pin for that fix, using ``_substitute_var_refs_
    candidates`` directly instead of the now-removed, whole-token-only
    ``_resolve_bare_or_indirect``."""
    name_to_value = {suffix_var: "method"}
    seg = ["gh", "api", "repos/x/y", f"--${suffix_var}", method]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(suffix_var=_IDENTIFIERS)
def test_gh_api_field_flagname_dynamic_hit_detects_a_flag_name_fused_with_a_literal_prefix(suffix_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twelfth round (issue #1326): the field-flag
    counterpart of the method-flag fix above -- ``--$FF`` (a literal
    ``--`` prefix fused with a bare variable reference) resolving to a
    genuine ``--field`` write is still caught."""
    name_to_value = {suffix_var: "field"}
    seg = ["gh", "api", "repos/x/y", f"--${suffix_var}", "name=value"]
    assert checker._gh_api_field_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(
    method=st.sampled_from(["post", "put", "patch", "delete"]),
    flag_var=_IDENTIFIERS,
    value_var=_IDENTIFIERS,
    flag_name=st.sampled_from(["-x", "--method"]),
)
def test_gh_api_method_flagname_dynamic_hit_detects_flagname_and_value_both_dynamic(
    method: str, flag_var: str, value_var: str, flag_name: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, fifth round (issue #1326):
    ``F=-X; M=POST; gh api .../merge $F $M`` resolved to a real write and
    was wrongly allowed -- neither the flag nor its value carried any
    literal flag-shaped text in its own token, so every prior scan (which
    all key off a literal text prefix somewhere in the token) missed it
    entirely."""
    assume(flag_var != value_var)  # distinct dict keys -- see the same guard below
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]
    name_to_value = {flag_var: flag_name, value_var: method}
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), flag_var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_detects_dynamic_flagname_literal_value(method: str, flag_var: str) -> None:
    """Model-based: the same bypass class also holds when only the flag
    NAME is hidden behind a variable and the value stays a literal token
    (``F=-X; gh api .../merge $F POST``)."""
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", method]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {flag_var: "-x"}, {})


@_PROPERTIES
@given(flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_allows_a_dynamic_flagname_resolved_to_a_read(
    flag_var: str, value_var: str
) -> None:
    """No false positive: a dynamic flag-name token that resolves to
    -X/--method, followed by a value that resolves to GET (not one of the
    four write methods), is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]
    assert not checker._gh_api_method_flagname_dynamic_hit(seg, {flag_var: "-x", value_var: "get"}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a bare variable reference that does not resolve
    to -X/--method at all is never treated as a flag."""
    seg = ["gh", "api", "repos/x/y", f"${var}", "POST"]
    assert not checker._gh_api_method_flagname_dynamic_hit(seg, {var: "repos/x/y"}, {})


@_PROPERTIES
@given(flag_var=_IDENTIFIERS, flag_name=st.sampled_from(["-f", "--field", "--raw-field"]))
def test_gh_api_field_flagname_dynamic_hit_detects_every_flag_name(flag_var: str, flag_name: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, fifth round (issue #1326):
    ``FF=--field; gh api repos/o/r/pulls/1 $FF name=value`` resolved to a
    real write and was wrongly allowed. This rule never inspects the
    field VALUE, only the flag's presence -- matching
    ``_gh_api_field_literal_hit``'s own scope."""
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", "name=value"]
    assert checker._gh_api_field_flagname_dynamic_hit(seg, {flag_var: flag_name}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_field_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a bare variable reference that does not resolve
    to a field flag at all is never treated as one."""
    seg = ["gh", "api", "repos/x/y", f"${var}"]
    assert not checker._gh_api_field_flagname_dynamic_hit(seg, {var: "repos/x/y"}, {})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_flagname_and_value_both_dynamic(method: str, flag_var: str, value_var: str) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the fifth-round bypass is caught at the
    orchestrator level, not just the sub-pass level."""
    assume(flag_var != value_var)  # distinct dict keys, same guard as the sub-pass test above
    segments = [["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]]
    name_to_value = {flag_var: "-x", value_var: method}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${flag_var} ${value_var}", name_to_value, {})
    assert result is not None


@_PROPERTIES
@given(flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_flagname_dynamic_resolved_to_a_read(flag_var: str, value_var: str) -> None:
    """No false positive at the orchestrator level: a dynamic flag-name
    token resolved to -X, with its value resolved to GET, must stay
    allowed."""
    segments = [["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]]
    name_to_value = {flag_var: "-x", value_var: "get"}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${flag_var} ${value_var}", name_to_value, {})
    assert result is None


# --- Round 6: a write-method value split across multiple concatenated
# variables (issue #1326, found live by Step 8 independent review, sixth
# round). The round-5 fixes above resolved each referenced variable's
# value SEPARATELY and checked whether any one of them alone was a write
# method -- so `-X "$M1$M2"` with M1="po", M2="st" was never recognized,
# even though bash concatenates them into the single word "post" with no
# separator. `_substitute_var_refs_candidates` (reconstruct-then-check,
# possibly multiple readings -- see round 8 below) closes this.

_SPLIT_METHODS = st.sampled_from([("po", "st"), ("pos", "t"), ("p", "ost"), ("pu", "t"), ("pat", "ch"), ("del", "ete")])


@_PROPERTIES
@given(parts=_SPLIT_METHODS, name1=_IDENTIFIERS, name2=_IDENTIFIERS)
def test_substitute_var_refs_candidates_includes_concatenated_reading(
    parts: tuple[str, str], name1: str, name2: str
) -> None:
    """Model-based: a token made of two adjacent variable references
    always includes, among its readings, the concatenation of their
    assigned values in order -- the exact reconstruction real bash
    performs with no separator between adjacent `$NAME` expansions.
    (Other readings may also appear, e.g. if one name happens to be a
    string-prefix of the other -- see round 8 below -- so this checks
    membership, not exact equality.)"""
    assume(name1 != name2)
    part1, part2 = parts
    token = f"${name1}${name2}"
    candidates = checker._substitute_var_refs_candidates(token, {name1: part1, name2: part2}, {})
    assert candidates is not None
    assert part1 + part2 in candidates


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES, prefix=_VALUES, suffix=_VALUES)
def test_substitute_var_refs_candidates_preserves_surrounding_literal_text(
    name: str, value: str, prefix: str, suffix: str
) -> None:
    """Model-based: literal text around a BRACED reference is preserved
    verbatim in the reconstructed reading -- a braced reference carries no
    quote-boundary ambiguity (the brace itself survives shlex's quote
    removal), so it always contributes exactly one candidate."""
    token = f"{prefix}${{{name}}}{suffix}"
    candidates = checker._substitute_var_refs_candidates(token, {name: value.lower()}, {})
    assert candidates == [f"{prefix}{value.lower()}{suffix}"]


@_PROPERTIES
@given(name=_IDENTIFIERS, assigned_name=_IDENTIFIERS, value=_VALUES)
def test_substitute_var_refs_candidates_empty_for_an_unassigned_reference(
    name: str, assigned_name: str, value: str
) -> None:
    """No false positive: a token whose second reference has no
    assigned-and-in-range reading at all (not even via a shorter prefix)
    cannot be soundly resolved -- returns `[]` rather than silently
    substituting a placeholder or skipping the reference."""
    assume(name != assigned_name)
    assume(not name.startswith(assigned_name))
    token = f"${assigned_name}${name}"
    assert checker._substitute_var_refs_candidates(token, {assigned_name: value.lower()}, {}) == []


@_PROPERTIES
@given(parts=_SPLIT_METHODS, var1=_IDENTIFIERS, var2=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_detects_a_value_split_across_two_variables(
    parts: tuple[str, str], var1: str, var2: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, sixth round (issue #1326):
    ``M1=PO; M2=ST; gh api .../merge -X "$M1$M2"`` resolves (via real bash
    string concatenation) to a real ``POST`` write and was wrongly
    allowed -- neither "po" nor "st" alone is a write method, so the
    round-5-era per-variable value check never recognized the
    concatenation."""
    assume(var1 != var2)
    part1, part2 = parts
    seg = ["gh", "api", "repos/x/y", "-X", f"${var1}${var2}"]
    assert checker._gh_api_method_dynamic_hit(seg, {var1: part1, var2: part2}, {})


@_PROPERTIES
@given(parts=_SPLIT_METHODS, flag_var=_IDENTIFIERS, var1=_IDENTIFIERS, var2=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_detects_flagname_and_concatenated_value(
    parts: tuple[str, str], flag_var: str, var1: str, var2: str
) -> None:
    """Model-based: the same concatenation gap also holds when the flag
    NAME is simultaneously hidden behind its own bare variable reference
    (``F=-X; M1=PO; M2=ST; gh api .../merge $F "$M1$M2"``) -- the
    combination of round 5's and round 6's own findings."""
    assume(len({flag_var, var1, var2}) == 3)
    part1, part2 = parts
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"${var1}${var2}"]
    name_to_value = {flag_var: "-x", var1: part1, var2: part2}
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(var1=_IDENTIFIERS, var2=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_a_concatenated_value_resolved_to_a_read(var1: str, var2: str) -> None:
    """No false positive: a concatenated value that resolves to GET, not
    one of the four write methods, is never flagged."""
    assume(var1 != var2)
    seg = ["gh", "api", "repos/x/y", "-X", f"${var1}${var2}"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var1: "ge", var2: "t"}, {})


@_PROPERTIES
@given(parts=_SPLIT_METHODS, var1=_IDENTIFIERS, var2=_IDENTIFIERS)
def test_rule_gh_api_write_detects_a_method_value_split_across_two_variables(
    parts: tuple[str, str], var1: str, var2: str
) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the sixth-round concatenation bypass is caught
    at the orchestrator level too, not just the sub-pass level."""
    assume(var1 != var2)
    part1, part2 = parts
    segments = [["gh", "api", "repos/x/y", "-X", f"${var1}${var2}"]]
    name_to_value = {var1: part1, var2: part2}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var1}${var2}", name_to_value, {})
    assert result is not None


# --- Round 7: an uppercase literal fragment fused with a variable in the
# SAME token (issue #1326, found live by Step 8 independent review,
# seventh round). `_substitute_var_refs_candidates` preserves a token's
# literal text exactly as typed -- only the substituted variable values are
# already-lowercased -- so `-X "PO$M"` with `M=ST` (lowered to "st")
# reconstructs to "POst", not "post". Every round-6 test above used a
# whole-variable-per-fragment split (`M1=PO; M2=ST`), which happens to
# already be all-lowercase after `_assigned_literals`'s own lowercasing,
# so this gap went unexercised until this round.

_UPPER_LITERAL_SPLIT_METHODS = st.sampled_from(
    [("PO", "st"), ("POS", "t"), ("P", "ost"), ("PU", "t"), ("PAT", "ch"), ("DEL", "ete")]
)


@_PROPERTIES
@given(parts=_UPPER_LITERAL_SPLIT_METHODS, var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_detects_uppercase_literal_fragment_fused_with_variable(
    parts: tuple[str, str], var: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, seventh round (issue #1326): the write-method
    comparison must lowercase the reconstructed string before comparing,
    not rely on the substituted variable values alone already being
    lowercased."""
    literal, var_value = parts
    seg = ["gh", "api", "repos/x/y", "-X", f"{literal}${var}"]
    assert checker._gh_api_method_dynamic_hit(seg, {var: var_value}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_uppercase_literal_fragment_resolved_to_a_read(var: str) -> None:
    """No false positive: an uppercase literal fragment fused with a
    variable that resolves to a read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", "-X", f"GE${var}"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var: "t"}, {})


@_PROPERTIES
@given(parts=_UPPER_LITERAL_SPLIT_METHODS, flag_var=_IDENTIFIERS, var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_detects_uppercase_literal_fragment_fused_with_variable(
    parts: tuple[str, str], flag_var: str, var: str
) -> None:
    """Same regression pin at the flag-name-indirection sub-pass level
    (round 5's finding combined with round 7's)."""
    assume(flag_var != var)
    literal, var_value = parts
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"{literal}${var}"]
    name_to_value = {flag_var: "-x", var: var_value}
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(parts=_UPPER_LITERAL_SPLIT_METHODS, var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_uppercase_literal_fragment_fused_with_variable(
    parts: tuple[str, str], var: str
) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the seventh-round case-normalization bypass is
    caught at the orchestrator level too, not just the sub-pass level."""
    literal, var_value = parts
    segments = [["gh", "api", "repos/x/y", "-X", f"{literal}${var}"]]
    name_to_value = {var: var_value}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {literal}${var}", name_to_value, {})
    assert result is not None


# --- Round 8: an unbraced reference immediately followed by more
# identifier-shaped literal text (issue #1326, found live by Step 8
# independent review, eighth round). shlex's own quote removal discards
# WHICH characters were originally inside quotes -- `"$M"ST` (a quoted,
# bounded reference to `M` followed by literal `ST`) and `$MST` (a bare,
# unquoted reference to a variable literally named `MST`) both dequote to
# the identical raw token text `$MST`. The prior single-greedy-match
# resolution always assumed the maximal-munch (unquoted) reading, so
# `M=PO; gh api .../merge -X"$M"ST` -- a real `-XPOST` write, confirmed
# via `bash -c` argv expansion -- was wrongly allowed. Closed by trying
# every non-empty prefix of an unbraced identifier run as a candidate
# variable name.


@_PROPERTIES
@given(parts=_SPLIT_METHODS, var=_IDENTIFIERS, suffix=_VALUES)
def test_substitute_var_refs_candidates_includes_the_bounded_prefix_reading(
    parts: tuple[str, str], var: str, suffix: str
) -> None:
    """Model-based: for an unbraced reference immediately followed by more
    identifier-shaped text, the reading that treats the reference as
    BOUNDED at the assigned variable name (with the trailing text kept as
    a literal suffix) is always among the candidates -- not just the
    reading that treats the whole run as one (unassigned) variable name."""
    part1, part2 = parts
    token = f"${var}{part2}{suffix}"
    candidates = checker._substitute_var_refs_candidates(token, {var: part1}, {})
    assert candidates is not None
    assert part1 + part2 + suffix in candidates


@_PROPERTIES
@given(parts=_SPLIT_METHODS, var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_detects_unbraced_reference_followed_by_more_identifier_text(
    parts: tuple[str, str], var: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighth round (issue #1326): the classifier must
    catch a write method hidden behind the bounded-reference reading, not
    only the maximal-munch reading of an unbraced `$NAME` run."""
    part1, part2 = parts
    seg = ["gh", "api", "repos/x/y", "-X", f"${var}{part2}"]
    assert checker._gh_api_method_dynamic_hit(seg, {var: part1}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_unbraced_reference_followed_by_more_identifier_text_read(var: str) -> None:
    """No false positive: the bounded-reference reading resolving to a
    read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", "-X", f"${var}T"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var: "ge"}, {})


@_PROPERTIES
@given(parts=_SPLIT_METHODS, flag_var=_IDENTIFIERS, var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_detects_unbraced_reference_followed_by_more_identifier_text(
    parts: tuple[str, str], flag_var: str, var: str
) -> None:
    """Same regression pin at the flag-name-indirection sub-pass level
    (round 5's finding combined with round 8's)."""
    assume(flag_var != var)
    part1, part2 = parts
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"${var}{part2}"]
    name_to_value = {flag_var: "-x", var: part1}
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value, {})


@_PROPERTIES
@given(parts=_SPLIT_METHODS, var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_unbraced_reference_followed_by_more_identifier_text(
    parts: tuple[str, str], var: str
) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the eighth-round quote-boundary bypass is
    caught at the orchestrator level too, not just the sub-pass level."""
    part1, part2 = parts
    segments = [["gh", "api", "repos/x/y", "-X", f"${var}{part2}"]]
    name_to_value = {var: part1}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}{part2}", name_to_value, {})
    assert result is not None


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_write_method_candidate_hit_true_for_none_candidates(var: str) -> None:
    """Direct coverage of the fail-closed branch: `_write_method_candidate_
    hit` treats `None` (too many candidate readings to enumerate) as a
    hit, not a silently-dropped possibility."""
    assert checker._write_method_candidate_hit(None)


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_write_method_candidate_hit_false_for_empty_candidates(var: str) -> None:
    """No false positive: an empty candidate list (nothing resolvable at
    all) is never treated as a hit."""
    assert not checker._write_method_candidate_hit([])


# --- Round 8 (continued): the flag NAME itself hidden behind a variable
# FUSED directly with its own value in the SAME token (issue #1326, found
# live by Step 8 independent review, eighth round, immediately after the
# plain quote-boundary-ambiguity case above). `F=-X; gh api ... "$F"POST`
# dequotes to the single token `$FPOST` -- neither the bare-anchored
# flag-name check (round 5) nor the literal-"-x"-prefix dynamic-value
# check (round 2/6/7/8) recognizes this shape, since the flag character
# itself is not literally present anywhere in the token's own text.


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), var=_IDENTIFIERS)
def test_gh_api_method_fused_flagname_dynamic_hit_detects_flagname_and_value_fused_in_one_token(
    method: str, var: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighth round (issue #1326): a token that is
    PURELY a variable reference resolving to "-x", immediately followed
    (in the same token) by a write-method value, is still caught."""
    seg = ["gh", "api", "repos/x/y", f"${var}{method.upper()}"]
    assert checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "-x"}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_fused_flagname_dynamic_hit_allows_a_read_method(var: str) -> None:
    """No false positive: the fused flag-plus-value reading resolving to a
    read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", f"${var}GET"]
    assert not checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "-x"}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_fused_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a dynamic token whose resolved value does not
    start with "-x"/"--method=" at all is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${var}issues"]
    assert not checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "repos/owner"}, {})


@_PROPERTIES
@given(flag_shape=st.sampled_from([("-f", ""), ("--field", "="), ("--raw-field", "=")]), var=_IDENTIFIERS)
def test_gh_api_field_fused_flagname_dynamic_hit_detects_flagname_and_value_fused_in_one_token(
    flag_shape: tuple[str, str], var: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighth round (issue #1326), the field-flag
    counterpart of the method-flag finding above: a token that is PURELY
    a variable reference resolving to a field flag, immediately followed
    (in the same token) by a field payload, is still caught. This rule
    never inspects the field VALUE, only the flag's presence.

    ``flag_shape``'s own separator mirrors real gh/pflag syntax exactly
    the way ``_gh_api_field_literal_hit``'s three shapes already do: the
    short flag ``-f`` fuses directly onto its value with no separator,
    while the long flags ``--field``/``--raw-field`` require the literal
    ``=`` -- fusing ``--field`` directly onto ``name=value`` with no
    ``=`` produces a DIFFERENT (invalid, gh-rejected) flag name, not a
    real field write, so that shape is correctly not flagged."""
    flag_name, separator = flag_shape
    seg = ["gh", "api", "repos/x/y", f"${var}{separator}name=value"]
    assert checker._gh_api_field_fused_flagname_dynamic_hit(seg, {var: flag_name}, {})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_field_fused_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a dynamic token whose resolved value does not
    start with a field-flag shape at all is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${var}issues"]
    assert not checker._gh_api_field_fused_flagname_dynamic_hit(seg, {var: "repos/owner"}, {})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_fused_flagname_and_value_in_one_token(method: str, var: str) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the eighth-round fused-flagname bypass is
    caught at the orchestrator level too, not just the sub-pass level."""
    token = f"${var}{method.upper()}"
    segments = [["gh", "api", "repos/x/y", token]]
    name_to_value = {var: "-x"}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", name_to_value, {})
    assert result is not None


# --- Round 9: bash's own `${NAME:-default}`/`${NAME-default}`/
# `${NAME:=default}`/`${NAME=default}` parameter-expansion (issue #1326,
# found live by Step 8 independent review, ninth round). This embeds
# literal text directly in a token with NO variable assignment anywhere
# in the command at all -- `gh api .../merge -X${TOTALLY_NEVER_MENTIONED-
# POST}` resolves (real bash, confirmed via argv expansion) to a real
# `-XPOST` write, and `${NEVER_SET:-uv} ${NEVER_SET2:-install} foo`
# resolves to a real `uv install foo`, fully bypassing even the most
# basic install-verb detection (B1a/B1b), not just the gh-api-specific
# checks every round 5-8 fix closed.

_DEFAULT_CLAUSE_OPERATORS = st.sampled_from([":-", "-", ":=", "="])


@_PROPERTIES
@given(name=_IDENTIFIERS, op=_DEFAULT_CLAUSE_OPERATORS, default=_VALUES)
def test_substitute_var_refs_candidates_extracts_the_default_text(name: str, op: str, default: str) -> None:
    """Model-based: a whole-token `${NAME<op>default}` construct, for
    every one of the four default-value operator shapes, yields the
    literal default text as its sole candidate reading when NAME itself
    is never assigned. Regression pin for the now-removed
    `_default_clause_literal` helper's own coverage -- its behavior lives
    on inside this function's own default-clause branch (round 11, issue
    #1326: B1a/B1b now call this function directly instead of that
    narrower, whole-token-anchored helper)."""
    assert checker._substitute_var_refs_candidates(f"${{{name}{op}{default}}}", {}, {}) == [default]


@_PROPERTIES
@given(prefix=_IDENTIFIERS, name=_IDENTIFIERS, default=_VALUES)
def test_substitute_var_refs_candidates_extracts_a_fused_default_clause(prefix: str, name: str, default: str) -> None:
    """Model-based regression pin for the eleventh-round finding: a
    default-clause construct FUSED with literal text in the SAME token
    (e.g. `in${NAME:-stall}`) still contributes a reconstructed candidate
    with the literal prefix preserved -- the whole-token-anchored
    `_default_clause_literal` this replaced could never see this shape at
    all, since the token as a whole is not exactly one construct."""
    assert checker._substitute_var_refs_candidates(f"{prefix}${{{name}:-{default}}}", {}, {}) == [prefix + default]


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), name=_IDENTIFIERS, op=_DEFAULT_CLAUSE_OPERATORS)
def test_gh_api_method_dynamic_hit_detects_a_default_clause_write_method(method: str, name: str, op: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): a write method
    embedded as a `${NAME:-default}` fallback, with NO assignment for
    NAME anywhere, is still caught."""
    seg = ["gh", "api", "repos/x/y", f"-X${{{name}{op}{method.upper()}}}"]
    assert checker._gh_api_method_dynamic_hit(seg, {}, {})


@_PROPERTIES
@given(name=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_a_default_clause_read_method(name: str) -> None:
    """No false positive: a default-clause value resolving to a read
    method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", f"-X${{{name}-GET}}"]
    assert not checker._gh_api_method_dynamic_hit(seg, {}, {})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), name=_IDENTIFIERS)
def test_rule_gh_api_write_detects_a_default_clause_write_method(method: str, name: str) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the ninth-round default-clause bypass is
    caught at the orchestrator level too, not just the sub-pass level."""
    token = f"-X${{{name}-{method.upper()}}}"
    segments = [["gh", "api", "repos/x/y", token]]
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", {}, {})
    assert result is not None


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1a_detects_a_default_clause_verb(tool_var: str, verb_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): a watched verb
    embedded as a `${NAME:-default}` fallback in a later segment token
    (with the command word itself also dynamic) is still caught, even
    though neither variable is ever assigned."""
    seg = [f"${{{tool_var}:-uv}}", f"${{{verb_var}:-install}}", "pkg"]
    assert checker._rule_b1a_dynamic_word_same_segment_verb(seg, checker._WATCHED_VERBS, {}, {})


@_PROPERTIES
@given(tool_var=_IDENTIFIERS, verb_var=_IDENTIFIERS)
def test_rule_b1b_detects_a_default_clause_tool_and_verb(tool_var: str, verb_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, ninth round (issue #1326): both the tool AND
    the verb hidden behind their own `${NAME:-default}` fallback (NO
    assignment for either variable anywhere) are still caught."""
    assume(tool_var != verb_var)
    seg = [f"${{{tool_var}:-uv}}", f"${{{verb_var}:-install}}", "pkg"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, {}, checker._WATCHED_VERBS, {})


@_PROPERTIES
@given(tool_var=_IDENTIFIERS)
def test_rule_b1a_allows_an_unrelated_default_clause_argument(tool_var: str) -> None:
    """No false positive: a dynamic command word with a default-clause
    argument that resolves to something unrelated to any watched verb
    must stay allowed."""
    seg = [f"${{{tool_var}:-cat}}", "${OTHER:-somefile.txt}"]
    assert not checker._rule_b1a_dynamic_word_same_segment_verb(seg, checker._WATCHED_VERBS, {}, {})


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES, other=_VALUES)
def test_resolve_seg_tokens_candidates_ignores_literal_tokens(name: str, value: str, other: str) -> None:
    """Model-based: only DYNAMIC tokens contribute a candidate reading --
    a plain literal token is skipped outright, matching every direct
    caller's own pre-seeded-literals convention (B1a) or empty-start
    convention (B1b, `_rule_git_push`). Direct coverage for the helper
    factored out of B1a/B1b/`_rule_git_push`'s own byte-identical loop
    (round 12, issue #1326)."""
    name_to_value = {name: value.lower()}
    result = checker._resolve_seg_tokens_candidates([other, f"${name}"], name_to_value, {})
    assert result == {value.lower()}


@_PROPERTIES
@given(literals=st.lists(_VALUES, max_size=3))
def test_resolve_seg_tokens_candidates_empty_set_for_all_literal_tokens(literals: list[str]) -> None:
    """No false positive: a token list with no dynamic tokens at all
    resolves to an empty set, not None -- there is nothing unresolved to
    fail closed on."""
    assert checker._resolve_seg_tokens_candidates(literals, {}, {}) == set()


@_PROPERTIES
@given(suf_ref=_IDENTIFIERS, suf_var=_IDENTIFIERS)
def test_rule_b1a_detects_a_verb_fused_with_a_literal_prefix_via_indirect_ref(suf_ref: str, suf_var: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eleventh round (issue #1326): a watched verb
    reconstructed by fusing literal text with an `${!NAME}` indirect
    reference in the SAME token (`in${!SUFREF}` where SUFREF resolves,
    two levels, to "stall") is still caught -- confirmed via real bash
    argv expansion that `$T in${!SUFREF} foo` resolves to a genuine `uv
    install foo`. The whole-token-anchored helpers this rule used through
    the tenth round could never see this shape at all."""
    assume(suf_ref != suf_var)
    name_to_raw_value = {suf_ref: suf_var}
    name_to_value = {suf_var: "stall"}
    seg = ["$T", f"in${{!{suf_ref}}}", "foo"]
    assert checker._rule_b1a_dynamic_word_same_segment_verb(
        seg, checker._WATCHED_VERBS, name_to_value, name_to_raw_value
    )


@_PROPERTIES
@given(h_ref=_IDENTIFIERS, h_var=_IDENTIFIERS, m_ref=_IDENTIFIERS, m_var=_IDENTIFIERS)
def test_rule_b1b_detects_a_tool_and_verb_each_fused_with_a_literal_prefix(
    h_ref: str, h_var: str, m_ref: str, m_var: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eleventh round (issue #1326): both the tool AND
    the verb, each reconstructed by fusing literal text with a resolved
    reference in its OWN token, are still caught -- confirmed via real
    bash argv expansion (`g${!HREF} pr m${!MREF} 1` resolves to a genuine
    `gh pr merge 1`). Neither "gh" nor "merge" is ever a plain literal
    token here -- B1b (unlike B1a) only ever collects values from
    dynamic, resolved tokens, so both fused reconstructions must succeed
    independently for this to fire."""
    assume(len({h_ref, h_var, m_ref, m_var}) == 4)
    name_to_raw_value = {h_ref: h_var, m_ref: m_var}
    name_to_value = {h_var: "h", m_var: "erge"}
    seg = [f"g${{!{h_ref}}}", "pr", f"m${{!{m_ref}}}"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(
        seg, name_to_value, checker._WATCHED_VERBS, name_to_raw_value
    )


@_PROPERTIES
@given(command=st.sampled_from(["${NEVER_SET:-uv} install foo", "${NEVER_SET:-uv} ${NEVER_SET2:-install} foo"]))
def test_classify_denies_default_clause_tool_verb_bypass(command: str) -> None:
    """End-to-end regression pin at the classify() level: the exact
    zero-assignment bypass reported live, confirmed via real bash to
    resolve to a genuine ``uv install foo``."""
    assert checker.classify(command).deny


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
    assert checker._is_git_push_segment(seg, {})


@_PROPERTIES
@given(subcommand=st.sampled_from(["status", "commit", "log", "diff", "fetch", "clone"]))
def test_is_git_push_segment_false_for_a_non_push_subcommand(subcommand: str) -> None:
    """No false positive: an ordinary git subcommand that is not push,
    with no literal 'git push' substring anywhere in the segment, is
    never misdetected."""
    seg = ["git", subcommand, "--short"]
    assert not checker._is_git_push_segment(seg, {})


@_PROPERTIES
@given(tokens=st.lists(st.text(max_size=15), max_size=6))
def test_is_git_push_segment_never_raises_on_arbitrary_tokens(tokens: list[str]) -> None:
    """Robustness: arbitrary token content (including tokens containing
    ``$``/backtick, empty strings, or unicode) never raises -- this
    function classifies untrusted, attacker-shaped Bash tokens."""
    result = checker._is_git_push_segment(tokens, {})
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
    assert checker._is_git_push_segment(["git", flag, "push", "origin"], {})


@_PROPERTIES
@given(flag=st.sampled_from(["-v", "-h", "-p", "-P"]), subcommand=st.sampled_from(["log", "status", "diff"]))
def test_is_git_push_segment_false_for_boolean_short_flag_before_non_push_subcommand(
    flag: str, subcommand: str
) -> None:
    """No false positive: a boolean short flag before an ordinary,
    non-push subcommand is never misdetected as git push."""
    assert not checker._is_git_push_segment(["git", flag, subcommand], {})


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
    assert not checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS, {})


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
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS, {})


@_PROPERTIES
@given(gh_var=_IDENTIFIERS, api_var=_IDENTIFIERS)
def test_rule_b1b_detects_gh_api_indirection(gh_var: str, api_var: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, fourth round (issue #1326): `G=gh; A=api; $G $A
    ... -X POST` was wrongly allowed, since "api" was never in
    `_WATCHED_VERBS` -- `gh api` write detection lived entirely in the
    separately-dispatched `_rule_gh_api_write`, never wired into the
    B-rule indirection machinery B1a/B1b already use for `gh issue`/
    `gh pr` write-subcommand indirection. Once BOTH `gh` and `api` are
    hidden behind variables, this is denied outright -- without
    inspecting whether the resolved call would have been a read or a
    write."""
    if gh_var == api_var:
        return
    name_to_value = {gh_var: "gh", api_var: "api"}
    seg = [f"${gh_var}", f"${api_var}", "repos/x/y", "-X", "POST"]
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS, {})


@_PROPERTIES
@given(flag=st.sampled_from(["--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"]))
def test_is_git_push_segment_true_for_long_flag_separate_token_form(flag: str) -> None:
    """Model-based, regression pin for a real bypass found live by Step 8
    independent review, fourth round (issue #1326): only the fused `=`
    form of git's value-taking long global options was ever handled --
    the separate-token form (`git --git-dir /tmp/repo push origin
    master`, confirmed to actually push with real git) went undetected,
    silently skipping the mandatory outward-artifact-preflight
    provenance scan this flag gates."""
    seg = ["git", flag, "/tmp/some/value", "push", "origin"]
    assert checker._is_git_push_segment(seg, {})


@_PROPERTIES
@given(flag=st.sampled_from(["--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"]))
def test_is_git_push_segment_true_for_long_flag_fused_equals_form(flag: str) -> None:
    """No regression: the fused `=` form these long flags already
    handled correctly continues to work after adding separate-token
    support alongside it."""
    seg = ["git", f"{flag}=/tmp/some/value", "push", "origin"]
    assert checker._is_git_push_segment(seg, {})


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_raw_values_captures_name_equals_value_rhs_case_preserved(name: str, value: str) -> None:
    """Model-based: `_assigned_raw_values` maps a bare assignment token's
    name to its RHS with the ORIGINAL case preserved -- unlike
    `_assigned_literals`, which lowercases it. `${!NAME}` indirect
    reference resolution needs a case-correct key for its first-level
    lookup (issue #1326, tenth round; see `_resolve_indirect_ref`)."""
    result = checker._assigned_raw_values([f"{name}={value}"])
    assert result.get(name) == value


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_assigned_raw_values_ignores_a_dynamic_rhs_token(name: str, value: str) -> None:
    """Same dynamic-RHS exclusion as `_assigned_literals` -- a token
    containing `$` is skipped outright before `_ASSIGN_RE` is consulted."""
    result = checker._assigned_raw_values([f"{name}=${value}"])
    assert result == {}


@_PROPERTIES
@given(name1=_IDENTIFIERS, name2=_IDENTIFIERS, value=_VALUES)
def test_substitute_var_refs_candidates_resolves_an_indirect_ref_two_level_lookup(
    name1: str, name2: str, value: str
) -> None:
    """Model-based regression pin for the tenth-round finding: `${!NAME1}`
    resolves via NAME1's own (case-preserved) value naming NAME2, whose
    own (lowercased) assigned value is the final result -- confirmed live
    against real bash argv expansion (`TOOLREF=T; T=uv; ${!TOOLREF}`
    resolves to a genuine `uv`). Regression pin for the now-removed
    `_resolve_indirect_ref` helper's own coverage -- its behavior lives on
    inside this function's own indirect-reference branch (round 12, issue
    #1326: `_resolve_indirect_ref`, `_resolve_bare_var`, and
    `_resolve_bare_or_indirect` were all removed once
    `_substitute_var_refs_candidates` became the flag-NAME resolver too,
    leaving them with zero remaining callers)."""
    assume(name1 != name2)
    name_to_raw_value = {name1: name2}
    name_to_value = {name2: value.lower()}
    assert checker._substitute_var_refs_candidates(f"${{!{name1}}}", name_to_value, name_to_raw_value) == [
        value.lower()
    ]


@_PROPERTIES
@given(name=_IDENTIFIERS)
def test_substitute_var_refs_candidates_empty_when_indirect_ref_first_level_unresolved(name: str) -> None:
    """When NAME was never assigned at all, the first-level lookup fails
    and the whole `${!NAME}` token cannot be soundly resolved at all."""
    assert checker._substitute_var_refs_candidates(f"${{!{name}}}", {}, {}) == []


@_PROPERTIES
@given(prefix_var=_IDENTIFIERS, suffix_var=_IDENTIFIERS, value=_VALUES)
def test_substitute_var_refs_candidates_resolves_a_flag_name_fused_indirect_ref(
    prefix_var: str, suffix_var: str, value: str
) -> None:
    """Model-based regression pin for the real bypass found live by Step 8
    independent review, twelfth round (issue #1326): a flag NAME
    reconstructed by fusing a literal `--` prefix with an `${!NAME}`
    indirect reference in the SAME token still resolves correctly through
    the general primitive -- the same class of fusion round eleven closed
    for B1a/B1b/etc. but round eleven's own dedup left open for the
    gh-api flag-NAME path specifically, under the (wrong) premise that a
    flag name is never fused with other text."""
    assume(prefix_var != suffix_var)
    name_to_raw_value = {prefix_var: suffix_var}
    name_to_value = {suffix_var: value.lower()}
    assert checker._substitute_var_refs_candidates(f"--${{!{prefix_var}}}", name_to_value, name_to_raw_value) == [
        "--" + value.lower()
    ]


# --- Issue #1326 Stage 1, fourteenth round: command-substitution folding ----
# and the recursive inner-content check this round added --------------------


@_PROPERTIES
@given(a=_IDENTIFIERS, b=_IDENTIFIERS)
def test_command_substitution_token_span_finds_the_matching_close_paren(a: str, b: str) -> None:
    """Model-based: a `$`-suffixed opener token immediately followed by a
    `(` token returns the index one past the matching `)`, tracking
    nesting depth across the intervening tokens -- shared by
    ``_fold_command_substitution_spans`` and ``_rule_command_substitution_
    content``, added by Step 8 independent review, fourteenth round (issue
    #1326), ported from the task-scoped sibling module's own function of
    the same name."""
    tokens = ["x=$", "(", a, b, ")", "trailing"]
    assert checker._command_substitution_token_span(tokens, 0) == 5


@_PROPERTIES
@given(a=_IDENTIFIERS)
def test_command_substitution_token_span_none_for_a_non_opener(a: str) -> None:
    """No false positive: a token that does not end with `$`, or is not
    immediately followed by a `(` token, never starts a span."""
    assert checker._command_substitution_token_span([a, "(", "y", ")"], 0) is None


@_PROPERTIES
@given(a=_IDENTIFIERS, inner=_IDENTIFIERS)
def test_fold_command_substitution_spans_merges_into_one_dynamic_token(a: str, inner: str) -> None:
    """Model-based: an unquoted `$(...)` span (split by shlex into
    separate `$`/`(`/.../`)` tokens) folds into ONE opaque token that
    ``_is_dynamic`` still recognizes, keeping any literal text before or
    after it in its OWN, unmerged position."""
    tokens = [a, "$", "(", inner, ")"]
    folded = checker._fold_command_substitution_spans(tokens)
    assert folded == [a, f"$( {inner})"]
    assert checker._is_dynamic(folded[1])


@_PROPERTIES
@given(inner=_IDENTIFIERS)
def test_find_fused_command_substitution_extracts_the_quoted_span(inner: str) -> None:
    """Model-based: the QUOTED shape shlex leaves fused as one token
    (`"prefix $(cmd) suffix"` dequotes to one token) is found via a
    character-level scan, distinct from the unquoted, cross-token shape
    ``_command_substitution_token_span`` handles."""
    token = f"prefix $({inner}) suffix"
    fused = checker._find_fused_command_substitution(token)
    assert fused is not None
    start, end = fused
    assert token[start + 2 : end - 1] == inner


@_PROPERTIES
@given(verb=st.sampled_from(["install", "i", "add"]))
def test_is_unresolvable_substitution_detects_command_substitution(verb: str) -> None:
    """Model-based: a token containing `$(` (a command substitution) is
    always flagged unresolvable -- the narrow, position-specific guard
    used at the gh-api flag-name/flag-value checks, NOT inside the
    shared, whole-segment `_substitute_var_refs_candidates` primitive
    itself (see that function's own docstring for the false-positive
    history behind this split)."""
    assert checker._is_unresolvable_substitution(f"$( echo {verb})")


@_PROPERTIES
@given(value=_VALUES)
def test_is_unresolvable_substitution_allows_an_ordinary_dynamic_token(value: str) -> None:
    """No false positive: an ordinary `$NAME` reference (resolvable
    through `_substitute_var_refs_candidates`'s own machinery) is never
    flagged by this narrower check."""
    assert not checker._is_unresolvable_substitution(f"${value}")


@_PROPERTIES
@given(tool=st.sampled_from(["pip", "uv"]))
def test_rule_command_substitution_content_detects_an_embedded_install(tool: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, fourteenth round (issue #1326): a BARE,
    unassigned, unquoted `$(...)` occupying the ENTIRE command position
    has its own OUTPUT word-split and re-executed as a brand-new command
    by bash -- bash genuinely RUNS a `$(...)` substitution's own inner
    content the instant it is evaluated, so an install command embedded
    inside one is just as dangerous as at the top level. `x=$` (not `x`,
    `=`, `$` as separate tokens) matches real shlex output -- `=` is not
    a punctuation character shlex breaks a word at, so an assignment's
    `NAME=` prefix stays fused onto the leading `$` in the same token."""
    tokens = ["x=$", "(", tool, "install", "evil-pkg", ")"]
    reason, _, _ = checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


@_PROPERTIES
@given(value=_VALUES)
def test_rule_command_substitution_content_allows_harmless_inner_content(value: str) -> None:
    """No false positive: a `$(...)` substitution whose own inner content
    is an ordinary, harmless command (not itself a denied pattern) is
    never flagged by this recursive check. Returns a `(None, is_git_push)`
    tuple, not a bare `None`, when nothing is found -- found live by Step
    8 independent review, fifteenth round (issue #1326): an earlier
    version of this function returned a bare reason string or `None`,
    silently dropping a non-denying inner `is_git_push=True` signal (see
    the function's own docstring)."""
    tokens = ["echo", "$", "(", "date", value, ")"]
    assert checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


# --- Issue #1326 Stage 1, fifteenth round: bash's own leading-assignment ----
# prefix and array-literal syntax, both found to defeat every seg[0]-anchored
# rule with no indirection technique at all -------------------------------


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES, tail=st.lists(_IDENTIFIERS, max_size=3))
def test_strip_leading_assignments_removes_one_prefix(name: str, value: str, tail: list[str]) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, fifteenth round (issue #1326): a leading
    `NAME=value` environment-assignment token is stripped, revealing the
    REAL command word at `seg[0]` for every rule that indexes it --
    confirmed live via a real bash proxy that `X=foo $T install foo`
    (T=uv) and `X=foo uv $x foo` (x=install) both fully bypassed B1a/
    B1b's own indirection detection before this fix."""
    seg = [f"{name}={value}", *tail]
    assert checker._strip_leading_assignments(seg) == tail


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_strip_leading_assignments_empty_for_assignment_only_segment(name: str, value: str) -> None:
    """Robustness: a segment consisting ENTIRELY of assignment tokens (no
    command word at all, e.g. a bare `X=1` statement) strips to an empty
    list, not a crash or a stray leftover token."""
    assert checker._strip_leading_assignments([f"{name}={value}"]) == []


@_PROPERTIES
@given(tool=_IDENTIFIERS, tail=st.lists(_IDENTIFIERS, min_size=1, max_size=3))
def test_strip_leading_assignments_no_op_without_a_leading_assignment(tool: str, tail: list[str]) -> None:
    """No false positive: a segment whose own first token is NOT
    assignment-shaped is returned unchanged."""
    seg = [tool, *tail]
    assert checker._strip_leading_assignments(seg) == seg


@_PROPERTIES
@given(name=_IDENTIFIERS, inner=_IDENTIFIERS)
def test_array_literal_token_span_finds_the_matching_close_paren(name: str, inner: str) -> None:
    """Model-based: a bare `NAME=` (empty-value) assignment token
    immediately followed by `(` -- bash's own array-literal syntax --
    returns the index one past the matching `)`."""
    tokens = [f"{name}=", "(", inner, ")", "trailing"]
    assert checker._array_literal_token_span(tokens, 0) == 4


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES, inner=_IDENTIFIERS)
def test_array_literal_token_span_none_for_a_non_empty_assignment(name: str, value: str, inner: str) -> None:
    """No false positive: an ordinary `NAME=value` assignment (non-empty
    value) immediately followed by `(` is NOT array-literal syntax."""
    assume(value)
    tokens = [f"{name}={value}", "(", inner, ")"]
    assert checker._array_literal_token_span(tokens, 0) is None


@_PROPERTIES
@given(name=_IDENTIFIERS, inner=_IDENTIFIERS)
def test_fold_array_literal_spans_merges_a_dynamic_element_into_one_token(name: str, inner: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, fifteenth round (issue #1326), ported from the
    task-scoped sibling module's own fifteenth-round fix of the same
    finding: an array literal with a DYNAMIC element folds into ONE token
    still matching `_ASSIGN_RE`, so `_strip_leading_assignments` removes
    it entirely as an ordinary assignment -- confirmed live that
    `declare -a arr=($(seq 1 5))` was wrongly denied before this fix,
    once the array's own content became `seg[0]` of its own segment."""
    dynamic_inner = f"${inner}"
    tokens = [f"{name}=", "(", dynamic_inner, ")", "trailing"]
    folded = checker._fold_array_literal_spans(tokens)
    assert folded == [f"{name}=( {dynamic_inner})", "trailing"]
    assert checker._strip_leading_assignments(folded[:1]) == []


@_PROPERTIES
@given(name=_IDENTIFIERS, inner=_IDENTIFIERS)
def test_fold_array_literal_spans_merges_a_fully_literal_element_too(name: str, inner: str) -> None:
    """Model-based: as of the eighteenth round's own redesign (issue
    #1326), a FULLY LITERAL array element folds into one token exactly
    the same as a dynamic one -- this function no longer carries ANY
    content-safety responsibility (see its own docstring's Design
    history): `_rule_array_literal_content` independently, recursively
    classifies the array's own inner content BEFORE this fold ever runs,
    so the fold's downstream effect on `_strip_leading_assignments` is
    safe regardless of what the array contains."""
    tokens = [f"{name}=", "(", inner, ")", "trailing"]
    folded = checker._fold_array_literal_spans(tokens)
    assert folded == [f"{name}=( {inner})", "trailing"]
    assert checker._strip_leading_assignments(folded[:1]) == []


@_PROPERTIES
@given(name=_IDENTIFIERS)
def test_fold_array_literal_spans_empty_array_no_trailing_space(name: str) -> None:
    """No false positive / no crash: an EMPTY array literal (`NAME=()`)
    has no inner elements to space-join -- `middle` must fall back to the
    empty string, not a stray leading space."""
    tokens = [f"{name}=", "(", ")"]
    assert checker._fold_array_literal_spans(tokens) == [f"{name}=()"]


@_PROPERTIES
@given(name=_IDENTIFIERS, first=_IDENTIFIERS, second=_IDENTIFIERS)
def test_rule_array_literal_content_detects_a_denied_pair_regardless_of_a_leading_dynamic_element(
    name: str, first: str, second: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, seventeenth AND eighteenth rounds (issue
    #1326): a denied adjacent-verb pair sitting inside an array literal
    must be caught by this recursive content check regardless of what
    ELSE is in the array (a leading dynamic element used to hide it from
    every fold-conditional heuristic rounds 16-17 tried in turn) --
    `Y=1; A=(uv install $Y); "${A[@]}"` was wrongly ALLOWED before this
    function existed."""
    tokens = ["dummy=", "(", f"${first}", "uv", "install", f"${second}", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


@_PROPERTIES
@given(unset_name=_IDENTIFIERS, verb_a=st.sampled_from(["uv", "gh"]))
def test_rule_array_literal_content_collapses_a_leading_unassigned_bare_ref(unset_name: str, verb_a: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighteenth round (issue #1326): a leading bare
    `$NAME` reference to a variable never assigned anywhere in the
    command word-splits away to NOTHING at real bash runtime (confirmed
    live via `declare -p` against real bash), so the array's own REAL
    first surviving element is what actually lands at the position a
    `seg[0]`-anchored rule would see -- `A=($NEVERSET uv install);
    "${A[@]}" foo` was wrongly ALLOWED before this collapsed reading was
    checked. A dynamic token that IS assigned in the command, or is
    fused with other text (not a bare whole-token reference), must NOT
    be collapsed -- that shape does not word-split away to nothing."""
    tokens = ["dummy=", "(", f"${unset_name}", verb_a, "install", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_rule_array_literal_content_does_not_collapse_an_assigned_reference(name: str, value: str) -> None:
    """No false positive: a leading bare `$NAME` reference to a variable
    that genuinely IS assigned elsewhere in the command does not
    word-split away -- collapsing it would wrongly treat its own real,
    assigned value's position as if it were absent."""
    tokens = ["dummy=", "(", f"${name}", "echo", "harmless", ")"]
    assert checker._strip_leading_unassigned_bare_refs(tokens[2:4], {name: value}) == tokens[2:4]


def test_rule_array_literal_content_allows_harmless_content() -> None:
    """No false positive: an array literal whose own content matches no
    denied pattern, with or without a leading unassigned reference,
    stays allowed."""
    tokens = ["dummy=", "(", "$NEVERSET", "echo", "harmless", ")"]
    assert checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


def test_rule_array_literal_content_no_span_present() -> None:
    """Robustness: a token stream with no array-literal span at all
    (e.g. an ordinary command) returns cleanly, never a crash."""
    assert checker._rule_array_literal_content(["echo", "hi"], {}, {}, {}, {}, {}) == (None, False, ())


def test_strip_leading_unassigned_bare_refs_stops_at_a_fused_token() -> None:
    """No false positive: a token with anything ELSE fused onto the
    reference (not a bare, whole-token `$NAME`) does not word-split away
    to nothing even when the reference itself is unset -- the collapse
    only applies to a token that IS entirely one bare reference."""
    tokens = ["-X$NEVERSET", "trailing"]
    assert checker._strip_leading_unassigned_bare_refs(tokens, {}) == tokens


@_PROPERTIES
@given(a=_IDENTIFIERS, b=_IDENTIFIERS)
def test_strip_leading_unassigned_bare_refs_strips_the_whole_run(a: str, b: str) -> None:
    """Robustness: when EVERY token is an unassigned bare reference (no
    literal token to stop the run), the whole list collapses to empty,
    not a crash or a stray leftover."""
    tokens = [f"${a}", f"${b}"]
    assert checker._strip_leading_unassigned_bare_refs(tokens, {}) == []


def test_rule_array_literal_content_empty_array_is_harmless() -> None:
    """No false positive / no crash: an empty array literal `NAME=()`
    has no inner content to recursively classify at all."""
    tokens = ["dummy=", "(", ")"]
    assert checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


def test_rule_array_literal_content_skips_the_collapsed_reading_without_a_leading_unassigned_ref() -> None:
    """No false positive / no redundant work: an array literal whose own
    first element is NOT an unassigned bare reference has nothing for
    `_strip_leading_unassigned_bare_refs` to strip -- the collapsed
    reading equals the as-is one, so only one classification is needed."""
    tokens = ["dummy=", "(", "echo", "harmless", ")"]
    assert checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


def test_rule_array_literal_content_denies_only_on_the_collapsed_reading() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighteenth round (issue #1326): the AS-IS
    reading of `$NEVERSET uv $VERB` is harmless -- B2 (`_rule_b2_
    watched_tool_dynamic_verb_position`) requires a LITERAL `seg[0]`, and
    `$NEVERSET` being dynamic blocks it from ever firing, regardless of
    what follows (unlike `_rule_a_literal`'s own filtered-adjacency scan,
    which already sees through a leading dynamic decoy for a PAIR of
    literal tokens -- this collapse is specifically needed for a
    POSITION-anchored rule like B2). The COLLAPSED reading (`$NEVERSET`
    stripped away, since it is never assigned) puts `uv` at `seg[0]` for
    real, with a dynamic verb argument right after it -- exactly B2's own
    watched shape."""
    tokens = ["dummy=", "(", "$NEVERSET", "uv", "$VERB", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None
    assert "unassigned reference" in reason


@_PROPERTIES
@given(name1=_IDENTIFIERS, value1=_VALUES, name2=_IDENTIFIERS, value2=_VALUES, tail=st.lists(_IDENTIFIERS, max_size=2))
def test_classify_tokens_outer_scope_merges_with_the_recursed_tokens_own_assignments(
    name1: str, value1: str, name2: str, value2: str, tail: list[str]
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, nineteenth round (issue #1326): OUTER_NAME_TO_
    VALUE/OUTER_NAME_TO_RAW_VALUE's own entries are visible to a recursive
    `_classify_tokens` call's internal `assigned`/`raw_assigned`
    computation, alongside (not instead of) whatever TOKENS itself
    assigns -- a name TOKENS itself assigns must still win over an outer
    entry of the same name (ordinary shadowing), while a name only the
    outer scope assigns must still resolve. `A=($NEVERSET uv install);
    "${A[@]}" foo`-style outer-scope threading is exercised end to end
    elsewhere; this pins the merge/shadow semantics of the parameters
    themselves directly."""
    assume(name1 != name2)
    outer_literals = {name1: "outer-value-should-be-shadowed", name2: value2}
    outer_raw = {name1: "Outer-Value-Should-Be-Shadowed", name2: value2}
    tokens = [f"{name1}={value1}", *tail]
    verdict = checker._classify_tokens(tokens, outer_literals, outer_raw)
    assert verdict.reason == "no denied pattern matched"


@_PROPERTIES
@given(unset_name=_IDENTIFIERS, verb_a=st.sampled_from(["uv", "gh"]))
def test_rule_array_literal_content_collapses_a_leading_unassigned_braced_bare_ref(
    unset_name: str, verb_a: str
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, nineteenth round (issue #1326): a BRACED
    `${NAME}` decoy word-splits away to nothing at real bash runtime
    exactly the same as an unbraced `$NAME` decoy, once NAME is never
    assigned -- `_BARE_VAR_REF_RE` only matched the unbraced shape before
    this round, silently degrading the collapsed reading to a no-op for
    this shape."""
    tokens = ["dummy=", "(", f"${{{unset_name}}}", verb_a, "install", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


def test_rule_array_literal_content_detects_an_outer_scope_resolved_pair() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, nineteenth round (issue #1326): a tool/verb
    pair built from variables assigned OUTSIDE the array literal's own
    span (name_to_value's own entries, not anything `_assigned_literals`
    would find by re-scanning the array's own inner tokens alone) must
    still be caught -- `G=gh; P=pr; M=merge; A=($G $P $M); "${A[@]}" 1`
    was wrongly ALLOWED before OUTER_SCOPE was threaded into the
    recursive `_classify_tokens` call."""
    tokens = ["dummy=", "(", "$G", "$P", "$M", ")"]
    outer = {"G": "gh", "P": "pr", "M": "merge"}
    reason, _, _ = checker._rule_array_literal_content(tokens, outer, outer, outer, {}, {})
    assert reason is not None


def test_classify_denies_array_literal_content_with_outer_scope_end_to_end() -> None:
    """`_classify_tokens`'s own early-return on a denying `_rule_array_
    literal_content` verdict, reached end-to-end through `classify()` --
    not just the recursive rule's own unit tests above. Regression pin
    for the real bypass found live by Step 8 independent review,
    nineteenth round (issue #1326)."""
    verdict = checker.classify('G=gh; P=pr; M=merge; A=($G $P $M); "${A[@]}" 1')
    assert verdict.deny is True


def test_classify_denies_array_literal_content_with_braced_decoy_end_to_end() -> None:
    """End-to-end companion to `test_rule_array_literal_content_collapses_
    a_leading_unassigned_braced_bare_ref` above, reached through
    `classify()`. Regression pin for the real bypass found live by Step 8
    independent review, nineteenth round (issue #1326)."""
    verdict = checker.classify('A=(${NEVERSET} gh pr merge 1); "${A[@]}"')
    assert verdict.deny is True


def test_rule_command_substitution_content_detects_an_outer_scope_resolved_checkout() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, eighteenth round (issue #1375): a `git` token
    built from a variable assigned OUTSIDE the `$(...)` span's own
    text (NAME_TO_VALUE's own entries, not anything the substitution's
    own inner tokens assign) must still be recognized -- `G=git; x=$($G
    checkout -- dirty.py)` was wrongly ALLOWED, with an EMPTY
    `checkout_restore_paths`, before outer scope was threaded into the
    recursive `_classify_tokens` call below. Mirrors `_rule_array_
    literal_content`'s own nineteenth-round test of the identical shape
    for the array-literal span."""
    tokens = ["x=$", "(", "$G", "checkout", "--", "dirty.py", ")"]
    outer = {"G": "git"}
    reason, _, checkout_restore_paths = checker._rule_command_substitution_content(tokens, outer, outer, outer, {}, {})
    assert reason is None
    assert checkout_restore_paths == ("dirty.py",)


def test_classify_extracts_command_substitution_checkout_paths_with_outer_scope_end_to_end() -> None:
    """`classify()`'s own `checkout_restore_paths` extraction, reached
    end-to-end -- not just the recursive rule's own unit test above.
    Regression pin for the real bypass found live by Step 8 independent
    review, eighteenth round (issue #1375): before the outer-scope fix,
    this resolved to an EMPTY `checkout_restore_paths`, the same silent
    "nothing to see here" this classifier's own `deny=False` gives every
    ordinary checkout/restore invocation -- `deny` itself stays False
    here regardless (this module never unconditionally denies checkout/
    restore; the live wrapper's own `git diff --quiet` check is what
    turns a non-empty `checkout_restore_paths` into an actual deny, see
    `hooks/check-bash-safety.sh`). Exercises the unquoted, cross-token
    `$(...)` shape (`_command_substitution_token_span`, recursed into via
    `_classify_tokens` on inner TOKENS)."""
    verdict = checker.classify("G=git; x=$($G checkout -- dirty.py)")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_classify_extracts_quoted_command_substitution_checkout_paths_with_outer_scope_end_to_end() -> None:
    """Companion to the end-to-end pin above, for the quoted/fused
    `$(...)` shape (`_find_fused_command_substitution`, recursed into via
    `classify()` on the inner TEXT rather than `_classify_tokens` on
    inner TOKENS) -- the two shapes are separate code paths in `_rule_
    command_substitution_content`, both needed the outer-scope fix
    (eighteenth round, issue #1375)."""
    verdict = checker.classify('G=git; x="$($G checkout -- dirty.py)"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_assigned_raw_values_biased_toward_stays_on_literal_once_assigned() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, nineteenth round (issue #1375): once a name is
    assigned the biased-toward literal at any point, a LATER, different
    reassignment of the SAME name must not overwrite it back out --
    `TOOL=git; ...; TOOL=npm` must still resolve `TOOL` to `git` here,
    unlike `_assigned_raw_values`'s own plain last-occurrence-wins
    collapse."""
    assert checker._assigned_raw_values_biased_toward(["TOOL=git", "TOOL=npm"], frozenset({"git"})) == {"TOOL": "git"}


def test_assigned_raw_values_biased_toward_locks_on_regardless_of_order() -> None:
    """The literal-assignment can arrive BEFORE or AFTER a different
    reassignment of the same name and the end result is the same -- this
    function does not attempt real execution-order tracking, only a
    bounded "was LITERAL ever assigned to this name" bias."""
    assert checker._assigned_raw_values_biased_toward(["TOOL=npm", "TOOL=git"], frozenset({"git"})) == {"TOOL": "git"}


def test_assigned_raw_values_biased_toward_falls_back_to_last_assignment_when_literal_never_seen() -> None:
    """A name never assigned the biased-toward literal anywhere resolves
    exactly as `_assigned_raw_values`'s own plain last-occurrence-wins
    collapse would -- this function only ever WIDENS toward the literal,
    never changes behavior for a name that was never a candidate."""
    assert checker._assigned_raw_values_biased_toward(["TOOL=npm", "TOOL=yarn"], frozenset({"git"})) == {"TOOL": "yarn"}


@_PROPERTIES
@given(name=_IDENTIFIERS, decoy_value=_VALUES, tail=st.lists(_IDENTIFIERS, max_size=2))
def test_assigned_raw_values_biased_toward_matches_plain_collapse_when_never_reassigned_to_literal(
    name: str, decoy_value: str, tail: list[str]
) -> None:
    """Model-based: for a single assignment never matching the biased-
    toward literal, `_assigned_raw_values_biased_toward` agrees exactly
    with the plain, order-blind `_assigned_raw_values`."""
    assume(decoy_value.lower() != "git")
    tokens = [f"{name}={decoy_value}", *tail]
    assert checker._assigned_raw_values_biased_toward(tokens, frozenset({"git"})) == checker._assigned_raw_values(
        tokens
    )


def test_find_git_checkout_restore_recognizes_a_git_biased_reassigned_token() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, nineteenth round (issue #1375): the ordinary
    NAME_TO_RAW_VALUE reading declines (TOOL's own collapsed value is
    "npm", not "git"), but the GIT_BIASED reading recognizes `git` was
    assigned to TOOL at some point, so the occurrence is still found."""
    seg = ["$TOOL", "checkout", "--", "f.py"]
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(
        seg, {"TOOL": "npm"}, {"TOOL": "git"}
    )
    assert subcommand == "checkout"
    assert tokens_after == ["--", "f.py"]
    assert saw_tree_relocation is False


def test_find_git_checkout_restore_still_declines_when_neither_reading_resolves_to_git() -> None:
    """No false positive: when NEITHER the ordinary nor the git-biased
    reading resolves `tok` to `git`, the occurrence is still declined --
    the git-biased reading only ever widens recognition, never invents a
    match out of nothing."""
    seg = ["$TOOL", "checkout", "--", "f.py"]
    subcommand, _tokens_after, _saw = checker._find_git_checkout_restore(seg, {"TOOL": "svn"}, {"TOOL": "svn"})
    assert subcommand is None


def test_classify_extracts_checkout_paths_when_git_token_is_reassigned_after_use() -> None:
    """End-to-end regression pin for the round-19 finding at the
    `classify()` level, top-level shape (no command substitution needed
    at all) -- an entirely ordinary "reuse a variable name for a later,
    unrelated purpose" idiom. Confirmed live before this fix:
    `TOOL=git; $TOOL checkout -- dirty.py; TOOL=npm` resolved to an EMPTY
    `checkout_restore_paths`, even though `$TOOL` genuinely was `git` at
    its actual point of use."""
    verdict = checker.classify("TOOL=git; $TOOL checkout -- dirty.py; TOOL=npm")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_classify_extracts_restore_paths_when_git_token_is_reassigned_after_use() -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-19 finding was confirmed live for both subcommands."""
    verdict = checker.classify("TOOL=git; $TOOL restore dirty.py; TOOL=npm")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_classify_extracts_checkout_paths_when_git_token_is_reassigned_after_a_command_substitution() -> None:
    """End-to-end regression pin for the round-19 finding's command-
    substitution shape: the SAME reassignment-after-use gap, reached
    through `_rule_command_substitution_content`'s own outer-scope
    threading (round 18). Confirmed live before this fix: `G=git;
    x=$($G checkout -- dirty.py); G=notgit` resolved to an EMPTY
    `checkout_restore_paths`."""
    verdict = checker.classify("G=git; x=$($G checkout -- dirty.py); G=notgit")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_assigned_raw_values_biased_toward_accepts_several_interchangeable_literals() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1375): LITERALS is a
    SET, not a single string, so `cd`, `pushd`, and `popd` -- three
    different literals that all answer the same "was the working tree
    possibly relocated" question -- are all sticky against a later
    reassignment, not just one of them."""
    assert checker._assigned_raw_values_biased_toward(["X=cd", "X=elsewhere"], checker._CWD_RELOCATING_COMMANDS) == {
        "X": "cd"
    }
    assert checker._assigned_raw_values_biased_toward(["X=pushd", "X=elsewhere"], checker._CWD_RELOCATING_COMMANDS) == {
        "X": "pushd"
    }


def test_rule_git_checkout_restore_recognizes_a_cd_biased_reassigned_relocator() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1375): `_rule_git_
    checkout_restore`'s own dynamic-cd-relocation check was fed only the
    ordinary, order-blind RAW_ASSIGNED, the IDENTICAL gap round 19 closed
    for the sibling git-token-recognition consumer in the same function,
    just left open here -- the ordinary reading declines (X's own
    collapsed value is "elsewhere", not a relocator), but the
    RAW_ASSIGNED_CD_BIASED reading recognizes `cd` was assigned to X at
    some point, so the earlier relocation is still flagged and the
    checkout is denied rather than confidently, wrongly resolved."""
    segments = [["$X", "sub"], ["git", "checkout", "--", "dirty.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"X": "elsewhere"}, {}, {"X": "cd"}, {})
    assert reason is not None
    assert "cd" in reason or "pushd" in reason or "popd" in reason
    assert resolved == ()


def test_classify_denies_checkout_when_a_cd_token_is_reassigned_after_use() -> None:
    """End-to-end regression pin for the round-20 finding at the
    `classify()` level. Confirmed live before this fix: `X=cd; $X sub;
    git checkout -- dirty.py; X=somethingelse` resolved to `deny=False`
    with a CONFIDENT, WRONG `checkout_restore_paths` claim, even though
    `$X` genuinely was `cd` at its actual point of use one statement
    earlier."""
    verdict = checker.classify("X=cd; $X sub; git checkout -- dirty.py; X=somethingelse")
    assert verdict.deny is True


def test_classify_denies_checkout_when_a_pushd_token_is_reassigned_after_use() -> None:
    """Companion to the `cd` pin above, for `pushd` -- the round-20
    finding was confirmed live for all three `_CWD_RELOCATING_COMMANDS`
    members."""
    verdict = checker.classify("X=pushd; $X sub; git checkout -- dirty.py; X=somethingelse")
    assert verdict.deny is True


def test_classify_does_not_flag_cd_relocation_for_an_unrelated_reassigned_tool() -> None:
    """No false positive: a variable reassigned but NEVER assigned
    `cd`/`pushd`/`popd` anywhere in the command must not be flagged as a
    possible relocator -- the cd-biased fallback only ever widens
    recognition of a name that really was a relocator at some point,
    never invents one out of nothing."""
    verdict = checker.classify("X=curl; $X sub; git checkout -- dirty.py; X=wget")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_classify_denies_checkout_when_a_cd_token_is_reassigned_across_a_command_substitution() -> None:
    """End-to-end regression pin for the round-21 finding at the
    `classify()` level: round 20's own cd-biased fix was scoped to the
    current `_classify_tokens` invocation's own top-level segments only,
    which missed a reassignment straddling a command substitution's OWN
    boundary -- the relocator `$X` is used entirely WITHIN the
    substitution, but the ambiguity lives in the OUTER token stream.
    Confirmed live before this fix: `X=cd; y=$($X sub; git checkout --
    dirty.py); X=somethingelse` resolved to `deny=False` with a
    CONFIDENT, WRONG `checkout_restore_paths` claim."""
    verdict = checker.classify("X=cd; y=$($X sub; git checkout -- dirty.py); X=somethingelse")
    assert verdict.deny is True


def test_assigned_raw_value_history_records_every_distinct_value() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twenty-first round (issue #1375): unlike
    `_assigned_raw_values`'s own last-occurrence-wins collapse, every
    DISTINCT value ever assigned to a name is kept, in first-seen order."""
    assert checker._assigned_raw_value_history(["F=dirty.py", "F=other.py"]) == {"F": ("dirty.py", "other.py")}


def test_assigned_raw_value_history_deduplicates_an_identical_reassignment() -> None:
    """The SAME value assigned twice to the same name contributes only
    ONE entry to its history, not a duplicate."""
    assert checker._assigned_raw_value_history(["F=dirty.py", "F=dirty.py"]) == {"F": ("dirty.py",)}


@_PROPERTIES
@given(name=_IDENTIFIERS, value1=_VALUES, value2=_VALUES, tail=st.lists(_IDENTIFIERS, max_size=2))
def test_assigned_raw_value_history_matches_last_assignment_of_assigned_raw_values(
    name: str, value1: str, value2: str, tail: list[str]
) -> None:
    """Model-based: `_assigned_raw_value_history`'s own last entry for a
    name always agrees with `_assigned_raw_values`'s own single,
    last-occurrence-wins value for that same name -- the history is a
    strict widening (every value `_assigned_raw_values` itself could ever
    report, plus every earlier one it silently discarded), never a
    disagreement."""
    tokens = [f"{name}={value1}", f"{name}={value2}", *tail]
    history = checker._assigned_raw_value_history(tokens)
    assert history[name][-1] == checker._assigned_raw_values(tokens)[name]


def test_merge_raw_value_histories_unions_rather_than_shadows() -> None:
    """Model-based: unlike the plain `{**outer, **inner}` shadowing
    convention every other scope dict in this module uses, a name
    appearing in BOTH outer and inner histories keeps candidates from
    BOTH, not just inner's own -- an inner reassignment could genuinely
    take effect only AFTER `$NAME` was already used with an outer value,
    which this module's own static analysis cannot rule out (see this
    function's own docstring)."""
    merged = checker._merge_raw_value_histories({"F": ("dirty.py",)}, {"F": ("other.py",)})
    assert merged == {"F": ("dirty.py", "other.py")}


def test_merge_raw_value_histories_deduplicates_a_value_shared_by_both_scopes() -> None:
    """A value present in BOTH outer's and inner's own history for the
    same name contributes only one entry to the merged result."""
    merged = checker._merge_raw_value_histories({"F": ("dirty.py", "other.py")}, {"F": ("other.py",)})
    assert merged == {"F": ("dirty.py", "other.py")}


def test_resolve_path_tokens_widens_a_bare_reference_to_its_full_history() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twenty-first round (issue #1375):
    `_resolve_path_tokens`'s own dynamic-path-argument resolution is a
    THIRD consumer of the order-blind `_assigned_raw_values` collapse,
    with no bias mechanism at all before this fix -- `F=dirty.py; git
    checkout -- $F; F=other.py` resolved `$F` to `"other.py"` (the LAST
    assignment in token order) alone, even though `$F` genuinely was
    `dirty.py` at its actual point of use, so the REAL dirty file was
    never checked. A bare/braced whole-token reference to a name with
    multiple distinct historical values now extracts ALL of them as
    separate candidates, not just the single, possibly-stale one the
    collapsed NAME_TO_RAW_VALUE dict gives."""
    reason, resolved = checker._resolve_path_tokens(["$F"], {"F": "other.py"}, {"F": ("dirty.py", "other.py")})
    assert reason is None
    assert resolved == ("dirty.py", "other.py")


def test_resolve_path_tokens_history_widening_deduplicates_against_existing_paths() -> None:
    """A historical value that coincides with a path already extracted
    from an earlier, literal token in the same command is not appended
    twice."""
    reason, resolved = checker._resolve_path_tokens(
        ["dirty.py", "$F"], {"F": "other.py"}, {"F": ("dirty.py", "other.py")}
    )
    assert reason is None
    assert resolved == ("dirty.py", "other.py")


def test_resolve_path_tokens_does_not_widen_a_fused_reference() -> None:
    """No false positive: a token that FUSES a reference with literal
    text is NOT widened by the history mechanism (`_BARE_OR_BRACED_VAR_
    REF_RE` only matches a WHOLE-token bare/braced reference) -- it keeps
    the ordinary, single-candidate resolution unchanged, the same
    documented, deliberately narrower-than-full-soundness scoping this
    fix uses everywhere else."""
    reason, resolved = checker._resolve_path_tokens(["${F}.py"], {"F": "dirty"}, {"F": ("dirty", "other")})
    assert reason is None
    assert resolved == ("dirty.py",)


def test_classify_extracts_every_historical_path_when_a_checkout_path_is_reassigned_after_use() -> None:
    """End-to-end regression pin for the round-21 finding at the
    `classify()` level. Confirmed live before this fix: `F=dirty.py; git
    checkout -- $F; F=other.py` resolved to `checkout_restore_paths=
    ('other.py',)` -- a CONFIDENT, WRONG claim, since `$F` genuinely was
    `dirty.py` at its actual point of use -- instead of including the
    real, at-risk path at all."""
    verdict = checker.classify("F=dirty.py; git checkout -- $F; F=other.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py", "other.py")


def test_classify_extracts_every_historical_path_when_a_restore_path_is_reassigned_after_use() -> None:
    """Companion to the checkout pin above, for `git restore` -- the
    round-21 finding was confirmed live for both subcommands."""
    verdict = checker.classify("F=dirty.py; git restore $F; F=other.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py", "other.py")


def test_classify_extracts_every_historical_path_behind_a_command_substitution() -> None:
    """Companion to the two pins above, for the command-substitution
    shape: the SAME reassignment-after-use gap, reached through
    `_rule_command_substitution_content`'s own outer-scope threading
    (rounds 18-21)."""
    verdict = checker.classify("F=dirty.py; x=$(git checkout -- $F); F=other.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py", "other.py")


@_PROPERTIES
@given(name=_IDENTIFIERS, subscript=st.sampled_from(["0", "1", "@", "*", "$i"]))
def test_token_is_all_unassigned_refs_recognizes_a_braced_subscript(name: str, subscript: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1326): a braced
    array-element subscript reference (`${NAME[0]}`, `${NAME[@]}`) to a
    NAME never assigned anywhere in this command word-splits away to
    NOTHING at real bash runtime, the identical collapse a plain `${NAME}`
    reference already gets -- the nineteenth round's own `_BARE_VAR_REF_
    RE` did not recognize this shape at all, silently leaving the
    collapsed reading a no-op for it."""
    assert checker._token_is_all_unassigned_refs(f"${{{name}[{subscript}]}}", {}) is True


@_PROPERTIES
@given(name1=_IDENTIFIERS, name2=_IDENTIFIERS, braced1=st.booleans(), braced2=st.booleans())
def test_token_is_all_unassigned_refs_recognizes_a_fused_reference_chain(
    name1: str, name2: str, braced1: bool, braced2: bool
) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1326): TWO (or more)
    bare/braced references fused into ONE token with nothing else between
    them (`$A$B`) word-split away to nothing as a unit at real bash
    runtime, when EVERY referenced name is unassigned -- confirmed live
    via `declare -p` that `A=($A_UNSET$B_UNSET gh pr merge 1)` (both
    unset) produces the identical 4-element array a single bare
    `$NEVERSET` decoy already produced."""
    assume(name1 != name2)
    ref1 = f"${{{name1}}}" if braced1 else f"${name1}"
    ref2 = f"${{{name2}}}" if braced2 else f"${name2}"
    assert checker._token_is_all_unassigned_refs(ref1 + ref2, {}) is True


def test_token_is_all_unassigned_refs_stops_at_an_assigned_name_in_the_chain() -> None:
    """No false positive: a fused reference chain where at least ONE
    referenced name IS assigned elsewhere in the command does not vanish
    to nothing -- the assigned reference keeps its own real value's
    position, so the whole token must NOT be treated as collapsing
    away."""
    assert checker._token_is_all_unassigned_refs("$A_SET$B_UNSET", {"A_SET": "x"}) is False


def test_token_is_all_unassigned_refs_rejects_a_mismatched_brace() -> None:
    """Model-based, regression pin for the bug found live by Step 8
    independent review, twentieth round (issue #1326): the nineteenth
    round's own `_BARE_VAR_REF_RE` (`^\\$\\{?([A-Za-z_][A-Za-z0-9_]*)\\}?$`)
    had independently-optional opening/closing braces, so a MISMATCHED
    brace (`$NAME}`, a stray trailing `}` fused onto an otherwise-bare
    reference; `${NAME`, an unterminated opening brace) wrongly matched
    as if it were a clean single reference. Neither shape actually
    vanishes to nothing at real bash runtime (the stray `}`/unterminated
    `{` is fused-on literal text), so `_token_is_all_unassigned_refs`
    must reject both."""
    assert checker._token_is_all_unassigned_refs("$NEVERSET}", {}) is False
    assert checker._token_is_all_unassigned_refs("${NEVERSET", {}) is False


def test_token_is_all_unassigned_refs_rejects_a_default_clause() -> None:
    """No false positive: a `${NAME:-default}` default-clause reference
    supplies REAL substitute text regardless of whether NAME is assigned
    -- it never vanishes to nothing the way a bare/braced/subscript
    reference does, so it must not be treated as one."""
    assert checker._token_is_all_unassigned_refs("${NEVERSET:-fallback}", {}) is False


def test_rule_array_literal_content_detects_a_braced_subscript_decoy() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1326): `A=(${NEVERSET
    [0]} uv "$1"); "${A[@]}"` was wrongly ALLOWED before the array-
    subscript shape was recognized as vanishing -- B2 (`_rule_b2_
    watched_tool_dynamic_verb_position`) requires a LITERAL `seg[0]`, and
    the subscript decoy blocked it from ever firing until it collapsed
    away."""
    tokens = ["dummy=", "(", "${NEVERSET[0]}", "uv", "$VERB", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


def test_rule_array_literal_content_detects_a_fused_reference_chain_decoy() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1326): `A=($A_UNSET
    $B_UNSET gh pr merge 1); "${A[@]}"` (both unset) was wrongly ALLOWED
    before a fused chain of two bare references was recognized as
    vanishing as a unit."""
    tokens = ["dummy=", "(", "$A_UNSET$B_UNSET", "gh", "pr", "merge", "1", ")"]
    reason, _, _ = checker._rule_array_literal_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


def test_classify_denies_array_literal_content_with_subscript_decoy_end_to_end() -> None:
    """End-to-end companion to `test_rule_array_literal_content_detects_a_
    braced_subscript_decoy` above, reached through `classify()`.
    Regression pin for the real bypass found live by Step 8 independent
    review, twentieth round (issue #1326)."""
    verdict = checker.classify('A=(${NEVERSET[0]} uv "$1"); "${A[@]}"')
    assert verdict.deny is True


def test_classify_denies_array_literal_content_with_fused_chain_decoy_end_to_end() -> None:
    """End-to-end companion to `test_rule_array_literal_content_detects_a_
    fused_reference_chain_decoy` above, reached through `classify()`.
    Regression pin for the real bypass found live by Step 8 independent
    review, twentieth round (issue #1326)."""
    verdict = checker.classify('A=($A_UNSET$B_UNSET gh pr merge 1); "${A[@]}"')
    assert verdict.deny is True


@_PROPERTIES
@given(unset_name=_IDENTIFIERS, verb=_IDENTIFIERS)
def test_segment_loop_hit_detects_b2_once_a_leading_decoy_is_collapsed(unset_name: str, verb: str) -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twenty-first round (issue #1326): B2 (`_rule_
    b2_watched_tool_dynamic_verb_position`) requires a LITERAL `seg[0]`
    naming a watched tool -- `$NEVERSET uv $VERB` was wrongly ALLOWED,
    since a leading decoy at `seg[0]` blocked B2 from ever firing
    regardless of what followed. `_classify_tokens` closes this by
    additionally checking `_segment_loop_hit` against a COLLAPSED reading
    (via `_strip_leading_unassigned_bare_refs`) when the as-is reading
    finds nothing -- this pins that collapsed reading itself is denied."""
    as_is = [f"${unset_name}", "uv", f"${verb}"]
    collapsed = checker._strip_leading_unassigned_bare_refs(as_is, {})
    assert collapsed == ["uv", f"${verb}"]
    hit, _ = checker._segment_loop_hit([collapsed], {}, {})
    assert hit is not None


def test_classify_denies_b2_leading_decoy_end_to_end() -> None:
    """End-to-end companion to `test_segment_loop_hit_detects_b2_once_a_
    leading_decoy_is_collapsed` above, reached through `classify()`.
    Regression pin for the real bypass found live by Step 8 independent
    review, twenty-first round (issue #1326)."""
    verdict = checker.classify("$NEVERSET uv $VERB")
    assert verdict.deny is True


# --- codecov/patch coverage gate: branches this PR's diff added but no ----
# existing DENIED/ALLOWED end-to-end fixture or property test happened to
# exercise -- each test below targets one specific line/branch named in the
# PR's own `codecov/patch` report against commit 95def74, not a Step 8
# independent-review finding.


def test_substitute_var_refs_candidates_unassigned_braced_returns_empty() -> None:
    """`${NAME}` with NAME not itself assigned resolves to no candidates at
    all -- distinct from the default-clause/indirect-reference cases, which
    always contribute at least one reading."""
    assert checker._substitute_var_refs_candidates("${UNSET}", {}, {}) == []


def test_substitute_var_refs_candidates_default_clause_also_yields_named_value() -> None:
    """`${NAME:-default}` contributes both the literal default text AND
    NAME's own resolved value, when NAME also happens to be assigned."""
    candidates = checker._substitute_var_refs_candidates("${VAR:-fallback}", {"VAR": "actual"}, {})
    assert candidates is not None
    assert set(candidates) == {"fallback", "actual"}


def test_substitute_var_refs_candidates_returns_none_over_cap() -> None:
    """Combinatorial expansion past `_MAX_SUBSTITUTION_CANDIDATES` fails
    closed (`None`), not a silent truncation of the candidate set."""
    assert checker._substitute_var_refs_candidates(_OVERFLOW_TOKEN, _OVERFLOW_NAME_TO_VALUE, {}) is None


def test_ifs_split_splits_on_braced_marker() -> None:
    assert checker._ifs_split("a${IFS}b") == ["a", "b"]


def test_ifs_split_splits_on_bare_marker() -> None:
    assert checker._ifs_split("a$IFSb") == ["a", "b"]


def test_ifs_split_braced_marker_found_but_no_productive_split_tries_next_marker() -> None:
    """`${IFS}` alone splits to only empty pieces (filtered away), so the
    loop must fall through and try the bare `$IFS` marker next rather than
    returning at the braced marker's own unproductive split."""
    assert checker._ifs_split("${IFS}") == ["${IFS}"]


def test_split_punct_run_keeps_multi_op_token_whole() -> None:
    assert checker._split_punct_run("&&") == ["&&"]
    assert checker._split_punct_run("||") == ["||"]


def test_split_punct_run_splits_single_op_run() -> None:
    assert checker._split_punct_run(");") == [")", ";"]


def test_command_substitution_token_span_tracks_nested_depth() -> None:
    """An unquoted `$(...)` span containing its OWN nested `$(...)` must
    track paren depth past the first close, not stop at it."""
    tokens = checker.tokenize("echo $(echo $(date))")
    i = tokens.index("$")
    span_end = checker._command_substitution_token_span(tokens, i)
    assert span_end is not None
    assert tokens[i:span_end].count("(") == tokens[i:span_end].count(")") == 2


def test_find_fused_command_substitution_tracks_nested_depth() -> None:
    """The fused/quoted-span counterpart of the nested-depth case above."""
    fused_text = "$(echo $(date))"
    fused = checker._find_fused_command_substitution(fused_text)
    assert fused is not None
    start, end = fused
    assert fused_text[start:end] == fused_text


def test_find_fused_command_substitution_none_when_unbalanced() -> None:
    assert checker._find_fused_command_substitution("prefix $(echo unclosed") is None


def test_rule_command_substitution_content_scans_second_fused_span_in_same_token() -> None:
    """Coverage pin for the second-fused-span case: a token with TWO fused
    `$(...)` spans has BOTH scanned, not just the first -- the fix itself
    (and the real bypass it closed) is `_find_fused_command_substitution`'s
    own `search_from` parameter, already covered by its own tests above;
    this test only proves that fix reached end-to-end through
    `_rule_command_substitution_content`'s own scan loop."""
    tokens = ["echo", "$(echo ok)$(pip install evil-pkg)"]
    reason, _, _ = checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


def test_rule_command_substitution_content_skips_blank_fused_span_then_finds_denial() -> None:
    """A blank/whitespace-only fused span contributes nothing and is
    skipped without denying by itself, but scanning continues to the next
    fused span in the same token."""
    tokens = ["echo", "$( )$(pip install evil-pkg)"]
    reason, _, _ = checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {})
    assert reason is not None


def test_rule_command_substitution_content_both_fused_spans_harmless() -> None:
    tokens = ["echo", "$(echo ok)$(echo also-ok)"]
    assert checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


def test_rule_command_substitution_content_empty_unquoted_span_skipped() -> None:
    """An empty, unquoted `$()` substitution has no inner tokens to
    recurse into -- distinct from the fused/quoted empty-span case above."""
    tokens = ["$", "(", ")"]
    assert checker._rule_command_substitution_content(tokens, {}, {}, {}, {}, {}) == (None, False, ())


def test_tokenize_raises_on_unbalanced_quote() -> None:
    with pytest.raises(checker.TokenizeError):
        checker.tokenize('echo "unclosed')


def test_segment_tokens_splits_at_control_operator() -> None:
    assert checker.segment_tokens(["a", ";", "b"]) == [["a"], ["b"]]


def test_array_literal_token_span_tracks_nested_depth() -> None:
    tokens = ["x=", "(", "(", "a", ")", ")"]
    assert checker._array_literal_token_span(tokens, 0) == 6


def test_rule_a_literal_detects_denied_phrase_substring() -> None:
    """The same-token literal-phrase fallback (distinct from the adjacent-
    pair n-gram scan above it) catches a denied phrase embedded anywhere
    inside one otherwise-unrelated literal token."""
    phrase = next(iter(checker._DENIED_PHRASES))
    segments = [[f"echo-{phrase}-suffix"]]
    reason = checker._rule_a_literal(segments)
    assert reason is not None
    assert phrase in reason


def test_gh_api_method_dynamic_hit_unresolvable_value() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "-X$(echo POST)"]
    assert checker._gh_api_method_dynamic_hit(seg, {}, {}) is True


def test_gh_api_method_flagname_dynamic_hit_unresolvable_flag_token() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$(echo -X)", "POST"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {}, {}) is True


def test_gh_api_method_flagname_dynamic_hit_overflow_flag_token() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", _OVERFLOW_TOKEN, "POST"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, _OVERFLOW_NAME_TO_VALUE, {}) is True


def test_gh_api_method_flagname_dynamic_hit_flag_is_last_token() -> None:
    """No false positive: a resolved `-X`/`--method` flag with no
    following token at all has no value to inspect."""
    seg = ["gh", "api", "repos/o/r/pulls/1", "$F"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {"F": "-x"}, {}) is False


def test_gh_api_method_flagname_dynamic_hit_unresolvable_value_token() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$F", "$(echo POST)"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {"F": "-x"}, {}) is True


def test_gh_api_method_flagname_dynamic_hit_literal_write_value() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$F", "POST"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {"F": "-x"}, {}) is True


def test_gh_api_method_flagname_dynamic_hit_literal_non_write_value() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$F", "GET"]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {"F": "-x"}, {}) is False


def test_gh_api_method_fused_flagname_dynamic_hit_unresolvable() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$(echo -XPOST)"]
    assert checker._gh_api_method_fused_flagname_dynamic_hit(seg, {}, {}) is True


def test_gh_api_method_fused_flagname_dynamic_hit_overflow() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", _OVERFLOW_TOKEN]
    assert checker._gh_api_method_fused_flagname_dynamic_hit(seg, _OVERFLOW_NAME_TO_VALUE, {}) is True


def test_gh_api_method_fused_flagname_dynamic_hit_method_equals_form() -> None:
    seg = ["gh", "api", "repos/o/r/pulls/1", "$F"]
    assert checker._gh_api_method_fused_flagname_dynamic_hit(seg, {"F": "--method=post"}, {}) is True


def test_gh_api_field_flagname_dynamic_hit_unresolvable() -> None:
    seg = ["gh", "api", "repos/o/r/1", "$(echo -f)"]
    assert checker._gh_api_field_flagname_dynamic_hit(seg, {}, {}) is True


def test_gh_api_field_flagname_dynamic_hit_overflow() -> None:
    seg = ["gh", "api", "repos/o/r/1", _OVERFLOW_TOKEN]
    assert checker._gh_api_field_flagname_dynamic_hit(seg, _OVERFLOW_NAME_TO_VALUE, {}) is True


def test_gh_api_field_fused_flagname_dynamic_hit_unresolvable() -> None:
    seg = ["gh", "api", "repos/o/r/1", "$(echo -fname=value)"]
    assert checker._gh_api_field_fused_flagname_dynamic_hit(seg, {}, {}) is True


def test_gh_api_field_fused_flagname_dynamic_hit_overflow() -> None:
    seg = ["gh", "api", "repos/o/r/1", _OVERFLOW_TOKEN]
    assert checker._gh_api_field_fused_flagname_dynamic_hit(seg, _OVERFLOW_NAME_TO_VALUE, {}) is True


def test_rule_gh_api_write_graphql_mutation_keyword() -> None:
    segments = [["gh", "api", "graphql", "-f", "query=mutation{addComment}"]]
    lowered = "gh api graphql -f query=mutation{addcomment}"
    reason = checker._rule_gh_api_write(segments, lowered, {}, {})
    assert reason is not None
    assert "mutation" in reason


def test_rule_gh_api_write_graphql_without_mutation_allowed() -> None:
    """No false positive: a graphql call with no `mutation` keyword skips
    the (graphql-exempt) field-flag checks entirely, not just the
    mutation-keyword check."""
    segments = [["gh", "api", "graphql", "-f", "query=allthingsquery"]]
    lowered = "gh api graphql -f query=allthingsquery"
    assert checker._rule_gh_api_write(segments, lowered, {}, {}) is None


def test_rule_gh_api_write_field_flagname_dynamic() -> None:
    """The field-flagname-dynamic pass reached through the orchestrator
    itself (`_rule_gh_api_write`), not just as a standalone unit call."""
    segments = [["gh", "api", "repos/o/r/1", "$FF", "name=value"]]
    lowered = "gh api repos/o/r/1 $ff name=value"
    reason = checker._rule_gh_api_write(segments, lowered, {"FF": "--field"}, {})
    assert reason == checker._FIELD_FLAG_HIT


def test_rule_gh_api_write_field_fused_flagname_dynamic() -> None:
    segments = [["gh", "api", "repos/o/r/1", "$FFsuffix"]]
    lowered = "gh api repos/o/r/1 $ffsuffix"
    reason = checker._rule_gh_api_write(segments, lowered, {"FF": "-f"}, {})
    assert reason == checker._FIELD_FLAG_HIT


def test_is_git_push_segment_git_alone_no_trailing_tokens() -> None:
    """ "git" as the segment's only token: the flag-skip loop's own
    condition fails immediately, nothing after "git" to scan."""
    assert checker._is_git_push_segment(["git"], {}) is False


def test_is_git_push_segment_value_flag_followed_by_another_flag() -> None:
    """ "-C" is a value-taking short flag; when the NEXT token itself looks
    like a flag ("-v", starts with "-"), it must NOT be consumed as -C's
    own value -- the loop re-examines it as its own flag instead."""
    assert checker._is_git_push_segment(["git", "-C", "-v", "push"], {}) is True


def test_is_git_push_segment_true_once_a_vanishing_decoy_is_skipped() -> None:
    """The positive case of the twenty-second-round fix: a leading decoy
    that vanishes to nothing at real bash runtime (NEVERSET never
    assigned) sits between a literal flag and "push" -- confirmed live via
    a real bash proxy (stand-in `git` binary on PATH) that `git -v
    $NEVERSET push origin main` genuinely runs `git push origin main`
    once the decoy word-splits away."""
    assert checker._is_git_push_segment(["git", "-v", "$NEVERSET", "push", "origin", "main"], {}) is True


def test_is_git_push_segment_false_for_a_non_vanishing_dynamic_token() -> None:
    """A dynamic token that does NOT vanish (its name IS assigned, so
    `_token_is_all_unassigned_refs` returns False) stops the flag-skip
    loop's scan via its own `break`, the same as any other non-flag,
    non-"push" token -- this function only looks PAST a token confirmed
    to vanish to nothing; resolving whether an assigned dynamic token's
    own VALUE happens to equal "push" is out of its scope (handled, if at
    all, by the separate obfuscated-git-push-second-token check in
    `_classify_tokens`, which this deliberately does not duplicate)."""
    assert checker._is_git_push_segment(["git", "$M", "push", "origin", "main"], {"M": "foo"}) is False


def test_is_git_push_segment_true_for_a_dash_c_value_past_a_vanishing_decoy() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-third round (issue #1326): the `-c`/
    `_GIT_LONG_VALUE_FLAGS` value-consumption block never looked past a
    leading decoy to find `-c`'s own real value, so the outer loop's own
    general decoy-skip consumed the decoy first and landed on the real
    value token (`user.name=x`) as an ordinary, never-claimed token, one
    position short of `push` -- confirmed live via a real `git` binary
    (2.43.0) that `-c user.name=x push origin main` genuinely reaches
    push dispatch, leaving `push` as the real subcommand once the decoy
    word-splits away."""
    seg = ["git", "-c", "$NEVERSET", "user.name=x", "push", "origin", "main"]
    assert checker._is_git_push_segment(seg, {}) is True


def test_is_git_push_segment_true_for_a_dash_c_assigned_dynamic_value() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-third round (issue #1326): the `-c`/
    `_GIT_LONG_VALUE_FLAGS` value-consumption block only ever consumed a
    LITERAL value -- an assigned, non-vanishing DYNAMIC value in this
    exact position was never consumed either, predating this round
    entirely. Confirmed live via a real bash proxy that `-c` genuinely
    consumes the resolved value as real argv, leaving `push` as the real
    subcommand."""
    seg = ["git", "-c", "$CFG", "push", "origin", "main"]
    assert checker._is_git_push_segment(seg, {"CFG": "user.name=x"}) is True


def test_is_git_push_segment_false_for_a_vanishing_decoy_consumed_by_dash_c_itself() -> None:
    """No false positive: when the decoy sitting in `-c`'s own value
    position vanishes AND nothing else survives between it and `push`,
    `push` ITSELF becomes the token `-c` consumes as its value (real
    git's own CLI parser unconditionally consumes the very next
    surviving token, confirmed live: `-c push` produces "error: key does
    not contain a section: push") -- so `origin` (not `push`) is left as
    the would-be subcommand, and no real push actually occurs. Confirmed
    this stays correctly unflagged after the twenty-third-round fix."""
    seg = ["git", "-c", "$NEVERSET", "push", "origin", "main"]
    assert checker._is_git_push_segment(seg, {}) is False


def test_is_git_push_segment_false_when_only_decoys_follow_dash_c_to_segment_end() -> None:
    """Branch-coverage pin: when `-c`'s own value-skip loop runs past
    EVERY remaining token (all vanishing decoys, nothing surviving all
    the way to the end of the segment), it must terminate via the
    while-loop's own natural `value_j == len(literals)` exit rather than
    an explicit `break`, and the subsequent `if value_j < len(literals)`
    guard must correctly decline to consume anything -- there is no
    "push" here regardless."""
    seg = ["git", "-c", "$NEVERSET1", "$NEVERSET2"]
    assert checker._is_git_push_segment(seg, {}) is False


def test_token_is_all_unassigned_refs_true_for_a_bare_ref_assigned_the_empty_string() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-fourth round (issue #1326): a BARE
    reference to a NAME assigned the EMPTY STRING word-splits away
    IDENTICALLY to a genuinely-unset one at real bash runtime -- this
    check used to only ask "is NAME a key in NAME_TO_VALUE at all,"
    never "does NAME's own assigned value actually survive word-
    splitting," wrongly treating an assigned-but-empty value as NOT
    vanishing."""
    assert checker._token_is_all_unassigned_refs("$CFG", {"CFG": ""}) is True


def test_token_is_all_unassigned_refs_false_for_a_braced_subscript_ref_to_an_empty_mapped_name() -> None:
    """No regression: the empty-string fix is deliberately scoped to the
    BARE and plain-braced (no subscript) forms only. A genuinely
    SUBSCRIPTED braced reference (`${NAME[0]}`) to a name mapped to the
    empty string in NAME_TO_VALUE stays on the ORIGINAL, narrower check
    -- `_assigned_literals` maps EVERY array declaration's own NAME to
    the empty string regardless of the array's real element contents,
    so generalizing the empty-string check to this form would wrongly
    treat `${NEVERSET[0]}` as vanishing even when NEVERSET's real first
    element is non-empty, which this module has no per-index tracking
    to rule out."""
    assert checker._token_is_all_unassigned_refs("${NEVERSET[0]}", {"NEVERSET": ""}) is False


def test_token_is_all_unassigned_refs_true_for_a_plain_braced_ref_assigned_the_empty_string() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-fifth round (issue #1326): a plain,
    UN-subscripted braced reference (`${NAME}`) has no array-content
    ambiguity at all -- it is exactly the braced spelling of the same
    bare scalar reference -- so it must get the SAME empty-value-counts-
    as-vanishing treatment as the bare form, confirmed live via real
    bash that `CFG=; git -v ${CFG} push origin main` real-expands to
    `git -v push origin main`."""
    assert checker._token_is_all_unassigned_refs("${CFG}", {"CFG": ""}) is True


def test_token_is_all_unassigned_refs_false_for_a_plain_braced_ref_assigned_a_real_value() -> None:
    """No false positive / branch-coverage pin: a plain, UN-subscripted
    braced reference assigned a genuinely non-empty, non-whitespace
    value is NOT vanishing -- the twenty-fifth-round fix's own
    `.strip()`-truthiness check must still correctly decline to treat a
    real assignment as vanishing."""
    assert checker._token_is_all_unassigned_refs("${CFG}", {"CFG": "real"}) is False


def test_token_is_all_unassigned_refs_true_for_a_bare_ref_assigned_all_ifs_whitespace() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-fifth round (issue #1326): a value
    consisting ENTIRELY of IFS whitespace (default IFS is space/tab/
    newline) ALSO word-splits away to nothing at real bash runtime, the
    same as a literally empty value -- confirmed live via real bash
    that `CFG=" "; git -v $CFG push origin main` real-expands to `git
    -v push origin main`. The un-stripped truthiness check this fix
    replaces would have missed this (`" "` is truthy in Python even
    though `" ".strip()` is falsy)."""
    assert checker._token_is_all_unassigned_refs("$CFG", {"CFG": " "}) is True


def test_token_is_all_unassigned_refs_true_for_a_plain_braced_ref_assigned_all_ifs_whitespace() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-sixth round (issue #1326): the
    twenty-fifth round's own IFS-whitespace fix was pinned for the bare
    form only -- the identical `.strip()`-truthiness check on the
    plain-braced arm had no whitespace-specific regression test,
    confirmed via mutation testing that reverting just the braced arm's
    `.strip()` call passed this file's full suite unchanged before this
    test was added. Confirmed live via real bash that `CFG=" "; git -v
    ${CFG} push origin main` real-expands to `git -v push origin main`,
    identically to the bare form."""
    assert checker._token_is_all_unassigned_refs("${CFG}", {"CFG": " "}) is True


def test_token_is_all_unassigned_refs_false_for_a_bare_ref_assigned_only_a_carriage_return() -> None:
    """No false positive: a value consisting ENTIRELY of a carriage
    return (`\\r`) is NOT IFS whitespace in bash (the default `$IFS` is
    exactly space/tab/newline) and does NOT word-split away at real
    bash runtime -- found live by Step 8 independent review, twenty-
    sixth round (issue #1326): confirmed live via real bash (`set -x`)
    that `CFG=$'\\r'; git -v $CFG push origin main` keeps `$'\\r'` as
    its own argv element (`+ git -v $'\\r' push origin main`), NOT
    word-splitting away, unlike Python's own broader `str.strip()`
    default whitespace set (which also strips `\\r`/`\\f`/`\\v`) would
    wrongly suggest. `_BASH_DEFAULT_IFS` scopes the stripping to
    exactly bash's own three IFS characters to avoid this."""
    assert checker._token_is_all_unassigned_refs("$CFG", {"CFG": "\r"}) is False


def test_token_is_all_unassigned_refs_true_for_a_carriage_return_when_ifs_is_reassigned() -> None:
    """Regression pin for the real HARD-DENY-BYPASS-capable bug found
    live by Step 8 independent review, twenty-eighth round (issue
    #1326): once the COMMAND ITSELF assigns anything to `IFS`
    (`"IFS" in name_to_value`), a value like `\\r` -- which the
    twenty-sixth round's own `_BASH_DEFAULT_IFS` scoping correctly does
    NOT treat as vanishing under bash's own DEFAULT `$IFS` -- must now
    fail closed and be treated as POSSIBLY vanishing anyway, since this
    module has no way to know the command's own reassigned `$IFS`
    doesn't include `\\r`. Confirmed live via real bash that `IFS="\\r";
    CFG="\\r"; git -v $CFG push origin main` (the carriage return
    DOUBLE-QUOTED so it survives shlex's own tokenization -- an
    unquoted `\\r` is absorbed as ordinary whitespace before this code
    ever runs) genuinely word-splits `$CFG` away under the reassigned
    IFS."""
    assert checker._token_is_all_unassigned_refs("$CFG", {"IFS": "\r", "CFG": "\r"}) is True


def test_is_git_push_segment_true_for_a_flag_skip_decoy_when_ifs_is_reassigned() -> None:
    """Regression pin for the same twenty-eighth-round bug: with `IFS`
    reassigned, a decoy sitting behind a literal boolean flag (`-v`)
    that previously stopped the flag-skip loop cold (since `\\r` alone
    does not vanish under the DEFAULT IFS) must now be skipped, so a
    real `push` past it is not missed."""
    seg = ["git", "-v", "$CFG", "push", "origin", "main"]
    assert checker._is_git_push_segment(seg, {"IFS": "\r", "CFG": "\r"}) is True


def test_classify_flags_git_push_via_ifs_reassignment_end_to_end() -> None:
    """End-to-end companion to the two unit tests above, reached through
    `classify()`: the identical-ARGV default-IFS control (`CFG=" ";
    ...`) already correctly returns `is_git_push=True` -- this confirms
    the reassigned-IFS case now matches it instead of being silently
    missed."""
    verdict = checker.classify('IFS="\r"; CFG="\r"; git -v $CFG push origin main')
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_token_is_all_unassigned_refs_false_for_a_non_vanishing_value_when_ifs_is_reassigned() -> None:
    """Regression pin for the real regression found live by Step 8
    independent review, twenty-ninth round (issue #1326): the twenty-
    eighth round's own blanket "IFS reassigned -> always True" rule
    wrongly treated a REAL, non-empty value as vanishing purely because
    `$IFS` was reassigned SOMEWHERE in the command, even when that
    value's own characters do not overlap the actual reassigned IFS at
    all. Confirmed live via real bash that `IFS=x; REAL=foo; $REAL uv
    $VERB` real-expands to `foo uv` -- `$REAL` (value "foo", no "x"
    character in it) never vanishes under IFS="x" either."""
    assert checker._token_is_all_unassigned_refs("$REAL", {"IFS": "x", "REAL": "foo"}) is False


def test_strip_leading_unassigned_bare_refs_keeps_a_non_vanishing_wrapper_when_ifs_is_reassigned() -> None:
    """Regression pin for the same twenty-ninth-round finding: a real
    wrapper token must NOT be stripped as a decoy just because `$IFS`
    was reassigned elsewhere in the command, or `_rule_b2_watched_tool_
    dynamic_verb_position` wrongly sees a bare `uv` sitting at
    position 0."""
    tokens = ["$REAL", "uv", "$VERB"]
    name_to_value = {"IFS": "x", "REAL": "foo"}
    assert checker._strip_leading_unassigned_bare_refs(tokens, name_to_value) == tokens


def test_classify_does_not_deny_a_dynamic_wrapper_command_via_stale_ifs_reassignment_end_to_end() -> None:
    """End-to-end companion: `classify()` must not deny this benign
    command, confirmed live via real bash that it runs `foo uv`, never
    touching the watched `uv` tool in a dynamic-verb position."""
    verdict = checker.classify("IFS=x; REAL=foo; $REAL uv $VERB")
    assert verdict.deny is False


def test_is_git_push_segment_true_for_a_real_config_value_when_ifs_is_reassigned() -> None:
    """Regression pin for the MOST severe twenty-ninth-round finding: the
    twenty-eighth round's own blanket IFS rule reopened a hard-deny
    bypass strictly broader than the one it closed. `-c`'s own value-
    consumption loop wrongly treated a REAL, non-vanishing config value
    as a decoy to skip past, landing on the literal `push` token itself
    and wrongly consuming IT as `-c`'s own value instead -- confirmed
    live via real bash that `IFS=,; CFG=user.name=x; git -c $CFG push`
    real-expands to `git -c user.name=x push`, a genuine push."""
    seg = ["git", "-c", "$CFG", "push"]
    assert checker._is_git_push_segment(seg, {"IFS": ",", "CFG": "user.name=x"}) is True


def test_classify_flags_git_push_via_a_real_config_value_despite_ifs_reassignment_end_to_end() -> None:
    """End-to-end companion to the above, and to the ordinary no-op
    variant `IFS=" "` (a single-space IFS, not bash's own three-
    character default, still an entirely realistic no-op reassignment a
    human might write) -- both must still be recognized as a push."""
    verdict = checker.classify("IFS=,; CFG=user.name=x; git -c $CFG push")
    assert verdict.is_git_push is True
    verdict_noop = checker.classify('IFS=" "; CFG=user.name=x; git -c $CFG push')
    assert verdict_noop.is_git_push is True


def test_value_position_after_returns_the_real_dynamic_value_when_ifs_is_reassigned() -> None:
    """Regression pin for the twenty-ninth-round finding in `_value_
    position_after`'s own skip-loop (routed through `_token_is_
    unambiguously_vanishing`): a real dynamic write-method value must
    not be skipped over as a decoy merely because `$IFS` was reassigned
    somewhere else in the command, confirmed live via real bash that
    `M=POST` genuinely survives as `-X`'s own value regardless of an
    unrelated `IFS=x` reassignment."""
    seg = ["gh", "api", "repos/foo/bar/merge", "-X", "${M}", "extra"]
    name_to_value = {"IFS": "x", "M": "post"}
    name_to_raw_value = {"IFS": "x", "M": "POST"}
    assert checker._value_position_after(seg, 3, name_to_value, name_to_raw_value) == "${M}"


def test_classify_denies_gh_api_dynamic_write_method_despite_ifs_reassignment_end_to_end() -> None:
    """End-to-end companion to the above: confirmed live via real bash
    that `IFS=x; echo hi; M=POST; gh api repos/foo/bar/merge -X ${M}
    extra` real-expands to `gh api repos/foo/bar/merge -X POST extra`, a
    genuine write."""
    verdict = checker.classify("IFS=x; echo hi; M=POST; gh api repos/foo/bar/merge -X ${M} extra")
    assert verdict.deny is True


def test_token_is_all_unassigned_refs_false_for_a_case_mismatched_ifs_and_value() -> None:
    """Direct characterization of this function's own case-SENSITIVE
    semantics, confirmed live via real bash that `IFS=post; DECOY=POST;
    ...${DECOY}...` leaves `${DECOY}` intact (`POST`'s own uppercase
    letters are untouched by a lowercase-only `$IFS`). NOT itself a
    regression pin for the thirtieth-round hard-deny bypass (issue
    #1326) -- this function's own internal `.strip(effective_ifs)` logic
    never changed that round; the bug lived entirely in which map its
    CALLERS passed it (the lowercased `name_to_value` instead of the
    case-preserving `name_to_raw_value`), so calling it directly with an
    already-correctly-cased dict, as this test does, passes identically
    whether or not that round's caller-level rewiring fix is present --
    confirmed live by Step 8 independent review, thirty-first round
    (issue #1326), which found this test (and its `_skip_fetch_exec_
    wrapper` counterpart in the task-scoped sibling module) vacuous
    against the pre-fix code for exactly this reason. The REAL
    regression pins for that round's fix are the caller-level test
    (`test_value_position_after_returns_the_real_value_despite_a_case_
    folded_ifs_collision`) and the end-to-end `classify()` test below,
    both of which route through the actual caller wiring that was
    broken and are confirmed to fail against the pre-fix code."""
    assert checker._token_is_all_unassigned_refs("${DECOY}", {"IFS": "post", "DECOY": "POST"}) is False


def test_value_position_after_returns_the_real_value_despite_a_case_folded_ifs_collision() -> None:
    """Regression pin for the same thirtieth-round finding, at the
    `_value_position_after` call site the bypass actually reached: a
    dynamic write-method value must not be skipped as a decoy merely
    because its LOWERCASED reading happens to coincide with the
    LOWERCASED reassigned `$IFS` -- real bash compares case-sensitively,
    so `${DECOY}` (value "POST") genuinely survives past `IFS=post`."""
    seg = ["gh", "api", "repos/foo/bar/merge", "-X", "${DECOY}", "extra"]
    name_to_value = {"IFS": "post", "DECOY": "post"}
    name_to_raw_value = {"IFS": "post", "DECOY": "POST"}
    assert checker._value_position_after(seg, 3, name_to_value, name_to_raw_value) == "${DECOY}"


def test_classify_denies_gh_api_dynamic_write_method_despite_a_case_folded_ifs_collision_end_to_end() -> None:
    """End-to-end companion to the above: confirmed live via real bash
    that `IFS=post; DECOY=POST; gh api repos/foo/bar/merge -X ${DECOY}
    extra` real-expands to `gh api repos/foo/bar/merge -X POST extra`, a
    genuine write."""
    verdict = checker.classify("IFS=post; DECOY=POST; gh api repos/foo/bar/merge -X ${DECOY} extra")
    assert verdict.deny is True


def test_is_git_push_segment_true_for_an_empty_assigned_variable_in_boolean_flag_position() -> None:
    """Regression pin for the real bypass found live by Step 8
    independent review, twenty-fourth round (issue #1326): a boolean
    flag (`-v`, no value) followed by a variable assigned the EMPTY
    STRING -- the reference word-splits away identically to an unset
    one, so `push` is the real next token, confirmed live via real bash
    that `git -v $CFG push origin main` (CFG assigned "") real-expands
    to `git -v push origin main`."""
    assert checker._is_git_push_segment(["git", "-v", "$CFG", "push", "origin", "main"], {"CFG": ""}) is True


def test_classify_flags_git_push_via_empty_assigned_variable_end_to_end() -> None:
    """End-to-end companion to `test_is_git_push_segment_true_for_an_
    empty_assigned_variable_in_boolean_flag_position` above, reached
    through `classify()`."""
    verdict = checker.classify("CFG=; git -v $CFG push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_classify_flags_git_push_via_plain_braced_empty_assigned_variable_end_to_end() -> None:
    """End-to-end companion to `test_token_is_all_unassigned_refs_true_
    for_a_plain_braced_ref_assigned_the_empty_string` above, reached
    through `classify()`."""
    verdict = checker.classify("CFG=; git -v ${CFG} push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_classify_flags_git_push_via_all_ifs_whitespace_assigned_variable_end_to_end() -> None:
    """End-to-end companion to `test_token_is_all_unassigned_refs_true_
    for_a_bare_ref_assigned_all_ifs_whitespace` above, reached through
    `classify()`."""
    verdict = checker.classify('CFG=" "; git -v $CFG push origin main')
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_resolve_seg_tokens_candidates_overflow_returns_none() -> None:
    assert checker._resolve_seg_tokens_candidates([_OVERFLOW_TOKEN], _OVERFLOW_NAME_TO_VALUE, {}) is None


def test_rule_b1a_fails_closed_on_tail_overflow() -> None:
    seg = ["$T", _OVERFLOW_TOKEN]
    assert (
        checker._rule_b1a_dynamic_word_same_segment_verb(seg, checker._WATCHED_VERBS, _OVERFLOW_NAME_TO_VALUE, {})
        is True
    )


def test_rule_b1b_fails_closed_on_overflow() -> None:
    seg = ["$T", _OVERFLOW_TOKEN]
    assert (
        checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, _OVERFLOW_NAME_TO_VALUE, checker._WATCHED_VERBS, {})
        is True
    )


def test_rule_b2_false_for_short_segment() -> None:
    assert checker._rule_b2_watched_tool_dynamic_verb_position(["uv"]) is False


def test_rule_b2_true_for_dynamic_verb_position() -> None:
    assert checker._rule_b2_watched_tool_dynamic_verb_position(["uv", "$x"]) is True


def test_classify_fails_closed_on_unparseable_command() -> None:
    verdict = checker.classify('echo "unclosed')
    assert verdict.deny is True
    assert "parsed as shell syntax" in verdict.reason


def test_classify_denies_bare_top_level_command_substitution() -> None:
    """`_classify_tokens`'s own early-return on a denying
    `_rule_command_substitution_content` verdict, reached end-to-end
    through `classify()` -- not just the recursive rule's own unit tests
    above."""
    verdict = checker.classify("$(pip install evil-pkg)")
    assert verdict.deny is True


def test_classify_denies_gh_api_write_end_to_end() -> None:
    verdict = checker.classify("gh api repos/o/r/pulls/1 -X POST")
    assert verdict.deny is True


def test_classify_denies_gh_api_write_past_a_vanishing_decoy_in_value_position_end_to_end() -> None:
    """Found live by Step 8 independent review, twenty-second round (issue
    #1326): `_gh_api_method_dynamic_value` used to read `seg[index + 1]`
    directly for the -X/--method flag's value, assuming it always sits
    immediately after the flag -- a leading decoy interposed there (`-X
    $NEVERSET $M`, NEVERSET never assigned) made it return the decoy
    itself as "the value," which resolved unresolvable and silently
    missed the real write method one position further."""
    verdict = checker.classify("M=POST; gh api repos/o/r/pulls/1 -X $NEVERSET $M")
    assert verdict.deny is True


def test_classify_denies_gh_api_write_flagname_past_a_vanishing_decoy_in_value_position_end_to_end() -> None:
    """Same twenty-second-round fix as above, for `_gh_api_method_
    flagname_dynamic_hit`'s own value-position read instead: `$F
    $NEVERSET $M` (the flag NAME itself indirected through `$F`, with a
    vanishing decoy between it and the real write-method value)."""
    verdict = checker.classify("F=-X; M=POST; gh api repos/o/r/pulls/1 $F $NEVERSET $M")
    assert verdict.deny is True


def test_classify_denies_array_literal_content_end_to_end() -> None:
    """`_classify_tokens`'s own early-return on a denying `_rule_array_
    literal_content` verdict, reached end-to-end through `classify()` --
    not just the recursive rule's own unit tests above. Regression pin
    for the real bypass found live by Step 8 independent review,
    eighteenth round (issue #1326)."""
    verdict = checker.classify('A=($NEVERSET uv install); "${A[@]}" foo')
    assert verdict.deny is True


def test_classify_denies_b1b_tool_and_verb_split_end_to_end() -> None:
    """B1b's own tool+verb-in-whole-segment resolution, reached end-to-end
    with a command shaped so B1a's narrower tail-only resolution does not
    already intercept it first."""
    verdict = checker.classify("X=install; Y=uv; $X $Y")
    assert verdict.deny is True


def test_classify_denies_b2_dynamic_verb_position_end_to_end() -> None:
    verdict = checker.classify("uv $x foo")
    assert verdict.deny is True


def test_classify_flags_git_push_via_dynamic_second_token() -> None:
    verdict = checker.classify("git $x")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_classify_flags_git_push_past_a_vanishing_leading_decoy_end_to_end() -> None:
    """Found live by Step 8 independent review, twenty-second round (issue
    #1326): `git -v $NEVERSET push origin main` (NEVERSET never assigned)
    used to stop `_is_git_push_segment`'s own flag-skip loop AT the decoy
    instead of skipping past it, so `is_git_push` was wrongly False --
    confirmed live via a real bash proxy (stand-in `git` binary on PATH,
    capturing its own argv) that this genuinely runs `git push origin
    main` once the decoy word-splits away."""
    verdict = checker.classify("git -v $NEVERSET push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_classify_flags_git_push_past_a_dash_c_value_decoy_end_to_end() -> None:
    """End-to-end companion to `test_is_git_push_segment_true_for_a_
    dash_c_value_past_a_vanishing_decoy` above, reached through
    `classify()`."""
    verdict = checker.classify("git -c $NEVERSET user.name=x push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def test_classify_flags_git_push_via_dash_c_assigned_dynamic_value_end_to_end() -> None:
    """End-to-end companion to `test_is_git_push_segment_true_for_a_
    dash_c_assigned_dynamic_value` above, reached through `classify()`."""
    verdict = checker.classify("CFG=user.name=x; git -c $CFG push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True


def _run_main(
    payload: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    payload_bytes = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    monkeypatch.setattr(sys, "stdin", _FakeStdin(payload_bytes))
    checker.main()
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


def test_main_fails_closed_on_malformed_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_main(b"not json", monkeypatch, capsys)["decision"] == "deny"


def test_main_fails_closed_on_non_object_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_main(b"[1, 2, 3]", monkeypatch, capsys)["decision"] == "deny"


def test_main_fails_closed_on_non_string_tool_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_main({"tool_name": 123}, monkeypatch, capsys)["decision"] == "deny"


def test_main_allows_non_bash_tool(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_main({"tool_name": "Read"}, monkeypatch, capsys)["decision"] == "allow"


def test_main_fails_closed_on_non_object_tool_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"tool_name": "Bash", "tool_input": "nope"}
    assert _run_main(payload, monkeypatch, capsys)["decision"] == "deny"


def test_main_fails_closed_on_non_string_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": 42}}
    assert _run_main(payload, monkeypatch, capsys)["decision"] == "deny"


def test_main_allows_empty_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": ""}}
    assert _run_main(payload, monkeypatch, capsys)["decision"] == "allow"


def test_main_allows_missing_tool_input(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_main({"tool_name": "Bash"}, monkeypatch, capsys)["decision"] == "allow"


def test_main_denies_a_real_denied_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "pip install evil-pkg"}}
    out = _run_main(payload, monkeypatch, capsys)
    assert out["decision"] == "deny"
    assert "is_git_push" in out


def test_main_allows_a_harmless_command(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    assert _run_main(payload, monkeypatch, capsys)["decision"] == "allow"


# --- Issue #1375: git checkout/restore path extraction. `classify()` stays
# I/O-free (this module's own established architecture); this section only
# extracts every candidate path a checkout/restore invocation could
# discard, for hooks/check-bash-safety.sh's own new wrapper step to check
# live against the real working tree. See hooks/gitapex_check_bash_safety.py's
# own "git checkout/restore path extraction" section for the full design
# rationale and the live-git verification (git 2.43.0) it is built on.

_PATH_TOKENS = st.text(alphabet=string.ascii_letters + string.digits + "_./", min_size=1, max_size=12).filter(
    lambda p: not p.startswith("-") and p not in (".", "..")
)


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=1, max_size=5))
def test_resolve_path_tokens_returns_literal_tokens_unchanged(paths: list[str]) -> None:
    """Model-based: every literal (non-dynamic) token is returned as-is, in
    order, with no deny reason."""
    reason, resolved = checker._resolve_path_tokens(paths, {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_PATH_TOKENS)
def test_resolve_path_tokens_resolves_a_braced_reference_case_preserved(name: str, value: str) -> None:
    """Model-based: a dynamic `${NAME}` path token resolves to NAME's own
    CASE-PRESERVED raw value -- unlike every other caller of
    `_substitute_var_refs_candidates` in this module (which compares a
    resolved value case-insensitively against a known tool/verb/flag
    literal via the lowercased `name_to_value`), a filesystem path is
    case-sensitive, so this must resolve against the raw, case-preserving
    map. Regression pin: an earlier version of this function resolved
    against the lowercased map and would have silently mismatched a
    mixed-case path like `README.md` against `readme.md`."""
    mixed_case_value = value.swapcase()
    reason, resolved = checker._resolve_path_tokens([f"${{{name}}}"], {name: mixed_case_value}, {})
    assert reason is None
    assert resolved == (mixed_case_value,)


@_PROPERTIES
@given(name=_IDENTIFIERS)
def test_resolve_path_tokens_denies_an_unresolvable_dynamic_token(name: str) -> None:
    """Fail-closed: a dynamic token referencing a name that is never
    assigned cannot be resolved to a literal -- denied outright here
    rather than passed to the live wrapper check empty-handed, since
    `git diff --quiet HEAD -- PATH` exits 0 (clean) for a path that does
    not exist (issue #1375 Fact 5, confirmed live), which would be
    fail-open."""
    reason, resolved = checker._resolve_path_tokens([f"${name}"], {}, {})
    assert reason is not None
    assert resolved == ()


def test_resolve_path_tokens_denies_an_array_subscript_token() -> None:
    """Regression pin, found during this function's own development: bash
    array-subscript syntax (`${paths[@]}`) is not matched by
    `_substitute_var_refs_candidates`'s own `_VAR_REF_FULL_RE` at all
    (issue #1375 Fact 5 cites this exact limitation), so with no `$NAME`
    match found inside the token, that function harmlessly returns the
    token's own text UNCHANGED -- silently treating an unexpanded shell
    construct as though it were already a resolved literal path. Must
    deny, not pass `${paths[@]}` through as a literal filename."""
    reason, resolved = checker._resolve_path_tokens(["${paths[@]}"], {}, {})
    assert reason is not None
    assert resolved == ()


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=1, max_size=4))
def test_git_checkout_paths_extracts_every_token_after_double_dash(paths: list[str]) -> None:
    """Model-based, sub-case (a): every token after a literal `--` is a
    path -- the near-miss's own exact shape (`git checkout -- PATH`)."""
    reason, resolved = checker._git_checkout_paths(["--", *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


def test_git_checkout_paths_denies_double_dash_with_nothing_following() -> None:
    """`git checkout --` with no paths following denies outright: a
    harmless no-op in real git by itself, but a downstream pipe/loop could
    still append paths at runtime this classifier cannot see, and denying
    a genuine no-op costs nothing."""
    reason, resolved = checker._git_checkout_paths(["--"], {}, {})
    assert reason is not None
    assert resolved == ()


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=2, max_size=4))
def test_git_checkout_paths_extracts_two_or_more_positionals_with_no_double_dash(paths: list[str]) -> None:
    """Model-based, sub-case (b): with no `--`, 2+ non-flag-shaped
    positionals are ALL read as paths -- confirmed live that
    `git checkout no-such-ref no-such-file` reports a pathspec error for
    BOTH arguments, so every position past the first is a pathspec under
    every resolution real git can take once one exists at all."""
    reason, resolved = checker._git_checkout_paths(paths, {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(dot=st.sampled_from([".", ".."]))
def test_git_checkout_paths_treats_a_single_dot_or_dotdot_positional_as_a_path(dot: str) -> None:
    """Model-based, sub-case (c): a lone `.`/`..` positional (no `--`) is
    a path, not a ref -- both are syntactically invalid git ref names
    (confirmed live: `git check-ref-format --branch .`/`--branch ..` both
    fail), and `git checkout .` on a dirty tracked file was confirmed live
    to silently discard the change."""
    reason, resolved = checker._git_checkout_paths([dot], {}, {})
    assert reason is None
    assert resolved == (dot,)


@_PROPERTIES
@given(name=_PATH_TOKENS)
def test_git_checkout_paths_is_a_non_goal_for_a_single_bare_positional(name: str) -> None:
    """No false positive: a single positional that is not `.`/`..` (e.g.
    a branch name) is a deliberate Non-goal -- disambiguating a bare
    `git checkout SOMENAME` from a branch/ref name needs a live
    ref-existence lookup this pure classifier does not perform."""
    assume(name not in (".", ".."))
    reason, resolved = checker._git_checkout_paths([name], {}, {})
    assert reason is None
    assert resolved == ()


def test_git_checkout_paths_allows_a_flag_only_invocation() -> None:
    """No false positive: `git checkout -b new-branch` has one
    flag-shaped and one non-flag-shaped token, but the non-flag token is
    a branch name, not `.`/`..` -- stays the Non-goal, empty paths."""
    reason, resolved = checker._git_checkout_paths(["-b", "new-branch"], {}, {})
    assert reason is None
    assert resolved == ()


@_PROPERTIES
@given(staged=st.sampled_from(["--staged", "-S"]), paths=st.lists(_PATH_TOKENS, min_size=0, max_size=3))
def test_git_restore_paths_empty_when_staged_without_worktree(staged: str, paths: list[str]) -> None:
    """Model-based: `--staged`/`-S` without `--worktree` never touches the
    working tree -- empty `checkout_restore_paths`, never live-checked,
    regardless of what path arguments are also present."""
    reason, resolved = checker._git_restore_paths([staged, *paths], {}, {})
    assert reason is None
    assert resolved == ()


@_PROPERTIES
@given(worktree=st.sampled_from(["--worktree", "-W"]), paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_checked_when_staged_and_worktree_both_present(worktree: str, paths: list[str]) -> None:
    """Model-based, regression pin for issue #1375's own Fact 5: `--staged
    --worktree PATH` is a real working-tree-affecting restore despite
    `--staged` being present -- `saw_worktree=True` must still force the
    path to be checked."""
    reason, resolved = checker._git_restore_paths(["--staged", worktree, *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_checked_with_no_flags_at_all(paths: list[str]) -> None:
    """Model-based: a bare `git restore PATH` with no flags at all is
    never staged-only-safe -- always checked."""
    reason, resolved = checker._git_restore_paths(paths, {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(ref=_PATH_TOKENS, paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_checked_for_source_short_flag_not_conflated_with_staged(ref: str, paths: list[str]) -> None:
    """Model-based, regression pin for issue #1375's own Fact 5: `-s`
    (`--source`, value-taking) must never be conflated with `-S`
    (`--staged`, boolean) the way a lower-casing flag scan (like
    `_is_git_push_segment`'s own) would -- `git restore -s main PATH`
    stays checked, not wrongly read as staged-only-safe."""
    reason, resolved = checker._git_restore_paths(["-s", ref, *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(last=st.sampled_from(["--staged", "--no-staged"]))
def test_git_restore_paths_last_occurrence_wins_for_staged(last: str) -> None:
    """Model-based: `saw_staged` is last-occurrence-wins -- `--staged
    --no-staged` ends with `saw_staged=False` (checked), and `--no-staged
    --staged` ends with `saw_staged=True` (empty, iff no `--worktree`)."""
    flags = ["--no-staged", "--staged"] if last == "--staged" else ["--staged", "--no-staged"]
    reason, resolved = checker._git_restore_paths([*flags, "f.py"], {}, {})
    assert reason is None
    if last == "--staged":
        assert resolved == ()
    else:
        assert resolved == ("f.py",)


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_last_occurrence_wins_for_worktree(paths: list[str]) -> None:
    """Model-based: `saw_worktree` is last-occurrence-wins too --
    `--staged --worktree --no-worktree` ends with `saw_worktree=False`,
    so the invocation is safe (staged, not worktree) and never
    live-checked -- exercises the `--no-worktree` branch directly."""
    reason, resolved = checker._git_restore_paths(["--staged", "--worktree", "--no-worktree", *paths], {}, {})
    assert reason is None
    assert resolved == ()


@_PROPERTIES
@given(
    flag=st.sampled_from(sorted(checker._RESTORE_BOOLEAN_FLAGS)),
    paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3),
)
def test_git_restore_paths_every_boolean_flag_consumes_no_value(flag: str, paths: list[str]) -> None:
    """Model-based: every flag in the enumerated boolean vocabulary
    (`--quiet`/`-q`, `--progress`/`--no-progress`, `--overlay`/
    `--no-overlay`, `--ours`/`--theirs`, `--merge`/`-m`,
    `--ignore-unmerged`, `--ignore-skip-worktree-bits`) is skipped without
    consuming the token after it as a value -- the following path tokens
    are still extracted."""
    reason, resolved = checker._git_restore_paths([flag, *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(value=st.sampled_from(["yes", "no"]), paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_recurse_submodules_bare_and_fused(value: str, paths: list[str]) -> None:
    """Model-based: `--recurse-submodules` (bare, consumes nothing) and
    `--recurse-submodules=VALUE` (fused, self-contained) are both skipped
    without treating the next token as a value or as part of the flag."""
    reason, resolved = checker._git_restore_paths(["--recurse-submodules", *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)
    reason, resolved = checker._git_restore_paths([f"--recurse-submodules={value}", *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


def test_find_git_checkout_restore_none_when_only_global_flags_and_no_subcommand_follow() -> None:
    """No false positive, and direct coverage for the flag-skip loop's own
    normal (non-`break`, non-ambiguous) exit: `git -C /tmp/x` with global
    flags consuming every remaining token and nothing left over is not a
    checkout/restore invocation -- the while loop runs off the end of the
    segment (`j == n`) rather than finding a literal `checkout`/`restore`
    token."""
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(["git", "-C", "/tmp/x"], {}, {})
    assert subcommand is None
    assert tokens_after == []
    assert saw_tree_relocation is False


# --- Two LOW-severity false positives, found by the same independent
# adversarial review round that found the round-2 vanishing-decoy bypass
# above: `git restore` denied two entirely legitimate, harmless
# invocations outright as "unrecognized flag" because neither shape was in
# the enumerated vocabulary.


@_PROPERTIES
@given(paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_git_restore_paths_extracts_every_token_after_double_dash(paths: list[str]) -> None:
    """`--` disambiguates every remaining token as a pathspec for `git
    restore`, the identical role it plays for `git checkout` -- must be
    recognized, not denied as an unrecognized flag."""
    reason, resolved = checker._git_restore_paths(["--", *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


@_PROPERTIES
@given(
    flag_value=st.sampled_from([("--source", "main"), ("--conflict", "diff3")]),
    paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3),
)
def test_git_restore_paths_recognizes_fused_value_flags(flag_value: tuple[str, str], paths: list[str]) -> None:
    """`--source=VALUE`/`--conflict=VALUE` (fused with `=`) are equally
    legitimate git syntax as the separate-token form already recognized --
    must not be denied as an unrecognized flag."""
    flag, value = flag_value
    reason, resolved = checker._git_restore_paths([f"{flag}={value}", *paths], {}, {})
    assert reason is None
    assert resolved == tuple(paths)


def test_classify_allows_restore_double_dash_when_clean() -> None:
    verdict = checker.classify("git restore -- f.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


@_PROPERTIES
@given(flag=st.sampled_from(["--pathspec-from-file=list.txt", "--pathspec-from-file", "--pathspec-file-nul"]))
def test_git_restore_paths_denies_pathspec_from_file(flag: str) -> None:
    """Paths sourced from a file this classifier cannot inspect deny
    outright rather than silently under-extracting (an empty
    `checkout_restore_paths` would be exactly issue #1375 Fact 5's own
    fail-open shape)."""
    reason, resolved = checker._git_restore_paths([flag], {}, {})
    assert reason is not None
    assert resolved == ()


@_PROPERTIES
@given(flag=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8).map(lambda s: f"--{s}"))
def test_git_restore_paths_denies_an_unrecognized_flag(flag: str) -> None:
    """Fail-closed: any flag-shaped token outside the enumerated
    vocabulary denies outright -- this classifier cannot safely guarantee
    correct path extraction past a flag whose own value-consumption
    behavior it does not know."""
    assume(flag not in checker._RESTORE_BOOLEAN_FLAGS | checker._RESTORE_VALUE_FLAGS)
    assume(not flag.startswith("--pathspec-from-file") and not flag.startswith("--recurse-submodules"))
    assume(flag not in ("--staged", "--no-staged", "--worktree", "--no-worktree"))
    reason, resolved = checker._git_restore_paths([flag], {}, {})
    assert reason is not None
    assert resolved == ()


@_PROPERTIES
@given(prefix=st.lists(_PATH_TOKENS, min_size=0, max_size=3), paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_find_git_checkout_restore_finds_git_at_any_segment_position(prefix: list[str], paths: list[str]) -> None:
    """Model-based, regression pin found during this function's own
    development: scans for a literal `git` token at ANY position in the
    segment, not just `seg[0]` -- like `_is_git_push_segment`'s own scan.
    A `for VAR in ...; do ...; done` loop is one real reason this matters:
    bash's `for`/`do`/`done`/`in` keywords are not shell control
    operators, so `segment_tokens` never splits a segment at them, and
    `git checkout -- PATH` sitting after a literal `do` would never be
    found at `seg[0]`."""
    assume(all(p != "git" for p in prefix))
    seg = [*prefix, "git", "checkout", "--", *paths]
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(seg, {}, {})
    assert subcommand == "checkout"
    assert tokens_after == ["--", *paths]
    assert saw_tree_relocation is False


def test_find_git_checkout_restore_none_for_a_segment_with_no_git() -> None:
    """No false positive: a segment with no literal `git` token at all is
    never treated as a checkout/restore invocation."""
    subcommand, _tokens_after, _saw = checker._find_git_checkout_restore(["echo", "checkout", "restore"], {}, {})
    assert subcommand is None


@_PROPERTIES
@given(flag=st.sampled_from(["-C", "--git-dir", "--work-tree"]))
def test_find_git_checkout_restore_flags_tree_relocation(flag: str) -> None:
    """Model-based: `-C`/`--git-dir`/`--work-tree` (global flags that
    relocate which working tree git operates against) are flagged
    regardless of their own value -- the caller uses this to deny outright
    rather than let the live wrapper check the wrong tree (issue #1375's
    own Fact 5 cwd finding)."""
    seg = ["git", flag, "/some/path", "checkout", "--", "f.py"]
    subcommand, _tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(seg, {}, {})
    assert subcommand == "checkout"
    assert saw_tree_relocation is True


def test_find_git_checkout_restore_does_not_flag_lowercase_c_config_flag() -> None:
    """No false positive: `-c` (lowercase, sets a config value) is
    case-sensitively distinct from `-C` (uppercase, relocates the working
    tree) and must never be conflated with it (issue #1375's own Fact 5)."""
    seg = ["git", "-c", "user.name=x", "checkout", "--", "f.py"]
    subcommand, _tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(seg, {}, {})
    assert subcommand == "checkout"
    assert saw_tree_relocation is False


def test_find_git_checkout_restore_is_a_non_goal_for_a_dynamic_subcommand() -> None:
    """No false positive (disclosed Non-goal): a dynamically constructed
    subcommand name (`V=checkout; git $V -- f.py`) is not honest-accident-
    shaped and is not detected -- the same disclosed-residual convention
    this module's own `KNOWN_BYPASS_COMMANDS` test list already uses for
    the analogous dynamic-tool/dynamic-verb case."""
    subcommand, _tokens_after, _saw = checker._find_git_checkout_restore(["git", "$V", "--", "f.py"], {}, {})
    assert subcommand is None


# --- Regression pins for two real findings from this PR's own independent
# adversarial review (issue #1375), both confirmed live before being fixed.


def test_find_git_checkout_restore_skips_a_vanishing_decoy_between_git_and_subcommand() -> None:
    """CRITICAL regression pin. A genuinely-unset, unquoted `$NEVERSET`
    sitting between `git` and `checkout`/`restore` word-splits away to
    nothing at real bash runtime (confirmed live via a real bash proxy,
    stand-in `git` binary on PATH, capturing its own argv: `git $NEVERSET
    checkout -- file.py` genuinely runs `git checkout -- file.py`). Before
    this fix, `_find_git_checkout_restore` treated ANY dynamic token in
    this position as ambiguous and gave up, so this exact near-zero-effort
    decoy silently bypassed the entire checkout/restore safety feature --
    the same vanishing-decoy bug class `_is_git_push_segment` already
    closed for `git push` over rounds 20-24 of issue #1326, using the same
    `_token_is_all_unassigned_refs` primitive this fix now reuses here."""
    seg = ["git", "$NEVERSET", "checkout", "--", "file.py"]
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(seg, {}, {})
    assert subcommand == "checkout"
    assert tokens_after == ["--", "file.py"]
    assert saw_tree_relocation is False


def test_classify_denies_checkout_with_a_vanishing_decoy_when_dirty() -> None:
    """End-to-end regression pin for the same finding: `classify()` must
    surface the resolved path, not silently allow with an empty
    `checkout_restore_paths`, when a vanishing decoy sits between `git`
    and `checkout`."""
    verdict = checker.classify("git $NEVERSET checkout -- file.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("file.py",)


# --- Round 2: an empty-default/alt-clause decoy in the SAME position,
# found by a second, independent adversarial review pass after the first
# fix above landed. `${NEVERSET:-}`/`${NEVERSET-}`/`${NEVERSET:+x}` all
# vanish identically to a bare `$NEVERSET` when NEVERSET is genuinely
# unset (confirmed live via a real bash proxy), but `_token_is_all_
# unassigned_refs`'s own regex never matches these clause shapes at all --
# its own docstring deliberately excludes them for a non-empty default,
# which is correct, but does not carve out the empty-default case.


@_PROPERTIES
@given(
    clause=st.sampled_from(
        ["${NEVERSET:-}", "${NEVERSET-}", "${NEVERSET:=}", "${NEVERSET=}", "${NEVERSET:+x}", "${NEVERSET+x}"]
    )
)
def test_classify_denies_checkout_with_an_empty_default_or_alt_clause_decoy(clause: str) -> None:
    """CRITICAL regression pin, round 2 (plus the `${NAME:=}`/`${NAME=}`
    assign-default shapes found immediately afterward, same root cause).
    Every one of these six clause shapes, with NEVERSET genuinely never
    assigned, must be recognized as vanishing -- the same near-zero-effort
    bypass class as the bare `$NEVERSET` case, just spelled differently."""
    verdict = checker.classify(f"git {clause} checkout -- file.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("file.py",)


@_PROPERTIES
@given(
    name=_IDENTIFIERS,
    shape=st.sampled_from(
        ["${{{name}:-}}", "${{{name}-}}", "${{{name}:=}}", "${{{name}=}}", "${{{name}:+x}}", "${{{name}+x}}"]
    ),
)
def test_token_is_a_vanishing_default_or_alt_clause_true_for_any_unassigned_name(name: str, shape: str) -> None:
    """Model-based, direct coverage of `_token_is_a_vanishing_default_or_
    alt_clause` itself: for ANY identifier never assigned, all six
    empty-default/assign-default/alt-clause shapes are recognized as
    vanishing."""
    token = shape.format(name=name)
    assert checker._token_is_a_vanishing_default_or_alt_clause(token, {}) is True


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_token_is_a_vanishing_default_or_alt_clause_false_for_any_assigned_non_empty_name(
    name: str, value: str
) -> None:
    """Model-based: for ANY identifier assigned a real, non-empty value,
    the colon-form clauses never vanish."""
    assert checker._token_is_a_vanishing_default_or_alt_clause(f"${{{name}:-}}", {name: value}) is False
    assert checker._token_is_a_vanishing_default_or_alt_clause(f"${{{name}:+x}}", {name: value}) is False


def test_token_is_a_vanishing_default_or_alt_clause_true_for_empty_default_unassigned() -> None:
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET:-}", {}) is True
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET-}", {}) is True


def test_token_is_a_vanishing_default_or_alt_clause_true_for_empty_assign_default_unassigned() -> None:
    """`${NAME:=}`/`${NAME=}` (assign-default, empty text) also vanishes
    to nothing when NAME is unassigned -- confirmed live that this both
    substitutes the empty string AND assigns NAME the empty string as a
    side effect, but the side effect does not change whether THIS token
    itself occupies an argv position."""
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET:=}", {}) is True
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET=}", {}) is True


def test_token_is_a_vanishing_default_or_alt_clause_false_for_error_message_clause() -> None:
    """No false positive: `${NAME:?}`/`${NAME?}` is deliberately NOT
    recognized -- real bash terminates the whole command with an error
    when NAME is unset for this clause, rather than silently vanishing,
    so there is no real invocation for a missed detection to miss."""
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET:?}", {}) is False
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET?}", {}) is False


def test_token_is_a_vanishing_default_or_alt_clause_true_for_alt_clause_unassigned() -> None:
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET:+x}", {}) is True
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET+x}", {}) is True


def test_token_is_a_vanishing_default_or_alt_clause_false_for_non_empty_default() -> None:
    """No false positive: a NON-empty default text supplies real
    substitute text regardless of NAME's own state, so it never
    vanishes."""
    assert checker._token_is_a_vanishing_default_or_alt_clause("${NEVERSET:-x}", {}) is False


def test_token_is_a_vanishing_default_or_alt_clause_false_when_name_is_assigned_non_empty() -> None:
    """No false positive: a NAME assigned a real, non-empty value does not
    vanish under the colon forms."""
    assert checker._token_is_a_vanishing_default_or_alt_clause("${SET:-}", {"SET": "-C"}) is False
    assert checker._token_is_a_vanishing_default_or_alt_clause("${SET:+x}", {"SET": "-C"}) is False


def test_token_is_a_vanishing_default_or_alt_clause_no_colon_plus_requires_strictly_unset() -> None:
    """The no-colon `+` form checks "is NAME set AT ALL" (ignoring
    emptiness), a stricter condition than the colon form's "set and
    non-empty" -- a NAME assigned the empty string still counts as SET
    for this form, so `${NAME+word}` does NOT vanish (WORD is genuinely
    substituted at real bash runtime), unlike `${NAME:+word}` for the
    identical assigned-empty NAME."""
    assert checker._token_is_a_vanishing_default_or_alt_clause("${SET+x}", {"SET": ""}) is False
    assert checker._token_is_a_vanishing_default_or_alt_clause("${SET:+x}", {"SET": ""}) is True


def test_find_git_checkout_restore_does_not_skip_an_assigned_dynamic_token() -> None:
    """No false positive from the vanishing-decoy fix itself: a dynamic
    token that IS assigned a real (non-empty) value does not
    unambiguously vanish, so it still makes this `git` occurrence
    ambiguous -- unchanged from the pre-fix behavior for this case."""
    seg = ["git", "$SET", "checkout", "--", "file.py"]
    subcommand, _tokens_after, _saw = checker._find_git_checkout_restore(seg, {"SET": "-C"}, {})
    assert subcommand is None


def test_tokenize_splits_on_an_unquoted_newline() -> None:
    """MEDIUM regression pin. shlex's own default `whitespace` set
    includes `\\n`, silently swallowing an unquoted newline as ordinary
    inter-token whitespace and never producing it as its own token --
    making `_SINGLE_OPS`'s inclusion of `"\\n"` (and `segment_tokens`'s
    own documented newline-boundary behavior) dead code. Confirmed live
    that this let an ordinary two-line script (`git checkout` on one
    line, something unrelated with a `$` token on the next) get the
    second line's own token swept into the first line's own checkout
    path candidates and spuriously denied -- not a security miss (the
    fail-closed direction), but a real false-positive regression for a
    very common multi-line Bash tool-call shape."""
    tokens = checker.tokenize("echo a\necho b")
    assert tokens == ["echo", "a", "\n", "echo", "b"]


def test_tokenize_preserves_a_newline_inside_a_quoted_string() -> None:
    """No false positive from the newline fix itself: a newline INSIDE a
    quoted string is real string content, not a shell control operator,
    and must stay fused into its own token exactly as before."""
    tokens = checker.tokenize('echo "multi\nline"')
    assert tokens == ["echo", "multi\nline"]


def test_classify_does_not_leak_a_later_lines_token_into_an_earlier_checkout() -> None:
    """End-to-end regression pin for the newline finding: an ordinary
    two-line script with `git checkout` on the first line and an
    unrelated `$`-containing token on the second line must classify the
    checkout using only its own line's tokens. Deliberately avoids `-b`
    (which the round-4 branch-creation-flag fix folds into the Non-goal
    regardless of what follows on either line, no longer exercising
    sub-case (b)'s own 2-positional path extraction this test targets) --
    two ordinary non-flag positionals exercise the identical sub-case."""
    verdict = checker.classify('git checkout a.py b.py\necho "exit=$?"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("a.py", "b.py")


def test_shlex_default_punctuation_chars_still_matches_the_hardcoded_extension() -> None:
    """Pins the stdlib assumption `tokenize()`'s own newline fix depends
    on: shlex's documented default `punctuation_chars` value for
    `punctuation_chars=True`, which `tokenize()` now hardcodes (extended
    with `\\n`) rather than deriving at runtime. If a future Python
    version ever changes this default, this test fails loudly instead of
    `tokenize()` silently drifting from it."""
    default_lexer = shlex.shlex("x", posix=True, punctuation_chars=True)
    assert default_lexer.punctuation_chars == "();<>|&"


def test_strip_line_continuations_removes_an_unquoted_backslash_newline() -> None:
    """CRITICAL regression pin (round-3 independent review). An ordinary
    line-continued command -- backslash immediately followed by a newline,
    outside any quoting -- must vanish entirely, exactly as real bash
    resolves it, joining the two physical lines with nothing left behind."""
    assert checker._strip_line_continuations("git checkout -- \\\nfile.py") == "git checkout -- file.py"


def test_strip_line_continuations_removes_a_double_quoted_backslash_newline() -> None:
    """Real bash also removes a backslash-newline pair INSIDE double
    quotes (backslash retains its escaping meaning there), unlike shlex's
    own posix-mode escape handling, which left both characters untouched."""
    assert checker._strip_line_continuations('echo "a\\\nb"') == 'echo "ab"'


def test_strip_line_continuations_preserves_a_single_quoted_backslash_newline() -> None:
    """Inside single quotes, backslash has no special meaning at all, so a
    literal backslash-newline pair there must stay exactly as written --
    confirmed live real bash does not join these two lines."""
    assert checker._strip_line_continuations("echo 'a\\\nb'") == "echo 'a\\\nb'"


def test_strip_line_continuations_does_not_double_consume_an_escaped_backslash() -> None:
    """An escaped literal backslash (`\\\\`) must consume its own pair
    atomically so the second backslash is never re-examined as a fresh,
    wrongly-applied escape-introducer for the newline that follows it --
    confirmed live real bash keeps this newline (the second backslash was
    already spent escaping the first)."""
    assert checker._strip_line_continuations('echo "a\\\\\nb"') == 'echo "a\\\\\nb"'


def test_strip_line_continuations_preserves_a_raw_quoted_newline() -> None:
    """A genuine embedded newline inside a quoted string, with no
    preceding backslash at all, is real string content, not a line
    continuation, and must never be stripped."""
    assert checker._strip_line_continuations('echo "line1\nline2"') == 'echo "line1\nline2"'


@_PROPERTIES
@given(text=st.text(alphabet=st.characters(blacklist_characters="\\'\"\n"), max_size=40))
def test_strip_line_continuations_is_a_no_op_without_backslash_or_quote(text: str) -> None:
    """Property: with no backslash, quote, or newline in the input at
    all, `_strip_line_continuations` cannot find anything to remove, so it
    must return the input byte-for-byte unchanged."""
    assert checker._strip_line_continuations(text) == text


@_PROPERTIES
@given(text=st.text(alphabet="ab\\'\"\n", max_size=12))
def test_strip_line_continuations_is_idempotent(text: str) -> None:
    """Property: running the pass twice must equal running it once -- once
    every unescaped, non-single-quoted backslash-newline pair is removed,
    a second pass over the result finds nothing further to remove."""
    once = checker._strip_line_continuations(text)
    twice = checker._strip_line_continuations(once)
    assert once == twice


def test_classify_denies_a_line_continued_checkout_path_that_used_to_bypass() -> None:
    """End-to-end regression pin for the round-3 independent-review
    finding: an ordinary `\\`-then-newline-wrapped `git checkout --
    file.py` must resolve to the real path (`file.py`), not a path with a
    literal leading newline baked in (`'\\nfile.py'`, which the live `git
    diff` wrapper check would silently run against a nonexistent path and
    allow through)."""
    verdict = checker.classify("git checkout -- \\\nfile.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("file.py",)


def test_strip_comments_preserves_boundary_status_across_a_line_continuation() -> None:
    """CRITICAL regression pin (round-6 independent review, issue #1375).
    A genuine line continuation vanishes with nothing left behind once
    `_strip_line_continuations` runs afterward -- `_strip_comments` only
    passes the pair through unchanged, so the boundary status right after
    it must be whatever it was right BEFORE the backslash, not forced to
    False the way every other escaped pair correctly is. A `#` right
    after a continuation must still start a comment."""
    result = checker._strip_comments("echo a \\\n#comment\necho b")
    assert result == "echo a \\\n\necho b"


def test_strip_comments_passes_through_a_double_quoted_line_continuation_unchanged() -> None:
    """The round-6 fix's own double-quoted branch: a continuation pair
    INSIDE an open double-quoted string is passed through unchanged (no
    comment can start there regardless of boundary status, since `#` is
    only ever checked in the top-level unquoted branch), covering the
    `nxt == "\\n"` skip-path this function's double-quoted backslash
    handling shares with its unquoted twin."""
    result = checker._strip_comments('echo "a \\\nb"')
    assert result == 'echo "a \\\nb"'


def test_strip_comments_still_clears_boundary_for_a_non_continuation_escape() -> None:
    """No regression from the round-6 fix: an escaped, non-newline
    character is still real word content, not a boundary -- `\\#` right
    after it must NOT be read as a comment-starter."""
    result = checker._strip_comments("echo a\\x#notacomment")
    assert result == "echo a\\x#notacomment"


def test_classify_no_longer_leaks_a_comment_past_a_line_continuation() -> None:
    """End-to-end regression pin for the round-6 independent-review
    finding: a `#`-comment sitting on the continued line right after a
    `\\<newline>` must be recognized and stripped, not swept into
    `checkout_restore_paths` as a phantom path candidate that could name
    an unrelated, genuinely dirty file and produce a misleading deny."""
    verdict = checker.classify("git checkout -- clean.py \\\n# TODO revisit auth.py later\n")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("clean.py",)


def test_strip_comments_strips_a_comment_nested_inside_a_double_quoted_substitution() -> None:
    """CRITICAL, full-classifier-bypass regression pin (round-7
    independent review, issue #1375). Real bash recursively re-enters
    ordinary, comment-aware command parsing for a `$(...)` embedded
    inside an outer double-quoted string -- a `)` inside a `#`-comment
    inside such a substitution does NOT end the substitution. The old
    inline double-quote handling here did not know this, leaving the
    comment (and its embedded `)`) unstripped; that stray `)` then made
    `_find_fused_command_substitution`'s own naive paren counter mistake
    it for the substitution's real closing paren, silently truncating
    everything after it -- including a real `git checkout` on the next
    line -- from all classification. Live-verified this let a genuine,
    dirty-file checkout run for real while `classify()` reported
    `deny=False` with an empty `checkout_restore_paths`."""
    result = checker._strip_comments('x="$(echo hi #comment with paren ) here\ngit checkout -- dirty.py)"')
    assert result == 'x="$(echo hi \ngit checkout -- dirty.py)"'


def test_classify_no_longer_loses_a_checkout_behind_a_commented_paren_in_a_substitution() -> None:
    """End-to-end regression pin for the round-7 finding at the
    `classify()` level: the real `git checkout -- dirty.py` embedded
    past the decoy comment must be found, not silently dropped."""
    verdict = checker.classify('x="$(echo hi #comment with paren ) here\ngit checkout -- dirty.py)"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_strip_comments_strips_a_comment_inside_a_substitution_nested_two_levels_deep() -> None:
    """No shortcut taken for nesting depth: a comment inside a `$(...)`
    that is itself nested inside ANOTHER `$(...)` inside the outer
    double-quoted string must also be recognized and stripped, mirroring
    bash's own arbitrarily-recursive re-entrant grammar."""
    result = checker._strip_comments('x="$(echo $(echo hi #comment\n) tail)"')
    assert result == 'x="$(echo $(echo hi \n) tail)"'


def test_strip_comments_still_treats_a_literal_hash_inside_a_substitution_string_as_literal() -> None:
    """No over-stripping regression: a `#` inside a QUOTED span within
    the substitution's own content is still ordinary literal text, not a
    comment-starter -- matching the same rule this function already
    enforces at the top level."""
    result = checker._strip_comments("x=\"$(echo 'a#b' tail)\"")
    assert result == "x=\"$(echo 'a#b' tail)\""


@pytest.mark.parametrize(
    "command",
    [
        'x="$(echo \'abc)"',
        'x="$(echo "inner" tail)"',
        'x="$(echo a\\\\x)"',
        'x="$(echo (nested) tail)"',
        'x="$(echo abc',
    ],
    ids=[
        "unterminated-single-quote-inside-substitution",
        "nested-double-quote-inside-substitution",
        "non-newline-escape-inside-substitution",
        "nested-unquoted-parens-inside-substitution",
        "unterminated-substitution",
    ],
)
def test_strip_comments_is_a_no_op_without_a_comment_inside_a_substitution(command: str) -> None:
    """No crash and no unintended stripping on every other shape
    `_consume_command_substitution_content` must walk through correctly
    to find (or fail to find, for the unterminated case) its own
    matching close-paren -- none of these contain a `#`, so the result
    must be byte-for-byte identical to the input; a real unbalanced
    quote/substitution is `tokenize()`'s own concern to fail closed on,
    not this function's, which never itself validates balance."""
    assert checker._strip_comments(command) == command


def test_strip_comments_preserves_a_line_continuation_inside_a_substitution() -> None:
    """The round-6 boundary-preserving fix applies inside a substitution
    too, not only at the top level: a genuine `\\<newline>` there must
    not clear AT_BOUNDARY, so a `#`-comment right after it is still
    correctly recognized and stripped."""
    result = checker._strip_comments('x="$(echo a \\\nb #c\nd)"')
    assert result == 'x="$(echo a \\\nb \nd)"'


@pytest.mark.parametrize("flag", ["-b", "-B", "--orphan"])
def test_git_checkout_paths_folds_branch_creation_flags_into_the_non_goal(flag: str) -> None:
    """CRITICAL regression pin (round-4 independent review, issue #1375).
    `-b`/`-B`/`--orphan` take the immediately following token as their own
    new-branch-NAME value, which does not start with `-` -- sub-case (b)'s
    dash-prefix positional filter used to sweep that value (and a
    start-point after it) into `checkout_restore_paths` as if they were
    file paths, so `git checkout -f -b newbranch other` reported
    `('newbranch', 'other')` -- neither the real at-risk file -- and the
    wrapper's live check against those two nonexistent paths found "clean"
    and silently allowed a real, forced branch switch that discarded an
    uncommitted change elsewhere. Live-verified end-to-end that real git
    discards the change while the old code reported this as checked-safe.
    Must now fold into the same honest, no-claim Non-goal bare `git
    checkout SOMENAME` already carries -- empty paths, not a false claim."""
    reason, paths = checker._git_checkout_paths([flag, "newbranch", "other"], {}, {})
    assert reason is None
    assert paths == ()


def test_git_checkout_paths_branch_creation_flag_wins_even_with_a_double_dash() -> None:
    """`-b`/`-B`/`--orphan` is git's own branch-creation mode, mutually
    exclusive with every pathspec-checkout mode (per `git checkout -h`'s
    own synopsis) -- the Non-goal fold must fire before sub-case (a)'s own
    `--`-present branch is ever reached, not only when `--` is absent."""
    reason, paths = checker._git_checkout_paths(["-b", "newbranch", "--", "file.py"], {}, {})
    assert reason is None
    assert paths == ()


def test_git_checkout_paths_still_extracts_a_real_path_without_a_branch_creation_flag() -> None:
    """No regression from the branch-creation fold: an ordinary two-
    positional pathspec checkout with no `-b`/`-B`/`--orphan` present is
    unaffected."""
    reason, paths = checker._git_checkout_paths(["a.py", "b.py"], {}, {})
    assert reason is None
    assert paths == ("a.py", "b.py")


def test_classify_no_longer_falsely_claims_safety_for_a_forced_branch_creation() -> None:
    """End-to-end regression pin for the round-4 independent-review
    finding: `git checkout -f -b newbranch other` must resolve to an empty
    `checkout_restore_paths` (the honest Non-goal), never a claim naming
    the branch name/start-point as though they were the checked paths."""
    verdict = checker.classify("git checkout -f -b newbranch other")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


@_PROPERTIES
@given(flag=st.sampled_from(["--pathspec-from-file=list.txt", "--pathspec-from-file", "--pathspec-file-nul"]))
def test_git_checkout_paths_denies_pathspec_from_file(flag: str) -> None:
    """CRITICAL regression pin (round-5 independent review, issue #1375).
    `_git_restore_paths` already hard-denies this exact flag pair ("paths
    come from a file this classifier cannot inspect"), but
    `_git_checkout_paths` never recognized it at all -- a single
    positional after it fell through to the honest bare-SOMENAME Non-goal,
    which is the WRONG treatment for a flag whose own value-consumption is
    a file containing the real pathspecs, not an ambiguous ref/path.
    Live-verified end-to-end that this silently discarded a dirty tracked
    file listed in the control file."""
    reason, resolved = checker._git_checkout_paths([flag, "files.txt"], {}, {})
    assert reason is not None
    assert resolved == ()


def test_classify_denies_checkout_pathspec_from_file() -> None:
    """End-to-end regression pin for the round-5 finding at the
    `classify()` level, mirroring the already-existing restore-side pin."""
    verdict = checker.classify("git checkout --pathspec-from-file files.txt")
    assert verdict.deny is True
    assert "pathspec-from-file" in verdict.reason


@_PROPERTIES
@given(command_paths=st.lists(_PATH_TOKENS, min_size=1, max_size=3))
def test_rule_git_checkout_restore_accumulates_paths_across_segments(command_paths: list[str]) -> None:
    """Model-based: multiple checkout/restore invocations chained in one
    command (`git checkout -- a.py; git restore b.py`) accumulate paths
    from every segment, not just the first."""
    segments = [["git", "checkout", "--", *command_paths], ["git", "restore", *command_paths]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {}, {}, {}, {})
    assert reason is None
    assert resolved == (*command_paths, *command_paths)


def test_rule_git_checkout_restore_denies_when_git_dir_env_var_assigned() -> None:
    """Model-based, regression pin for issue #1375's own Fact 5: a
    `GIT_DIR=`/`GIT_WORK_TREE=`/`GIT_INDEX_FILE=` assignment anywhere in
    the command makes the wrapper's own fixed `.cwd` reference point
    unsound -- denied outright by the classifier itself (I/O-free, a
    token-shape fact) rather than letting the live wrapper check the
    wrong tree."""
    segments = [["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"GIT_DIR": "/tmp/x.git"}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_rule_git_checkout_restore_denies_when_an_earlier_segment_is_cd() -> None:
    """Model-based, regression pin for issue #1375's own Fact 5: an
    earlier segment in the same command containing a literal `cd` makes
    the wrapper's own fixed `.cwd` unsound for a LATER checkout/restore
    segment -- denied outright."""
    segments = [["cd", "/tmp"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_rule_git_checkout_restore_allows_cd_after_the_checkout_segment() -> None:
    """No false positive: `_rule_git_checkout_restore` only denies for a
    `cd` in an EARLIER segment -- a `cd` AFTER the checkout/restore segment
    does not retroactively make the already-scanned segment unsound."""
    segments = [["git", "checkout", "--", "f.py"], ["cd", "/tmp"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {}, {}, {}, {})
    assert reason is None
    assert resolved == ("f.py",)


@pytest.mark.parametrize("relocator", ["pushd", "popd"])
def test_rule_git_checkout_restore_denies_when_an_earlier_segment_is_pushd_or_popd(relocator: str) -> None:
    """CRITICAL regression pin (round-9 independent review, issue #1375).
    `pushd`/`popd` relocate the shell's own working directory exactly
    like `cd` does, but only a literal `cd` token was recognized here --
    live-verified this let `pushd sub && git checkout -- dirty.py`
    (dirty.py dirty relative to `sub`, absent at the PreToolUse payload's
    own `.cwd`) resolve to a CONFIDENT, WRONG `checkout_restore_paths`
    claim that the wrapper's live check then found clean at the wrong
    `.cwd`, silently allowing a real, uncommitted-change discard."""
    segments = [[relocator, "/tmp"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_classify_denies_a_checkout_hidden_behind_pushd() -> None:
    """End-to-end regression pin for the round-9 finding at the
    `classify()` level: the previously wrong, confident
    `checkout_restore_paths=('dirty.py',)` claim must become an honest
    outright deny instead."""
    verdict = checker.classify("pushd sub && git checkout -- dirty.py")
    assert verdict.deny is True
    assert "pushd" in verdict.reason


def test_rule_git_checkout_restore_denies_when_an_earlier_segment_starts_with_a_dynamic_non_vanishing_word() -> None:
    """CRITICAL regression pin (round-10 independent review, issue
    #1375). Round 9's literal-token scan only ever recognized
    `cd`/`pushd`/`popd` written out directly -- a dynamic command word
    (e.g. `$X` with `X=cd`) that resolves to one of those at real bash
    runtime was not recognized at all, live-verified to let `X=cd; $X
    sub; git checkout -- file.py` resolve to a CONFIDENT, WRONG
    `checkout_restore_paths` claim the same way round 9's own fix closed
    for the literal case."""
    segments = [["$X", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"X": "cd"}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_rule_git_checkout_restore_allows_a_genuinely_vanishing_dynamic_word() -> None:
    """No false positive: a dynamic `seg[0]` that unambiguously vanishes
    (word-splits to nothing at real bash runtime, e.g. an unset
    parameter with no default) is NOT flagged as a possible relocator --
    real bash would run whatever token follows as the actual command
    word instead, and that token is scanned on its own merits."""
    segments = [["${NEVERSET}", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {}, {}, {}, {})
    assert reason is None
    assert resolved == ("f.py",)


def test_classify_denies_a_checkout_hidden_behind_a_dynamic_cd() -> None:
    """End-to-end regression pin for the round-10 finding at the
    `classify()` level: a variable holding `cd` (or `pushd`) must deny
    the same way a literal `cd`/`pushd` does."""
    for cmd in (
        "X=cd; $X sub; git checkout -- file.py",
        "X=pushd; $X sub; git checkout -- file.py",
    ):
        verdict = checker.classify(cmd)
        assert verdict.deny is True, cmd
        assert verdict.checkout_restore_paths == ()


def test_rule_git_checkout_restore_allows_a_dynamic_word_resolving_to_something_harmless() -> None:
    """CRITICAL false-positive regression pin (round-11 independent
    review, issue #1375). Round 10's own first version flagged EVERY
    non-vanishing dynamic `seg[0]` regardless of what it could actually
    resolve to -- live-verified to wrongly deny `EDITOR=vim; $EDITOR sub;
    git checkout -- f.py`, a completely safe, ordinary command (an
    `$EDITOR`/`$TOOL` dispatch idiom followed by an unrelated, clean
    checkout), purely because `$EDITOR` is dynamic and non-vanishing.
    `_dynamic_word_may_resolve_to_a_cwd_relocator` must resolve the
    word's actual candidate value and only flag when it could genuinely
    be `cd`/`pushd`/`popd`.

    RAW_ASSIGNED_CD_BIASED here mirrors RAW_ASSIGNED exactly (round 20,
    issue #1375's own fourth argument) -- in real production use it is
    always built from the SAME token stream as RAW_ASSIGNED and so
    always carries the SAME entry for a name never assigned `cd`/`pushd`/
    `popd`; an EMPTY dict here would NOT be equivalent (unlike the
    git-biased fallback's own fail-toward-"not git" posture, `_dynamic_
    word_may_resolve_to_a_cwd_relocator`'s own posture fails toward
    "might be a relocator" on an unresolvable name, so a dict missing
    EDITOR's own entry would wrongly flag it once the first, correctly-
    resolving `raw_assigned` reading is bypassed by this test's own
    construction -- this is a hand-built-test-consistency requirement,
    not a live production gap, since production always keeps the two
    dicts' own key sets in sync)."""
    segments = [["$EDITOR", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"EDITOR": "vim"}, {}, {"EDITOR": "vim"}, {})
    assert reason is None
    assert resolved == ("f.py",)


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_dynamic_word_may_resolve_to_a_cwd_relocator_matches_relocator_set(name: str, value: str) -> None:
    """Model-based: `_dynamic_word_may_resolve_to_a_cwd_relocator` flags a
    resolvable dynamic word if and only if its resolved value is exactly
    one of `cd`/`pushd`/`popd` -- case-sensitively, matching real bash's
    own case-sensitive command-name lookup."""
    result = checker._dynamic_word_may_resolve_to_a_cwd_relocator(f"${name}", {name: value})
    assert result == (value in checker._CWD_RELOCATING_COMMANDS)


def test_dynamic_word_may_resolve_to_a_cwd_relocator_true_for_a_matching_assignment() -> None:
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("$X", {"X": "cd"}) is True
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("$X", {"X": "pushd"}) is True


def test_dynamic_word_may_resolve_to_a_cwd_relocator_false_for_a_harmless_assignment() -> None:
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("$EDITOR", {"EDITOR": "vim"}) is False


def test_dynamic_word_may_resolve_to_a_cwd_relocator_is_case_sensitive() -> None:
    """`cd`/`pushd`/`popd` are real bash command names, case-SENSITIVE --
    an assignment of `CD` (uppercase) must not be treated as resolving to
    the `cd` builtin, unlike this module's usual lowercased write-method
    comparisons elsewhere."""
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("$X", {"X": "CD"}) is False


def test_dynamic_word_may_resolve_to_a_cwd_relocator_true_when_unresolvable() -> None:
    """A token whose dynamism this classifier cannot decompose into
    `$NAME`-shaped references at all (e.g. a folded command-substitution
    placeholder) fails closed, preserving round 10's own blanket-flag
    behavior for this shape -- this primitive only ever narrows what
    round 10 already flagged, never widens it."""
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("__CMDSUB_PLACEHOLDER__", {}) is True


def test_dynamic_word_may_resolve_to_a_cwd_relocator_true_for_an_unresolvable_reference() -> None:
    """A `$NAME`-shaped reference this classifier cannot resolve at all
    (NAME never assigned) also fails closed, via
    `_substitute_var_refs_candidates`'s own empty-list return -- a
    narrower unit-level pin than the vanishing-check short-circuit
    `_rule_git_checkout_restore` applies before ever reaching this helper
    in that context."""
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("$NEVERSET", {}) is True


def test_classify_allows_a_checkout_hidden_behind_an_unrelated_dynamic_word() -> None:
    """End-to-end regression pin for the round-11 finding at the
    `classify()` level."""
    verdict = checker.classify("EDITOR=vim; $EDITOR sub; git checkout -- f.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


def test_dynamic_word_may_resolve_to_a_cwd_relocator_true_for_a_still_dynamic_candidate() -> None:
    """CRITICAL bypass regression pin (round-12 independent review, issue
    #1375). `_substitute_var_refs_candidates` does NOT recursively
    re-expand a `${NAME:-default}` clause's own DEFAULT text (a
    disclosed residual of that primitive itself) -- so when the default
    text is itself a `$OTHER` reference, the one returned candidate is
    the literal, still-unexpanded string `"$OTHER"`, never equal to
    `cd`/`pushd`/`popd` as plain text even when `$OTHER` genuinely holds
    one of those at real bash runtime. Live-verified before this fix:
    `${UNSET:-$OTHER}` with `OTHER=cd` resolved to a false `False`
    (not-a-relocator) verdict instead of failing closed, mirroring the
    identical still-dynamic-candidate check `_resolve_path_tokens`
    already carries for the same reason."""
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("${UNSET:-$OTHER}", {"OTHER": "cd"}) is True
    assert checker._dynamic_word_may_resolve_to_a_cwd_relocator("${UNSET:-$OTHER}", {"OTHER": "pushd"}) is True


def test_rule_git_checkout_restore_denies_a_still_dynamic_candidate() -> None:
    segments = [["${UNSET:-$OTHER}", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"OTHER": "cd"}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_classify_denies_a_checkout_hidden_behind_a_still_dynamic_default_clause() -> None:
    """End-to-end regression pin for the round-12 finding at the
    `classify()` level."""
    verdict = checker.classify("OTHER=cd; ${UNSET:-$OTHER} sub; git checkout -- dirty.py")
    assert verdict.deny is True
    assert verdict.checkout_restore_paths == ()


def test_first_surviving_segment_word_skips_a_leading_vanishing_run() -> None:
    """A leading run of vanishing decoys (bare-unassigned, then an empty
    default clause) is skipped, landing on the real surviving word --
    whether that word is dynamic or a plain literal."""
    assert checker._first_surviving_segment_word(["$NEVERSET", "${OTHER:-}", "$X"], {"X": "cd"}) == "$X"
    assert checker._first_surviving_segment_word(["$NEVERSET", "sub"], {}) == "sub"


def test_first_surviving_segment_word_none_when_everything_vanishes() -> None:
    assert checker._first_surviving_segment_word(["$NEVERSET", "${OTHER:-}"], {}) is None


def test_rule_git_checkout_restore_denies_a_dynamic_relocator_behind_a_leading_vanishing_decoy() -> None:
    """CRITICAL bypass regression pin (round-13 independent review, issue
    #1375). The prior `seg[0]`-only check silently skipped the whole
    segment whenever `seg[0]` itself genuinely vanished, even though the
    token that actually survives to become bash's real command word was
    never itself checked. Live-verified before this fix: `X=cd; $NEVERSET
    $X sub; git checkout -- dirty.py` (`NEVERSET` genuinely never
    assigned) resolved to a CONFIDENT, WRONG `checkout_restore_paths`
    claim -- real bash genuinely runs `cd sub` there."""
    segments = [["$NEVERSET", "$X", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"X": "cd"}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_classify_denies_a_checkout_hidden_behind_a_leading_vanishing_decoy() -> None:
    """End-to-end regression pin for the round-13 finding at the
    `classify()` level."""
    for cmd in (
        "X=cd; $NEVERSET $X sub; git checkout -- dirty.py",
        "X=pushd; $NEVERSET $X sub; git checkout -- dirty.py",
        "X=cd; ${NEVERSET:-} $X sub; git checkout -- dirty.py",
    ):
        verdict = checker.classify(cmd)
        assert verdict.deny is True, cmd
        assert verdict.checkout_restore_paths == ()


def test_redirect_span_length_recognizes_operator_and_target() -> None:
    assert checker._redirect_span_length([">", "/dev/null", "x"], 0) == 2
    assert checker._redirect_span_length([">&", "1", "x"], 0) == 2


def test_redirect_span_length_zero_when_no_redirect_present() -> None:
    assert checker._redirect_span_length(["checkout", "--", "f.py"], 0) == 0
    assert checker._redirect_span_length(["2", "checkout", "--", "f.py"], 0) == 0
    assert checker._redirect_span_length([">"], 0) == 0


def test_first_surviving_segment_word_skips_a_leading_redirect() -> None:
    assert checker._first_surviving_segment_word([">", "/dev/null", "$X"], {"X": "cd"}) == "$X"
    assert checker._first_surviving_segment_word(["$NEVERSET", ">", "/dev/null", "$X"], {"X": "cd"}) == "$X"


def test_rule_git_checkout_restore_denies_a_dynamic_relocator_behind_a_leading_redirect() -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). A leading redirect clause (ordinary, legal bash syntax) made
    `_first_surviving_segment_word` return the redirect operator token
    itself -- neither vanishing nor dynamic -- as the "surviving word,"
    so the real, cd-resolving `$X` one position later was never checked.
    Live-verified before this fix: `X=cd; > /dev/null $X sub; git
    checkout -- dirty.py` resolved to a confident, wrong ALLOW."""
    segments = [[">", "/dev/null", "$X", "sub"], ["git", "checkout", "--", "f.py"]]
    reason, resolved = checker._rule_git_checkout_restore(segments, {"X": "cd"}, {}, {}, {})
    assert reason is not None
    assert resolved == ()


def test_classify_denies_a_checkout_hidden_behind_a_leading_redirect() -> None:
    """End-to-end regression pin for the round-14 redirect-before-dynamic-
    word finding at the `classify()` level."""
    verdict = checker.classify("X=cd; > /dev/null $X sub; git checkout -- dirty.py")
    assert verdict.deny is True
    assert verdict.checkout_restore_paths == ()


def test_find_git_checkout_restore_skips_a_redirect_between_git_and_subcommand() -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). A fully literal command with a redirect between `git` and its
    subcommand was invisible to detection -- the redirect operator token
    was mistaken for the subcommand position and the scan gave up.
    Live-verified before this fix: `git > /dev/null checkout -- dirty.py`
    resolved to an empty, wrong `checkout_restore_paths`."""
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(
        ["git", ">", "/dev/null", "checkout", "--", "f.py"], {}, {}
    )
    assert subcommand == "checkout"
    assert tokens_after == ["--", "f.py"]
    assert saw_tree_relocation is False


def test_classify_extracts_paths_behind_a_redirect_between_git_and_subcommand() -> None:
    """End-to-end regression pin for the round-14 redirect-between-git-
    and-subcommand finding at the `classify()` level."""
    verdict = checker.classify("git > /dev/null checkout -- dirty.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES)
def test_dynamic_token_resolves_only_to_literal_matches_the_resolved_value(name: str, value: str) -> None:
    """Model-based: `_dynamic_token_resolves_only_to_literal` returns
    `True` if and only if the token's one resolved candidate equals the
    target literal, case-insensitively."""
    result = checker._dynamic_token_resolves_only_to_literal(f"${name}", {name: value}, "git")
    assert result == (value.lower() == "git")


def test_dynamic_token_resolves_only_to_literal_true_for_an_unambiguous_match() -> None:
    assert checker._dynamic_token_resolves_only_to_literal("$G", {"G": "git"}, "git") is True
    assert checker._dynamic_token_resolves_only_to_literal("$G", {"G": "GIT"}, "git") is True


def test_dynamic_token_resolves_only_to_literal_false_for_an_unrelated_value() -> None:
    assert checker._dynamic_token_resolves_only_to_literal("$G", {"G": "svn"}, "git") is False


def test_dynamic_token_resolves_only_to_literal_false_when_unresolvable() -> None:
    """A false positive here would mis-attribute an unrelated tool's own
    subcommand (e.g. `$TOOL checkout` where TOOL is not git) as a git
    checkout/restore invocation, so an ambiguous or unresolvable token
    declines rather than assumes the positive case -- the mirror image of
    `_dynamic_word_may_resolve_to_a_cwd_relocator`'s own fail-closed
    posture, appropriate here because the risk direction is reversed."""
    assert checker._dynamic_token_resolves_only_to_literal("$UNKNOWN", {}, "git") is False


def test_find_git_checkout_restore_recognizes_a_dynamic_git_token() -> None:
    """CRITICAL bypass regression pin (round-14 independent review, issue
    #1375). Only a LITERAL `git` token was ever recognized as the start
    of a checkout/restore invocation -- live-verified before this fix:
    `G=git; $G checkout -- dirty.py` resolved to an empty, wrong
    `checkout_restore_paths` even though `$G` unambiguously resolves to
    `git`."""
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(
        ["$G", "checkout", "--", "f.py"], {"G": "git"}, {}
    )
    assert subcommand == "checkout"
    assert tokens_after == ["--", "f.py"]
    assert saw_tree_relocation is False


def test_find_git_checkout_restore_declines_an_unresolvable_dynamic_first_word() -> None:
    """No false positive: a dynamic first token that does not unambiguously
    resolve to `git` (unrelated tool, or unresolvable) is not mistaken for
    a git invocation."""
    subcommand, _tokens_after, _saw_tree_relocation = checker._find_git_checkout_restore(
        ["$TOOL", "checkout", "--", "f.py"], {"TOOL": "svn"}, {}
    )
    assert subcommand is None


def test_classify_extracts_paths_behind_a_dynamic_git_token() -> None:
    """End-to-end regression pin for the round-14 dynamic-git-token
    finding at the `classify()` level."""
    verdict = checker.classify("G=git; $G checkout -- dirty.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


def test_classify_does_not_extract_paths_from_an_unrelated_dynamic_tool() -> None:
    """No false positive: `$TOOL checkout -- x` where TOOL resolves to a
    non-git tool must not be mistaken for a git checkout."""
    verdict = checker.classify("TOOL=svn; $TOOL checkout -- x")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


def test_strip_redirect_clauses_removes_a_redirect_wherever_it_occurs() -> None:
    assert checker._strip_redirect_clauses(["f.py", ">>", "log.txt"]) == ["f.py"]
    assert checker._strip_redirect_clauses([">>", "log.txt", "f.py"]) == ["f.py"]
    assert checker._strip_redirect_clauses(["f.py", ">&", "1"]) == ["f.py"]
    assert checker._strip_redirect_clauses(["f.py", "g.py"]) == ["f.py", "g.py"]


def test_strip_redirect_clauses_preserves_a_leading_digit_as_a_real_token() -> None:
    """CRITICAL data-loss regression pin (round-16 independent review,
    issue #1375): the strict, path-extraction-facing variant must NOT
    guess "consumed by the redirect" for a leading digit token -- see
    `_redirect_span_length`'s own docstring for why."""
    assert checker._strip_redirect_clauses(["f.py", "2", ">", "target.txt"]) == ["f.py", "2"]


def test_git_checkout_paths_excludes_a_trailing_redirect_clause() -> None:
    """CRITICAL false-positive regression pin (round-15 independent
    review, issue #1375). Round 14 taught `_find_git_checkout_restore`
    and `_first_surviving_segment_word` to skip a redirect clause, but
    never taught the path-extraction functions the same lesson -- a
    redirect operator and its target were swept into
    `checkout_restore_paths` as if they were real git path arguments.
    Live-verified before this fix: `git checkout -- f.py >>
    unrelated_append_target.py` resolved to `checkout_restore_paths=
    ('f.py', '>>', 'unrelated_append_target.py')`, causing the live
    wrapper check to wrongly deny whenever the unrelated append target
    happened to be dirty, even though an append redirect can never
    discard that file's existing content."""
    deny_reason, paths = checker._git_checkout_paths(["--", "f.py", ">>", "unrelated_append_target.py"], {}, {})
    assert deny_reason is None
    assert paths == ("f.py",)


def test_git_restore_paths_excludes_a_trailing_redirect_clause() -> None:
    deny_reason, paths = checker._git_restore_paths(["f.py", ">>", "unrelated_append_target.py"], {}, {})
    assert deny_reason is None
    assert paths == ("f.py",)


def test_classify_does_not_flag_a_redirect_target_as_a_checkout_path() -> None:
    """End-to-end regression pin for the round-15 finding at the
    `classify()` level."""
    for cmd in (
        "git checkout -- f.py >> unrelated_append_target.py",
        "git restore f.py >> unrelated_append_target.py",
    ):
        verdict = checker.classify(cmd)
        assert verdict.deny is False, cmd
        assert verdict.checkout_restore_paths == ("f.py",), cmd


def test_redirect_span_length_never_consumes_a_leading_digit() -> None:
    """CRITICAL data-loss regression pin (round-16 independent review,
    issue #1375). `tokenize()`'s own shlex punctuation-splitting cannot
    distinguish a fused `2>file` (a genuine fd-redirect prefix, no
    argument) from a spaced `2 >file` (the literal word `2` followed by
    a separate redirect) -- both produce the identical token sequence.
    The strict, path-extraction-facing `_redirect_span_length` must NOT
    guess "consumed by the redirect" for the leading digit: doing so
    silently drops a real argument from `checkout_restore_paths`."""
    assert checker._redirect_span_length(["2", ">", "target.txt"], 0) == 0
    assert checker._redirect_span_length([">", "target.txt"], 0) == 2


def test_git_checkout_paths_does_not_drop_a_digit_shaped_path() -> None:
    """CRITICAL data-loss regression pin (round-16 independent review,
    issue #1375). Live-verified before this fix: `git checkout --
    realfile.py 2 >target.txt` resolved to
    `checkout_restore_paths=('realfile.py',)`, silently dropping `2` (a
    real, dirty, tracked file) -- the classifier's own former digit-
    consuming redirect heuristic wrongly treated `2` as an fd-redirect
    prefix rather than a real path argument."""
    deny_reason, paths = checker._git_checkout_paths(["--", "realfile.py", "2", ">", "target.txt"], {}, {})
    assert deny_reason is None
    assert paths == ("realfile.py", "2")


def test_git_restore_paths_does_not_drop_a_real_path_behind_a_digit_redirect() -> None:
    """CRITICAL data-loss regression pin (round-16 independent review,
    issue #1375). Live-verified before this fix: `git restore --source 2
    >target.txt file.py` resolved to an EMPTY `checkout_restore_paths` --
    once `2` vanished into the wrongly-recognized redirect, `--source`'s
    own value-consumption swallowed `file.py` itself, the actual restore
    target, leaving nothing for the live wrapper check to examine."""
    deny_reason, paths = checker._git_restore_paths(["--source", "2", ">", "target.txt", "file.py"], {}, {})
    assert deny_reason is None
    assert paths == ("file.py",)


def test_classify_does_not_drop_a_digit_shaped_path_behind_a_redirect() -> None:
    """End-to-end regression pin for the round-16 finding at the
    `classify()` level."""
    verdict = checker.classify("git checkout -- realfile.py 2 >target.txt")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("realfile.py", "2")


def test_redirect_span_length_with_optional_fd_recognizes_a_fused_fd_redirect() -> None:
    """CRITICAL false-negative regression pin (round-16 independent
    review, issue #1375, own follow-up). The strict, digit-free
    `_redirect_span_length` alone made the subcommand-finding/cwd-
    relocation walks stop on a bare digit token sitting in front of a
    genuine `2>&1`-shaped redirect, so a fully literal, unambiguous `git
    > out.log 2>&1 checkout -- dirty.py` went entirely unrecognized as a
    checkout invocation (empty `checkout_restore_paths`, the live
    wrapper check never runs at all) -- the FAIL-OPEN direction for this
    walk. `_redirect_span_length_with_optional_fd` (used only by the
    skip-PAST-a-possible-redirect walks, never by path extraction)
    closes this by also consuming an optional leading digit."""
    assert checker._redirect_span_length_with_optional_fd(["2", ">&", "1", "checkout"], 0) == 3
    assert checker._redirect_span_length_with_optional_fd([">", "out.log", "checkout"], 0) == 2
    assert checker._redirect_span_length_with_optional_fd(["checkout"], 0) == 0


def test_find_git_checkout_restore_skips_a_digit_prefixed_redirect_between_git_and_subcommand() -> None:
    subcommand, tokens_after, saw_tree_relocation = checker._find_git_checkout_restore(
        ["git", ">", "out.log", "2", ">&", "1", "checkout", "--", "f.py"], {}, {}
    )
    assert subcommand == "checkout"
    assert tokens_after == ["--", "f.py"]
    assert saw_tree_relocation is False


def test_classify_extracts_paths_behind_multiple_redirects_including_a_digit_prefixed_one() -> None:
    """End-to-end regression pin for the round-16 follow-up finding at
    the `classify()` level."""
    verdict = checker.classify("git > out.log 2>&1 checkout -- dirty.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("dirty.py",)


# --- End-to-end classify() coverage, pinning every explicit safe/deny case
# issue #1375's own Acceptance Criteria Map and "Explicit safe cases"
# section name by hand.


@_PROPERTIES
@given(ref=st.sampled_from(["main", "HEAD~1", "some-branch"]))
def test_classify_allows_ordinary_branch_switching(ref: str) -> None:
    verdict = checker.classify(f"git checkout {ref}")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


def test_classify_allows_checkout_dash_b() -> None:
    verdict = checker.classify("git checkout -b new-branch")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


def test_classify_allows_restore_staged_only() -> None:
    verdict = checker.classify("git restore --staged f.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


def test_classify_extracts_path_for_checkout_double_dash() -> None:
    verdict = checker.classify("git checkout -- f.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


def test_classify_extracts_dot_for_checkout_dot() -> None:
    verdict = checker.classify("git checkout .")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == (".",)


def test_classify_extracts_path_for_bare_restore() -> None:
    verdict = checker.classify("git restore f.py")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


def test_classify_resolves_a_same_command_assignment_to_a_literal_path() -> None:
    """A dynamic path token that resolves to a literal via a same-command
    assignment (`f=README.md; git checkout -- "$f"`) is substituted and
    surfaced as a candidate, not denied."""
    verdict = checker.classify('f=README.md; git checkout -- "$f"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("README.md",)


def test_classify_denies_a_loop_fed_dynamic_checkout_path() -> None:
    """Regression pin for issue #1375's own Acceptance Criteria Map: a
    `for`-loop-fed dynamic path with no same-command assignment for the
    loop variable is unresolvable and denies outright, rather than
    silently passing through with an empty `checkout_restore_paths`."""
    verdict = checker.classify('for f in $(git diff --name-only); do git checkout -- "$f"; done')
    assert verdict.deny is True


def test_classify_denies_an_array_subscript_fed_checkout_path() -> None:
    """Regression pin for issue #1375's own Acceptance Criteria Map: the
    `${paths[@]}`-shaped array-subscript indirection is a real, pinned
    `KNOWN_BYPASS` shape (this module's own `array-literal-assignment-
    indirection` entry) for the same underlying `_VAR_REF_FULL_RE`
    limitation -- must deny, not silently pass an unresolved literal
    string through as a path."""
    verdict = checker.classify('paths=(a.py b.py); git checkout -- "${paths[@]}"')
    assert verdict.deny is True


def test_classify_threads_checkout_restore_paths_through_command_substitution() -> None:
    """Regression pin, mirroring the fifteenth-round `is_git_push`
    recursion-drop fix this module already carries: a checkout/restore
    invocation embedded in a `$(...)` command substitution must still
    surface its own `checkout_restore_paths` in the outer `Verdict`, not
    silently drop it the way an earlier version of this function would
    have."""
    verdict = checker.classify("x=$(git checkout -- f.py)")
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


def test_classify_threads_checkout_restore_paths_through_array_literal() -> None:
    """Regression pin, mirroring `_rule_array_literal_content`'s own
    nineteenth-round outer-scope fix: a checkout/restore invocation
    embedded in a `NAME=(...)` array literal must still surface its own
    `checkout_restore_paths` in the outer `Verdict`."""
    verdict = checker.classify('A=(git checkout -- f.py); "${A[@]}"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ("f.py",)


def test_classify_denies_checkout_with_a_tree_relocation_flag() -> None:
    """Regression pin for issue #1375's own Fact 5 cwd finding: a `-C`
    global flag makes the wrapper's fixed `.cwd` unsound for this
    invocation -- denied outright by the classifier."""
    verdict = checker.classify("git -C /tmp/some-repo checkout -- f.py")
    assert verdict.deny is True


def test_classify_denies_checkout_after_an_earlier_cd() -> None:
    """Regression pin for issue #1375's own Fact 5 cwd finding: an
    earlier `cd` in the same command makes the wrapper's fixed `.cwd`
    unsound for a later checkout -- denied outright."""
    verdict = checker.classify("cd /tmp; git checkout -- f.py")
    assert verdict.deny is True


def test_classify_does_not_flag_checkout_restore_prose_inside_a_commit_message() -> None:
    """No false positive: this module's own established convention (see
    its module docstring's own "no substring/prose fallback" constraint)
    -- `git checkout`-shaped TEXT sitting inside an unrelated command's own
    quoted string argument is not a real invocation and must never be
    flagged, unlike `_rule_a_literal`'s own deliberate same-token
    literal-phrase fallback for install verbs (a `deny`-severity false
    positive here would fire exactly when files are legitimately dirty,
    which this gate cannot tolerate the way a `warn` could)."""
    verdict = checker.classify('git commit -m "revert via git checkout -- foo.py"')
    assert verdict.deny is False
    assert verdict.checkout_restore_paths == ()


def test_classify_leaves_ordinary_git_push_unaffected() -> None:
    """No regression: this is purely additive detection surface -- an
    ordinary `git push` must still classify exactly as before, with no
    checkout_restore_paths."""
    verdict = checker.classify("git push origin main")
    assert verdict.deny is False
    assert verdict.is_git_push is True
    assert verdict.checkout_restore_paths == ()


def test_main_output_includes_checkout_restore_paths_for_a_checkout_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """End-to-end: the stdin-JSON entrypoint surfaces `checkout_restore_
    paths` as a genuine JSON array (issue #1375: not a newline-joined
    string, so hooks/check-bash-safety.sh's own new wrapper step can
    base64-decode each element safely even if a path contains a
    newline)."""
    payload = {"tool_name": "Bash", "tool_input": {"command": "git checkout -- f.py"}}
    out = _run_main(payload, monkeypatch, capsys)
    assert out["decision"] == "allow"
    assert out["checkout_restore_paths"] == ["f.py"]


def test_main_output_includes_empty_checkout_restore_paths_for_a_harmless_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    out = _run_main(payload, monkeypatch, capsys)
    assert out["checkout_restore_paths"] == []

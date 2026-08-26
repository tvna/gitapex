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
    extracted = checker._gh_api_method_dynamic_value(seg, index, seg[index])
    assert extracted is not None
    assert f"${var}" in extracted


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
    assert checker._is_git_push_segment(seg)


@_PROPERTIES
@given(flag=st.sampled_from(["--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"]))
def test_is_git_push_segment_true_for_long_flag_fused_equals_form(flag: str) -> None:
    """No regression: the fused `=` form these long flags already
    handled correctly continues to work after adding separate-token
    support alongside it."""
    seg = ["git", f"{flag}=/tmp/some/value", "push", "origin"]
    assert checker._is_git_push_segment(seg)


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
    reason, _ = checker._rule_command_substitution_content(tokens)
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
    assert checker._rule_command_substitution_content(tokens) == (None, False)


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
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
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
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
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
    assert checker._rule_array_literal_content(tokens, {}, {}) == (None, False)


def test_rule_array_literal_content_no_span_present() -> None:
    """Robustness: a token stream with no array-literal span at all
    (e.g. an ordinary command) returns cleanly, never a crash."""
    assert checker._rule_array_literal_content(["echo", "hi"], {}, {}) == (None, False)


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
    assert checker._rule_array_literal_content(tokens, {}, {}) == (None, False)


def test_rule_array_literal_content_skips_the_collapsed_reading_without_a_leading_unassigned_ref() -> None:
    """No false positive / no redundant work: an array literal whose own
    first element is NOT an unassigned bare reference has nothing for
    `_strip_leading_unassigned_bare_refs` to strip -- the collapsed
    reading equals the as-is one, so only one classification is needed."""
    tokens = ["dummy=", "(", "echo", "harmless", ")"]
    assert checker._rule_array_literal_content(tokens, {}, {}) == (None, False)


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
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
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
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
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
    reason, _ = checker._rule_array_literal_content(tokens, outer, outer)
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
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
    assert reason is not None


def test_rule_array_literal_content_detects_a_fused_reference_chain_decoy() -> None:
    """Model-based, regression pin for the real bypass found live by Step
    8 independent review, twentieth round (issue #1326): `A=($A_UNSET
    $B_UNSET gh pr merge 1); "${A[@]}"` (both unset) was wrongly ALLOWED
    before a fused chain of two bare references was recognized as
    vanishing as a unit."""
    tokens = ["dummy=", "(", "$A_UNSET$B_UNSET", "gh", "pr", "merge", "1", ")"]
    reason, _ = checker._rule_array_literal_content(tokens, {}, {})
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
    reason, _ = checker._rule_command_substitution_content(tokens)
    assert reason is not None


def test_rule_command_substitution_content_skips_blank_fused_span_then_finds_denial() -> None:
    """A blank/whitespace-only fused span contributes nothing and is
    skipped without denying by itself, but scanning continues to the next
    fused span in the same token."""
    tokens = ["echo", "$( )$(pip install evil-pkg)"]
    reason, _ = checker._rule_command_substitution_content(tokens)
    assert reason is not None


def test_rule_command_substitution_content_both_fused_spans_harmless() -> None:
    tokens = ["echo", "$(echo ok)$(echo also-ok)"]
    assert checker._rule_command_substitution_content(tokens) == (None, False)


def test_rule_command_substitution_content_empty_unquoted_span_skipped() -> None:
    """An empty, unquoted `$()` substitution has no inner tokens to
    recurse into -- distinct from the fused/quoted empty-span case above."""
    tokens = ["$", "(", ")"]
    assert checker._rule_command_substitution_content(tokens) == (None, False)


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
    assert checker._is_git_push_segment(["git"]) is False


def test_is_git_push_segment_value_flag_followed_by_another_flag() -> None:
    """ "-C" is a value-taking short flag; when the NEXT token itself looks
    like a flag ("-v", starts with "-"), it must NOT be consumed as -C's
    own value -- the loop re-examines it as its own flag instead."""
    assert checker._is_git_push_segment(["git", "-C", "-v", "push"]) is True


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

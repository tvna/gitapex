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


# --- Round 5: the -X/--method/-f/--field flag NAME itself hidden behind a
# bare variable reference (issue #1326, found live by Step 8 independent
# review, fifth round). Every check above assumes the flag token carries a
# literal "-x"/"--method"/"-f"/"--field" text prefix somewhere in itself --
# a token that is PURELY `$F` has none, so none of them ever recognized it
# as a flag at all until `_resolve_bare_var` and the two
# `*_flagname_dynamic_hit` passes below closed this.


@_PROPERTIES
@given(name=_IDENTIFIERS, value=_VALUES, braced=st.booleans())
def test_resolve_bare_var_resolves_a_bare_or_braced_reference(name: str, value: str, braced: bool) -> None:
    """Model-based: a token that is *exactly* one variable reference,
    ``$NAME`` or ``${NAME}``, resolves to that variable's assigned
    (lowercased) value via ``name_to_value`` -- both bracing shapes are
    equivalent references to the same variable."""
    token = f"${{{name}}}" if braced else f"${name}"
    assert checker._resolve_bare_var(token, {name: value.lower()}) == value.lower()


@_PROPERTIES
@given(name=_IDENTIFIERS, suffix=_VALUES)
def test_resolve_bare_var_none_for_a_fused_or_unassigned_token(name: str, suffix: str) -> None:
    """No false positive: a token carrying anything beyond the bare
    reference (e.g. ``${NAME}suffix``) is deliberately NOT resolved --
    narrower than a full expansion, matching the "specific, checked
    structural pattern" discipline the other B-rules already follow, not
    "this token is dynamic somehow." A bare reference to a name that was
    never assigned also resolves to None."""
    assert checker._resolve_bare_var(f"${{{name}}}{suffix}", {name: "post"}) is None
    assert checker._resolve_bare_var(f"${name}", {}) is None


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
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value)


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), flag_var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_detects_dynamic_flagname_literal_value(method: str, flag_var: str) -> None:
    """Model-based: the same bypass class also holds when only the flag
    NAME is hidden behind a variable and the value stays a literal token
    (``F=-X; gh api .../merge $F POST``)."""
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", method]
    assert checker._gh_api_method_flagname_dynamic_hit(seg, {flag_var: "-x"})


@_PROPERTIES
@given(flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_allows_a_dynamic_flagname_resolved_to_a_read(
    flag_var: str, value_var: str
) -> None:
    """No false positive: a dynamic flag-name token that resolves to
    -X/--method, followed by a value that resolves to GET (not one of the
    four write methods), is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]
    assert not checker._gh_api_method_flagname_dynamic_hit(seg, {flag_var: "-x", value_var: "get"})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a bare variable reference that does not resolve
    to -X/--method at all is never treated as a flag."""
    seg = ["gh", "api", "repos/x/y", f"${var}", "POST"]
    assert not checker._gh_api_method_flagname_dynamic_hit(seg, {var: "repos/x/y"})


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
    assert checker._gh_api_field_flagname_dynamic_hit(seg, {flag_var: flag_name})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_field_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a bare variable reference that does not resolve
    to a field flag at all is never treated as one."""
    seg = ["gh", "api", "repos/x/y", f"${var}"]
    assert not checker._gh_api_field_flagname_dynamic_hit(seg, {var: "repos/x/y"})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_flagname_and_value_both_dynamic(method: str, flag_var: str, value_var: str) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the fifth-round bypass is caught at the
    orchestrator level, not just the sub-pass level."""
    assume(flag_var != value_var)  # distinct dict keys, same guard as the sub-pass test above
    segments = [["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]]
    name_to_value = {flag_var: "-x", value_var: method}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${flag_var} ${value_var}", name_to_value)
    assert result is not None


@_PROPERTIES
@given(flag_var=_IDENTIFIERS, value_var=_IDENTIFIERS)
def test_rule_gh_api_write_allows_flagname_dynamic_resolved_to_a_read(flag_var: str, value_var: str) -> None:
    """No false positive at the orchestrator level: a dynamic flag-name
    token resolved to -X, with its value resolved to GET, must stay
    allowed."""
    segments = [["gh", "api", "repos/x/y", f"${flag_var}", f"${value_var}"]]
    name_to_value = {flag_var: "-x", value_var: "get"}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y ${flag_var} ${value_var}", name_to_value)
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
    candidates = checker._substitute_var_refs_candidates(token, {name1: part1, name2: part2})
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
    candidates = checker._substitute_var_refs_candidates(token, {name: value.lower()})
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
    assert checker._substitute_var_refs_candidates(token, {assigned_name: value.lower()}) == []


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
    assert checker._gh_api_method_dynamic_hit(seg, {var1: part1, var2: part2})


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
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value)


@_PROPERTIES
@given(var1=_IDENTIFIERS, var2=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_a_concatenated_value_resolved_to_a_read(var1: str, var2: str) -> None:
    """No false positive: a concatenated value that resolves to GET, not
    one of the four write methods, is never flagged."""
    assume(var1 != var2)
    seg = ["gh", "api", "repos/x/y", "-X", f"${var1}${var2}"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var1: "ge", var2: "t"})


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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var1}${var2}", name_to_value)
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
    assert checker._gh_api_method_dynamic_hit(seg, {var: var_value})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_uppercase_literal_fragment_resolved_to_a_read(var: str) -> None:
    """No false positive: an uppercase literal fragment fused with a
    variable that resolves to a read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", "-X", f"GE${var}"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var: "t"})


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
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value)


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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x {literal}${var}", name_to_value)
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
    candidates = checker._substitute_var_refs_candidates(token, {var: part1})
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
    assert checker._gh_api_method_dynamic_hit(seg, {var: part1})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_dynamic_hit_allows_unbraced_reference_followed_by_more_identifier_text_read(var: str) -> None:
    """No false positive: the bounded-reference reading resolving to a
    read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", "-X", f"${var}T"]
    assert not checker._gh_api_method_dynamic_hit(seg, {var: "ge"})


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
    assert checker._gh_api_method_flagname_dynamic_hit(seg, name_to_value)


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
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y -x ${var}{part2}", name_to_value)
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
    assert checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "-x"})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_fused_flagname_dynamic_hit_allows_a_read_method(var: str) -> None:
    """No false positive: the fused flag-plus-value reading resolving to a
    read method (GET) must stay allowed."""
    seg = ["gh", "api", "repos/x/y", f"${var}GET"]
    assert not checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "-x"})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_method_fused_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a dynamic token whose resolved value does not
    start with "-x"/"--method=" at all is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${var}issues"]
    assert not checker._gh_api_method_fused_flagname_dynamic_hit(seg, {var: "repos/owner"})


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
    assert checker._gh_api_field_fused_flagname_dynamic_hit(seg, {var: flag_name})


@_PROPERTIES
@given(var=_IDENTIFIERS)
def test_gh_api_field_fused_flagname_dynamic_hit_allows_an_unrelated_dynamic_token(var: str) -> None:
    """No false positive: a dynamic token whose resolved value does not
    start with a field-flag shape at all is never flagged."""
    seg = ["gh", "api", "repos/x/y", f"${var}issues"]
    assert not checker._gh_api_field_fused_flagname_dynamic_hit(seg, {var: "repos/owner"})


@_PROPERTIES
@given(method=st.sampled_from(["post", "put", "patch", "delete"]), var=_IDENTIFIERS)
def test_rule_gh_api_write_detects_fused_flagname_and_value_in_one_token(method: str, var: str) -> None:
    """End-to-end regression pin, matching the other ``_rule_gh_api_write``
    end-to-end tests above: the eighth-round fused-flagname bypass is
    caught at the orchestrator level too, not just the sub-pass level."""
    token = f"${var}{method.upper()}"
    segments = [["gh", "api", "repos/x/y", token]]
    name_to_value = {var: "-x"}
    result = checker._rule_gh_api_write(segments, f"gh api repos/x/y {token}", name_to_value)
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
    assert checker._rule_b1b_dynamic_word_assigned_tool_and_verb(seg, name_to_value, checker._WATCHED_VERBS)


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

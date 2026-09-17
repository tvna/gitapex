"""Hypothesis property-based layer for
``skills/evaluating-context-channel-maturity/scripts/gitapex_check_channel_shape.py``
(issue #1178's own ``detection-logic-property-coverage`` gate, opened for
this brand-new module by issue #1987's own Task 2 diff -- every detection
call site in that module is "new" relative to origin/main, so this file
covers every flagged function rather than one, unlike
``tests/test_gitapex_check_skill_shape_properties.py``'s own narrower,
incremental scope against a long-lived sibling module).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching that same file's own established rationale
(this repository runs pytest under ``pytest-xdist``, where a randomly-seeded
generator turns a latent failure into an intermittently red suite).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import gitapex_check_channel_shape as ccs
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# No ":" or "#" -- keeps a generated value from ever accidentally tripping
# one of the four yaml-unsafe patterns except the one each dedicated test
# below deliberately constructs.
_SAFE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-."
_SAFE_TEXT = st.text(alphabet=_SAFE_ALPHABET, max_size=40)

# Also excludes "-", so a generated value can never accidentally spell a
# "---" frontmatter delimiter when embedded inside a constructed block body.
_BLOCK_SAFE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _."
_TRIMMED_BLOCK_TEXT = (
    st.text(alphabet=_BLOCK_SAFE_ALPHABET, min_size=1, max_size=60).map(lambda s: s.strip()).filter(lambda s: s != "")
)

# A bare tool-name token: alnum/underscore only, never empty -- matches
# _declared_boundary's own re.split(r"[,\s]+", ...) filter exactly, so a
# space-joined list of these round-trips through it unchanged.
_TOKEN_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
_TOKEN = st.text(alphabet=_TOKEN_ALPHABET, min_size=1, max_size=10)

_PATH_COMPONENT = st.text(alphabet=_TOKEN_ALPHABET, min_size=1, max_size=10)


# --- _unquote ---------------------------------------------------------


@_PROPERTIES
@given(inner=_SAFE_TEXT)
def test_matching_single_quotes_are_stripped(inner: str) -> None:
    assert ccs._unquote(f"'{inner}'") == inner


@_PROPERTIES
@given(inner=_SAFE_TEXT)
def test_matching_double_quotes_are_stripped(inner: str) -> None:
    assert ccs._unquote(f'"{inner}"') == inner


@_PROPERTIES
@given(raw=_SAFE_TEXT)
def test_unquoted_text_is_never_altered(raw: str) -> None:
    # _SAFE_ALPHABET carries neither quote character, so `raw` (whatever
    # its length) never opens with one -- the "matching pair" branch can
    # never fire, and _unquote must return it byte-for-byte.
    assert ccs._unquote(raw) == raw


# --- _yaml_unsafe_reasons ----------------------------------------------


@_PROPERTIES
@given(prefix=_SAFE_TEXT, suffix=_SAFE_TEXT)
def test_colon_space_is_always_detected(prefix: str, suffix: str) -> None:
    value = f"{prefix}: {suffix}"
    assert 'contains ": " (colon + space)' in ccs._yaml_unsafe_reasons(value)


@_PROPERTIES
@given(prefix=_SAFE_TEXT)
def test_trailing_colon_is_always_detected(prefix: str) -> None:
    value = f"{prefix}:"
    assert 'ends with a trailing ":"' in ccs._yaml_unsafe_reasons(value)


@_PROPERTIES
@given(suffix=_SAFE_TEXT)
def test_leading_hash_is_always_detected(suffix: str) -> None:
    value = f"#{suffix}"
    assert 'starts with "#"' in ccs._yaml_unsafe_reasons(value)


@_PROPERTIES
@given(prefix=_SAFE_TEXT, suffix=_SAFE_TEXT)
def test_space_hash_is_always_detected(prefix: str, suffix: str) -> None:
    value = f"{prefix} #{suffix}"
    assert 'contains " #" (space + hash)' in ccs._yaml_unsafe_reasons(value)


@_PROPERTIES
@given(value=_SAFE_TEXT)
def test_value_with_no_colon_or_hash_has_no_reasons(value: str) -> None:
    # _SAFE_ALPHABET carries neither ":" nor "#", so none of the four
    # patterns can ever occur regardless of arrangement.
    assert ccs._yaml_unsafe_reasons(value) == []


# --- _parse_frontmatter_fields -------------------------------------------


@_PROPERTIES
@given(text=_SAFE_TEXT)
def test_text_not_opening_frontmatter_yields_no_fields_and_is_never_malformed(text: str) -> None:
    # Leading "X" guarantees the text never opens with "---" itself.
    fields, malformed = ccs._parse_frontmatter_fields("X" + text)
    assert fields is None
    assert malformed is False


@_PROPERTIES
@given(value=_TRIMMED_BLOCK_TEXT)
def test_well_formed_block_parses_its_plain_description_value(value: str) -> None:
    content = f"---\ndescription: {value}\n---\nbody text\n"
    fields, malformed = ccs._parse_frontmatter_fields(content)
    assert malformed is False
    assert fields is not None
    assert fields["description"].style == "plain"
    assert fields["description"].value == value


@_PROPERTIES
@given(value=_TRIMMED_BLOCK_TEXT)
def test_unterminated_block_is_malformed_with_no_fields(value: str) -> None:
    content = f"---\ndescription: {value}\n"  # never closed
    fields, malformed = ccs._parse_frontmatter_fields(content)
    assert malformed is True
    assert fields is None


# --- _quote_is_genuinely_closed --------------------------------------------


@_PROPERTIES
@given(inner=_SAFE_TEXT)
def test_plain_double_quoted_scalar_is_genuinely_closed(inner: str) -> None:
    assert ccs._quote_is_genuinely_closed(f'"{inner}"') is True


@_PROPERTIES
@given(inner=_SAFE_TEXT)
def test_plain_single_quoted_scalar_is_genuinely_closed(inner: str) -> None:
    assert ccs._quote_is_genuinely_closed(f"'{inner}'") is True


@_PROPERTIES
@given(inner=_SAFE_TEXT, pairs=st.integers(min_value=0, max_value=5))
def test_double_quote_closure_tracks_backslash_parity(inner: str, pairs: int) -> None:
    # `pairs` complete `\\` (escaped-literal-backslash) pairs before the
    # presumed closing quote leave an EVEN run of backslashes -- that
    # quote is unescaped, genuinely closed. One further single backslash
    # makes the run ODD -- the presumed closing quote is itself escaped,
    # genuinely unclosed (issue #1987's own Step 8 defeat-test shape).
    closed = f'"{inner}' + "\\\\" * pairs + '"'
    assert ccs._quote_is_genuinely_closed(closed) is True
    unclosed = f'"{inner}' + "\\\\" * pairs + '\\"'
    assert ccs._quote_is_genuinely_closed(unclosed) is False


@_PROPERTIES
@given(inner=_SAFE_TEXT, escaped_pairs=st.integers(min_value=0, max_value=5))
def test_single_quote_closure_tracks_total_quote_parity(inner: str, escaped_pairs: int) -> None:
    # `escaped_pairs` complete `''` (escaped-literal-quote) pairs before
    # the real closing quote keep the total quote count EVEN -- genuinely
    # closed. One further trailing `'` makes the total ODD -- the last
    # quote is the un-paired half of an escape, genuinely unclosed.
    closed = f"'{inner}" + "''" * escaped_pairs + "'"
    assert ccs._quote_is_genuinely_closed(closed) is True
    unclosed = f"'{inner}" + "''" * escaped_pairs + "''"
    assert ccs._quote_is_genuinely_closed(unclosed) is False


@_PROPERTIES
@given(text=_SAFE_TEXT)
def test_non_quote_opening_is_never_genuinely_closed(text: str) -> None:
    # _SAFE_ALPHABET carries neither quote character, so this can never
    # open with one -- the function's own first guard must reject it
    # regardless of content.
    assert ccs._quote_is_genuinely_closed(text) is False


# --- _description_checks -------------------------------------------------


@_PROPERTIES
@given(text=st.text(alphabet=_SAFE_ALPHABET, min_size=0, max_size=800))
def test_description_length_check_tracks_the_cap_exactly(text: str) -> None:
    fields = {"description": ccs._Field(style="plain", value=text)}
    results = ccs._description_checks(fields)
    length_result = next(r for r in results if r.name == "description-length")
    assert length_result.passed == (len(text) <= ccs.DESCRIPTION_MAX_CHARS)


@_PROPERTIES
@given(text=st.text(alphabet=_SAFE_ALPHABET, max_size=200))
def test_quoted_or_block_style_description_always_passes_yaml_safety(text: str) -> None:
    for style in ("quoted", "block"):
        fields = {"description": ccs._Field(style=style, value=text)}
        results = ccs._description_checks(fields)
        safety_result = next(r for r in results if r.name == "yaml-plain-scalar-safety")
        assert safety_result.passed


# --- _declared_boundary ---------------------------------------------------


@_PROPERTIES
@given(tokens=st.lists(_TOKEN, min_size=0, max_size=5))
def test_disallowed_tools_field_declares_deny_mode_with_exact_tokens(tokens: list[str]) -> None:
    fields = {"disallowedTools": ccs._Field(style="plain", value=" ".join(tokens))}
    boundary = ccs._declared_boundary(fields)
    assert boundary is not None
    assert boundary.mode == "deny"
    assert boundary.tokens == tuple(tokens)


@_PROPERTIES
@given(tokens=st.lists(_TOKEN, min_size=0, max_size=5))
def test_tools_field_declares_allow_mode_with_exact_tokens(tokens: list[str]) -> None:
    fields = {"tools": ccs._Field(style="plain", value=" ".join(tokens))}
    boundary = ccs._declared_boundary(fields)
    assert boundary is not None
    assert boundary.mode == "allow"
    assert boundary.tokens == tuple(tokens)


def test_no_fields_declares_no_boundary() -> None:
    assert ccs._declared_boundary(None) is None


# --- _opencode_key_for_token ----------------------------------------------


@_PROPERTIES
@given(server=_TOKEN, tool=st.one_of(st.none(), _TOKEN))
def test_mcp_prefixed_token_always_maps_to_the_wildcard_key(server: str, tool: str | None) -> None:
    token = f"mcp__{server}" if tool is None else f"mcp__{server}__{tool}"
    assert ccs._opencode_key_for_token(token) == "*mcp*"


@_PROPERTIES
@given(
    token=st.sampled_from(sorted(ccs._CLAUDE_TOOL_TO_OPENCODE_KEY)),
    casing=st.sampled_from(["lower", "upper", "title"]),
)
def test_known_table_tokens_map_case_insensitively(token: str, casing: str) -> None:
    spelled = {"lower": token.lower(), "upper": token.upper(), "title": token.title()}[casing]
    assert ccs._opencode_key_for_token(spelled) == ccs._CLAUDE_TOOL_TO_OPENCODE_KEY[token]


# --- check_shape -----------------------------------------------------------


@_PROPERTIES
@given(text=st.text(alphabet=_SAFE_ALPHABET, max_size=200))
def test_text_with_no_frontmatter_passes_every_frontmatter_derived_check(text: str) -> None:
    # tempfile.TemporaryDirectory(), not the pytest `tmp_path` fixture: a
    # function-scoped fixture is not reset between examples the same
    # @given-decorated test generates, which Hypothesis's own health check
    # refuses to run under (a fresh directory per example is required here
    # regardless, since each example writes a different file).
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "AGENTS.md"
        target.write_text("X" + text, encoding="utf-8")  # never opens "---"
        results = ccs.check_shape(target, agent_specs=None)
    by_name = {r.name: r for r in results}
    assert by_name["frontmatter-parsable"].passed
    assert by_name["tool-boundary-declared"].passed
    assert by_name["description-length"].passed
    assert by_name["yaml-plain-scalar-safety"].passed


# --- _validate_read_scope ---------------------------------------------------


@_PROPERTIES
@given(sub=_PATH_COMPONENT, filename=_PATH_COMPONENT)
def test_target_inside_allowed_root_never_raises(sub: str, filename: str) -> None:
    # tempfile.TemporaryDirectory(), not `tmp_path` -- see the identical
    # rationale on test_text_with_no_frontmatter_passes_every_
    # frontmatter_derived_check above.
    with tempfile.TemporaryDirectory() as tmp:
        allowed_root = Path(tmp) / "root"
        allowed_root.mkdir()
        target_dir = allowed_root / sub
        target_dir.mkdir()
        target = target_dir / f"{filename}.md"
        target.write_text("x", encoding="utf-8")
        ccs._validate_read_scope(target, allowed_root)  # must not raise


@_PROPERTIES
@given(other=_PATH_COMPONENT)
def test_target_outside_allowed_root_always_raises(other: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        allowed_root = Path(tmp) / "root"
        allowed_root.mkdir()
        sibling_dir = Path(tmp) / "sibling"
        sibling_dir.mkdir()
        target = sibling_dir / f"{other}.md"
        target.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="resolves outside"):
            ccs._validate_read_scope(target, allowed_root)

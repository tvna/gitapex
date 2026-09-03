"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_unguarded_shell_pipe_in_docs.py`` (issue
#1531's own gate), added because issue #1178's
``detection-logic-property-coverage`` gate requires one for the regex-based
detection logic that gate introduces.

Four properties, one per trigger-bearing helper function -- the example
suite next door (``tests/test_gitapex_gate_unguarded_shell_pipe_in_docs.py``,
36 tests) enumerates specific input shapes by hand; these properties instead
generate the shape space each helper's own regex is meant to accept or
reject, so a boundary condition no hand-written example happens to hit still
gets exercised.

Which properties are model-based
---------------------------------
* :func:`test_fenced_line_ranges_pairs_fences_by_commonmark_run_length` --
  **model-based**. Adapted from the identical generative model
  ``tests/test_gitapex_gate_no_raw_gh_cli_in_docs_properties.py`` already
  validated for the sibling gate's own ``_fenced_line_ranges`` (byte-for-byte
  the same function, copied rather than imported -- see this gate's own
  module docstring for why one copy per gate is this repository's existing
  convention). The generator holds the intended block structure
  independently of the function under test, so a fence-pairing regression
  (closing a longer fence on a shorter nested marker of the same character)
  fails against it.
* :func:`test_pipe_match_requires_a_recognized_consumer_token_after_a_single_pipe`
  -- **model-based**. The generator draws separately from
  ``gate._PIPE_CONSUMERS`` (must match) and a disjoint pool of non-consumer
  words (must not match), so a boundary defect in either direction fails.
  Confirmed live against an injected defect: dropping the trailing ``\\b``
  makes a non-consumer word that merely *starts* with a consumer token
  (``pythonic``) match, and this property catches it.
* :func:`test_has_pipefail_disclosure_is_a_case_insensitive_substring_search`
  -- **model-based**. The generator plants (or withholds) ``pipefail`` in a
  randomly-cased spelling at a random position in otherwise random text, so
  the oracle (whether it planted the substring) is independent of the
  regex under test.
* :func:`test_has_allow_marker_accepts_only_a_valid_marker_directly_above` --
  **model-based**, adapted from the sibling gate's own identical property
  (same marker grammar, different token name). The generator knows which
  line is a well-formed marker and where it placed it, so both an
  over-permissive regex and an off-by-one in the inspected line fail.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, applied per property rather than as a global Hypothesis
profile -- the same rationale
``tests/test_gitapex_gate_no_raw_gh_cli_in_docs_properties.py``'s own module
docstring gives (this repository runs pytest under ``-n auto``, where a
randomly-seeded generator turns a latent failure into an intermittently red
suite, and a wall-clock deadline measures CI scheduling noise rather than
the code under test).
"""

from __future__ import annotations

from typing import NamedTuple

import gitapex_gate_unguarded_shell_pipe_in_docs as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)


# ==========================================================================
# `_fenced_line_ranges` -- model-based, adapted from the sibling gate's own
# already-validated generative model.
# ==========================================================================

_PROSE = (
    "",
    "Ordinary prose line.",
    "## A heading",
    "- a list item",
    "text mentioning ``` inline, not at line start",
    "  indented prose",
    "~~ two tildes only",
    "`` two backticks only",
)

_INFO_STRINGS = ("", "bash", "markdown", "text", "json", "console")
_INDENTS = ("", " ", "   ")
_CLOSE_TRAILING = ("", " ", "\t", "  ")


class _FenceBlock(NamedTuple):
    char: str
    open_len: int
    close_extra: int
    info: str
    indent: str
    close_trailing: str
    decoys: tuple[int, ...]


def _to_fence_block(raw: tuple[bool, int, int, int, int, int, list[int]]) -> _FenceBlock:
    backtick, open_len, close_extra, info_index, indent_index, trailing_index, decoys = raw
    return _FenceBlock(
        char="`" if backtick else "~",
        open_len=open_len,
        close_extra=close_extra,
        info=_INFO_STRINGS[info_index % len(_INFO_STRINGS)],
        indent=_INDENTS[indent_index % len(_INDENTS)],
        close_trailing=_CLOSE_TRAILING[trailing_index % len(_CLOSE_TRAILING)],
        decoys=tuple(decoys),
    )


def _decoy_pool(char: str, open_len: int) -> tuple[str, ...]:
    other = "~" if char == "`" else "`"
    pool = [
        "content line inside the block",
        f"echo {char * 2}",
        other * 3,
        other * (open_len + 2),
        f"{char * open_len} not a bare run",
        f"{char * (open_len + 3)}info-string",
        f"  {other * open_len}  ",
        "",
    ]
    pool.extend(char * shorter for shorter in range(3, open_len))
    return tuple(pool)


def _render_fence_document(
    sections: list[tuple[list[int], _FenceBlock]], tail: list[int], unclosed: bool
) -> tuple[list[str], list[tuple[int, int]]]:
    lines: list[str] = []
    expected: list[tuple[int, int]] = []
    for index, (prose_choices, block) in enumerate(sections):
        lines.extend(_PROSE[choice % len(_PROSE)] for choice in prose_choices)
        open_line = len(lines) + 1
        lines.append(f"{block.indent}{block.char * block.open_len}{block.info}")
        pool = _decoy_pool(block.char, block.open_len)
        lines.extend(pool[choice % len(pool)] for choice in block.decoys)
        if unclosed and index == len(sections) - 1:
            expected.append((open_line, 0))
        else:
            close_len = block.open_len + block.close_extra
            lines.append(f"{block.indent}{block.char * close_len}{block.close_trailing}")
            expected.append((open_line, len(lines)))
    lines.extend(_PROSE[choice % len(_PROSE)] for choice in tail)
    if expected and expected[-1][1] == 0:
        expected[-1] = (expected[-1][0], len(lines) + 1)
    return lines, expected


_FENCE_BLOCKS = st.tuples(
    st.booleans(),
    st.integers(min_value=3, max_value=9),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.lists(st.integers(min_value=0, max_value=99), max_size=5),
).map(_to_fence_block)

_FENCE_SECTIONS = st.tuples(st.lists(st.integers(min_value=0, max_value=99), max_size=3), _FENCE_BLOCKS)

_NESTING_BLOCKS = st.tuples(
    st.just(True),
    st.integers(min_value=4, max_value=7),
    st.integers(min_value=0, max_value=3),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.lists(st.integers(min_value=0, max_value=99), max_size=3),
).map(_to_fence_block)


def _with_forced_nesting(block: _FenceBlock) -> _FenceBlock:
    pool = _decoy_pool(block.char, block.open_len)
    shorter = (pool.index(block.char * 3), pool.index(block.char * (block.open_len - 1)))
    return block._replace(decoys=shorter + block.decoys)


def _bare_run_length(stripped: str, char: str) -> int:
    return len(stripped) if stripped and set(stripped) == {char} else 0


@_PROPERTIES
@given(
    sections=st.lists(_FENCE_SECTIONS, max_size=3),
    nesting=st.tuples(st.lists(st.integers(min_value=0, max_value=99), max_size=3), _NESTING_BLOCKS),
    position=st.integers(min_value=0, max_value=99),
    tail=st.lists(st.integers(min_value=0, max_value=99), max_size=3),
    unclosed=st.booleans(),
)
def test_fenced_line_ranges_pairs_fences_by_commonmark_run_length(
    sections: list[tuple[list[int], _FenceBlock]],
    nesting: tuple[list[int], _FenceBlock],
    position: int,
    tail: list[int],
    unclosed: bool,
) -> None:
    """Fence pairing follows CommonMark's run-length rule for every generated
    nesting/sibling structure: a fence closes only on a bare run of the same
    marker character at least as long as the one that opened it.

    Every generated example forces at least one block opened with four to
    seven backticks whose body carries a bare three-backtick line -- the
    shape a naive `startswith` toggle would mistake for a close. Flip-tested
    against that exact defect: reverting `_fenced_line_ranges` to a naive
    `stripped.startswith(char * 3)` toggle fails this property; the current
    run-length-aware implementation passes.
    """
    prose_choices, block = nesting
    ordered = list(sections)
    ordered.insert(position % (len(ordered) + 1), (prose_choices, _with_forced_nesting(block)))
    lines, expected = _render_fence_document(ordered, tail, unclosed)

    ranges = gate._fenced_line_ranges(lines)

    assert ranges == expected

    previous_close = 0
    for open_line, close_line in ranges:
        assert open_line > previous_close
        assert close_line >= open_line
        previous_close = close_line
        opened = lines[open_line - 1].strip()
        marker = opened[0]
        open_run = len(opened) - len(opened.lstrip(marker))
        if close_line == len(lines) + 1:
            continue
        closed = lines[close_line - 1].strip()
        assert _bare_run_length(closed, marker) >= open_run


# ==========================================================================
# `_pipe_match` -- model-based.
# ==========================================================================

_CONSUMERS = tuple(sorted(gate._PIPE_CONSUMERS))

# Words that must never match: each is either not in `_PIPE_CONSUMERS` at
# all, or a near-miss on the trailing `\b` (a consumer token as a strict
# prefix of a longer word).
_NON_CONSUMERS = (
    "None",
    "int",
    "str",
    "cat",
    "curl",
    "echo",
    "pythonic",
    "basher",
    "unix",
    "notaconsumer",
)

_LEFT_TOKENS = ("cmd", "git", "$(cmd)", "1", "value", "a-b_c.d")
_SEPARATORS = (" ", "  ", "\t", "")
_SUFFIXES = ("", " arg", " --flag value", " x.py")


@_PROPERTIES
@given(
    left=st.sampled_from(_LEFT_TOKENS),
    left_sep=st.sampled_from(_SEPARATORS),
    right_sep=st.sampled_from(_SEPARATORS),
    consumer=st.sampled_from(_CONSUMERS),
    suffix=st.sampled_from(_SUFFIXES),
)
def test_pipe_match_requires_a_recognized_consumer_token_after_a_single_pipe(
    left: str, left_sep: str, right_sep: str, consumer: str, suffix: str
) -> None:
    """Every generated `<left> | <consumer><suffix>` line matches, for every
    consumer token the gate's own vocabulary declares and every whitespace
    variant around the pipe.

    **Model-based**: `consumer` is drawn directly from `gate._PIPE_CONSUMERS`
    (the gate's own vocabulary), so this does not detect a *stale*
    vocabulary (a real shell tool missing from it) -- the same disclosed
    residual risk the sibling gate's own subcommand-vocabulary property
    carries. It does detect a regex regression that stops matching a
    registered token, or that stops matching one of the generated whitespace
    variants.
    """
    line = f"{left}{left_sep}|{right_sep}{consumer}{suffix}"
    match = gate._pipe_match(line)
    assert match is not None
    assert match.group(0).endswith(consumer) or consumer in match.group(0)


@_PROPERTIES
@given(
    left=st.sampled_from(_LEFT_TOKENS),
    left_sep=st.sampled_from(_SEPARATORS),
    right_sep=st.sampled_from(_SEPARATORS),
    non_consumer=st.sampled_from(_NON_CONSUMERS),
    suffix=st.sampled_from(_SUFFIXES),
)
def test_pipe_match_rejects_a_non_consumer_token_after_a_single_pipe(
    left: str, left_sep: str, right_sep: str, non_consumer: str, suffix: str
) -> None:
    """The mirror property: a `<left> | <non_consumer><suffix>` line -- a
    Python type hint (`list[str] | None`), a table cell, or a near-miss on
    the trailing word boundary (`pythonic`, `basher`) -- never matches.

    Confirmed live: dropping the trailing `\\b` from `_PIPE_RE` makes
    `pythonic`/`basher` (both a registered consumer as a strict prefix)
    match, and this property catches it.
    """
    line = f"{left}{left_sep}|{right_sep}{non_consumer}{suffix}"
    assert gate._pipe_match(line) is None


@_PROPERTIES
@given(left=st.sampled_from(_LEFT_TOKENS), consumer=st.sampled_from(_CONSUMERS))
def test_pipe_match_rejects_a_double_pipe(left: str, consumer: str) -> None:
    """`||` (logical OR) never matches, regardless of what follows it --
    this gate's own risk class is specific to a single unguarded pipe."""
    assert gate._pipe_match(f"{left} || {consumer}") is None


# ==========================================================================
# `_has_pipefail_disclosure` -- model-based.
# ==========================================================================

_PIPEFAIL_SPELLINGS = ("pipefail", "PIPEFAIL", "PipeFail", "pIpEfAil")
_FILLER = ("", "some prose ", "set -o ", "line one\nline two\n")


@_PROPERTIES
@given(
    before=st.sampled_from(_FILLER),
    spelling=st.sampled_from(_PIPEFAIL_SPELLINGS),
    after=st.sampled_from(_FILLER),
)
def test_has_pipefail_disclosure_finds_a_planted_case_insensitive_occurrence(
    before: str, spelling: str, after: str
) -> None:
    """`pipefail`, in any letter-casing, planted anywhere in the text, is
    always found."""
    assert gate._has_pipefail_disclosure(f"{before}{spelling}{after}") is True


@_PROPERTIES
@given(text=st.sampled_from((*_FILLER, "no risky word here", "PIPE FAIL (split, not planted)")))
def test_has_pipefail_disclosure_is_false_with_no_planted_occurrence(text: str) -> None:
    """The mirror property: text with no `pipefail` substring planted (the
    filler pool itself, plus a split near-miss) is never reported as
    disclosed."""
    assert gate._has_pipefail_disclosure(text) is False


# ==========================================================================
# `_has_allow_marker` -- model-based, adapted from the sibling gate's own
# identical property (same marker grammar, different token name).
# ==========================================================================

_REASONS = ("historical", "illustrative prose, not an instruction to run", "x", "a --> b", "issue #1531")

_VALID_MARKER_SPACINGS = (
    ("", " ", "", " ", ""),
    ("  ", "", " ", "", ""),
    ("\t", " ", " ", " ", "  "),
    ("", "", "", "", ""),
    ("   ", "\t", "\t", "\t", "\t"),
)

_INVALID_MARKERS = (
    "<!-- gitapex-allow-unguarded-shell-pipe: -->",
    "<!-- gitapex-allow-unguarded-shell-pipe:    -->",
    "<!-- gitapex-allow-unguarded-shell-pipe reason -->",
    "<!-- gitapex-allow-shell-pipe: reason -->",
    "<!-- gitapex-allow-unguarded-shell-pipe: reason",
    "x <!-- gitapex-allow-unguarded-shell-pipe: reason -->",
    "<!-- gitapex-allow-unguarded-shell-pipe: reason --> tail",
    "<!--gitapex-allow-unguarded-shell-pipe-->",
    "<!-- GITAPEX-ALLOW-UNGUARDED-SHELL-PIPE: reason -->",
)

_MARKER_PROSE = ("", "Ordinary prose above a fence.", "```bash", "<!-- an unrelated HTML comment -->")


def _valid_marker_line(reason: str, spacing: tuple[str, str, str, str, str]) -> str:
    indent, after_open, before_colon, after_colon, trailing = spacing
    return (
        f"{indent}<!--{after_open}gitapex-allow-unguarded-shell-pipe{before_colon}:{after_colon}{reason} -->{trailing}"
    )


_MARKER_LINES = st.one_of(
    st.builds(_valid_marker_line, st.sampled_from(_REASONS), st.sampled_from(_VALID_MARKER_SPACINGS)).map(
        lambda text: (True, text)
    ),
    st.sampled_from(_INVALID_MARKERS).map(lambda text: (False, text)),
    st.sampled_from(_MARKER_PROSE).map(lambda text: (False, text)),
)


@_PROPERTIES
@given(candidates=st.lists(_MARKER_LINES, min_size=1, max_size=6), open_choice=st.integers(min_value=0, max_value=99))
def test_has_allow_marker_accepts_only_a_valid_marker_directly_above(
    candidates: list[tuple[bool, str]], open_choice: int
) -> None:
    """The exemption holds exactly when the line directly above the given
    index is a syntactically valid `gitapex-allow-unguarded-shell-pipe`
    marker -- not one line higher, not the line itself, and not a marker
    missing its reason, its colon, its closing `-->`, or its line
    anchoring.

    **Model-based** on two axes at once: validity (each generated line is
    drawn from a pool that knows whether it is well-formed) and position
    (the inspected index is drawn independently of where the valid marker
    landed).
    """
    lines = [text for _, text in candidates]
    index = 1 + open_choice % len(lines)
    expected = index >= 2 and candidates[index - 2][0]

    assert gate._has_allow_marker(lines, index) is expected

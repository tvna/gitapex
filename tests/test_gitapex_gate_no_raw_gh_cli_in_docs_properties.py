"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_no_raw_gh_cli_in_docs.py`` (issue #529's own
gate), added because issue #1178's ``detection-logic-property-coverage`` gate
requires one for the regex-, path-resolution- and string-comparison-based
detection logic that gate's own hardening pass introduced.

What this layer is for
----------------------
The example-based suite next door
(``tests/test_gitapex_gate_no_raw_gh_cli_in_docs.py``, 32 tests) enumerates
input shapes by hand: one nested fence, one quoted invocation, one stale-
vocabulary subcommand, one blank-line-separated marker. Every one of those
was written *after* an adversarial review pointed at the exact shape. The
fence-pairing defect that review found -- a naive ``startswith("```")``
toggle closing a four-backtick fence on the first three-backtick line nested
inside it, so an entire nested block went unscanned -- is precisely the class
a hand-enumerated suite cannot be trusted to cover: it lives in the *shape*
of the input (run lengths, marker characters, nesting depth), not in any one
literal example. Generating that shape space is what this module adds.

Which properties are model-based, and which are not
---------------------------------------------------
Stated per property in its own docstring, and summarised here so a reader
does not have to infer it:

* :func:`test_fenced_line_ranges_pair_fences_by_commonmark_run_length` --
  **model-based**, and the one that covers the motivating defect. The
  generator builds a document from an intended block structure it holds
  independently, so the function's own output cannot define correctness. It
  is the only property here that would fail against the pre-``f19314d``
  fence toggle.
* :func:`test_discover_returns_exactly_the_tracked_docs_markdown_files` --
  **model-based** for the discovery set: the expected set is recomputed by a
  genuinely different mechanism (``pathlib.PurePosixPath`` ``parts``/
  ``suffix``) than the one under test (``str.endswith`` over ``git
  ls-files`` output).
* :func:`test_has_allow_marker_accepts_only_a_valid_marker_directly_above` --
  **model-based**: the generator knows which generated line is a
  syntactically valid marker and which line the fence opens on, so both an
  over-permissive marker regex and an off-by-one in the line it inspects
  fail against the model.
* :func:`test_violations_in_text_finds_exactly_the_generated_invocations` --
  **model-based for the matching half only.** The generator holds which
  lines are real invocations and which are near-misses, so a missed
  command-start position or a false positive on word-internal text fails.
  It **does not** detect a stale ``_GH_SUBCOMMANDS`` vocabulary: the
  generator draws its subcommands from that same frozenset, so a real gh
  CLI command absent from it is invisible to this property exactly as it is
  to the gate. That residual risk is the gate's own disclosed one, not
  closed here.
* :func:`test_violations_in_file_reports_the_path_relative_to_the_root` --
  **model-based for the path half**: the generator holds the intended
  repository-relative path, including nested directories and a dotted
  directory name, so a regression that reported a basename (or an absolute
  path) instead fails. Its findings half re-uses the same document model as
  the property above rather than adding a new defect class.

None of them exercises ``find_violations``/``violations_in``/``main``: those
are thin compositions with no detection logic of their own, and the example
suite already pins each end to end.

Measured, not asserted: what these properties actually kill
-----------------------------------------------------------
Every "detects X" claim below was checked by running the property against a
scratch copy of the gate with X's defect injected, rather than by reasoning
about it. Nineteen single-edit mutations were run; fifteen are killed (the
property fails), and the four survivors are recorded here rather than left
for a later reader to find, because each is a mutation that turns out to be
*semantically equivalent* on this gate rather than a hole in a property:

* ``_ALLOW_MARKER_RE.match(...)`` -> ``.search(...)``: survives, and should.
  The pattern is ``^``-anchored and compiled without ``re.MULTILINE``, so
  the two spellings cannot differ on a single line. The line-start
  requirement is really carried by that ``^``, which
  :func:`test_has_allow_marker_accepts_only_a_valid_marker_directly_above`
  does kill when it is removed.
* ``sorted(_GH_SUBCOMMANDS)`` -> ``sorted(_GH_SUBCOMMANDS, key=len)``:
  survives. The trailing ``\\b`` makes the alternation order irrelevant for
  the overlapping entries (``skill``/``skills``, ``cs``/``codespace``) --
  the engine backtracks past a shadowing prefix. Removing that ``\\b`` *is*
  killed, so the invariant is covered; the ordering itself simply is not an
  independent defect class here.
* ``range(open_line + 1, close_line)`` -> ``range(open_line, close_line +
  1)`` (scan the fence's own marker lines too): survives, because a fence
  marker line cannot carry a ``gh <subcommand>`` invocation anywhere in the
  generated space. A disclosed limit of the generator, not a claim withdrawn
  -- the neighbouring case that *does* matter (an invocation on the prose
  line directly outside a fence) is generated and is caught.
* ``sorted(root / name ...)`` -> ``list(root / name ...)`` in ``discover``:
  survives, because ``git ls-files`` already emits sorted output. The order
  assertion in that property is therefore a guard against a future change,
  not a demonstrated catch.

Reproducibility
---------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property as a local ``settings`` object rather than registered as
a global Hypothesis profile.
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own module
docstring carries the full rationale (this repository runs pytest under
``-n auto``, where a randomly-seeded generator turns a latent failure into an
intermittently red suite that reruns green, and a wall-clock deadline
measures CI scheduling noise rather than the code under test; and
``register_profile``/``load_profile`` would mutate process-global state that
follows into every other test module). It is not repeated here beyond this
pointer, including its disclosed trade: a derandomized run explores a fixed
example set that is a function of the resolved Hypothesis version.

The two filesystem-backed properties use a **module-scoped** fixture, not
``tmp_path``. That is what resolves Hypothesis' ``function_scoped_fixture``
health check honestly, rather than suppressing it -- no health check is
suppressed in this module at all. The fixture hands back one base directory;
each generated example then creates its *own* fresh subdirectory inside it
and never reads or writes another example's, so sharing the base cannot leak
state between examples. Their ``max_examples`` is lowered to 150 (from the
200 the pure-function properties use) because each example runs a real ``git
init``/``git add`` pair or writes a real file.
"""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
from typing import NamedTuple

import gitapex_gate_no_raw_gh_cli_in_docs as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Lowered from 200 for the two properties that build a real git repository or
# write a real file per example, for the reason the module docstring gives.
_FILESYSTEM_PROPERTIES = settings(derandomize=True, max_examples=150, deadline=None)


@pytest.fixture(scope="module")
def scratch_root(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """One base directory for the whole module.

    Module-scoped on purpose -- see this module's docstring for why that, and
    not a ``suppress_health_check``, is the resolution for Hypothesis'
    ``function_scoped_fixture`` health check. Every example below creates its
    own fresh subdirectory under this base and touches nothing outside it, so
    reusing the base across examples cannot carry state from one into the
    next.
    """
    return tmp_path_factory.mktemp("no_raw_gh_cli_properties")


# ==========================================================================
# `_fenced_line_ranges` -- model-based. Covers the motivating defect.
# ==========================================================================

# Lines that are never fence markers and never close a block: none of them
# strips to a run of three or more backticks or tildes.
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

# Kept at or below three spaces deliberately. CommonMark caps a fence
# marker's own indentation at three spaces; this gate's docstring discloses
# that it does not model that cap (a flat line scanner cannot see the
# container indentation a fence inside a list item legitimately carries), so
# generating a four-space indent would assert on the gate's own disclosed
# deviation rather than on its pairing logic, which is what this property is
# about.
_INDENTS = ("", " ", "   ")

# Trailing whitespace on a closing marker, which `.strip()` must absorb.
_CLOSE_TRAILING = ("", " ", "\t", "  ")


class _FenceBlock(NamedTuple):
    """One intended fenced block: the generator's own ground truth."""

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
    """Lines that are legal *inside* a fence of `open_len` `char`s and must
    not close it, under CommonMark's run-length rule.

    Every entry is one of: not a marker run at all; a run of the *other*
    marker character (any length); a run of the same character that is not
    bare (an info string or trailing text follows); or -- the shape the
    pre-`f19314d` `startswith` toggle got wrong -- a *bare* run of the same
    character that is strictly shorter than the opening run.
    """
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
    sections: list[tuple[list[int], _FenceBlock]],
    tail: list[int],
    unclosed: bool,
) -> tuple[list[str], list[tuple[int, int]]]:
    """Render `sections` into document lines plus the `(open, close)` ranges
    a correct implementation must return, both computed from the intended
    structure rather than from the function under test.

    `unclosed` drops only the *final* block's closing marker, so the
    end-of-file fallback is exercised without making the rest of the model
    ambiguous.
    """
    lines: list[str] = []
    expected: list[tuple[int, int]] = []
    for index, (prose_choices, block) in enumerate(sections):
        lines.extend(_PROSE[choice % len(_PROSE)] for choice in prose_choices)
        open_line = len(lines) + 1
        lines.append(f"{block.indent}{block.char * block.open_len}{block.info}")
        pool = _decoy_pool(block.char, block.open_len)
        lines.extend(pool[choice % len(pool)] for choice in block.decoys)
        if unclosed and index == len(sections) - 1:
            # Patched to end-of-file once every remaining line is emitted.
            expected.append((open_line, 0))
        else:
            close_len = block.open_len + block.close_extra
            lines.append(f"{block.indent}{block.char * close_len}{block.close_trailing}")
            expected.append((open_line, len(lines)))
    lines.extend(_PROSE[choice % len(_PROSE)] for choice in tail)
    if expected and expected[-1][1] == 0:
        # Exclusive scan boundary one past the last real line -- see
        # gate._fenced_line_ranges's own docstring for why this must not be
        # `len(lines)` (that off-by-one silently dropped the file's last
        # line from the scan, a real bug this property caught).
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

# The motivating shape, forced into every generated example rather than left
# to chance -- the same "make the defect-triggering shape structural, not
# probable" discipline `tests/test_gitapex_gate_metadata_outcome_lines_
# properties.py` gets from its two-file pool plus `min_size=3`. Backticks,
# not a drawn marker character, because the real defect was a literal
# `startswith("```")`: a tilde-fenced example would not have reproduced it.
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
    """Guarantee this block contains a bare, strictly shorter same-character
    run -- the exact line the pre-`f19314d` toggle mistook for a close."""
    pool = _decoy_pool(block.char, block.open_len)
    shorter = (pool.index(block.char * 3), pool.index(block.char * (block.open_len - 1)))
    return block._replace(decoys=shorter + block.decoys)


def _bare_run_length(stripped: str, char: str) -> int:
    """Length of `stripped` if it is nothing but a run of `char`, else 0.
    Computed with plain string operations, not the module's own regexes, so
    the invariant below is checked independently of what it is checking."""
    return len(stripped) if stripped and set(stripped) == {char} else 0


@_PROPERTIES
@given(
    sections=st.lists(_FENCE_SECTIONS, max_size=3),
    nesting=st.tuples(st.lists(st.integers(min_value=0, max_value=99), max_size=3), _NESTING_BLOCKS),
    position=st.integers(min_value=0, max_value=99),
    tail=st.lists(st.integers(min_value=0, max_value=99), max_size=3),
    unclosed=st.booleans(),
)
def test_fenced_line_ranges_pair_fences_by_commonmark_run_length(
    sections: list[tuple[list[int], _FenceBlock]],
    nesting: tuple[list[int], _FenceBlock],
    position: int,
    tail: list[int],
    unclosed: bool,
) -> None:
    """Fence pairing follows CommonMark's run-length rule for every generated
    nesting/sibling structure: a fence closes only on a bare run of the same
    marker character at least as long as the one that opened it.

    **This is the property that detects the motivating defect class**, and it
    is **model-based**: the generator holds the intended block structure --
    which line opens each block, which lines inside it are decoys that must
    not close it, and which line closes it -- so the function's own output
    cannot define correctness. Every generated example contains at least one
    block opened with four to seven backticks whose body carries a *bare*
    three-backtick line, which is exactly the shape commit ``f19314d``
    fixed: the previous `stripped.startswith("```")` toggle closed the outer
    block there, dropped every following line of it out of every computed
    range, and so never scanned a nested example block at all.

    Flip-tested against that real defect rather than a proxy: run against a
    copy of the gate whose ``_fenced_line_ranges`` is reverted to the naive
    ``startswith`` toggle, this property fails; against the current
    implementation it passes. Both outcomes were observed, not predicted --
    and the failure is structural rather than lucky, since
    :func:`_with_forced_nesting` puts the defect-triggering shape into every
    generated example, the first one included. Two further injected defects
    were also killed: dropping the run-length half of the close test
    (``len(closing) >= len(open_run)``), and unanchoring ``_FENCE_CLOSE_RE``
    so a marker line with an info string closes a block.

    Does **not** detect anything about *what* is scanned inside a range --
    the subcommand vocabulary, the command-start lookbehind and the
    exception marker are covered by the properties below. Deliberately says
    nothing about a fence marker indented four or more spaces: this gate's
    own docstring discloses that it does not model CommonMark's three-space
    indentation cap, so ``_INDENTS`` stays inside that cap rather than
    pinning the disclosed deviation.
    """
    prose_choices, block = nesting
    ordered = list(sections)
    ordered.insert(position % (len(ordered) + 1), (prose_choices, _with_forced_nesting(block)))
    lines, expected = _render_fence_document(ordered, tail, unclosed)

    ranges = gate._fenced_line_ranges(lines)

    assert ranges == expected

    # The same invariant read back off the output, computed without the
    # module's own regexes: a returned range either closes on a bare run of
    # the opening character at least as long as the opening run, or it runs
    # to end-of-file.
    previous_close = 0
    for open_line, close_line in ranges:
        assert open_line > previous_close, (open_line, previous_close)
        assert close_line >= open_line
        previous_close = close_line
        opened = lines[open_line - 1].strip()
        marker = opened[0]
        open_run = len(opened) - len(opened.lstrip(marker))
        if close_line == len(lines) + 1:
            continue  # unclosed fence -- scan boundary is past the last real line, no marker line to inspect
        closed = lines[close_line - 1].strip()
        assert _bare_run_length(closed, marker) >= open_run


# ==========================================================================
# `discover` -- model-based, over a real git repository per example.
# ==========================================================================

# A bare `docs/.md` is deliberately absent: `str.endswith(".md")` counts it
# and `pathlib.PurePosixPath(".md").suffix` (this property's independent
# oracle) does not, so generating it would report a disagreement about
# whether a dotfile named `.md` is a Markdown document -- a question about
# the doc corpus, not about this gate's discovery logic, and not one this
# property is entitled to settle.
#
# `docs/README.MD` is present, and both mechanisms agree it is *not*
# discovered: the gate's extension match is case-sensitive. That is a real
# behavior this property therefore pins, stated here rather than smuggled in
# -- a `.MD`-suffixed doc would not be scanned, which is a live (if unlikely)
# gap on a case-insensitive filesystem, not something this layer fixes.
_CANDIDATE_PATHS = (
    "docs/plan.md",
    "docs/spec.md",
    "docs/nested/deep/notes.md",
    "docs/a.b/c.md",
    "docs/notes.md.txt",
    "docs/readme.txt",
    "docs/diagram.png",
    "docs/md",
    "docs/notes.markdown",
    "docs/notes.mdx",
    "docs/README.MD",
    "README.md",
    "src/notes.md",
    "not-docs/z.md",
    "docsx/y.md",
)


def _expected_discovery(tracked: dict[str, bool]) -> list[str]:
    """The repository-relative paths a correct ``discover`` must return.

    Recomputed by an independent mechanism: ``PurePosixPath.parts``/
    ``.suffix``, not the ``git ls-files -- docs`` pathspec plus
    ``str.endswith(".md")`` pair under test. ``parts[0] == "docs"`` is git's
    own pathspec semantics for a bare directory name, confirmed live rather
    than assumed (``docsx/y.md`` is not matched by ``-- docs``).
    """
    return sorted(
        relative
        for relative, is_tracked in tracked.items()
        if is_tracked
        and pathlib.PurePosixPath(relative).parts[0] == "docs"
        and pathlib.PurePosixPath(relative).suffix == ".md"
    )


@_FILESYSTEM_PROPERTIES
@given(entries=st.lists(st.tuples(st.sampled_from(_CANDIDATE_PATHS), st.booleans()), min_size=1, max_size=8))
def test_discover_returns_exactly_the_tracked_docs_markdown_files(
    entries: list[tuple[str, bool]], scratch_root: pathlib.Path
) -> None:
    """Discovery returns exactly the tracked ``docs/**/*.md`` files -- no
    file outside ``docs/``, no non-Markdown file, no untracked file, and no
    near-miss extension.

    **Model-based**: the expected set is recomputed from the generator's own
    record of what it wrote and tracked, through ``pathlib``'s path parsing
    rather than the ``git ls-files`` pathspec plus ``str.endswith`` pair the
    gate uses -- two genuinely different mechanisms, so agreement is
    evidence rather than a tautology. A widened extension test (``".md" in
    name``, which would take ``docs/notes.md.txt``), a scope that escapes
    ``docs/`` into a sibling directory (``docsx/y.md``, ``not-docs/z.md``,
    a repository-root ``README.md``), and an untracked file all fail against
    the model. Three matching defects were injected into a scratch copy of
    the gate and all three killed -- ``".md" in name``; dropping the
    ``-- docs`` pathspec; adding ``--others`` so untracked files are listed
    too -- rather than merely reasoned about.

    The returned order is asserted too, but as a guard rather than a
    demonstrated catch: ``git ls-files`` already emits sorted output, so
    removing the ``sorted(...)`` call does not fail this property. It is
    asserted anyway because ``violations_in`` reports in the order
    ``discover`` hands paths over, and an unstable order would make the
    gate's own output unstable between runs.

    Does **not** detect anything about the scan applied to a discovered
    file. Covers the `.endswith(".md")` string-comparison call site and the
    `git ls-files` scoping in one property rather than two, because the same
    generated example exercises both.
    """
    tracked = dict(entries)
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for relative in sorted(tracked):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    to_add = sorted(relative for relative, is_tracked in tracked.items() if is_tracked)
    if to_add:
        subprocess.run(["git", "-C", str(root), "add", "-f", "--", *to_add], check=True)

    discovered = gate.discover(root)

    assert [path.relative_to(root).as_posix() for path in discovered] == _expected_discovery(tracked)
    for path in discovered:
        assert path.is_file()


# ==========================================================================
# `_has_allow_marker` -- model-based.
# ==========================================================================

_REASONS = (
    "historical, predates the gate (#529)",
    "illustrative prose, not an instruction to run",
    "x",
    "a --> b",
    "#529 refs #205 Repairs 5 & 8",
)

# (indent, after `<!--`, before `:`, after `:`, trailing) -- every slot the
# marker regex spells `[ \t]*`, including all-empty.
_VALID_MARKER_SPACINGS = (
    ("", " ", "", " ", ""),
    ("  ", "", " ", "", ""),
    ("\t", " ", " ", " ", "  "),
    ("", "", "", "", ""),
    ("   ", "\t", "\t", "\t", "\t"),
)

_INVALID_MARKERS = (
    "<!-- gitapex-allow-raw-gh-cli: -->",  # no reason at all
    "<!-- gitapex-allow-raw-gh-cli:    -->",  # whitespace-only reason
    "<!-- gitapex-allow-raw-gh-cli reason -->",  # no colon
    "<!-- gitapex-allow-gh-cli: reason -->",  # wrong marker token
    "<!-- gitapex-allow-raw-gh-cli: reason",  # never closed
    "x <!-- gitapex-allow-raw-gh-cli: reason -->",  # not at line start
    "<!-- gitapex-allow-raw-gh-cli: reason --> tail",  # trailing content
    "<!--gitapex-allow-raw-gh-cli-->",  # neither colon nor reason
    "<!-- GITAPEX-ALLOW-RAW-GH-CLI: reason -->",  # wrong case
)

_MARKER_PROSE = (
    "",
    "Ordinary prose above a fence.",
    "```bash",
    "See the exception marker documentation.",
    "<!-- an unrelated HTML comment -->",
)


def _valid_marker_line(reason: str, spacing: tuple[str, str, str, str, str]) -> str:
    indent, after_open, before_colon, after_colon, trailing = spacing
    return f"{indent}<!--{after_open}gitapex-allow-raw-gh-cli{before_colon}:{after_colon}{reason} -->{trailing}"


_MARKER_LINES = st.one_of(
    st.builds(_valid_marker_line, st.sampled_from(_REASONS), st.sampled_from(_VALID_MARKER_SPACINGS)).map(
        lambda text: (True, text)
    ),
    st.sampled_from(_INVALID_MARKERS).map(lambda text: (False, text)),
    st.sampled_from(_MARKER_PROSE).map(lambda text: (False, text)),
)


@_PROPERTIES
@given(
    candidates=st.lists(_MARKER_LINES, min_size=1, max_size=6),
    open_choice=st.integers(min_value=0, max_value=99),
)
def test_has_allow_marker_accepts_only_a_valid_marker_directly_above(
    candidates: list[tuple[bool, str]], open_choice: int
) -> None:
    """The exemption holds exactly when the line *directly* above the fence's
    opening marker is a syntactically valid exception marker -- not one line
    higher, not the opening line itself, and not a marker missing its
    reason, its colon, its closing ``-->``, or its line anchoring.

    **Model-based** on two axes at once, both held by the generator
    independently of the regex under test. Validity: each generated line is
    drawn from a pool that knows whether it is a well-formed marker.
    Position: ``open_line`` is drawn independently of where the valid marker
    landed, so an off-by-one fails on the examples where the two disagree --
    which a fixture that always puts the marker directly above the fence
    cannot reach.

    Four injected defects were run against it and all four killed: dropping
    the mandatory-``\\S`` reason (``<!-- gitapex-allow-raw-gh-cli: -->``
    would start exempting blocks); dropping the ``[ \\t]*$`` end anchor
    (``<!-- ... --> tail`` would); inspecting ``lines[open_line - 1]``
    instead of ``lines[open_line - 2]``; and relaxing the ``open_line < 2``
    guard to ``< 1``, which silently reads ``lines[-1]`` -- Python's own
    negative index -- and exempts a fence on line 1 whenever the document's
    *last* line happens to be a marker. Swapping ``.match`` for ``.search``
    is *not* killed, and should not be: the pattern is ``^``-anchored with
    no ``re.MULTILINE``, so the two are equivalent here (see the module
    docstring's own "Measured, not asserted" section).

    Does **not** detect whether the exemption is then applied to the right
    span of lines; that is
    :func:`test_violations_in_text_finds_exactly_the_generated_invocations`'s
    job, which drives the marker through the real caller.
    """
    lines = [text for _, text in candidates]
    open_line = 1 + open_choice % len(lines)
    expected = open_line >= 2 and candidates[open_line - 2][0]

    assert gate._has_allow_marker(lines, open_line) is expected


# ==========================================================================
# `violations_in_text` -- model-based for the matching half.
# ==========================================================================

# Drawn from the module's own vocabulary on purpose, and disclosed as the
# limit that implies: this cannot detect a *stale* `_GH_SUBCOMMANDS` (a real
# gh command absent from it), only an entry the compiled alternation then
# fails to match correctly -- e.g. a missing `re.escape` mangling
# `agent-task`, or a dropped `\b` letting the `skill` alternative shadow a
# real `gh skills` (measured: with the `\b` in place, the alternation's own
# ordering is *not* an independent defect class -- reordering it by length
# changes nothing, because the engine backtracks past a shadowing prefix).
_SUBCOMMANDS = tuple(sorted(gate._GH_SUBCOMMANDS))

# Every one of these puts `gh` in a real command-start position: the
# negative lookbehind must accept all of them. `run_id=$(` and the quoted
# forms are the shapes an enumerated opener character class silently missed
# before commit `f19314d`.
_COMMAND_START_PREFIXES = (
    "",
    "  ",
    "$ ",
    "run_id=$(",
    'bash -lc "',
    "/usr/bin/",
    "cd /tmp && ",
    "echo hi; ",
    "cat x | ",
    "* ",
    '{"tool": "Bash", "command": "',
)

_SEPARATORS = (" ", "  ", "\t")

# Each starts on a non-word character so the pattern's trailing `\b` lands
# on a real boundary, matching how a subcommand is really followed.
_SUFFIXES = (
    "",
    ")",
    '"',
    " view 123",
    " list --limit 1 --json databaseId)",
    ' close 42"}',
    " --help",
)

# Lines that must never be reported. Each is a near-miss on exactly one
# element of the detection: the lookbehind (word-internal or hyphen-
# prefixed `gh`), the subcommand vocabulary, or the trailing `\b`.
_INNOCUOUS_LINES = (
    "Route it through pr review, then rank high pr first.",
    "See weigh issue counts before merging.",
    "for t in uv gh actionlint bun lychee; do echo $t; done",
    "a-gh pr view 123",
    "github pr view 123",
    "gh prometheus dashboards",
    "gh csv export",
    "gh --version",
    "# See the gh manual for details.",
    "echo 'nothing to see here'",
    "$(git rev-parse HEAD)",
    "",
)


def _invocation_line(subcommand: str, separator: str, prefix: str, suffix: str) -> tuple[str, str | None]:
    """One line carrying exactly one real invocation, paired with the exact
    text the gate must report for it (`match.group(1)`, whitespace and
    all)."""
    invocation = f"gh{separator}{subcommand}"
    return f"{prefix}{invocation}{suffix}", invocation


_BODY_LINES = st.one_of(
    st.builds(
        _invocation_line,
        st.sampled_from(_SUBCOMMANDS),
        st.sampled_from(_SEPARATORS),
        st.sampled_from(_COMMAND_START_PREFIXES),
        st.sampled_from(_SUFFIXES),
    ),
    st.sampled_from(_INNOCUOUS_LINES).map(lambda text: (text, None)),
)

_SCAN_FENCES = st.sampled_from(("```", "~~~", "````", "~~~~"))

_SCAN_SECTIONS = st.tuples(
    st.lists(_BODY_LINES, max_size=2),  # lines OUTSIDE any fence
    st.booleans(),  # exempted by an allow marker?
    _SCAN_FENCES,
    st.sampled_from(_INFO_STRINGS),
    st.lists(_BODY_LINES, max_size=4),  # lines INSIDE the fence
)

_ScanSection = tuple[list[tuple[str, str | None]], bool, str, str, list[tuple[str, str | None]]]


def _render_scan_document(
    sections: list[_ScanSection], tail: list[tuple[str, str | None]]
) -> tuple[str, list[tuple[int, str]]]:
    """Render a document plus the `(line, matched)` list a correct
    ``violations_in_text`` must return, both from the generator's own record
    of which lines it made invocations and where it put them."""
    lines: list[str] = []
    expected: list[tuple[int, str]] = []
    for outside, exempt, fence, info, body in sections:
        lines.extend(text for text, _ in outside)
        if exempt:
            lines.append("<!-- gitapex-allow-raw-gh-cli: generated exemption -->")
        lines.append(f"{fence}{info}")
        for text, matched in body:
            lines.append(text)
            if matched is not None and not exempt:
                expected.append((len(lines), matched))
        lines.append(fence)
    lines.extend(text for text, _ in tail)
    return "\n".join(lines), expected


@_PROPERTIES
@given(sections=st.lists(_SCAN_SECTIONS, min_size=1, max_size=3), tail=st.lists(_BODY_LINES, max_size=2))
def test_violations_in_text_finds_exactly_the_generated_invocations(
    sections: list[_ScanSection], tail: list[tuple[str, str | None]]
) -> None:
    """Every invocation the generator placed inside a non-exempt fenced block
    is reported, at the right line and with the right matched text -- and
    nothing else is: not a near-miss, not an invocation outside any fence,
    not one inside a block an exception marker exempts.

    **Model-based for the matching half.** The generator holds which lines
    are real invocations, which are near-misses, and which sit outside a
    fence, so the function's own output cannot define correctness. Four
    injected defects were run against it and all four killed: removing the
    ``(?<![\\w-])`` lookbehind (``through pr``, ``a-gh pr`` and
    ``github pr`` start being reported); removing the trailing ``\\b``
    (``gh prometheus``, ``gh csv`` start being reported, and a drawn
    ``skills`` starts reporting as the shadowing ``skill`` prefix);
    scanning every line rather than only fenced ones; and ignoring the
    exception marker. The lookbehind case is the one that matters most: it
    is what accepts a quoted (``bash -lc "gh pr merge 1"``) or
    path-prefixed (``/usr/bin/gh pr merge 1``) invocation, the bypass class
    commit ``f19314d`` closed, and this generator puts ``gh`` at eleven
    different command-start positions rather than the two the example suite
    enumerates.

    **Does NOT detect a stale ``_GH_SUBCOMMANDS``.** ``_SUBCOMMANDS`` draws
    from the gate's own frozenset, so a real gh CLI command missing from it
    -- the exact residual risk that gate's own docstring discloses, and the
    one the ``gh discussion``/``gh agent-task`` audit finding was an
    instance of -- is as invisible here as it is to the gate. Closing that
    needs an independent vocabulary source (gh's published manual), not a
    generator.

    Also does not detect the two per-line gaps the gate discloses rather
    than claims closed: an indented (non-fenced) code block, and an
    invocation split across a shell line continuation. Both are per-line
    scanning limits, and the generator stays inside them. And it does not
    distinguish scanning a fence's own two marker lines from skipping them
    -- widening the scanned range to ``range(open_line, close_line + 1)``
    survives, because no generated marker line can carry an invocation. The
    adjacent case that does matter, an invocation on the prose line
    immediately outside a fence, is generated and is caught.
    """
    text, expected = _render_scan_document(sections, tail)

    assert gate.violations_in_text(text) == expected


# ==========================================================================
# `violations_in_file` -- model-based for the path half.
# ==========================================================================

_RELATIVE_PATHS = (
    "docs/plan.md",
    "docs/nested/deep/plan.md",
    "docs/a.b/c.md",
    "docs/dir with space/plan.md",
    "notes.md",
    "deep/nested/tree/spec.md",
)


@_FILESYSTEM_PROPERTIES
@given(
    sections=st.lists(_SCAN_SECTIONS, min_size=1, max_size=3),
    tail=st.lists(_BODY_LINES, max_size=2),
    relative=st.sampled_from(_RELATIVE_PATHS),
)
def test_violations_in_file_reports_the_path_relative_to_the_root(
    sections: list[_ScanSection],
    tail: list[tuple[str, str | None]],
    relative: str,
    scratch_root: pathlib.Path,
) -> None:
    """A violation's reported path is the file's full path relative to the
    scan root, at any nesting depth, and its line/matched pair is the one
    the generated document intends.

    **Model-based for the path half**: the generator chose the relative path
    and the root independently of the function, so a regression that
    reported ``path.name`` (dropping ``docs/nested/deep/``), the absolute
    path, or a path relative to the wrong ancestor fails here -- the
    ``path.name`` one was injected into a scratch copy of the gate and
    killed, not merely reasoned about. Depths of one, two and four segments
    are generated, plus a directory whose own name carries a dot (``a.b``)
    and one carrying a space, because a basename-shaped regression is
    invisible at depth one and a suffix-splitting one is invisible without
    the dotted directory. The path assertion is necessarily vacuous on an
    example whose document happens to carry no invocation at all -- a
    violation has to exist before its path can be wrong -- so it is the
    generated examples that *do* carry one that do the work here.

    The findings half re-uses the same document model as
    :func:`test_violations_in_text_finds_exactly_the_generated_invocations`
    and adds no new defect class of its own -- it is here so the
    file-reading and path-resolution layer is exercised against a real file
    on disk rather than only against a string, and so a future change that
    made this function drop or reorder findings is caught at this layer too.
    """
    text, expected = _render_scan_document(sections, tail)
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    violations = gate.violations_in_file(path, root)

    assert [(violation.line, violation.matched) for violation in violations] == expected
    assert [violation.path for violation in violations] == [str(pathlib.PurePath(relative))] * len(expected)

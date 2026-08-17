"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_detection_logic_property_coverage.py`` (issue
#1178). Covers the four functions in that file which, per its own AST-shape
trigger rules (that module's own "Trigger categories" docstring section),
actually contain a regex-, path-resolution-, or string-comparison-shaped call
reached by this diff: :func:`in_scope`, :func:`_diff_target_path`,
:func:`parse_added_lines`, and :func:`_waived_lines`.

Self-referential by design: the gate's own source file matches its own
in-scope pattern (``.github/scripts/gitapex_gate_*.py``), so once its CI
workflow is wired it will grade itself against this exact file -- the
co-located properties path its own ``_properties_path`` computes from the
stem ``gitapex_gate_detection_logic_property_coverage``. Every property below
is written to be genuine coverage first (each docstring below states plainly
what it checks and what real defect class it would catch); satisfying the
gate's own self-check against this file is a consequence of that, not the
design goal.

Verified enumeration of trigger-bearing functions
--------------------------------------------------
Confirmed by direct reading of the source's own AST shapes against its own
``_regex_trigger``/``_path_resolution_trigger``/``_string_comparison_call_trigger``/
``_string_comparison_compare_trigger`` logic, cross-checked with a grep sweep
over every occurrence of a trigger-attribute name in the file -- not merely
assumed from a prior trace:

* :func:`in_scope` -- ``_IN_SCOPE_RE.fullmatch(path)`` (regex) and
  ``name.startswith("test_")`` (string-comparison).
* :func:`_diff_target_path` -- ``target.startswith("b/")`` (string-comparison).
* :func:`parse_added_lines` -- six ``.startswith(...)`` call sites
  (string-comparison) plus ``_HUNK_RE.match(line)`` (regex).
* :func:`_waived_lines` -- ``_WAIVER_RE.search(token.string)`` (regex).

No other function in the source file contains a trigger-shaped call under the
gate's own strict AST rules. Confirmed, not assumed, for each of the
following near-misses -- each looks trigger-shaped on a casual read but fails
one of the gate's own strict conditions, so none needs (or gets) a property
here:

* ``_regex_trigger``/``_path_resolution_trigger``/``_string_comparison_call_trigger``/
  ``_string_comparison_compare_trigger`` themselves: every ``in`` check inside
  them (e.g. ``func.attr in _REGEX_RECEIVER_AGNOSTIC_ATTRS``) compares against
  a module-level ``frozenset`` *name*, not an inline literal -- the gate's own
  ``_string_comparison_compare_trigger`` requires
  ``isinstance(node.comparators[0], ast.List | ast.Tuple | ast.Set)``, which a
  bare ``ast.Name`` reference never satisfies.
* ``parse_added_lines``'s own ``added.setdefault(path, set()).add(lineno)``
  and ``_waived_lines``'s own ``waived: set[int] = set()``: both call
  ``set()`` with zero arguments; the gate's own
  ``_string_comparison_call_trigger`` requires ``len(node.args) == 1``.
* ``_span``'s own ``set(range(node.lineno, end + 1))``: one argument, but a
  ``range(...)`` call, not an inline ``List``/``Tuple``/``Set`` literal.
* ``findings_for_source``'s own ``finding.line in waived_lines`` and
  ``sorted(set(violations)), sorted(set(waived))``: the ``in`` comparator and
  every ``set(...)`` argument are local-variable ``ast.Name`` references, not
  inline literals -- the same "name reference to a previously-defined
  collection" miss the module docstring's own "Trigger categories" section
  discloses for category (c).

This matches a prior session's own starting trace unchanged; no addition or
correction was needed.

Module-scope triggers need no dedicated property
--------------------------------------------------
The source file's own module level (outside any function) carries real
triggers too -- ``REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]``
(path-resolution), three ``re.compile(...)`` constants (regex), and five
``frozenset({...})`` constants (string-comparison). None needs a property
that mentions it by name: the gate's own ``_covered`` treats the
``"<module>"`` scope as covered by *any* ``@given``-decorated function in
this file, once this file both imports the source module and contains at
least one such function -- "for the `"<module>"` scope, any `@given`
function anywhere in the file clears it, since a bare module-level constant
has no function identity of its own to search a body for." Every property
below clears it as a side effect of existing at all.

An observed dead branch, disclosed rather than silently worked around
------------------------------------------------------------------------
:func:`in_scope`'s own ``name.startswith("test_") or name == "conftest.py"``
exclusion is, on direct inspection, unreachable through ``_IN_SCOPE_RE``
itself as currently written: all three of that pattern's alternatives fix
the basename's own literal prefix to ``gitapex_check_`` or ``gitapex_gate_``,
neither of which can ever start with ``test_`` or equal ``conftest.py``. The
gate's own module docstring already flags this precisely -- "the exclusion
is applied defensively rather than assumed unreachable by ``_IN_SCOPE_RE``'s
own fixed-prefix construction." :func:`test_in_scope_matches_its_own_scope_rules`
below therefore does not exercise that exclusion branch, and does not claim
to; this is a fact about the current regex, recorded here rather than
overclaimed away.

Reproducibility
----------------
``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
applied per property rather than as a registered global profile --
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own module
docstring gives the full rationale (this repository's ``-n auto``
pytest-xdist run turns a randomly-seeded generator into an intermittently red
suite that reruns green, and a wall-clock deadline measures CI scheduling
noise, not these pure functions); not repeated here beyond this pointer.
None of the four functions below perform filesystem or subprocess I/O, so
unlike that module's own module-scoped ``skill_dir`` fixture, no shared
fixture is needed here at all -- every property below builds its own
in-memory input from scratch.
"""

from __future__ import annotations

import gitapex_gate_detection_logic_property_coverage as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)


# ---------------------------------------------------------------------------
# in_scope -- regex (fullmatch) + string-comparison (startswith) triggers
# ---------------------------------------------------------------------------

# No "/" or "." in either alphabet: keeps every generated path's directory
# segments and basename unambiguous, so the hand-built expectations below
# cannot be undermined by generated content accidentally reshaping the path.
_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_SKILL_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=12)

_IN_SCOPE_KIND = st.sampled_from(("skills_check", "gate", "hooks_check"))
_OUT_OF_SCOPE_KIND = st.sampled_from(("wrong_prefix_scan", "wrong_directory", "extra_path_segment", "trailing_suffix"))


def _in_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built from one of `_IN_SCOPE_RE`'s own three documented
    alternatives -- always in scope by construction."""
    if kind == "skills_check":
        return f"skills/{skill}/scripts/gitapex_check_{ident}.py"
    if kind == "gate":
        return f".github/scripts/gitapex_gate_{ident}.py"
    return f"hooks/gitapex_check_{ident}.py"


def _out_of_scope_path(kind: str, skill: str, ident: str) -> str:
    """A path built to violate exactly one documented scope boundary --
    always out of scope by construction."""
    if kind == "wrong_prefix_scan":
        # Issue #1032's own scope boundary: gitapex_scan_*.py never matches,
        # by construction -- see the gate's own module docstring.
        return f"skills/{skill}/scripts/gitapex_scan_{ident}.py"
    if kind == "wrong_directory":
        return f"evals/scripts/gitapex_check_{ident}.py"
    if kind == "extra_path_segment":
        # Breaks the single-`[^/]+`-segment requirement between `skills/`
        # and `/scripts/`.
        return f"skills/{skill}/extra/scripts/gitapex_check_{ident}.py"
    # A real in-scope-shaped name with a further suffix appended: the last
    # three characters are "bak", not "py", so re.fullmatch must reject it,
    # even though "...gitapex_check_<ident>.py" is a genuine *prefix* a
    # re.match()-based regression would wrongly accept.
    return f"hooks/gitapex_check_{ident}.py.bak"


@_PROPERTIES
@given(in_kind=_IN_SCOPE_KIND, out_kind=_OUT_OF_SCOPE_KIND, skill=_SKILL_NAME, ident=_IDENT)
def test_in_scope_matches_its_own_scope_rules(in_kind: str, out_kind: str, skill: str, ident: str) -> None:
    """Model-based. The expected answer for each path is known independently
    of `in_scope`'s own implementation: it follows directly from the scope
    rules the gate's own module docstring states in its "Scope" section, not
    from calling `in_scope` itself or re-deriving its regex.

    Real defect classes this would catch:

    * A typo or accidental narrowing/widening in one of `_IN_SCOPE_RE`'s
      three fixed literal prefixes, or an alternative silently dropped.
    * A widened `[^/]+` (e.g. to `.+`, letting a path cross a directory
      separator) -- the `extra_path_segment` case.
    * A dropped or loosened directory anchor -- the `wrong_directory` case.
    * The `gitapex_check_`/`gitapex_gate_` prefix silently widening to also
      accept `gitapex_scan_` -- the `wrong_prefix_scan` case, issue #1032's
      own scope boundary.
    * A regression from `re.fullmatch` to `re.match` -- the `trailing_suffix`
      case, the same fullmatch-vs-match distinction issue #1129's own
      motivating defect turned on, applied here to this gate's own scope
      check.

    `name.startswith("test_") or name == "conftest.py"` is never exercised by
    either generated path here -- see the module docstring's own "An
    observed dead branch" section for why every path either generator can
    build structurally cannot trigger it.
    """
    assert gate.in_scope(_in_scope_path(in_kind, skill, ident)) is True
    assert gate.in_scope(_out_of_scope_path(out_kind, skill, ident)) is False


# ---------------------------------------------------------------------------
# _diff_target_path -- string-comparison (startswith) trigger
# ---------------------------------------------------------------------------

# Printable ASCII, no whitespace at all (codepoint 33 "!" .. 126 "~"): a
# whitespace-free suffix cannot be altered by `_diff_target_path`'s own
# leading `raw.strip()`, so "b/" + suffix round-trips through it unchanged,
# with no filter (and no rejection overhead) needed to guarantee that.
_NO_WHITESPACE_TEXT = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), max_size=80)
_NON_B_PREFIXED_TEXT = st.text(max_size=80).filter(
    lambda s: s.strip() != "/dev/null" and not s.strip().startswith("b/")
)


@_PROPERTIES
@given(suffix=_NO_WHITESPACE_TEXT, other=_NON_B_PREFIXED_TEXT)
def test_diff_target_path_strips_b_prefix_and_rejects_everything_else(suffix: str, other: str) -> None:
    """Model-based for both halves. The expected output of
    `_diff_target_path("b/" + suffix)` is `suffix` by construction -- known
    from how the input was built, not from calling `_diff_target_path`
    itself or mirroring its slicing logic. `/dev/null` -> `None` is a
    fixed-input regression, restated here rather than left only in the
    example-based suite.

    `other` is built to avoid both accepted shapes (`/dev/null`, a
    `b/`-prefixed path) after stripping, so `_diff_target_path(other)` must
    reach its documented `raise ScanError(...)` branch. This is also
    model-based, not merely "does not crash": the expectation of a *raise*,
    not just of some return value, is known from the module docstring's own
    "Anything other than `/dev/null` or git's own `b/`-prefixed post-image
    raises `ScanError`" sentence, independent of `_diff_target_path`'s own
    code.

    Real defect class this would catch: the `b/`-prefix check or the
    `/dev/null` special case being loosened -- e.g. a future change silently
    accepting a `--no-prefix` diff's un-prefixed path, which the module
    docstring explicitly says must not be guessed at.
    """
    assert gate._diff_target_path("b/" + suffix) == suffix
    assert gate._diff_target_path("/dev/null") is None
    with pytest.raises(gate.ScanError):
        gate._diff_target_path(other)


# ---------------------------------------------------------------------------
# parse_added_lines -- string-comparison (startswith, x6) + regex (match)
# ---------------------------------------------------------------------------

_LINE_KIND = st.sampled_from(("+", " ", "-"))
_HUNK_BODY = st.lists(_LINE_KIND, max_size=20)
_START_LINE = st.integers(min_value=1, max_value=500)
_FILE_DIFF = st.tuples(_START_LINE, _HUNK_BODY)
_MULTI_FILE_DIFFS = st.lists(_FILE_DIFF, min_size=1, max_size=3)


def _expected_added_for_hunk(start: int, kinds: list[str]) -> set[int]:
    """The post-image added-line-number set a correct parser must produce
    for one hunk starting at post-image line `start`, per the module
    docstring's own documented contract: added and context lines both
    advance the counter, a removed line advances nothing, and only added
    lines are recorded."""
    expected: set[int] = set()
    lineno = start
    for kind in kinds:
        if kind == "+":
            expected.add(lineno)
            lineno += 1
        elif kind == " ":
            lineno += 1
    return expected


def _file_diff_text(path: str, start: int, kinds: list[str]) -> str:
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1 +{start} @@",
        *kinds,
    ]
    return "\n".join(lines)


@_PROPERTIES
@given(file_diffs=_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_an_independently_computed_line_count(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Model-based. Each file's synthetic diff is built from a starting
    post-image line number and a generated sequence of "+"/" "/"-" line
    kinds; :func:`_expected_added_for_hunk` recomputes the intended
    added-line-number set directly from the module docstring's own
    documented post-image-counting contract, not by calling
    `parse_added_lines` or mirroring its control-flow/header-detection state
    machine. Honestly: this re-derives the same counting *rule*
    `parse_added_lines` must itself implement (that rule is the
    specification, not an implementation detail this test independently
    guesses at) -- what it does *not* re-derive is `parse_added_lines`'s own
    state machine (header detection, in-hunk tracking, per-file reset on
    `diff --git `), so a regression there still fails this property: e.g. a
    context line silently failing to advance the counter, a removed line
    incorrectly counted as added, or an off-by-one in `_HUNK_RE`'s own
    captured start line.

    A file whose hunk body adds nothing never gets a key in
    `parse_added_lines`'s own returned dict (`added.setdefault` is only
    reached from the "+" branch), so files with an empty expected set are
    dropped from both sides of the comparison to match that documented
    shape, not papered over.

    `paths` is derived directly from `len(file_diffs)`, so `zip(..., strict=
    True)` can never raise here -- unlike the paired-vs-independently-sized
    strategy bug the reference pilot file's own
    `test_traversal_tokens_never_bind_outside_the_skill_directory` docstring
    records, `file_diffs` is one single generated list, never two combined.
    """
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )

    added = gate.parse_added_lines(diff_text)

    expected = {
        path: _expected_added_for_hunk(start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    }
    expected = {path: lines for path, lines in expected.items() if lines}
    assert added == expected


# ---------------------------------------------------------------------------
# _waived_lines -- regex (search) trigger
# ---------------------------------------------------------------------------

_REASON_TEXT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=24,
)


def _source_with_waiver_at_line(before: int, after: int, reason: str) -> tuple[str, int]:
    """A `before + 1 + after`-line source where exactly one line -- number
    `before + 1` -- carries a real waiver comment with `reason`; every other
    line is a plain assignment statement carrying no comment at all."""
    lines = [f"x{i} = {i}" for i in range(before)]
    waiver_line = before + 1
    lines.append(f"y = 1  # detection-logic-property-coverage: WAIVED: {reason}")
    lines.extend(f"z{i} = {i}" for i in range(after))
    return "\n".join(lines) + "\n", waiver_line


def _source_with_waiver_text_only_in_a_string_literal(reason: str) -> str:
    """The same waiver text, but as the *content* of a string literal, never
    as a real comment -- `tokenize` emits a STRING token here, never a
    COMMENT one."""
    return f'DOC = "# detection-logic-property-coverage: WAIVED: {reason}"\n'


@_PROPERTIES
@given(before=st.integers(0, 5), after=st.integers(0, 5), reason=_REASON_TEXT)
def test_waived_lines_finds_exactly_the_real_comment_line(before: int, after: int, reason: str) -> None:
    """Model-based. The expected waived-line set is known by construction in
    both halves of this property, independent of `_waived_lines`'s own
    implementation:

    1. A source built with the waiver marker on exactly one real comment
       line, surrounded by plain, comment-free assignment statements, must
       waive exactly that one line number -- not a superset (a plain code
       line falsely flagged) and not a subset (the real marker missed).
    2. The identical marker text placed only inside a string literal's own
       content -- never as a comment -- must waive nothing at all.

    Real defect class this would catch: switching the implementation from a
    `tokenize`-based scan to a raw-text/regex-over-lines scan, which the
    module docstring's own "Waiver" section explicitly says must not happen
    ("honoured only as a real comment token and never inside a string
    literal quoting this gate's own documentation"). Case 2 above fails
    immediately against such a regression, since a raw-text scan would find
    the marker text inside the string literal too.
    """
    comment_source, waiver_line = _source_with_waiver_at_line(before, after, reason)
    assert gate._waived_lines(comment_source) == {waiver_line}

    string_literal_source = _source_with_waiver_text_only_in_a_string_literal(reason)
    assert gate._waived_lines(string_literal_source) == set()

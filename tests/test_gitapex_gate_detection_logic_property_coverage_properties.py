"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_detection_logic_property_coverage.py`` (issue
#1178). Covers the five functions in that file which, per its own AST-shape
trigger rules (that module's own "Trigger categories" docstring section),
actually contain a regex-, path-resolution-, or string-comparison-shaped call
reached by this diff: :func:`in_scope`, :func:`_diff_target_path`,
:func:`_looks_like_real_header_pair`, :func:`parse_added_lines`, and
:func:`_waived_lines`.

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
* :func:`_looks_like_real_header_pair` -- two ``.startswith(...)`` call sites
  (string-comparison): ``source.startswith("a/")``, ``target.startswith("b/")``.
  Its two ``== "/dev/null"`` equality checks are not triggers at all under
  the gate's own strict rules -- ``_string_comparison_compare_trigger``
  matches only an ``in``/``not in`` comparator against an inline collection
  literal, never a bare ``==``.
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

This matches the earlier trace it was checked against, unchanged; no addition
or correction was needed.

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

import os

import gitapex_gate_detection_logic_property_coverage as gate
import pytest
import unidiff
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
#
# Issue #1316: the PR-blocking gate's own invocation (this default branch)
# stays pinned exactly as before -- fast and deterministic. A separate,
# scheduled, non-PR-blocking workflow
# (.github/workflows/diff-parsing-property-deep-scan.yml) sets
# GITAPEX_HYPOTHESIS_DEEP_SCAN=1 to re-run these same properties with much
# higher, randomized exploration instead, without touching this file's
# own default settings object or requiring a duplicate test body.
_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)


def _unidiff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Issue #1316: an independent oracle for `parse_added_lines`'s own
    `{path: added-lines}` contract, computed by `unidiff`'s own parser --
    a genuinely different mechanism from this file's hand-rolled
    header/hunk state machine, unlike `_expected_added_for_hunk` below
    (which re-derives the same counting *rule* `parse_added_lines` must
    itself implement, not an independent parse). A file whose hunk body
    adds nothing is dropped, matching `parse_added_lines`'s own documented
    shape (`added.setdefault` is only reached from the "+" branch)."""
    result: dict[str, set[int]] = {}
    for patched_file in unidiff.PatchSet(diff_text):
        # `target_line_no` is `int | None` per unidiff's own stub, but is
        # always a real int for an added line -- only a removed line ever
        # carries `target_line_no is None`.
        added = {
            line.target_line_no
            for hunk in patched_file
            for line in hunk
            if line.is_added and line.target_line_no is not None
        }
        if added:
            result[patched_file.path] = added
    return result


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
# _looks_like_real_header_pair -- string-comparison (startswith, x2) trigger
# ---------------------------------------------------------------------------

_HEADER_PATH_TEXT = st.text(max_size=60)
_NOT_A_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("a/"))
_NOT_B_PREFIXED_TEXT = st.text(max_size=80).filter(lambda s: s != "/dev/null" and not s.startswith("b/"))


@_PROPERTIES
@given(
    matching_path=_HEADER_PATH_TEXT,
    rename_source_path=_HEADER_PATH_TEXT,
    rename_target_path=_HEADER_PATH_TEXT,
    not_a_prefixed=_NOT_A_PREFIXED_TEXT,
    not_b_prefixed=_NOT_B_PREFIXED_TEXT,
)
def test_looks_like_real_header_pair_recognises_every_real_shape_and_rejects_the_rest(
    matching_path: str,
    rename_source_path: str,
    rename_target_path: str,
    not_a_prefixed: str,
    not_b_prefixed: str,
) -> None:
    """Model-based for every case. Each input pair is built to have a known
    answer by construction, not by recomputing `_looks_like_real_header_pair`'s
    own `a/`/`b/`/`/dev/null` formula:

    * A same-stem `a/<path>`/`b/<path>` pair is exactly the shape a real,
      unrenamed file's own header pair always has -- True.
    * `/dev/null` on either side alone (source for a new file, target for a
      deleted one) is a real header shape too -- True, independent of what
      the other side names.
    * A *different*-stem `a/<path1>`/`b/<path2>` pair is still real-shaped --
      a renamed file's own header pair never has matching stems, and the
      function's own docstring states plainly it is "deliberately silent on
      whether the two paths match." True.
    * `not_a_prefixed`/`not_b_prefixed` are built to structurally avoid both
      the `/dev/null` and `a/`/`b/`-prefixed shapes on their own side, so
      pairing either with anything real-shaped on the other side still makes
      the whole pair False -- ordinary hunk content (a changelog marker, a
      divider) never has this shape by construction, which is the exact
      property this function exists to tell apart from a real absorbed
      header.

    Real defect class this would catch: the `a/`/`b/`-prefix check or the
    `/dev/null` special case on either side being loosened or dropped -- e.g.
    a future change that starts requiring matching stems, which would
    silently stop catching a renamed file's own absorbed header pair, or one
    that drops the `/dev/null` case, which would silently stop catching an
    absorbed new-file or deleted-file header.
    """
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair("--- /dev/null", f"+++ b/{matching_path}") is True
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", "+++ /dev/null") is True
    assert gate._looks_like_real_header_pair(f"--- a/{rename_source_path}", f"+++ b/{rename_target_path}") is True
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ b/{matching_path}") is False
    assert gate._looks_like_real_header_pair(f"--- a/{matching_path}", f"+++ {not_b_prefixed}") is False
    assert gate._looks_like_real_header_pair(f"--- {not_a_prefixed}", f"+++ {not_b_prefixed}") is False


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
    # Explicit, accurate pre- and post-image counts -- not the bare/
    # implicit-1 shorthand this helper used before issue #1193 -- since
    # `kinds` can contain any mix of "+"/" "/"-" lines, or none at all.
    # `parse_added_lines` now tracks both sides (issue #1193, porting
    # issue #1184's own dual-counter fix) and rejects a hunk whose header's
    # declared count on either side does not match its own real body, so a
    # still-bare or post-image-only-accurate header here would make this
    # generator produce a malformed diff whenever `kinds` doesn't happen to
    # carry exactly one pre-image (" "/"-") or post-image ("+"/" ") line,
    # which `parse_added_lines` would then correctly raise `ScanError` on --
    # not the counting behavior this property means to exercise.
    pre_image_count = sum(1 for kind in kinds if kind != "+")
    post_image_count = sum(1 for kind in kinds if kind != "-")
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,{pre_image_count} +{start},{post_image_count} @@",
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


# unidiff's own hunk parser cannot handle a zero/zero declared hunk with an
# empty body (`@@ -1,0 +1,0 @@` followed immediately by the next file's own
# `diff --git ` line) -- confirmed directly against the installed unidiff
# 1.0.0 (`UnidiffParseError: Hunk diff line expected: diff --git a/...`).
# Real `git diff` output never emits a hunk with nothing in it, so this is
# not a gap in the oracle's real-world coverage; the differential property
# below uses a non-empty-hunk-body variant of the shared strategy above so
# every generated diff stays within unidiff's own parseable shape. The
# empty-hunk-body case stays covered by the self-consistency property
# above, which needs no external parser.
_NON_EMPTY_HUNK_BODY = st.lists(_LINE_KIND, min_size=1, max_size=20)
_NON_EMPTY_FILE_DIFF = st.tuples(_START_LINE, _NON_EMPTY_HUNK_BODY)
_NON_EMPTY_MULTI_FILE_DIFFS = st.lists(_NON_EMPTY_FILE_DIFF, min_size=1, max_size=3)


@_PROPERTIES
@given(file_diffs=_NON_EMPTY_MULTI_FILE_DIFFS)
def test_parse_added_lines_matches_unidiffs_independent_parse(
    file_diffs: list[tuple[int, list[str]]],
) -> None:
    """Differential-oracle property (issue #1316). Compares
    `parse_added_lines`'s own `{path: added-lines}` output against
    `unidiff`'s own independent parse of the identical generated diff
    text -- a genuinely independent parser, catching a misattribution-
    class defect the sibling property above cannot, since that property
    recomputes the same post-image-counting *rule* `parse_added_lines`
    must itself implement, never an independent parse of the diff text
    itself. True-negative coverage across many well-formed generated
    diffs; the corresponding true-positive check (does this oracle catch
    the real header-misattribution defect class issue #1184/#1193 fixed)
    is recorded as a fixed regression case rather than a Hypothesis
    property, since it needs a specific adversarial input shape (a
    disguised header mid-hunk) this property's own generator does not
    construct -- see this file's own regression suite
    (`tests/test_gitapex_gate_detection_logic_property_coverage.py`) and
    this task's own commit message for that proof.
    """
    paths = [f"module_{index}.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, kinds) for path, (start, kinds) in zip(paths, file_diffs, strict=True)
    )
    assert gate.parse_added_lines(diff_text) == _unidiff_added_lines(diff_text)


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

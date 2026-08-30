"""Hypothesis property-based layer for
``skills/executing-a-branch-plan/scripts/gitapex_check_task_commit_provenance.py``
(issue #1477, closing issue #1178's own ``detection-logic-property-coverage``
gap for this new module's ``load_provenance_scanner``, whose default
resolution path calls ``Path(__file__).resolve()``).

This module resolves via ``import gitapex_check_task_commit_provenance``
against ``skills/executing-a-branch-plan/scripts`` (that directory's own
``pyproject.toml`` ``pythonpath`` entry, the same resolution
``test_gitapex_check_branch_plan_reverified_properties.py`` already uses for
its sibling module in the same directory).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py`` and
``tests/test_gitapex_check_acm_present_properties.py``.

The three filesystem-backed properties use a **module-scoped** fixture, not
``tmp_path`` -- matching
``tests/test_gitapex_gate_no_raw_gh_cli_in_docs_properties.py``'s own
resolution of Hypothesis' ``function_scoped_fixture`` health check: one base
directory is handed out once, and each generated example creates its own
fresh subdirectory inside it via ``tempfile.mkdtemp``, so no example can
read or write another example's state.
"""

from __future__ import annotations

import pathlib
import tempfile

import gitapex_check_task_commit_provenance as checker
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)
_FILESYSTEM_PROPERTIES = settings(derandomize=True, max_examples=150, deadline=None)

# Safe, portable filename components: no path separator, no NUL, non-empty --
# a generated value used as a bare filename under a scratch directory, never
# crossing out of it.
_FILENAME_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="/\\\x00")
_FILENAMES = st.text(alphabet=_FILENAME_ALPHABET, min_size=1, max_size=40).filter(
    lambda s: s not in (".", "..") and s.strip() != ""
)

# Literal Python source fragments for a "value assigned to scan" that is
# never callable -- driven across many generated literals rather than one
# hand-picked int, per this module's own `getattr(module, "scan", None)`
# callable check.
_NON_CALLABLE_SCAN_LITERALS = st.one_of(
    st.integers(),
    st.text(max_size=20).map(repr),
    st.booleans(),
    st.none(),
    st.floats(allow_nan=False, allow_infinity=False),
).map(repr)


@pytest.fixture(scope="module")
def scratch_root(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """One base directory for the whole module; see this module's own
    docstring for why this, not ``tmp_path``, resolves Hypothesis'
    ``function_scoped_fixture`` health check."""
    return tmp_path_factory.mktemp("task_commit_provenance_properties")


@_FILESYSTEM_PROPERTIES
@given(filename=_FILENAMES)
def test_any_nonexistent_path_is_rejected_loudly_never_silently(filename: str, scratch_root: pathlib.Path) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    for any generated filename that does not exist under a fresh scratch
    subdirectory, ``load_provenance_scanner`` always raises
    ``ScannerLoadError`` naming the missing path -- driven across a wide
    space of Unicode filenames, not only the single hand-picked
    ``does-not-exist.py`` example in the fixed-example suite. A missing
    scan dependency must never resolve to an implicit clean verdict.

    Confirmed to have teeth: removing the ``if not path.is_file(): raise
    ScannerLoadError(...)`` guard (letting ``spec_from_file_location`` run
    directly against the nonexistent path) makes this property fail on the
    first generated example -- on Python 3.12,
    ``importlib.util.spec_from_file_location`` for a nonexistent path
    returns a spec whose loader raises ``ModuleNotFoundError`` only once
    ``exec_module`` actually runs, one step later than this function's own
    ``except Exception`` around that call catches it, so the real observed
    failure is "could not be loaded as a Python module" -- a different,
    less specific message than the documented "was not found", not the
    silent pass a first guess might expect.
    """
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    missing = root / filename
    assert not missing.exists()
    with pytest.raises(checker.ScannerLoadError, match="was not found"):
        checker.load_provenance_scanner(missing)


@_FILESYSTEM_PROPERTIES
@given(literal=_NON_CALLABLE_SCAN_LITERALS)
def test_any_non_callable_scan_attribute_is_rejected(literal: str, scratch_root: pathlib.Path) -> None:
    """**Model-based:** for any generated non-callable value assigned to a
    module-level ``scan`` name (an int, a string, a bool, ``None``, or a
    float), ``load_provenance_scanner`` rejects the module as not the real
    scanner -- driven across many generated literals rather than the one
    hand-picked ``VALUE = 1`` example (which does not even define ``scan``
    at all) in the fixed-example suite.

    Confirmed to have teeth: replacing ``callable(getattr(module, "scan",
    None))`` with a mere ``hasattr(module, "scan")`` makes this property
    fail on every generated example, since each decoy module genuinely
    defines a `scan` attribute -- just not a callable one.
    """
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    decoy = root / "decoy.py"
    decoy.write_text(f"scan = {literal}\n", encoding="utf-8")
    with pytest.raises(checker.ScannerLoadError, match="no callable scan"):
        checker.load_provenance_scanner(decoy)


@_FILESYSTEM_PROPERTIES
@given(source=st.text(max_size=200))
def test_arbitrary_file_content_never_raises_an_uncaught_exception(source: str, scratch_root: pathlib.Path) -> None:
    """Robustness: arbitrary file content -- syntactically invalid Python,
    a runtime error at module scope, or anything else -- reaching
    ``load_provenance_scanner`` always resolves to a caught
    ``ScannerLoadError``, never an uncaught exception escaping this
    function. This module runs as a merge-blocking main-thread gate, where
    an uncaught exception would crash the check itself rather than report
    a verdict.
    """
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    candidate = root / "candidate.py"
    candidate.write_text(source, encoding="utf-8")
    with pytest.raises(checker.ScannerLoadError):
        checker.load_provenance_scanner(candidate)


@_PROPERTIES
@given(messages=st.lists(st.text(max_size=50), max_size=10))
def test_split_commit_messages_never_produces_an_empty_entry(messages: list[str]) -> None:
    """Robustness: for any list of generated message strings (including
    ones already containing NUL, empty strings, or both), splitting their
    NUL-joined form never yields an empty entry -- ``find_flagged_commits``
    relies on this to keep commit indices meaningful."""
    raw = "".join(message + "\0" for message in messages)
    result = checker.split_commit_messages(raw)
    assert all(entry for entry in result)


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_split_commit_messages_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text produces a result rather than an
    exception, and the same input produces the same output."""
    first = checker.split_commit_messages(text)
    second = checker.split_commit_messages(text)
    assert first == second
    assert isinstance(first, list)

"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_plans_traceability.py`` (issue #1796), closing
issue #1178's own ``detection-logic-property-coverage`` gap for this new
module's regex compiles (`_ISSUE_URL_RE`, `_SOURCE_ACM_ROWS_RE`,
`_FENCED_CODE_BLOCK_RE`, `_PLAN_FILE_SHAPE_RE`, `_EXCLUDED_STATUS_RE`), its
module-level `REPO_ROOT` path resolution, and the string-comparison/split/
regex call sites inside `find_missing_traceability`, `_parse_name_status_line`,
`_added_or_modified` and `_diff_plan_files`.

This module resolves via ``import gitapex_gate_plans_traceability`` --
``.github/scripts`` is on pyproject.toml's own ``pythonpath``, the same
resolution ``tests/test_gitapex_gate_plans_traceability.py`` already uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching this repository's own established rationale in
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.

The two properties that build a real git repository (`_diff_plan_files`) use
a **module-scoped** fixture, not ``tmp_path`` -- the same resolution for
Hypothesis' ``function_scoped_fixture`` health check
``tests/test_gitapex_gate_no_raw_gh_cli_in_docs_properties.py``'s own module
docstring explains: one base directory is handed out once, and each generated
example creates its own fresh subdirectory under it, so sharing the base
cannot leak state between examples. Their ``max_examples`` is lowered well
below the pure-function properties' because each example runs two real `git
commit`s (a seed commit plus the commit under test).
"""

from __future__ import annotations

import pathlib
import string
import subprocess
import tempfile

import gitapex_gate_plans_traceability as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Applied per test, not registered as a global Hypothesis profile -- see the
# module docstring's own "Reproducibility" section.
_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Lowered for the two properties that build a real git repository (two real
# commits per example) rather than exercising a pure function.
_GIT_PROPERTIES = settings(derandomize=True, max_examples=30, deadline=None)


@pytest.fixture(scope="module")
def scratch_root(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """One base directory for the whole module -- see the module docstring's
    own note on why this, and not a per-example ``tmp_path``, resolves
    Hypothesis' ``function_scoped_fixture`` health check honestly."""
    return tmp_path_factory.mktemp("plans_traceability_properties")


def _git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _init_repo(root: pathlib.Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.email", "t@e")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")


# ==========================================================================
# `find_missing_traceability` -- model-based (issue-url / source-acm-rows
# citation presence), exercising `_ISSUE_URL_RE` and `_SOURCE_ACM_ROWS_RE`
# (the module-level regex compiles at lines 69/73) via the `.search(...)`
# call inside `find_missing_traceability` itself (line 133).
# ==========================================================================

# ASCII-only, matching `_ISSUE_URL_RE`'s own `[A-Za-z0-9_.-]+` character
# class exactly -- a generated non-ASCII "letter" (e.g. "µ") is a
# category-Ll codepoint Python's `str.isalnum()` accepts but that regex's
# character class does not, which would make a well-formed, included
# citation line silently fail to match and desync this property's own
# expected-missing computation from what the regex actually decides.
_TOKEN_ALPHABET = st.sampled_from(string.ascii_letters + string.digits + "_.-")
_TOKEN = st.text(alphabet=_TOKEN_ALPHABET, min_size=1, max_size=12).filter(lambda s: any(c.isalnum() for c in s))
_ISSUE_NUMBER = st.integers(min_value=1, max_value=9_999_999)
_ACM_LABEL = st.sampled_from(("Source ACM row:", "Source ACM rows:"))
_LEADING_WS = st.sampled_from(("", " ", "  ", "\t"))


@_PROPERTIES
@given(
    owner=_TOKEN,
    repo=_TOKEN,
    issue_number=_ISSUE_NUMBER,
    acm_label=_ACM_LABEL,
    issue_indent=_LEADING_WS,
    acm_indent=_LEADING_WS,
    include_issue=st.booleans(),
    include_acm=st.booleans(),
)
def test_find_missing_traceability_matches_exactly_the_present_citations(
    owner: str,
    repo: str,
    issue_number: int,
    acm_label: str,
    issue_indent: str,
    acm_indent: str,
    include_issue: bool,
    include_acm: bool,
) -> None:
    """**Model-based:** for ANY owner/repo token pair, issue number,
    `Source ACM row`/`rows` label spelling, and leading-whitespace amount,
    `find_missing_traceability`'s verdict for each of `"issue-url"`/
    `"source-acm-rows"` exactly matches whether a genuine citation line for
    that label was included -- generalizing
    tests/test_gitapex_gate_plans_traceability.py's own hand-picked
    `tvna/gitapex/issues/1796` example and singular/plural ACM-label
    fixtures across generated owner/repo/number/label variation, not only
    that one fixture. The expected-missing set is computed here from what
    the generator itself chose to include, independently of the module's
    own regex objects.
    """
    lines = ["# Sample plan", ""]
    if include_issue:
        lines.append(f"{issue_indent}Issue: https://github.com/{owner}/{repo}/issues/{issue_number}")
    if include_acm:
        lines.append(f'{acm_indent}{acm_label} row 1 ("Sample criterion").')
    content = "\n".join(lines) + "\n"

    missing = set(gate.find_missing_traceability(content))
    expected = set()
    if not include_issue:
        expected.add("issue-url")
    if not include_acm:
        expected.add("source-acm-rows")
    assert missing == expected


@_PROPERTIES
@given(owner=_TOKEN, repo=_TOKEN, issue_number=_ISSUE_NUMBER, acm_label=_ACM_LABEL)
def test_find_missing_traceability_ignores_citations_inside_a_fenced_code_block(
    owner: str, repo: str, issue_number: int, acm_label: str
) -> None:
    """**Model-based:** for ANY generated owner/repo/issue-number/ACM-label
    combination, a citation that appears only inside a fenced code block
    never counts as genuine -- both labels are always reported missing,
    regardless of what the fenced-out citation content actually says.
    Exercises `_FENCED_CODE_BLOCK_RE` (module level, line 79) together with
    the two citation regexes on the same generated content."""
    fenced = (
        "# Sample plan\n\n"
        "```\n"
        f"Issue: https://github.com/{owner}/{repo}/issues/{issue_number}\n"
        f'{acm_label} row 1 ("Sample criterion").\n'
        "```\n"
    )
    assert set(gate.find_missing_traceability(fenced)) == {"issue-url", "source-acm-rows"}


# ==========================================================================
# `_parse_name_status_line` -- model-based, exercising its own
# `line.split("\t")` (line 166) and `status.startswith("R")` (line 171).
# ==========================================================================

_PATH_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs", "Cf"), blacklist_characters="\t\n\r")
_PATH_TEXT = st.text(alphabet=_PATH_ALPHABET, min_size=1, max_size=20).filter(lambda s: s.strip() != "")
_NON_RENAME_STATUS = st.sampled_from(("A", "M", "T", "D", "C100"))
_RENAME_STATUS = st.sampled_from(("R087", "R100", "R042"))


@_PROPERTIES
@given(status=_NON_RENAME_STATUS, old_path=_PATH_TEXT)
def test_parse_name_status_line_non_rename_reuses_old_path_as_new_path(status: str, old_path: str) -> None:
    """For ANY non-rename status code and path, `_parse_name_status_line`
    returns `(status, old_path, old_path)` -- the `new_path == old_path`
    identity a non-rename line always carries, checked across generated
    status/path content rather than only the one fixed `"A"` example in
    the sibling example suite. Compared against `old_path.strip()`, not
    `old_path` itself -- `_parse_name_status_line` strips each field, so a
    generated path carrying incidental leading/trailing whitespace must
    round-trip stripped, not verbatim."""
    stripped = old_path.strip()
    assert gate._parse_name_status_line(f"{status}\t{old_path}") == (status, stripped, stripped)


@_PROPERTIES
@given(status=_RENAME_STATUS, old_path=_PATH_TEXT, new_path=_PATH_TEXT)
def test_parse_name_status_line_rename_round_trips_both_paths(status: str, old_path: str, new_path: str) -> None:
    """For ANY rename status code (any similarity score) and any old/new
    path pair, `_parse_name_status_line` returns the destination path, not
    the source -- across generated content, not only the one fixed
    `"R087"` example in the sibling example suite. Compared against each
    path's own `.strip()`, matching `_parse_name_status_line`'s own
    per-field stripping."""
    assert gate._parse_name_status_line(f"{status}\t{old_path}\t{new_path}") == (
        status,
        old_path.strip(),
        new_path.strip(),
    )


@_PROPERTIES
@given(status=_RENAME_STATUS, old_path=_PATH_TEXT)
def test_parse_name_status_line_rename_without_destination_always_raises(status: str, old_path: str) -> None:
    """For ANY rename status code missing its destination field, parsing
    raises `GateError` -- generalizing the one fixed `"R100"` example in
    the sibling example suite to every rename similarity score."""
    with pytest.raises(gate.GateError, match="rename line carries no destination"):
        gate._parse_name_status_line(f"{status}\t{old_path}")


# ==========================================================================
# `_added_or_modified` -- model-based, exercising its own CRLF/CR
# normalization + split (line 183) and `line.strip()`/`_EXCLUDED_STATUS_RE.
# match(...)` filter (line 184).
# ==========================================================================

_KEEP_STATUSES = ("A", "M", "T", "C100", "R087")
_DROP_STATUSES = ("D", "R100")
_EOL = st.sampled_from(("\n", "\r\n", "\r"))
_LINE_PATH = st.text(alphabet=_PATH_ALPHABET, min_size=1, max_size=10).filter(lambda s: s.strip() != "")

_NAME_STATUS_LINE = st.one_of(
    st.tuples(st.sampled_from(_KEEP_STATUSES + _DROP_STATUSES), _LINE_PATH).map(lambda t: f"{t[0]}\t{t[1]}"),
    st.just(""),  # a blank line -- must be dropped regardless of any status text
    st.text(alphabet=st.sampled_from((" ", "\t")), min_size=1, max_size=3),  # whitespace-only line
)


@_PROPERTIES
@given(entries=st.lists(_NAME_STATUS_LINE, max_size=8), eol=_EOL)
def test_added_or_modified_keeps_exactly_the_non_blank_non_excluded_lines(entries: list[str], eol: str) -> None:
    """**Model-based:** for ANY sequence of generated `--name-status`-shaped
    lines (mixing kept statuses, dropped `D`/`R100` statuses, blank lines,
    and whitespace-only lines) joined by ANY of the three line-ending
    forms this module normalizes, `_added_or_modified` keeps exactly the
    lines that are non-blank and not `D`-/`R100`-prefixed.

    The expected set is computed here via `str.splitlines()` (Python's own
    universal-newline splitter, a different mechanism from this module's
    own `.replace("\\r\\n", "\\n").replace("\\r", "\\n").split("\\n")`
    pipeline) and `str.startswith(...)` (rather than
    `_EXCLUDED_STATUS_RE.match(...)`) -- two independently-implemented
    checks, not the module's own, so agreement is evidence rather than a
    tautology.
    """
    text = eol.join(entries)
    kept = gate._added_or_modified(text)
    expected = [line for line in text.splitlines() if line.strip() and not line.startswith(("D\t", "R100\t"))]
    assert kept == expected


# ==========================================================================
# `_diff_plan_files` -- model-based, over a real git repository per
# example. Exercises its own `_PLAN_FILE_SHAPE_RE.fullmatch(...)` call
# (line 201).
# ==========================================================================

# ASCII-only, matching `_PLAN_FILE_SHAPE_RE`'s own `[A-Za-z0-9._-]+`
# character class exactly -- see `_TOKEN_ALPHABET`'s own comment above for
# why a non-ASCII "letter" would desync a generated example from what the
# regex actually accepts.
_PLAN_NAME_ALPHABET = st.sampled_from(string.ascii_letters + string.digits + "._-")
_PLAN_NAME = st.text(alphabet=_PLAN_NAME_ALPHABET, min_size=1, max_size=12).filter(
    lambda s: any(c.isalnum() for c in s)
)


@_GIT_PROPERTIES
@given(names=st.lists(_PLAN_NAME, min_size=1, max_size=4, unique=True))
def test_diff_plan_files_returns_exactly_the_added_well_formed_paths(
    names: list[str], scratch_root: pathlib.Path
) -> None:
    """**Model-based:** for ANY set of well-formed
    `docs/gitapex/plans/<name>.md` filenames added in one commit,
    `_diff_plan_files` returns exactly those paths -- generalizing the
    sibling example suite's two fixed single-file examples
    (`test_check_diff_passes_for_a_well_formed_added_plans_file`,
    `test_check_diff_only_grades_the_file_actually_touched_not_a_sibling`)
    to generated filenames and to more than one file added in the same
    diff at once. The expected set is the generator's own record of what
    it named and wrote, not anything recomputed from
    `_PLAN_FILE_SHAPE_RE` itself.
    """
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    _init_repo(root)
    plans_dir = root / "docs" / "gitapex" / "plans"
    plans_dir.mkdir(parents=True)
    for name in names:
        (plans_dir / f"{name}.md").write_text("placeholder\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add plans files")

    result = gate._diff_plan_files(root, "HEAD~1", "HEAD")

    assert sorted(result) == sorted(f"docs/gitapex/plans/{name}.md" for name in names)


@_GIT_PROPERTIES
@given(nested_dir=_PLAN_NAME, name=_PLAN_NAME)
def test_diff_plan_files_raises_for_any_nested_plans_path(
    nested_dir: str, name: str, scratch_root: pathlib.Path
) -> None:
    """**Model-based:** for ANY nested `docs/gitapex/plans/<dir>/<name>.md`
    path added in the diff, `_diff_plan_files` raises `GateError` naming
    it as an unsupported shape -- generalizing the sibling example suite's
    one fixed `docs/gitapex/plans/nested/deep.md` fixture to generated
    directory and file names, confirming the `.fullmatch(...)` rejection
    (rather than a partial `.match(...)`/`.search(...)`) holds generally."""
    root = pathlib.Path(tempfile.mkdtemp(dir=scratch_root))
    _init_repo(root)
    nested_path = root / "docs" / "gitapex" / "plans" / nested_dir / f"{name}.md"
    nested_path.parent.mkdir(parents=True)
    nested_path.write_text("placeholder\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add nested plans file")

    with pytest.raises(gate.GateError, match="unsupported docs/gitapex/plans"):
        gate._diff_plan_files(root, "HEAD~1", "HEAD")

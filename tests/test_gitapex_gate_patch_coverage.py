"""Tests for the patch-coverage gate
(.github/scripts/gitapex_gate_patch_coverage.py).

Issue #1568 (gate-proposal-umbrella, consolidating #1493, #1509, #1539,
#1555, #1703, #1718, #1724, #1862): a diff-added line inside this
repository's own coverage-tracked source directories must be exercised
by a test -- a local, pre-push equivalent of Codecov's own
patch-coverage check.

`parse_added_lines`/`_diff_target_path`/`_looks_like_real_header_pair`
are byte-for-byte copies of the sibling diff-scoped gates' own parser
(see gitapex_gate_function_body_test_coverage.py's own module docstring
for the full incremental history of why each boundary check exists) --
their own direct tests below are likewise ported from that file's own
test suite rather than re-derived, since the code under test is
identical.

Per this repository's defeat-test-disclosure process, at least one test
below is specifically constructed to defeat -- not merely exercise the
happy path of -- the new detection logic; see the `test_defeat_*` tests
below.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import gitapex_gate_local_preflight
import gitapex_gate_patch_coverage as gate
import pytest
from conftest import FakeStdin as _FakeStdin
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "gitapex_gate_patch_coverage.py"
_WORKFLOW_NAME = "patch-coverage-gate.yml"


def _diff(path: str, added_lines: list[int]) -> str:
    """Build a minimal single-hunk unified diff adding `path` with
    content lines at exactly `added_lines` (1-indexed), padded with
    unrelated placeholder lines so the hunk's own declared count matches
    its body -- the same synthetic-diff-fixture convention the sibling
    diff-scoped gates' own test suites already use."""
    total = max(added_lines)
    body = []
    for line_no in range(1, total + 1):
        body.append(f"+line {line_no}" if line_no in added_lines else f"+placeholder {line_no}")
    return "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            "--- /dev/null",
            f"+++ b/{path}",
            f"@@ -0,0 +1,{total} @@",
            *body,
            "",
        ]
    )


_UNPARSEABLE_HUNK_DIFF = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ garbage @@\n+x = 1\n"

_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF = "diff --git a/x.py b/x.py\n+++ b/x.py\n@@ -0,0 +1,1 @@\n+x = 1\n"


# --- parse_added_lines / _diff_target_path / _looks_like_real_header_pair ---
# Ported directly from gitapex_gate_function_body_test_coverage.py's own test
# suite (identical code under test, see the module docstring above).


def test_diff_target_path_returns_none_for_dev_null() -> None:
    assert gate._diff_target_path("/dev/null") is None


def test_diff_target_path_strips_the_b_prefix() -> None:
    assert gate._diff_target_path("b/x.py") == "x.py"


def test_diff_target_path_raises_on_an_unrecognised_prefix() -> None:
    with pytest.raises(gate.ScanError, match="not a plain b/-prefixed path"):
        gate._diff_target_path("c/some/other/prefix.py")


def test_looks_like_real_header_pair_accepts_a_genuine_pair() -> None:
    assert gate._looks_like_real_header_pair("--- a/x.py", "+++ b/x.py")


def test_looks_like_real_header_pair_rejects_ordinary_content() -> None:
    assert not gate._looks_like_real_header_pair("--- not a header", "+++ also not one")


def test_parse_added_lines_returns_the_added_line_numbers_per_path() -> None:
    added = gate.parse_added_lines(_diff("x.py", [1, 2, 3]))
    assert added == {"x.py": {1, 2, 3}}


def test_parse_added_lines_skips_added_lines_for_a_deleted_file() -> None:
    diff_text = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-x = 1\n"
    assert gate.parse_added_lines(diff_text) == {}


def test_parse_added_lines_raises_on_unparseable_hunk_header() -> None:
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(_UNPARSEABLE_HUNK_DIFF)


def test_parse_added_lines_raises_on_post_image_without_source_header() -> None:
    with pytest.raises(gate.ScanError, match="no `--- ` source header"):
        gate.parse_added_lines(_POST_IMAGE_WITHOUT_SOURCE_HEADER_DIFF)


def test_parse_added_lines_raises_on_an_over_declared_hunk_count() -> None:
    """Exercises `_reject_if_hunk_incomplete`'s own raise path: the hunk
    header below declares 2 post-image lines but the body supplies only 1,
    so the boundary check at the next hunk header must fire."""
    diff_text = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,0 +1,2 @@\n+first\n@@ -5,0 +6,1 @@\n+second\n"
    with pytest.raises(gate.ScanError, match="declared more"):
        gate.parse_added_lines(diff_text)


def test_parse_added_lines_raises_at_the_diff_end_on_an_incomplete_hunk() -> None:
    diff_text = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,0 +1,2 @@\n+only one line\n"
    with pytest.raises(gate.ScanError, match="declared more"):
        gate.parse_added_lines(diff_text)


def test_a_dash_plus_shaped_hunk_with_nothing_following_it_is_not_an_error() -> None:
    """A hunk that closes exactly on a `--- `/`+++ ` real-looking header
    pair, with nothing after it at all (not a new hunk or file header),
    must not raise -- only the ambiguous case (immediately followed by
    what looks like a new hunk/file transition) does."""
    diff_text = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -5,0 +6,1 @@\n+added line\n--- a/y.py\n+++ b/y.py\n"
    )
    assert gate.parse_added_lines(diff_text) == {"x.py": {6}}


def test_parse_added_lines_ignores_an_added_line_with_no_path_yet() -> None:
    """A stray `+`-prefixed line before any `+++ ` post-image header has
    been seen -- a malformed hand-fed diff, never real `git diff` output
    -- is silently ignored (attributed to no path) rather than crashing,
    matching the sibling diff-scoped gates' own identical parser."""
    diff_text = "diff --git a/x.py b/x.py\n+stray line before any header\n"
    assert gate.parse_added_lines(diff_text) == {}


def test_parse_added_lines_advances_line_number_across_context_lines() -> None:
    diff_text = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,3 @@\n unchanged\n+added\n unchanged too\n"
    )
    assert gate.parse_added_lines(diff_text) == {"x.py": {2}}


def test_parse_added_lines_raises_on_an_over_declared_hunk_that_drains_into_a_real_header_pair() -> None:
    diff_text = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,0 +1,1 @@\n"
        "--- a/y.py\n"
        "+++ b/y.py\n"
        "@@ -1,0 +1,1 @@\n"
        "+z = 1\n"
    )
    with pytest.raises(gate.ScanError, match="ambiguous between coincidental"):
        gate.parse_added_lines(diff_text)


def test_a_hunk_draining_into_a_real_header_pair_not_followed_by_a_new_hunk_is_not_an_error() -> None:
    """Same coincidental-header-pair shape as the ambiguous case above,
    but followed by an ordinary context line rather than a new hunk/file
    transition -- not ambiguous, so this must not raise."""
    diff_text = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,0 +1,1 @@\n"
        "--- a/y.py\n"
        "+++ b/y.py\n"
        " an ordinary context line, not a new hunk or file header\n"
    )
    assert gate.parse_added_lines(diff_text) == {"x.py": {1}}


# --- read_coverage_sources ---------------------------------------------------


def test_read_coverage_sources_reads_the_real_pyproject() -> None:
    sources = gate.read_coverage_sources(REPO_ROOT / "pyproject.toml")
    assert ".github/scripts" in sources
    assert "evals/scripts" in sources


def test_read_coverage_sources_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ScanError, match="could not read"):
        gate.read_coverage_sources(tmp_path / "nope.toml")


def test_read_coverage_sources_invalid_toml(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text("not [ valid toml", encoding="utf-8")
    with pytest.raises(gate.ScanError, match="not valid TOML"):
        gate.read_coverage_sources(bad)


def test_read_coverage_sources_no_source_key(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text("[tool.coverage.run]\nbranch = true\n", encoding="utf-8")
    with pytest.raises(gate.ScanError, match=r"no \[tool.coverage.run\] source list"):
        gate.read_coverage_sources(bad)


def test_read_coverage_sources_source_not_a_list(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text('[tool.coverage.run]\nsource = "not-a-list"\n', encoding="utf-8")
    with pytest.raises(gate.ScanError, match="non-empty list of non-blank strings"):
        gate.read_coverage_sources(bad)


def test_read_coverage_sources_strips_trailing_slash(tmp_path: pathlib.Path) -> None:
    good = tmp_path / "pyproject.toml"
    good.write_text('[tool.coverage.run]\nsource = ["a/b/"]\n', encoding="utf-8")
    assert gate.read_coverage_sources(good) == ["a/b"]


# --- in_scope ------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (".github/scripts/gitapex_gate_foo.py", True),
        (".github/scripts/test_gitapex_gate_foo.py", False),
        (".github/scripts/conftest.py", False),
        (".github/scripts/sub/gitapex_gate_foo.py", False),
        ("skills/some-skill/scripts/gitapex_check_foo.py", False),
        (".github/scripts/gitapex_gate_foo.txt", False),
        ("tests/test_gitapex_gate_foo.py", False),
    ],
)
def test_in_scope(path: str, expected: bool) -> None:
    assert gate.in_scope(path, [".github/scripts"]) is expected


def test_in_scope_never_crosses_a_directory_separator_via_a_path_prefix() -> None:
    """A source that is itself a path-prefix of a deeper directory must
    not swallow that deeper directory's own files -- the same
    exact-parent-directory discipline gitapex_gate_evals_scripts_coverage.py's
    own select_files_in_source docstring names as load-bearing."""
    assert gate.in_scope("evals/scripts/sub/foo.py", ["evals"]) is False


# --- _stem / _test_relative_paths ------------------------------------------


def test_stem() -> None:
    assert gate._stem(".github/scripts/gitapex_gate_foo.py") == "gitapex_gate_foo"


def test_test_relative_paths() -> None:
    assert gate._test_relative_paths("gitapex_gate_foo") == (
        "tests/test_gitapex_gate_foo.py",
        "tests/test_gitapex_gate_foo_properties.py",
    )


# --- _waived_lines -----------------------------------------------------------


def test_waived_lines_requires_a_reason() -> None:
    source = "x = 1  # patch-coverage: WAIVED:\ny = 2  # patch-coverage: WAIVED: because reasons\n"
    assert gate._waived_lines(source) == {2}


def test_waived_lines_only_honours_real_comment_tokens() -> None:
    """A string literal containing the waiver marker's own text must not
    be honoured -- only a real `#` comment token counts."""
    source = 'x = "# patch-coverage: WAIVED: not a real comment"\n'
    assert gate._waived_lines(source) == set()


# --- resolve_existing_test_files --------------------------------------------


def test_resolve_existing_test_files(tmp_path: pathlib.Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_foo.py").write_text("", encoding="utf-8")
    result = gate.resolve_existing_test_files(["skills/x/scripts/foo.py", "skills/x/scripts/bar.py"], tmp_path)
    assert result == {
        "skills/x/scripts/foo.py": ["tests/test_foo.py"],
        "skills/x/scripts/bar.py": [],
    }


# --- load_coverage_json ------------------------------------------------------


def test_load_coverage_json_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ScanError, match="could not read"):
        gate.load_coverage_json(tmp_path / "nope.json")


def test_load_coverage_json_invalid_json(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "coverage.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(gate.ScanError, match="not valid JSON"):
        gate.load_coverage_json(bad)


def test_load_coverage_json_no_files_object(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "coverage.json"
    bad.write_text(json.dumps({"totals": {}}), encoding="utf-8")
    with pytest.raises(gate.ScanError, match="no 'files' object"):
        gate.load_coverage_json(bad)


def test_load_coverage_json_ok(tmp_path: pathlib.Path) -> None:
    good = tmp_path / "coverage.json"
    good.write_text(json.dumps({"files": {}}), encoding="utf-8")
    assert gate.load_coverage_json(good) == {"files": {}}


# --- findings_for_file --------------------------------------------------------


def test_findings_for_file_missing_source_file_raises_scan_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ScanError, match="cannot be read as UTF-8"):
        gate.findings_for_file("skills/x/scripts/missing.py", {1}, [], {"files": {}}, tmp_path)


def test_findings_for_file_no_test_file_is_a_violation(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\ny = 2\n", encoding="utf-8")
    violations, waived = gate.findings_for_file(path, {1, 2}, [], {"files": {}}, tmp_path)
    assert waived == []
    assert len(violations) == 1
    assert violations[0].path == path
    assert violations[0].line == 1
    assert "no tests/test_foo.py or tests/test_foo_properties.py exists" in violations[0].message


def test_findings_for_file_no_test_file_but_waived(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1  # patch-coverage: WAIVED: covered via integration test\n", encoding="utf-8")
    violations, waived = gate.findings_for_file(path, {1}, [], {"files": {}}, tmp_path)
    assert violations == []
    assert len(waived) == 1


def test_findings_for_file_missing_coverage_entry_is_a_scan_error(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(gate.ScanError, match="no entry in the coverage report"):
        gate.findings_for_file(path, {1}, ["tests/test_foo.py"], {"files": {}}, tmp_path)


def test_findings_for_file_grades_added_lines_against_coverage(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    coverage_data: dict[str, object] = {"files": {path: {"executed_lines": [1, 3], "missing_lines": [2]}}}
    violations, waived = gate.findings_for_file(path, {1, 2, 3}, ["tests/test_foo.py"], coverage_data, tmp_path)
    assert waived == []
    assert [v.line for v in violations] == [2]


def test_findings_for_file_a_non_statement_added_line_is_not_graded(tmp_path: pathlib.Path) -> None:
    """A diff-added line outside both executed_lines and missing_lines
    (a comment, a blank line, a docstring) is not a coverage-measurable
    statement at all and must not be reported."""
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("# a comment\nx = 1\n", encoding="utf-8")
    coverage_data: dict[str, object] = {"files": {path: {"executed_lines": [2], "missing_lines": []}}}
    violations, waived = gate.findings_for_file(path, {1, 2}, ["tests/test_foo.py"], coverage_data, tmp_path)
    assert violations == []
    assert waived == []


def test_findings_for_file_waived_line_is_honoured(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text(
        "x = 1\ny = 2  # patch-coverage: WAIVED: defensive branch, see issue #1862\n", encoding="utf-8"
    )
    coverage_data: dict[str, object] = {"files": {path: {"executed_lines": [1], "missing_lines": [2]}}}
    violations, waived = gate.findings_for_file(path, {1, 2}, ["tests/test_foo.py"], coverage_data, tmp_path)
    assert violations == []
    assert [w.line for w in waived] == [2]


def test_findings_for_file_missing_or_non_list_lines_is_a_scan_error(tmp_path: pathlib.Path) -> None:
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    coverage_data: dict[str, object] = {"files": {path: {"executed_lines": "not-a-list", "missing_lines": []}}}
    with pytest.raises(gate.ScanError, match="no numeric executed_lines/missing_lines"):
        gate.findings_for_file(path, {1}, ["tests/test_foo.py"], coverage_data, tmp_path)


# --- find_violations (unit, coverage_json supplied) -------------------------


def test_find_violations_no_in_scope_paths_returns_empty(tmp_path: pathlib.Path) -> None:
    violations, waived, graded = gate.find_violations({"other/thing.py": {1}}, [".github/scripts"], tmp_path, None, 60)
    assert (violations, waived, graded) == ([], [], 0)


def test_find_violations_no_coverage_json_and_no_existing_test_file(tmp_path: pathlib.Path) -> None:
    """No --coverage-json given and no in-scope path has an existing test
    file at all -- run_scoped_pytest must never be invoked (nothing to
    run), and every added line is graded uncovered outright."""
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    violations, waived, graded = gate.find_violations({path: {1}}, ["skills/x/scripts"], tmp_path, None, 60)
    assert graded == 1
    assert waived == []
    assert [v.line for v in violations] == [1]


def test_find_violations_with_supplied_coverage_json(tmp_path: pathlib.Path) -> None:
    path = ".github/scripts/gitapex_gate_foo.py"
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_gitapex_gate_foo.py").write_text("", encoding="utf-8")
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps({"files": {path: {"executed_lines": [], "missing_lines": [1]}}}), encoding="utf-8"
    )
    violations, waived, graded = gate.find_violations({path: {1}}, [".github/scripts"], tmp_path, coverage_json, 60)
    assert graded == 1
    assert [v.line for v in violations] == [1]
    assert waived == []


# --- run_scoped_pytest / find_violations without --coverage-json (real subprocess) ---


def test_run_scoped_pytest_raises_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    def _raise_timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["uv"], timeout=1)

    monkeypatch.setattr(gate.subprocess, "run", _raise_timeout)
    with pytest.raises(gate.ScanError, match="timed out"):
        gate.run_scoped_pytest(["tests/foo.py"], tmp_path, tmp_path / "coverage.json", 1)


def test_run_scoped_pytest_raises_on_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    def _raise_oserror(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("uv not found")

    monkeypatch.setattr(gate.subprocess, "run", _raise_oserror)
    with pytest.raises(gate.ScanError, match="could not run pytest"):
        gate.run_scoped_pytest(["tests/foo.py"], tmp_path, tmp_path / "coverage.json", 1)


@pytest.mark.slow
def test_run_scoped_pytest_produces_a_real_coverage_report(tmp_path: pathlib.Path) -> None:
    """A real subprocess call against a genuinely small, fast existing
    test file in this repository -- confirms this gate's own scoped
    pytest invocation actually produces a usable coverage JSON report,
    not merely that the argv it builds looks plausible."""
    coverage_json = tmp_path / "coverage.json"
    gate.run_scoped_pytest(["tests/test_gitapex_run_base_diff.py"], REPO_ROOT, coverage_json, 300)
    data = gate.load_coverage_json(coverage_json)
    files = data["files"]
    assert isinstance(files, dict)
    assert ".github/scripts/gitapex_run_base_diff.py" in files


@pytest.mark.slow
def test_run_scoped_pytest_raises_on_a_failing_or_uncollectable_run() -> None:
    with pytest.raises(gate.ScanError, match="pytest exited"):
        gate.run_scoped_pytest(
            ["tests/test_gitapex_gate_patch_coverage_no_such_file.py"],
            REPO_ROOT,
            REPO_ROOT / "does-not-matter.json",
            60,
        )


@pytest.mark.slow
def test_find_violations_runs_a_scoped_pytest_when_no_coverage_json_given() -> None:
    """End-to-end: no --coverage-json given, an in-scope path with an
    existing test file -- this gate must run its own scoped pytest and
    grade against the result, entirely without depending on a
    pre-existing coverage artifact."""
    path = ".github/scripts/gitapex_run_base_diff.py"
    added = {1}  # module docstring line -- not a coverage-measurable statement, so this must clear cleanly
    violations, waived, graded = gate.find_violations({path: added}, [".github/scripts"], REPO_ROOT, None, 300)
    assert graded == 1
    assert violations == []
    assert waived == []


# --- main() CLI --------------------------------------------------------------


def _run_cli(args: list[str], stdin_bytes: bytes, cwd: pathlib.Path = REPO_ROOT) -> subprocess.CompletedProcess[bytes]:
    """Black-box invocation of the real script via subprocess (not
    gate.main() in-process), for a real CLI-entrypoint smoke test. This
    runs in a separate process, so coverage.py cannot attribute any of
    it back to this test suite's own measurement -- every other main()
    test below calls gate.main() in-process instead, exactly so its
    coverage is actually counted."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin_bytes,
        capture_output=True,
        check=False,
        cwd=cwd,
    )


@pytest.mark.slow
def test_main_cli_entrypoint_smoke_test() -> None:
    diff_text = _diff("docs/README.md", [1])
    result = _run_cli([], diff_text.encode())
    assert result.returncode == 0, result.stderr


def test_main_clean_when_nothing_in_scope(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    diff_text = _diff("docs/README.md", [1])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(diff_text.encode()))
    exit_code = gate.main([])
    assert exit_code == 0
    assert "OK: 0 in-scope file(s)" in capsys.readouterr().out


def test_main_bad_root_exits_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b""))
    exit_code = gate.main(["--root", "/no/such/directory"])
    assert exit_code == 2
    assert "--root must be an existing directory" in capsys.readouterr().err


def test_main_bad_coverage_json_path_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b""))
    exit_code = gate.main(["--coverage-json", "/no/such/file.json"])
    assert exit_code == 2
    assert "--coverage-json must name an existing file" in capsys.readouterr().err


def test_main_diff_file_not_utf8(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "diff.txt"
    bad.write_bytes(b"\xff\xfe")
    exit_code = gate.main(["--diff", str(bad)])
    assert exit_code == 2
    assert "cannot be read as UTF-8" in capsys.readouterr().err


def test_main_stdin_not_utf8(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b"\xff\xfe"))
    exit_code = gate.main([])
    assert exit_code == 2
    assert "cannot be read as UTF-8" in capsys.readouterr().err


def test_main_scan_error_from_bad_diff(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(b"@@ -bad hunk @@\n"))
    exit_code = gate.main([])
    assert exit_code == 2
    assert "unparseable hunk header" in capsys.readouterr().err


def test_main_reports_a_violation_with_a_supplied_coverage_json(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = ".github/scripts/gitapex_gate_zzz_fixture.py"
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.coverage.run]\nsource = [".github/scripts"]\n', encoding="utf-8")
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps({"files": {path: {"executed_lines": [], "missing_lines": [1]}}}), encoding="utf-8"
    )
    diff_text = _diff(path, [1])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(diff_text.encode()))
    # Relative --coverage-json, resolved against --root -- exercises the
    # relative-path branch main() itself resolves before validation.
    exit_code = gate.main(["--root", str(tmp_path), "--coverage-json", "coverage.json"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "patch-coverage-gap" in err
    assert "issue #1568" in err


def test_main_prints_honoured_waivers(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = ".github/scripts/gitapex_gate_zzz_waived.py"
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1  # patch-coverage: WAIVED: defensive default\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.coverage.run]\nsource = [".github/scripts"]\n', encoding="utf-8")
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps({"files": {path: {"executed_lines": [], "missing_lines": [1]}}}), encoding="utf-8"
    )
    diff_text = _diff(path, [1])
    monkeypatch.setattr(sys, "stdin", _FakeStdin(diff_text.encode()))
    exit_code = gate.main(["--root", str(tmp_path), "--coverage-json", str(coverage_json)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "waived inline" in captured.err
    assert "OK: 1 in-scope file(s)" in captured.out
    assert "1 inline waiver(s) honoured" in captured.out


# --- defeat tests --------------------------------------------------------------


def test_defeat_a_test_file_that_exists_but_never_actually_ran_is_a_scan_error_not_a_pass(
    tmp_path: pathlib.Path,
) -> None:
    """An attacker (or an honest bug) could create an empty test file
    named exactly right to satisfy `resolve_existing_test_files` while
    never actually running against the source module at all. This must
    surface as a fail-closed ScanError (an ambiguous state), never as a
    silent 'covered' verdict -- confirmed here by supplying a coverage
    report with no entry for the source path even though its test file
    exists on disk."""
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_foo.py").write_text("def test_nothing():\n    pass\n", encoding="utf-8")
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(json.dumps({"files": {}}), encoding="utf-8")
    with pytest.raises(gate.ScanError, match="no entry in the coverage report"):
        gate.find_violations({path: {1}}, ["skills/x/scripts"], tmp_path, coverage_json, 60)


def test_defeat_waiver_marker_inside_a_string_literal_is_not_honoured(tmp_path: pathlib.Path) -> None:
    """A source file could contain the literal waiver text inside an
    ordinary string (a docstring, a log message) without it being a real
    comment -- this must not clear a finding."""
    path = "skills/x/scripts/foo.py"
    (tmp_path / "skills" / "x" / "scripts").mkdir(parents=True)
    (tmp_path / path).write_text('x = "# patch-coverage: WAIVED: fake"\n', encoding="utf-8")
    violations, waived = gate.findings_for_file(path, {1}, [], {"files": {}}, tmp_path)
    assert waived == []
    assert len(violations) == 1


# --- .gitapex/ssot.json wiring -----------------------------------------------


def test_wired_into_local_preflight() -> None:
    checks = {check.gate_id: check for check in gitapex_gate_local_preflight.load_local_checks()}
    assert "patch-coverage" in checks
    check = checks["patch-coverage"]
    assert check.argv[-1].endswith("gitapex_gate_patch_coverage.py")
    assert check.stdin_argv is not None
    assert check.stdin_argv[-1] == "*.py"


# --- workflow wiring drift tests ---------------------------------------------


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW_NAME)


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW_NAME)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to(_WORKFLOW_NAME, "diff")


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags(_WORKFLOW_NAME, "--no-renames", "core.quotePath=false")

"""Regression suite for gitapex_check_branch_plan_reverified.py's own marker
detection. Runs the shipped script via subprocess, the same convention
test_gitapex_check_file_ownership_conflicts.py and
test_gitapex_check_canonical_governance_paths.py already use in this
directory -- the script is the thing under test, not a reimplementation
of it.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT = Path(__file__).parent / "gitapex_check_branch_plan_reverified.py"

_VALID_MARKER = "Re-verified: `planning-a-branch-from-an-issue` (2026-08-25T00:00:00Z)"


def run(body: str, extra_args: Sequence[str] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        input=body,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_passes_on_a_bare_marker_line() -> None:
    result = run(_VALID_MARKER)
    assert result.returncode == 0
    assert "PASS: re-verification marker found" in result.stdout


def test_passes_on_a_bulleted_marker_inside_a_larger_body() -> None:
    body = f"## Acceptance criteria\n\n(table here)\n\n- {_VALID_MARKER}\n"
    result = run(body)
    assert result.returncode == 0


def test_passes_case_insensitively() -> None:
    result = run("re-VERIFIED: `PLANNING-A-BRANCH-FROM-AN-ISSUE` (2026-08-25T00:00:00Z)")
    assert result.returncode == 0


def test_passes_without_the_optional_backticks() -> None:
    result = run("Re-verified: planning-a-branch-from-an-issue (2026-08-25T00:00:00Z)")
    assert result.returncode == 0


def test_passes_with_crlf_line_endings() -> None:
    body = f"Some prose.\r\n{_VALID_MARKER}\r\n"
    result = run(body)
    assert result.returncode == 0


def test_fails_on_no_marker_at_all() -> None:
    result = run("This is a still-draft ACM issue body with no marker.")
    assert result.returncode == 1
    assert "FAIL: no planning-a-branch-from-an-issue re-verification marker found" in result.stderr


def test_fails_on_empty_body() -> None:
    result = run("")
    assert result.returncode == 1


# Defeat cases: each is a body specifically shaped to try to slip past the
# regex -- an illustrative quote, a wrong skill name, and shape without
# real content -- rather than merely exercising the happy path above.


def test_fails_when_the_marker_is_only_quoted_inside_a_fenced_example() -> None:
    # A reviewer instructions doc (or a copy-pasted worked example inside a
    # real issue body) quoting this marker's own syntax must not be
    # misdetected as a genuine disclosure -- the identical false-positive
    # class hooks/gitapex_check_acm_present_or_waiver.py's own fence-stripping
    # was built to close for the ACM waiver line.
    body = f"Example marker syntax:\n\n```\n{_VALID_MARKER}\n```\n"
    result = run(body)
    assert result.returncode == 1


def test_fails_when_the_marker_is_only_quoted_via_4_space_indentation() -> None:
    # Found by an adversarial review round (issue #1306): a 4+ space
    # indented block is CommonMark/GFM's own "indented code block"
    # convention (this file's own module docstring's "one example" uses
    # exactly this style) -- an unbounded leading-whitespace match would
    # let this illustrative-quoting path bypass _strip_fences entirely,
    # even though the fenced-example case above is correctly caught.
    body = f"Here's an example of the marker format:\n\n    {_VALID_MARKER}\n\nNot a real disclosure.\n"
    result = run(body)
    assert result.returncode == 1


def test_fails_on_a_single_unpaired_backtick() -> None:
    # Found by the same adversarial review round: the skill-name backticks
    # must be a matched pair, not independently optional -- a stray
    # opening-only or closing-only backtick must not still match.
    result = run("Re-verified: `planning-a-branch-from-an-issue (2026-08-25T00:00:00Z)")
    assert result.returncode == 1
    result = run("Re-verified: planning-a-branch-from-an-issue` (2026-08-25T00:00:00Z)")
    assert result.returncode == 1


def test_fails_when_the_marker_names_a_different_skill() -> None:
    result = run("Re-verified: `some-other-skill` (2026-08-25T00:00:00Z)")
    assert result.returncode == 1


def test_fails_on_an_empty_parenthesized_value() -> None:
    result = run("Re-verified: `planning-a-branch-from-an-issue` ()")
    assert result.returncode == 1


def test_fails_on_whitespace_only_parenthesized_value() -> None:
    result = run("Re-verified: `planning-a-branch-from-an-issue` (   )")
    assert result.returncode == 1


def test_body_flag_reads_from_a_file(tmp_path: Path) -> None:
    body_file = tmp_path / "issue-body.md"
    body_file.write_text(_VALID_MARKER, encoding="utf-8")
    result = run("", extra_args=["--body", str(body_file)])
    assert result.returncode == 0


def test_body_flag_reports_error_for_a_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"
    result = run("", extra_args=["--body", str(missing)])
    assert result.returncode == 1
    assert "error: body file not found" in result.stderr


def test_body_flag_reports_error_for_a_directory(tmp_path: Path) -> None:
    # Found by an adversarial review round (issue #1306): --body pointed at
    # a directory used to raise an uncaught IsADirectoryError traceback
    # instead of this file's own established `error: ...` convention.
    result = run("", extra_args=["--body", str(tmp_path)])
    assert result.returncode == 1
    assert "error: could not read body file" in result.stderr
    assert "Traceback" not in result.stderr


def test_body_flag_reports_error_for_non_utf8_file(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_bytes(b"\xff\xfe bad")
    result = run("", extra_args=["--body", str(body_file)])
    assert result.returncode == 1
    assert "not valid UTF-8" in result.stderr
    assert "Traceback" not in result.stderr

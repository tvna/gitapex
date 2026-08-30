"""Regression suite for gitapex_check_task_commit_provenance.py.

Runs the shipped script via subprocess for its CLI-level behavior (the
same convention test_gitapex_check_branch_plan_reverified.py and
test_gitapex_check_canonical_governance_paths.py already use in this
directory -- the script is the thing under test, not a reimplementation of
it), and imports it directly (this directory is on pyproject.toml's
pythonpath/testpaths) for the scanner-load-failure seam, matching
hooks/gitapex_check_post_write_provenance.py's own `scanner_path` injection
point for the identical kind of test.

Issue #1477 (gate-proposal, retro #1475 repair 3): the primary regression
case reintroduces the original defect verbatim -- a Claude-Session URL
trailer appended to a commit message -- and confirms this gate fails
(FLAGGED) against it, then passes once the trailer is gone.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import gitapex_check_task_commit_provenance as checker

SCRIPT = Path(__file__).parent / "gitapex_check_task_commit_provenance.py"

# The original incident's own shape (issue #1477, retro #1475 repair 3):
# a Co-Authored-By trailer naming a model, plus a Claude-Session URL, both
# appended to a commit message rather than a PR body.
_UNDISCLOSED_TRAILER = "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01D2mFkS5rNiaNPVaZbsu9zy"

_CLEAN_MESSAGE = (
    "fix(parser): handle a trailing comma in the config array\n\nNo behavior change for the non-trailing-comma case."
)


def _nul_join(messages: Sequence[str]) -> str:
    """Build `git log --format=%B -z`-shaped input: each message followed by
    a NUL, matching git's own trailing-NUL-per-entry output shape."""
    return "".join(message + "\0" for message in messages)


def run(raw_input: str, extra_args: Sequence[str] = ()) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        input=raw_input,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_fails_when_a_commit_message_carries_the_original_undisclosed_trailer() -> None:
    # Issue #1477's own regression proof: reintroducing the exact defect
    # shape must fail before the fix, and this test is what confirms it
    # does -- ported forward, it also confirms the fix keeps failing on any
    # future reintroduction of the identical shape.
    result = run(_nul_join([_UNDISCLOSED_TRAILER]))
    assert result.returncode == 1
    assert "FLAGGED" in result.stderr
    assert "commit 1" in result.stderr


def test_passes_on_a_single_clean_commit_message() -> None:
    result = run(_nul_join([_CLEAN_MESSAGE]))
    assert result.returncode == 0
    assert "PASS: 1 commit message(s) scanned clean" in result.stdout


def test_passes_on_no_commits_in_range() -> None:
    result = run("")
    assert result.returncode == 0
    assert "PASS: no commits in range" in result.stdout


def test_flags_only_the_dirty_commit_among_several_clean_ones() -> None:
    messages = [_CLEAN_MESSAGE, _UNDISCLOSED_TRAILER, _CLEAN_MESSAGE]
    result = run(_nul_join(messages))
    assert result.returncode == 1
    assert "1 of 3 commit message(s)" in result.stderr
    assert "commit 2" in result.stderr
    assert "commit 1" not in result.stderr
    assert "commit 3" not in result.stderr


def test_flags_the_last_commit_in_a_multi_commit_range() -> None:
    # Defeat case: an off-by-one in commit indexing could silently misname
    # or drop the final entry in a range -- construct the boundary directly
    # rather than only exercising a hit in the middle.
    messages = [_CLEAN_MESSAGE, _CLEAN_MESSAGE, _UNDISCLOSED_TRAILER]
    result = run(_nul_join(messages))
    assert result.returncode == 1
    assert "commit 3" in result.stderr


def test_flags_every_dirty_commit_when_more_than_one_is_dirty() -> None:
    messages = [_UNDISCLOSED_TRAILER, _CLEAN_MESSAGE, _UNDISCLOSED_TRAILER]
    result = run(_nul_join(messages))
    assert result.returncode == 1
    assert "2 of 3 commit message(s)" in result.stderr
    assert "commit 1" in result.stderr
    assert "commit 3" in result.stderr


def test_truncates_the_reported_commit_list_beyond_the_cap() -> None:
    # Defeat case: a pathological task branch with many small WIP commits
    # (accumulated before step 6's own screening runs) must not produce an
    # unbounded report -- the total count is always exact, only the
    # per-commit detail is capped.
    dirty_count = checker._MAX_REPORTED_COMMITS + 3
    messages = [_UNDISCLOSED_TRAILER] * dirty_count
    result = run(_nul_join(messages))
    assert result.returncode == 1
    assert f"{dirty_count} of {dirty_count} commit message(s)" in result.stderr
    assert "... and 3 more flagged commit(s)" in result.stderr
    # Every shown commit index is within the cap; none beyond it leaks
    # through despite the truncation.
    assert f"commit {checker._MAX_REPORTED_COMMITS}" in result.stderr
    assert f"commit {checker._MAX_REPORTED_COMMITS + 1}" not in result.stderr


def test_truncates_the_reported_hit_list_within_one_commit() -> None:
    # Defeat case: a single commit message repeating the marker many times
    # (e.g. a copy-pasted block) must not blow up the report either. Each
    # line below produces exactly one "session URL" hit (a bare non-claude.ai
    # domain, so neither the "anthropic session domain" nor the
    # "model identifier" pattern also fires on the same line) -- so the hit
    # count equals the line count precisely, letting the assertion below
    # pin an exact overflow.
    hit_count = checker._MAX_REPORTED_HITS_PER_COMMIT + 2
    message = "\n".join(f"http://example.com/session_{i:03d}" for i in range(hit_count))
    result = run(_nul_join([message]))
    assert result.returncode == 1
    assert "... and 2 more hit(s)" in result.stderr


def test_multiline_commit_message_is_not_split_at_its_own_newlines() -> None:
    # Defeat case: a naive newline-based splitter (rather than the actual
    # NUL delimiter git emits) would fragment this single multi-line
    # message into several bogus "commits" -- confirm the real message
    # boundary (NUL) is what is honored, not an internal line break.
    multiline_clean = "feat(x): add the thing\n\nBody paragraph one.\n\nBody paragraph two.\n"
    result = run(_nul_join([multiline_clean, _UNDISCLOSED_TRAILER]))
    assert result.returncode == 1
    assert "2 of 2" not in result.stderr
    assert "1 of 2 commit message(s)" in result.stderr
    assert "commit 2" in result.stderr


def test_does_not_false_positive_on_a_bare_model_tag_with_no_corroborating_context() -> None:
    # A commit legitimately discussing a pinned model id (e.g. an eval
    # config comment) must not be blocked -- this is the same
    # corroborating-context rule gitapex_scan_provenance.py already applies
    # to PR/issue bodies, unchanged here; this test pins that this gate
    # does not silently widen it into a bare-substring match.
    message = "chore(evals): bump the pinned eval model to claude-sonnet-4.6"
    result = run(_nul_join([message]))
    assert result.returncode == 0


def test_does_not_false_positive_on_prose_describing_the_convention() -> None:
    # A commit message that merely *discusses* the disclosure convention
    # (no session URL, no claude.ai link, no build/agent tag) must not trip
    # this gate -- only genuinely corroborated markers are unconditionally
    # flagged (session URL / claude.ai domain / build-tag), matching the
    # underlying scanner's own documented scope.
    message = "docs(contributing): clarify that commit messages are always in scope for provenance review"
    result = run(_nul_join([message]))
    assert result.returncode == 0


def test_trailing_nul_produces_no_phantom_empty_commit() -> None:
    # git log -z always terminates the LAST entry with a NUL too (not just
    # a separator between entries) -- confirm this does not manifest as a
    # phantom extra "commit" in the count.
    result = run(_CLEAN_MESSAGE + "\0")
    assert result.returncode == 0
    assert "PASS: 1 commit message(s) scanned clean" in result.stdout


def test_input_with_no_trailing_nul_is_still_read_as_one_commit() -> None:
    result = run(_CLEAN_MESSAGE)
    assert result.returncode == 0
    assert "PASS: 1 commit message(s) scanned clean" in result.stdout


def test_messages_flag_reads_from_a_file(tmp_path: Path) -> None:
    messages_file = tmp_path / "messages.bin"
    messages_file.write_bytes(_nul_join([_CLEAN_MESSAGE]).encode("utf-8"))
    result = run("", extra_args=["--messages", str(messages_file)])
    assert result.returncode == 0


def test_messages_flag_reports_error_for_a_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.bin"
    result = run("", extra_args=["--messages", str(missing)])
    assert result.returncode == 2
    assert "error: messages file not found" in result.stderr


def test_messages_flag_reports_error_for_non_utf8_file(tmp_path: Path) -> None:
    messages_file = tmp_path / "messages.bin"
    messages_file.write_bytes(b"\xff\xfe bad")
    result = run("", extra_args=["--messages", str(messages_file)])
    assert result.returncode == 2
    assert "not valid UTF-8" in result.stderr
    assert "Traceback" not in result.stderr


# --- direct-import tests: the scanner-load-failure seam -------------------
# Matching hooks/gitapex_check_post_write_provenance.py's own test
# convention for the identical reuse pattern -- this directory is on
# pyproject.toml's pythonpath/testpaths, so the module is imported directly
# rather than exercised only through subprocess, for the one seam that
# genuinely needs dependency injection (there is no CLI flag for the
# scanner's own location, deliberately -- see the module's own docstring;
# adding one purely for this test would be a feature this issue never
# asked for).


def test_load_provenance_scanner_fails_loudly_when_the_file_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.py"
    try:
        checker.load_provenance_scanner(missing)
        raise AssertionError("expected ScannerLoadError")
    except checker.ScannerLoadError as error:
        assert "was not found" in str(error)


def test_load_provenance_scanner_fails_loudly_on_a_non_scanner_module(tmp_path: Path) -> None:
    # A file that exists and imports cleanly but is not the scanner (no
    # callable scan()) must still fail loudly, not crash with an
    # AttributeError once find_flagged_commits calls scan() on it.
    decoy = tmp_path / "decoy.py"
    decoy.write_text("VALUE = 1\n", encoding="utf-8")
    try:
        checker.load_provenance_scanner(decoy)
        raise AssertionError("expected ScannerLoadError")
    except checker.ScannerLoadError as error:
        assert "no callable scan()" in str(error)


def test_load_provenance_scanner_fails_loudly_on_a_broken_module(tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    try:
        checker.load_provenance_scanner(broken)
        raise AssertionError("expected ScannerLoadError")
    except checker.ScannerLoadError as error:
        assert "failed to import" in str(error)


def test_load_provenance_scanner_loads_the_real_bundled_scanner() -> None:
    # Confirms the default (no override) resolution path actually reaches
    # the real, bundled scanner -- not only that the override seam works.
    scanner = checker.load_provenance_scanner()
    assert callable(scanner.scan)


def test_split_commit_messages_drops_only_empty_entries() -> None:
    assert checker.split_commit_messages("a\0b\0") == ["a", "b"]
    assert checker.split_commit_messages("a\0\0b\0") == ["a", "b"]
    assert checker.split_commit_messages("") == []
    assert checker.split_commit_messages("\0") == []


def test_find_flagged_commits_reports_1_indexed_positions() -> None:
    scanner = checker.load_provenance_scanner()
    flagged = checker.find_flagged_commits([_CLEAN_MESSAGE, _UNDISCLOSED_TRAILER], scanner)
    assert [index for index, _ in flagged] == [2]

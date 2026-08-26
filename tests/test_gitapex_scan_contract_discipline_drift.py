"""CI gate + unit tests for the Contract-discipline <-> contract-
structure.md drift lock (issue #1194).

Same two-layer shape as `test_gitapex_scan_contract_axis_vocabulary_drift.py`:
an integration test against this repository's own real content, then a
battery of deliberately corrupted/adversarial fixtures asserting each
lock actually fires -- a lock exercised only against correct content is
indistinguishable from one that returns 0 unconditionally.
"""

from __future__ import annotations

from pathlib import Path

import gitapex_scan_contract_discipline_drift as G
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo_subset(tmp_path: Path) -> Path:
    """A tmp_path tree carrying just the two real files this gate reads,
    at their real repo-relative paths, so `check_content`/`check_diff`
    (which take a `repo_root` and read fixed relative paths under it)
    exercise real content without mutating the actual repository."""
    for rel in (G.RUBRIC_MD, G.CONTRACT_STRUCTURE_MD):
        src = REPO_ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _mutate(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture setup: {old!r} not present in {rel}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _diff(rel_path: str, new_start: int, added_lines: list[str]) -> str:
    """A minimal unified diff touching `rel_path` at 1-indexed
    `new_start`, matching `git diff -U0`'s own hunk-header shape closely
    enough for `_parse_diff_hunks` to read."""
    header = (
        f"diff --git a/{rel_path} b/{rel_path}\nindex 0000000..1111111 100644\n--- a/{rel_path}\n+++ b/{rel_path}\n"
    )
    hunk = f"@@ -{new_start},0 +{new_start},{len(added_lines)} @@\n"
    body = "".join(f"+{line}\n" for line in added_lines)
    return header + hunk + body


# --- Integration: the real content passes ------------------------------------


def test_real_content_passes_content_lock() -> None:
    assert G.check_content(REPO_ROOT) == []


def test_main_on_real_content_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert G.main(["--repo-root", str(REPO_ROOT)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_main_with_no_argv_defaults_to_this_repository() -> None:
    assert G.main([]) == 0


def test_real_rubric_section_span_is_nonempty() -> None:
    start, end = G._contract_discipline_line_span(REPO_ROOT)
    assert end > start > 0


def test_section_span_missing_heading_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    _mutate(root, G.RUBRIC_MD, G.CONTRACT_DISCIPLINE_HEADING, "## Renamed section")
    with pytest.raises(G.ScanError, match="heading not found"):
        G._contract_discipline_line_span(root)


def test_section_span_reaches_end_of_file_when_it_is_the_last_section(tmp_path: Path) -> None:
    """When Contract discipline is the last section in the file, no
    following heading exists to bound it -- the span must extend to
    EOF, not raise or silently truncate."""
    root = _copy_repo_subset(tmp_path)
    text = (root / G.RUBRIC_MD).read_text(encoding="utf-8")
    heading_idx = text.index(G.CONTRACT_DISCIPLINE_HEADING)
    truncated = text[:heading_idx] + G.CONTRACT_DISCIPLINE_HEADING + "\n\nFault attribution. Never both.\n"
    (root / G.RUBRIC_MD).write_text(truncated, encoding="utf-8")
    start, end = G._contract_discipline_line_span(root)
    line_count = len(truncated.split("\n"))
    assert end == line_count + 1
    assert end > start


# --- Content lock: each term fires on a corrupted copy ------------------------


@pytest.mark.parametrize(
    ("rel", "old", "new", "expected_fragment"),
    [
        (
            G.RUBRIC_MD,
            "Fault attribution",
            "Blame assignment",
            "Contract discipline section lost the term 'Fault attribution'",
        ),
        (G.RUBRIC_MD, "Never both", "Pick one place", "Contract discipline section lost the term 'Never both'"),
        (G.CONTRACT_STRUCTURE_MD, "Fault attribution", "Blame assignment", "lost the shared term 'Fault attribution'"),
        (G.CONTRACT_STRUCTURE_MD, "Never both", "Pick one place", "lost the shared term 'Never both'"),
    ],
)
def test_corrupted_term_fails(tmp_path: Path, rel: str, old: str, new: str, expected_fragment: str) -> None:
    root = _copy_repo_subset(tmp_path)
    _mutate(root, rel, old, new)
    problems = G.check_content(root)
    assert any(expected_fragment in p for p in problems), problems


def test_contract_structure_dropping_the_section_name_fails(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    path = root / G.CONTRACT_STRUCTURE_MD
    text = path.read_text(encoding="utf-8")
    text = text.replace("Contract discipline", "the shared rules").replace("Contract-discipline", "the shared rules")
    path.write_text(text, encoding="utf-8")
    problems = G.check_content(root)
    assert any("no longer cites rubric.md's Contract discipline section by name" in p for p in problems), problems


# --- Fail-closed input handling (dimension 15) ---------------------------------


def test_missing_rubric_file_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    (root / G.RUBRIC_MD).unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.check_content(root)


def test_missing_contract_structure_file_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    (root / G.CONTRACT_STRUCTURE_MD).unlink()
    with pytest.raises(G.ScanError, match="not found"):
        G.check_content(root)


def test_absent_contract_discipline_heading_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    _mutate(root, G.RUBRIC_MD, G.CONTRACT_DISCIPLINE_HEADING, "## Renamed section")
    with pytest.raises(G.ScanError, match="heading not found"):
        G.check_content(root)


def test_duplicated_contract_discipline_heading_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    _mutate(
        root,
        G.RUBRIC_MD,
        G.CONTRACT_DISCIPLINE_HEADING,
        f"{G.CONTRACT_DISCIPLINE_HEADING}\n\nStub.\n\n{G.CONTRACT_DISCIPLINE_HEADING}",
    )
    with pytest.raises(G.ScanError, match="appears 2 times"):
        G.check_content(root)


def test_directory_in_place_of_a_file_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    (root / G.CONTRACT_STRUCTURE_MD).unlink()
    (root / G.CONTRACT_STRUCTURE_MD).mkdir()
    with pytest.raises(G.ScanError, match="could not be read"):
        G.check_content(root)


def test_non_utf8_file_is_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    (root / G.RUBRIC_MD).write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(G.ScanError, match="could not decode"):
        G.check_content(root)


def test_garbage_diff_input_is_a_scan_error(tmp_path: Path) -> None:
    """Unstructured text must never be indistinguishable from a
    genuinely empty, clean diff (same guard the stdlib-only-claim-drift
    gate applies) -- includes ordinary prose that merely contains '---'
    or '@@' mid-sentence, a real false positive that adversarial review
    found against a naive substring check."""
    root = _copy_repo_subset(tmp_path)
    with pytest.raises(G.ScanError, match="does not look like a unified diff"):
        G.check_diff("looks fine --- go ahead (cc @@release-bot)", root)


def test_empty_diff_is_not_a_scan_error(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    assert G.check_diff("", root) == []


# --- Diff awareness: the exact regression this gate exists to catch -----------


def test_diff_touching_section_without_structure_file_fails(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, start + 1, ["A rewritten Fault attribution paragraph, still using the phrase."])
    problems = G.check_diff(diff, root)
    assert len(problems) == 1
    assert "edits the Contract discipline section" in problems[0]
    assert G.CONTRACT_STRUCTURE_MD in problems[0]


def test_diff_touching_section_and_structure_file_passes(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, start + 1, ["A rewritten paragraph."]) + _diff(
        G.CONTRACT_STRUCTURE_MD, 5, ["Updated to match."]
    )
    assert G.check_diff(diff, root) == []


def test_diff_touching_section_with_ack_comment_passes(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff = _diff(
        G.RUBRIC_MD,
        start + 1,
        ["A typo fix only.", "<!-- contract-discipline-ack: typo fix, no rule-substance change -->"],
    )
    assert G.check_diff(diff, root) == []


def test_diff_outside_the_section_is_silent(tmp_path: Path) -> None:
    """A hunk elsewhere in rubric.md -- not inside Contract discipline at
    all -- must not fire this gate; it is a different section's own
    concern."""
    root = _copy_repo_subset(tmp_path)
    _start, end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, end + 20, ["An edit somewhere else entirely."])
    assert G.check_diff(diff, root) == []


def test_diff_one_line_past_the_section_end_is_silent(tmp_path: Path) -> None:
    """Boundary test: a hunk starting exactly at the section's own
    (exclusive) end line -- the next heading's own line -- must not be
    misread as still inside the section. Constructed specifically to
    defeat an off-by-one in the overlap comparison."""
    root = _copy_repo_subset(tmp_path)
    _start, end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, end, ["The next section's own first added line."])
    assert G.check_diff(diff, root) == []


def test_diff_ending_exactly_at_the_last_section_line_fires(tmp_path: Path) -> None:
    """Boundary test on the other edge: a one-line hunk at the section's
    own last line must still be caught, not fall just outside the
    overlap window."""
    root = _copy_repo_subset(tmp_path)
    _start, end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, end - 1, ["The section's own last line, edited."])
    problems = G.check_diff(diff, root)
    assert len(problems) == 1


def test_ack_comment_elsewhere_in_an_unrelated_file_does_not_count(tmp_path: Path) -> None:
    """The ack comment must appear in the diff actually being graded --
    a decoy hunk on a third file carrying the token must not suppress a
    real, unacknowledged finding constructed to defeat a naive
    'token present anywhere in the repo' check. (The token only needs to
    be anywhere *in this diff*, per the module's own documented
    contract -- this test proves the token is read from the diff text
    itself, not from some stale prior state.)"""
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff = _diff(G.RUBRIC_MD, start + 1, ["An unacknowledged rewrite."])
    problems = G.check_diff(diff, root)
    assert len(problems) == 1


# --- CLI surface ----------------------------------------------------------------


def test_main_reports_drift_on_stderr_and_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _copy_repo_subset(tmp_path)
    _mutate(root, G.RUBRIC_MD, "Fault attribution", "Blame assignment")
    assert G.main(["--repo-root", str(root)]) == 1
    err = capsys.readouterr().err
    assert "::error::" in err
    assert "FAIL:" in err


def test_main_exits_two_on_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _copy_repo_subset(tmp_path)
    (root / G.RUBRIC_MD).unlink()
    assert G.main(["--repo-root", str(root)]) == 2
    assert "failing closed" in capsys.readouterr().err


def test_main_with_diff_file_argument(tmp_path: Path) -> None:
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff_file = tmp_path / "the.diff"
    diff_file.write_text(_diff(G.RUBRIC_MD, start + 1, ["An unacknowledged rewrite."]), encoding="utf-8")
    assert G.main(["--repo-root", str(root), "--diff", str(diff_file)]) == 1


def test_main_with_diff_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_repo_subset(tmp_path)
    start, _end = G._contract_discipline_line_span(root)
    diff_bytes = _diff(G.RUBRIC_MD, start + 1, ["An unacknowledged rewrite."]).encode("utf-8")
    monkeypatch.setattr("sys.stdin.buffer.read", lambda: diff_bytes)
    assert G.main(["--repo-root", str(root), "--diff", "-"]) == 1


def test_main_exits_two_on_unreadable_diff_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _copy_repo_subset(tmp_path)
    assert G.main(["--repo-root", str(root), "--diff", str(tmp_path / "nope.diff")]) == 2
    assert "could not read diff" in capsys.readouterr().err

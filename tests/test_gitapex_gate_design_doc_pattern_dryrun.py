"""Tests for the design-doc pattern dry-run gate
(.github/scripts/gitapex_gate_design_doc_pattern_dryrun.py).

Issue #1507 (retro #1504 repair 3, refs #1499): a design doc's first draft
specified resolving a fixture's declared "Step N" label via a literal-text
search for the string "Step N:", which a dispatched adversarial-review
subagent found matches nothing in the real repository corpus (every skill
uses bare "1.", "2." numbering). This gate automates that dry run so a
zero-match stated pattern is caught mechanically instead of depending on a
reviewer's own initiative to think to check.
"""

from __future__ import annotations

from pathlib import Path

import gitapex_gate_design_doc_pattern_dryrun as gate
import pytest
from conftest import FakeStdin as _FakeStdin

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The exact defective wording issue #1507's own body attributes to the
# design doc's first draft, reconstructed for this regression test (the
# defective text itself was never committed -- fixed in the same commit
# that introduced the design doc, per PR #1499's own history).
_ORIGINAL_DEFECTIVE_PARAGRAPH = (
    "A `Step N` ordinal is resolved by a literal-text search for the "
    'string "Step N:" directly under a `## Procedure` or `## Steps` '
    "heading.\n"
)

# The real, already-fixed paragraph from
# docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-item-coverage-design.md
# (item 6's own Design section), copied verbatim -- proving no false
# positive against this repository's own real, already-reviewed content,
# the same "verify against real content before shipping" bar this
# repository's gate family applies throughout.
_REAL_FIXED_PARAGRAPH = (
    "Positional resolution is the only viable reading: a fresh adversarial "
    "review of this document (dispatched during elicitation) confirmed no "
    "skill in this repository writes a Procedure/Steps item's own text as "
    'literal "Step N:" -- every skill uses bare "1.", "2." numbering, with '
    '"Step N" phrasing appearing only in unrelated cross-reference prose '
    'elsewhere in the file. A literal-text-search reading of "Step N" '
    "would therefore resolve against nothing in any current skill; this "
    "document specifies positional resolution explicitly rather than "
    "leaving the choice implicit.\n"
)

_NO_CUE_PARAGRAPH = 'This paragraph merely quotes "Step N" as an example label, nothing more.\n'


def test_find_candidate_patterns_detects_hyphen_space_form() -> None:
    candidates = gate.find_candidate_patterns(_ORIGINAL_DEFECTIVE_PARAGRAPH)
    assert [c.pattern for c in candidates] == ["Step N:"]


def test_find_candidate_patterns_detects_fully_hyphenated_form() -> None:
    text = 'Resolved via a literal-text-search reading of "Step N:" in the file.\n'
    candidates = gate.find_candidate_patterns(text)
    assert [c.pattern for c in candidates] == ["Step N:"]


def test_find_candidate_patterns_ignores_paragraph_with_no_search_intent_cue() -> None:
    assert gate.find_candidate_patterns(_NO_CUE_PARAGRAPH) == []


def test_find_candidate_patterns_suppresses_a_paragraph_disclosing_rejection() -> None:
    """The real, already-fixed design-doc paragraph states the
    zero-match fact itself, in prose, as the reason it rejected the
    literal-text-search reading -- it must not be re-flagged as a live
    proposal."""
    assert gate.find_candidate_patterns(_REAL_FIXED_PARAGRAPH) == []


def test_dry_run_corpus_finds_a_live_match(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. Do the Step N: thing.\n", encoding="utf-8")
    matches = gate.dry_run_corpus("Step N:", tmp_path, gate._DEFAULT_CORPUS_GLOB)
    assert len(matches) == 1


def test_dry_run_corpus_case_insensitive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. STEP n: do the thing.\n", encoding="utf-8")
    matches = gate.dry_run_corpus("Step N:", tmp_path, gate._DEFAULT_CORPUS_GLOB)
    assert len(matches) == 1


def test_dry_run_corpus_returns_empty_when_pattern_matches_nothing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. Bare numbering, no ordinal label.\n", encoding="utf-8")
    matches = gate.dry_run_corpus("Step N:", tmp_path, gate._DEFAULT_CORPUS_GLOB)
    assert matches == []


def test_find_zero_match_candidates_flags_the_original_defect(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. Bare numbering only.\n", encoding="utf-8")
    zero_match = gate.find_zero_match_candidates(_ORIGINAL_DEFECTIVE_PARAGRAPH, tmp_path)
    assert [c.pattern for c in zero_match] == ["Step N:"]


def test_find_zero_match_candidates_passes_when_pattern_has_a_live_match(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. Do the Step N: thing.\n", encoding="utf-8")
    zero_match = gate.find_zero_match_candidates(_ORIGINAL_DEFECTIVE_PARAGRAPH, tmp_path)
    assert zero_match == []


def test_find_zero_match_candidates_dedupes_repeated_pattern(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("## Procedure\n\n1. Bare numbering only.\n", encoding="utf-8")
    text = _ORIGINAL_DEFECTIVE_PARAGRAPH + "\n\n" + _ORIGINAL_DEFECTIVE_PARAGRAPH
    zero_match = gate.find_zero_match_candidates(text, tmp_path)
    assert len(zero_match) == 1


def test_has_disclosure_marker_true() -> None:
    text = "Some prose.\n\ncorpus-dryrun-disclosure: WAIVED: owner approved on 2026-08-30\n"
    assert gate.has_disclosure_marker(text)


def test_has_disclosure_marker_false() -> None:
    assert not gate.has_disclosure_marker("Some ordinary prose with no marker.\n")


# --- Live-repository regression tests (real corpus, real design-doc text) ---


def test_live_corpus_has_zero_matches_for_the_historical_defect_pattern() -> None:
    """Ground truth this whole gate exists to catch, re-verified live
    rather than assumed: literal "Step N:" truly matches nothing under
    this repository's real skills/ tree today."""
    matches = gate.dry_run_corpus("Step N:", _REPO_ROOT, gate._DEFAULT_CORPUS_GLOB)
    assert matches == []


def test_live_gate_flags_a_reintroduced_instance_of_the_original_defect() -> None:
    """Proof method from issue #1507's own Acceptance Criteria Map:
    confirm the check fails against a reintroduced instance of the
    original defect, using this repository's real live corpus."""
    zero_match = gate.find_zero_match_candidates(_ORIGINAL_DEFECTIVE_PARAGRAPH, _REPO_ROOT)
    assert [c.pattern for c in zero_match] == ["Step N:"]


def test_live_gate_does_not_false_positive_on_the_real_merged_design_doc_text() -> None:
    """...then passes: the real, already-fixed paragraph must not be
    flagged against this repository's real live corpus either."""
    zero_match = gate.find_zero_match_candidates(_REAL_FIXED_PARAGRAPH, _REPO_ROOT)
    assert zero_match == []


# --- CLI (main()) tests ---


def test_main_stdin_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_NO_CUE_PARAGRAPH.encode("utf-8")))
    exit_code = gate.main(["--repo-root", str(_REPO_ROOT)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_stdin_fail(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_ORIGINAL_DEFECTIVE_PARAGRAPH.encode("utf-8")))
    exit_code = gate.main(["--repo-root", str(_REPO_ROOT)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "Step N:" in err


def test_main_stdin_undecodable_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    exit_code = gate.main(["--repo-root", str(_REPO_ROOT)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_diff_added_file_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    added = tmp_path / "added.md"
    added.write_text(_NO_CUE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(added), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_diff_added_file_fail_against_real_corpus(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    added = tmp_path / "added.md"
    added.write_text(_ORIGINAL_DEFECTIVE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(added), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err and "Step N:" in err


def test_main_diff_added_missing_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = gate.main(["--diff-added", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_diff_added_undecodable_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    added = tmp_path / "added.md"
    added.write_bytes(b"\xff\xfe bad")
    exit_code = gate.main(["--diff-added", str(added)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(added) in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_body_missing_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    added = tmp_path / "added.md"
    added.write_text(_NO_CUE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(added), "--body", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_waiver_in_diff_added_suppresses_a_zero_match_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    added = tmp_path / "added.md"
    added.write_text(
        _ORIGINAL_DEFECTIVE_PARAGRAPH + "\ncorpus-dryrun-disclosure: WAIVED: intentional, no live target yet\n",
        encoding="utf-8",
    )
    exit_code = gate.main(["--diff-added", str(added), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_waiver_in_body_suppresses_a_zero_match_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The waiver marker can live in either source -- matching this
    repository's own established `<name>: WAIVED: <reason>` convention,
    which accepts the marker anywhere in the combined disclosure corpus."""
    added = tmp_path / "added.md"
    added.write_text(_ORIGINAL_DEFECTIVE_PARAGRAPH, encoding="utf-8")
    body = tmp_path / "body.md"
    body.write_text("corpus-dryrun-disclosure: WAIVED: owner approved in review\n", encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(added), "--body", str(body), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_body_alone_never_triggers_pattern_detection(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A PR body is not design-doc prose -- a stated pattern living only
    in the body (never in the diff-added design-doc text) must not be
    scanned for candidates at all."""
    added = tmp_path / "added.md"
    added.write_text(_NO_CUE_PARAGRAPH, encoding="utf-8")
    body = tmp_path / "body.md"
    body.write_text(_ORIGINAL_DEFECTIVE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(added), "--body", str(body), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_multiple_diff_added_files_are_all_scanned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = tmp_path / "first.md"
    first.write_text(_NO_CUE_PARAGRAPH, encoding="utf-8")
    second = tmp_path / "second.md"
    second.write_text(_ORIGINAL_DEFECTIVE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(["--diff-added", str(first), "--diff-added", str(second), "--repo-root", str(_REPO_ROOT)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err and "Step N:" in err


def test_main_custom_corpus_glob(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    (other_dir / "notes.md").write_text("Do the Step N: thing.\n", encoding="utf-8")
    added = tmp_path / "added.md"
    added.write_text(_ORIGINAL_DEFECTIVE_PARAGRAPH, encoding="utf-8")
    exit_code = gate.main(
        [
            "--diff-added",
            str(added),
            "--repo-root",
            str(tmp_path),
            "--corpus-glob",
            "elsewhere/*.md",
        ]
    )
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out

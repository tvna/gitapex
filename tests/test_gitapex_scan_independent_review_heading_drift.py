"""Tests for the independent-review-pending marker drift gate
(.github/scripts/gitapex_scan_independent_review_heading_drift.py).

The final test is the gate itself: the repository's real target files must
be drift-free. The rest unit-test the spec-driven detector with fixtures,
built directly against the two real `MarkerSpec` instances
(`_INDEPENDENT_REVIEW_HEADING`, `_MERGE_GATE_NOTE`) rather than synthetic
ones -- this file tracks whichever specs the gate script actually defines.
"""

from __future__ import annotations

import pathlib

import gitapex_scan_independent_review_heading_drift as drift
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_HEADING_SPEC = drift._INDEPENDENT_REVIEW_HEADING
_NOTE_SPEC = drift._MERGE_GATE_NOTE

# skills/drafting-a-pr-to-merge/SKILL.md: a Markdown target of the heading
# spec. .gitapex/ssot.json: that spec's one non-Markdown target -- used to
# exercise the Markdown-only HTML-comment/fence stripping on the right kind
# of target.
_MARKDOWN_TARGET, _MARKDOWN_TARGET_IS_MD = _HEADING_SPEC.targets[0]
_NON_MARKDOWN_TARGET, _NON_MARKDOWN_TARGET_IS_MD = _HEADING_SPEC.targets[2]
assert _MARKDOWN_TARGET_IS_MD is True
assert _NON_MARKDOWN_TARGET_IS_MD is False


def _write_clean_fixture(root: pathlib.Path) -> None:
    # A target file can belong to more than one spec (e.g.
    # `.github/PULL_REQUEST_TEMPLATE.md` carries both the heading spec's
    # and the merge-gate-note spec's canonical text) -- collect every
    # canonical text a given path must carry before writing it once, so a
    # later spec's write does not clobber an earlier spec's text on a
    # shared target.
    canonical_texts_by_path: dict[pathlib.Path, list[str]] = {}
    for spec in drift._MARKER_SPECS:
        for relative, _is_markdown in spec.targets:
            canonical_texts_by_path.setdefault(relative, []).append(spec.canonical_text)
    for relative, texts in canonical_texts_by_path.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n\n".join(f"some prose\n\n{text}\n\nmore prose" for text in texts)
        path.write_text(body + "\n", encoding="utf-8")


def test_clean_fixture_has_no_drift(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    assert drift.find_drift(tmp_path) == []


def test_missing_canonical_text_is_reported(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text("no tracked text here at all\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert str(_MARKDOWN_TARGET) in findings[0]
    assert _HEADING_SPEC.canonical_text in findings[0]


def test_every_target_file_is_independently_checked(tmp_path: pathlib.Path) -> None:
    # Empty root -- none of the target files exist at all: one finding per
    # (spec, target) pair across both specs.
    findings = drift.find_drift(tmp_path)
    total_targets = sum(len(spec.targets) for spec in drift._MARKER_SPECS)
    assert len(findings) == total_targets


def test_missing_target_file_fails_closed(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).unlink()
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "file not found" in findings[0]


def test_undecodable_target_file_fails_closed_not_skipped(tmp_path: pathlib.Path) -> None:
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_bytes(b"\xff\xfe bad")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "could not read" in findings[0]


def test_legacy_text_alone_is_reported_as_both_missing_and_stale(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression (deterministic-gate-quality review, issue #1343): the
    # first drafted version of this gate checked only "is the canonical
    # text present", so a file carrying a retired heading and nothing else
    # read as clean-ish (one finding: canonical text missing) instead of
    # also flagging the retired text itself. A file with only legacy text
    # is missing the canonical marker AND still carries the retired one --
    # both must be reported.
    #
    # Uses a locally constructed, monkeypatched-in spec whose legacy text
    # does NOT contain its own canonical text as a substring. The real
    # `_HEADING_SPEC`'s legacy text ("Step 8 independent review verdict")
    # does contain its canonical text ("Independent review verdict") as a
    # substring, so a file carrying only that real legacy text already
    # satisfies the canonical-text presence check trivially and would not
    # exercise this "both missing and stale" combination -- see
    # test_real_legacy_heading_text_also_satisfies_canonical_substring_check
    # below for that (correct, not a bug) real-world case.
    spec = drift.MarkerSpec(
        name="a synthetic marker",
        canonical_text="brand new marker",
        legacy_texts=("totally different retired marker",),
        targets=((_MARKDOWN_TARGET, True),),
    )
    monkeypatch.setattr(drift, "_MARKER_SPECS", (spec,))
    path = tmp_path / _MARKDOWN_TARGET
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"## {spec.legacy_texts[0]}\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 2
    assert any("does not carry" in f for f in findings)
    assert any("still carries a retired form" in f for f in findings)


def test_real_legacy_heading_text_also_satisfies_canonical_substring_check(tmp_path: pathlib.Path) -> None:
    # Documents a real property of the production spec's own string pair,
    # not a bug: `_HEADING_SPEC`'s legacy text ("Step 8 independent review
    # verdict") contains its own canonical text ("Independent review
    # verdict") as a case-insensitive substring, so a file carrying ONLY
    # the legacy heading already reads as carrying the canonical text too.
    # The migration-incomplete finding still fires (the actionable
    # signal); a separate "canonical text missing" finding does not,
    # because that would be false -- the string genuinely is there,
    # embedded in the retired heading.
    _write_clean_fixture(tmp_path)
    legacy_text = _HEADING_SPEC.legacy_texts[0]
    (tmp_path / _MARKDOWN_TARGET).write_text(f"## {legacy_text}\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "still carries a retired form" in findings[0]


def test_legacy_text_alongside_canonical_marker_is_reported(tmp_path: pathlib.Path) -> None:
    # The one-directional-check gap itself: BOTH the canonical text and a
    # retired heading text present in the same file (an incomplete
    # migration that left the old text behind) must not read as clean just
    # because the new text is also there.
    _write_clean_fixture(tmp_path)
    legacy_text = _HEADING_SPEC.legacy_texts[0]
    (tmp_path / _MARKDOWN_TARGET).write_text(
        f"## {_HEADING_SPEC.canonical_text}\n\n## {legacy_text}\n", encoding="utf-8"
    )
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "still carries a retired form" in findings[0]
    assert str(_MARKDOWN_TARGET) in findings[0]


def test_marker_inside_html_comment_on_markdown_target_does_not_count_as_live(tmp_path: pathlib.Path) -> None:
    # A Markdown-target marker hidden inside an HTML comment renders as
    # nothing at all on GitHub -- dead text, not live prose -- so it must
    # not satisfy the presence check.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(
        f"prose\n\n<!--\n{_HEADING_SPEC.canonical_text}\n-->\n\nmore prose\n", encoding="utf-8"
    )
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "does not carry" in findings[0]


def test_marker_inside_fenced_block_on_markdown_target_does_not_count_as_live(tmp_path: pathlib.Path) -> None:
    # Same reasoning as the HTML-comment case, for a fenced code block --
    # an illustrative example, not a live section.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(
        f"prose\n\n```\n{_HEADING_SPEC.canonical_text}\n```\n\nmore prose\n", encoding="utf-8"
    )
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "does not carry" in findings[0]


def test_marker_inside_html_comment_on_non_markdown_target_still_counts(tmp_path: pathlib.Path) -> None:
    # HTML-comment/fence stripping is Markdown-only (module docstring): a
    # non-Markdown target (e.g. ssot.json) has no such convention, so a
    # literal `<!-- ... -->`-shaped substring in its own text is not
    # special-cased away -- it is searched as plain text, unchanged.
    _write_clean_fixture(tmp_path)
    (tmp_path / _NON_MARKDOWN_TARGET).write_text(
        f"prose <!-- {_HEADING_SPEC.canonical_text} --> more\n", encoding="utf-8"
    )
    assert drift.find_drift(tmp_path) == []


def test_canonical_text_with_different_casing_is_not_flagged_as_drift(tmp_path: pathlib.Path) -> None:
    # Regression: a second review round found the substring search was
    # case-sensitive, where the sibling gate's own detection regex is
    # `re.IGNORECASE`. A same-meaning casing change must not read as
    # missing.
    _write_clean_fixture(tmp_path)
    (tmp_path / _MARKDOWN_TARGET).write_text(f"## {_HEADING_SPEC.canonical_text.upper()}\n", encoding="utf-8")
    assert drift.find_drift(tmp_path) == []


def test_legacy_text_with_different_casing_is_still_caught(tmp_path: pathlib.Path) -> None:
    # The other direction of the same case-sensitivity regression: an
    # incomplete migration recorded in a different case must still be
    # caught, not silently cleared by a case-sensitive comparison.
    _write_clean_fixture(tmp_path)
    legacy_text = _HEADING_SPEC.legacy_texts[0]
    (tmp_path / _MARKDOWN_TARGET).write_text(
        f"## {_HEADING_SPEC.canonical_text}\n\n## {legacy_text.upper()}\n", encoding="utf-8"
    )
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert "still carries a retired form" in findings[0]


def test_canonical_text_split_across_a_line_wrap_is_still_found(tmp_path: pathlib.Path) -> None:
    # Regression (this gate's own first live run against the real
    # repository, module docstring point 7): a Markdown line-wrap can
    # split the tracked text across two source lines inside a code span.
    # GitHub still renders that as one unbroken phrase; this gate must
    # too, via whitespace normalization.
    #
    # Uses targets[1] (skills/executing-a-branch-plan/SKILL.md), not
    # targets[0] (.github/PULL_REQUEST_TEMPLATE.md) -- the template is
    # also a heading-spec target, so overwriting it would additionally
    # drop that spec's own canonical text and force filtering findings by
    # spec name instead of asserting a clean result directly.
    _write_clean_fixture(tmp_path)
    words = _NOTE_SPEC.canonical_text.split(" ")
    midpoint = len(words) // 2
    wrapped = " ".join(words[:midpoint]) + "\n   " + " ".join(words[midpoint:])
    note_target, _is_markdown = _NOTE_SPEC.targets[1]
    (tmp_path / note_target).write_text(f"prose `{wrapped}` more prose\n", encoding="utf-8")
    assert drift.find_drift(tmp_path) == []


def test_merge_gate_note_spec_targets_are_independently_checked(tmp_path: pathlib.Path) -> None:
    # Uses targets[1] (skills/executing-a-branch-plan/SKILL.md), not
    # targets[0] (.github/PULL_REQUEST_TEMPLATE.md) -- the template is
    # also a heading-spec target, so overwriting it would additionally
    # trip that spec's own finding and defeat this test's "exactly one
    # finding" assertion.
    _write_clean_fixture(tmp_path)
    note_target, _is_markdown = _NOTE_SPEC.targets[1]
    (tmp_path / note_target).write_text("no tracked text here at all\n", encoding="utf-8")
    findings = drift.find_drift(tmp_path)
    assert len(findings) == 1
    assert str(note_target) in findings[0]
    assert _NOTE_SPEC.canonical_text in findings[0]


def test_repository_target_files_are_drift_free() -> None:
    """The gate: real target files must carry every spec's current
    canonical text and none of the retired ones."""
    findings = drift.find_drift(REPO_ROOT)
    assert findings == [], f"independent-review-pending marker drift found: {findings}"


def test_main_prints_no_drift_and_returns_zero_when_clean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    assert rc == 0
    assert "No independent-review-pending marker drift found." in capsys.readouterr().out


def test_main_prints_findings_and_returns_one_on_drift(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        drift,
        "find_drift",
        lambda: ["skills/drafting-a-pr-to-merge/SKILL.md: does not carry the tracked heading text"],
    )
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "Independent-review-pending marker drift found:" in out
    assert "skills/drafting-a-pr-to-merge/SKILL.md" in out

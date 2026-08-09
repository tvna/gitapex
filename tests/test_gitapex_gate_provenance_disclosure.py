"""Tests for the provenance disclosure gate
(.github/scripts/gitapex_gate_provenance_disclosure.py).

Issue #520 (row 3, refs #350): a review-response draft or doc/PR-body diff
must not name a specific tool's absence/presence as an evidence-limitation
reason without an owner-disclosure marker in the same diff.

Issue #978: the gate's cue-word matching redesigned to exclude quoted/
backtick-fenced examples from live-prose matching, fixing issue #549's own
self-trigger class of false positive (repairs 1 and 8) structurally rather
than by manually rewording each instance.
"""

from __future__ import annotations

import gitapex_gate_provenance_disclosure as gate
from conftest import FakeStdin as _FakeStdin

_UNDISCLOSED_NOTE = (
    "The reviewing context had already read the full rubric, so this evaluation "
    "notes the absence of a registered skill invocation and a generic dispatch "
    "tool as the reason a prior run's judgment could not be reused directly.\n"
)

_DISCLOSED_NOTE = (
    _UNDISCLOSED_NOTE + "\n" + "tool-fingerprint-disclosure: WAIVED: owner approved disclosing this in "
    "review on 2026-07-25\n"
)

_CLEAN_NOTE = (
    "The reviewing context had already read the full rubric and its iteration "
    "history, so reusing it would not meet the skill's own isolation bar.\n"
)

_LIMITATION_WITHOUT_TOOL_CUE = "This section notes the absence of a clear owner decision on rollout timing.\n"

_TOOL_CUE_WITHOUT_LIMITATION = "The generic dispatch tool routed the request to the correct subagent.\n"


def test_find_offending_paragraphs_flags_undisclosed_note():
    assert len(gate.find_offending_paragraphs(_UNDISCLOSED_NOTE)) == 1


def test_find_offending_paragraphs_ignores_clean_note():
    assert gate.find_offending_paragraphs(_CLEAN_NOTE) == []


def test_find_offending_paragraphs_requires_both_cues():
    assert gate.find_offending_paragraphs(_LIMITATION_WITHOUT_TOOL_CUE) == []
    assert gate.find_offending_paragraphs(_TOOL_CUE_WITHOUT_LIMITATION) == []


def test_has_disclosure_marker():
    assert gate.has_disclosure_marker(_DISCLOSED_NOTE) is True
    assert gate.has_disclosure_marker(_UNDISCLOSED_NOTE) is False


def test_has_disclosure_marker_requires_non_empty_reason():
    text = "tool-fingerprint-disclosure: WAIVED:\n"
    assert gate.has_disclosure_marker(text) is False


def test_main_stdin_pass(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_CLEAN_NOTE.encode("utf-8")))
    exit_code = gate.main([])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_stdin_fail(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(_UNDISCLOSED_NOTE.encode("utf-8")))
    exit_code = gate.main([])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_stdin_undecodable_errors(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    exit_code = gate.main([])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_body_file_disclosed_passes(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_DISCLOSED_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_body_file_missing_errors(tmp_path, capsys):
    exit_code = gate.main(["--body", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_body_file_undecodable_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_bytes(b"\xff\xfe bad")
    exit_code = gate.main(["--body", str(body)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(body) in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_diff_added_file_undecodable_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_bytes(b"\xff\xfe bad")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(diff_added) in err and "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_diff_added_missing_errors(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_main_marker_in_diff_added_covers_offense_in_body(tmp_path, capsys):
    """The disclosure marker can live in either source; the check applies
    to the combined corpus, matching the ACM's own "same diff" framing."""
    body = tmp_path / "body.md"
    body.write_text(_UNDISCLOSED_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_text("tool-fingerprint-disclosure: WAIVED: owner approved\n", encoding="utf-8")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_offense_in_diff_added_with_no_marker_fails(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_CLEAN_NOTE, encoding="utf-8")
    diff_added = tmp_path / "added.md"
    diff_added.write_text(_UNDISCLOSED_NOTE, encoding="utf-8")
    exit_code = gate.main(["--body", str(body), "--diff-added", str(diff_added)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "absence of a registered skill invocation" in err.lower()


# --- Issue #978: quoting-aware matching, replacing #549's per-instance workaround ---

_QUOTED_VOCABULARY_LISTING = (
    "Vocabulary: limitation/reason cue examples include "
    '"no access to", "lacks access to", "absence of", "missing a"; '
    "tool-fingerprint cue examples include "
    '"a registered skill invocation", "a dispatch tool", "a subagent", '
    'and "an mcp tool call".\n'
)

_RECONSTRUCTED_PR539_FACTS_SECTION = (
    "## Facts\n\n"
    "This PR adds a new gate whose vocabulary combines limitation/reason "
    'cue examples such as "no access to", "lacks access to", "absence of" '
    'with tool-fingerprint cue examples such as "a registered skill '
    'invocation", "a dispatch tool", and "an mcp tool call" to detect '
    "undisclosed evidence-limitation prose.\n"
)


def test_quoted_example_spans_finds_short_backtick_and_straight_quoted_spans():
    text = 'See `_LIMITATION_CUE_RE` and "no access to" for the pattern.'
    spans = gate._quoted_example_spans(text)
    assert len(spans) == 2
    substrings = [text[start:end] for start, end in spans]
    assert "`_LIMITATION_CUE_RE`" in substrings
    assert '"no access to"' in substrings


def test_quoted_example_spans_recognizes_curly_quotes():
    text = "See “no access to” for the pattern."
    spans = gate._quoted_example_spans(text)
    assert len(spans) == 1
    start, end = spans[0]
    assert text[start:end] == "“no access to”"


def test_quoted_example_spans_excludes_a_span_combining_both_cue_types():
    """A quoted span combining both cue types does not read as a
    documented example (issue #978, adversarial-review finding: an
    earlier draft let an entire offending clause evade detection by
    quoting the whole sentence)."""
    text = '"the absence of a registered skill invocation and a generic dispatch tool" is what one reviewer wrote.\n'
    assert gate._quoted_example_spans(text) == []


def test_quoted_example_spans_excludes_a_short_span_combining_both_cue_types():
    """A second-round adversarial-review finding against the word-count-cap
    draft: a *minimal* quoted phrase carrying just one instance of each
    cue (well under any word-count cap) must still be excluded from the
    documented-example set, the same as a long clause."""
    text = '"absence of a dispatch tool" is a real problem here.\n'
    assert gate._quoted_example_spans(text) == []


def test_find_offending_paragraphs_ignores_quoted_vocabulary_listing():
    """A paragraph documenting the gate's own cue-word vocabulary as quoted
    examples -- the #549 self-trigger shape -- must not flag (issue #978)."""
    assert gate.find_offending_paragraphs(_QUOTED_VOCABULARY_LISTING) == []


def test_find_offending_paragraphs_still_flags_live_prose_with_unrelated_quote():
    """Stripping quoted spans must not suppress a genuine violation whose
    cue phrases are themselves unquoted, even if the paragraph also
    contains an unrelated quoted aside."""
    text = (
        "This evaluation notes the absence of a registered skill invocation "
        "and a generic dispatch tool as the reason, in what one reviewer "
        'called "a genuinely surprising gap."\n'
    )
    assert len(gate.find_offending_paragraphs(text)) == 1


def test_module_docstring_is_not_self_flagged():
    """Regression proof for issue #978: the module's own docstring
    documents both cue types (quoted) in one paragraph without
    self-triggering, replacing issue #549 repair 8's narrower
    two-paragraph-split workaround."""
    assert gate.find_offending_paragraphs(gate.__doc__ or "") == []


def test_reconstructed_pr539_facts_section_reproducer_no_longer_flags():
    """Issue #978, row 2: a permanent regression fixture for issue #549's
    self-trigger. The literal historical PR #539 body was never committed
    (fixed by an in-place body edit before merge, and #549's own
    retrospective deliberately avoided reproducing it verbatim to avoid
    re-triggering the gate on itself) -- this reconstructs the documented
    shape (a PR Facts section quoting the gate's own cue-word vocabulary as
    an example) from #549 repair 1's description."""
    assert gate.find_offending_paragraphs(_RECONSTRUCTED_PR539_FACTS_SECTION) == []


def test_main_quoted_vocabulary_listing_in_body_passes(tmp_path, capsys):
    body = tmp_path / "body.md"
    body.write_text(_QUOTED_VOCABULARY_LISTING, encoding="utf-8")
    exit_code = gate.main(["--body", str(body)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_find_offending_paragraphs_still_flags_fully_quoted_violating_clause():
    """Adversarial-review finding against issue #978's first draft: wrapping
    an entire offending clause in one long quoted span must not evade
    detection -- a span reads as a documented example only when it does
    NOT itself combine both cue types, never merely because it is short."""
    text = (
        'This evaluation notes "the absence of a registered skill '
        'invocation and a generic dispatch tool" as the reason a prior '
        "run's judgment could not be reused directly.\n"
    )
    assert len(gate.find_offending_paragraphs(text)) == 1


def test_find_offending_paragraphs_still_flags_a_minimal_quoted_violating_phrase():
    """Second-round adversarial-review finding (two independent finder
    angles, both live-verified): a word-count cap on "documented example"
    let a *minimal* violating phrase -- just enough words to carry one
    instance of each cue, well under any plausible cap -- evade detection
    exactly as completely as a full sentence did. The fix checks the
    span's own content against both cue regexes instead of its length, so
    there is no threshold length to slip under."""
    text = 'The agent noted "missing a mcp tool" during the run.\n'
    assert len(gate.find_offending_paragraphs(text)) == 1


def test_find_offending_paragraphs_does_not_bridge_across_an_unrelated_quoted_aside():
    """Adversarial-review finding against issue #978's first draft: an
    earlier version *rewrote* the paragraph text (replacing a documented
    example with a single space), which let a whitespace-tolerant cue
    alternative (``lacks\\s+access to``) bridge across the removed span and
    fabricate a match between two words that were never actually adjacent.
    Filtering match positions instead of rewriting text must not
    reproduce that bridge."""
    text = "The audit lacks `some unrelated inline code aside` access to a dispatch tool and a registered skill invocation as context.\n"
    assert gate.find_offending_paragraphs(text) == []


def test_find_offending_paragraphs_recognizes_a_hard_wrapped_quoted_example():
    """Adversarial-review finding against issue #978's first draft: the
    quoted-span pattern excluded embedded newlines, so a documented
    vocabulary example hard-wrapped across two lines of Markdown source
    (this repository's own docs/skills/evals convention) was not
    recognized as one span and could still self-trigger the gate."""
    text = 'Vocabulary: examples include "no access to" and "a registered skill\ninvocation" as documented above.\n'
    assert gate.find_offending_paragraphs(text) == []


def test_quoted_example_spans_finds_a_hard_wrapped_span():
    text = '"a registered skill\ninvocation"'
    spans = gate._quoted_example_spans(text)
    assert len(spans) == 1
    start, end = spans[0]
    assert text[start:end] == text


def test_quoted_span_does_not_pair_across_more_than_one_newline():
    """Adversarial-review finding: an unbounded newline-tolerant quote span
    would let an accidental, unmatched backtick in hard-wrapped prose pair
    with an unrelated closing backtick several lines later, silently
    swallowing real cue content. Bounding the span to at most one embedded
    newline keeps an accidental mispair's reach small while still
    supporting this module's own docstring's single-line-wrapped example."""
    text = "`stray opening backtick\non one line\nand a real closing backtick` elsewhere\n"
    assert gate._QUOTED_SPAN_RE.search(text) is None


def test_find_offending_paragraphs_still_flags_content_past_an_accidental_backtick_mispair():
    """The same finding, end to end: a stray backtick more than one line
    away from its accidental closing partner must not swallow a genuine
    violation that sits between them."""
    text = (
        "This script lacks access to the runtime because `escaped\n"
        "some filler line\n"
        "an MCP tool call` is not available here.\n"
    )
    assert len(gate.find_offending_paragraphs(text)) == 1

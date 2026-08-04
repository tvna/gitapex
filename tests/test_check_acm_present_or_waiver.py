"""Direct-import unit suite for hooks/check_acm_present_or_waiver.py.

No such suite existed before issue #657's own adversarial review: this
module was previously exercised only indirectly, via
hooks/test_check_issue_acm_disclosure.py's subprocess-level `.sh`-wrapper
tests and tests/test_check_pr_issue_acm_disclosure.py's classify_issue
tests (which stub the fetched issue body but never probe this module's
own fence-stripping directly). `hooks` is on pyproject.toml's
`pythonpath`, so this module imports the same way
tests/test_check_pr_issue_acm_disclosure.py imports
check_pr_issue_acm_disclosure -- as a plain top-level module.
"""

from __future__ import annotations

import io

import check_acm_present_or_waiver as checker


class _FakeStdin:
    """Just the surface `main` uses: `sys.stdin.buffer.read()`."""

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


_VALID_ACM_TABLE = (
    "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |\n"
    "|---|---|---|---|---|\n"
    "| Thing works | It should do X | Add Y | Run Z | None |\n"
)


def test_has_acm_disclosure_true_for_a_real_table():
    assert checker.has_acm_disclosure(_VALID_ACM_TABLE) is True


def test_has_acm_disclosure_true_for_a_real_waiver_line():
    assert checker.has_acm_disclosure("ACM: not-applicable (chore): docs-only rewording.") is True


def test_has_acm_disclosure_true_for_a_backtick_wrapped_waiver_line():
    # `_ACM_WAIVER_RE` itself optionally wraps the literal word ACM in a
    # single backtick pair -- must still pass. This is exactly the
    # legitimate syntax that a naive single-backtick inline-code strip
    # (as hooks/check_pr_issue_acm_disclosure.py's own `_strip_fences`
    # does) would false-negative; confirmed directly before choosing
    # fence-only stripping for this module instead.
    assert checker.has_acm_disclosure("`ACM`: not-applicable (chore): docs-only rewording.") is True


def test_has_acm_disclosure_false_for_plain_text():
    assert checker.has_acm_disclosure("just a plain body with no table and no waiver") is False


def test_has_acm_disclosure_false_for_none():
    assert checker.has_acm_disclosure(None) is False


def test_fenced_acm_table_does_not_count_as_disclosure():
    # Regression for issue #657's own adversarial review:
    # hooks/check_pr_issue_acm_disclosure.py's classify_issue() now calls
    # this function against a remotely fetched, different issue's body --
    # an issue author quoting an unfilled ACM table inside a fence as an
    # illustrative example, with prose disclaiming it, must not read as a
    # real disclosure.
    body = (
        "Some text.\n\n"
        "```\n"
        f"{_VALID_ACM_TABLE}"
        "```\n\n"
        "I have not actually filled one in, this is just an example of the shape."
    )
    assert checker.has_acm_disclosure(body) is False


def test_fenced_waiver_line_does_not_count_as_disclosure():
    body = (
        "```\n"
        "ACM: not-applicable (chore): example only, not real\n"
        "```\n"
        "I have not actually disclosed a waiver, just showing the syntax."
    )
    assert checker.has_acm_disclosure(body) is False


def test_tilde_fenced_acm_table_does_not_count_as_disclosure():
    body = f"~~~\n{_VALID_ACM_TABLE}~~~\nJust an example, not a real disclosure."
    assert checker.has_acm_disclosure(body) is False


def test_real_disclosure_outside_an_unrelated_fence_still_counts():
    # A fence elsewhere in the body (e.g. a code sample unrelated to ACM)
    # must not swallow a genuine, unfenced waiver line that follows it.
    body = "```\nsome_code()\n```\n\nACM: not-applicable (docs): typo fix only.\n"
    assert checker.has_acm_disclosure(body) is True


def test_waiver_category_returns_none_for_a_fenced_fake_waiver():
    body = "```\nACM: not-applicable (tracking): example only\n```\nNot a real waiver."
    assert checker.waiver_category(body) is None


def test_waiver_category_still_reads_a_real_backtick_wrapped_waiver():
    assert checker.waiver_category("`ACM`: not-applicable (defect): bare defect report.") == "defect"


def test_waiver_category_returns_none_for_no_waiver():
    assert checker.waiver_category("just a plain body") is None


# ---------------------------------------------------------------------------
# Fence-stripping edge cases: an adversarial re-verification of the fix
# above found the naive matched-pair-only regex it originally used had two
# real gaps (unclosed fence, odd marker count). _strip_fences was rewritten
# as a stateful per-line scan (fence markers toggle in/out of a fence)
# specifically to close them -- see that function's own comment.
# ---------------------------------------------------------------------------


def test_unclosed_fence_extends_to_end_of_text():
    # An opening marker with no matching close: a naive `re.sub(r"```.*?```",
    # ...)` finds no pair at all and leaves everything after the opening
    # marker fully exposed. The real GitHub renderer treats an unclosed
    # fence as extending to end-of-text; this scan matches that.
    body = (
        "```\n"
        "I have not actually filled one in, example only.\n\n"
        f"{_VALID_ACM_TABLE}"
    )
    assert checker.has_acm_disclosure(body) is False


def test_unclosed_tilde_fence_extends_to_end_of_text():
    body = "~~~\nACM: not-applicable (chore): fake, never closed\n"
    assert checker.has_acm_disclosure(body) is False


def test_odd_fence_marker_count_leaves_a_genuine_unfenced_line_detected():
    # Three total markers: the first pair forms one complete, closed
    # fenced block; the third marker opens a second, unclosed block. A
    # real Markdown renderer shows the line between the 2nd and 3rd
    # markers as ordinary, unfenced prose -- not visually distinguished
    # as quoted/illustrative in any way -- so a genuine disclosure line
    # placed there is correctly still detected: it isn't actually hidden
    # by anything, the same as writing it with no fences at all.
    body = "```\nreal code sample\n```\nACM: not-applicable (chore): genuinely unfenced text\n```\nmore code\n"
    assert checker.has_acm_disclosure(body) is True


def test_content_between_two_separate_closed_fences_stays_stripped_in_each():
    # Two independent, individually well-formed fenced blocks (4 markers
    # total, matched pairwise) -- content inside either must still strip;
    # only the genuinely-unfenced line between them survives.
    body = f"```\n{_VALID_ACM_TABLE}```\nACM: not-applicable (docs): ok\n```\nfake table again\n```"
    assert checker.has_acm_disclosure(body) is True
    # Remove the real disclosure and confirm both fenced blocks alone
    # (with no genuine unfenced content at all) do not pass.
    body_no_real = f"```\n{_VALID_ACM_TABLE}```\njust some prose in between, no disclosure here\n```\nfake table\n```"
    assert checker.has_acm_disclosure(body_no_real) is False


def test_known_residual_gap_single_backtick_multiline_span_not_stripped():
    # Named, disclosed limitation (not fixed by the fence-stripping work
    # above, and not a regression from it either -- this was never
    # stripped, before or after issue #657's own fence fix): a multi-line
    # span delimited by a single backtick pair is not treated as fenced,
    # by design (stripping single backticks would break _ACM_WAIVER_RE's
    # own legitimate `` `ACM`: ... `` syntax -- see this module's own
    # _strip_fences comment). An issue author can still place misleading
    # content inside one and have it detected as a real disclosure.
    body = "`\nACM: not-applicable (chore): fake, inside a multi-line single-backtick span\n`"
    assert checker.has_acm_disclosure(body) is True


def test_known_residual_gap_four_space_indented_block_not_stripped():
    # Named, disclosed limitation: this module only recognizes fenced
    # (```/~~~) code blocks, not Markdown's traditional 4-space-indent
    # code-block convention -- a pre-existing gap, not introduced or
    # claimed to be closed by issue #657's fence-stripping fix.
    body = "    ACM: not-applicable (chore): fake, 4-space indented\n"
    assert checker.has_acm_disclosure(body) is True


# ---------------------------------------------------------------------------
# main()'s read path: a non-UTF-8 --body file or stdin must exit cleanly
# with the documented exit code, not an uncaught UnicodeDecodeError.
# ---------------------------------------------------------------------------


def test_main_reports_error_for_non_utf8_body_file(tmp_path, capsys):
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe bad")
    assert checker.main(["--body", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, capsys):
    monkeypatch.setattr(checker.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert checker.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err

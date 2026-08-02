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

import check_acm_present_or_waiver as checker

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

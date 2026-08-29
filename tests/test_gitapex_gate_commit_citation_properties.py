"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_commit_citation.py`` (issue #1212, closing
issue #1178's own ``detection-logic-property-coverage`` gap for this new
module's ``REPO_ROOT``/``sys.path`` module-level ``.resolve()`` calls and its
``check_commit_message``/``check_pr_text`` citation-detection wrappers).

These wrappers carry no detection logic of their own beyond the call to
``extract_citations`` (``hooks/gitapex_check_pr_issue_acm_disclosure.py``,
reused rather than reimplemented -- see this module's own docstring); the
properties below confirm the *integration* holds across generated input
(a citation form is still recognized once wrapped, fence-stripping is not
bypassed by the wrapping, arbitrary text never raises), not the citation
regex's own vocabulary, which is that module's own concern.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_check_pr_duplicate_issue_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite that reruns green).
"""

from __future__ import annotations

import gitapex_gate_commit_citation as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Every citation form check_commit_message/check_pr_text must recognize
# (extract_citations' own resolving and context-only vocabulary), each as a
# format string taking one issue number.
_CITATION_TEMPLATES = ("Closes #{n}", "Fixes #{n}", "Resolves #{n}", "Refs #{n}", "#{n}")

# Free text with no digit at all, so it can never accidentally contain a
# `#N`-shaped citation of its own -- used as filler/surrounding prose in the
# properties below.
_NO_DIGIT_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="#0123456789`"),
    max_size=60,
)


@_PROPERTIES
@given(
    template=st.sampled_from(_CITATION_TEMPLATES),
    number=st.integers(min_value=1, max_value=999999),
    prefix=_NO_DIGIT_TEXT,
    suffix=_NO_DIGIT_TEXT,
)
def test_any_citation_form_is_recognized_in_a_commit_message(
    template: str, number: int, prefix: str, suffix: str
) -> None:
    """Every citation form this repository's own convention documents
    (CONTRIBUTING.md's "Issue citation convention") is recognized by
    check_commit_message, wherever it sits inside otherwise-arbitrary
    surrounding text -- not only the one or two hand-picked examples in
    tests/test_gitapex_gate_commit_citation.py."""
    message = f"{prefix}\n\n{template.format(n=number)}\n{suffix}"
    assert gate.check_commit_message(message) is True


@_PROPERTIES
@given(
    template=st.sampled_from(_CITATION_TEMPLATES),
    number=st.integers(min_value=1, max_value=999999),
    prefix=_NO_DIGIT_TEXT,
    suffix=_NO_DIGIT_TEXT,
)
def test_any_citation_form_is_recognized_in_pr_title_or_body(
    template: str, number: int, prefix: str, suffix: str
) -> None:
    """The same recognition property, through check_pr_text's own title/body
    pair -- confirms the wrapper does not silently narrow what
    extract_citations already accepts."""
    citation = template.format(n=number)
    assert gate.check_pr_text("tvna", "gitapex", f"{prefix} {citation}", "") is True
    assert gate.check_pr_text("tvna", "gitapex", "", f"{prefix}\n{citation}\n{suffix}") is True


@_PROPERTIES
@given(
    template=st.sampled_from(_CITATION_TEMPLATES),
    number=st.integers(min_value=1, max_value=999999),
)
def test_a_citation_inside_a_fenced_code_block_is_never_recognized(template: str, number: int) -> None:
    """Containment: a citation form shown only inside a fenced code block
    (an illustrative example of this repository's own citation syntax, the
    exact false-positive class hooks/gitapex_check_pr_issue_acm_disclosure.py's
    own docstring names as found live against its own PR body) is never
    misdetected as a real citation -- across every generated citation form
    and issue number, not only the one hand-picked example in
    tests/test_gitapex_gate_commit_citation.py.

    Confirmed to have teeth: passing the raw, un-stripped text straight to
    a bare ``#\\d+`` search instead of through extract_citations makes this
    property FAIL on every generated example, since the fenced line still
    contains a real citation-shaped match."""
    message = f"docs: explain the citation syntax\n\n```\n{template.format(n=number)}\n```\n"
    assert gate.check_commit_message(message) is False


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_check_commit_message_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text (including stray `#`, backticks, or
    partial keyword fragments) produces a result rather than an exception,
    and the same input produces the same output -- this function runs
    inside a git commit-msg hook, where an uncaught exception blocks every
    commit rather than reporting one FAIL."""
    first = gate.check_commit_message(text)
    second = gate.check_commit_message(text)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(title=st.text(max_size=150), body=st.text(max_size=300))
def test_check_pr_text_never_raises_and_is_deterministic(title: str, body: str) -> None:
    """The same robustness property for check_pr_text's own title/body
    pair -- this function runs inside the CI backstop, where an uncaught
    exception fails the job with a traceback rather than a clear FAIL."""
    first = gate.check_pr_text("tvna", "gitapex", title, body)
    second = gate.check_pr_text("tvna", "gitapex", title, body)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(text=_NO_DIGIT_TEXT)
def test_text_never_containing_a_hash_is_never_recognized_as_a_citation(text: str) -> None:
    """No false positive: text that can never contain a `#`-shaped
    citation at all is never recognized as carrying one, regardless of
    what other punctuation or structure it happens to contain."""
    assert gate.check_commit_message(text) is False
    assert gate.check_pr_text("tvna", "gitapex", text, text) is False

"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_independent_review_pending.py`` (issue #1311,
closing issue #1178's own ``detection-logic-property-coverage`` gap for
this new module's ``_HEADING_RE``/``_FENCED_BLOCK_RE``/``_VERDICT_RE``/
``_COMMIT_RE`` module-level compiles and the ``_last_section_from``/
``parse_verdict`` functions).

Issue #1343 briefly extended this file with property tests for a public
``heading_pattern()`` function, added to this module so
``gitapex_scan_independent_review_heading_drift.py`` could reuse its
ATX-heading regex shape for arbitrary text -- reverted (both the
function and these tests) once a reuse/simplification review found the
call that justified making it public never actually happened (see that
module's own history), leaving a public function with no caller. One
property survives, adapted to exercise ``_HEADING_RE`` directly instead:
case-insensitivity of the heading text itself, which no pre-existing
test covered (only the Verdict/commit field values' own casing was
pinned).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_check_pr_duplicate_issue_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite).
"""

from __future__ import annotations

import re

import gitapex_gate_independent_review_pending as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_ANY_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_HEX = "0123456789abcdefABCDEF"
_SHAS = st.text(alphabet=_HEX, min_size=7, max_size=40)
_HEADING_LEVELS = ("##", "###", "####")
_EMPHASIS = ("", "*", "_", "`")
_BULLETS = ("-", "*")


@_PROPERTIES
@given(text=st.text(max_size=500))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: this module runs inside a required CI status check, where
    an uncaught exception in `parse_verdict`/`check` is a crashed gate, not
    a reported finding -- confirmed live this session against a directory
    path via `main`'s own file-reading branch (now caught there), but
    `parse_verdict`/`check` themselves take an in-memory string and must
    never raise regardless of its content."""
    first = gate.parse_verdict(text)
    second = gate.parse_verdict(text)
    assert first.status == second.status
    assert first.commit == second.commit
    assert first.error == second.error
    # Issue #2013: the three new optional fields must be just as
    # deterministic as the two pre-existing ones.
    assert first.finding_class == second.finding_class
    assert first.round == second.round
    assert first.owner_decision == second.owner_decision

    passed_first, message_first = gate.check(text, "abc123")
    passed_second, message_second = gate.check(text, "abc123")
    assert passed_first == passed_second
    assert message_first == message_second
    assert isinstance(passed_first, bool)


@_PROPERTIES
@given(text=st.text(max_size=300).filter(lambda s: "independent review verdict" not in s.lower()))
def test_text_never_containing_the_heading_phrase_never_parses(text: str) -> None:
    """No false positive: text that never contains the heading phrase at all
    (case-insensitively) never yields a usable verdict, regardless of what
    other Markdown structure it happens to contain."""
    verdict = gate.parse_verdict(text)
    assert verdict.error is not None


@_PROPERTIES
@given(
    level=st.sampled_from(_HEADING_LEVELS),
    sha=_SHAS,
    verdict_emphasis=st.sampled_from(_EMPHASIS),
    commit_emphasis=st.sampled_from(_EMPHASIS),
    bullet=st.sampled_from(_BULLETS),
    casing=st.sampled_from(("Independent review verdict", "INDEPENDENT REVIEW VERDICT", "independent review verdict")),
)
def test_a_real_clean_verdict_is_always_detected_and_passes(
    level: str, sha: str, verdict_emphasis: str, commit_emphasis: str, bullet: str, casing: str
) -> None:
    """**Model-based, detects a real gap fixed examples cannot:** a genuine,
    unfenced verdict section is always recognized as CLEAN against its own
    stated commit, across heading level, verdict/commit emphasis markup,
    bullet style, and heading casing -- not only the handful of hand-picked
    combinations in test_gitapex_gate_independent_review_pending.py.

    Confirmed to have teeth: narrowing `_HEADING_RE`'s `#{1,6}` to a literal
    `##` makes this property FAIL on every `###`/`####`-level generated
    example."""
    body = (
        f"{level} {casing}\n\n"
        f"{bullet} Verdict: {verdict_emphasis}CLEAN{verdict_emphasis}\n"
        f"{bullet} Verified commit: {commit_emphasis}{sha}{commit_emphasis}\n"
    )
    passed, message = gate.check(body, sha)
    assert passed is True, f"expected PASS for body={body!r}, got: {message}"


@_PROPERTIES
@given(sha=_SHAS, fence=st.sampled_from(("```", "~~~", "````", "~~~~")))
def test_a_verdict_inside_a_fenced_code_block_is_never_detected(sha: str, fence: str) -> None:
    """Containment: a syntactically valid CLEAN verdict section, wrapped in
    a fenced code block (an illustrative example only), is never
    misdetected as a real, live verdict -- across generated SHAs and fence
    styles/lengths, not only the one hand-picked example in
    test_gitapex_gate_independent_review_pending.py's own defeat-attempt
    tests. This is a live-confirmed defeat class (see the module docstring
    and issue #1311's own defeat-test-disclosure round), not a theoretical
    one.

    Confirmed to have teeth: removing `strip_fenced_code_blocks`'s call
    from `parse_verdict` makes this property FAIL on every generated
    example, since the unstripped fenced section still matches
    `_HEADING_RE`/`_VERDICT_RE`/`_COMMIT_RE` directly."""
    body = f"Example usage:\n{fence}\n## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n{fence}\n"
    passed, _ = gate.check(body, sha)
    assert passed is False


@_PROPERTIES
@given(
    open_len=st.integers(min_value=3, max_value=6),
    extra_close_len=st.integers(min_value=0, max_value=4),
    fence_char=st.sampled_from(("`", "~")),
    inner=st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="`~"), max_size=100),
)
def test_strip_fenced_code_blocks_direct_call_handles_any_valid_close_length(
    open_len: int, extra_close_len: int, fence_char: str, inner: str
) -> None:
    """Direct call into `strip_fenced_code_blocks` itself: CommonMark's own
    rule is that a closing fence needs the same character repeated *at
    least* as many times as the opening one, not an exact-length match --
    a live adversarial round found an earlier backreference-based version
    only recognized an exact-length close, letting a longer one defeat it.
    `close_len` is always `>= open_len` by construction (`extra_close_len`
    is a non-negative offset), so every generated example is a valid
    CommonMark close, never filtered away by an `assume`/early-return that
    would leave this property under-exercised."""
    close_len = open_len + extra_close_len
    open_fence = fence_char * open_len
    close_fence = fence_char * close_len
    marker = f"MARKER_START{inner}MARKER_END"  # a sentinel `inner` alone can't coincidentally match "before"/"after"
    text = f"before\n{open_fence}\n{marker}\n{close_fence}\nafter\n"
    stripped = gate.strip_fenced_code_blocks(text)
    assert "before" in stripped
    assert "after" in stripped
    assert marker not in stripped


@_PROPERTIES
@given(
    fence_char=st.sampled_from(("`", "~")), inner=st.text(max_size=100).filter(lambda s: "`" not in s and "~" not in s)
)
def test_strip_fenced_code_blocks_direct_call_unclosed_fence_extends_to_eof(fence_char: str, inner: str) -> None:
    """Direct call: an opened but never-closed fence (a plausible authoring
    slip, not only a deliberate attack -- a live adversarial round found
    this defeated an earlier version) extends to end-of-document, per
    CommonMark, rather than leaving its own contents unstripped."""
    fence = fence_char * 3
    marker = f"MARKER_START{inner}MARKER_END"  # a sentinel `inner` alone can't coincidentally match "before"
    text = f"before\n{fence}\n{marker}"
    stripped = gate.strip_fenced_code_blocks(text)
    assert "before" in stripped
    assert marker not in stripped


_TRAILING_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), max_size=200).filter(
    lambda s: "independent review verdict" not in s.lower()
)


@_PROPERTIES
@given(sha=_SHAS, other_sha=_SHAS, trailing=_TRAILING_TEXT)
def test_last_section_from_never_crosses_the_next_heading(sha: str, other_sha: str, trailing: str) -> None:
    """`_last_section_from` (used by `parse_verdict` to isolate the matched
    heading's own section) never lets a field belonging to a later,
    different section leak into the current one -- checked across
    generated trailing content that itself might coincidentally contain
    `##`-shaped text or verdict-field-shaped lines."""
    body = (
        f"## Independent review verdict\n\n"
        f"- Verdict: CLEAN\n- Verified commit: {sha}\n\n"
        f"## Some later section\n\n"
        f"- Verdict: CLEAN\n- Verified commit: {other_sha}\n{trailing}\n"
    )
    verdict = gate.parse_verdict(body)
    assert verdict.commit == sha


_HEADING_FREE_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")), max_size=100).filter(
    lambda s: not _ANY_HEADING_RE.search(s)
)


@_PROPERTIES
@given(before=_HEADING_FREE_TEXT, after=_HEADING_FREE_TEXT)
def test_last_section_from_direct_call_stops_at_next_heading(before: str, after: str) -> None:
    """Direct call into `_last_section_from` itself (not only via
    `parse_verdict`): the returned slice from `start` never includes any
    `##`-shaped heading line or anything past it, across generated
    heading-free `before`/`after` content."""
    marker = "## Next heading here\nunreachable content"
    text = f"{before}\n{marker}\n{after}" if after else f"{before}\n{marker}"
    start = len(before) + 1  # just after "before\n"
    section = gate._last_section_from(text, start)
    assert "Next heading here" not in section
    assert "unreachable content" not in section


_HEADING_LEVEL_MARKS = ("#", "##", "###", "####", "#####", "######")


@_PROPERTIES
@given(level=st.sampled_from(_HEADING_LEVEL_MARKS))
def test_heading_re_is_case_insensitive(level: str) -> None:
    """`_HEADING_RE` is case-insensitive (module docstring); no
    pre-existing test exercised case-insensitivity of the heading text
    itself, only of the Verdict/commit field values' own casing (see
    `test_check_is_case_insensitive_on_verdict_and_commit` in
    tests/test_gitapex_gate_independent_review_pending.py). Confirmed to
    have teeth: dropping `re.IGNORECASE` from `_HEADING_RE`'s own
    `re.compile` call makes this property FAIL for every generated level.

    `CANONICAL_HEADING_TEXT` ("Independent review verdict") is plain
    ASCII, so `str.swapcase()` is safe here -- unlike arbitrary Unicode
    text, it maps every character to exactly one character, with no
    length-changing special case (e.g. German sharp-S `'ß'` swapcasing to
    the two-character `'SS'`) to work around."""
    body = f"{level} {gate.CANONICAL_HEADING_TEXT.swapcase()}\n"
    assert gate._HEADING_RE.search(body) is not None


# ---------------------------------------------------------------------------
# _email_matches_pattern (issue #1858, closing issue #1178's own
# detection-logic-property-coverage gap for this new string-comparison/
# regex allowlist check -- the trusted-bot exemption's head-commit email
# verification, see the module docstring's own "Trusted-bot exemption"
# section).
# ---------------------------------------------------------------------------

_EMAIL_ALPHABET = st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\n\r")
_EMAIL_TEXT = st.text(alphabet=_EMAIL_ALPHABET, max_size=40)
# An empty pattern is deliberately excluded here: `_email_matches_pattern`
# fail-closes an empty pattern to False (module docstring) while Python's
# own `str.startswith("")`/`endswith("")`/`"" in s` are all vacuously True
# -- a real, intentional divergence from Python's own semantics, already
# covered by its own dedicated property (`test_empty_or_non_string_pattern_never_matches`
# below), not a case these three "matches Python's own operator" properties
# should also assert against.
_NON_EMPTY_EMAIL_TEXT = _EMAIL_TEXT.filter(lambda s: s != "")


@_PROPERTIES
@given(prefix=_NON_EMPTY_EMAIL_TEXT, rest=_EMAIL_TEXT)
def test_starts_with_matches_python_str_startswith(prefix: str, rest: str) -> None:
    """`starts_with` is a thin wrapper over `str.startswith` -- checked
    across generated prefix/rest content, not only the one hand-picked
    example in test_gitapex_gate_independent_review_pending.py."""
    email = prefix + rest
    assert gate._email_matches_pattern(email, "starts_with", prefix) == email.startswith(prefix)


@_PROPERTIES
@given(prefix=_EMAIL_TEXT, suffix=_NON_EMPTY_EMAIL_TEXT)
def test_ends_with_matches_python_str_endswith(prefix: str, suffix: str) -> None:
    email = prefix + suffix
    assert gate._email_matches_pattern(email, "ends_with", suffix) == email.endswith(suffix)


@_PROPERTIES
@given(before=_EMAIL_TEXT, needle=_NON_EMPTY_EMAIL_TEXT, after=_EMAIL_TEXT)
def test_contains_matches_python_in_operator(before: str, needle: str, after: str) -> None:
    email = before + needle + after
    assert gate._email_matches_pattern(email, "contains", needle) == (needle in email)


@_PROPERTIES
@given(email=_EMAIL_TEXT)
def test_regex_operator_matches_re_search_semantics(email: str) -> None:
    """A fixed, always-valid pattern (not itself generated) -- this
    property is about `_email_matches_pattern`'s own regex dispatch
    matching `re.search`'s own semantics, not about regex-pattern
    validity (a malformed pattern is a separate, already-covered fixed
    example in test_gitapex_gate_independent_review_pending.py)."""
    pattern = r"^[a-z]"
    assert gate._email_matches_pattern(email, "regex", pattern) == (re.search(pattern, email) is not None)


@_PROPERTIES
@given(
    email=_EMAIL_TEXT,
    operator=st.text(max_size=20).filter(lambda s: s not in {"starts_with", "ends_with", "contains", "regex"}),
    pattern=_EMAIL_TEXT.filter(lambda s: s != ""),
)
def test_unknown_operator_never_matches(email: str, operator: str, pattern: str) -> None:
    """Fail-closed default (module docstring): an unrecognized operator
    never matches, across generated operator/pattern/email content, not
    only the single hand-picked `"unknown-operator"` example."""
    assert gate._email_matches_pattern(email, operator, pattern) is False


@_PROPERTIES
@given(email=_EMAIL_TEXT, operator=st.sampled_from(("starts_with", "ends_with", "contains", "regex")))
def test_empty_or_non_string_pattern_never_matches(email: str, operator: str) -> None:
    assert gate._email_matches_pattern(email, operator, "") is False
    assert gate._email_matches_pattern(email, operator, None) is False


@_PROPERTIES
@given(email=st.text(max_size=100), operator=st.text(max_size=20), pattern=st.text(max_size=40))
def test_email_matches_pattern_never_raises_and_is_deterministic(email: str, operator: str, pattern: str) -> None:
    """Robustness: arbitrary operator/pattern/email content produces a
    result rather than an exception (this function runs inside a required
    CI status check, where an uncaught exception is a crashed gate, not a
    reported finding), and is deterministic."""
    first = gate._email_matches_pattern(email, operator, pattern)
    second = gate._email_matches_pattern(email, operator, pattern)
    assert first == second
    assert isinstance(first, bool)


# ---------------------------------------------------------------------------
# Round-cap parsing/enforcement (issue #2013): the three fields issue
# #2035/PR #2036 previously only documented -- `- Finding class:`,
# `- Round:`, `- Owner decision:` -- are now actually parsed and gated on.
# Model-based coverage of the same four-case matrix
# test_gitapex_gate_independent_review_pending.py's own hand-picked
# examples establish, generated across many finding-class/round/SHA
# combinations rather than the one hand-picked value each.
# ---------------------------------------------------------------------------

# Deliberately excludes `*`/`_`/backtick (this module's own emphasis-wrap
# markers -- a generated value ending in one of these would be stripped by
# `_FINDING_CLASS_RE`/`_OWNER_DECISION_RE` themselves, an artifact of the
# tolerant-emphasis parsing this property is not testing, not a real
# mismatch) and leading/trailing whitespace (already stripped by every
# field's own trailing `[ \t]*$`, so a generated value carrying it could
# never round-trip unchanged either).
_FIELD_VALUE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/.:#() "
_FINDING_CLASSES = st.text(alphabet=_FIELD_VALUE_ALPHABET, min_size=1, max_size=30).filter(lambda s: s.strip() == s)
_OWNER_DECISIONS = st.text(alphabet=_FIELD_VALUE_ALPHABET, min_size=1, max_size=60).filter(lambda s: s.strip() == s)
# `_ROUND_CAP` itself is the trigger point (`check()` compares with `>=`,
# not `>`) -- `drafting-a-pr-to-merge/SKILL.md`'s own Stopping rule fires
# at exactly `Round: 2` ("2 consecutive rounds"), the same value
# `_ROUND_CAP` holds, not `_ROUND_CAP + 1`. An earlier revision of both
# `check()` and these two ranges shared an off-by-one that never generated
# the actual trigger state at all; fixed together with `check()` itself.
_AT_OR_OVER_CAP_ROUNDS = st.integers(min_value=gate._ROUND_CAP, max_value=gate._ROUND_CAP + 50)
_BELOW_CAP_ROUNDS = st.integers(min_value=0, max_value=gate._ROUND_CAP - 1)


@_PROPERTIES
@given(sha=_SHAS, round_value=_BELOW_CAP_ROUNDS, finding_class=st.one_of(st.none(), _FINDING_CLASSES))
def test_round_below_cap_always_passes_with_or_without_finding_class(
    sha: str, round_value: int, finding_class: str | None
) -> None:
    """PASS case of the four-case matrix: `Round < _ROUND_CAP`, generated
    both with and without a `Finding class` line present."""
    finding_class_line = f"- Finding class: {finding_class}\n" if finding_class is not None else ""
    body = f"## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n{finding_class_line}- Round: {round_value}\n"
    passed, message = gate.check(body, sha)
    assert passed is True, f"expected PASS for body={body!r}, got: {message}"


@_PROPERTIES
@given(sha=_SHAS, round_value=_AT_OR_OVER_CAP_ROUNDS, owner_decision=_OWNER_DECISIONS)
def test_round_at_or_over_cap_with_owner_decision_always_passes(
    sha: str, round_value: int, owner_decision: str
) -> None:
    """PASS case: `Round >= _ROUND_CAP` with an `- Owner decision: <url>`
    line present in the same section."""
    body = (
        f"## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n"
        f"- Round: {round_value}\n- Owner decision: {owner_decision}\n"
    )
    passed, message = gate.check(body, sha)
    assert passed is True, f"expected PASS for body={body!r}, got: {message}"


@_PROPERTIES
@given(sha=_SHAS, round_value=_AT_OR_OVER_CAP_ROUNDS, finding_class=_FINDING_CLASSES)
def test_round_at_or_over_cap_without_owner_decision_always_fails_with_round_cap_message(
    sha: str, round_value: int, finding_class: str
) -> None:
    """FAIL case: `Round >= _ROUND_CAP` with no `- Owner decision:` line --
    the failure message must be the new round-cap message (naming the
    finding class and the recorded round), not a generic one."""
    body = (
        f"## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n"
        f"- Finding class: {finding_class}\n- Round: {round_value}\n"
    )
    passed, message = gate.check(body, sha)
    assert passed is False, f"expected FAIL for body={body!r}, got PASS: {message}"
    assert "not CLEAN" not in message
    assert "stale verdict" not in message
    assert finding_class in message
    assert str(round_value) in message


@_PROPERTIES
@given(sha=_SHAS, round_value=_AT_OR_OVER_CAP_ROUNDS, fence=st.sampled_from(("```", "~~~", "````", "~~~~")))
def test_fenced_round_line_is_never_counted_toward_the_cap(sha: str, round_value: int, fence: str) -> None:
    """Containment (same defeat class as
    `test_a_verdict_inside_a_fenced_code_block_is_never_detected` above,
    applied to the new `Round` field): a `- Round: N` line fenced off as an
    illustrative example is never read as a live value, across generated
    over-cap round values and fence styles/lengths -- confirmed explicitly
    rather than assumed to follow for free from the pre-existing
    `strip_fenced_code_blocks` stripping."""
    body = (
        f"## Independent review verdict\n\n- Verdict: CLEAN\n- Verified commit: {sha}\n"
        f"{fence}\n- Round: {round_value}\n{fence}\n"
    )
    verdict = gate.parse_verdict(body)
    assert verdict.round is None
    passed, message = gate.check(body, sha)
    assert passed is True, f"expected PASS (fenced Round ignored) for body={body!r}, got: {message}"


# Deliberately ASCII letters only, mirroring the field labels this module's
# own five callers of `_field_line_re` actually pass ("Verdict", "Finding
# class", ...) -- this factory's own `re.escape(name)` already makes an
# arbitrary label safe to embed, but a label is never itself Markdown-
# emphasis-wrapped or regex-special in this module's real usage, so testing
# with realistic label shapes (plus a defeat-style regex-metacharacter case
# below) is more informative than an unconstrained alphabet.
_FIELD_NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ", min_size=1, max_size=20)
_BULLET_VALUES = st.text(alphabet=_FIELD_VALUE_ALPHABET, min_size=1, max_size=30).filter(lambda s: s.strip() == s)


@_PROPERTIES
@given(name=_FIELD_NAMES, value=_BULLET_VALUES, bullet=st.sampled_from(("-", "*")), emphasis=st.sampled_from(_EMPHASIS))
def test_field_line_re_matches_its_own_constructed_bullet_line(
    name: str, value: str, bullet: str, emphasis: str
) -> None:
    """`_field_line_re(name, value_pattern)` (the shared factory the
    refactor pass introduced to de-duplicate `_VERDICT_RE`/`_COMMIT_RE`/
    `_FINDING_CLASS_RE`/`_ROUND_RE`/`_OWNER_DECISION_RE`) matches a
    `- <name>: <value>` bullet line it was built to match, across generated
    labels, values, bullet markers, and optional emphasis wrapping --
    confirmed to have teeth: a label typo (`name + "x"`) never matches."""
    pattern = gate._field_line_re(name, r".+?")
    line = f"{bullet} {name}: {emphasis}{value}{emphasis}\n"
    match = pattern.search(line)
    assert match is not None, f"expected a match for line={line!r}"
    assert match.group(1) == value
    assert pattern.search(f"{bullet} {name}x: {value}\n") is None


@_PROPERTIES
@given(name=_FIELD_NAMES)
def test_field_line_re_escapes_regex_metacharacters_in_name(name: str) -> None:
    """A label containing a regex metacharacter (here, appending `.*` --
    matches "anything" if `re.escape` were dropped) is treated literally,
    not as a pattern fragment: only the exact literal label matches."""
    literal_name = f"{name}.*"
    pattern = gate._field_line_re(literal_name, r".+?")
    assert pattern.search(f"- {literal_name}: value\n") is not None
    assert pattern.search(f"- {name}xyz: value\n") is None

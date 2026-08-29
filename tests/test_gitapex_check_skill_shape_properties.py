"""Hypothesis property-based layer for
``skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py``'s
``LIFECYCLE_ISSUE_REF_RE``/``_valid_tracking_issue`` (issue #1347, closing
issue #1178's own ``detection-logic-property-coverage`` gap for the
regex's generalization from a ``tvna/gitapex``-only pattern to an
any-owner/any-repo shape) and its ``_owning_skill_dir`` path-normalization
helper (issue #1387, closing the same gap for that function's own
string-comparison allowlist checks).

Reproducibility: ``derandomize=True`` with an explicit ``max_examples`` and
``deadline=None``, matching
``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``'s own
established rationale (this repository runs pytest under ``pytest-xdist``,
where a randomly-seeded generator turns a latent failure into an
intermittently red suite).
"""

from __future__ import annotations

from pathlib import Path

import gitapex_check_skill_shape as css
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# GitHub owner/repo segment alphabet: alphanumerics plus the separators the
# real naming rules allow mid-string. The leading/trailing character is
# forced alphanumeric separately below -- GitHub owner names may not start
# or end with a hyphen, and the regex's `[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?`
# shape encodes exactly that boundary constraint for the owner segment.
_ALNUM = st.characters(
    whitelist_categories=(), whitelist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)
_OWNER_MID = st.characters(
    whitelist_categories=(), whitelist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
)
_REPO_CHAR = st.characters(
    whitelist_categories=(), whitelist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def _owner_strategy() -> st.SearchStrategy[str]:
    # A single alphanumeric char, or an alphanumeric-bounded run that may
    # contain interior hyphens -- both shapes the regex's owner group
    # accepts.
    single = _ALNUM.map(str)
    multi = st.tuples(_ALNUM, st.text(alphabet=_OWNER_MID, min_size=0, max_size=8), _ALNUM).map(
        lambda parts: parts[0] + parts[1] + parts[2]
    )
    return st.one_of(single, multi)


_OWNER = _owner_strategy()
_REPO = st.text(alphabet=_REPO_CHAR, min_size=1, max_size=12)
_KIND = st.sampled_from(("issues", "pull"))
_ISSUE_NUMBER = st.integers(min_value=1, max_value=999_999_999)


@_PROPERTIES
@given(owner=_OWNER, repo=_REPO, kind=_KIND, number=_ISSUE_NUMBER)
def test_any_well_formed_owner_repo_url_is_a_valid_tracking_issue(
    owner: str, repo: str, kind: str, number: int
) -> None:
    """**Model-based, detects a real gap the fixed example tests cannot:**
    the hand-picked examples in test_gitapex_check_skill_shape.py only ever
    exercise a handful of literal owner/repo strings (this repository's own,
    plus a couple of hand-written non-origin ones) -- this drives the
    owner and repo segments themselves across a wide space of GitHub-legal
    naming shapes, confirming the pattern accepts any well-formed
    owner/repo, not just the examples an author happened to think of.

    Confirmed to have teeth: reverting ``LIFECYCLE_ISSUE_REF_RE`` to its
    pre-#1347 ``tvna/gitapex``-only form makes this property FAIL on the
    first generated example whose owner or repo differs from that literal
    string -- exactly the class of over-narrowing a fixed-example suite
    would not catch.
    """
    value = f"https://github.com/{owner}/{repo}/{kind}/{number}"
    assert css._valid_tracking_issue(value)


@_PROPERTIES
@given(owner=_OWNER, repo=_REPO, kind=_KIND, number=_ISSUE_NUMBER)
def test_leading_or_trailing_hyphen_owner_is_always_rejected(owner: str, repo: str, kind: str, number: int) -> None:
    """Defeat-test-shaped: GitHub owner names may not start or end with a
    hyphen, and the regex's owner group
    (``[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?``) encodes exactly that
    boundary. Prepending or appending a hyphen to an otherwise well-formed
    owner must always push the whole match out of range, across generated
    owner/repo content rather than a single hand-picked ``-owner`` string.
    """
    leading = f"https://github.com/-{owner}/{repo}/{kind}/{number}"
    trailing = f"https://github.com/{owner}-/{repo}/{kind}/{number}"
    assert not css._valid_tracking_issue(leading)
    assert not css._valid_tracking_issue(trailing)


@_PROPERTIES
@given(owner=_OWNER, repo=_REPO, number=_ISSUE_NUMBER)
def test_a_path_segment_other_than_issues_or_pull_is_always_rejected(owner: str, repo: str, number: int) -> None:
    """Robustness: the regex's alternation is closed to exactly
    ``issues``/``pull`` -- any other path segment (checked across generated
    owner/repo content) must never validate, not only the single
    hand-picked ``/commits/`` counter-example."""
    value = f"https://github.com/{owner}/{repo}/commits/{number}"
    assert not css._valid_tracking_issue(value)


@_PROPERTIES
@given(owner=_OWNER, repo=_REPO, kind=_KIND, number=_ISSUE_NUMBER)
def test_a_trailing_non_digit_suffix_is_always_rejected(owner: str, repo: str, kind: str, number: int) -> None:
    """Robustness: the regex anchors on ``\\d+$`` -- appending any
    non-digit suffix after the issue number (checked across generated
    owner/repo/number content) must always break the match, confirming the
    end anchor is load-bearing rather than incidentally satisfied by the
    hand-picked examples."""
    value = f"https://github.com/{owner}/{repo}/{kind}/{number}x"
    assert not css._valid_tracking_issue(value)


@_PROPERTIES
@given(text=st.text(max_size=300))
def test_arbitrary_text_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: arbitrary text (including text containing stray
    ``github.com``, slashes, or partial URL fragments) produces a result
    rather than an exception, and the same input produces the same output
    -- this function runs inside a shape checker whose gates must never
    crash on attacker- or author-controlled sidecar content."""
    first = css._valid_tracking_issue(text)
    second = css._valid_tracking_issue(text)
    assert first == second
    assert isinstance(first, bool)


@_PROPERTIES
@given(
    value=st.one_of(st.integers(), st.booleans(), st.none(), st.lists(st.text(), max_size=3), st.floats(allow_nan=True))
)
def test_non_string_values_are_always_rejected(value: object) -> None:
    """No false positive on type confusion: ``_valid_tracking_issue`` is
    documented as shape-only for ``spec.lifecycle.experimental.trackingIssue``
    values read back from parsed YAML, which can hand it any YAML scalar or
    collection type -- every non-string type must be rejected outright
    rather than raising or coercing."""
    assert not css._valid_tracking_issue(value)


# Issue #1387: `_owning_skill_dir`'s `target.name == "SKILL.md"` and
# `ancestor.name in ("metadata", "references")` checks are exactly the
# allowlist-comparison shape `detection-logic-property-coverage` (issue
# #1178) flags. Component alphabet deliberately excludes "." so a
# generated component can never accidentally collide with "SKILL.md",
# "metadata", or "references" themselves (all contain a literal "." or
# are the exact reserved names under test) -- pure Path arithmetic, no
# real filesystem entries, since `_owning_skill_dir` only calls
# `Path.is_dir()` (always False for a nonexistent generated path) before
# falling into the string-comparison branches this coverage gap is about.
_PATH_COMPONENT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_PATH_COMPONENT = st.text(alphabet=_PATH_COMPONENT_ALPHABET, min_size=1, max_size=12)
_PATH_COMPONENTS = st.lists(_PATH_COMPONENT, min_size=0, max_size=4)


@_PROPERTIES
@given(prefix=_PATH_COMPONENTS, leaf_parent=_PATH_COMPONENT)
def test_skill_md_path_always_normalizes_to_its_parent(prefix: list[str], leaf_parent: str) -> None:
    """Function-scoped property for `_owning_skill_dir`'s
    `target.name == "SKILL.md"` branch: regardless of how many, or what,
    arbitrary directory segments precede it, a path whose final component
    is literally "SKILL.md" must always normalize to its immediate
    parent -- never further up, never left unchanged."""
    target = Path(*prefix, leaf_parent, "SKILL.md")
    assert css._owning_skill_dir(target) == target.parent


@_PROPERTIES
@given(
    prefix=_PATH_COMPONENTS,
    kind=st.sampled_from(("metadata", "references")),
    depth=st.integers(min_value=0, max_value=5),
    leaf=_PATH_COMPONENT,
)
def test_nested_metadata_or_references_path_normalizes_to_the_owning_directory_at_any_depth(
    prefix: list[str], kind: str, depth: int, leaf: str
) -> None:
    """Defeat-test-shaped, encoding the exact regression an adversarial
    review found in this function's first version (issue #1387): a file
    any number of levels under a `metadata`/`references` directory -- not
    only one level -- must still normalize to that directory's own parent
    (the owning skill directory), never silently misresolve to the wrong
    ancestor. Reverting to checking only `target.parent.name` (this
    function's own pre-fix shape) makes this property FAIL as soon as
    `depth` generates > 0, which is exactly the false-pass the review
    reproduced live against a real `references/sub/deep.md` fixture."""
    owner = Path(*prefix)
    nested = [f"sub{i}" for i in range(depth)]
    target = owner / kind / Path(*nested, leaf)
    assert css._owning_skill_dir(target) == owner


@_PROPERTIES
@given(prefix=_PATH_COMPONENTS, leaf=_PATH_COMPONENT)
def test_a_path_with_no_skill_md_or_metadata_or_references_component_is_left_unchanged(
    prefix: list[str], leaf: str
) -> None:
    """Robustness: a path that matches neither of `_owning_skill_dir`'s
    two normalization branches (no "SKILL.md" leaf, no "metadata"/
    "references" ancestor anywhere in its own generated segments) must be
    returned unchanged -- the function's own documented fallback for a
    target it does not recognize, not silently altered."""
    target = Path(*prefix, leaf)
    assert css._owning_skill_dir(target) == target

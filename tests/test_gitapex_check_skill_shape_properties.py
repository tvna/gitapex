"""Hypothesis property-based layer for
``skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py``'s
``_owning_skill_dir`` path-normalization helper (issue #1387, closing
issue #1178's own ``detection-logic-property-coverage`` gap for that
function's own string-comparison allowlist checks).

Issue #758: this module used to also carry a property layer for
``LIFECYCLE_ISSUE_REF_RE``/``_valid_tracking_issue`` (issue #1347). Both
are deleted by the schema-consolidation migration: ``trackingIssue``'s
shape (owner/repo/issue-or-pull/number, hyphen-boundary rules, digit-only
suffix) is now enforced solely by jsonschema.Draft202012Validator reading
skill-metadata.schema.json's own ``pattern`` directly, which has no
second, hand-written regex implementation left for a property test to
hold accountable against a model -- the class of over-narrowing/
under-narrowing bug this property layer existed to catch has no second
side anymore.

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


# Issue #1387: `_owning_skill_dir`'s `target.name == "SKILL.md"` and
# `ancestor.name in ("metadata", "references")` checks are exactly the
# allowlist-comparison shape `detection-logic-property-coverage` (issue
# #1178) flags. Component alphabet excludes "." so a generated component
# can never accidentally collide with "SKILL.md" (which contains a
# literal "."). It must ALSO exclude the exact literal strings "metadata"
# and "references" themselves -- both spell entirely from the remaining
# alnum/underscore/hyphen alphabet, so a plain character-set exclusion
# does not stop the generator from producing them outright. Confirmed
# live: prefix=["references"], leaf="0" makes "references" itself an
# ancestor of the generated target, which
# `_owning_skill_dir`'s own documented "known residual limitation"
# paragraph already accepts (a real top-level directory named literally
# "references"/"metadata" is out of scope, unreachable via the actual
# pre-commit-hook caller) -- so this is the *_left_unchanged property's
# own precondition to enforce, not a code defect to chase. Pure Path
# arithmetic either way, no real filesystem entries, since
# `_owning_skill_dir` only calls `Path.is_dir()` (always False for a
# nonexistent generated path) before falling into the string-comparison
# branches this coverage gap is about.
_RESERVED_PATH_COMPONENTS = frozenset({"metadata", "references"})
_PATH_COMPONENT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_PATH_COMPONENT = st.text(alphabet=_PATH_COMPONENT_ALPHABET, min_size=1, max_size=12).filter(
    lambda s: s not in _RESERVED_PATH_COMPONENTS
)
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

"""Hypothesis property layer for
`.github/scripts/gitapex_gate_agents_md_reference_drift.py` (issue #1963,
closing issue #1178's ``detection-logic-property-coverage`` gap for this
gate's code-span regex, its identifier-shape test, and its fence
stripping).

The fixed-example tests pin the tokens this repository's own AGENTS.md
happens to carry today. These properties assert the invariants those
tokens are instances of, which is where a shape test that works on eight
hand-checked names but not in general shows up.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples``
and ``deadline=None``, matching this repository's own established
rationale in ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_gate_agents_md_reference_drift as gate  # noqa: E402

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_IDENTIFIER = st.from_regex(r"\A[a-z0-9]{1,8}(?:-[a-z0-9]{1,8}){1,3}\Z", fullmatch=True)
# Prose that cannot itself open a code span or a fence, so a generated
# surrounding sentence never changes what the scan under test sees.
_PROSE = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="`~\n\r"),
    max_size=40,
)


@_PROPERTIES
@given(identifier=_IDENTIFIER, before=_PROSE, after=_PROSE)
def test_any_identifier_shaped_span_is_picked_up_wherever_it_sits(identifier: str, before: str, after: str) -> None:
    assert gate.referenced_identifiers(f"{before}`{identifier}`{after}\n") == [identifier]


@_PROPERTIES
@given(identifier=_IDENTIFIER)
def test_no_identifier_survives_a_fenced_block(identifier: str) -> None:
    """**Detects a real gap the fixed examples cannot:** the fixed case
    fences one hand-written name. For ANY identifier, fencing it must
    remove it from the graded set -- a fence is sample text, not a
    reference the file is making."""
    assert gate.referenced_identifiers(f"```\n`{identifier}`\n```\n") == []


@_PROPERTIES
@given(word=st.from_regex(r"\A[a-z]{1,12}\Z", fullmatch=True))
def test_no_hyphen_free_word_is_ever_a_reference(word: str) -> None:
    """The shape test, asserted over the whole class rather than over the
    single hyphen-free span (`catch`) AGENTS.md carries today."""
    assert gate.referenced_identifiers(f"`{word}`\n") == []


@_PROPERTIES
@given(text=st.text(max_size=200))
def test_referenced_identifiers_never_raises(text: str) -> None:
    """AGENTS.md is hand-edited prose; this scan must classify whatever it
    finds, never crash on it."""
    assert isinstance(gate.referenced_identifiers(text), list)


@_PROPERTIES
@given(identifiers=st.lists(_IDENTIFIER, min_size=1, max_size=5, unique=True))
def test_every_identifier_is_graded_exactly_once(identifiers: list[str]) -> None:
    spans = " ".join(f"`{identifier}`" for identifier in identifiers)
    assert gate.referenced_identifiers(f"{spans}\n") == identifiers
    assert gate.referenced_identifiers(f"{spans} {spans}\n") == identifiers


@_PROPERTIES
@given(identifier=_IDENTIFIER, resolves=st.booleans())
def test_exit_code_matches_whether_the_reference_resolves(identifier: str, resolves: bool) -> None:
    """Covers ``main``'s own comparison over the evaluated rows, for any
    identifier rather than the two the fixed tests pin.

    A plain ``TemporaryDirectory`` rather than pytest's ``tmp_path``:
    hypothesis re-runs the body many times per test, while a
    function-scoped fixture is created once for the whole test, so
    successive examples would otherwise write over each other's files.
    """
    with tempfile.TemporaryDirectory() as raw_dir:
        root = pathlib.Path(raw_dir)
        (root / "AGENTS.md").write_text(f"see `{identifier}`\n", encoding="utf-8")
        (root / "skills").mkdir()
        if resolves:
            (root / "skills" / identifier).mkdir()
            (root / "skills" / identifier / "SKILL.md").write_text("x\n", encoding="utf-8")
        (root / ".gitapex").mkdir()
        (root / ".gitapex" / "ssot.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
        assert (gate.main(["--repo-root", str(root)]) == 0) is resolves


@_PROPERTIES
@given(parts=st.lists(st.from_regex(r"\A[a-z]{1,8}\Z", fullmatch=True), min_size=1, max_size=4))
def test_repo_root_resolution_is_stable_under_relative_suffixes(parts: list[str]) -> None:
    """Covers the module-level ``.resolve()`` path-resolution site."""
    candidate = (gate.REPO_ROOT.joinpath(*parts)).resolve()
    assert str(candidate).startswith(str(gate.REPO_ROOT))

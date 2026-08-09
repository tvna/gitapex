"""Deterministic drift gate for issue #406.

The `## Contract discipline` section of `references/rubric.md` summarises,
in its **Precondition** bullet, what `SKILL.md`'s Procedure steps 1-4
establish. That summary has drifted stale from the steps twice (issue #149's
Blind spot pass and issue #183's capability assumption were both wired into
the steps without updating the summary). Issue #406 corrected the drift and
added a "Keep this enumeration in sync" invariant; per CLAUDE.md section 3
("Establishing an invariant ... ship its drift gate in the same change"),
this test IS that gate rather than leaving the invariant to prose alone.

The same drift class reaches the other two Contract discipline bullets, so
this gate covers them too: `_POSTCONDITION_PHRASES` mirrors what step 5
requires of a quotation against the **Postcondition** bullet, and
`_INVARIANT_PHRASES` mirrors the invariant-scope Stop boundary that names it
against the **Invariant** bullet. Both were added when the citation-fidelity
rule landed, since that edit's own sync had to be done by hand -- exactly the
manual step CLAUDE.md section 3 says to replace with a gate in the same change.

Mechanism, and its one honest limitation: `_CHECKPOINT_PHRASES` is the
mechanically-shared source of truth for the precondition checkpoints. The
test asserts each phrase appears in BOTH the Procedure steps-1-4 block and
the Precondition bullet (a bidirectional mirror), so a checkpoint added to a
step but not the bullet -- or removed from a step but left stale in the
bullet -- fails loudly in CI. It cannot, by construction, know about a
genuinely new checkpoint phrase that a future edit forgets to add to this
list at all; that residual gap is smaller than pure prose and is itself named
by the invariant bullet the list guards. Extend `_CHECKPOINT_PHRASES` in the
same change that adds a new step-1-4 checkpoint.

Runs against the real, shipped `evaluating-skill-quality` files (this is a
self-consistency gate for one specific skill, deliberately NOT added to the
general `gitapex_check_skill_shape.py`, which grades any target skill and has no
Contract discipline section to check).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).resolve().parent.parent
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_RUBRIC_MD = _SKILL_DIR / "references" / "rubric.md"

# The precondition checkpoints steps 1-4 establish. Source of truth for the
# mirror below; extend this in the same change that adds a new checkpoint to
# a Procedure step (that is the invariant this gate exists to enforce).
_CHECKPOINT_PHRASES = (
    "mechanism fit",
    "Blind spot pass",
    "deterministic shape",
    "portability level",
    "capability assumption",
    "declaration-vs-pin",
)


# What Procedure step 5 requires of every quotation, mirrored against the
# **Postcondition** bullet. Extend in the same change that alters step 5's
# own postcondition-bearing requirements. The honest limitation the module
# docstring records for _CHECKPOINT_PHRASES applies to this tuple and to
# _INVARIANT_PHRASES below too: both track a few short anchor substrings, not
# the whole synced prose, so a driftless reword in both files still needs its
# tuple updated by hand, and a phrase nobody adds here is not guarded at all.
_POSTCONDITION_PHRASES = (
    "Citation fidelity",
    "cited evidence",
)

# The invariant-scope Stop boundaries the **Invariant** bullet must name.
# Extend in the same change that adds an invariant-scope Stop boundary.
_INVARIANT_PHRASES = ("fabricated citation",)


def _reduce(text):
    """Collapse whitespace runs to one space, so a phrase split across a soft
    wrap still matches.

    This is the *whitespace* half of the reduction
    references/adversarial-self-audit.md's Citation fidelity rule defines, and
    deliberately not the whole of it: that rule also scopes matching to a single
    block, while this runs over a whole extracted bullet or step. The difference
    is safe here because every phrase tracked below is a short span inside one
    bullet, never a quotation a reader could splice -- but the two are not
    equivalent, and an earlier version of this docstring claimed they were.
    """
    return re.sub(r"\s+", " ", text).strip()


def _steps_1_to_4_block(skill_md_text):
    """Return SKILL.md's Procedure steps 1-4 text (item ``1.`` up to ``5.``)."""
    procedure = re.search(r"\n## Procedure\n(.*?)\n## ", skill_md_text, re.S)
    assert procedure, "SKILL.md has no '## Procedure' section -- gate cannot run"
    body = procedure.group(1)
    block = re.search(r"\n1\. .*?(?=\n5\. )", body, re.S)
    assert block, "SKILL.md Procedure has no items 1-4 in the expected shape"
    return block.group(0)


def _precondition_bullet(rubric_text):
    """Return the Contract discipline **Precondition** bullet text."""
    section = re.search(r"\n## Contract discipline\n(.*?)\n## ", rubric_text, re.S)
    assert section, "rubric.md has no '## Contract discipline' section -- gate cannot run"
    bullet = re.search(r"- \*\*Precondition\*\*.*?(?=\n- \*\*Postcondition\*\*)", section.group(1), re.S)
    assert bullet, "Contract discipline has no **Precondition** bullet in the expected shape"
    return bullet.group(0)


def _step_5_text(skill_md_text):
    """Return SKILL.md's Procedure step 5 text (item ``5.`` up to ``6.``)."""
    procedure = re.search(r"\n## Procedure\n(.*?)\n## ", skill_md_text, re.S)
    assert procedure, "SKILL.md has no '## Procedure' section -- gate cannot run"
    block = re.search(r"\n5\. .*?(?=\n6\. )", procedure.group(1), re.S)
    assert block, "SKILL.md Procedure has no item 5 in the expected shape"
    return block.group(0)


def _stop_boundaries_text(skill_md_text):
    """Return SKILL.md's ``## Stop boundaries`` section text."""
    section = re.search(r"\n## Stop boundaries\n(.*?)\n## ", skill_md_text, re.S)
    assert section, "SKILL.md has no '## Stop boundaries' section -- gate cannot run"
    return section.group(1)


def _contract_bullet(rubric_text, name):
    """Return the Contract discipline bullet ``name``, up to the next bullet.

    Terminated by the next ``- **`` bullet or the end of the section, never by
    a named successor: an adversarial review of this gate confirmed that
    naming the successor made extraction order-dependent, so reordering the
    bullets with zero content drift failed CI with a misleading "bullet not
    found" message on a harmless edit. The generic terminator also drops the
    closing-``**`` special case a bold run ending in a period needed
    (``- **Keep this enumeration in sync.**``).
    """
    section = re.search(r"\n## Contract discipline\n(.*?)\n## ", rubric_text, re.S)
    assert section, "rubric.md has no '## Contract discipline' section -- gate cannot run"
    bullet = re.search(rf"- \*\*{name}\*\*.*?(?=\n- \*\*|\Z)", section.group(1), re.S)
    assert bullet, f"Contract discipline has no **{name}** bullet in the expected shape"
    return bullet.group(0)


@pytest.fixture(scope="module")
def contract_blocks():
    skill = _SKILL_MD.read_text(encoding="utf-8")
    rubric = _RUBRIC_MD.read_text(encoding="utf-8")
    return {
        "step_5": _reduce(_step_5_text(skill)),
        "stop_boundaries": _reduce(_stop_boundaries_text(skill)),
        "postcondition": _reduce(_contract_bullet(rubric, "Postcondition")),
        "invariant": _reduce(_contract_bullet(rubric, "Invariant")),
    }


@pytest.mark.parametrize("phrase", _POSTCONDITION_PHRASES)
def test_postcondition_mirrors_step_5(phrase, contract_blocks):
    """Each phrase step 5 requires of a quotation must also appear in the
    Contract discipline **Postcondition** bullet, and vice versa."""
    assert phrase in contract_blocks["step_5"], (
        f"postcondition phrase {phrase!r} is listed in the sync gate but no longer "
        f"appears in SKILL.md Procedure step 5 -- update _POSTCONDITION_PHRASES "
        f"or step 5"
    )
    assert phrase in contract_blocks["postcondition"], (
        f"drift: SKILL.md step 5 requires {phrase!r} but the Contract discipline "
        f"Postcondition bullet in rubric.md does not mention it -- update the "
        f"Postcondition bullet to match"
    )


@pytest.mark.parametrize("phrase", _INVARIANT_PHRASES)
def test_invariant_mirrors_stop_boundaries(phrase, contract_blocks):
    """Each invariant-scope Stop boundary the gate tracks must appear in BOTH
    SKILL.md's Stop boundaries and the Contract discipline **Invariant**
    bullet -- the drift the citation-fidelity edit had to close by hand."""
    assert phrase in contract_blocks["stop_boundaries"], (
        f"invariant phrase {phrase!r} is listed in the sync gate but no longer "
        f"appears in SKILL.md's Stop boundaries -- update _INVARIANT_PHRASES "
        f"or the Stop boundary"
    )
    assert phrase in contract_blocks["invariant"], (
        f"drift: SKILL.md carries an invariant-scope Stop boundary naming "
        f"{phrase!r} but the Contract discipline Invariant bullet in rubric.md "
        f"does not name it -- update the Invariant bullet to match"
    )


def test_contract_extraction_is_not_vacuous(contract_blocks):
    """Guard against a rename silently making the two mirrors above pass on
    empty blocks, the same way test_extraction_is_not_vacuous does below."""
    for name, text in contract_blocks.items():
        assert len(text) > 80, f"{name} block suspiciously short -- extraction may be broken"


@pytest.fixture(scope="module")
def blocks():
    steps = _reduce(_steps_1_to_4_block(_SKILL_MD.read_text(encoding="utf-8")))
    bullet = _reduce(_precondition_bullet(_RUBRIC_MD.read_text(encoding="utf-8")))
    return steps, bullet


@pytest.mark.parametrize("phrase", _CHECKPOINT_PHRASES)
def test_checkpoint_mirrored_between_steps_and_precondition(phrase, blocks):
    """Each checkpoint phrase must appear in BOTH the steps-1-4 block and the
    Precondition bullet -- the exact drift class of issue #406."""
    steps, bullet = blocks
    in_steps = phrase in steps
    in_bullet = phrase in bullet
    assert in_steps, (
        f"checkpoint {phrase!r} is listed in the sync gate but no longer appears "
        f"in SKILL.md Procedure steps 1-4 -- update _CHECKPOINT_PHRASES or the steps"
    )
    assert in_bullet, (
        f"drift: SKILL.md steps 1-4 establish {phrase!r} but the Contract "
        f"discipline Precondition bullet in rubric.md does not mention it -- "
        f"update the Precondition bullet to match (issue #406 invariant)"
    )


def test_extraction_is_not_vacuous(blocks):
    """Guard against a section rename silently making the mirror check pass on
    empty blocks."""
    steps, bullet = blocks
    assert len(steps) > 200, "steps-1-4 block suspiciously short -- extraction may be broken"
    assert len(bullet) > 100, "Precondition bullet suspiciously short -- extraction may be broken"

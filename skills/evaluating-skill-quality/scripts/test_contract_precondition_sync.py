"""Deterministic drift gate for issue #406.

The `## Contract discipline` section of `references/rubric.md` summarises,
in its **Precondition** bullet, what `SKILL.md`'s Procedure steps 1-4
establish. That summary has drifted stale from the steps twice (issue #149's
Blind spot pass and issue #183's capability assumption were both wired into
the steps without updating the summary). Issue #406 corrected the drift and
added a "Keep this enumeration in sync" invariant; per CLAUDE.md section 3
("Establishing an invariant ... ship its drift gate in the same change"),
this test IS that gate rather than leaving the invariant to prose alone.

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
general `check_skill_shape.py`, which grades any target skill and has no
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


@pytest.fixture(scope="module")
def blocks():
    steps = _steps_1_to_4_block(_SKILL_MD.read_text(encoding="utf-8"))
    bullet = _precondition_bullet(_RUBRIC_MD.read_text(encoding="utf-8"))
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

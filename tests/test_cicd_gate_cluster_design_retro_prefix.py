"""Drift gate tying the design doc's retro title-prefix correction note
to the real source of truth (Codex review on PR #362, issue #361).

PR #362 fixed a stale, unmarked directive in
docs/superpowers/specs/2026-07-18-cicd-gate-cluster-design.md that named
the wrong retro title prefix -- but the fix itself just hard-codes the
corrected prefix as prose, a second manually-synchronized copy alongside
the doc's own retro-identity.toml sample and
.github/scripts/post_merge_retro.py's real `_retro_title`. Without a
check tying all three together, a future convention change could leave
the design doc silently stale again -- the exact failure this file's own
commit was repairing. This asserts all three stay in lockstep.
"""

from __future__ import annotations

import pathlib
import re

import post_merge_retro as pmr

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DESIGN_DOC = REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-07-18-cicd-gate-cluster-design.md"


def _real_prefix() -> str:
    """The fixed prefix implied by `_retro_title`, the single source of
    truth `.github/scripts/post_merge_retro.py` already establishes."""
    title = pmr._retro_title(1)
    match = re.match(r"^(.*#)\d+$", title)
    assert match is not None, (
        f"post_merge_retro._retro_title(1) returned {title!r}, which does "
        "not end in '<prefix>#<digits>' as expected -- update this "
        "helper if the title shape changed deliberately."
    )
    return match.group(1)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_correction_note_prefix_matches_real_retro_title():
    text = _normalized(DESIGN_DOC.read_text(encoding="utf-8"))
    match = re.search(
        r"gate 3\(a\) should reserve, if implemented from this doc, is "
        r"`([^`]+)`",
        text,
    )
    assert match is not None, (
        f"{DESIGN_DOC} no longer states the corrected retro title prefix "
        "in its expected sentence shape -- update this test's regex if "
        "the wording changed deliberately, but do not let the assertion "
        "silently stop checking."
    )
    assert match.group(1) == _real_prefix(), (
        f"{DESIGN_DOC}'s correction note states the retro title prefix as "
        f"{match.group(1)!r}, but post_merge_retro.py's `_retro_title` "
        f"(the real source of truth) implies {_real_prefix()!r} instead -- "
        "these must stay in lockstep or the design doc drifts stale "
        "again, the exact failure issue #361/PR #362 fixed."
    )


def test_toml_sample_title_prefixes_matches_real_retro_title():
    text = DESIGN_DOC.read_text(encoding="utf-8")
    match = re.search(r'title_prefixes\s*=\s*\["([^"]+)"\]', text)
    assert match is not None, (
        f"{DESIGN_DOC} no longer has a `title_prefixes = [...]` sample line in its retro-identity.toml block."
    )
    assert match.group(1) == _real_prefix(), (
        f"{DESIGN_DOC}'s retro-identity.toml sample states "
        f"title_prefixes as {match.group(1)!r}, but post_merge_retro.py's "
        f"`_retro_title` implies {_real_prefix()!r} instead."
    )

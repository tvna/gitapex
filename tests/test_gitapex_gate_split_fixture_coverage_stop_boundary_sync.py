"""CI gate: Check E's Stop-boundary bullet identity
(gitapex_gate_split_fixture_coverage.stop_boundary_identity_counter)
must stay in exact agreement with the `#49` gate's own
(gitapex_gate_skill_branch_fixture_coverage.stop_boundary_bullet_counter)
that Check E's own docstring already claims to mirror.

Issue #192 item 6's design deliberately duplicates this identity logic
rather than importing across the two independent `.github/scripts/`
gates (see gitapex_gate_split_fixture_coverage.py's own module-docstring
paragraph on why each `.github/scripts/` file stays self-contained). That
duplication is exactly the drift risk this repository's own dimension-12
gate-quality rubric flags: nothing previously re-verified that the two
independently-maintained copies still agree on what counts as "the same
Stop-boundary bullet" after an edit to either one -- found during the
issue #192 step 8 adversarial (gate-quality specialist) review of this
gate. A silent drift here would let Check E resolve an `exercises` label
against a bullet the `#49` gate's own delta-scoping counts differently
(or not at all), defeating the "identical identity convention" guarantee
`stop_boundary_identity_counter`'s own docstring already claims.
"""

from __future__ import annotations

import pathlib
from collections import Counter

import gitapex_gate_skill_branch_fixture_coverage as gate_49
import gitapex_gate_split_fixture_coverage as gate_e

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_REAL_SKILL_MD_FILES = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))

# Synthetic edge cases exercising the identity logic's own known-tricky
# corners -- nested code fences (the CommonMark nesting rule both gates'
# fence-blanking helpers implement independently), multiple Stop-boundary
# headings, a heading-level variation, and CRLF line endings.
_SYNTHETIC_CASES = [
    ("empty", ""),
    ("no stop boundary section at all", "## Procedure\n\n1. Do a thing.\n"),
    (
        "single stop boundary bullet",
        "## Stop boundary\n\n- Never do the dangerous thing.\n",
    ),
    (
        "stop boundaries plural heading, multiple bullets",
        "## Stop boundaries\n\n- Never do the first dangerous thing.\n- Never do the second.\n",
    ),
    (
        "deeper heading level",
        "#### Stop boundary\n\n- Never do the thing, even at heading level 4.\n",
    ),
    (
        "two separate stop boundary sections",
        "## Stop boundary\n\n- First section's own bullet.\n\n"
        "## Notes\n\nprose in between.\n\n"
        "## Stop boundaries\n\n- Second section's own bullet.\n",
    ),
    (
        "bullet inside a fenced code block is not counted",
        "## Stop boundary\n\n```\n- This is inside a fence, illustrative only.\n```\n\n- This one is real.\n",
    ),
    (
        "nested fence: an inner 3-backtick line does not close an outer 4-backtick fence",
        "## Stop boundary\n\n````\n```\n- Still fenced, still illustrative.\n```\n````\n\n- This one is real.\n",
    ),
    (
        "duplicate bullet text counts as a multiset, not deduped",
        "## Stop boundary\n\n- Never do the same thing.\n- Never do the same thing.\n",
    ),
    (
        "CRLF line endings normalize the same as LF",
        "## Stop boundary\r\n\r\n- Never do the thing, with CRLF endings.\r\n",
    ),
    (
        "case-insensitive heading text",
        "## sTOP bOUNDARY\n\n- Never do the thing, oddly cased heading.\n",
    ),
    (
        "indented bullet (not column-0) is not counted",
        "## Stop boundary\n\n  - Indented, not top-level.\n",
    ),
]


def _as_pairs(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items())


def test_real_skill_md_files_agree_between_both_gates() -> None:
    assert _REAL_SKILL_MD_FILES, f"expected to find at least one skills/*/SKILL.md under {REPO_ROOT / 'skills'}"
    mismatches: list[tuple[pathlib.Path, list[tuple[str, int]], list[tuple[str, int]]]] = []
    for path in _REAL_SKILL_MD_FILES:
        text = path.read_text(encoding="utf-8")
        check_e = gate_e.stop_boundary_identity_counter(text)
        gate_49_counter = gate_49.stop_boundary_bullet_counter(text)
        if check_e != gate_49_counter:
            mismatches.append((path.relative_to(REPO_ROOT), _as_pairs(check_e), _as_pairs(gate_49_counter)))
    assert not mismatches, (
        "Check E's stop_boundary_identity_counter has diverged from the #49 gate's own "
        "stop_boundary_bullet_counter for these real SKILL.md files:\n"
        + "\n".join(f"  - {p}: Check E={ce!r} vs #49={c49!r}" for p, ce, c49 in mismatches)
    )


def test_synthetic_edge_cases_agree_between_both_gates() -> None:
    mismatches: list[tuple[str, list[tuple[str, int]], list[tuple[str, int]]]] = []
    for label, text in _SYNTHETIC_CASES:
        check_e = gate_e.stop_boundary_identity_counter(text)
        gate_49_counter = gate_49.stop_boundary_bullet_counter(text)
        if check_e != gate_49_counter:
            mismatches.append((label, _as_pairs(check_e), _as_pairs(gate_49_counter)))
    assert not mismatches, (
        "Check E's stop_boundary_identity_counter has diverged from the #49 gate's own "
        "stop_boundary_bullet_counter for these synthetic cases:\n"
        + "\n".join(f"  - {label!r}: Check E={ce!r} vs #49={c49!r}" for label, ce, c49 in mismatches)
    )

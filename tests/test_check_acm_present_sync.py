"""CI gate: every check_acm_present.py-shaped script under skills/*/scripts/
shares the same Acceptance Criteria Map header regex.

drafting-an-acm-issue and issue-to-branch each ship an independent copy of
check_acm_present.py (no skill in this repository shares a scripts/
directory with another). Both copies' own docstrings say the ACM table's
header regex must be updated together, but nothing enforced that until
now -- a PR editing one copy's header shape could merge green while the
other copy silently kept checking the old shape. This closes that gap
(PR #238 retrospective, issue #242, repair 5; tracked as issue #245).
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# Marker a diverging copy's source can carry to opt out of the sync
# requirement for a deliberate, reviewed divergence. Must appear in both
# copies being compared, not just one -- an unmarked copy stays a failure.
DIVERGED_MARKER = "intentionally diverged"

# Guards against the discovery glob silently finding nothing (a moved
# skills/ directory, a renamed script) and this test then vacuously
# passing. There are 2 known copies today (drafting-an-acm-issue,
# issue-to-branch); the floor matches that exactly so a copy going
# missing is caught, not just a wholesale discovery failure.
MIN_EXPECTED_COPIES = 2


def _discover_acm_checker_scripts() -> list[pathlib.Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(SKILLS_DIR.glob("*/scripts/check_acm_present.py"))


ACM_CHECKER_SCRIPTS = _discover_acm_checker_scripts()


def _load_module(path: pathlib.Path) -> types.ModuleType:
    # Unique module name per path -- every copy is literally named
    # check_acm_present.py, so importing by filename alone would collide.
    module_name = f"_check_acm_present_sync__{path.parent.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovery_found_the_expected_number_of_copies():
    assert len(ACM_CHECKER_SCRIPTS) >= MIN_EXPECTED_COPIES, (
        f"expected at least {MIN_EXPECTED_COPIES} check_acm_present.py "
        f"copies under {SKILLS_DIR}, found {len(ACM_CHECKER_SCRIPTS)}: "
        f"{[str(p.relative_to(REPO_ROOT)) for p in ACM_CHECKER_SCRIPTS]}. "
        "This usually means discovery is broken (moved skills/ directory, "
        "renamed script), not that copies were actually removed."
    )


def test_all_copies_expose_a_header_regex():
    missing = [
        p for p in ACM_CHECKER_SCRIPTS
        if not isinstance(getattr(_load_module(p), "_HEADER_RE", None), re.Pattern)
    ]
    assert not missing, (
        "these check_acm_present.py copies have no module-level _HEADER_RE "
        f"compiled pattern: {[str(p.relative_to(REPO_ROOT)) for p in missing]}"
    )


def test_header_regex_stays_in_sync_across_all_copies():
    by_path = {p: _load_module(p)._HEADER_RE for p in ACM_CHECKER_SCRIPTS}
    patterns = {p: (rx.pattern, rx.flags) for p, rx in by_path.items()}
    distinct = set(patterns.values())
    if len(distinct) <= 1:
        return

    unmarked_diverging = [
        p for p in ACM_CHECKER_SCRIPTS
        if DIVERGED_MARKER not in p.read_text(encoding="utf-8").lower()
    ]
    if not unmarked_diverging:
        return

    diffs = "\n".join(
        f"  - {p.relative_to(REPO_ROOT)}: {pattern!r}"
        for p, (pattern, _flags) in patterns.items()
    )
    assert not unmarked_diverging, (
        "check_acm_present.py copies' _HEADER_RE patterns have diverged "
        f"without an '{DIVERGED_MARKER}' marker comment in every copy:\n"
        f"{diffs}\n"
        "If this divergence is deliberate and reviewed, add a comment "
        f"containing '{DIVERGED_MARKER}' to every diverging copy explaining "
        "why; otherwise update both copies' header regex together."
    )

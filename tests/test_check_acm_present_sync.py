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

import collections
import functools
import importlib.util
import pathlib
import re
import types

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# Marker a diverging copy's source can carry to opt out of the sync
# requirement for a deliberate, reviewed divergence. Must appear as its own
# comment line in every copy that diverges from the consensus pattern -- an
# unmarked diverging copy stays a failure. Anchored to a `#`-prefixed line
# (not a bare substring anywhere in the file) so the marker can't be
# satisfied by accident -- e.g. by prose in a docstring that merely
# discusses or warns against divergence.
_MARKER_RE = re.compile(r"^\s*#.*\bintentionally diverged\b", re.IGNORECASE | re.MULTILINE)

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


@functools.lru_cache(maxsize=None)
def _load_module(path: pathlib.Path) -> types.ModuleType:
    # Cached -- every test function below needs each copy's module, and
    # without caching each would re-read and re-exec the same file from
    # disk independently. Unique module name per path -- every copy is
    # literally named check_acm_present.py, so importing by filename alone
    # would collide.
    module_name = f"_check_acm_present_sync__{path.parent.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_diverged_marker(path: pathlib.Path) -> bool:
    return bool(_MARKER_RE.search(path.read_text(encoding="utf-8")))


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
    patterns = {
        p: (_load_module(p)._HEADER_RE.pattern, _load_module(p)._HEADER_RE.flags)
        for p in ACM_CHECKER_SCRIPTS
    }
    counts = collections.Counter(patterns.values())
    if len(counts) <= 1:
        return

    # The consensus is whichever pattern the most copies share; only copies
    # that disagree with it need the marker -- not every copy in the repo.
    # A tie for most-common leaves no single baseline to diverge from, so
    # every copy is treated as diverging rather than guessing which side is
    # "correct".
    max_count = max(counts.values())
    consensus_candidates = [pat for pat, count in counts.items() if count == max_count]
    if len(consensus_candidates) == 1:
        (consensus,) = consensus_candidates
        diverging = [p for p, pat in patterns.items() if pat != consensus]
    else:
        diverging = list(ACM_CHECKER_SCRIPTS)

    unmarked_diverging = [p for p in diverging if not _has_diverged_marker(p)]
    if not unmarked_diverging:
        return

    diffs = "\n".join(
        f"  - {p.relative_to(REPO_ROOT)}: {patterns[p][0]!r}" for p in diverging
    )
    assert not unmarked_diverging, (
        "check_acm_present.py copies' _HEADER_RE patterns have diverged from "
        "the consensus pattern without a '# ... intentionally diverged ...' "
        f"marker comment in every diverging copy:\n{diffs}\n"
        "If this divergence is deliberate and reviewed, add a comment "
        "containing 'intentionally diverged' to every diverging copy "
        "explaining why; otherwise update the copies' header regex to match."
    )

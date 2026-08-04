"""CI gate: every script that checks for the Acceptance Criteria Map
header shares the same regex for it.

drafting-an-acm-issue and planning-a-branch-from-an-issue each ship an independent copy of
check_acm_present.py (no skill in this repository shares a scripts/
directory with another). Both copies' own docstrings say the ACM table's
header regex must be updated together, but nothing enforced that until
now -- a PR editing one copy's header shape could merge green while the
other copy silently kept checking the old shape. This closes that gap
(PR #238 retrospective, issue #242, repair 5; tracked as issue #245).

.github/scripts/gate_acm_issue_disclosure.py (issue #414) is a third,
differently-named, differently-located copy of the same header check
(plus its own additional waiver vocabulary, out of this test's scope) --
added to `_EXTRA_ACM_CHECKER_SCRIPTS` explicitly below rather than
matched by the skills/*/scripts/ glob, per a Codex review finding on PR
#425 that this drift gate would otherwise miss it silently.

hooks/check_acm_present_or_waiver.py (issue #413) is a fourth copy, for
the same reason: a Codex review on PR #433 found that the PreToolUse
hook cannot depend on .github/scripts/gate_acm_issue_disclosure.py
(never deployed with the plugin, per docs/repository-layout.md), so it
carries its own self-contained copy of the header regex bundled beside
the hook script itself. Also added to `_EXTRA_ACM_CHECKER_SCRIPTS`
explicitly, same reasoning as the third copy above.

Waiver vocabulary (issue #657) is a narrower, separate claim from the
above: only the third and fourth copies -- .github/scripts/gate_acm_issue_disclosure.py
and hooks/check_acm_present_or_waiver.py -- implement `_ACM_WAIVER_RE` at
all. The two skills/*/scripts/check_acm_present.py copies check the ACM
*table*'s presence only; neither skill they belong to accepts a waiver in
lieu of the table, so no waiver concept exists in either file, by design.
`test_waiver_regex_stays_in_sync_between_the_two_copies_that_define_one`
below is therefore scoped to exactly those two files -- not the full
`ACM_CHECKER_SCRIPTS` discovery list the header-regex tests above use --
and is a *new* gate: prior to issue #657, nothing kept the two files'
`_ACM_WAIVER_RE` patterns in sync at all.
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

# Explicit extra copies that the skills/*/scripts/ glob below cannot find
# (different filename, different directory). Each entry's own module must
# still expose a module-level `_HEADER_RE` for test_all_copies_expose_a_header_regex
# and test_header_regex_stays_in_sync_across_all_copies to pick it up.
_EXTRA_ACM_CHECKER_SCRIPTS = (
    REPO_ROOT / ".github" / "scripts" / "gate_acm_issue_disclosure.py",
    REPO_ROOT / "hooks" / "check_acm_present_or_waiver.py",
)

# Guards against discovery silently finding nothing (a moved skills/
# directory, a renamed script) and this test then vacuously passing.
# There are 4 known copies today (drafting-an-acm-issue,
# planning-a-branch-from-an-issue, gate_acm_issue_disclosure.py, and
# hooks/check_acm_present_or_waiver.py); the floor matches that exactly so
# a copy going missing is caught, not just a wholesale discovery failure.
MIN_EXPECTED_COPIES = 4


def _discover_acm_checker_scripts() -> list[pathlib.Path]:
    glob_matches = SKILLS_DIR.glob("*/scripts/check_acm_present.py") if SKILLS_DIR.is_dir() else []
    return sorted({*glob_matches, *(p for p in _EXTRA_ACM_CHECKER_SCRIPTS if p.is_file())})


ACM_CHECKER_SCRIPTS = _discover_acm_checker_scripts()


@functools.cache
def _load_module(path: pathlib.Path) -> types.ModuleType:
    # Cached -- every test function below needs each copy's module, and
    # without caching each would re-read and re-exec the same file from
    # disk independently. Unique module name per path -- every copy is
    # literally named check_acm_present.py, so importing by filename alone
    # would collide.
    module_name = f"_check_acm_present_sync__{path.parent.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"could not build a module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_diverged_marker(path: pathlib.Path) -> bool:
    return bool(_MARKER_RE.search(path.read_text(encoding="utf-8")))


def test_discovery_found_the_expected_number_of_copies():
    assert len(ACM_CHECKER_SCRIPTS) >= MIN_EXPECTED_COPIES, (
        f"expected at least {MIN_EXPECTED_COPIES} ACM-header-checking copies "
        f"under {SKILLS_DIR} plus {_EXTRA_ACM_CHECKER_SCRIPTS}, found "
        f"{len(ACM_CHECKER_SCRIPTS)}: "
        f"{[str(p.relative_to(REPO_ROOT)) for p in ACM_CHECKER_SCRIPTS]}. "
        "This usually means discovery is broken (moved skills/ directory, "
        "renamed script), not that copies were actually removed."
    )


def test_all_copies_expose_a_header_regex():
    missing = [
        p for p in ACM_CHECKER_SCRIPTS if not isinstance(getattr(_load_module(p), "_HEADER_RE", None), re.Pattern)
    ]
    assert not missing, (
        "these check_acm_present.py copies have no module-level _HEADER_RE "
        f"compiled pattern: {[str(p.relative_to(REPO_ROOT)) for p in missing]}"
    )


def test_header_regex_stays_in_sync_across_all_copies():
    patterns = {p: (_load_module(p)._HEADER_RE.pattern, _load_module(p)._HEADER_RE.flags) for p in ACM_CHECKER_SCRIPTS}
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

    diffs = "\n".join(f"  - {p.relative_to(REPO_ROOT)}: {patterns[p][0]!r}" for p in diverging)
    assert not unmarked_diverging, (
        "check_acm_present.py copies' _HEADER_RE patterns have diverged from "
        "the consensus pattern without a '# ... intentionally diverged ...' "
        f"marker comment in every diverging copy:\n{diffs}\n"
        "If this divergence is deliberate and reviewed, add a comment "
        "containing 'intentionally diverged' to every diverging copy "
        "explaining why; otherwise update the copies' header regex to match."
    )


# ---------------------------------------------------------------------------
# Waiver vocabulary (_ACM_WAIVER_RE) sync -- issue #657. Deliberately scoped
# to just the two files that actually define this regex (see this module's
# own docstring), not the 4-copy ACM_CHECKER_SCRIPTS discovery list above,
# which is about _HEADER_RE only.
# ---------------------------------------------------------------------------

_WAIVER_REGEX_SCRIPTS = (
    REPO_ROOT / ".github" / "scripts" / "gate_acm_issue_disclosure.py",
    REPO_ROOT / "hooks" / "check_acm_present_or_waiver.py",
)


def test_both_waiver_scripts_expose_a_waiver_regex():
    missing = [
        p for p in _WAIVER_REGEX_SCRIPTS if not isinstance(getattr(_load_module(p), "_ACM_WAIVER_RE", None), re.Pattern)
    ]
    assert not missing, (
        "these files are expected to expose a module-level _ACM_WAIVER_RE "
        f"compiled pattern but do not: {[str(p.relative_to(REPO_ROOT)) for p in missing]}"
    )


def test_waiver_regex_stays_in_sync_between_the_two_copies_that_define_one():
    gate_module = _load_module(_WAIVER_REGEX_SCRIPTS[0])
    hook_module = _load_module(_WAIVER_REGEX_SCRIPTS[1])
    gate_pattern = (gate_module._ACM_WAIVER_RE.pattern, gate_module._ACM_WAIVER_RE.flags)
    hook_pattern = (hook_module._ACM_WAIVER_RE.pattern, hook_module._ACM_WAIVER_RE.flags)
    assert gate_pattern == hook_pattern, (
        "_ACM_WAIVER_RE has diverged between "
        f"{_WAIVER_REGEX_SCRIPTS[0].relative_to(REPO_ROOT)} "
        f"({gate_pattern[0]!r}) and "
        f"{_WAIVER_REGEX_SCRIPTS[1].relative_to(REPO_ROOT)} ({hook_pattern[0]!r}). "
        "Both must accept the exact same waiver vocabulary -- update the "
        "one that changed to match the other."
    )

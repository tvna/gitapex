"""CI gate: the two Conventional-Commits PR-title checkers share one regex.

Issue #1058 ships two independent copies of the same
CONVENTIONAL_COMMIT_RE, by design (docs/repository-layout.md: only
skills/ and hooks/ are deployed when this repository ships as a plugin,
so hooks/gitapex_check_pr_title_convention.py cannot import
.github/scripts/gitapex_gate_pr_title_convention.py, and the CI script
stays standalone for the same reason in the other direction -- see both
files' own docstrings). Nothing enforces the two patterns staying
identical except this test, the same shape as
tests/test_gitapex_check_acm_present_sync.py's own header-regex sync gate
for the ACM checker family.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

HOOK_COPY = REPO_ROOT / "hooks" / "gitapex_check_pr_title_convention.py"
CI_COPY = REPO_ROOT / ".github" / "scripts" / "gitapex_gate_pr_title_convention.py"


def _load_module(path: pathlib.Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"could not load a module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_copies_exist() -> None:
    assert HOOK_COPY.is_file(), f"expected {HOOK_COPY} to exist"
    assert CI_COPY.is_file(), f"expected {CI_COPY} to exist"


def test_both_copies_expose_conventional_commit_re() -> None:
    hook_module = _load_module(HOOK_COPY, "_pr_title_sync__hook")
    ci_module = _load_module(CI_COPY, "_pr_title_sync__ci")
    assert hasattr(hook_module, "CONVENTIONAL_COMMIT_RE")
    assert hasattr(ci_module, "CONVENTIONAL_COMMIT_RE")


def test_conventional_commit_regex_stays_in_sync_between_the_two_copies() -> None:
    hook_module = _load_module(HOOK_COPY, "_pr_title_sync__hook_pattern")
    ci_module = _load_module(CI_COPY, "_pr_title_sync__ci_pattern")
    assert hook_module.CONVENTIONAL_COMMIT_RE.pattern == ci_module.CONVENTIONAL_COMMIT_RE.pattern, (
        "hooks/gitapex_check_pr_title_convention.py and "
        ".github/scripts/gitapex_gate_pr_title_convention.py's CONVENTIONAL_COMMIT_RE "
        "patterns have drifted apart -- update both together (issue #1058)"
    )
    # `.pattern` equality alone would still pass if one copy added a flag
    # (e.g. re.IGNORECASE) the other lacks -- same string, different
    # matching behavior. Caught by review on PR #1059.
    assert hook_module.CONVENTIONAL_COMMIT_RE.flags == ci_module.CONVENTIONAL_COMMIT_RE.flags, (
        "hooks/gitapex_check_pr_title_convention.py and "
        ".github/scripts/gitapex_gate_pr_title_convention.py's CONVENTIONAL_COMMIT_RE "
        "flags have drifted apart -- update both together (issue #1058)"
    )

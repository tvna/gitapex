#!/usr/bin/env python3
"""Differential output-diff oracle for the gitapex_check_skill_shape.py ->
shape_checks/ package split (issue #1330 ACM row 1).

Runs check_shape() from the pre-refactor OLD gitapex_check_skill_shape.py
(the single-file version at this branch's own BASE commit, fetched via
`git show` and imported standalone -- it is stdlib-only, so this works with
no shape_checks/ package context at all) and from the NEW (refactored,
shape_checks/-backed) version, over every skills/*/SKILL.md in this
repository, and asserts the two returned CheckResult lists are identical
(same check name, passed, rule, and evidence, in the same order) for every
skill directory.

This is the mechanical-move proof the refactor's own task description
requires: the split must be a pure code-motion with zero detection-logic
change, and this script is the live-artifact evidence for that claim (not a
proxy such as a green type-check or a passing unit-test suite alone -- see
CLAUDE.md's Decision 1 gate-completion rule). A real difference reported
here is a genuine regression introduced by the move, not a problem with this
script -- fix the move, not this comparison.

The one way to silently defeat this oracle is to point BASE_SHA at a
POST-split commit. The "OLD" module fetched from such a commit is itself
shape_checks/-backed, and its own `from shape_checks... import ...` lines
resolve against the very same live, on-disk package "NEW" uses (this
script's own directory is on sys.path), so the comparison degenerates to
comparing the working tree against itself and passes no matter how badly
detection has regressed. Reproduced live, not theorized: a deliberate
evidence-string regression injected into shape_checks/orchestrator.py makes
this script report all 29 skills differing at the real BASE_SHA, and report
a clean PASS the moment BASE_SHA is moved to a post-split commit.
``_assert_pre_split_source`` below closes that hole by refusing any fetched
OLD source that imports shape_checks at all.

Usage:
  python3 skills/evaluating-skill-quality/scripts/verify_shape_check_output_diff.py

Exit code: 0 if every skill's OLD and NEW check_shape() output is identical,
1 if any difference is found or a skill could not be checked under either
version.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import types
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# This branch's own BASE commit (issue #1330 ACM row 1's task dispatch), the
# pre-refactor single-file gitapex_check_skill_shape.py's last-known-good
# revision -- not a moving ref, so a rebase/force-push of this branch cannot
# silently change what "OLD" means for this comparison.
BASE_SHA = "635ff313b068c2154e0a5f8e8a9fbe7f64031d93"
REPO_ROOT = Path(__file__).resolve().parents[3]
NEW_SCRIPTS_DIR = Path(__file__).resolve().parent
# Repo-relative so it works the same from `git show BASE:<path>` regardless
# of REPO_ROOT's own absolute location on disk.
OLD_RELATIVE_PATH = "skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py"
# The marker that tells a genuinely pre-split OLD source apart from a
# post-split one: the pre-split checker is a single stdlib-only file that
# never mentions the shape_checks package, while every post-split revision
# of the same path imports it. Matched as an import statement rather than a
# bare substring so a future prose mention of the name in a comment or
# docstring cannot trip the guard -- it is specifically the IMPORT that
# makes this script's comparison vacuous (see the module docstring).
_SHAPE_CHECKS_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+shape_checks\b", re.MULTILINE)


def _load_module_from_source(module_name: str, source_path: Path) -> types.ModuleType:
    """Import `source_path` as a standalone module named `module_name`,
    independent of whatever is already on sys.path or in sys.modules under
    that name. Used for both the OLD (temp-file, no package context) and
    NEW (real on-disk shape_checks/-backed) gitapex_check_skill_shape.py, so
    neither import can shadow or contaminate the other."""
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _assert_pre_split_source(source: str) -> None:
    """Fail loudly when the source fetched for "OLD" is not the pre-split,
    self-contained single-file checker.

    Without this, pointing BASE_SHA at any post-split commit silently turns
    this whole script into a no-op: that revision's own
    ``from shape_checks... import ...`` lines resolve against the same live,
    on-disk package the NEW module uses, so OLD and NEW run identical code
    and agree unconditionally -- a green PASS that proves nothing. A gate
    that cannot fail is worse than no gate, so this raises rather than
    warning or degrading to a partial comparison."""
    if _SHAPE_CHECKS_IMPORT_RE.search(source):
        raise RuntimeError(
            f"the source fetched from BASE_SHA={BASE_SHA} imports the shape_checks package, so it is a "
            f"POST-split revision of {OLD_RELATIVE_PATH}, not the pre-split single-file checker this "
            "comparison needs. Its imports would resolve against the same live package the NEW module "
            "uses, making every comparison below vacuously identical. Point BASE_SHA at a commit that "
            "predates the shape_checks/ split instead."
        )


def _load_old_module(tmp_dir: Path) -> types.ModuleType:
    """The pre-refactor, single-file gitapex_check_skill_shape.py exactly as
    it stood at this branch's own BASE commit -- fetched via `git show`
    rather than trusting whatever now sits on disk at that path, and written
    to a temp file so it imports with no shape_checks/ package on its own
    sys.path (it needs none: the pre-refactor file is fully stdlib-only)."""
    result = subprocess.run(  # noqa: S603
        ["git", "show", f"{BASE_SHA}:{OLD_RELATIVE_PATH}"],  # noqa: S607
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    # Checked BEFORE the source is written or imported: a post-split source
    # would otherwise pull the live shape_checks package in on import and
    # make the whole comparison vacuous (see _assert_pre_split_source).
    _assert_pre_split_source(result.stdout)
    old_source_path = tmp_dir / "gitapex_check_skill_shape_old.py"
    old_source_path.write_text(result.stdout, encoding="utf-8")
    return _load_module_from_source("gitapex_check_skill_shape_old", old_source_path)


def _load_new_module() -> types.ModuleType:
    """The refactored, shape_checks/-backed gitapex_check_skill_shape.py as
    it actually sits on disk right now. NEW_SCRIPTS_DIR (this script's own
    directory) is prepended to sys.path first so `from shape_checks import
    ...`/`import shape_checks.x` resolve as the sibling package, the same
    way a direct `python3 gitapex_check_skill_shape.py` invocation and
    pytest's own pythonpath ini option both already resolve it."""
    if str(NEW_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(NEW_SCRIPTS_DIR))
    return _load_module_from_source("gitapex_check_skill_shape_new", NEW_SCRIPTS_DIR / "gitapex_check_skill_shape.py")


def _result_tuples(results: Iterable[Any]) -> list[tuple[str, bool, str, str]]:
    """A CheckResult list reduced to plain (name, passed, rule, evidence)
    tuples -- comparable across the OLD and NEW modules' own, separately
    defined CheckResult dataclasses (equal fields, but not the same class
    object, so a direct dataclass `==` would spuriously report every result
    as different). Typed ``Iterable[Any]`` rather than ``list[CheckResult]``
    deliberately: OLD and NEW each carry their own, separately imported
    CheckResult class (see module docstring), so there is no single type to
    name here -- only their shared, duck-typed attribute shape matters."""
    return [(r.name, r.passed, r.rule, r.evidence) for r in results]


def main() -> int:
    skill_md_paths = sorted(REPO_ROOT.glob("skills/*/SKILL.md"))
    if not skill_md_paths:
        print("FAIL: found zero skills/*/SKILL.md under this repository -- nothing to compare.")
        return 1

    with tempfile.TemporaryDirectory(prefix="verify-shape-check-output-diff-") as tmp:
        old_css = _load_old_module(Path(tmp))
        new_css = _load_new_module()

        failures: list[str] = []
        for skill_md in skill_md_paths:
            skill_label = skill_md.parent.name
            try:
                old_results = _result_tuples(old_css.check_shape(skill_md))
            except Exception as exc:  # broad on purpose: report as a diff, not a crash
                failures.append(f"{skill_label}: OLD check_shape() raised {exc!r}")
                continue
            try:
                new_results = _result_tuples(new_css.check_shape(skill_md))
            except Exception as exc:  # broad on purpose: report as a diff, not a crash
                failures.append(f"{skill_label}: NEW check_shape() raised {exc!r}")
                continue

            if old_results != new_results:
                old_only = [r for r in old_results if r not in new_results]
                new_only = [r for r in new_results if r not in old_results]
                detail = [f"{skill_label}: OLD and NEW check_shape() output differs."]
                if len(old_results) != len(new_results):
                    detail.append(f"  result count: OLD={len(old_results)} NEW={len(new_results)}")
                for r in old_only:
                    detail.append(f"  OLD only: {r}")
                for r in new_only:
                    detail.append(f"  NEW only: {r}")
                failures.append("\n".join(detail))

        print(
            f"Compared check_shape() output for {len(skill_md_paths)} skills (BASE={BASE_SHA[:12]} vs. working tree)."
        )
        if failures:
            print(f"\nFAIL: {len(failures)} skill(s) differ:\n")
            for failure in failures:
                print(failure)
                print()
            return 1

        print(f"PASS: all {len(skill_md_paths)} skills produced identical OLD/NEW check_shape() output.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

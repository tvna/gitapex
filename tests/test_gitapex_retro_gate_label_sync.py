"""CI gate: the two `gate-proposal` label copies share one literal string.

Issue #1406 ships two independent copies of the same `GATE_PROPOSAL_LABEL`,
by design (docs/repository-layout.md: only skills/ and hooks/ are deployed
when this repository ships as a plugin, so
skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py cannot be
imported by .github/scripts/gitapex_scan_retrospective_gate_drift.py, and
the CI script stays standalone for the same reason in the other direction
-- see both files' own docstrings). Nothing enforces the two literals
staying identical except this test, the same shape as
tests/test_gitapex_pr_title_convention_regex_sync.py's own regex sync gate
for the PR-title checker family.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

SKILL_COPY = REPO_ROOT / "skills" / "merge-retrospective" / "scripts" / "gitapex_file_gate_proposal.py"
CI_COPY = REPO_ROOT / ".github" / "scripts" / "gitapex_scan_retrospective_gate_drift.py"


def _load_module(path: pathlib.Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"could not load a module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_copies_exist() -> None:
    assert SKILL_COPY.is_file(), f"expected {SKILL_COPY} to exist"
    assert CI_COPY.is_file(), f"expected {CI_COPY} to exist"


def test_both_copies_expose_gate_proposal_label() -> None:
    skill_module = _load_module(SKILL_COPY, "_retro_gate_label_sync__skill")
    ci_module = _load_module(CI_COPY, "_retro_gate_label_sync__ci")
    assert hasattr(skill_module, "GATE_PROPOSAL_LABEL")
    assert hasattr(ci_module, "GATE_PROPOSAL_LABEL")


def test_gate_proposal_label_stays_in_sync_between_the_two_copies() -> None:
    skill_module = _load_module(SKILL_COPY, "_retro_gate_label_sync__skill_value")
    ci_module = _load_module(CI_COPY, "_retro_gate_label_sync__ci_value")
    assert skill_module.GATE_PROPOSAL_LABEL == ci_module.GATE_PROPOSAL_LABEL, (
        "skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py and "
        ".github/scripts/gitapex_scan_retrospective_gate_drift.py's GATE_PROPOSAL_LABEL "
        "values have drifted apart -- update both together (issue #1406)"
    )


# Issue #2097: the escalation label, threshold, and the two record-line
# regexes the family counter reads have a third, CI-side copy in the
# consolidation scan -- same install-time reason as the label above.
CONSOLIDATION_COPY = REPO_ROOT / ".github" / "scripts" / "gitapex_scan_gate_proposal_consolidation_drift.py"


def test_family_record_constants_stay_in_sync() -> None:
    skill_module = _load_module(SKILL_COPY, "_retro_gate_label_sync__skill_family")
    scan_module = _load_module(CONSOLIDATION_COPY, "_retro_gate_label_sync__scan_family")
    assert skill_module.GATE_PROPOSAL_ESCALATED_LABEL == scan_module.GATE_PROPOSAL_ESCALATED_LABEL
    assert skill_module.ESCALATION_THRESHOLD == scan_module.ESCALATION_THRESHOLD
    assert skill_module.RECURRENCE_LINE_RE.pattern == scan_module.RECURRENCE_LINE_RE.pattern
    assert skill_module.RECURRENCE_LINE_RE.flags == scan_module.RECURRENCE_LINE_RE.flags
    assert skill_module.CONSOLIDATES_LINE_RE.pattern == scan_module._CONSOLIDATES_LINE_RE.pattern
    assert skill_module.CONSOLIDATES_LINE_RE.flags == scan_module._CONSOLIDATES_LINE_RE.flags

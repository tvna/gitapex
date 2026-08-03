"""Sync test: gate_skill_audit_disclosure.py's base two-audit disclosure
check and hooks/check_skill_audit_disclosure_or_waiver.py's standalone
port of it must agree on _SECTION_RE, _NEXT_HEADING_RE, and _VERDICTS.

Issue #517 (refs #285, #300): the new hook is a deliberately partial,
self-contained copy of the CI gate's base check (see that hook module's
own docstring for why it cannot import .github/scripts/ directly, per
docs/repository-layout.md and the PR #433 precedent). Mirrors
tests/test_check_acm_present_sync.py's own drift-gate pattern for the
ACM-disclosure family, applied to this second two-copy family.
"""

from __future__ import annotations

import functools
import importlib.util
import pathlib
import types

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

CI_GATE_PATH = REPO_ROOT / ".github" / "scripts" / "gate_skill_audit_disclosure.py"
HOOK_PATH = REPO_ROOT / "hooks" / "check_skill_audit_disclosure_or_waiver.py"


@functools.cache
def _load_module(path: pathlib.Path) -> types.ModuleType:
    # Loaded by file path, not `import`, since hooks/ is deliberately not
    # on pythonpath (it must work standalone from inside a distributed
    # plugin bundle) -- same technique
    # tests/test_check_acm_present_sync.py's own _load_module uses.
    module_name = f"_skill_audit_disclosure_sync__{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_copies_exist():
    assert CI_GATE_PATH.is_file(), f"missing {CI_GATE_PATH}"
    assert HOOK_PATH.is_file(), f"missing {HOOK_PATH}"


def test_section_and_next_heading_regexes_stay_in_sync():
    gate = _load_module(CI_GATE_PATH)
    hook = _load_module(HOOK_PATH)
    assert (gate._SECTION_RE.pattern, gate._SECTION_RE.flags) == (
        hook._SECTION_RE.pattern,
        hook._SECTION_RE.flags,
    )
    assert (gate._NEXT_HEADING_RE.pattern, gate._NEXT_HEADING_RE.flags) == (
        hook._NEXT_HEADING_RE.pattern,
        hook._NEXT_HEADING_RE.flags,
    )


def test_verdicts_vocabulary_stays_in_sync():
    gate = _load_module(CI_GATE_PATH)
    hook = _load_module(HOOK_PATH)
    assert gate._VERDICTS == hook._VERDICTS


def test_line_patterns_stay_in_sync_for_each_audit():
    gate = _load_module(CI_GATE_PATH)
    hook = _load_module(HOOK_PATH)
    assert set(gate._VERDICTS) == set(hook._LINE_PATTERNS)
    for name in gate._VERDICTS:
        gate_pattern = gate._LINE_PATTERNS[name]
        hook_pattern = hook._LINE_PATTERNS[name]
        assert (gate_pattern.pattern, gate_pattern.flags) == (
            hook_pattern.pattern,
            hook_pattern.flags,
        ), f"{name}'s disclosure-line pattern has diverged between the CI gate and the hook copy"


def test_base_find_missing_disclosures_behavior_stays_in_sync():
    """Belt-and-suspenders behavioral check on top of the pattern-identity
    assertions above: run a handful of representative bodies through both
    copies' find_missing_disclosures and require identical results."""
    gate = _load_module(CI_GATE_PATH)
    hook = _load_module(HOOK_PATH)
    bodies = [
        "# My PR\n\nNo evidence section at all.\n",
        "## Skill audit evidence\n\n- battle-testing-a-skill: PASS\n"
        "- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n",
        "## Skill audit evidence\n\n- battle-testing-a-skill: WAIVED: reason\n"
        "- evaluating-skill-quality: WAIVED\n",
        "## Skill audit evidence\n\n- battle-testing-a-skill: PASSED\n"
        "- evaluating-skill-quality: NOT-WELL-FORMED\n",
    ]
    for body in bodies:
        assert sorted(gate.find_missing_disclosures(body)) == sorted(
            hook.find_missing_disclosures(body)
        ), f"find_missing_disclosures diverged for body: {body!r}"

"""Generator/hook agreement for the Dedup-sweep proof line (issue #1806).

`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py` emits
the line; `hooks/gitapex_check_gate_proposal_dedup_sweep.py` grades it.
The two modules carry independent copies of the line shape (never an
import -- the hooks tree must work standalone inside an installed plugin
bundle, per docs/repository-layout.md), so nothing but this test keeps
them from silently drifting apart: a generator change the hook no longer
accepts would deny every legitimate filing, and a hook change the
generator never emits would let stale lines through. Same sync-test
pattern as tests/test_gitapex_retro_gate_label_sync.py.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

import gitapex_check_gate_proposal_dedup_sweep as checker


def _load_builder() -> types.ModuleType:
    """Load skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py
    by file path: that directory is not one of pytest's pythonpath
    entries, so a bare import would depend on config-discovery behavior
    rather than being guaranteed to resolve."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    module_path = repo_root / "skills" / "merge-retrospective" / "scripts" / "gitapex_file_gate_proposal.py"
    spec = importlib.util.spec_from_file_location("gitapex_file_gate_proposal", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_new_line_is_accepted_by_hook_parser() -> None:
    builder = _load_builder()
    line = builder.build_dedup_sweep_line(open_count=63, timestamp="2026-09-05T11:00:00Z")
    found = checker.find_sweep_lines("body\n\n" + line + "\n")
    assert found == [(63, "2026-09-05T11:00:00Z", "NEW")]


def test_generator_duplicate_of_line_is_accepted_by_hook_parser() -> None:
    builder = _load_builder()
    line = builder.build_dedup_sweep_line(open_count=63, timestamp="2026-09-05T11:00:00Z", verdict="DUPLICATE-OF #1571")
    found = checker.find_sweep_lines("body\n\n" + line + "\n")
    assert found == [(63, "2026-09-05T11:00:00Z", "DUPLICATE-OF #1571")]


def test_full_generated_body_carries_exactly_one_hook_visible_line() -> None:
    builder = _load_builder()
    body = builder.build_gate_proposal_acm_body(
        retrospective_issue_number=1405,
        repair_label="Failed CI rerun",
        classification_rationale="No pre-push hook caught the lint failure before push.",
        proposed_gate_text="Add a pre-push hook running the lint suite.",
        residual_risk=None,
        dedup_sweep_open_count=63,
        dedup_sweep_timestamp="2026-09-05T11:00:00Z",
    )
    assert len(checker.find_sweep_lines(body)) == 1

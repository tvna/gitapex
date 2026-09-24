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


def test_every_hook_accepted_duplicate_line_names_a_target_the_reader_reads() -> None:
    # Issue #2097: a filing the hook allows must never be a record the
    # skill's duplicate_target drops, or the skill undercounts escalation.
    builder = _load_builder()
    for verdict in ("DUPLICATE-OF #1571", "DUPLICATE-OF #7"):
        line = f"Dedup-sweep: 3 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict {verdict}"
        assert checker._ACCEPTED_VERDICT_RE.match(verdict)
        assert builder.duplicate_target("body\n\n" + line + "\n") == int(verdict.split("#")[1])
    for verdict in ("duplicate-of #12", "DUPLICATE-OF #0", "DUPLICATE-OF #012", "DUPLICATE-OF\t#12"):
        assert not checker._ACCEPTED_VERDICT_RE.match(verdict)


def test_hook_denies_duplicate_lines_the_reader_would_drop() -> None:
    # Independent-review finding F1 (issue #2097): each variant passes the
    # loose sweep-line recognizer but not duplicate_target, so the hook
    # must deny it rather than let the skill undercount escalation.
    builder = _load_builder()
    line = "Dedup-sweep: 3 open gate-proposal issues at 2026-09-05T11:00:00Z; verdict DUPLICATE-OF #5"
    fenced_example = "```\n" + line + "\n```\n"
    variants = [
        "  " + line,
        line.replace("open gate", "open  gate"),
        line + " ",
        line.replace("Dedup-sweep", "dedup-sweep"),
        fenced_example + line,
    ]
    for variant in variants:
        body = "| a | b |\n\n" + variant + "\n"
        assert builder.duplicate_target(body) is None
        passed, message = checker.evaluate("tvna", "gitapex", "create", ["gate-proposal"], body, "")
        assert passed is False
        assert "generator's exact shape" in message
    exact_body = "| a | b |\n\n" + line + "\n"
    assert builder.duplicate_target(exact_body) == 5
    passed, message = checker.evaluate("tvna", "gitapex", "create", ["gate-proposal"], exact_body, "")
    assert "generator's exact shape" not in message

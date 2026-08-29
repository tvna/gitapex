"""Tests for the gate-enforcement drift scanner
(.github/scripts/gitapex_scan_gate_enforcement_drift.py).

Refs #1422. Two layers, mirroring
tests/test_gitapex_gate_ruleset_required_checks.py's own shape: synthetic
fixtures pinning each pure-logic case, and a live pass over this
repository's own `.gitapex/ssot.json` and `.github/rulesets/main.json` --
because the whole point of this script is that the two committed files
stay in step, and a synthetic-only pass would not prove that.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Any

import gitapex_scan_gate_enforcement_drift as scanner
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_load_active_ci_gate_ids_filters_status_and_planes() -> None:
    ssot: dict[str, Any] = {
        "gates": [
            {"id": "a", "status": "active", "planes": ["ci"]},
            {"id": "b", "status": "active", "planes": ["ci", "local"]},
            {"id": "c", "status": "experimental", "planes": ["ci"]},
            {"id": "d", "status": "active", "planes": ["local"]},
            {"id": "e", "status": "active", "planes": ["pretooluse"]},
        ]
    }
    assert scanner.load_active_ci_gate_ids(ssot) == {"a", "b"}


def test_load_active_ci_gate_ids_tolerates_malformed_entries() -> None:
    ssot: dict[str, Any] = {
        "gates": [
            {"id": "a", "status": "active", "planes": ["ci"]},
            "not-a-dict",
            {"status": "active", "planes": ["ci"]},  # missing id
            {"id": "", "status": "active", "planes": ["ci"]},  # blank id
            {"id": "b", "status": "active", "planes": "ci"},  # planes not a list
        ]
    }
    assert scanner.load_active_ci_gate_ids(ssot) == {"a"}


def test_load_active_ci_gate_ids_raises_when_gates_key_broken() -> None:
    """Dimension 15 (fail-closed on malformed input): a missing/non-list
    top-level `gates` key must raise, not silently read as zero active
    gates -- that would make run() report a clean PASS with no gap at all
    for a corrupted registry."""
    with pytest.raises(scanner.RegistryReadError):
        scanner.load_active_ci_gate_ids({})
    with pytest.raises(scanner.RegistryReadError):
        scanner.load_active_ci_gate_ids({"gates": "not-a-list"})


def test_load_required_contexts_reads_required_status_checks_rule() -> None:
    ruleset: dict[str, Any] = {
        "rules": [
            {"type": "deletion"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {"context": "actionlint"},
                        {"context": "pytest", "integration_id": 123},
                    ]
                },
            },
        ]
    }
    assert scanner.load_required_contexts(ruleset) == {"actionlint", "pytest"}


def test_load_required_contexts_empty_when_rule_type_absent() -> None:
    """A well-formed `rules` list simply carrying no
    `required_status_checks`-typed entry is a valid "zero required
    contexts" state, distinct from the `rules` key itself being broken --
    see test_load_required_contexts_raises_when_rules_key_broken."""
    assert scanner.load_required_contexts({"rules": [{"type": "deletion"}]}) == set()


def test_load_required_contexts_tolerates_malformed_rule_entry() -> None:
    """A malformed *individual* `required_status_checks`-typed rule entry
    (non-dict parameters, non-list required_status_checks, a non-dict/
    missing-context entry) is a skip, not a raise -- distinct from the
    top-level `rules` key itself being broken (see
    test_load_required_contexts_raises_when_rules_key_broken)."""
    ruleset: dict[str, Any] = {
        "rules": [
            {"type": "required_status_checks", "parameters": "not-a-dict"},
            {"type": "required_status_checks", "parameters": {"required_status_checks": "not-a-list"}},
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": ["not-a-dict", {"context": 123}, {"no_context": "x"}]},
            },
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "actionlint"}]},
            },
        ]
    }
    assert scanner.load_required_contexts(ruleset) == {"actionlint"}


def test_load_required_contexts_raises_when_rules_key_broken() -> None:
    """Dimension 15: a missing/non-list top-level `rules` key must raise,
    not silently read as zero required contexts."""
    with pytest.raises(scanner.RulesetReadError):
        scanner.load_required_contexts({})


def test_find_unregistered_gates_is_sorted_set_difference() -> None:
    result = scanner.find_unregistered_gates({"b", "a", "c"}, {"b"})
    assert result == ["a", "c"]


def test_find_unregistered_gates_ignores_the_reverse_direction() -> None:
    """Dimension 20: this scanner is deliberately one-directional (see the
    module docstring) -- a required context with no matching ssot.json
    gate id (e.g. this repository's own baseline `ruff`/`pytest`/`mypy`
    jobs, never registered as ssot.json gates in the first place) must not
    appear in the result or affect it."""
    result = scanner.find_unregistered_gates({"a"}, {"a", "ruff", "pytest", "mypy"})
    assert result == []


def test_evaluate_exceeds_threshold() -> None:
    assert scanner.evaluate(unregistered_count=3, threshold=2) is True
    assert scanner.evaluate(unregistered_count=2, threshold=2) is False
    assert scanner.evaluate(unregistered_count=0, threshold=0) is False


def test_format_report_pass_when_nothing_unregistered() -> None:
    report = scanner.format_report([], total_active_ci_gates=5, threshold=0)
    assert "PASS: 0 does not exceed threshold 0." in report
    assert "Every active CI-plane gate is registered" in report


def test_format_report_fail_lists_each_gate() -> None:
    report = scanner.format_report(["gate-a", "gate-b"], total_active_ci_gates=5, threshold=0)
    assert "FAIL: 2 exceeds threshold 0." in report
    assert "  gate-a" in report
    assert "  gate-b" in report


def test_run_raises_on_missing_ssot_file(tmp_path: pathlib.Path) -> None:
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text("{}", encoding="utf-8")
    with pytest.raises(scanner.RegistryReadError):
        scanner.run(tmp_path / "missing-ssot.json", ruleset_path, threshold=0)


def test_run_raises_on_missing_ruleset_file(tmp_path: pathlib.Path) -> None:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text('{"gates": []}', encoding="utf-8")
    with pytest.raises(scanner.RulesetReadError):
        scanner.run(ssot_path, tmp_path / "missing-ruleset.json", threshold=0)


def test_run_raises_on_non_object_ssot(tmp_path: pathlib.Path) -> None:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text("[]", encoding="utf-8")
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text("{}", encoding="utf-8")
    with pytest.raises(scanner.RegistryReadError):
        scanner.run(ssot_path, ruleset_path, threshold=0)


def test_run_raises_on_non_object_ruleset(tmp_path: pathlib.Path) -> None:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text('{"gates": []}', encoding="utf-8")
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text("[]", encoding="utf-8")
    with pytest.raises(scanner.RulesetReadError):
        scanner.run(ssot_path, ruleset_path, threshold=0)


def test_run_end_to_end_pass_and_fail(tmp_path: pathlib.Path) -> None:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text(
        '{"gates": [{"id": "a", "status": "active", "planes": ["ci"]}, '
        '{"id": "b", "status": "active", "planes": ["ci"]}]}',
        encoding="utf-8",
    )
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text(
        '{"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "a"}]}}]}',
        encoding="utf-8",
    )
    report, ok = scanner.run(ssot_path, ruleset_path, threshold=0)
    assert ok is False
    assert "  b" in report

    report, ok = scanner.run(ssot_path, ruleset_path, threshold=1)
    assert ok is True


def test_main_exits_1_on_read_error(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = scanner.main(["--ssot", str(tmp_path / "missing.json"), "--ruleset", str(tmp_path / "also.json")])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err


def test_main_exits_0_when_under_threshold(tmp_path: pathlib.Path) -> None:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text('{"gates": [{"id": "a", "status": "active", "planes": ["ci"]}]}', encoding="utf-8")
    ruleset_path = tmp_path / "main.json"
    ruleset_path.write_text(
        '{"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "a"}]}}]}',
        encoding="utf-8",
    )
    exit_code = scanner.main(["--ssot", str(ssot_path), "--ruleset", str(ruleset_path), "--threshold", "0"])
    assert exit_code == 0


def test_live_repository_within_threshold() -> None:
    """The whole point of this scanner: this repository's own committed
    ssot.json and main.json must not drift past the recorded threshold.
    A live pass rather than a fixture, mirroring
    test_gitapex_gate_ruleset_required_checks.py's own live-repository test."""
    report, ok = scanner.run(scanner.DEFAULT_SSOT_PATH, scanner.DEFAULT_RULESET_PATH, scanner.DEFAULT_THRESHOLD)
    assert ok, report


def test_cli_matches_library_call() -> None:
    """The CLI's default invocation must agree with a direct call against
    this repository's own committed files -- the same parity discipline
    gitapex_gate_ruleset_required_checks.py's own test module applies via
    a subprocess run of the real script, not just its importable functions."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / ".github" / "scripts" / "gitapex_scan_gate_enforcement_drift.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout

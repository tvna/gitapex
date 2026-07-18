"""Tests for the OWASP LLM01-10 mapping-completeness gate
(.github/scripts/gate_owasp_llm_mapping.py).

Sibling to test_gate_owasp_asi_mapping.py -- same discipline, independent
of the ASI list's own versioning. The final test is the gate itself: the
repository's real inventory file must be a complete, well-formed
LLM01-10 mapping.
"""

from __future__ import annotations

import pathlib

import gate_owasp_llm_mapping as gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

HEADING = "## OWASP Top 10 for LLM Applications and Generative AI (LLM01-10:2025)\n\n"
TABLE_HEADER = "| LLM | Status | Rationale |\n|---|---|---|\n"


def _complete_rows() -> str:
    return "".join(f"| LLM{i:02d} Some Category | covered | Because reasons #{100 + i}. |\n" for i in range(1, 11))


def _write(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "inventory.md"
    path.write_text(f"# Security control inventory\n\n{HEADING}{TABLE_HEADER}{body}")
    return path


def test_missing_file_is_drift(tmp_path):
    assert gate.find_drift(tmp_path / "does-not-exist.md") == [f"{tmp_path / 'does-not-exist.md'}: file does not exist"]


def test_missing_section_heading_is_drift(tmp_path):
    path = tmp_path / "inventory.md"
    path.write_text("# Security control inventory\n\nNo relevant section here.\n")
    problems = gate.find_drift(path)
    assert len(problems) == 1
    assert "missing section heading" in problems[0]


def test_complete_table_has_no_drift(tmp_path):
    path = _write(tmp_path, _complete_rows())
    assert gate.find_drift(path) == []


def test_missing_row_is_drift(tmp_path):
    rows = "".join(f"| LLM{i:02d} Some Category | covered | Because reasons #{100 + i}. |\n" for i in range(1, 10))
    path = _write(tmp_path, rows)
    problems = gate.find_drift(path)
    assert any("LLM10: missing row" in p for p in problems)


def test_duplicated_row_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| LLM01 Duplicate | covered | Because reasons #200. |\n")
    problems = gate.find_drift(path)
    assert any("LLM01: duplicated (2 rows)" in p for p in problems)


def test_invalid_status_is_drift(tmp_path):
    rows = _complete_rows().replace("| covered |", "| kinda covered |", 1)
    path = _write(tmp_path, rows)
    problems = gate.find_drift(path)
    assert any("invalid status" in p for p in problems)


def test_empty_rationale_is_drift(tmp_path):
    path = _write(tmp_path, "| LLM01 Some Category | covered |  |\n" + _complete_rows())
    problems = gate.find_drift(path)
    assert any("LLM01: empty rationale" in p for p in problems)


def test_future_version_heading_is_treated_as_missing(tmp_path):
    """A differently-versioned heading (e.g. a future LLM01-10:2026 taxonomy
    bump) must not silently match under the 2025 rules -- it should be
    reported the same as a missing section, forcing explicit re-verification."""
    path = tmp_path / "inventory.md"
    body = HEADING.replace("2025", "2026") + TABLE_HEADER + _complete_rows()
    path.write_text(f"# Security control inventory\n\n{body}")
    problems = gate.find_drift(path)
    assert len(problems) == 1
    assert "missing section heading" in problems[0]


def test_missing_table_header_is_drift(tmp_path):
    path = tmp_path / "inventory.md"
    path.write_text(f"# Security control inventory\n\n{HEADING}{_complete_rows()}")
    problems = gate.find_drift(path)
    assert any("table header" in p or "table separator" in p or "header/separator" in p for p in problems)


def test_no_table_at_all_is_drift(tmp_path):
    path = tmp_path / "inventory.md"
    path.write_text(f"# Security control inventory\n\n{HEADING}Just prose, no table.\n")
    problems = gate.find_drift(path)
    assert any("header/separator row missing" in p for p in problems)


def test_header_with_lead_in_prose_is_still_recognized(tmp_path):
    """Prose (a "Source: ..." paragraph) before the header/separator, as in
    the real inventory doc, must not be mistaken for the header row itself."""
    path = tmp_path / "inventory.md"
    prose = "Source: OWASP GenAI Security Project, some citation text.\n\n"
    path.write_text(f"# Security control inventory\n\n{HEADING}{prose}{TABLE_HEADER}{_complete_rows()}")
    assert gate.find_drift(path) == []


def test_malformed_header_row_is_drift(tmp_path):
    path = tmp_path / "inventory.md"
    bad_header = "| Category | State | Notes |\n|---|---|---|\n"
    path.write_text(f"# Security control inventory\n\n{HEADING}{bad_header}{_complete_rows()}")
    problems = gate.find_drift(path)
    assert any("malformed table header row" in p for p in problems)


def test_missing_separator_row_is_drift(tmp_path):
    path = tmp_path / "inventory.md"
    header_only = "| LLM | Status | Rationale |\n"
    path.write_text(f"# Security control inventory\n\n{HEADING}{header_only}{_complete_rows()}")
    problems = gate.find_drift(path)
    assert any("separator" in p for p in problems)


def test_malformed_row_missing_trailing_pipe_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| LLM01 Duplicate | covered | rationale")
    problems = gate.find_drift(path)
    assert any("malformed table row" in p for p in problems)


def test_unrecognized_id_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| LLM11 Not A Real Category | covered | N/A. |\n")
    problems = gate.find_drift(path)
    assert any("LLM11: not a recognized LLM01-10 ID" in p for p in problems)


def test_main_returns_nonzero_on_drift(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "INVENTORY_PATH", tmp_path / "missing.md")
    assert gate.main() == 1
    assert "drift" in capsys.readouterr().out.lower()


def test_main_returns_zero_when_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "INVENTORY_PATH", _write(tmp_path, _complete_rows()))
    assert gate.main() == 0
    assert "complete" in capsys.readouterr().out.lower()


def test_repository_inventory_is_valid():
    """The gate: the real inventory file's LLM01-10 mapping must be complete."""
    problems = gate.find_drift(REPO_ROOT / "docs" / "security-control-inventory.md")
    assert problems == [], f"LLM01-10 mapping drift in real inventory: {problems}"

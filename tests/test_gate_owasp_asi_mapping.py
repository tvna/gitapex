"""Tests for the OWASP ASI01-10 mapping-completeness gate
(.github/scripts/gate_owasp_asi_mapping.py).

The final test is the gate itself: the repository's real inventory file
must be a complete, well-formed ASI01-10 mapping.
"""

from __future__ import annotations

import pathlib

import gate_owasp_asi_mapping as gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

HEADING = "## OWASP Top 10 for Agentic Applications (ASI01-10)\n\n"
TABLE_HEADER = "| ASI | Status | Rationale |\n|---|---|---|\n"


def _complete_rows() -> str:
    return "".join(f"| ASI{i:02d} Some Category | covered | Because reasons #{100 + i}. |\n" for i in range(1, 11))


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
    rows = "".join(f"| ASI{i:02d} Some Category | covered | Because reasons #{100 + i}. |\n" for i in range(1, 10))
    path = _write(tmp_path, rows)
    problems = gate.find_drift(path)
    assert any("ASI10: missing row" in p for p in problems)


def test_duplicated_row_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| ASI01 Duplicate | covered | Because reasons #200. |\n")
    problems = gate.find_drift(path)
    assert any("ASI01: duplicated (2 rows)" in p for p in problems)


def test_invalid_status_is_drift(tmp_path):
    rows = _complete_rows().replace("| covered |", "| kinda covered |", 1)
    path = _write(tmp_path, rows)
    problems = gate.find_drift(path)
    assert any("invalid status" in p for p in problems)


def test_empty_rationale_is_drift(tmp_path):
    path = _write(tmp_path, "| ASI01 Some Category | covered |  |\n" + _complete_rows())
    problems = gate.find_drift(path)
    assert any("ASI01: empty rationale" in p for p in problems)


def test_malformed_row_missing_trailing_pipe_is_drift(tmp_path):
    """A row-shaped line referencing an ASI ID that doesn't match the
    3-column shape (e.g. missing the trailing pipe) must not be silently
    dropped -- it should surface as drift even though the remaining
    well-formed ASI01 row alone would otherwise look complete."""
    path = _write(tmp_path, _complete_rows() + "| ASI01 Duplicate | covered | rationale")
    problems = gate.find_drift(path)
    assert any("malformed table row" in p for p in problems)


def test_malformed_row_extra_column_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| ASI02 Duplicate | covered | rationale | extra |\n")
    problems = gate.find_drift(path)
    assert any("malformed table row" in p for p in problems)


def test_unrecognized_id_is_drift(tmp_path):
    path = _write(tmp_path, _complete_rows() + "| ASI11 Not A Real Category | covered | N/A. |\n")
    problems = gate.find_drift(path)
    assert any("ASI11: not a recognized ASI01-10 ID" in p for p in problems)


def test_main_returns_nonzero_on_drift(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "INVENTORY_PATH", tmp_path / "missing.md")
    assert gate.main() == 1
    assert "drift" in capsys.readouterr().out.lower()


def test_main_returns_zero_when_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "INVENTORY_PATH", _write(tmp_path, _complete_rows()))
    assert gate.main() == 0
    assert "complete" in capsys.readouterr().out.lower()


def test_repository_inventory_is_valid():
    """The gate: the real inventory file's ASI01-10 mapping must be complete."""
    problems = gate.find_drift(REPO_ROOT / "docs" / "security-control-inventory.md")
    assert problems == [], f"ASI01-10 mapping drift in real inventory: {problems}"

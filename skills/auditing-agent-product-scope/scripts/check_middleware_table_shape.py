"""Check that middleware-inventory.md's per-section tables keep their
required columns and expected row labels.

`references/middleware-inventory.md` backs Axis F with per-tool
"why needed" / "scope of responsibility" attributes rendered as
Markdown tables (one per section) rather than prose bullets, so a
reader can compare tools at a glance. This is a narrow, deterministic
shape check on that rendering -- the same kind of structural-drift
guard `check_axis_shape.py` already applies to the scope map itself --
not a check that the prose inside any cell stays factually accurate.
Standard library only, no network calls, no side effects.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator
from pathlib import Path

_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_TABLE_LINE_RE = re.compile(r"^\|(.*)\|[ \t]*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")

# heading text -> (required column labels, required first-cell row labels).
# Both keyed to this file's own current table rendering; a deliberate
# reshape of a table (new column, renamed/added row) updates this
# constant in the same change, the same convention check_axis_shape.py's
# _DEFAULT_EXPECTED_LABELS already establishes for the scope map.
_EXPECTED_TABLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Nix toolchain (`flake.nix`)": (
        ("Tool", "Class", "Why needed", "Scope of responsibility", "Supply-chain coverage"),
        ("`uv`", "`gh`", "`actionlint`", "`python312`", "`bun`", "`lychee`", "`waza`", "`apm`", "`rtk`", "`betterleaks`"),
    ),
    "apm": (
        ("Dependency", "Why needed", "Scope of responsibility", "Pinned in"),
        ("`apm` (the tool itself)", "`obra/superpowers`", "`tvna/clairvoyance`"),
    ),
    "Python dev tooling": (
        ("Package", "Why needed", "Scope of responsibility"),
        ("`pytest`", "`pytest-cov`", "`pyyaml`", "`prek`"),
    ),
    "GitHub MCP server": (
        ("Attribute", "Detail"),
        ("Why needed", "Scope of responsibility", "Coverage / alternative"),
    ),
    "Supply-chain coverage summary": (
        ("Ecosystem", "Bumps", "Covers Class B binaries?"),
        ("`nix`", "`github-actions`", "`uv`"),
    ),
}


def _split_sections(body_text: str) -> Iterator[tuple[str, str]]:
    """Yield (heading_text, section_text) for every '## ' heading, where
    section_text runs to the next '## ' heading or end of file."""
    matches = list(_HEADING_RE.finditer(body_text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        yield m.group(1), body_text[start:end]


def _parse_cells(line: str) -> list[str]:
    inner = line.strip()[1:-1]
    return [cell.strip() for cell in inner.split("|")]


def _first_table(section_text: str) -> tuple[list[str], list[list[str]]] | None:
    """Return (header_cells, [row_cells, ...]) for the first Markdown
    table block (header + '---' separator + data rows) in
    section_text, or None if no such table is present."""
    lines = section_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not _TABLE_LINE_RE.match(stripped):
            continue
        if i + 1 >= len(lines):
            continue
        sep_stripped = lines[i + 1].strip()
        if not _TABLE_LINE_RE.match(sep_stripped):
            continue
        sep_cells = _parse_cells(sep_stripped)
        if not sep_cells or not all(_SEPARATOR_CELL_RE.match(c) for c in sep_cells):
            continue
        header = _parse_cells(stripped)
        rows = []
        j = i + 2
        while j < len(lines) and _TABLE_LINE_RE.match(lines[j].strip()):
            rows.append(_parse_cells(lines[j].strip()))
            j += 1
        return header, rows
    return None


def check_middleware_table_shape(
    body_text: str,
    expected: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = _EXPECTED_TABLES,
) -> list[str]:
    """Return one evidence string per offense: an expected section
    heading missing entirely, a section with no Markdown table, a
    table missing one of its required columns, or a table missing one
    of its required row labels. Empty list means every expected
    section's table has every required column and row."""
    sections = dict(_split_sections(body_text))
    offenses = []
    for heading, (required_columns, required_rows) in expected.items():
        if heading not in sections:
            offenses.append(
                f"{heading}: expected but no '## {heading}' heading found in the document"
            )
            continue
        table = _first_table(sections[heading])
        if table is None:
            offenses.append(
                f"{heading}: expected a Markdown table in this section, none found"
            )
            continue
        header, rows = table
        missing_columns = [c for c in required_columns if c not in header]
        if missing_columns:
            offenses.append(
                f"{heading}: table missing column(s) {', '.join(missing_columns)}"
            )
        row_labels = {r[0] for r in rows if r}
        missing_rows = [label for label in required_rows if label not in row_labels]
        if missing_rows:
            offenses.append(
                f"{heading}: table missing row(s) for {', '.join(missing_rows)}"
            )
    return offenses


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff every expected section's table in the given file
    has all required columns and rows, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that middleware-inventory.md's per-section "
        "tables have their required columns and row labels."
    )
    parser.add_argument("path", help="Path to the doc to check.")
    args = parser.parse_args(argv)
    try:
        body_text = Path(args.path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"error: could not decode {args.path} as UTF-8: {exc}", file=sys.stderr)
        return 1
    offenses = check_middleware_table_shape(body_text)
    if not offenses:
        print("PASS: every expected table has its required columns and rows")
        return 0
    print("FAIL: table shape offense(s):", file=sys.stderr)
    for offense in offenses:
        print(f"  - {offense}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Guard docs/security-control-inventory.md's LLM01-10 mapping-table completeness.

Issue #145 adds an OWASP Top 10 for LLM Applications and Generative AI
2025 (LLM01-LLM10) mapping table alongside issue #144's Agentic Top 10
(ASI01-10) mapping. This is a **sibling** gate to
``gate_owasp_asi_mapping.py``, not an extension of it: the two OWASP
lists version independently, so a version bump in one list's contract
must never force re-verification of the other's. Same discipline as the
ASI gate -- completeness only (every LLM ID present exactly once, valid
status, non-empty rationale), never correctness.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gate_owasp_llm_mapping.py``.
"""

from __future__ import annotations

import pathlib
import re
import sys

INVENTORY_PATH = pathlib.Path("docs/security-control-inventory.md")
SECTION_HEADING = "## OWASP Top 10 for LLM Applications and Generative AI"
REQUIRED_IDS = [f"LLM{i:02d}" for i in range(1, 11)]
VALID_STATUSES = {"covered", "partially covered", "not covered", "not applicable"}

_ROW_RE = re.compile(r"^\|(?P<id>[^|]+)\|(?P<status>[^|]+)\|(?P<rationale>[^|]+)\|\s*$")


def _extract_section(text: str) -> str | None:
    """Return the section body starting at SECTION_HEADING, up to the next
    ``## `` heading or end of file. None if the heading isn't present."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(SECTION_HEADING)), None)
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end])


def _parse_rows(section: str) -> list[tuple[str, str, str]]:
    """Return (id, status, rationale) for each markdown table row in the
    section, skipping the header row and the ``---`` separator row."""
    rows: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        match = _ROW_RE.match(line.strip())
        if not match:
            continue
        raw_id = match.group("id").strip()
        if raw_id.lower() in {"llm", "---", ""} or set(raw_id) <= {"-", " ", ":"}:
            continue
        # First whitespace-delimited token is the LLM ID, e.g. "LLM01 Prompt Injection".
        llm_id = raw_id.split()[0] if raw_id.split() else raw_id
        rows.append((llm_id, match.group("status").strip(), match.group("rationale").strip()))
    return rows


def find_drift(inventory_path: pathlib.Path = INVENTORY_PATH) -> list[str]:
    """Return a list of human-readable problems. Empty list means the
    LLM01-10 mapping table is complete and well-formed."""
    if not inventory_path.exists():
        return [f"{inventory_path}: file does not exist"]

    text = inventory_path.read_text()
    section = _extract_section(text)
    if section is None:
        return [f"{inventory_path}: missing section heading {SECTION_HEADING!r}"]

    rows = _parse_rows(section)
    problems: list[str] = []

    seen: dict[str, int] = {}
    for llm_id, status, rationale in rows:
        seen[llm_id] = seen.get(llm_id, 0) + 1
        if status.lower() not in VALID_STATUSES:
            problems.append(f"{llm_id}: invalid status {status!r} (expected one of {sorted(VALID_STATUSES)})")
        if not rationale:
            problems.append(f"{llm_id}: empty rationale")

    for required_id in REQUIRED_IDS:
        count = seen.get(required_id, 0)
        if count == 0:
            problems.append(f"{required_id}: missing row")
        elif count > 1:
            problems.append(f"{required_id}: duplicated ({count} rows)")

    unexpected = sorted(set(seen) - set(REQUIRED_IDS))
    for extra_id in unexpected:
        problems.append(f"{extra_id}: not a recognized LLM01-10 ID")

    return problems


def main() -> int:
    problems = find_drift(INVENTORY_PATH)
    if problems:
        print(f"OWASP LLM01-10 mapping drift in {INVENTORY_PATH}:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("OWASP LLM01-10 mapping is complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

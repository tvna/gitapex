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
# Exact, version-pinned heading (not a prefix match): a future taxonomy
# bump such as "LLM01-10:2026" must be treated as a missing section --
# forcing explicit re-verification of this gate's ID/status contract --
# rather than silently matching under the 2025 rules.
SECTION_HEADING = "## OWASP Top 10 for LLM Applications and Generative AI (LLM01-10:2025)"
REQUIRED_IDS = [f"LLM{i:02d}" for i in range(1, 11)]
VALID_STATUSES = {"covered", "partially covered", "not covered", "not applicable"}

_ROW_RE = re.compile(r"^\|(?P<id>[^|]+)\|(?P<status>[^|]+)\|(?P<rationale>[^|]+)\|\s*$")
_ID_TOKEN_RE = re.compile(r"\bLLM\d{2}\b")
_HEADER_ID_RE = re.compile(r"^(llm|id)$", re.IGNORECASE)
_HEADER_ROW_RE = re.compile(r"^\|\s*(?:LLM|ID)\s*\|\s*Status\s*\|\s*Rationale\s*\|\s*$", re.IGNORECASE)
_SEPARATOR_ROW_RE = re.compile(r"^\|(?:\s*:?-+:?\s*\|){3}\s*$")


def _extract_section(text: str) -> str | None:
    """Return the section body starting at SECTION_HEADING, up to the next
    ``## `` heading or end of file. None if the heading isn't present.

    Matches the heading line exactly (after stripping trailing
    whitespace), not as a prefix, so a differently-versioned heading is
    treated as absent rather than silently accepted.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == SECTION_HEADING), None)
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end])


def _validate_table_header(section: str) -> str | None:
    """Return an error message if the table's header/separator rows are
    missing or malformed, else None.

    Without this check, deleting the header/separator rows still leaves
    row-shaped data lines that `_parse_rows` would happily accept, even
    though GitHub would render the remaining lines as plain text instead
    of a table. Looks at the first two ``|``-prefixed lines in the
    section (skipping any lead-in prose paragraphs), not the section's
    first two lines outright.
    """
    pipe_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(pipe_lines) < 2:
        return "table header/separator row missing"
    header, separator = pipe_lines[0], pipe_lines[1]
    if not _HEADER_ROW_RE.match(header):
        return f"malformed table header row: {header!r}"
    if not _SEPARATOR_ROW_RE.match(separator):
        return f"malformed table separator row: {separator!r}"
    return None


def _parse_rows(section: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ((id, status, rationale) rows, malformed row lines) for the section.

    Skips the header row and the ``---`` separator row. A line that looks
    like a table row referencing an LLM ID (``|``-delimited, containing an
    ``LLMnn`` token) but does not match the required 3-column shape is
    reported as malformed rather than silently dropped.
    """
    rows: list[tuple[str, str, str]] = []
    malformed: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        match = _ROW_RE.match(stripped)
        if not match:
            if stripped.startswith("|") and _ID_TOKEN_RE.search(stripped):
                malformed.append(stripped)
            continue
        raw_id = match.group("id").strip()
        if _HEADER_ID_RE.match(raw_id) or set(raw_id) <= {"-", " ", ":"}:
            continue
        # First whitespace-delimited token is the LLM ID, e.g. "LLM01 Prompt Injection".
        llm_id = raw_id.split()[0] if raw_id.split() else raw_id
        rows.append((llm_id, match.group("status").strip(), match.group("rationale").strip()))
    return rows, malformed


def find_drift(inventory_path: pathlib.Path = INVENTORY_PATH) -> list[str]:
    """Return a list of human-readable problems. Empty list means the
    LLM01-10 mapping table is complete and well-formed."""
    if not inventory_path.exists():
        return [f"{inventory_path}: file does not exist"]

    text = inventory_path.read_text()
    section = _extract_section(text)
    if section is None:
        return [f"{inventory_path}: missing section heading {SECTION_HEADING!r}"]

    header_problem = _validate_table_header(section)
    if header_problem:
        return [f"{inventory_path}: {header_problem}"]

    rows, malformed = _parse_rows(section)
    problems: list[str] = []

    for bad_row in malformed:
        problems.append(f"malformed table row (does not match the id|status|rationale shape): {bad_row!r}")

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

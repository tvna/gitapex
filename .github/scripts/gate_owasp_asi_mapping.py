#!/usr/bin/env python3
"""Guard docs/security-control-inventory.md's ASI01-10 mapping-table completeness.

Issue #144 ports `tvna/claude-md`'s OWASP Agentic Top 10 mapping
discipline: a living status table, one row per ASI01..ASI10, drifts
silently if a row goes missing, gets duplicated, or loses its rationale
during an edit. This gate checks completeness only -- every ASI ID
present exactly once, with a status drawn from a closed vocabulary and a
non-empty rationale -- never the correctness of a verdict, which stays
with human/PR review.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gate_owasp_asi_mapping.py``.
"""

from __future__ import annotations

import pathlib
import re
import sys

INVENTORY_PATH = pathlib.Path("docs/security-control-inventory.md")
SECTION_HEADING = "## OWASP Top 10 for Agentic Applications"
REQUIRED_IDS = [f"ASI{i:02d}" for i in range(1, 11)]
VALID_STATUSES = {"covered", "partially covered", "not covered", "not applicable"}

_ROW_RE = re.compile(r"^\|(?P<id>[^|]+)\|(?P<status>[^|]+)\|(?P<rationale>[^|]+)\|\s*$")
_ID_TOKEN_RE = re.compile(r"\bASI\d{2}\b")
_HEADER_ID_RE = re.compile(r"^(asi|id)$", re.IGNORECASE)


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


def _parse_rows(section: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ((id, status, rationale) rows, malformed row lines) for the section.

    Skips the header row and the ``---`` separator row. A line that looks
    like a table row referencing an ASI ID (``|``-delimited, containing an
    ``ASInn`` token) but does not match the required 3-column shape is
    reported as malformed rather than silently dropped, so a broken or
    extra-column duplicate row still surfaces as drift instead of vanishing.
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
        # First whitespace-delimited token is the ASI ID, e.g. "ASI01 Agent Goal Hijack".
        asi_id = raw_id.split()[0] if raw_id.split() else raw_id
        rows.append((asi_id, match.group("status").strip(), match.group("rationale").strip()))
    return rows, malformed


def find_drift(inventory_path: pathlib.Path = INVENTORY_PATH) -> list[str]:
    """Return a list of human-readable problems. Empty list means the ASI01-10
    mapping table is complete and well-formed."""
    if not inventory_path.exists():
        return [f"{inventory_path}: file does not exist"]

    text = inventory_path.read_text()
    section = _extract_section(text)
    if section is None:
        return [f"{inventory_path}: missing section heading {SECTION_HEADING!r}"]

    rows, malformed = _parse_rows(section)
    problems: list[str] = []

    for bad_row in malformed:
        problems.append(f"malformed table row (does not match the id|status|rationale shape): {bad_row!r}")

    seen: dict[str, int] = {}
    for asi_id, status, rationale in rows:
        seen[asi_id] = seen.get(asi_id, 0) + 1
        if status.lower() not in VALID_STATUSES:
            problems.append(f"{asi_id}: invalid status {status!r} (expected one of {sorted(VALID_STATUSES)})")
        if not rationale:
            problems.append(f"{asi_id}: empty rationale")

    for required_id in REQUIRED_IDS:
        count = seen.get(required_id, 0)
        if count == 0:
            problems.append(f"{required_id}: missing row")
        elif count > 1:
            problems.append(f"{required_id}: duplicated ({count} rows)")

    unexpected = sorted(set(seen) - set(REQUIRED_IDS))
    for extra_id in unexpected:
        problems.append(f"{extra_id}: not a recognized ASI01-10 ID")

    return problems


def main() -> int:
    problems = find_drift(INVENTORY_PATH)
    if problems:
        print(f"OWASP ASI01-10 mapping drift in {INVENTORY_PATH}:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("OWASP ASI01-10 mapping is complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

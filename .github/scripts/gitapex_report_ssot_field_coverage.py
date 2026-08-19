#!/usr/bin/env python3
"""Report, non-blocking, which .gitapex/ssot.json gates still lack fail_mode/target.

Issue #1232's own explicit design: this report is non-blocking regardless
of the coverage level it finds, on purpose. `target` reached 100% of the
63 pre-existing gates in this same issue's own backfill (0 of the 8 gates
docs/superpowers/specs/2026-08-19-ssot-completeness-design.md flagged as
medium/ambiguous actually needed a NO-FIT verdict once grounded in their
real, current scripts) -- but that is this issue's outcome, not a
structural guarantee: a future gate can land without target, and
`fail_mode` has no backfill effort behind it at all yet, so a fail-closed
check against either field would still just get bypassed or waived the
moment either regresses below 100%, which is worse than an honest,
visible report. So this script always exits 0 except on a genuine
read/parse failure (missing file, invalid JSON, non-UTF-8 text) -- a
non-object top-level value (a bare list/string/number/null) is schema-
invalid but still valid JSON, so it is not one of those failures either:
field_coverage() treats it the same as an empty gates list and reports an
honest 0/0, exit 0. Incomplete coverage, and a malformed-but-parseable
registry shape, are both expected, honestly-reported states, never a
structural error. Whether to later promote either field to a fail-closed
check (e.g. "new gates must carry target") is a separate, future decision,
left open here per that same design doc.

Deliberately a sibling script to gitapex_scan_ssot_schema.py rather than an
extension of it: that script's whole contract is "exit 1 on drift," and
folding an always-exit-0 report into the same main() would make one
script's exit code mean two different things depending on which check
produced it.

Run standalone, or via the pytest gate in
tests/test_gitapex_report_ssot_field_coverage.py (which asserts the report
runs and is well-formed, never that coverage is complete -- asserting
completeness there would make the "report, don't block" contract this
script exists for silently blocking after all, just one layer up).
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import _gitapex_schema_validation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

# The two fields issue #1232 scopes this report to. Deliberately not every
# optional gate field (bypass_review_status is already required[] as of
# this same issue, so a coverage report for it would always read 100/100
# and add nothing) -- see the module docstring for why these two specifically
# still need visibility.
FIELDS = ("fail_mode", "target")


class RegistryReadError(Exception):
    """.gitapex/ssot.json could not be read as UTF-8 text or parsed as JSON
    at all. The only condition this script treats as a real failure (exit
    1) -- see the module docstring for why incomplete field coverage itself
    never is."""


def field_coverage(instance: Any, field: str) -> tuple[list[str], list[str]]:
    """Return (present, missing) gate ids for `field` across instance["gates"],
    sorted. A missing/non-list `gates`, or a non-dict entry within it, or an
    entry with a non-string `id`, is silently excluded from both lists
    rather than raised -- schema validity is ssot-schema-drift's job, not
    this report's; a schema-invalid instance simply yields a smaller,
    still-honest count instead of a crash."""
    gates = instance.get("gates") if isinstance(instance, dict) else None
    if not isinstance(gates, list):
        return [], []
    present: list[str] = []
    missing: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("id")
        if not isinstance(gate_id, str):
            continue
        (present if field in gate else missing).append(gate_id)
    return sorted(present), sorted(missing)


def build_report(instance: Any) -> str:
    """Human-readable, per-field coverage report. Never empty, never raises
    on a schema-invalid or field-less instance -- see field_coverage."""
    lines = ["ssot.json field coverage (report only, never fails CI):"]
    for field in FIELDS:
        present, missing = field_coverage(instance, field)
        total = len(present) + len(missing)
        pct = (100 * len(present) // total) if total else 0
        lines.append(f"  {field}: {len(present)}/{total} gates ({pct}%)")
        if missing:
            lines.append(f"    missing: {', '.join(missing)}")
    return "\n".join(lines)


def main() -> int:
    try:
        instance = _gitapex_schema_validation.load_json_or_raise(SSOT_PATH, RegistryReadError)
    except RegistryReadError as error:
        print(f"ssot field coverage report: cannot run: {error}")
        return 1
    print(build_report(instance))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Check that every newly-added Kept-edit-log `**Iteration:` entry in a
diff over `evals/*/split.md` discloses a `Transfer check` line.

Issue #517 (refs #487): several split.md files (e.g.
evals/evaluating-skill-quality/split.md, evals/merge-retrospective/split.md,
evals/scorer-gated-skill-edits/split.md) document a `## Kept-edit log`
convention where every KEEP iteration entry carries a bold
`**Transfer check:**` line, either disclosing a real result or explicitly
stating the transfer check was not run this iteration -- mirroring
scorer-gated-skill-edits/SKILL.md's own stop boundary, "Never ship a
skill that has not passed a transfer check." Nothing enforced that
disclosure requirement deterministically until now; a KEEP entry could
previously omit it silently.

Scoped to any `evals/*/split.md`, not literally only
`evals/scorer-gated-skill-edits/split.md` (which has zero Kept-edit-log
entries today and would make a literally-scoped check a permanent no-op) --
the convention this closes is genuinely repo-wide, not specific to one
skill's split.md.

Diff-scoped by design, not a full-file audit: only entries whose own
`**Iteration:` header line is newly added in the current diff are
checked (the calling workflow computes this list via `git diff -U0`, the
same "git access stays in the workflow, this script only grades the
facts handed to it" split as gate_skill_audit_disclosure.py). This means
the pre-existing entries in evals/evaluating-skill-quality/split.md that
predate this gate are never retroactively flagged -- only a future new
entry, anywhere, must comply. Each entry's Transfer-check search always
reads the *current* on-disk file content (mirrors
gate_skill_rename_lifecycle.py's own `all_renamed_from_values`, which
reads skills/*/metadata/gitapex.yaml directly from the checked-out
working tree) rather than the diff hunk itself, so a reworded existing
entry whose own Transfer check line sits a few lines below, untouched by
this diff, still correctly passes.

Deliberately not merged into gate_skill_audit_disclosure.py: that script
grades PR-body text against workflow-supplied skill/doc lists; this one
grades repository file content (an evals/*/split.md's own prose) against
a workflow-supplied list of newly-added entries -- a different task
shape, kept as its own focused gate script and workflow per this repo's
existing gate_owasp_asi_mapping.py / gate_owasp_llm_mapping.py precedent
of independent, single-purpose gates.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ITERATION_PREFIX = "**Iteration:"
_HEADING_RE = re.compile(r"^##[ \t]+\S")
_TRANSFER_CHECK_RE = re.compile(r"transfer check", re.IGNORECASE)


def _entry_span(lines, start_index):
    """Return the lines from start_index (inclusive) up to, but excluding,
    the next `**Iteration:` line or `##` heading line, or EOF."""
    end = len(lines)
    for i in range(start_index + 1, len(lines)):
        line = lines[i]
        if line.startswith(_ITERATION_PREFIX) or _HEADING_RE.match(line):
            end = i
            break
    return lines[start_index:end]


def _find_line_index(lines, target_line):
    for i, line in enumerate(lines):
        if line == target_line:
            return i
    return None


def find_missing_transfer_checks(entries):
    """entries: an iterable of (path, iteration_line) pairs -- workflow-
    computed, newly-added `**Iteration:` lines in this diff. Returns the
    subset whose entry span (read from the current on-disk file content)
    has no `Transfer check` mention, or whose (path, iteration_line) could
    not be located at all (missing file, or the line text no longer
    matches current content) -- either way treated as a disclosure
    failure, not silently skipped.
    """
    missing = []
    file_lines_cache = {}
    for path, iteration_line in entries:
        if path not in file_lines_cache:
            try:
                file_lines_cache[path] = Path(path).read_text(encoding="utf-8").splitlines()
            except OSError:
                file_lines_cache[path] = None
        lines = file_lines_cache[path]
        if lines is None:
            missing.append((path, iteration_line))
            continue
        idx = _find_line_index(lines, iteration_line)
        if idx is None:
            missing.append((path, iteration_line))
            continue
        span_text = "\n".join(_entry_span(lines, idx))
        if not _TRANSFER_CHECK_RE.search(span_text):
            missing.append((path, iteration_line))
    return missing


def _parse_entries(text):
    """Parse `<path>\\t<iteration line text>` pairs, one per line, blank
    lines ignored."""
    entries = []
    for line in text.splitlines():
        if not line.strip():
            continue
        path, sep, iteration_line = line.partition("\t")
        if not sep:
            continue
        entries.append((path, iteration_line))
    return entries


def _truncate(text, limit=100):
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main(argv=None):
    """CLI: exit 0 iff every newly-added Kept-edit-log entry handed in
    discloses a Transfer check line, else 1."""
    parser = argparse.ArgumentParser(
        description="Check that every newly-added Kept-edit-log '**Iteration:' "
        "entry in a diff over evals/*/split.md discloses a Transfer check line."
    )
    parser.add_argument(
        "--entries",
        help="Path to a file of '<path><TAB><iteration line text>' pairs, "
        "one per line (workflow-computed: newly-added '**Iteration:' lines "
        "in this diff); reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        text = (
            open(args.entries, encoding="utf-8").read() if args.entries else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: entries file not found: {args.entries}", file=sys.stderr)
        return 1

    entries = _parse_entries(text)
    if not entries:
        print("PASS: no newly-added Kept-edit-log entries in this diff")
        return 0

    missing = find_missing_transfer_checks(entries)
    if not missing:
        print(f"PASS: Transfer check disclosed for all {len(entries)} newly-added entry(ies)")
        return 0

    print(
        "FAIL: the following newly-added Kept-edit-log entries have no "
        "disclosed Transfer check line:",
        file=sys.stderr,
    )
    for path, iteration_line in missing:
        print(f"  - {path}: {_truncate(iteration_line)}", file=sys.stderr)
    print(
        "Add a '**Transfer check:** ...' line within the entry's own span "
        "(disclosing a real result, or that it was not run this iteration), "
        "per the convention already used in "
        "evals/evaluating-skill-quality/split.md's Kept-edit log.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

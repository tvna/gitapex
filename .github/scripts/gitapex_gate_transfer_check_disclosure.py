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
facts handed to it" split as gitapex_gate_skill_audit_disclosure.py). This means
the pre-existing entries in evals/evaluating-skill-quality/split.md that
predate this gate are never retroactively flagged -- only a future new
entry, anywhere, must comply. Each entry's Transfer-check search always
reads the *current* on-disk file content (mirrors
gitapex_gate_skill_rename_lifecycle.py's own `all_renamed_from_values`, which
reads skills/*/metadata/gitapex.yaml directly from the checked-out
working tree) rather than the diff hunk itself, so a reworded existing
entry whose own Transfer check line sits a few lines below, untouched by
this diff, still correctly passes.

Deliberately not merged into gitapex_gate_skill_audit_disclosure.py: that script
grades PR-body text against workflow-supplied skill/doc lists; this one
grades repository file content (an evals/*/split.md's own prose) against
a workflow-supplied list of newly-added entries -- a different task
shape, kept as its own focused gate script and workflow per this repo's
existing gitapex_gate_owasp_asi_mapping.py / gitapex_gate_owasp_llm_mapping.py precedent
of independent, single-purpose gates.

Scoped specifically to the `## Kept-edit log` section, not any `##`
section a split.md happens to contain: an entry under `## Rejected-edit
log` was rejected before a transfer check could even be relevant, so this
gate only requires the line for an entry whose nearest preceding `##`
heading is `Kept-edit log` (case-insensitive); an entry under any other
heading, or with no heading above it at all, is out of this gate's scope
and never reported as a failure.

Line selection is multiplicity-aware: if two entries in the same file
share byte-identical `**Iteration:` header text (an edge case -- real
entries cite a unique issue number -- but not impossible), naively
matching the *first* occurrence in the file would grade a later,
genuinely new entry against an earlier, unrelated one's span. Each
workflow-supplied (path, iteration_line) tuple instead consumes one
not-yet-claimed matching line, preferring the *last* (highest-numbered)
remaining occurrence first, since new entries are conventionally appended
to the end of a Kept-edit log.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ITERATION_PREFIX = "**Iteration:"
_HEADING_RE = re.compile(r"^##[ \t]+(\S.*)$")
_KEPT_EDIT_LOG_HEADING_RE = re.compile(r"^kept-edit log$", re.IGNORECASE)
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


def _nearest_heading(lines, index):
    """Return the text of the nearest `##` heading at or before `index`,
    or None if there is none (index sits before any heading)."""
    for i in range(index, -1, -1):
        match = _HEADING_RE.match(lines[i])
        if match:
            return match.group(1).strip()
    return None


def _select_unconsumed_line_index(lines, target_line, consumed):
    """Return the highest-index line in `lines` equal to `target_line`
    that is not already in `consumed`, or None if every occurrence (or
    there are none at all) is already claimed. Preferring the last
    occurrence first matches how new Kept-edit-log entries are
    conventionally appended."""
    for i in range(len(lines) - 1, -1, -1):
        if i not in consumed and lines[i] == target_line:
            return i
    return None


def find_missing_transfer_checks(entries):
    """entries: an iterable of (path, iteration_line) pairs -- workflow-
    computed, newly-added `**Iteration:` lines in this diff. Returns the
    subset that are in scope (nearest heading is `## Kept-edit log`) and
    whose entry span (read from the current on-disk file content) has no
    `Transfer check` mention, or whose (path, iteration_line) could not be
    located at all (missing file, or the line text no longer matches
    current content, or every matching occurrence already claimed by an
    earlier tuple) -- either way treated as a disclosure failure, not
    silently skipped. An entry located but scoped to a heading other than
    `## Kept-edit log` (e.g. `## Rejected-edit log`) is out of scope and
    never added to the returned list.
    """
    missing = []
    file_lines_cache: dict[str, list[str] | None] = {}
    consumed_by_path: dict[str, set[int]] = {}
    for path, iteration_line in entries:
        if path not in file_lines_cache:
            try:
                file_lines_cache[path] = Path(path).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError) as exc:
                print(f"warning: could not read {path}: {exc}", file=sys.stderr)
                file_lines_cache[path] = None
        lines = file_lines_cache[path]
        if lines is None:
            missing.append((path, iteration_line))
            continue
        consumed = consumed_by_path.setdefault(path, set())
        idx = _select_unconsumed_line_index(lines, iteration_line, consumed)
        if idx is None:
            missing.append((path, iteration_line))
            continue
        consumed.add(idx)
        heading = _nearest_heading(lines, idx)
        if heading is None or not _KEPT_EDIT_LOG_HEADING_RE.match(heading):
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


def main(argv: list[str] | None = None) -> int:
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
            Path(args.entries).read_text(encoding="utf-8") if args.entries else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: entries file not found: {args.entries}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as error:
        source = args.entries if args.entries else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
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
        "FAIL: the following newly-added Kept-edit-log entries have no disclosed Transfer check line:",
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

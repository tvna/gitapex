"""Deterministic pre-filter for task-decomposition.md's file-ownership edge.

Step 3's own tool: given a task list's file assignments (task-id -> the
files that task will write), reports every task pair that would write
the same file -- the literal, pure-string-matching case
task-decomposition.md's "Two dependency-edge types" section already
describes in prose ("build a file path -> task ID map ... any two tasks
that would write the same file share an edge"). A pre-filter, not a full
replacement: this mechanizes the file-ownership edge only. The
interface-dependency edge (a semantic producer/consumer judgment between
two tasks' free-text Planned-ops descriptions) stays a model judgment,
carrying its own pin -- see references/task-decomposition.md.

Read-only: reads the given task/file mapping only, writes nothing,
network-free. Path comparison is exact-string equality after a light
normalization (strip a leading "./", collapse backslashes to forward
slashes, collapse redundant "//" runs, resolve embedded "/./"
segments) -- no glob, no symlink resolution, no case-folding, no ".."
resolution, no absolute-vs-relative reconciliation, no trailing-"/"
stripping. A genuinely ambiguous case (a glob-shaped Planned-ops
description, a symlink, a case-insensitive-filesystem collision, an
absolute path naming the same file as a relative one) is exactly the
kind of case this pre-filter does not claim to catch; that stays the
model's own step-3 judgment.

Also rejects, as malformed input, a raw JSON object with a duplicate
task-ID key -- Python's own `json.loads` otherwise silently keeps only
the last occurrence and drops the earlier one's files with no warning,
which would silently hide a real file-ownership conflict involving the
discarded task rather than merely mis-normalize a path.

Usage:
  python3 gitapex_check_file_ownership_conflicts.py --input <path-to-json>
  echo '{"task-a": ["a.py"], "task-b": ["a.py"]}' | python3 gitapex_check_file_ownership_conflicts.py

Input JSON shape: an object mapping each task ID (string) to a list of
file paths (strings) that task will write.

Exit code: 0 on a successful run (conflicts, if any, are reported to
stdout as informational output for the caller's own wave-assignment
step -- finding a conflict is not itself a failure of this tool). 2 on
malformed input or usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from _gitapex_path_normalize import normalize as _normalize


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """`object_pairs_hook` for `json.loads`: raise instead of silently
    keeping only the last value for a repeated key. Plain `json.loads`
    (via its default dict construction) drops every earlier occurrence
    of a duplicate key with no warning -- exactly the kind of silent
    data loss this conflict-detection tool must not itself commit,
    since a dropped task's files are files this tool never checks."""
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate task ID in input JSON: {key!r}")
        seen[key] = value
    return seen


def find_conflicts(task_files: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """Given {task_id: [file, ...]}, return a sorted list of
    (file, sorted([task_id, ...])) tuples for every file written by more
    than one task."""
    owners = defaultdict(list)
    for task_id, files in task_files.items():
        for raw_path in files:
            owners[_normalize(raw_path)].append(task_id)
    conflicts = []
    for path, task_ids in owners.items():
        unique_owners = sorted(set(task_ids))
        if len(unique_owners) > 1:
            conflicts.append((path, unique_owners))
    return sorted(conflicts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report task pairs that would write the same file "
        "(task-decomposition.md's file-ownership edge, mechanized)."
    )
    parser.add_argument(
        "--input",
        help="Path to a JSON file mapping task ID -> list of file paths; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        raw_text = (
            Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as error:
        source = args.input if args.input else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 2
    try:
        task_files = json.loads(raw_text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        print(f"error: input is not valid JSON: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(task_files, dict):
        print("error: input JSON must be an object mapping task ID -> list of file paths", file=sys.stderr)
        return 2
    for task_id, files in task_files.items():
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            print(f"error: task {task_id!r}'s value must be a list of file-path strings", file=sys.stderr)
            return 2

    conflicts = find_conflicts(task_files)
    if not conflicts:
        print("no file-ownership conflicts found")
        return 0
    for path, task_ids in conflicts:
        print(
            f"CONFLICT: {path} is written by: {', '.join(task_ids)} -- sequence these tasks, never co-assign to the same wave"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
slashes) -- no glob, no symlink resolution, no case-folding. A genuinely
ambiguous case (a glob-shaped Planned-ops description, a symlink, a
case-insensitive-filesystem collision) is exactly the kind of case this
pre-filter does not claim to catch; that stays the model's own step-3
judgment.

Usage:
  python3 check_file_ownership_conflicts.py --input <path-to-json>
  echo '{"task-a": ["a.py"], "task-b": ["a.py"]}' | python3 check_file_ownership_conflicts.py

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


def _normalize(path):
    """Light path normalization: strip a leading './', collapse backslashes
    to forward slashes. Not a full path-canonicalization -- see module
    docstring's own scope note."""
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def find_conflicts(task_files):
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report task pairs that would write the same file "
        "(task-decomposition.md's file-ownership edge, mechanized)."
    )
    parser.add_argument(
        "--input",
        help="Path to a JSON file mapping task ID -> list of file paths; "
        "reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        raw_text = (
            open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    try:
        task_files = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        print(f"error: input is not valid JSON: {exc}", file=sys.stderr)
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
        print(f"CONFLICT: {path} is written by: {', '.join(task_ids)} -- sequence these tasks, never co-assign to the same wave")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

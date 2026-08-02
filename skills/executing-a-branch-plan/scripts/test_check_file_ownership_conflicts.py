"""Regression suite for check_file_ownership_conflicts.py's own conflict
detection. Runs the shipped script via subprocess, the same convention
test_check_task_bash_safety.py already uses in this directory -- the
script is the thing under test, not a reimplementation of it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "check_file_ownership_conflicts.py"


def run(task_files):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(task_files),
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_no_conflicts():
    result = run({"task-a": ["a.py"], "task-b": ["b.py"]})
    assert result.returncode == 0
    assert "no file-ownership conflicts found" in result.stdout


def test_one_shared_file_pair():
    result = run({"task-a": ["shared.py", "a.py"], "task-b": ["shared.py"]})
    assert result.returncode == 0
    assert "CONFLICT: shared.py" in result.stdout
    assert "task-a" in result.stdout and "task-b" in result.stdout


def test_three_way_shared_file():
    result = run({"task-a": ["x.py"], "task-b": ["x.py"], "task-c": ["x.py"]})
    assert result.returncode == 0
    assert "task-a" in result.stdout and "task-b" in result.stdout and "task-c" in result.stdout


def test_path_normalization_collapses_dotslash_prefix():
    result = run({"task-a": ["./a.py"], "task-b": ["a.py"]})
    assert result.returncode == 0
    assert "CONFLICT: a.py" in result.stdout


def test_path_normalization_collapses_double_slash():
    # Adversarial gate finding: "a//b.py" and "a/b.py" name the exact same
    # file on any POSIX filesystem -- must still be detected as a conflict.
    result = run({"task-a": ["a//b.py"], "task-b": ["a/b.py"]})
    assert result.returncode == 0
    assert "CONFLICT: a/b.py" in result.stdout


def test_path_normalization_resolves_embedded_dotslash_segment():
    # Adversarial gate finding: an embedded "/./" segment (not just a
    # leading "./") is lexically a no-op and must not hide a conflict.
    result = run({"task-a": ["a/./b.py"], "task-b": ["a/b.py"]})
    assert result.returncode == 0
    assert "CONFLICT: a/b.py" in result.stdout


def test_path_normalization_handles_leading_dotslash_adjacent_to_slash():
    # Independent /code-review finding: a leading "./" immediately
    # followed by another "/" (".//a.py") is a distinct case from either
    # "./a.py" or "a//b.py" alone -- an earlier normalize() implementation
    # stripped "./" before collapsing "//", leaving a stray leading "/"
    # neither test above (one exercises a leading "./" alone, the other a
    # "//" with no leading "./") happened to combine, letting this bug
    # through untested.
    result = run({"task-a": [".//a.py"], "task-b": ["a.py"]})
    assert result.returncode == 0
    assert "CONFLICT: a.py" in result.stdout


def test_duplicate_task_id_key_is_usage_error_not_silent_drop():
    # Adversarial gate finding: plain json.loads silently keeps only the
    # last occurrence of a duplicate object key, dropping the earlier
    # task's files with no warning -- exactly the kind of silent data loss
    # a conflict-detection tool must not itself commit. Must be a usage
    # error, not a clean "no conflicts" report.
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input='{"task-a": ["a.py"], "task-a": ["b.py"]}',
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "duplicate task ID" in result.stderr


def test_malformed_json_is_usage_error():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_non_object_json_is_usage_error():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_empty_task_map_has_no_conflicts():
    result = run({})
    assert result.returncode == 0
    assert "no file-ownership conflicts found" in result.stdout

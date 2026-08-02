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

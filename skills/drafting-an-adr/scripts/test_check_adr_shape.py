"""Tests for check_adr_shape.py.

Not wired into the root pyproject.toml testpaths -- this skill's checker
is meant to stand alone; run directly with:
    python3 -m pytest skills/drafting-an-adr/scripts/
"""

import subprocess
import sys
from pathlib import Path

import check_adr_shape as cas

_VALID_ADR = """# Switch session store from in-memory affinity to Redis

## Status

Proposed

## Context and Problem Statement

Sticky in-memory affinity blocks horizontal autoscaling.

## Considered Options

- Keep sticky affinity
- Shared Redis-backed store

## Decision Outcome

We will move to a shared Redis-backed session store.

## Consequences

Good, because autoscaling no longer needs session-aware routing.
Bad, because the API now depends on Redis's own availability.

## Confirmation

A code-review checklist item: any new session code must use the shared client.
"""


def test_valid_adr_passes():
    assert cas.check_adr_shape(_VALID_ADR) == []


def test_missing_heading_fails():
    body = _VALID_ADR.replace("## Consequences\n\n", "")
    failures = cas.check_adr_shape(body)
    assert any("Consequences" in f for f in failures)


def test_invalid_status_value_fails():
    body = _VALID_ADR.replace("Proposed", "In Progress")
    failures = cas.check_adr_shape(body)
    assert any("Status" in f for f in failures)


def test_status_case_insensitive():
    body = _VALID_ADR.replace("Proposed", "ACCEPTED")
    assert cas.check_adr_shape(body) == []


def test_status_with_trailing_approval_detail_passes():
    body = _VALID_ADR.replace("Proposed", "Accepted (approved by @platform-lead, 2026-06-02)")
    assert cas.check_adr_shape(body) == []


def test_empty_consequences_fails():
    body = _VALID_ADR.replace(
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "Bad, because the API now depends on Redis's own availability.\n",
        "",
    )
    failures = cas.check_adr_shape(body)
    assert any("Consequences" in f for f in failures)


def test_consequences_html_comment_only_is_empty():
    body = _VALID_ADR.replace(
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "Bad, because the API now depends on Redis's own availability.\n",
        "<!-- unknown, pending investigation -->\n",
    )
    failures = cas.check_adr_shape(body)
    assert any("Consequences" in f for f in failures)


def test_one_sided_consequences_fails():
    body = _VALID_ADR.replace(
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "Bad, because the API now depends on Redis's own availability.\n",
        "Good, because it's faster.\nGood, because it's simpler.\n",
    )
    failures = cas.check_adr_shape(body)
    assert any("Consequences" in f for f in failures)


def test_single_unknown_entry_alone_fails():
    body = _VALID_ADR.replace(
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "Bad, because the API now depends on Redis's own availability.\n",
        "unknown, pending a load test of the failover path.\n",
    )
    failures = cas.check_adr_shape(body)
    assert any("Consequences" in f for f in failures)


def test_unknown_pending_stands_in_for_missing_side():
    body = _VALID_ADR.replace(
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "Bad, because the API now depends on Redis's own availability.\n",
        "Good, because autoscaling no longer needs session-aware routing.\n"
        "unknown, pending a load test of the failover path.\n",
    )
    assert cas.check_adr_shape(body) == []


def test_missing_multiple_headings_lists_all():
    body = "# Title\n\n## Status\n\nProposed\n"
    failures = cas.check_adr_shape(body)
    assert any(
        "Context and Problem Statement" in f and "Decision Outcome" in f and "Consequences" in f for f in failures
    )


def test_cli_pass_via_stdin(tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(cas.__file__).resolve())],
        input=_VALID_ADR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_cli_fail_via_body_file(tmp_path):
    bad_path = tmp_path / "bad.md"
    bad_path.write_text("# Title\n\n## Status\n\nProposed\n")
    result = subprocess.run(
        [sys.executable, str(Path(cas.__file__).resolve()), "--body", str(bad_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stderr


def test_cli_missing_file_errors(tmp_path):
    missing_path = tmp_path / "does-not-exist.md"
    result = subprocess.run(
        [sys.executable, str(Path(cas.__file__).resolve()), "--body", str(missing_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    # The exact "error: ..." prefix, not a bare "error" substring: pytest's
    # own tmp_path directory name embeds this test's function name, which
    # contains "error" and "directory" as substrings of its own -- a bare
    # substring check would pass even with the except clause deleted.
    assert "error: body file not found:" in result.stderr


def test_cli_directory_path_errors(tmp_path):
    result = subprocess.run(
        [sys.executable, str(Path(cas.__file__).resolve()), "--body", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "error: body path is a directory, not a file:" in result.stderr


def test_cli_non_utf8_file_errors(tmp_path):
    bad_path = tmp_path / "bad-encoding.md"
    bad_path.write_bytes(b"\xff\xfe not valid utf-8")
    result = subprocess.run(
        [sys.executable, str(Path(cas.__file__).resolve()), "--body", str(bad_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "error: body file is not valid UTF-8:" in result.stderr

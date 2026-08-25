#!/usr/bin/env python3
"""Report (and fail CI on) retrospective issues with no citing commit.

Issue #297 (refs #187, #242, #246): `merge-retrospective`'s Step 0
requires, every cycle, a manual search of every `retrospective`-labelled
issue for a commit on `main` citing it. Issue #187 proposed automating
this as a meta-gate; #242 and #246 each ran that search by hand again and
confirmed the meta-gate itself was never built. This script mechanizes
Step 0's own method (list `retrospective`-labelled issues, unfiltered by
state; search `main`'s commit history for a citing `#N`) and fails when
the count of issues with zero citing commits exceeds a threshold.

Design: docs/superpowers/specs/2026-07-22-retrospective-gate-drift-design.md

Split into pure logic (fixture-testable, no I/O) and I/O glue (GitHub REST
API over `urllib`, a local `git log`, plus a `.gitapex/ssot.json` read).
Deliberately dependency-light (stdlib plus `pydantic`, this repository's own
pinned CLI-arg validation dependency) and does not import
`gitapex_sync_pr_publish.py` -- this
repository keeps `.github/scripts/*.py` files independently self-contained
(see `gitapex_gate_skill_rename_lifecycle.py`'s own docstring for the same
rationale) even though the retry-with-backoff shape below mirrors
`gitapex_sync_pr_publish.apply_call`.

Issue #709: a citing commit alone is not proof the issue's proposed gate
was actually built -- `#N` in a commit message only shows someone worked
on *something related to* issue N. An issue now clears the no-citation
report only when a citing commit AND a corroborating
`.gitapex/ssot.json` `gates[].tracking_issue == N` entry both agree
(`load_gate_tracking_issue_counts`, wired into `find_no_citation_issues`).
Issue #1177 widens this from "does at least one gate cite N" to "do at
least as many gates cite N as `proposed_gates[]` requires"
(`load_proposed_gate_requirements`), so a multi-gate retrospective issue
cannot clear on its first citation alone.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_scan_retrospective_gate_drift.py \\
        --owner tvna --repo gitapex --ref HEAD --threshold 20

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs), matching retrospective-gate-drift.yml's own
invocation.

Environment variables:
    GITHUB_TOKEN  GitHub token with read access to issues (the default
                  Actions token's `issues: read` permission suffices).

Exit codes:
    0  No-citation count does not exceed the threshold.
    1  No-citation count exceeds the threshold, or a GitHub API / git
       error prevented the check from completing (never silently
       reported as "zero issues found").
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from collections.abc import Callable
from typing import Any

import _gitapex_github_http
from _gitapex_github_http import GitHubApiError
from pydantic import BaseModel, Field, ValidationError, field_validator

DEFAULT_THRESHOLD = 20
DEFAULT_LABEL = "retrospective"

_API_ROOT = "https://api.github.com"
_PER_PAGE = 100

# Record separator (0x1e) / unit separator (0x1f): neither appears in real
# commit messages, so they safely delimit `git log` entries and fields
# without a risk of an attacker-controlled commit message forging a fake
# boundary the way a printable delimiter (comma, pipe, newline) could.
_LOG_FORMAT = "%x1e%H%x1f%B"


class GitLogError(RuntimeError):
    """Raised when the local `git log` invocation fails."""


class SsotLedgerError(RuntimeError):
    """Raised when `.gitapex/ssot.json` cannot be read as a usable gate
    registry. Never caught and silently downgraded to an empty
    corroboration set -- that would reopen the exact bare-citation
    false-negative issue #709 exists to close."""


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def _citation_pattern(issue_number: int) -> re.Pattern[str]:
    # Digit-boundary-aware: "#187" matches, but neither "#1870" nor "#2187"
    # does -- a plain substring or `\b`-based match would treat "7" and "0"
    # (both word characters) as a boundary and false-positive on unrelated
    # larger issue/PR numbers that happen to contain the target as a prefix
    # or suffix.
    return re.compile(rf"(?<!\d)#{issue_number}(?!\d)")


def citation_count(commit_messages: list[str], issue_number: int) -> int:
    """Count how many of `commit_messages` cite `issue_number`."""
    pattern = _citation_pattern(issue_number)
    return sum(1 for message in commit_messages if pattern.search(message))


def find_no_citation_issues(
    issue_numbers: list[int],
    commit_messages: list[str],
    tracking_issue_gate_counts: dict[int, int],
    proposed_gate_requirements: dict[int, int],
) -> list[int]:
    """Return the subset of `issue_numbers` that lack either a citing
    commit or enough corroborating `.gitapex/ssot.json` `gates[].tracking_issue`
    entries.

    Issue #709: a bare citing commit is not sufficient on its own -- it is
    evidence someone touched *something related to* the issue, not proof
    its proposed gate was built. An issue number clears (is excluded from
    the returned list) only when both signals agree: at least one commit
    cites it AND at least `required` distinct `gates[]` entries carry it as
    their own `tracking_issue`.

    Issue #1177: `required` is no longer always 1. A retrospective issue
    whose own Repairs section proposed several distinct gates registers
    that count in `.gitapex/ssot.json`'s `proposed_gates[]` manifest
    (`proposed_gate_requirements`, `{tracking_issue: len(proposals)}`);
    an issue absent from that manifest defaults to `required = 1`,
    preserving the original single-citation behavior unchanged. This is
    count-based, not slug-identity-based: which specific `gates[]` id
    satisfies which proposal is never checked, only how many exist.
    """
    result = []
    for n in issue_numbers:
        if citation_count(commit_messages, n) == 0:
            result.append(n)
            continue
        required = proposed_gate_requirements.get(n, 1)
        if tracking_issue_gate_counts.get(n, 0) < required:
            result.append(n)
    return result


def evaluate(no_citation_count: int, threshold: int) -> bool:
    """Return True iff `no_citation_count` exceeds `threshold`."""
    return no_citation_count > threshold


def format_report(no_citation_issues: list[int], total_issues: int, threshold: int) -> str:
    """Human-readable report, printed to stdout and captured in the CI step summary."""
    no_citation_count = len(no_citation_issues)
    lines = [
        f"Retrospective gate-drift report: {no_citation_count} of {total_issues} "
        f"'{DEFAULT_LABEL}'-labelled issues have no citing commit on main "
        f"(threshold: {threshold}).",
    ]
    if no_citation_issues:
        lines.append("Issues with no citing commit:")
        lines.extend(f"  #{n}" for n in sorted(no_citation_issues))
    else:
        lines.append(f"Every '{DEFAULT_LABEL}'-labelled issue has at least one citing commit.")
    if evaluate(no_citation_count, threshold):
        lines.append(f"FAIL: {no_citation_count} exceeds threshold {threshold}.")
    else:
        lines.append(f"PASS: {no_citation_count} does not exceed threshold {threshold}.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O glue
# ---------------------------------------------------------------------------


# Issue #726: the generic, endpoint-agnostic retry/pagination client
# lives in `_gitapex_github_http.py`, shared with `gitapex_compute_gprr.py`, so this
# script does not duplicate it and does not need `gitapex_compute_gprr.py` (or
# any other script) importing this file just to reach it. Re-exported
# under their prior local names so every existing call site and test
# below (`fetch_json_page(...)`, `opener=_default_opener`) is unchanged.
_default_opener = _gitapex_github_http.default_opener
fetch_json_page = _gitapex_github_http.fetch_json_page


def list_labelled_issue_records(
    owner: str,
    repo: str,
    label: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    """Return the full issue record (as GitHub's REST API returns it) for
    every issue carrying `label`, unfiltered by state (matches
    merge-retrospective's own Step 0 method, which deliberately does not
    limit the search to open issues). Issue #726: this is the shared fetch
    both `list_labelled_issues` below (bare issue numbers, for the
    citation-drift check) and `gitapex_compute_gprr.py` (full records -- it needs
    `body` and `created_at`, not just `number`) build on, so pagination and
    retry logic exists exactly once."""
    sleeper = sleeper if sleeper is not None else time.sleep
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{_API_ROOT}/repos/{owner}/{repo}/issues?labels={label}&state=all&per_page={_PER_PAGE}&page={page}"
        items = fetch_json_page(url, token, opener, sleeper)
        if not items:
            break
        for item in items:
            # The issues-list endpoint also returns pull requests; a
            # retrospective issue is never a PR, so this is a defensive
            # exclusion rather than an expected real-world hit.
            if "pull_request" in item:
                continue
            records.append(item)
        if len(items) < _PER_PAGE:
            break
        page += 1
    return records


def list_labelled_issues(
    owner: str,
    repo: str,
    label: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> list[int]:
    """Return issue numbers carrying `label`, unfiltered by state. Thin
    wrapper over `list_labelled_issue_records` -- see that function's
    docstring for why the fetch itself lives there."""
    records = list_labelled_issue_records(owner, repo, label, token, opener, sleeper)
    return [record["number"] for record in records]


def git_commit_messages(
    ref: str,
    cwd: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Return the full message (subject + body) of every commit reachable
    from `ref`, via a local `git log` in `cwd`."""
    result = runner(
        ["git", "log", ref, f"--pretty=format:{_LOG_FORMAT}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitLogError(f"git log {ref} failed: {result.stderr.strip()}")

    messages: list[str] = []
    for entry in result.stdout.split("\x1e"):
        if not entry:
            continue
        _sha, _, message = entry.partition("\x1f")
        messages.append(message.rstrip("\n"))
    return messages


def _load_ssot_registry(path: str) -> dict[str, Any]:
    """Read and JSON-decode `.gitapex/ssot.json`, raising `SsotLedgerError`
    on any failure rather than returning a fallback. Shared by
    `load_gate_tracking_issue_counts` and `load_proposed_gate_requirements`
    below -- both need the same read-and-decode step before extracting
    their own distinct key."""
    try:
        raw = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SsotLedgerError(f"{path}: gate registry cannot be read: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SsotLedgerError(f"{path}: gate registry is not valid JSON: {error}") from error

    # `[]`, `"x"`, and `1` are all valid JSON, so a successful parse does
    # not mean the shape is usable -- without this guard, `data.get` below
    # would raise an uncaught AttributeError instead of the documented
    # SsotLedgerError.
    if not isinstance(data, dict):
        raise SsotLedgerError(f"{path}: gate registry must be a JSON object, got {type(data).__name__}")
    return data


def _gate_tracking_issue_counts_from_registry(path: str, data: dict[str, Any]) -> dict[int, int]:
    """Pure extraction half of `load_gate_tracking_issue_counts` below,
    taking an already-loaded registry dict instead of reading `path`
    itself -- shared with `load_gate_and_proposed_gate_corroboration` so a
    caller needing both readers' output does not pay for two separate
    file reads and JSON decodes of the same `.gitapex/ssot.json`."""
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SsotLedgerError(f"{path}: gate registry has no usable 'gates' list")

    counts: dict[int, int] = {}
    for gate in gates:
        tracking_issue = gate.get("tracking_issue") if isinstance(gate, dict) else None
        # `bool` is an `int` subclass in Python, so `isinstance(True, int)`
        # is True -- without the extra check, a stray `"tracking_issue":
        # true` would silently corroborate issue #1 instead of being
        # skipped as the malformed value it is.
        if isinstance(tracking_issue, int) and not isinstance(tracking_issue, bool):
            counts[tracking_issue] = counts.get(tracking_issue, 0) + 1
    return counts


def load_gate_tracking_issue_counts(path: str) -> dict[int, int]:
    """Return, for every `.gitapex/ssot.json` `gates[].tracking_issue`
    value, how many `gates[]` entries carry it.

    Issue #709's corroborating signal, widened by issue #1177 from a bare
    `set[int]` ("does at least one gate cite this issue") to a per-issue
    count ("how many gates cite this issue"), so a multi-gate retrospective
    issue's resolution can be compared against how many gates it actually
    proposed rather than clearing on the first one built. Raises
    `SsotLedgerError` rather than returning an empty dict on a
    missing/malformed registry -- an empty dict here would silently widen
    the no-citation report back to bare-citation-only behavior, the exact
    false-negative class this check exists to close. Mirrors
    `gitapex_detect_changed_gate_scripts.py`'s `registered_gate_paths()`
    fail-closed shape.
    """
    return _gate_tracking_issue_counts_from_registry(path, _load_ssot_registry(path))


def _proposed_gate_requirements_from_registry(path: str, data: dict[str, Any]) -> dict[int, int]:
    """Pure extraction half of `load_proposed_gate_requirements` below --
    see `_gate_tracking_issue_counts_from_registry`'s own docstring for
    why this split exists.

    Deliberately fail-closed per malformed entry, unlike
    `_gate_tracking_issue_counts_from_registry`'s tolerant skip of a
    malformed `gates[].tracking_issue`: an adversarial-gate-quality review
    of this PR found that the two skips, though structurally parallel,
    have opposite risk directions. Skipping a malformed `gates[]` entry
    only under-counts a citation, which can never falsely resolve an
    issue (fail-closed, safe). Skipping a malformed `proposed_gates[]`
    entry would silently fall the requirement back to the weaker default
    of 1, which *can* falsely resolve a multi-gate issue on its first
    citation -- exactly the false-clear this module exists to prevent.
    So a malformed entry here raises instead of being dropped.
    """
    proposed_gates = data.get("proposed_gates")
    if proposed_gates is None:
        return {}
    if not isinstance(proposed_gates, list):
        raise SsotLedgerError(f"{path}: gate registry's 'proposed_gates' must be a list")

    requirements: dict[int, int] = {}
    for entry in proposed_gates:
        if not isinstance(entry, dict):
            raise SsotLedgerError(f"{path}: gate registry's 'proposed_gates' has a non-object entry: {entry!r}")
        tracking_issue = entry.get("tracking_issue")
        proposals = entry.get("proposals")
        if not (isinstance(tracking_issue, int) and not isinstance(tracking_issue, bool)):
            raise SsotLedgerError(
                f"{path}: gate registry's 'proposed_gates' entry has a non-integer tracking_issue: {tracking_issue!r}"
            )
        if not isinstance(proposals, list):
            raise SsotLedgerError(
                f"{path}: gate registry's 'proposed_gates' entry for tracking_issue {tracking_issue} "
                f"has a non-list 'proposals': {proposals!r}"
            )
        if tracking_issue in requirements:
            raise SsotLedgerError(
                f"{path}: gate registry's 'proposed_gates' has more than one entry for tracking_issue {tracking_issue}"
            )
        requirements[tracking_issue] = len(proposals)
    return requirements


def load_proposed_gate_requirements(path: str) -> dict[int, int]:
    """Return, for every `.gitapex/ssot.json` `proposed_gates[]` entry, how
    many distinct gates its own retrospective issue requires
    (`len(proposals)`).

    Issue #1177. A tracking_issue absent from the returned dict defaults
    to `required = 1` at the call site (`find_no_citation_issues`),
    preserving this check's original single-citation behavior for every
    issue that has not (yet) registered a manifest entry. `proposed_gates`
    missing entirely, or present but empty, both yield `{}` -- this
    manifest is additive and populated only going forward, unlike `gates`,
    so its absence is not itself an error the way an empty/missing
    `gates` list is (see `load_gate_tracking_issue_counts` above). A
    malformed individual entry (non-dict, non-integer `tracking_issue`, or
    non-list `proposals`) raises `SsotLedgerError` rather than being
    skipped -- unlike `load_gate_tracking_issue_counts`'s tolerant skip of
    a malformed `gates[].tracking_issue`, skipping here would silently
    fall a real issue's requirement back to the weaker default of 1,
    which can falsely resolve it (see
    `_proposed_gate_requirements_from_registry`'s own docstring for the
    full asymmetry). A duplicate `tracking_issue` across `proposed_gates`
    raises `SsotLedgerError` -- `.gitapex/ssot.schema.json`'s own
    `find_duplicate_proposed_gate_tracking_issues` drift check is the
    primary gate against this ever reaching `main`, but this loader does
    not silently pick a winner if it somehow does.
    """
    return _proposed_gate_requirements_from_registry(path, _load_ssot_registry(path))


def load_gate_and_proposed_gate_corroboration(path: str) -> tuple[dict[int, int], dict[int, int]]:
    """Return `(load_gate_tracking_issue_counts(path),
    load_proposed_gate_requirements(path))`, reading and JSON-decoding
    `path` exactly once rather than the twice that calling those two
    functions separately would cost -- both need the same parsed
    registry, and `main()` below always needs both together."""
    data = _load_ssot_registry(path)
    return (
        _gate_tracking_issue_counts_from_registry(path, data),
        _proposed_gate_requirements_from_registry(path, data),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


# This CLI's own wording for each constraint the model below imposes, keyed
# by pydantic's own error type. pydantic's message text is deliberately not
# echoed -- it is not part of this CLI's contract, so a version bump must
# not change what an operator reads -- but naming only the offending flag
# and nothing else leaves the operator without the reason. An unmapped type
# falls back to a generic label rather than raising, so a future constraint
# kind can never turn a rejected argument into a traceback.
_CONSTRAINT_HINTS = {
    "string_too_short": "must not be blank",
    # Issue #1087: min_length=1 alone accepts a whitespace-only string; the
    # validator below closes that with a plain ValueError, which pydantic
    # reports as this generic type. Reuses "must not be blank" since an
    # operator would never need to distinguish it from a truly empty value.
    # Keyed on pydantic's error *type* alone, not on which validator raised
    # it: a future field_validator added to this model that raises a plain
    # ValueError for an unrelated reason would also render here as "must
    # not be blank" -- give it a distinct error type or extend this dict
    # deliberately rather than letting it fall through this entry.
    "value_error": "must not be blank",
}


def _is_blank(value: str) -> bool:
    """True iff every character in `value` is ordinary whitespace or a
    Unicode Format-category (Cf) mark -- invisible either way. Cf covers
    U+200B ZERO WIDTH SPACE, U+FEFF ZERO WIDTH NO-BREAK SPACE, and U+180E
    MONGOLIAN VOWEL SEPARATOR, none of which str.strip() removes -- so a
    value made solely of Cf marks passed the old `.strip()`-only check
    unrejected (issue #1094)."""
    return all(char.isspace() or unicodedata.category(char) == "Cf" for char in value)


class ScanRetrospectiveGateDriftArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace. Every field rejects a
    blank value: argparse's own ``required=True`` only guarantees the flag
    was passed, not that its value is non-empty, and ``ref``/``cwd``/
    ``label``/``ssot_path`` each become a real ref/path/query fragment
    downstream where an empty value was never a meaningful input.
    ``threshold`` is deliberately absent from this model -- it keeps its
    bare ``int`` type with no floor, since a caller intentionally passing
    a negative threshold to force a hard fail is unusual, not malformed."""

    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    cwd: str = Field(min_length=1)
    label: str = Field(min_length=1)
    ssot_path: str = Field(min_length=1)

    @field_validator("owner", "repo", "ref", "cwd", "label", "ssot_path")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        # Checked via _is_blank() without storing a stripped result -- this
        # validates, it does not trim (issue #1087). _is_blank() also
        # rejects a value made solely of Unicode Format-category (Cf)
        # characters, which plain .strip() leaves in place (issue #1094).
        if _is_blank(value):
            raise ValueError("must not be blank")
        return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report and fail on retrospective-labelled issues with no citing commit."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument("--ref", default="HEAD", help="Git ref to search for citing commits (default: HEAD)")
    parser.add_argument("--cwd", default=".", help="Repository working directory for git log (default: .)")
    parser.add_argument("--label", default=DEFAULT_LABEL, help=f"Issue label to search (default: {DEFAULT_LABEL})")
    parser.add_argument(
        "--ssot-path",
        default=".gitapex/ssot.json",
        help="Path (relative to --cwd) to the gate registry used as the corroborating "
        "signal (default: .gitapex/ssot.json)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Fail if the no-citation count exceeds this value (default: {DEFAULT_THRESHOLD})",
    )
    args = parser.parse_args(argv)
    try:
        ScanRetrospectiveGateDriftArgs(
            owner=args.owner,
            repo=args.repo,
            ref=args.ref,
            cwd=args.cwd,
            label=args.label,
            ssot_path=args.ssot_path,
        )
    except ValidationError as error:
        # Only the offending flag names and this CLI's own constraint
        # wording are echoed -- never pydantic's own message text, and
        # never the rejected value itself.
        invalid = ", ".join(
            f"--{str(item['loc'][0]).replace('_', '-')} ({_CONSTRAINT_HINTS.get(item['type'], 'invalid value')})"
            for item in error.errors()
        )
        print(f"error: invalid arguments: {invalid}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("error: GITHUB_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    try:
        issue_numbers = list_labelled_issues(args.owner, args.repo, args.label, token)
        commit_messages = git_commit_messages(args.ref, args.cwd)
        ssot_path = str(pathlib.Path(args.cwd) / args.ssot_path)
        tracking_issue_gate_counts, proposed_gate_requirements = load_gate_and_proposed_gate_corroboration(ssot_path)
    except (GitHubApiError, GitLogError, SsotLedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    no_citation_issues = find_no_citation_issues(
        issue_numbers, commit_messages, tracking_issue_gate_counts, proposed_gate_requirements
    )
    print(format_report(no_citation_issues, len(issue_numbers), args.threshold))
    return 1 if evaluate(len(no_citation_issues), args.threshold) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Report (and fail CI on) `gate-proposal`-labelled issue drift.

Issue #1406 (refs #297, #187, #242, #246, #709, #1297; supersedes this
script's own prior scope): the flat gate-proposal-issues design
(`docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md`)
files every `missing-deterministic-gate` retrospective finding as its own
standalone, `gate-proposal`-labelled issue (Decision 1) rather than
leaving it embedded in an ever-growing `retrospective`-labelled issue.
This script is rescoped to audit *that* new label instead of sweeping
every `retrospective`-labelled issue for a citing commit -- the prior
345-issue-wide citation-drift sweep this docstring used to describe is
retired along with the design it audited.

Two passes, both gated by a label-liveness guard that must pass first:

  (a) Primary, threshold-gated: count of currently-open `gate-proposal`-
      labelled issues (a plain `state=open` + label search -- the actual
      backlog size). Threshold unchanged from before this rescope (20).
  (b) Secondary, unbounded and zero-tolerance: every issue in state
      `closed` carrying the label -- no `closed_at` time window, no
      filtering by age -- re-run the existing two-signal check (issue
      #709: a commit on the checked ref citing the issue's own number,
      AND a corroborating `.gitapex/ssot.json` `gates[].tracking_issue`
      entry naming that same number) on each, after excluding any whose
      own `state_reason` is `not_planned` or `duplicate` (a legitimately
      declined proposal, not a silent-close failure). Any remaining,
      non-exempt issue that closed without passing the check fails this
      run. There is no reopen action of any kind -- this pass only
      detects and fails loudly; a human resolves it by hand afterward
      (Decision 5's own scope: detection, not remediation).

**Label-liveness guard**: both passes assume `gate-proposal` itself still
exists as a repository label. Before either runs, `label_exists` confirms
it via a plain `GET /repos/{owner}/{repo}/labels/{name}` lookup; a
missing label fails loudly, naming it explicitly, rather than reporting a
clean zero-count pass that cannot be told apart from "the label was
renamed or deleted out from under this check."

`GATE_PROPOSAL_LABEL` (Decision 6) is this script's own independent copy
of the literal string `"gate-proposal"` -- a parallel copy of the same
constant `skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
defines, never an import of it: `docs/repository-layout.md` states
`.github/` never ships with the installed plugin, so a cross-tree import
would break at install time exactly like
`hooks/gitapex_check_pr_title_convention.py` and
`.github/scripts/gitapex_gate_pr_title_convention.py`'s own pre-existing
independent-copy pair for the identical structural reason. A dedicated
sync test, `tests/test_gitapex_retro_gate_label_sync.py`, keeps the two
copies from silently drifting apart -- not owned by this file.

`DEFAULT_LABEL` (`"retrospective"`) is kept, unrescoped, purely because
`gitapex_compute_gprr.py` imports it as its own CLI default for an
unrelated concern (the Gate-Preventable Repair Rate, computed over
`retrospective`-labelled issues regardless of this script's own scope) --
this script's own CLI no longer defaults to it anywhere.

The two-signal check itself (issue #709) is unchanged in *logic*, only in
*scope*: `find_no_citation_issues` is the same function this script
always had, now run over the `gate-proposal`-labelled closed set instead
of the full `retrospective`-labelled sweep.

Split into pure logic (fixture-testable, no I/O) and I/O glue (GitHub REST
API over `urllib`, a local `git log`, plus a `.gitapex/ssot.json` read).
Deliberately dependency-light (stdlib plus `pydantic`, this repository's own
pinned CLI-arg validation dependency) and does not import
`gitapex_sync_pr_publish.py` -- this
repository keeps `.github/scripts/*.py` files independently self-contained
(see `gitapex_gate_skill_rename_lifecycle.py`'s own docstring for the same
rationale) even though the retry-with-backoff shape below mirrors
`gitapex_sync_pr_publish.apply_call`.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_scan_retrospective_gate_drift.py \\
        --owner tvna --repo gitapex --ref HEAD --threshold 20

Run via `uv run` (needed for the pydantic import -- a bare `python3`
invocation without pydantic installed now fails at import time, before
argparse even runs), matching retrospective-gate-drift.yml's own
invocation.

Environment variables:
    GITHUB_TOKEN  GitHub token with read access to issues (the default
                  Actions token's `issues: read` permission suffices --
                  this script never writes, so no elevated scope is ever
                  requested).

Exit codes:
    0  The open-issue count does not exceed the threshold, and every
       closed labelled issue either passed the two-signal check or was
       exempt.
    1  The open-issue count exceeds the threshold, or at least one closed
       labelled issue never passed the two-signal check and was not
       exempt, or the `gate-proposal` label itself does not exist, or a
       GitHub API / git error prevented the check from completing (never
       silently reported as "zero issues found").
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
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

import _gitapex_github_http
from _gitapex_github_http import GitHubApiError
from pydantic import BaseModel, Field, ValidationError, field_validator

DEFAULT_THRESHOLD = 20

# Kept solely because gitapex_compute_gprr.py imports this name as its own
# CLI default (an unrelated GPRR concern over `retrospective`-labelled
# issues) -- see module docstring. Not used as this script's own CLI
# default any more; that is GATE_PROPOSAL_LABEL below.
DEFAULT_LABEL = "retrospective"

# Decision 6: this script's own independent copy of the label literal --
# never imported from skills/merge-retrospective/scripts/
# gitapex_file_gate_proposal.py. See module docstring for why.
GATE_PROPOSAL_LABEL = "gate-proposal"

_API_ROOT = "https://api.github.com"
_PER_PAGE = 100

# Decision 5: a closed gate-proposal issue with either state_reason is a
# legitimately declined proposal, not a silent-close failure -- exempted
# from the zero-tolerance integrity pass rather than flagged forever.
_EXEMPT_CLOSED_STATE_REASONS = frozenset({"not_planned", "duplicate"})

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
    tracking_issues: set[int],
) -> list[int]:
    """Return the subset of `issue_numbers` that lack either a citing
    commit or a corroborating `.gitapex/ssot.json` `tracking_issue` entry.

    The two-signal check (issue #709): a bare citing commit is not
    sufficient on its own -- it is evidence someone touched *something
    related to* the issue, not proof its proposed gate was built. An
    issue number clears (is excluded from the returned list) only when
    both signals agree: at least one commit cites it AND
    `tracking_issues` contains it.

    Used by `main` below for the closed-issue zero-tolerance integrity
    pass (b) -- unchanged logic from this script's prior, wider
    `retrospective`-label sweep, only the caller's own issue-number set
    has changed scope."""
    return [n for n in issue_numbers if citation_count(commit_messages, n) == 0 or n not in tracking_issues]


def evaluate(count: int, threshold: int) -> bool:
    """Return True iff `count` exceeds `threshold`. Used for the open-issue
    backlog size in pass (a)."""
    return count > threshold


def format_open_count_report(open_count: int, threshold: int, label: str) -> str:
    """Human-readable report for pass (a), printed to stdout and captured
    in the CI step summary."""
    lines = [
        f"Retrospective gate-drift report: {open_count} currently-open '{label}'-labelled "
        f"issue(s) (threshold: {threshold}).",
    ]
    if evaluate(open_count, threshold):
        lines.append(f"FAIL: {open_count} exceeds threshold {threshold}.")
    else:
        lines.append(f"PASS: {open_count} does not exceed threshold {threshold}.")
    return "\n".join(lines)


def is_exempt_closed_issue(state_reason: str | None) -> bool:
    """True iff `state_reason` legitimately excuses a closed
    `gate-proposal` issue from the two-signal integrity check (Decision
    5) -- a declined proposal is not a silent-close failure."""
    return state_reason in _EXEMPT_CLOSED_STATE_REASONS


def partition_exempt_closed_issues(records: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    """Partition full closed-issue `records` (each carrying `number` and
    `state_reason`) into `(exempt, remaining)` issue numbers, preserving
    order. Run *before* `find_no_citation_issues` -- an exempt issue must
    never inflate the integrity-failure report just because it closed
    without a citing commit or tracking entry; it was never expected to
    have either."""
    exempt: list[int] = []
    remaining: list[int] = []
    for record in records:
        number = record["number"]
        if is_exempt_closed_issue(record.get("state_reason")):
            exempt.append(number)
        else:
            remaining.append(number)
    return exempt, remaining


def format_closed_integrity_report(
    unverified_issues: list[int], total_closed: int, exempt_count: int, label: str
) -> str:
    """Human-readable report for pass (b), printed to stdout and captured
    in the CI step summary. Zero-tolerance: any non-exempt entry in
    `unverified_issues` fails this pass, regardless of how small it is
    relative to `total_closed` -- unlike pass (a), this is not
    threshold-gated (Decision 5)."""
    lines = [
        f"Closed '{label}'-labelled issue integrity: {len(unverified_issues)} of {total_closed} closed "
        f"issue(s) closed without passing the two-signal check ({exempt_count} exempted by state_reason "
        "not_planned/duplicate).",
    ]
    if unverified_issues:
        lines.append("Closed issues with no verified gate (no reopen action taken -- resolve by hand):")
        lines.extend(f"  #{n}" for n in sorted(unverified_issues))
        lines.append(f"FAIL: {len(unverified_issues)} closed issue(s) never passed the two-signal check.")
    else:
        lines.append("PASS: every closed issue either passed the two-signal check or was exempt.")
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


def label_exists(
    owner: str,
    repo: str,
    label: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
) -> bool:
    """Return True iff `label` exists on the repository -- a plain
    `GET /repos/{owner}/{repo}/labels/{name}` lookup (the label-liveness
    guard both passes below require before running).

    An HTTP 404 is the only outcome treated as "does not exist"; any
    other non-2xx status or a persistent network failure still raises
    `GitHubApiError` via `_gitapex_github_http.fetch_json_document`'s own
    retry/backoff, rather than being silently folded into "missing" --
    this guard must itself fail loudly on an inconclusive result, the
    same fail-closed posture it exists to give the two passes that depend
    on it. Mirrors `gitapex_gate_acm_issue_disclosure.py`'s own
    `ensure_label_exists`, which checks its analogous idempotent-422 case
    the identical way: catch, inspect the HTTP code in the message, only
    then decide."""
    sleeper = sleeper if sleeper is not None else time.sleep
    url = f"{_API_ROOT}/repos/{owner}/{repo}/labels/{urllib.parse.quote(label, safe='')}"
    try:
        _gitapex_github_http.fetch_json_document(url, token, opener, sleeper)
    except GitHubApiError as error:
        if "HTTP 404" in str(error):
            return False
        raise
    return True


def list_labelled_issue_records(
    owner: str,
    repo: str,
    label: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any] = _default_opener,
    sleeper: Callable[[float], None] | None = None,
    state: str = "all",
) -> list[dict[str, Any]]:
    """Return the full issue record (as GitHub's REST API returns it) for
    every issue carrying `label` in the given `state` (`"all"` by
    default, matching this function's own pre-rescope behavior --
    `gitapex_compute_gprr.py` calls this positionally with exactly four
    arguments and depends on that default staying "all"). `state` is
    appended after the pre-existing `opener`/`sleeper` parameters rather
    than inserted before them, so every pre-existing positional call site
    (including `list_labelled_issues` below, which calls this
    positionally through `sleeper`) is unaffected.

    `main` below passes `state="open"` and `state="closed"` explicitly
    for its own two passes. Issue #726: this is the shared fetch both
    `list_labelled_issues` below (bare issue numbers) and
    `gitapex_compute_gprr.py` (full records -- it needs `body` and
    `created_at`, not just `number`) build on, so pagination and retry
    logic exists exactly once.

    `label` is percent-quoted before it reaches the query string, exactly
    as `label_exists` above already quotes it. Interpolating it raw made
    the liveness guard and the passes it guards disagree about which
    label they were even asking for: a GitHub label name may contain a
    space or an `&` (`good first issue` is GitHub's own default), so a
    raw `labels={label}` either emitted a space into the request line or
    let the label's own text inject a second `state=` parameter ahead of
    this function's -- a silently-wrong answer of exactly the class the
    liveness guard exists to rule out, reported as a clean count."""
    sleeper = sleeper if sleeper is not None else time.sleep
    quoted_label = urllib.parse.quote(label, safe="")
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            f"{_API_ROOT}/repos/{owner}/{repo}/issues"
            f"?labels={quoted_label}&state={state}&per_page={_PER_PAGE}&page={page}"
        )
        items = fetch_json_page(url, token, opener, sleeper)
        if not items:
            break
        for item in items:
            # The issues-list endpoint also returns pull requests; a
            # retrospective/gate-proposal issue is never a PR, so this is
            # a defensive exclusion rather than an expected real-world hit.
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


def load_gate_tracking_issues(path: str) -> set[int]:
    """Return every `.gitapex/ssot.json` `gates[].tracking_issue` value.

    Issue #709's corroborating signal. Raises `SsotLedgerError` rather
    than returning an empty set on a missing/malformed registry -- an
    empty set here would silently widen the integrity report back to
    bare-citation-only behavior, the exact false-negative class this
    check exists to close. Mirrors `gitapex_detect_changed_gate_scripts.py`'s
    `registered_gate_paths()` fail-closed shape.
    """
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
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise SsotLedgerError(f"{path}: gate registry has no usable 'gates' list")

    tracking_issues: set[int] = set()
    for gate in gates:
        tracking_issue = gate.get("tracking_issue") if isinstance(gate, dict) else None
        # `bool` is an `int` subclass in Python, so `isinstance(True, int)`
        # is True -- without the extra check, a stray `"tracking_issue":
        # true` would silently corroborate issue #1 instead of being
        # skipped as the malformed value it is. A gate legitimately
        # tracked under more than one issue (issue #1425) stores a list;
        # flatten it the same way a bare int is added.
        candidates = tracking_issue if isinstance(tracking_issue, list) else [tracking_issue]
        for candidate in candidates:
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                tracking_issues.add(candidate)
    return tracking_issues


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
        description="Confirm the gate-proposal label exists, then report (and fail CI on) its "
        "open-issue backlog size and any closed issue that never passed the two-signal "
        "gate-resolution check."
    )
    parser.add_argument("--owner", required=True, help="Repository owner, e.g. tvna")
    parser.add_argument("--repo", required=True, help="Repository name, e.g. gitapex")
    parser.add_argument("--ref", default="HEAD", help="Git ref to search for citing commits (default: HEAD)")
    parser.add_argument("--cwd", default=".", help="Repository working directory for git log (default: .)")
    parser.add_argument(
        "--label",
        default=GATE_PROPOSAL_LABEL,
        help=f"Issue label to search (default: {GATE_PROPOSAL_LABEL})",
    )
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
        help=f"Fail if the open-issue count exceeds this value (default: {DEFAULT_THRESHOLD})",
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
        if not label_exists(args.owner, args.repo, args.label, token):
            print(
                f"error: label '{args.label}' does not exist on {args.owner}/{args.repo} -- "
                "cannot tell a genuinely empty backlog apart from a renamed/deleted label; "
                "create the label (or fix --label) before this check can run",
                file=sys.stderr,
            )
            return 1
        open_records = list_labelled_issue_records(args.owner, args.repo, args.label, token, state="open")
        closed_records = list_labelled_issue_records(args.owner, args.repo, args.label, token, state="closed")
        commit_messages = git_commit_messages(args.ref, args.cwd)
        tracking_issues = load_gate_tracking_issues(str(pathlib.Path(args.cwd) / args.ssot_path))
    except (GitHubApiError, GitLogError, SsotLedgerError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    open_count = len(open_records)
    exempt_numbers, remaining_numbers = partition_exempt_closed_issues(closed_records)
    unverified_closed_issues = find_no_citation_issues(remaining_numbers, commit_messages, tracking_issues)

    print(format_open_count_report(open_count, args.threshold, args.label))
    print(
        format_closed_integrity_report(unverified_closed_issues, len(closed_records), len(exempt_numbers), args.label)
    )

    open_over_threshold = evaluate(open_count, args.threshold)
    closed_integrity_failed = bool(unverified_closed_issues)
    return 1 if (open_over_threshold or closed_integrity_failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

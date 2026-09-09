#!/usr/bin/env python3
"""CI gate: a `docs/gitapex/plans/*.md` task list this diff adds or
modifies must name its source Issue URL and cite `Source ACM rows` for
each task.

Issue #1796 (ACM row 6), mirroring the `docs/gitapex/specs/*.md` entry
issue #1700 already registered for `design-doc-pattern-dryrun`. This is a
shape gate, not a soundness gate: it checks that the two citations exist
somewhere in a diff-touched file's content, not that they are correct or
that every individual task actually has one -- the same disclosure-not-
soundness scope `gitapex_gate_skill_audit_disclosure.py`'s own docstring
states for its two audit checks ("checks that disclosure was made, not
that the audits actually passed").

**Scoped to diff-touched files only, never the whole corpus.** Confirmed
live before this gate shipped: of the 20 pre-existing files under
`docs/gitapex/plans/`, 5 had no `Issue: <url>` line at all (one used a
bare `Issue: #1879` instead of a full URL) and 11 had no `Source ACM
rows?:` citation. A gate that scanned every file under `docs/gitapex/
plans/` unconditionally would fail CI on every unrelated PR that never
touches that directory. `--check-diff BASE_REF HEAD_REF` computes exactly
which files this diff adds or modifies (a three-dot/merge-base diff,
`D`/`R100` excluded -- a deletion or byte-identical rename has no new
content to check) and grades only those, mirroring
`gitapex_gate_skill_audit_disclosure.py`'s own `--check-diff` mode and
`gitapex_compute_skill_audit_flags.py`'s `_added_or_modified` filter.

**Fail-closed on malformed/missing input**
(`skills/evaluating-deterministic-gate-quality/references/dimensions.md`
dimension 15): a blank ref, an unparseable `--name-status` line, a
`docs/gitapex/plans/*.md` path with an unsupported (e.g. nested) shape, a
git failure, or non-UTF-8 file content all raise `GateError` and exit 1 --
never a silent pass. Empty or missing file content reads as missing both
citations, never as an accidental pass.

**Fenced-code-block stripping.** A ` ``` `-fenced block is removed from a
file's content before either citation is searched for, so a citation
string quoted only as a documentation example inside one -- e.g. this very
gate's own design doc quoting `` `Source ACM rows?:` `` while describing
the convention -- does not count as a genuine citation. A citation quoted
mid-sentence (not at the start of a line) is already excluded by the two
patterns' own line-anchored `^` match and needs no separate handling; see
`tests/test_gitapex_gate_plans_traceability.py`'s defeat tests for both
shapes, live-verified rather than assumed.

Usage::

    uv run --frozen python3 gitapex_gate_plans_traceability.py \\
        --check-diff BASE_REF HEAD_REF
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Both patterns are line-anchored (`^`, MULTILINE) and case-sensitive,
# matching the one spelling every existing docs/gitapex/plans/*.md file
# actually uses (confirmed by direct inspection, not assumed): "Issue: "
# followed immediately by a full GitHub issue URL, and "Source ACM row:"
# or "Source ACM rows:" (both forms are in live use). Owner/repo are left
# generic (`[A-Za-z0-9_.-]+`) rather than hardcoded to this repository, in
# case a plans file is ever generated for a fork.
_ISSUE_URL_RE = re.compile(
    r"^[ \t]*Issue:[ \t]*https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+[ \t]*$",
    re.MULTILINE,
)
_SOURCE_ACM_ROWS_RE = re.compile(r"^[ \t]*Source ACM rows?:", re.MULTILINE)

# Non-greedy + DOTALL so a fence closes at the *next* ``` line rather than
# consuming to the end of the file if a closing fence is missing (a
# malformed file then simply keeps its last, unterminated block
# unstripped -- still graded, never silently dropped).
_FENCED_CODE_BLOCK_RE = re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$\n?", re.MULTILINE | re.DOTALL)

# label -> pattern, the single source of truth `find_missing_traceability`
# grades against. Two entries stay a plain tuple rather than a registry
# class: `gitapex_gate_skill_audit_disclosure.py`'s own docstring notes
# its process-disclosure checks only collapsed into a registry "by the
# third such check" -- below that, explicit is simpler than a shared
# abstraction paying for a scale this gate does not have.
_TRACEABILITY_CHECKS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("issue-url", _ISSUE_URL_RE),
    ("source-acm-rows", _SOURCE_ACM_ROWS_RE),
)

# Flat one level under docs/gitapex/plans/ only -- matches the existing
# corpus and `--check-diff BASE HEAD -- docs/gitapex/plans/*.md`'s own
# pathspec; a nested docs/gitapex/plans/<dir>/<f>.md is an unsupported
# shape this gate hard-fails on rather than silently skips, the same
# choice `gitapex_compute_skill_audit_flags.py`'s `_DESIGN_DOC_SHAPE_RE`
# makes for `docs/*/specs/*.md`.
_PLAN_FILE_SHAPE_RE = re.compile(r"docs/gitapex/plans/[A-Za-z0-9._-]+\.md")
_PLAN_FILE_PATHSPEC = "docs/gitapex/plans/*.md"

_EXCLUDED_STATUS_RE = re.compile(r"(D|R100)\s")


class GateError(Exception):
    """This gate's own computation could not be trusted -- always exits 1,
    never a silent pass (dimension 15)."""


def _normalize(text: str | None) -> str:
    """CRLF/CR -> LF, and `None` -> `""` so a caller need not special-case
    a file that could not be read (fails closed via `find_missing_traceability`
    returning both labels for empty content, never raising here)."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _strip_fenced_code_blocks(text: str) -> str:
    """Remove every ` ``` `-fenced block from `text` before either
    citation pattern is searched for -- see this module's own docstring
    for why."""
    return _FENCED_CODE_BLOCK_RE.sub("", text)


def find_missing_traceability(content: str | None) -> list[str]:
    """Return the subset of `_TRACEABILITY_CHECKS` labels ("issue-url",
    "source-acm-rows") that `content` carries no genuine citation for.

    Fails closed on malformed input: `None`, an empty string, or a
    whitespace-only string returns both labels, never `[]` -- a caller
    reading an empty list as "well-formed" cannot be fooled by a missing
    or unreadable file's content reaching here as `None` or `""`.
    """
    scanned = _strip_fenced_code_blocks(_normalize(content))
    return [label for label, pattern in _TRACEABILITY_CHECKS if not pattern.search(scanned)]


def _is_blank(value: str) -> bool:
    return not value.strip()


def _run_git(repo_root: Path, *args: str) -> str:
    """Run `git -C repo_root <args>` and return stdout, raising
    `GateError` on any failure -- a missing `git` executable, a non-zero
    exit, or non-UTF-8 output. `git` is resolved from PATH, not pinned to
    an absolute path, matching every other gate script in this family.
    """
    try:
        # S603/S607 waived: a fixed argv list with no shell.
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), *args],  # noqa: S607
            capture_output=True,
        )
    except OSError as error:
        raise GateError(f"git {' '.join(args)} could not be run: {error}") from error
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"git {' '.join(args)} failed: {stderr}")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GateError(f"git {' '.join(args)} produced output that is not valid UTF-8: {error}") from error


def _parse_name_status_line(line: str) -> tuple[str, str, str]:
    """Return `(status, old_path, new_path)` for one `--name-status` line,
    raising `GateError` on a shape this gate cannot trust."""
    fields = line.split("\t")
    if len(fields) < 2 or not fields[0].strip():
        raise GateError(f"unparseable --name-status line: {line!r}")
    status = fields[0].strip()
    old_path = fields[1].strip()
    if status.startswith("R"):
        if len(fields) < 3 or not fields[2].strip():
            raise GateError(f"rename line carries no destination path: {line!r}")
        return status, old_path, fields[2].strip()
    return status, old_path, old_path


def _added_or_modified(name_status_text: str) -> list[str]:
    """Drop `D` and `R100` lines -- a deleted or byte-identically-renamed
    file has no new content to check."""
    return [
        line
        for line in name_status_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip() and not _EXCLUDED_STATUS_RE.match(line)
    ]


def _diff_plan_files(repo_root: Path, base_ref: str, head_ref: str) -> list[str]:
    """`docs/gitapex/plans/*.md` paths this diff adds or modifies -- never
    a deletion-only or byte-identical-rename-only change, and never a
    file this diff does not itself touch. Three-dot (merge-base) diff, so
    a file changed on the base branch after this PR forked is never
    misattributed to it, matching every sibling diff-scoped gate in this
    repository.
    """
    text = _run_git(repo_root, "diff", "--name-status", f"{base_ref}...{head_ref}", "--", _PLAN_FILE_PATHSPEC)
    lines = _added_or_modified(text)
    paths = []
    for line in lines:
        _, _, new_path = _parse_name_status_line(line)
        if not _PLAN_FILE_SHAPE_RE.fullmatch(new_path):
            raise GateError(f"unsupported docs/gitapex/plans filename for traceability check: {new_path}")
        paths.append(new_path)
    return paths


def _git_show(repo_root: Path, rev: str, path: str) -> str:
    """`path`'s content at `rev`. `_diff_plan_files` only ever returns
    paths this same diff just added or modified, so the file must exist
    at `head_ref` -- a `GateError` here (propagated from `_run_git`) means
    the local git state cannot be trusted, not that the file is
    legitimately absent."""
    return _run_git(repo_root, "show", f"{rev}:{path}")


def check_diff(repo_root: Path, base_ref: str, head_ref: str) -> dict[str, list[str]]:
    """Return `{path: [missing labels]}` for every `docs/gitapex/plans/*.md`
    file this diff adds or modifies that is missing at least one
    traceability citation. An empty dict means every diff-touched file (if
    any) is well-formed, or the diff touches none at all -- both a pass.
    Raises `GateError` when the diff itself cannot be trusted.
    """
    blank = [name for name, value in (("BASE_REF", base_ref), ("HEAD_REF", head_ref)) if _is_blank(value)]
    if blank:
        raise GateError("blank " + " and ".join(blank) + "; refusing to compute a diff from an unresolved ref")
    failures: dict[str, list[str]] = {}
    for path in _diff_plan_files(repo_root, base_ref, head_ref):
        missing = find_missing_traceability(_git_show(repo_root, head_ref, path))
        if missing:
            failures[path] = missing
    return failures


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff every `docs/gitapex/plans/*.md` file the given diff
    adds or modifies names its source Issue URL and cites `Source ACM
    rows` at least once; else 1."""
    parser = argparse.ArgumentParser(
        description="Check that every docs/gitapex/plans/*.md file a diff adds or "
        "modifies names its source Issue URL and cites Source ACM rows "
        "(existence-only; issue #1796)."
    )
    parser.add_argument(
        "--check-diff",
        nargs=2,
        required=True,
        metavar=("BASE_REF", "HEAD_REF"),
        help="Compute which docs/gitapex/plans/*.md files this diff adds or modifies "
        "and grade only those -- never the whole corpus.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to run git in (defaults to this checkout).",
    )
    args = parser.parse_args(argv)
    base_ref, head_ref = args.check_diff

    try:
        failures = check_diff(args.repo_root, base_ref, head_ref)
    except GateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not failures:
        print(
            "PASS: every docs/gitapex/plans/*.md file this diff adds or modifies "
            "names its source Issue URL and cites Source ACM rows"
        )
        return 0

    for path in sorted(failures):
        print(f"FAIL: {path} is missing: {', '.join(failures[path])}", file=sys.stderr)
    print(
        "Add a top-level 'Issue: https://github.com/<owner>/<repo>/issues/<N>' line "
        "and at least one 'Source ACM row: ...' / 'Source ACM rows: ...' citation "
        "to each file listed above.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compute the next `plugin` product SemVer bump from conventional commits.

Issue #642 (design:
docs/superpowers/plans/2026-08-01-versioning-release-mechanism.md): a
release-PR workflow needs to know, deterministically, whether the commits
since the last release warrant a `minor` or `patch` bump to the `plugin`
product's version (`docs/versioning.md`'s product-scoped SemVer axis; see
that file's "Commit convention" section) -- and by exactly how much, never
guessed by a human and never cumulative across commits.

This module splits into a pure core (parsing, classification, version
arithmetic, manifest rewriting, notes rendering -- all unit-testable with
plain Python data, zero real git calls) and a thin git/CLI wrapper
(`discover_last_tag`, `collect_commits`, `main`) that only ever talks to a
repository through an injectable `git_runner` callable, so even the
wrapper stays swappable in tests.

Commit-scope convention (docs/versioning.md): only a commit whose header
scope is exactly `plugin` (e.g. `feat(plugin): ...`) counts toward this
product's version. A commit scoped to something else (`feat(skills): ...`,
`feat(cli): ...`, unscoped, or unparsed) never bumps `plugin`'s version,
even if its type would otherwise qualify.

Severity rule (also docs/versioning.md): `feat` or any breaking-marked
commit (`!` immediately before the header colon, or a `BREAKING CHANGE:`
footer line) is a `minor` bump; `fix`/`refactor`/`perf` is a `patch` bump
(per that doc's own text: "refactor ... is a patch at most"). Everything
else (`docs`/`chore`/`test`/`build`/`ci`, non-breaking) is a no-op.
Severity is the *max* across all commits since the last release, never
summed or multiplied -- one `feat(plugin)` and five `feat(plugin)`s both
produce exactly one minor bump.

Critical invariant: **no code path in this module ever returns, implies,
or computes a major-version bump.** `1.0.0` is reserved for a deliberate
human guarantee, per docs/versioning.md and SemVer #4 -- not something
automation may decide on a commit-count heuristic. `classify()`'s return
type has no `"major"` value, and `compute_next_version()` re-asserts this
invariant at runtime (see its loop) so a future edit that accidentally
introduces one fails loudly instead of silently shipping a major bump. Do
not relax this by adding a `"major"` branch anywhere in this file.

Manifest rewriting (`write_bumped_manifests`) is a targeted regex
substitution, deliberately not a `json.dump`/`yaml.safe_dump` round-trip:
a round-trip would reformat `plugin.json` (key order, indentation,
trailing newline) and would destroy `apm.yml`'s leading comment block
(PyYAML's `safe_dump` does not preserve comments). It asserts the version
line matches exactly once per file before writing -- zero matches or more
than one both raise `RuntimeError` (fail loud, matching
`scan_apm_manifest_drift.py`'s own style) rather than silently no-op-ing
or guessing which line to bump. Each file is written via a temp file in
the same directory followed by `os.replace` (atomic; no partially-written
manifest possible, and no stray temp file survives a successful run).

Usage::

    # Compute-only (dry run); prints the result, writes nothing.
    python3 .github/scripts/compute_release_bump.py

    # Apply the bump to plugin.json/apm.yml, write release notes, and
    # record bump=/version= for a GitHub Actions step.
    python3 .github/scripts/compute_release_bump.py --write \\
        --notes-out release-notes.md --github-output "$GITHUB_OUTPUT"

Exit codes:
    0  Success -- a bump was computed (and applied, if --write) or no
       plugin-scoped commit since the last release warranted one (both
       are a normal, successful outcome, not an error).
    1  Failure -- a manifest is malformed or missing its version field,
       a manifest's version line is missing or duplicated,
       `current_version` is not a valid X.Y.Z string, or the underlying
       `git` invocation failed.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Callable, Literal

PLUGIN_SCOPE = "plugin"

_HEADER_RE = re.compile(
    r"^(feat|fix|docs|refactor|perf|test|chore|build|ci)"
    r"(\(([a-z0-9_-]+)\))?(!)?:\s*(.+)$"
)
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING CHANGE:", re.MULTILINE)
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PLUGIN_VERSION_RE = re.compile(r'"version":\s*"\d+\.\d+\.\d+"')
# `[ \t]*`, deliberately not `\s*`: `\s` matches "\n", so `\s*` let a match
# starting at a valueless `version:` line run on into the *next* line and
# treat that line's key as the version value -- still exactly one match, so
# the "exactly one match" guard below passed and the substitution silently
# deleted the following key. Keeping the whitespace run line-local means a
# valueless `version:` yields zero matches and fails loud instead.
_APM_VERSION_RE = re.compile(r"^version:[ \t]*\S+$", re.MULTILINE)

_LAST_TAG_GLOB = "gitapex--v*"
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"

Bump = Literal["minor", "patch"]


@dataclasses.dataclass(frozen=True)
class ParsedCommit:
    """A conventional-commit header, parsed. `scope` is None when the
    header carries no `(scope)` at all (e.g. a bare `feat: ...`)."""

    commit_type: str
    scope: str | None
    breaking_marker: bool
    description: str


def parse_header(subject: str) -> ParsedCommit | None:
    """Parse a commit subject as a conventional-commit header. Returns
    None for anything that doesn't match -- merge-commit subjects ("Merge
    pull request #1 from ..."), freeform text, or a type outside the fixed
    feat/fix/docs/refactor/perf/test/chore/build/ci set."""
    match = _HEADER_RE.match(subject)
    if match is None:
        return None
    commit_type, _scope_group, scope, breaking_marker, description = match.groups()
    return ParsedCommit(
        commit_type=commit_type,
        scope=scope,
        breaking_marker=breaking_marker is not None,
        description=description,
    )


def is_breaking(subject: str, body: str) -> bool:
    """True if `subject` carries a conventional-commit `!` breaking marker
    immediately before the header colon, or `body` contains a
    `BREAKING CHANGE:` footer line. A subject that doesn't parse as a
    conventional-commit header at all can still be breaking via the body
    footer alone."""
    parsed = parse_header(subject)
    if parsed is not None and parsed.breaking_marker:
        return True
    return _BREAKING_FOOTER_RE.search(body) is not None


def classify(parsed: ParsedCommit | None, breaking: bool) -> Bump | None:
    """Classify one already-parsed commit as a `plugin` SemVer bump
    severity, or None if it doesn't count.

    Only `scope == "plugin"` counts (docs/versioning.md's commit-scope
    convention) -- a wrong scope, no scope, or an unparsed subject all
    return None regardless of type or breaking marker.

    Critical invariant: this function's return type is `Bump | None`
    where `Bump = Literal["minor", "patch"]` -- there is no `"major"`
    value anywhere in this logic, by construction. `1.0.0` is a
    deliberate human decision (docs/versioning.md), never an automated
    one. Do not add a `"major"` branch here.
    """
    if parsed is None or parsed.scope != PLUGIN_SCOPE:
        return None
    if breaking or parsed.commit_type == "feat":
        return "minor"
    if parsed.commit_type in ("fix", "refactor", "perf"):
        return "patch"
    return None


def compute_next_version(
    current_version: str, commits: list[dict]
) -> dict[str, str] | None:
    """Compute the max-of-signals bump across every commit in `commits`
    (each a {"sha", "subject", "body"} dict) and apply it once to
    `current_version`.

    Severity is the max across all commits, never cumulative: one
    `feat(plugin)` and five `feat(plugin)`s both yield exactly one minor
    bump. Returns None if no commit classifies (a genuine no-op -- nothing
    to release). Otherwise returns {"version": "<bumped X.Y.Z>", "bump":
    "minor"|"patch"}; a minor bump resets patch to 0, a patch bump leaves
    major/minor alone, and major is never incremented.
    """
    severity: Bump | None = None
    for commit in commits:
        parsed = parse_header(commit["subject"])
        breaking = is_breaking(commit["subject"], commit["body"])
        bump = classify(parsed, breaking)
        if bump is None:
            continue
        if bump not in ("minor", "patch"):
            # Defense-in-depth for the no-major-bump invariant: classify()
            # is typed to never return anything else, but a future edit
            # that violates that typing must fail loudly here rather than
            # silently falling through to a wrong severity below.
            raise AssertionError(
                f"classify() returned {bump!r} for commit "
                f"{commit.get('sha', '?')!r}; only 'minor', 'patch', or "
                "None are ever valid"
            )
        if bump == "minor":
            severity = "minor"
        elif severity != "minor":
            severity = "patch"

    if severity is None:
        return None

    match = _SEMVER_RE.match(current_version)
    if match is None:
        raise ValueError(
            f"current_version {current_version!r} is not a valid X.Y.Z SemVer string"
        )
    major, minor, patch = (int(part) for part in match.groups())
    if severity == "minor":
        return {"version": f"{major}.{minor + 1}.0", "bump": "minor"}
    return {"version": f"{major}.{minor}.{patch + 1}", "bump": "patch"}


def discover_last_tag(git_runner: Callable[[list[str]], str]) -> str | None:
    """Return the most recent `gitapex--v*` tag (by version sort), or None
    if no such tag exists yet (the pre-release bootstrap case).

    `git_runner` is a callable taking a list of git args and returning
    stdout text, so this never needs a real git repository in tests. A
    None result is not special-cased by any caller: `compute_next_version`
    handles an arbitrarily long "all of history" commit list the same way
    it handles a short one, by construction (max-of-signals still yields
    at most one bump).
    """
    output = git_runner(["tag", "-l", _LAST_TAG_GLOB, "--sort=-v:refname"])
    for line in output.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def write_bumped_manifests(
    plugin_path: pathlib.Path, apm_path: pathlib.Path, new_version: str
) -> None:
    """Bump `plugin_path`'s JSON `"version": "X.Y.Z"` line and
    `apm_path`'s top-level YAML `version: X.Y.Z` line to `new_version`, in
    place, each via a same-directory temp file + `os.replace` (atomic; no
    partially-written manifest possible).

    A targeted regex substitution, deliberately not a
    `json.dump`/`yaml.safe_dump` round-trip: a round-trip would reformat
    `plugin.json` and would destroy `apm.yml`'s leading comment block
    (PyYAML's `safe_dump` does not preserve comments). Raises
    `RuntimeError` if a file's version line doesn't appear exactly once --
    zero matches or more than one both fail loud rather than silently
    no-op-ing or guessing which line to bump. `plugin_path` is processed
    before `apm_path`; if `plugin_path` fails, `apm_path` is never read or
    touched at all.
    """
    _replace_manifest_version(
        pathlib.Path(plugin_path),
        _PLUGIN_VERSION_RE,
        f'"version": "{new_version}"',
        'JSON "version": "X.Y.Z"',
    )
    _replace_manifest_version(
        pathlib.Path(apm_path),
        _APM_VERSION_RE,
        f"version: {new_version}",
        "top-level YAML version: X.Y.Z",
    )


def _replace_manifest_version(
    manifest_path: pathlib.Path,
    pattern: re.Pattern[str],
    replacement: str,
    field_description: str,
) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"{manifest_path}: expected exactly one {field_description} "
            f"line, found {len(matches)} -- refusing to guess which one "
            "to bump"
        )
    match = matches[0]
    new_text = text[: match.start()] + replacement + text[match.end() :]
    _atomic_write(manifest_path, new_text)


def _atomic_write(path: pathlib.Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def render_notes(commits: list[dict]) -> str:
    """Render Markdown release notes grouped by classified type: `###
    Features` (feat), `### Fixes` (fix), `### Refactors` (refactor/perf)
    -- one bullet per commit as `- <subject> (<short-sha>)` (7-char short
    sha). A section is omitted entirely when it has no commits. A trailing
    line always prints, counting every other commit (wrong scope,
    unparsed, or a `docs`/`chore`/`build`/`ci`/`test` type) that didn't
    land in one of the three sections -- 0 is a valid, printed count, not
    an omitted line.

    Deliberately independent of classify()'s breaking-marker override:
    these three sections describe conventional-commit *type* (what kind
    of change it was), not SemVer severity, so a breaking-marked `docs`/
    `chore`/`build`/`ci`/`test` commit (which classify() would still score
    as a minor bump) is not force-fit into "Refactors" -- it has no
    matching section here and is counted in the trailing omitted line
    instead.
    """
    features: list[str] = []
    fixes: list[str] = []
    refactors: list[str] = []
    omitted = 0

    for commit in commits:
        parsed = parse_header(commit["subject"])
        bucket: list[str] | None = None
        if parsed is not None and parsed.scope == PLUGIN_SCOPE:
            if parsed.commit_type == "feat":
                bucket = features
            elif parsed.commit_type == "fix":
                bucket = fixes
            elif parsed.commit_type in ("refactor", "perf"):
                bucket = refactors
        if bucket is None:
            omitted += 1
            continue
        bucket.append(f"- {commit['subject']} ({commit['sha'][:7]})")

    sections: list[str] = []
    if features:
        sections.append("### Features\n" + "\n".join(features))
    if fixes:
        sections.append("### Fixes\n" + "\n".join(fixes))
    if refactors:
        sections.append("### Refactors\n" + "\n".join(refactors))
    sections.append(
        f"_{omitted} other commit(s) since the last release "
        "(docs/chore/ci/test) omitted above._"
    )
    return "\n\n".join(sections) + "\n"


def _default_git_runner(repo_root: pathlib.Path) -> Callable[[list[str]], str]:
    """Build a real `git_runner` (see discover_last_tag/collect_commits)
    bound to `repo_root`. Kept separate from the pure functions above so
    every test can inject its own stub instead."""

    def run(args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    return run


def collect_commits(
    repo_root: pathlib.Path, git_runner: Callable[[list[str]], str]
) -> list[dict]:
    """Thin git wrapper: discover the last release tag via
    `discover_last_tag`, then return every non-merge commit since it (or
    since the start of history, if no tag exists yet) as plain
    {"sha", "subject", "body"} dicts -- the shape every pure function
    above expects.

    Uses ASCII unit/record separators (0x1f/0x1e) in `git log --format`,
    the same delimiter-safety reasoning this repo's own
    `detect_touched_eval_skills.py` applies to NUL-delimited paths: a
    commit subject or body can legitimately contain almost any printable
    character, so a human-typed delimiter (space, comma, pipe) risks
    misparsing a record, while these two control bytes practically never
    appear in commit messages. `repo_root` is accepted for symmetry with
    `_default_git_runner`/discoverability even though `git_runner` already
    carries its own bound working directory; it is not otherwise used
    here.
    """
    last_tag = discover_last_tag(git_runner)
    commit_range = f"{last_tag}..HEAD" if last_tag is not None else "HEAD"
    log_format = f"%H{_FIELD_SEP}%s{_FIELD_SEP}%b{_RECORD_SEP}"
    output = git_runner(["log", commit_range, "--no-merges", f"--format={log_format}"])
    commits: list[dict] = []
    for record in output.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, body = record.split(_FIELD_SEP, 2)
        commits.append({"sha": sha, "subject": subject, "body": body})
    return commits


def _read_current_version(plugin_path: pathlib.Path) -> str:
    data = json.loads(plugin_path.read_text(encoding="utf-8"))
    if "version" not in data:
        raise KeyError(f"{plugin_path}: missing required 'version' field")
    return str(data["version"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute (and optionally apply) the next `plugin` "
        "SemVer bump from conventional commits since the last "
        "gitapex--v* tag. Never computes a major bump -- see this "
        "module's docstring."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root (default: cwd).")
    parser.add_argument(
        "--plugin-manifest",
        default=".claude-plugin/plugin.json",
        help="Path to plugin.json, relative to --repo-root (default: %(default)s).",
    )
    parser.add_argument(
        "--apm-manifest",
        default="apm.yml",
        help="Path to apm.yml, relative to --repo-root (default: %(default)s).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the computed bump to the manifests. Omitted: "
        "compute-only (dry run) -- nothing on disk changes.",
    )
    parser.add_argument(
        "--notes-out", default=None, help="Write rendered Markdown release notes to this path."
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="Append bump=none|minor|patch and version=X.Y.Z KEY=value "
        "lines to this GITHUB_OUTPUT-format file.",
    )
    args = parser.parse_args(argv)

    repo_root = pathlib.Path(args.repo_root).resolve()
    plugin_path = repo_root / args.plugin_manifest
    apm_path = repo_root / args.apm_manifest

    try:
        current_version = _read_current_version(plugin_path)
        git_runner = _default_git_runner(repo_root)
        commits = collect_commits(repo_root, git_runner)
        result = compute_next_version(current_version, commits)
        notes = render_notes(commits)

        if args.notes_out is not None:
            pathlib.Path(args.notes_out).write_text(notes, encoding="utf-8")

        if result is not None and args.write:
            write_bumped_manifests(plugin_path, apm_path, result["version"])

        if args.github_output is not None:
            bump = result["bump"] if result is not None else "none"
            version = result["version"] if result is not None else current_version
            with open(args.github_output, "a", encoding="utf-8") as handle:
                handle.write(f"bump={bump}\n")
                handle.write(f"version={version}\n")
    except (
        KeyError,
        ValueError,
        RuntimeError,
        subprocess.CalledProcessError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if result is None:
        print("No plugin-scoped commit since the last release; nothing to bump.")
    else:
        print(f"Computed {result['bump']} bump: {current_version} -> {result['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

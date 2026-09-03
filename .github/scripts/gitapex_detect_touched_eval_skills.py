#!/usr/bin/env python3
"""Compute the sorted, deduped set of skill names under `evals/<skill>/...`
touched by a list of changed file paths.

Issue #582: `skill-eval-gate.yml` needs to know which skills' `evals/<skill>/`
suites to run for a given diff, without re-deriving this extraction logic
inline in bash. This repo's existing convention keeps that kind of
extraction in a small, unit-tested Python script -- e.g.
`gitapex_skill_description_diff.py`, `gitapex_skill_security_relevance.py` -- and leaves
the actual `git diff` invocation in the calling workflow step, which
merely feeds this script the resulting path list.

A path counts as touching skill `<skill>` iff it starts with `evals/` and
its second path segment (`<skill>`) is followed by at least one further
segment -- i.e. it is a file *inside* `evals/<skill>/`, not `evals/<skill>`
itself with no further segment, and not a bare top-level `evals/` file
(e.g. `evals/README.md`, which has no skill directory beneath it at all).

`evals/scripts/` is excluded outright: it is shared eval-runner
infrastructure (see `evals/scripts/gitapex_set_config_model.py`), not any skill's
own suite -- matching `skill-audit-gate.yml`'s own existing
`evals/scripts/*.py` exclusion for the same reason. This exclusion is
keyed on the exact second path segment being the literal string
`"scripts"`, so it applies regardless of what appears deeper in the path
(e.g. `evals/scripts/subdir/looks-like-a-skill/eval.yaml` is still
excluded -- what looks skill-shaped further down does not matter, only the
top-level segment right after `evals/` does).

Every extracted skill-name segment that is not excluded is validated
against `^[A-Za-z0-9_-]+$` before being added to the result -- raising
`ValueError` (fail loud) on a name outside that class rather than silently
dropping it, the same convention `skill-audit-gate.yml`'s own inline bash
already applies to a skill name pulled from a diff before writing it to
`$GITHUB_OUTPUT` (see `gitapex_gate_skill_audit_disclosure.py`'s docstring for the
rationale: an attacker- or mistake-controlled directory name is untrusted
input the moment it reaches a shell-interpolated or comma-joined sink, and
a validated raise beats a silent drop for the same audit-trail reason
`gitapex_gate_skill_rename_lifecycle.py` and `gitapex_gate_evals_scripts_coverage.py`
already established for this repo's other deterministic gates). A segment
containing a space (e.g. `evals/foo bar/tasks/x.yaml`) is caught the same
way. A path containing a `..` segment (e.g. `evals/../etc/passwd`) is
instead caught earlier, by a dedicated check described below, not by this
regex -- see the `./`-stripping paragraph further down for why a regex-only
check would miss a leading `..`.
Validation uses `re.fullmatch`, not `re.match` -- Python's `$` anchor
(without `re.MULTILINE`) matches just before a trailing newline as well as
at the true end of string, so `re.match(r"^[A-Za-z0-9_-]+$", "foo\n")`
would otherwise incorrectly succeed and let a skill-name segment carrying
an embedded/trailing newline through, corrupting the single-line
`$GITHUB_OUTPUT` value this script's output feeds into. `re.fullmatch`
requires the match to span the entire segment, which a trailing `\n`
prevents.

A leading `./` (repeated, e.g. `././evals/foo/eval.yaml`) is stripped
before the `evals/`-prefix check runs, so it does not silently defeat
detection the way an un-stripped leading segment otherwise would (the
first segment would be `"."`, not `"evals"`, and the path would be
dropped with no error at all -- worse than the raised-error cases above,
since nothing would flag it). `git diff --name-only` itself never emits a
`./`-prefixed path, but this script's own CLI/stdin usage (see Usage
below) accepts arbitrary caller-supplied paths, and `./`-prefixed output
is a common shape from other tools (e.g. `find .`) a caller might pipe in
instead. Only a literal leading `.` segment is stripped this way -- a `..`
segment is never stripped, and is instead rejected explicitly: any path
whose segments (after the leading-`.` strip above) contain a literal `".."`
element anywhere -- leading, in the skill-name position, or elsewhere --
raises `ValueError` before the `evals/`-prefix check runs, so a leading
`..` cannot fall through that check silently the way an un-stripped
leading `.` segment otherwise would. This is a dedicated check, not
reliance on the skill-name regex incidentally catching a `..` that happens
to land in the skill-name position -- that incidental mechanism does not
cover a leading `..` (segment 0, checked before the regex is ever reached)
or a `..` elsewhere in the path (e.g. `evals/foo/../secret.yaml`, whose
skill-name segment is the valid `"foo"`). Collapsing `..` instead (e.g. via
`posixpath.normpath`) is deliberately not done: that would silently resolve
`evals/../etc/passwd` down to `etc/passwd` and defeat the path-traversal
check instead of preserving it.

A path whose segments (after the same leading-`.` strip) end in a single
empty segment produced by a literal trailing `/` (e.g.
`"evals/foo/".split("/") == ["evals", "foo", ""]`) has that one trailing
empty segment stripped before the length check below -- otherwise it would
satisfy `len(segments) >= 3` by accident and miscount a bare directory path
with no file inside it as touching that skill, contradicting this script's
own "not `evals/<skill>` itself with no further segment" invariant above.
Only the single trailing element is stripped this way; an empty segment
anywhere else in the path (e.g. a literal `evals//foo/x.yaml`) is left
alone and still fails the skill-name regex check the normal way.

A bare leading `/` (an absolute-looking path, e.g. `/evals/foo/eval.yaml`)
is a known, deliberately undefended input shape: neither `git diff
--name-only` nor this workflow's `workflow_dispatch` fallback ever
produces one, so it is left out of scope rather than adding unrequested
normalization surface.

Every path this script receives in its default (newline) mode is also
expected to already be free of git's own `--name-only` C-style quoting
(the double-quote-and-octal-escape wrapping git applies to a path
containing a non-ASCII byte, a double quote, a backslash, or a control
character, unless the diff is taken with `-z`). This script does not
un-quote such a line itself -- the calling workflow step is responsible
for invoking `git diff --name-only -z` (NUL-delimited, which disables that
quoting) and passing the result through in one of two ways: either into
this script's `--nul`/`-0` mode (see below), which reads the raw
NUL-delimited bytes directly, or -- only once safely converted to one
path per line with no embedded NUL remaining -- into this script's
default newline mode. NUL must never pass through a plain bash scalar
variable (`x=$(...)`) on its way there: bash silently drops embedded NUL
bytes on capture (confirmed empirically: `x=$(printf 'a\\0b')` yields
`x="ab"`), which would glue two touched paths together. See
`skill-eval-gate.yml`'s "Determine touched skills" step for the actual
invocation and its rationale.

Output matches `skill-audit-gate.yml`'s own comma-join convention for
`$GITHUB_OUTPUT` values (e.g. its `security-relevant-skills` output): a
single sorted, deduped, comma-joined line, empty when no skill was
touched -- so the calling workflow step can read this script's stdout
directly into a `GITHUB_OUTPUT` variable.

Usage::

    git diff --name-only -z "$BASE_SHA...$HEAD_SHA" | \\
        python3 .github/scripts/gitapex_detect_touched_eval_skills.py --nul

    python3 .github/scripts/gitapex_detect_touched_eval_skills.py \\
        evals/foo/tasks/x.yaml evals/bar/eval.yaml

A bare pipe in the first form masks `git diff`'s own exit status in a
non-`pipefail` shell (issue #1531): add `set -o pipefail` first, or check
`git diff`'s own exit code separately, if the caller must detect an
upstream failure rather than silently classifying whatever partial path
list reached stdin.

`--nul`/`-0` (matching the `-0` convention of `xargs -0`/`grep -z`) reads
raw NUL-delimited bytes from `sys.stdin.buffer`, decoding each piece with
`os.fsdecode` (POSIX-safe, round-trips non-UTF-8-but-valid path bytes via
surrogateescape, unlike a plain `.decode("utf-8")` which would raise on
one) rather than converting NUL to newline in bash first: a real path
containing a literal, unescaped newline byte (legal on a POSIX filesystem,
not escaped by `-z`) would otherwise become indistinguishable from the
NUL-turned-newline record separator once such a conversion ran, silently
splitting one touched path into two bogus fragments -- reintroducing,
through the `-z` fix itself, the same class of false negative it was
meant to prevent. The default (no `--nul`) mode is unchanged for every
existing caller: one path per line from stdin, split on a literal `"\\n"`
only (`str.split("\\n")`, not `str.splitlines()`, which also splits on
`\\r`, `\\v`, `\\f`, `\\x1c`-`\\x1e`, `\\x85`, U+2028, and U+2029 -- a real
path containing one of those raw bytes must not be mis-split either).

`skill-eval-gate.yml`'s actual "Determine touched skills" step composes
`--nul` with `git diff --name-status -z` (not `--name-only`), so a
deleted or purely-renamed path can be filtered out in that workflow step
before the surviving paths ever reach this script -- see that step's own
comment for the full invocation and its D/R100-exclusion, rename-aware
field walk. This script's own job stays a flat path list in, skill names
out; the status-code filtering is the calling workflow's concern, the
same "git diff stays in the workflow step" split as the rest of this
docstring describes.

Positional args and stdin are both supported (matching this repo's mixed
conventions across existing `.github/scripts/*.py` CLIs): when one or more
positional path arguments are given, those are used as the path list and
standard input is not read at all (regardless of `--nul`); when none are
given, stdin is read in whichever mode (`--nul` or the newline-delimited
default) was selected.

Exit codes:
    0  Success; touched skill names (possibly none) printed to stdout.
    1  A touched path's skill-name segment fails the ^[A-Za-z0-9_-]+$ check.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_EXCLUDED_SKILL_SEGMENT = "scripts"
_EVALS_SEGMENT = "evals"


def parse_paths(text: str) -> list[str]:
    """Parse one path per line, blank lines and surrounding whitespace ignored.

    Splits on a literal ``"\\n"`` only -- not ``str.splitlines()``, which
    additionally splits on ``\\r``, ``\\v``, ``\\f``, ``\\x1c``-``\\x1e``,
    ``\\x85``, U+2028, and U+2029, mis-splitting a real path that happens to
    contain one of those raw bytes.
    """
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_paths_nul(data: bytes) -> list[str]:
    """Parse NUL-delimited paths from raw stdin bytes (``--nul``/``-0`` mode).

    Splits on a literal NUL byte, drops a single trailing empty element
    produced by a trailing NUL (the shape both `git diff ... -z` and a
    `printf '%s\\0'` producer emit), and decodes each remaining piece with
    `os.fsdecode` -- the standard POSIX-safe way to round-trip arbitrary
    path bytes through `str` via surrogateescape, tolerating a legitimate
    non-UTF-8-but-valid filename that `.decode("utf-8")` would raise on.
    """
    pieces = data.split(b"\0")
    if pieces and pieces[-1] == b"":
        pieces = pieces[:-1]
    return [os.fsdecode(piece) for piece in pieces if piece]


def touched_skills(paths: list[str]) -> list[str]:
    """Return the sorted, deduped list of skill names under `evals/<skill>/...`
    touched by `paths`.

    Raises ValueError if any touched path's skill-name segment does not
    match ``^[A-Za-z0-9_-]+$`` -- fail loud rather than silently drop it.
    """
    skills: set[str] = set()
    for path in paths:
        segments = path.split("/")
        # Leading "./" strip: see module docstring ("A leading `./`...")
        # for the full rationale. Deliberately narrow: only a literal
        # leading "." is stripped here, never "..".
        while len(segments) > 1 and segments[0] == ".":
            segments = segments[1:]
        # Any ".." segment anywhere -- leading, skill-name position, or
        # elsewhere -- is rejected explicitly rather than left to be
        # caught incidentally by the skill-name regex below, which does
        # not cover a leading ".." or one outside the skill-name segment
        # (see module docstring).
        if ".." in segments:
            raise ValueError(
                f"path {path!r} contains a '..' path segment, which is "
                "rejected as a path-traversal attempt rather than "
                "silently skipped or resolved"
            )
        # A single trailing empty segment from a literal trailing "/" is
        # stripped before the length check below (see module docstring's
        # "ends in a single empty segment" paragraph) -- otherwise a bare
        # directory path with no file inside it would be miscounted as
        # touching that skill.
        if len(segments) > 1 and segments[-1] == "":
            segments = segments[:-1]
        # Must start with "evals/" and have at least one segment beyond
        # the skill-name segment itself: ["evals", "<skill>", ...at least
        # one more...]. A bare "evals/<skill>" (length 2) or a top-level
        # "evals/<file>" (also length 2, e.g. "evals/README.md") are both
        # excluded here.
        if len(segments) < 3 or segments[0] != _EVALS_SEGMENT:
            continue
        skill = segments[1]
        if skill == _EXCLUDED_SKILL_SEGMENT:
            continue
        if not _SKILL_NAME_RE.fullmatch(skill):
            raise ValueError(f"path {path!r} has a skill-name segment {skill!r} that does not match ^[A-Za-z0-9_-]+$")
        skills.add(skill)
    return sorted(skills)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the sorted, comma-joined set of evals/<skill>/ "
        "names touched by a list of changed file paths."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Changed file paths. When omitted, reads paths from standard "
        "input instead (newline-delimited by default, or NUL-delimited "
        "with --nul).",
    )
    parser.add_argument(
        "--nul",
        "-0",
        action="store_true",
        help="Read NUL-delimited paths from raw standard input bytes "
        "instead of one newline-delimited path per line (the default). "
        "Matches the -0 convention of xargs -0/grep -z. Use when a path "
        "may contain a raw special byte (e.g. an embedded literal "
        "newline) that newline-delimited parsing cannot distinguish from "
        "the record separator itself.",
    )
    args = parser.parse_args(argv)

    if args.paths:
        paths = args.paths
    elif args.nul:
        paths = parse_paths_nul(sys.stdin.buffer.read())
    else:
        paths = parse_paths(sys.stdin.read())

    try:
        skills = touched_skills(paths)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(",".join(skills))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

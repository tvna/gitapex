#!/usr/bin/env python3
"""Compute the sorted, deduped set of skill names under `evals/<skill>/...`
touched by a list of changed file paths.

Issue #582: `waza-eval-gate.yml` needs to know which skills' `evals/<skill>/`
suites to run for a given diff, without re-deriving this extraction logic
inline in bash. This repo's existing convention keeps that kind of
extraction in a small, unit-tested Python script -- e.g.
`skill_description_diff.py`, `skill_security_relevance.py` -- and leaves
the actual `git diff` invocation in the calling workflow step, which
merely feeds this script the resulting path list.

A path counts as touching skill `<skill>` iff it starts with `evals/` and
its second path segment (`<skill>`) is followed by at least one further
segment -- i.e. it is a file *inside* `evals/<skill>/`, not `evals/<skill>`
itself with no further segment, and not a bare top-level `evals/` file
(e.g. `evals/README.md`, which has no skill directory beneath it at all).

`evals/scripts/` is excluded outright: it is shared eval-runner
infrastructure (see `evals/scripts/set_config_model.py`), not any skill's
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
`$GITHUB_OUTPUT` (see `gate_skill_audit_disclosure.py`'s docstring for the
rationale: an attacker- or mistake-controlled directory name is untrusted
input the moment it reaches a shell-interpolated or comma-joined sink, and
a validated raise beats a silent drop for the same audit-trail reason
`gate_skill_rename_lifecycle.py` and `gate_evals_scripts_coverage.py`
already established for this repo's other deterministic gates). A path
containing a `..` segment (e.g. `evals/../etc/passwd`) is caught by this
same class check, since `.` is not in `[A-Za-z0-9_-]`; a segment containing
a space (e.g. `evals/foo bar/tasks/x.yaml`) is caught the same way.
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
segment (leading or otherwise) is deliberately left alone and continues to
raise via the class check above, since collapsing `..` (e.g. via
`posixpath.normpath`) would silently resolve `evals/../etc/passwd` down to
`etc/passwd` and defeat the path-traversal check instead of preserving it.

A bare leading `/` (an absolute-looking path, e.g. `/evals/foo/eval.yaml`)
is a known, deliberately undefended input shape: neither `git diff
--name-only` nor this workflow's `workflow_dispatch` fallback ever
produces one, so it is left out of scope rather than adding unrequested
normalization surface.

Every path this script receives is also expected to already be free of
git's own `--name-only` C-style quoting (the double-quote-and-octal-escape
wrapping git applies to a path containing a non-ASCII byte, a double
quote, a backslash, or a control character, unless the diff is taken with
`-z`). This script does not un-quote such a line itself -- the calling
workflow step is responsible for invoking `git diff --name-only -z`
(NUL-delimited, which disables that quoting) and converting NUL to
newline *before* capturing the result into a shell variable, not after,
since a bash `$(...)` capture silently drops embedded NUL bytes and would
otherwise glue two touched paths together. See `waza-eval-gate.yml`'s
"Determine touched skills" step for the fixed invocation and its
rationale.

Output matches `skill-audit-gate.yml`'s own comma-join convention for
`$GITHUB_OUTPUT` values (e.g. its `security-relevant-skills` output): a
single sorted, deduped, comma-joined line, empty when no skill was
touched -- so the calling workflow step can read this script's stdout
directly into a `GITHUB_OUTPUT` variable.

Usage::

    git diff --name-only -z "$BASE_SHA...$HEAD_SHA" | tr '\0' '\n' | \\
        python3 .github/scripts/detect_touched_eval_skills.py

    python3 .github/scripts/detect_touched_eval_skills.py \\
        evals/foo/tasks/x.yaml evals/bar/eval.yaml

The `-z | tr '\0' '\n'` above is required, not a style choice: a plain
`git diff --name-only` (no `-z`) C-quotes any path containing a non-ASCII
byte, a double quote, a backslash, or a control character, and the quoted
line then fails this script's `evals/`-prefix check (see above) -- silently
dropping a real touched skill instead of reporting it.

Positional args and stdin are both supported (matching this repo's mixed
conventions across existing `.github/scripts/*.py` CLIs): when one or more
positional path arguments are given, those are used as the path list and
standard input is not read at all; when none are given, one path per line
is read from standard input.

Exit codes:
    0  Success; touched skill names (possibly none) printed to stdout.
    1  A touched path's skill-name segment fails the ^[A-Za-z0-9_-]+$ check.
"""

from __future__ import annotations

import argparse
import re
import sys

_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_EXCLUDED_SKILL_SEGMENT = "scripts"
_EVALS_SEGMENT = "evals"


def parse_paths(text: str) -> list[str]:
    """Parse one path per line, blank lines and surrounding whitespace ignored."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def touched_skills(paths: list[str]) -> list[str]:
    """Return the sorted, deduped list of skill names under `evals/<skill>/...`
    touched by `paths`.

    Raises ValueError if any touched path's skill-name segment does not
    match ``^[A-Za-z0-9_-]+$`` -- fail loud rather than silently drop it.
    """
    skills: set[str] = set()
    for path in paths:
        segments = path.split("/")
        # Strip a leading "./" (repeated -- "././evals/foo/x" too) before
        # the "evals/" check below: an un-stripped leading "." segment
        # would otherwise make segments[0] != "evals" and silently drop an
        # otherwise-valid touched path with no error at all. Deliberately
        # narrow: only a literal leading "." is stripped, never "..",  so
        # this does not weaken the path-traversal class check below (see
        # module docstring for why a general normpath-style collapse would).
        while len(segments) > 1 and segments[0] == ".":
            segments = segments[1:]
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
            raise ValueError(
                f"path {path!r} has a skill-name segment {skill!r} that does "
                "not match ^[A-Za-z0-9_-]+$"
            )
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
        help="Changed file paths. When omitted, reads one path per line "
        "from standard input.",
    )
    args = parser.parse_args(argv)

    paths = args.paths if args.paths else parse_paths(sys.stdin.read())

    try:
        skills = touched_skills(paths)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(",".join(skills))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

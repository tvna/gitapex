#!/usr/bin/env python3
"""Flag a changed fixture-assertion whose split.md disclosure omits it.

Issue #218 (Repair 1) / #1399: the "Iteration: issue #200" entry in
evals/evaluating-skill-quality/split.md named three fixed fixture-assertion
bugs in its own gate-record disclosure paragraph but omitted a fourth --
edge.yaml's "never delete production data" assertion was also loosened
during that same gate run, for the identical reason, but never listed. The
fix itself was correct; the omission from the disclosure was not, and
nothing caught it mechanically -- an external adversarial-verification
pass found it by hand.

This script is the deterministic backstop for that manual step: given a
commit range, it finds every ``evals/evaluating-skill-quality/tasks/*.yaml``
fixture whose ``output_contains``/``output_not_contains`` assertions were
touched, and fails if that fixture is not cited in the same range's own
*added* lines to split.md with the possessive form its established
disclosure-prose convention already uses -- backtick-quoted, with its
``.yaml`` extension, followed by ``'s`` (e.g. `` `edge.yaml`'s `` -- the
same ``NAME`'s`` possessive-citation shape
``skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py``'s
own ``PORTABLE_SKILL_FACT_CLAIM_RE`` already recognizes for a sibling-skill
citation, applied here to a fixture-name citation instead).

Deliberately narrower than "the fixture's bare name appears anywhere in
split.md's diff", a first design this module was validated against the
real historical range before shipping: every fixture actually run in a
gate iteration is named at least once in that iteration's own scoring
table (`` | `edge.yaml` | 1.000000 | ... | ``) *regardless* of whether its
assertions changed, so a bare-mention check is satisfied by routine
scoring-table bookkeeping and never actually fires -- confirmed live: run
against PR #216's own real, historically undisclosed commit
(`4b9edfa39e20bc1b8a16651d1fc6e7db778c8909`), a bare-mention design
reported clean when the omission it exists to catch was live and
unfixed. The possessive form is what split.md's disclosure prose actually
uses to make a fixture-specific claim ("`edge.yaml`'s `\"never delete
production data\"` assertion was also loosened...", the real corrected
text, `37284a64dd4fad9de60a578b53b01ba52a031fdb`) and a routine table row
never produces; re-run against the same real range with this narrower
form, it correctly reports the omission (see
tests/test_gitapex_check_split_disclosure.py's own real-history
regression test).

Otherwise still deliberately coarse, matching the issue's own stated
scope: this needs to understand only that every changed fixture is
*named* as a specific claim somewhere in the same range's split.md
narrative, never *why* an assertion changed or whether the disclosure's
prose is any good -- that judgment is what scorer-gated-skill-edits' own
recommended adversarial-verification pass (SKILL.md step 8) is for. A
fixture is "touched" here whenever its own diff hunk contains the literal
text ``output_contains``/``output_not_contains`` at all (assertion-list
items sit only a line or two below that key in every fixture this
repository ships, well within git's default 3-line hunk context) -- a
coarse, cheap proxy for "this fixture's assertions changed", not a
YAML-aware diff. A deleted fixture file is out of scope (see Residual
risk in issue #1399's own Acceptance Criteria Map): this repository's
split.md convention discloses an *edit*, and no historical incident this
script is modeled on involved a deletion.

Run standalone (exit 1 on an undisclosed fixture) or via the pytest gate
in tests/test_gitapex_check_split_disclosure.py.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

TASKS_GLOB_PREFIX = "evals/evaluating-skill-quality/tasks/"
SPLIT_MD_PATH = "evals/evaluating-skill-quality/split.md"
_ASSERTION_KEY_RE = re.compile(r"output_(?:not_)?contains\b")


def _run_git(args: list[str], root: pathlib.Path) -> str:
    """Run a git subcommand in `root`, returning raw (unstripped) stdout.
    Raises RuntimeError (not a bare CalledProcessError/OSError) on
    failure, so a caller only ever needs to catch one exception type.
    Unstripped, unlike a plain version-lookup helper: a diff's own leading/
    trailing blank context lines are part of what this script's callers
    scan, not incidental whitespace to discard.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise RuntimeError(f"`git {' '.join(args)}` failed in {root}: {exc}") from exc
    return result.stdout


def changed_task_files(base: str, head: str, root: pathlib.Path) -> list[str]:
    """Return every ``evals/evaluating-skill-quality/tasks/*.yaml`` path
    added or modified between `base` and `head` -- a deleted file (status
    ``D``) is excluded, per this module's own documented scope limit."""
    raw = _run_git(
        ["diff", "--name-status", "--no-renames", f"{base}..{head}", "--", f"{TASKS_GLOB_PREFIX}*.yaml"],
        root,
    )
    paths = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        if status.startswith("D"):
            continue
        paths.append(path)
    return paths


def touched_fixtures(base: str, head: str, root: pathlib.Path, task_files: list[str]) -> list[str]:
    """Return the basename (e.g. ``edge.yaml``) of every fixture in
    `task_files` whose own diff hunk contains an
    ``output_contains``/``output_not_contains`` mention -- see the module
    docstring for why this is a deliberately coarse proxy, not a
    YAML-aware diff."""
    touched = []
    for path in task_files:
        diff_text = _run_git(["diff", f"{base}..{head}", "--", path], root)
        if _ASSERTION_KEY_RE.search(diff_text):
            touched.append(pathlib.PurePosixPath(path).name)
    return touched


def split_md_added_text(base: str, head: str, root: pathlib.Path) -> str:
    """Return every line *added* to split.md between `base` and `head`,
    joined with spaces -- only additions count as new disclosure
    narrative; an unrelated removed line must not rescue a fixture that
    was never actually named in what the range added. Joined with a
    space, not a newline: this repository's own Markdown source is
    hard-wrapped at roughly 80 columns, so a real disclosure sentence can
    have an added line boundary anywhere a rendered reader would see
    ordinary whitespace."""
    diff_text = _run_git(["diff", f"{base}..{head}", "--", SPLIT_MD_PATH], root)
    added_lines = [line[1:] for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++")]
    return " ".join(added_lines)


def _fixture_citation_re(fixture_name: str) -> re.Pattern[str]:
    """The possessive-citation shape split.md's own disclosure prose uses
    to make a fixture-specific claim: a backtick-quoted fixture filename
    followed by ``'s`` (or a bare trailing apostrophe, for the unlikely
    case of a filename already ending in "s") -- the same shape
    ``gitapex_check_skill_shape.py``'s own ``PORTABLE_SKILL_FACT_CLAIM_RE``
    recognizes for a sibling-skill citation, applied here to a fixture
    filename. Deliberately narrower than a bare-name mention -- see the
    module docstring for why a bare mention is satisfied by every gate
    run's own routine scoring table regardless of whether that fixture's
    assertions changed, and does not actually reproduce the real
    historical incident this check exists to catch."""
    return re.compile(r"`" + re.escape(fixture_name) + r"`'s?(?![A-Za-z0-9])")


def undisclosed_fixtures(base: str, head: str, root: pathlib.Path | None = None) -> list[str]:
    """Return every touched fixture's basename with no possessive citation
    (see `_fixture_citation_re`) in split.md's own added lines for the
    same range, sorted for stable output."""
    repo_root = root if root is not None else pathlib.Path()
    task_files = changed_task_files(base, head, repo_root)
    if not task_files:
        return []
    fixtures = touched_fixtures(base, head, repo_root, task_files)
    if not fixtures:
        return []
    added_text = split_md_added_text(base, head, repo_root)
    return sorted({name for name in fixtures if not _fixture_citation_re(name).search(added_text)})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail if a commit range touches a evals/evaluating-skill-quality/tasks/*.yaml "
            "fixture's output_contains/output_not_contains assertions without naming that "
            "fixture anywhere in the same range's added lines to split.md."
        )
    )
    parser.add_argument("--base", default="HEAD^", help="Base ref (default: HEAD^, i.e. the single latest commit).")
    parser.add_argument("--head", default="HEAD", help="Head ref (default: HEAD).")
    parser.add_argument("--repo-root", default=".", help="Repository root to run git in (default: current directory).")
    args = parser.parse_args(argv)

    try:
        missing = undisclosed_fixtures(args.base, args.head, pathlib.Path(args.repo_root))
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not missing:
        print(f"PASS: every touched fixture (base {args.base}, head {args.head}) is named in split.md's own diff")
        return 0

    print(
        f"FAIL: {len(missing)} fixture(s) with a changed output_contains/output_not_contains "
        f"assertion (base {args.base}, head {args.head}) are not named anywhere in split.md's own "
        "added lines for this range: " + ", ".join(missing),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compute ruleset-verify.yml's scan-scope outputs for one run.

Issue #1013 (task 13). Ported unchanged from the ~37 lines of inline bash
this replaces -- see that workflow's own comments (`Resolve scan scope and
source of truth` step) for the full original rationale, restated here only
where this module's own shape needs it. This is the local-reproducibility/
pytest-coverage precedent `gitapex_compute_skill_audit_flags.py` already
established (issue #874), applied to `ruleset-verify.yml`'s own
scope-resolution step: previously that step had no local invocation and no
test coverage at all, only the bash embedded in the workflow file itself.

Two scopes, selected by `--event-name`:

* Non-`pull_request` (`schedule` / `workflow_dispatch`) -> `scope=full`
  against `main`'s own committed `.github/rulesets/main.json`. Broader and
  bidirectional, so a change made directly in the Settings UI surfaces
  within a day.
* `pull_request` -> `scope=required-checks` against the base ref's own
  committed ruleset, materialized via `git show <base-sha>:<path>` into
  `--runner-temp`. A full second checkout is not needed: `fetch-depth: 0`
  already makes the base commit locally known, the same precondition the
  original bash step depended on.

Fails loudly (`RulesetVerifyScopeError`, exit 1 via `main`) when the base
commit is not locally present at all -- distinct from "the base ref
carries no ruleset file yet" (`applicable=false`, not an error).
Swallowing every git failure as the latter would read a missing base
commit -- routine after a force-push to the base branch -- as "nothing to
check" and pass the gate green; only a readable base commit that
genuinely lacks the file is a skip.

Output contract: `key=value` lines on stdout only, suitable for appending
directly to `$GITHUB_OUTPUT` -- exactly the two shapes the original bash
already emitted (`applicable=true` plus `scope`/`sot`, or `applicable=false`
alone), no new keys invented. Every diagnostic, including the informational
"comparing in full" notice the original bash printed before its own
`$GITHUB_OUTPUT` block, goes to stderr instead, so a caller redirecting
stdout into `$GITHUB_OUTPUT` never captures anything but the intended keys.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

MAIN_RULESET_PATH = ".github/rulesets/main.json"


class RulesetVerifyScopeError(Exception):
    """The scan scope could not be resolved at all -- a hard stop, not a skip."""


def _git(args: list[str], repo_root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    # S603/S607 waived: a fixed argv list with no shell, `git` intentionally
    # resolved from PATH -- same convention as this repo's other git-shelling
    # scripts (pinning an absolute path would break the runner/devShell/
    # contributor-machine environments this has to run in equally).
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit_exists(repo_root: pathlib.Path, commit_ish: str) -> bool:
    return _git(["cat-file", "-e", f"{commit_ish}^{{commit}}"], repo_root).returncode == 0


def _path_exists_at_commit(repo_root: pathlib.Path, commit_ish: str, path: str) -> bool:
    # `cat-file -e` alone returns 0 for a tree (directory) or a symlink at
    # this path just as it does for a blob, and a downstream `git show`
    # on either materializes something that is not the file's own content
    # (a directory listing, or the symlink target string) -- see issue #1024.
    # Only a blob is a genuinely readable ruleset file.
    return _git(["cat-file", "-t", f"{commit_ish}:{path}"], repo_root).stdout.strip() == "blob"


def _show_at_commit(repo_root: pathlib.Path, commit_ish: str, path: str) -> str:
    result = _git(["show", f"{commit_ish}:{path}"], repo_root)
    if result.returncode != 0:
        raise RulesetVerifyScopeError(f"git show {commit_ish}:{path} failed: {result.stderr.strip()}")
    return result.stdout


def compute_scope(
    event_name: str,
    base_sha: str,
    repo_root: pathlib.Path,
    runner_temp: pathlib.Path,
    step_summary_file: pathlib.Path | None,
) -> dict[str, str]:
    """The `key -> value` output pairs for one run, given the resolved
    inputs. Raises `RulesetVerifyScopeError` when the scope cannot be
    resolved at all (see module docstring)."""
    if event_name != "pull_request":
        print(
            "Comparing the live ruleset against main's committed source of truth, in full.",
            file=sys.stderr,
        )
        return {"applicable": "true", "scope": "full", "sot": MAIN_RULESET_PATH}

    if not base_sha:
        raise RulesetVerifyScopeError("--base-sha is required (and must be non-empty) for a pull_request event")

    if not _commit_exists(repo_root, base_sha):
        raise RulesetVerifyScopeError(
            f"base commit {base_sha} is not present; cannot establish what the base ref requires."
        )

    if not _path_exists_at_commit(repo_root, base_sha, MAIN_RULESET_PATH):
        if step_summary_file is not None:
            with step_summary_file.open("a", encoding="utf-8") as handle:
                handle.write(f"The base ref carries no {MAIN_RULESET_PATH}; this pull request introduces it.\n")
        return {"applicable": "false"}

    sot_text = _show_at_commit(repo_root, base_sha, MAIN_RULESET_PATH)
    sot_file = runner_temp / "base_main_ruleset.json"
    sot_file.write_text(sot_text, encoding="utf-8")
    return {"applicable": "true", "scope": "required-checks", "sot": str(sot_file)}


def _render(outputs: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in outputs.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute ruleset-verify.yml's scan-scope outputs. Prints "
        "`key=value` lines suitable for appending to $GITHUB_OUTPUT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--event-name", required=True, help="github.event_name for this run.")
    parser.add_argument(
        "--base-sha",
        default="",
        help="github.event.pull_request.base.sha -- empty string on a non-pull_request event, "
        "matching that GitHub Actions expression's own empty-string behavior on any other trigger.",
    )
    parser.add_argument(
        "--repo-root", type=pathlib.Path, default=pathlib.Path(), help="Repository root (defaults to cwd)."
    )
    parser.add_argument(
        "--runner-temp",
        type=pathlib.Path,
        default=None,
        help="Scratch directory to materialize the base ref's ruleset into "
        "(defaults to $RUNNER_TEMP, then cwd if that is unset too).",
    )
    parser.add_argument(
        "--step-summary-file",
        type=pathlib.Path,
        default=None,
        help="Append the 'no ruleset yet' notice here when applicable=false "
        "(defaults to $GITHUB_STEP_SUMMARY; omit both to skip writing it).",
    )
    args = parser.parse_args(argv)

    runner_temp = args.runner_temp
    if runner_temp is None:
        runner_temp = pathlib.Path(os.environ.get("RUNNER_TEMP", "."))
    step_summary_file = args.step_summary_file
    if step_summary_file is None and os.environ.get("GITHUB_STEP_SUMMARY"):
        step_summary_file = pathlib.Path(os.environ["GITHUB_STEP_SUMMARY"])

    try:
        outputs = compute_scope(args.event_name, args.base_sha, args.repo_root, runner_temp, step_summary_file)
    except RulesetVerifyScopeError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    print(_render(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

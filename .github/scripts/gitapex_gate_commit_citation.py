#!/usr/bin/env python3
"""Two-layer enforcement of CLAUDE.md section 3's issue-citation rule for
commits (issue #1212): a fast local `commit-msg` git hook, and the CI
`pr-range` backstop that is the actual no-exceptions gate.

Both modes share one detector, `extract_citations`
(`hooks/gitapex_check_pr_issue_acm_disclosure.py`), reused rather than
reimplemented -- a citation shown only inside a fenced or inline code
block must not count, and that module's own regex already carries that
behavior (issue #657's own adversarial-review fix); a second copy here
would risk drifting out of sync with it. This file mirrors
`.github/scripts/gitapex_run_betterleaks.py`'s one-script/two-`--mode`
shape: the single script both `.pre-commit-config.yaml`'s `commit-msg`
stage hook and this issue's own CI workflow invoke, at a different
`--mode` each.

**`--mode commit-msg`** (the local first pass,
`.pre-commit-config.yaml`'s `stages: [commit-msg]` hook): reads the
commit-message file path prek hands it as its sole positional argument --
live-verified against a real `prek install -t commit-msg` run rather than
assumed (a `language: system` hook run from the repo root receives the
same single, repo-root-relative path git's own commit-msg hook contract
does: `.git/COMMIT_EDITMSG`). Passes when the message alone carries a
citation.

**`--mode pr-range`** (the CI backstop, no-exceptions per this issue):
passes when a citation is found in the PR's own title/body OR in at
least one *non-merge* commit in the PR's range; an uncited merge commit
in that same range never fails this check on its own -- `git log
--no-merges` excludes it from the scan entirely, before any citation
check ever runs against it.

**Base-ref resolution, local vs. CI.** `.gitapex/ssot.json`'s own
`local_invocation` runs this mode with no `--base-ref` at all, since a
`local-preflight` run has no PR yet: this self-heals `origin/main` the
same way `gitapex_run_base_diff.py`'s own `ensure_base_ref` does --
`_gitapex_base_ref`'s peeled-probe-then-destination-refspec-fetch, only
when the probe first finds nothing -- rather than
`gitapex_gate_behind_base.py`'s unconditional-fetch-every-run posture:
this gate does not need `origin/main` to be perfectly fresh (a stale
local ref only shifts which already-cited commits fall inside the
scanned range, not whether the *current* branch's own commits/title/body
carry a citation), so the cheaper probe-first form is the right
trade-off here, not a corner cut. The CI workflow instead passes
`--base-ref` explicitly -- the real `git merge-base "$BASE_SHA"
"$HEAD_SHA"` the workflow itself computes, mirroring
`exception-handler-gap-gate.yml`'s own established
merge-base-not-base.sha pattern (never `base.sha` directly, which can go
stale relative to a `main` that advanced after the PR opened) -- so this
module's own fetch/self-heal path never runs in CI: the workflow's own
`harden-checkout` step already fetched enough history for the merge-base
it computed to resolve.

**PR title/body, passed as files, not stdin.** `--title`/`--body` each
optionally name a file (mirroring `gitapex_gate_acm_issue_disclosure.py`'s
own `--body PATH` and `gitapex_gate_provenance_disclosure.py`'s own
`--body`/`--diff-added` file-path convention) rather than one JSON
payload or stdin -- this mode needs *two* independent pieces of untrusted
text at once, and stdin can only carry one. The calling workflow follows
`provenance-disclosure-gate.yml`'s exact pattern: write each of
`github.event.pull_request.title`/`.body` to its own file via `env:`
indirection first (`printf '%s' "$PR_TITLE" > ...`), never interpolating
either directly into a shell command line. Both are omitted in
`local_invocation` (no PR exists yet locally) and default to empty text
-- the commit-range scan alone still runs.

Exit codes (both modes): 0 pass, 1 no citation found (a clear FAIL on
stderr), 2 the check itself could not be trusted -- invalid CLI
arguments, an unreadable input file, or (`pr-range` only) a base ref that
could not be resolved/fetched or shares no common ancestor with HEAD.
Mirrors `gitapex_gate_behind_base.py`'s/`gitapex_run_base_diff.py`'s own
0/1/2 convention, distinct from a confirmed policy FAIL.

Non-goals (named explicitly, not silently out of scope): no retroactive
citation of existing merged commit history, and no citation *format*
validation (issue #521's separate scope) -- this gate only asks whether
*any* citation form (`Closes #N`, `Fixes #N`, `Refs #N`, or a bare `#N`)
is present, never which one or whether it resolves.

Usage::

    # commit-msg (installed by .pre-commit-config.yaml; the path below is
    # what prek itself hands the hook, not typed by a contributor):
    uv run --frozen python3 .github/scripts/gitapex_gate_commit_citation.py \\
        --mode commit-msg .git/COMMIT_EDITMSG

    # pr-range (CI): base-ref is the workflow's own precomputed merge-base
    uv run --frozen python3 .github/scripts/gitapex_gate_commit_citation.py \\
        --mode pr-range --owner tvna --repo gitapex \\
        --base-ref "$merge_base" --head-ref "$HEAD_SHA" \\
        --title "$RUNNER_TEMP/pr_title.txt" --body "$RUNNER_TEMP/pr_body.txt"

    # pr-range (local preflight; no PR yet -- commit range only):
    uv run --frozen python3 .github/scripts/gitapex_gate_commit_citation.py --mode pr-range
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from typing import Literal, cast

import _gitapex_base_ref
from pydantic import BaseModel, ValidationError, field_validator, model_validator

# hooks/ is a sibling of .github/ at the repo root, never on sys.path by
# default for a standalone `uv run --frozen python3` invocation of this file
# (Python only auto-adds this script's own directory). Mirrors the
# exact `sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))`
# bootstrap style every other cross-file .github/scripts/*.py import in this
# repository already uses (e.g. gitapex_gate_ruleset_required_checks.py), just
# pointed at hooks/ instead of this file's own directory. Under pytest this is
# a harmless no-op prepend: pyproject.toml's own `pythonpath` already lists
# both ".github/scripts" and "hooks".
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "hooks"))

from gitapex_check_pr_issue_acm_disclosure import extract_citations  # sys.path bootstrap above must run first

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Hardcoded per the same posture gitapex_gate_behind_base.py's own
# BASE_REMOTE/BASE_BRANCH and gitapex_run_base_diff.py's own identical
# constants document (issue #985) -- this repository has exactly one base
# branch today; see either module's own docstring for the named residual
# risks that posture carries. Only reached by resolve_base_ref's own local
# self-heal path below -- CI always passes --base-ref explicitly.
BASE_REMOTE = "origin"
BASE_BRANCH = "main"

# Ceiling for one git subprocess call this module makes (a probe, a fetch, a
# merge-base check, or the real `git log`) -- matches
# _gitapex_base_ref.GIT_TIMEOUT_SECONDS exactly rather than redefining 60 as
# a second literal, the same convention gitapex_gate_behind_base.py and
# gitapex_run_base_diff.py both already follow.
GIT_TIMEOUT_SECONDS = _gitapex_base_ref.GIT_TIMEOUT_SECONDS


class CitationGateError(Exception):
    """The check could not be trusted -- exit 2, never a silent pass and
    never conflated with a genuine no-citation FAIL (exit 1)."""


def check_commit_message(text: str) -> bool:
    """True iff one commit's own message `text` carries any citation --
    resolving or context-only, either counts here: this gate only asks
    *whether* an issue is cited, never which form or whether it resolves
    (format/ACM validation is out of scope -- issue #521, #657). Always
    `owner=None, repo=None`: a lone commit message carries no notion of
    "this PR's own target repo" the way a PR title/body does, matching
    exactly how `--mode commit-msg` itself calls `extract_citations`."""
    resolving, context = extract_citations(None, None, None, text)
    return bool(resolving or context)


def check_pr_text(owner: str, repo: str, title: str, body: str) -> bool:
    """True iff the PR's own `title`/`body` together carry any citation.
    `owner`/`repo` (the PR's own target repo) are passed through so
    `extract_citations` can normalize a same-repo-qualified
    `owner/repo#N` citation down to a bare `#N` -- see its own docstring."""
    resolving, context = extract_citations(owner or None, repo or None, title or None, body or None)
    return bool(resolving or context)


def resolve_base_ref(root: pathlib.Path, base_ref: str | None) -> str:
    """The PR's own base ref for `git log --no-merges <base>..<head>`.

    CI passes `base_ref` explicitly (its own precomputed merge-base -- see
    module docstring), which is returned unchanged with no git call at
    all. A local run leaves it unset: this self-heals `refs/remotes/
    origin/main`, mirroring `gitapex_run_base_diff.py`'s own
    `ensure_base_ref` -- a cheap peeled probe first, a destination-refspec
    fetch only when that probe finds nothing, then a re-probe that never
    trusts the fetch's own exit code alone (issue #1345) -- and finally
    confirms a common ancestor exists with HEAD (the shallow-clone case;
    `git merge-base` prints nothing to stderr on that failure otherwise,
    per `_gitapex_base_ref.require_common_ancestor`'s own docstring)."""
    if base_ref is not None:
        return base_ref

    if not _gitapex_base_ref.peeled_ref_exists(
        root, BASE_REMOTE, BASE_BRANCH, timeout=GIT_TIMEOUT_SECONDS, error_cls=CitationGateError
    ):
        _gitapex_base_ref.fetch_destination_refspec(
            root, BASE_REMOTE, BASE_BRANCH, timeout=GIT_TIMEOUT_SECONDS, error_cls=CitationGateError
        )
        if not _gitapex_base_ref.peeled_ref_exists(
            root, BASE_REMOTE, BASE_BRANCH, timeout=GIT_TIMEOUT_SECONDS, error_cls=CitationGateError
        ):
            raise CitationGateError(
                f"git fetch {BASE_REMOTE} {BASE_BRANCH} reported success but "
                f"refs/remotes/{BASE_REMOTE}/{BASE_BRANCH} still does not resolve -- "
                "never trusting a fetch's exit code alone (issue #1345)"
            )

    qualified_ref = f"refs/remotes/{BASE_REMOTE}/{BASE_BRANCH}"
    _gitapex_base_ref.require_common_ancestor(
        root, qualified_ref, timeout=GIT_TIMEOUT_SECONDS, error_cls=CitationGateError
    )
    return qualified_ref


def commit_range_messages(root: pathlib.Path, base_ref: str, head_ref: str) -> list[str]:
    """Every *non-merge* commit's own full message (`%B`) in
    `base_ref..head_ref`, NUL-separated (`%x00`) so a message that itself
    contains a blank line cannot be mistaken for a commit boundary -- a
    real commit message cannot itself carry a NUL byte. `--no-merges`
    excludes a real merge commit from this list entirely, before any
    citation check ever runs against it -- an uncited merge commit in the
    range therefore never fails this gate on its own, this issue's own
    stated Non-goal."""
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "log", "--no-merges", f"{base_ref}..{head_ref}", "--format=%B%x00"],  # noqa: S607
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise CitationGateError(f"git log --no-merges {base_ref}..{head_ref} failed: {result.stderr.strip()}")
    return [message.strip() for message in result.stdout.split("\x00") if message.strip()]


def evaluate_pr_range(
    root: pathlib.Path,
    owner: str,
    repo: str,
    title: str,
    body: str,
    base_ref: str | None,
    head_ref: str,
) -> tuple[bool, str]:
    """(passed, message) for the full `--mode pr-range` check: a citation
    in the PR's own title/body is checked first (no git call at all, and
    the common case), so `resolve_base_ref`'s own fetch/self-heal path
    only ever runs when the title/body carry nothing -- never on the
    already-satisfied common case."""
    if check_pr_text(owner, repo, title, body):
        return True, "PR title/body cites an issue"

    resolved_base = resolve_base_ref(root, base_ref)
    for message in commit_range_messages(root, resolved_base, head_ref):
        if check_commit_message(message):
            return True, f"a non-merge commit in {resolved_base}..{head_ref} cites an issue"

    return False, (
        f"neither the PR title/body nor any non-merge commit in {resolved_base}..{head_ref} "
        "cites an issue. Per this repository's own citation convention (CONTRIBUTING.md), "
        "cite one via Closes #N, Fixes #N, Refs #N, or a bare #N."
    )


class CommitCitationArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1040's
    pydantic CLI-arg-validation convention, applied here like every other
    `.github/scripts/*.py` gate)."""

    mode: Literal["commit-msg", "pr-range"]
    commit_msg_file: str | None
    owner: str
    repo: str
    title: str | None
    body: str | None
    base_ref: str | None
    head_ref: str
    root: pathlib.Path

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value

    @model_validator(mode="after")
    def _commit_msg_file_required_in_commit_msg_mode(self) -> CommitCitationArgs:
        if self.mode == "commit-msg" and not self.commit_msg_file:
            raise ValueError("a commit message file path is required in --mode commit-msg")
        return self


def _read_optional_file(path: str | None) -> tuple[str, str | None]:
    """(text, error) for an optional `--title`/`--body` file. `error` is
    None on success. Empty text -- never an error -- when `path` itself is
    None: the flag was omitted, the local `local_invocation` shape, where
    no PR title/body exists yet and the commit-range scan alone runs."""
    if path is None:
        return "", None
    try:
        return pathlib.Path(path).read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"file not found: {path}"
    except UnicodeDecodeError as error:
        return "", f"{path} is not valid UTF-8: {error}"


def _run_commit_msg(args: CommitCitationArgs) -> int:
    # Guaranteed non-None/non-empty here: CommitCitationArgs' own validator
    # already rejected any commit-msg-mode construction missing it; cast (not
    # assert -- ruff S101 bans a bare assert outside tests) only narrows the
    # static type to match that already-enforced runtime guarantee.
    commit_msg_path = pathlib.Path(cast(str, args.commit_msg_file))
    try:
        message = commit_msg_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: commit message file not found: {commit_msg_path}", file=sys.stderr)
        return 2
    except UnicodeDecodeError as error:
        print(f"error: {commit_msg_path} is not valid UTF-8: {error}", file=sys.stderr)
        return 2

    if check_commit_message(message):
        print("PASS: commit message cites an issue")
        return 0
    print(
        "FAIL: commit message cites no issue. Per this repository's own citation convention "
        "(CONTRIBUTING.md), cite one via Closes #N, Fixes #N, Refs #N, or a bare #N.",
        file=sys.stderr,
    )
    return 1


def _run_pr_range(args: CommitCitationArgs) -> int:
    title, title_error = _read_optional_file(args.title)
    if title_error:
        print(f"error: {title_error}", file=sys.stderr)
        return 2
    body, body_error = _read_optional_file(args.body)
    if body_error:
        print(f"error: {body_error}", file=sys.stderr)
        return 2

    try:
        passed, message = evaluate_pr_range(args.root, args.owner, args.repo, title, body, args.base_ref, args.head_ref)
    except CitationGateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if passed:
        print(f"PASS: {message}")
        return 0
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce CLAUDE.md section 3's issue-citation rule for commits (issue #1212): "
        "a citation must exist in at least one non-merge commit, or in the PR title/body."
    )
    parser.add_argument("--mode", required=True, choices=["commit-msg", "pr-range"])
    parser.add_argument(
        "commit_msg_file",
        nargs="?",
        help="--mode commit-msg only: path to the commit message file (prek's own sole positional argument).",
    )
    parser.add_argument("--owner", default="", help="--mode pr-range only: the PR's own target repo owner.")
    parser.add_argument("--repo", default="", help="--mode pr-range only: the PR's own target repo name.")
    parser.add_argument("--title", help="--mode pr-range only: path to a file holding the PR title. Omit for none.")
    parser.add_argument("--body", help="--mode pr-range only: path to a file holding the PR body. Omit for none.")
    parser.add_argument(
        "--base-ref",
        help="--mode pr-range only: the PR's base ref/SHA (a workflow's own precomputed merge-base). "
        "Omit for a local run -- self-heals refs/remotes/origin/main.",
    )
    parser.add_argument("--head-ref", default="HEAD", help="--mode pr-range only: the PR's head ref/SHA.")
    parser.add_argument(
        "--root", type=pathlib.Path, default=REPO_ROOT, help="--mode pr-range only: the git working tree to scan."
    )
    args = parser.parse_args(argv)

    try:
        validated = CommitCitationArgs(
            mode=args.mode,
            commit_msg_file=args.commit_msg_file,
            owner=args.owner,
            repo=args.repo,
            title=args.title,
            body=args.body,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            root=args.root,
        )
    except ValidationError as error:
        print(f"error: invalid CLI arguments: {error}", file=sys.stderr)
        return 2

    if validated.mode == "commit-msg":
        return _run_commit_msg(validated)
    return _run_pr_range(validated)


if __name__ == "__main__":
    raise SystemExit(main())

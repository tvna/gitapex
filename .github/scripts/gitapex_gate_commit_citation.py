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
citation -- the *cleaned* message, see next paragraph -- or when the
commit being written is a *merge* commit (`merge_in_progress`), which
`--mode pr-range` already exempts through `git log --no-merges` and which
this layer would otherwise reject on every `git merge`.

**Why `--mode commit-msg` must clean the file first (and `--mode
pr-range` must not).** A `commit-msg` hook runs *before* git applies its
own `--cleanup` pass, so the file git hands the hook is still raw: it
carries git's whole comment block (`core.commentChar`, `#` by default)
and, under `commit.verbose=true`/`git commit -v`, the entire staged diff
below the `# ------------------------ >8 ------------------------`
scissors line. Live-reproduced, not assumed (issue #1212's own
adversarial review): staging a file whose *content* contains a
citation-shaped line, then committing the uncited subject `chore: tidy up
formatting` through an editor, produced a raw hook file whose diff
section read `+    # See issue #1212 for the rationale.` -- and this gate
returned PASS for a commit whose actually-stored `%B` was
`chore: tidy up formatting`, citing nothing. `clean_commit_message`
closes that false-PASS by applying git's own two cleanup steps in git's
own order before any citation check runs. `--mode pr-range` deliberately
skips this: `git log --format=%B` already returns post-cleanup messages,
so cleaning there would be a redundant subprocess per commit.

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

**"Nothing to check" is not a policy FAIL.** `.gitapex/ssot.json`'s own
`local_invocation` runs `--mode pr-range` with neither `--title` nor
`--body`, and that invocation feeds the `pre-push` hook's
`local-preflight` runner, which reads *any* non-zero exit as a blocked
push. On a checkout where `refs/remotes/origin/main..HEAD` is empty --
right after a fast-forward, or a branch whose own commits are all already
merged into `main` -- there is no commit and no PR text to evaluate at
all, so there is no citation obligation to violate; reporting that state
as "you cited nothing" (live-reproduced as exit 1, issue #1212's own
adversarial review) blocks a push for a state that cannot cite anything.
`evaluate_pr_range`'s own `pr_text_supplied` flag separates the two: an
empty commit range *and* neither `--title` nor `--body` supplied passes
with an explicit "nothing to check" message, while every other shape
keeps its previous verdict byte for byte. The flag tracks whether the
*flags were passed*, never whether their text is non-empty, so CI -- which
always passes both -- is unreachable from this path and its behavior is
unchanged even for an empty range; the parameter's own default is the
strict `True`, so a caller that forgets it fails closed.

Exit codes (both modes): 0 pass, 1 no citation found (a clear FAIL on
stderr), 2 the check itself could not be trusted -- invalid CLI
arguments, an unreadable input file, a `git stripspace` call that could
not run or failed (`commit-msg` only -- never a silent fallback to
uncleaned text), or (`pr-range` only) a base ref that could not be
resolved/fetched, shares no common ancestor with HEAD, or a git call that
could not run at all (no `git` on PATH, a hang past
`GIT_TIMEOUT_SECONDS`).
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
#
# Spelled out here rather than reusing REPO_ROOT below: ruff's own E402
# tolerates a sys.path mutation before this deferred import, but not a
# preceding assignment, so hoisting REPO_ROOT above this line to share the
# expression fails `ruff check` outright (verified, not assumed).
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

# The body of git's own "scissors" cut line, verbatim from git-commit(1)'s
# own `--cleanup=scissors` documentation ("everything from (and including)
# the line found below is truncated"). Only the *prefix* of that line varies
# -- git writes `<comment_line_str> <cut line>`, so a repository configuring
# `core.commentChar = ;` gets `; ------------------------ >8 ---...` instead
# (live-verified, both forms). Matched as a substring rather than anchored to
# a known comment prefix precisely so no comment-character guess is needed:
# `core.commentChar = auto` makes `git config --get core.commentChar` report
# the literal string "auto" rather than the character git actually chose
# (live-verified), so a prefix-anchored match would silently stop truncating
# there. The looser match can only ever truncate *earlier* than git would,
# which drops text from the scanned message and can therefore only turn a
# PASS into a FAIL -- fail-closed, never a new false-PASS.
SCISSORS_MARKER = "------------------------ >8 ------------------------"


class CitationGateError(Exception):
    """The check could not be trusted -- exit 2, never a silent pass and
    never conflated with a genuine no-citation FAIL (exit 1)."""


def truncate_at_scissors(text: str) -> str:
    """`text` up to (never including) git's own scissors line -- the first
    line containing :data:`SCISSORS_MARKER` -- or `text` unchanged when
    there is none (the ordinary, non-`commit.verbose` commit).

    Step one of two, and it must run *before* the comment strip, not
    after: the scissors line is itself a comment line, so stripping
    comments first would delete the only marker separating the message
    from the verbatim staged diff below it and leave that whole diff in
    the scanned text -- exactly the false-PASS this function exists to
    close. `git stripspace --strip-comments` has no scissors handling of
    its own at all (live-verified: it removes the scissors line and leaves
    the diff), so this step cannot be delegated to git the way the comment
    strip below is."""
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        if SCISSORS_MARKER in line:
            break
        kept.append(line)
    return "".join(kept)


def clean_commit_message(root: pathlib.Path, text: str) -> str:
    """One raw `commit-msg`-hook file's text, reduced to what git will
    actually store as the commit message: scissors block truncated
    (:func:`truncate_at_scissors`), then comment lines removed.

    The comment strip is delegated to `git stripspace --strip-comments`
    rather than hand-rolled: that is git's *own* implementation of this
    exact step, so it resolves `core.commentChar` (and, on git >= 2.45,
    `core.commentString`) itself, from the same config the commit being
    checked will be cleaned with. Live-verified against a repository
    configuring `core.commentChar = ;`, where a hardcoded `#` strip would
    have removed nothing at all. It also runs fine outside a git
    repository (verified), so a checkout in an odd state degrades to
    default-`#` behavior rather than an error.

    Raises :class:`CitationGateError` -- exit 2, "the check could not be
    trusted" -- when `git stripspace` cannot run (no `git` on PATH, a hang
    past `GIT_TIMEOUT_SECONDS`) or exits non-zero. Deliberately never a
    silent fallback to the unstripped text: that fallback would restore
    the precise false-PASS this function exists to close, and would do it
    invisibly, on exactly the broken-environment path where nobody is
    looking."""
    truncated = truncate_at_scissors(text)
    result = _gitapex_base_ref.run_git(
        root,
        ["stripspace", "--strip-comments"],
        label="strip comments from the commit message",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=CitationGateError,
        stdin_text=truncated,
    )
    if result.returncode != 0:
        raise CitationGateError(f"git stripspace --strip-comments failed: {result.stderr.strip()}")
    return result.stdout


def merge_in_progress(root: pathlib.Path) -> bool:
    """Whether git is part-way through creating a *merge* commit right
    now -- `git rev-parse --verify --quiet MERGE_HEAD`, which resolves
    exactly while `.git/MERGE_HEAD` exists and not otherwise.

    `--mode commit-msg` needs this to reach the same verdict `--mode
    pr-range` already reaches through `git log --no-merges`: this issue's
    own stated non-goal is that an uncited merge commit never fails this
    gate. Without it the two layers actively disagree -- live-reproduced,
    not theorized: with the hook installed, an ordinary `git merge --no-ff`
    whose default message is `Merge branch 'side'` was rejected outright
    ("Not committing merge; use 'git commit' to complete the merge"),
    which would break this repository's own documented `git pull
    --no-rebase` shared-branch workflow (CLAUDE.md section 3) on every
    merge -- and `.claude/hooks/session-start.sh` now installs this hook
    automatically for every session, so nobody has to opt in to hit it.

    `MERGE_HEAD`, never the message file's own basename: git-merge hands
    the hook `.git/MERGE_MSG`, but a `git commit` *completing* an already-
    started merge hands it `.git/COMMIT_EDITMSG` with `MERGE_HEAD` still
    set -- both are the same merge commit and both must be exempt (both
    verified live). `git merge --squash` deliberately stays gated: it sets
    `SQUASH_MSG`, never `MERGE_HEAD`, and produces an ordinary
    single-parent commit that `git log --no-merges` would scan in CI too,
    so exempting it would be a real divergence rather than a matching one.
    `git revert` and `git cherry-pick` need no handling here at all --
    verified live that neither invokes this hook."""
    result = _gitapex_base_ref.run_git(
        root,
        ["rev-parse", "--verify", "--quiet", "MERGE_HEAD"],
        label="check whether a merge is in progress",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=CitationGateError,
    )
    return result.returncode == 0


def _extract_citations_or_raise(
    owner: str | None, repo: str | None, title: str | None, body: str | None
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """`extract_citations`, with one failure mode converted to this
    module's own exit-2 contract rather than an uncaught traceback (issue
    #1212's own adversarial review, dimension 15 of
    `skills/evaluating-deterministic-gate-quality`): Python 3.12's default
    integer-string-conversion digit limit (`sys.get_int_max_str_digits`,
    4300) makes `extract_citations`' own `int(n)` calls raise `ValueError`
    for a citation whose digit run is implausibly long (a PR title/body or
    commit message containing `#` followed by thousands of digits -- live-
    reproduced: `int('9' * 5000)` raises). Uncaught, that `ValueError`
    exits 1 -- the code this module reserves for a *confirmed* no-citation
    policy FAIL -- so a malformed/adversarial input would report itself as
    a real citation violation instead of "the check itself could not be
    trusted." No other `extract_citations` failure mode is known; this is
    not a blanket except-and-hide."""
    try:
        return extract_citations(owner, repo, title, body)
    except ValueError as error:
        raise CitationGateError(f"could not parse a citation number in the input text: {error}") from error


def check_commit_message(text: str) -> bool:
    """True iff one commit's own message `text` carries any citation --
    resolving or context-only, either counts here: this gate only asks
    *whether* an issue is cited, never which form or whether it resolves
    (format/ACM validation is out of scope -- issue #521, #657). Always
    `owner=None, repo=None`: a lone commit message carries no notion of
    "this PR's own target repo" the way a PR title/body does, matching
    exactly how `--mode commit-msg` itself calls `extract_citations`.

    Expects an already-*cleaned* message: `git log`'s own `%B` output in
    `--mode pr-range`, or :func:`clean_commit_message`'s output in
    `--mode commit-msg`. Cleaning stays the caller's job rather than
    moving in here, so `--mode pr-range` does not pay a `git stripspace`
    subprocess per commit re-cleaning text git already cleaned.

    May raise :class:`CitationGateError` -- see `_extract_citations_or_raise`."""
    resolving, context = _extract_citations_or_raise(None, None, None, text)
    return bool(resolving or context)


def check_pr_text(owner: str, repo: str, title: str, body: str) -> bool:
    """True iff the PR's own `title`/`body` together carry any citation.
    `owner`/`repo` (the PR's own target repo) are passed through so
    `extract_citations` can normalize a same-repo-qualified
    `owner/repo#N` citation down to a bare `#N` -- see its own docstring.

    May raise :class:`CitationGateError` -- see `_extract_citations_or_raise`."""
    resolving, context = _extract_citations_or_raise(owner or None, repo or None, title or None, body or None)
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
    stated Non-goal.

    Runs through `_gitapex_base_ref.run_git`, like every other git call
    this module makes: that helper already carries this call's exact
    capture/`errors="replace"` shape, and turns a subprocess-layer failure
    (no `git` on PATH, a hang past `GIT_TIMEOUT_SECONDS`) into a
    `CitationGateError` -- the exit-2 "could not be trusted" signal --
    rather than an uncaught exception.

    One entry per commit, *including* a commit whose message is empty
    (`git commit --allow-empty-message`), which is why the split drops
    only its own final element rather than filtering every empty one out.
    `git log --format=%B%x00` emits `<message>%x00` plus git's own
    per-commit trailing newline, so N commits always produce exactly N+1
    NUL-separated parts and the last is a separator artifact, never a
    commit (verified live against a real repo, including the zero-commit
    case, where stdout is empty and the single part yields an empty list).
    Filtering on truthiness instead -- the pre-review form -- made two
    real `--allow-empty-message` commits indistinguishable from an *empty
    range*, which `evaluate_pr_range` now treats as "nothing to check";
    an uncited commit would have passed the gate as though it were not
    there at all."""
    result = _gitapex_base_ref.run_git(
        root,
        ["log", "--no-merges", f"{base_ref}..{head_ref}", "--format=%B%x00"],
        label=f"list commits in {base_ref}..{head_ref}",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=CitationGateError,
    )
    if result.returncode != 0:
        raise CitationGateError(f"git log --no-merges {base_ref}..{head_ref} failed: {result.stderr.strip()}")
    return [message.strip() for message in result.stdout.split("\x00")[:-1]]


def evaluate_pr_range(
    root: pathlib.Path,
    owner: str,
    repo: str,
    title: str,
    body: str,
    base_ref: str | None,
    head_ref: str,
    *,
    pr_text_supplied: bool = True,
) -> tuple[bool, str]:
    """(passed, message) for the full `--mode pr-range` check: a citation
    in the PR's own title/body is checked first (no git call at all, and
    the common case), so `resolve_base_ref`'s own fetch/self-heal path
    only ever runs when the title/body carry nothing -- never on the
    already-satisfied common case.

    `pr_text_supplied` is False only for the local `local_invocation`
    shape, where neither `--title` nor `--body` was passed at all. It
    separates "nothing to check" from "something to check and it failed":
    an empty commit range with no PR text supplied carries no citation
    obligation to violate (see the module docstring), and reporting it as
    a FAIL blocks the `pre-push` local-preflight for a state that cannot
    cite anything. Defaults to the strict True so a caller that forgets it
    -- or any future call site -- fails closed; CI always passes both
    flags and therefore never reaches this branch."""
    if check_pr_text(owner, repo, title, body):
        return True, "PR title/body cites an issue"

    resolved_base = resolve_base_ref(root, base_ref)
    messages = commit_range_messages(root, resolved_base, head_ref)
    for message in messages:
        if check_commit_message(message):
            return True, f"a non-merge commit in {resolved_base}..{head_ref} cites an issue"

    if not messages and not pr_text_supplied:
        return True, (
            f"nothing to check -- no non-merge commit in {resolved_base}..{head_ref}, "
            "and no PR title/body was supplied. Nothing here can carry a citation, "
            "so this is not a citation-policy failure."
        )

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


def _read_input_file(path: str | None, *, label: str = "file") -> str:
    """The text of one input file this gate was pointed at. Empty text --
    never an error -- when `path` itself is None: the `--title`/`--body`
    flag was omitted, the local `local_invocation` shape, where no PR
    title/body exists yet and the commit-range scan alone runs.

    Raises :class:`CitationGateError` -- the module's own exit-2 "the
    check itself could not be trusted" signal, which both call sites
    already catch -- rather than returning an error alongside the text, so
    all three reads share one handler pair instead of three copies.
    `label` only names the file in the not-found message ("commit message
    file" for `--mode commit-msg`'s own positional argument).

    The broad `OSError` arm is not defensive padding (issue #1212's own
    adversarial review, dimension 15 of
    `skills/evaluating-deterministic-gate-quality`): before it, only
    `FileNotFoundError` and `UnicodeDecodeError` were caught, so pointing
    any of the three path flags at a *directory* (`IsADirectoryError`) or
    at a file the process cannot read (`PermissionError`) escaped as an
    uncaught traceback -- and Python's own exit code for that is 1, which
    is exactly the code this module reserves for a *confirmed* no-citation
    policy FAIL. A broken invocation therefore reported itself as a real
    citation violation. All three were live-reproduced against the CLI,
    not inferred from reading the except clauses."""
    if path is None:
        return ""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise CitationGateError(f"{label} not found: {path}") from error
    except UnicodeDecodeError as error:
        raise CitationGateError(f"{path} is not valid UTF-8: {error}") from error
    except OSError as error:
        raise CitationGateError(f"{label} could not be read: {path}: {error}") from error


def _run_commit_msg(args: CommitCitationArgs) -> int:
    # Guaranteed non-None/non-empty here: CommitCitationArgs' own validator
    # already rejected any commit-msg-mode construction missing it; cast (not
    # assert -- ruff S101 bans a bare assert outside tests) only narrows the
    # static type to match that already-enforced runtime guarantee.
    try:
        # Checked before the message is even read: a merge commit is exempt
        # by this issue's own non-goal, exactly as `--mode pr-range`'s own
        # `git log --no-merges` already exempts it.
        if merge_in_progress(args.root):
            print("PASS: merge commit -- exempt, matching --mode pr-range's own git log --no-merges")
            return 0
        raw = _read_input_file(cast(str, args.commit_msg_file), label="commit message file")
        # Never the raw text: at commit-msg-hook time git has not run its own
        # cleanup yet, so `raw` still carries the comment block and (under
        # commit.verbose) the whole staged diff -- see the module docstring's
        # own live-reproduced false-PASS.
        message = clean_commit_message(args.root, raw)
        cited = check_commit_message(message)
    except CitationGateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if cited:
        print("PASS: commit message cites an issue")
        return 0
    print(
        "FAIL: commit message cites no issue. Per this repository's own citation convention "
        "(CONTRIBUTING.md), cite one via Closes #N, Fixes #N, Refs #N, or a bare #N.",
        file=sys.stderr,
    )
    return 1


def _run_pr_range(args: CommitCitationArgs) -> int:
    try:
        title = _read_input_file(args.title)
        body = _read_input_file(args.body)
        passed, message = evaluate_pr_range(
            args.root,
            args.owner,
            args.repo,
            title,
            body,
            args.base_ref,
            args.head_ref,
            # Flag *presence*, never text emptiness: CI always passes both
            # (a PR body can legitimately be empty), so CI never reaches
            # evaluate_pr_range's own "nothing to check" branch.
            pr_text_supplied=args.title is not None or args.body is not None,
        )
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
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="The git working tree to scan (--mode pr-range), and the one whose core.commentChar "
        "`git stripspace` resolves when cleaning the message (--mode commit-msg).",
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

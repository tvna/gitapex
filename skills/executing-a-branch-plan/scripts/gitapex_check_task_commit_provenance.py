"""Deterministic scan for undisclosed AI-provenance markers in a task's own
new commit messages, before those commits are merged onto the shared branch.

Issue #1477 (gate-proposal, retro #1475 repair 3): a branch-plan-task
subagent appended a Claude-Session URL and a Co-Authored-By: Claude Sonnet 5
trailer to its own commit message -- a violation of this repository's
disclosure convention. CONTRIBUTING.md's "outward-artifact-preflight:
PR-body trailer disclosure" section ratifies ONLY the server-appended
PR-body trailer as a disclosed convention; it states plainly that a model
identifier, session URL, or internal tooling fingerprint appearing anywhere
else -- "a commit message, code comment, issue body, generated file, or
review comment. Those stay in scope by default." The offending commit had
already been merged onto the shared branch and pushed to the remote before
merge-back review caught it, requiring a git commit-tree history rewrite
and a force-with-lease push to remediate -- exactly the destructive-repair
class CLAUDE.md section 3's own harness-building principle says to close
with a deterministic gate rather than relying on review to catch it after
the fact.

This closes the gap by running BEFORE that merge, not after: step 6 of
executing-a-branch-plan/SKILL.md scans each task's own new commit messages
(the same `BASE..HEAD` range already computed for that step's per-task diff
screening) and, on a hit, blocks the merge outright -- dispatched through
step 7's failure rule, the same hard-flag treatment step 6 already gives a
workflow-file or governance-file edit found during diff screening.

**Deterministic, not advisory, unlike check-bash-safety.sh's own git-push
path.** That hook's own `warn()` on `git push` is deliberately advisory
(gitapex_scan_provenance.py's own docstring: "surfaces candidates, it does
not decide") because a PR/issue-body hit can legitimately be the one
ratified trailer CONTRIBUTING.md discloses. No equivalent ratified exception
exists for a commit message -- see that same CONTRIBUTING.md section, which
states a commit message and its kin "stay in scope by default" -- so a hit
here has no legitimate reading to preserve judgment for, and this script's own exit
code is meant to gate the merge, not merely advise on it.

**Runs in the main thread, not inside the branch-plan-task's own isolated
worktree, by design.** Issue #1477's own residual-risk column named an open
question: whether a hook running inside a branch-plan-task's own worktree
has the tooling access the outward-artifact-preflight scanner needs, and
whether it fires consistently across both the project-local variant (an
embedded PreToolUse hook) and the plugin-distributed variant (no hook
support at all, per Claude Code's own plugin-agent frontmatter restriction
-- see references/threat-model-and-authorization.md's own accounting of
that asymmetry). Running this check in the main thread instead of inside
the task's own worktree sidesteps that asymmetry entirely: the main thread
always has full filesystem access regardless of which branch-plan-task
variant produced the commit, so this check's own correctness does not
depend on which variant ran, or on either variant's own Bash-hook coverage.

Reuses, not re-implements, `gitapex_scan_provenance.py`'s own `scan()` --
loaded by file path, the identical technique
`hooks/gitapex_check_post_write_provenance.py` already established for the
same reuse need (that directory is not on pyproject.toml's `pythonpath`).
No new detection heuristic is added here: the same corroborating-context
rule that scanner already applies to PR/issue bodies applies unchanged to a
commit message, disclosed residuals included -- widening that scanner's own
regex coverage is out of this issue's scope, which is extending an existing,
already-trusted discipline to a new surface, not improving its accuracy.

Usage -- two separate steps, deliberately never piped directly together::

    git log --format=%B -z BASE..HEAD > /tmp/task-commit-messages.bin
    python3 gitapex_check_task_commit_provenance.py --messages /tmp/task-commit-messages.bin

`-z` NUL-terminates each commit's own raw message body, so a multi-line
message is never mistaken for a boundary between two commits.

**Never invoke as `git log ... | python3 ...` in an ordinary (non-`pipefail`)
shell.** A bare pipe hides `git log`'s own failure: an unresolvable `BASE`
(a stale ref, a rebase, a shallow worktree, or an agent copying this
docstring's own `BASE..HEAD` placeholder text verbatim without substituting
real refs) makes `git log` exit non-zero and write nothing to stdout, but a
plain shell pipeline's own exit status is the RIGHT-hand command's -- this
script's own, which then reads empty stdin, correctly reports "PASS: no
commits in range" per its own contract, and exits 0. A caller checking only
`$?` after the pipe sees a clean PASS even though no commit was ever
actually scanned -- exactly the "never a silent PASS" contract this
docstring's own Exit codes section states, silently defeated one layer
above this script's own control, for exactly the class of incident (issue
#1477) this gate exists to prevent. The two-step form above closes this by
construction: `git log`'s own exit code is a separate, directly observable
signal on its own command, confirmed non-zero before this script ever
runs, not a masked one that would otherwise still route to a python
process this script does not own or protect. Found live by this script's
own security review (issue #1477's implementing PR).

Exit codes:
    0  PASS -- no commits in range, or every commit message scanned clean.
    1  FLAGGED -- at least one commit message carries a candidate
       undisclosed AI-provenance marker. Never a judgment call to weigh
       here (see the "no ratified exception" note above): treat this as a
       hard block on the merge.
    2  usage/environment error (the provenance scanner could not be loaded,
       or the input could not be read/decoded) -- never a silent PASS.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

# skills/, not hooks/, is this file's own sibling directory here -- three
# parents up from skills/executing-a-branch-plan/scripts/<this file>.py
# reaches the repository root, matching how
# hooks/gitapex_check_post_write_provenance.py resolves the identical
# scanner one directory level up from its own shallower location.
_SCANNER_RELATIVE_PATH = Path("skills") / "outward-artifact-preflight" / "scripts" / "gitapex_scan_provenance.py"


# Reported hits are capped so a pathological task branch (many small WIP
# commits accumulated before step 6's own screening runs, or a single
# commit whose message repeats a marker many times) cannot produce an
# unbounded report -- the same defensive convention
# hooks/gitapex_check_post_write_provenance.py's own `_MAX_REPORTED_HITS`
# already establishes for the identical reuse of this scanner. The verdict
# and the total counts are always reported in full; only the per-item
# detail is truncated.
_MAX_REPORTED_COMMITS = 20
_MAX_REPORTED_HITS_PER_COMMIT = 20


class ScannerLoadError(RuntimeError):
    """The provenance scanner could not be loaded -- exit 2, never a silent PASS."""


def load_provenance_scanner(scanner_path: Path | None = None) -> ModuleType:
    """Import gitapex_scan_provenance.py by file path and return the module.

    Raises ScannerLoadError when the file is absent or cannot be executed --
    a missing scan dependency is an inability to verify, never an implicit
    clean verdict.
    """
    path = scanner_path if scanner_path is not None else Path(__file__).resolve().parents[3] / _SCANNER_RELATIVE_PATH
    if not path.is_file():
        raise ScannerLoadError(
            f"the provenance scanner was not found at {path} -- this looks like a corrupted or incomplete bundle"
        )
    spec = importlib.util.spec_from_file_location("_gitapex_task_commit_scan_provenance", path)
    if spec is None or spec.loader is None:
        raise ScannerLoadError(f"the provenance scanner at {path} could not be loaded as a Python module")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    # Deliberately broad: any import-time failure of the scanner (a syntax
    # error, a missing transitive import, an exception raised at module
    # level) is an inability to verify, and must reach the exit-2 path
    # rather than escape as a traceback that reads as a crash.
    except Exception as error:
        raise ScannerLoadError(f"the provenance scanner at {path} failed to import: {error}") from error
    # A file can exist at the expected path, import cleanly, and still not
    # be the scanner -- a rename, a truncated bundle, or a shadowing file.
    if not callable(getattr(module, "scan", None)):
        raise ScannerLoadError(f"the module at {path} imported but exposes no callable scan() -- not the scanner")
    return module


def split_commit_messages(raw: str) -> list[str]:
    """Split NUL-terminated `git log --format=%B -z` output into individual
    commit messages, in order.

    Strips exactly the one trailing NUL git always emits after the last
    message -- never every empty string in the input. An interior empty
    message (a real, if unusual, commit made with `git commit
    --allow-empty-message`) is a legitimate zero-length entry in the
    result, not something to drop: dropping it would shift every later
    commit's own 1-based index in `find_flagged_commits`'s reporting and
    undercount `len(messages)`, misdirecting an operator toward the wrong
    commit when told which one to amend. Confirmed live: filtering every
    empty string (an earlier version of this function) reported a range of
    4 real commits (clean, empty-message, flagged, clean) as "1 of 3", with
    the flagged one mislabeled commit 2 instead of its real position 3.

    `raw == ""` (no commits at all) and `raw == "\\0"` (one commit whose
    message is itself empty) are distinguishable by this function precisely
    because only ONE trailing NUL is ever stripped: the former returns `[]`,
    the latter returns `[""]`.
    """
    if raw == "":
        return []
    if raw.endswith("\0"):
        raw = raw[:-1]
    return raw.split("\0")


def find_flagged_commits(messages: list[str], scanner: ModuleType) -> list[tuple[int, list[tuple[int, str, str]]]]:
    """Return `(commit_index, hits)` for every 1-indexed commit message in
    `messages` that scanner.scan() finds at least one candidate marker in.
    1-indexed so a reported commit number reads naturally in a message
    (e.g. "commit 1 of 3"), matching git's own 1-based --format=%B... ordering
    intuition rather than a 0-based internal index leaking into user text.
    """
    flagged = []
    for index, message in enumerate(messages, start=1):
        hits = list(scanner.scan(message))
        if hits:
            flagged.append((index, hits))
    return flagged


def _subject_line(message: str) -> str:
    lines = message.splitlines()
    return lines[0] if lines else "(empty message)"


def _format_flagged(messages: list[str], flagged: list[tuple[int, list[tuple[int, str, str]]]]) -> str:
    shown = flagged[:_MAX_REPORTED_COMMITS]
    parts = []
    for index, hits in shown:
        shown_hits = hits[:_MAX_REPORTED_HITS_PER_COMMIT]
        hit_text = "; ".join(f"line {line_no}: {label}: {matched}" for line_no, label, matched in shown_hits)
        if len(hits) > len(shown_hits):
            hit_text += f"; ... and {len(hits) - len(shown_hits)} more hit(s)"
        parts.append(f"commit {index} ({_subject_line(messages[index - 1])!r}): {hit_text}")
    detail = " | ".join(parts)
    if len(flagged) > len(shown):
        detail += f" | ... and {len(flagged) - len(shown)} more flagged commit(s)"
    return detail


def main(argv: list[str] | None = None) -> int:
    """CLI: scan NUL-separated commit messages (--messages or stdin) for
    candidate undisclosed AI-provenance markers."""
    parser = argparse.ArgumentParser(
        description="Scan a task's own new commit messages (a BASE..HEAD range) for undisclosed "
        "AI-provenance markers before merging onto the shared branch. Feed with: "
        "git log --format=%B -z BASE..HEAD | python3 gitapex_check_task_commit_provenance.py"
    )
    parser.add_argument(
        "--messages",
        help="Path to NUL-separated commit messages (git log --format=%%B -z output); "
        "reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        raw = (
            Path(args.messages).read_bytes().decode("utf-8")
            if args.messages
            else sys.stdin.buffer.read().decode("utf-8")
        )
    except FileNotFoundError:
        print(f"error: messages file not found: {args.messages}", file=sys.stderr)
        return 2
    except OSError as error:
        # Broader than FileNotFoundError above -- IsADirectoryError (a
        # directory passed to --messages) and PermissionError both
        # otherwise surface as an uncaught traceback instead of this
        # module's own established `error: ...` convention, the same gap
        # gitapex_check_branch_plan_reverified.py's own adversarial review
        # (issue #1306) already found and fixed for its `--body` flag.
        print(f"error: could not read messages file: {args.messages} ({error})", file=sys.stderr)
        return 2
    except UnicodeDecodeError as error:
        source = args.messages if args.messages else "standard input"
        print(f"error: {source} is not valid UTF-8: {error}", file=sys.stderr)
        return 2

    try:
        scanner = load_provenance_scanner()
    except ScannerLoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    messages = split_commit_messages(raw)
    if not messages:
        print("PASS: no commits in range")
        return 0

    flagged = find_flagged_commits(messages, scanner)
    if not flagged:
        print(f"PASS: {len(messages)} commit message(s) scanned clean")
        return 0

    print(
        f"FLAGGED: {len(flagged)} of {len(messages)} commit message(s) carry a candidate undisclosed "
        f"AI-provenance marker -- {_format_flagged(messages, flagged)}. Per CONTRIBUTING.md's "
        "outward-artifact-preflight PR-body trailer disclosure section, the ratified PR-body trailer "
        "exception does not extend to commit messages; this is a hard block, not a judgment call. Amend "
        "the flagged commit(s) in the task's own worktree to remove the marker before merging onto the "
        "shared branch.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

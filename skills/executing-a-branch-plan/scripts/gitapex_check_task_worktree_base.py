"""Classifier backing check_task_bash_safety.sh's own worktree-base
precondition check (issue #1508, one of four duplicates consolidated into
issue #1566's own gate-preconditions-mechanism umbrella).

**The defect this closes.** A `branch-plan-task` dispatch running inside a
`isolation: 'worktree'` worktree (design doc Decision 13) is forked from
the shared plan branch's tip at wave-dispatch time. Nothing previously
re-checked, from INSIDE that worktree, whether the shared plan branch had
since advanced past the worktree's own fork point (e.g. a concurrent
sibling task's own wave merged and pushed onto the shared branch after
this worktree was created, or a stale worktree was reused across waves) --
a task could keep working, and reporting complete, from a base that no
longer reflects the shared branch's own current state, with nothing
surfacing the drift until much later, if ever.

**Why this runs as a PreToolUse Bash hook, not a SubagentStart-equivalent
one.** Claude Code has no `SubagentStart` hook event -- confirmed directly
against Claude Code's own hooks documentation during this script's own
authoring pass, matching design doc Decision 7's own "test, don't assume"
method applied to the identical question elsewhere in this skill. The
`branch-plan-task` agent type's own embedded `PreToolUse` "Bash" hook
(`check_task_bash_safety.sh`, `.claude/agents/branch-plan-task.md`) is the
earliest deterministic enforcement point actually available -- this module
is chained into that shell script as a second sibling classifier call,
exactly the way `gitapex_check_task_bash_safety.py` is already invoked
there, rather than adding a second `hooks.PreToolUse` frontmatter entry
(no such second entry exists in the shipped frontmatter for any hook
event in this agent type -- each event has exactly one). This means the
check piggybacks on the task's own FIRST (and every subsequent) Bash
call, not a true "before any tool call at all, including a non-Bash one"
gate -- an explicitly disclosed, asymmetric-strength residual, matching
this skill's own established disclosure convention (Decision 17's own
two-variant asymmetry) rather than overclaiming full coverage. See
references/execution-and-dispatch.md and
references/threat-model-and-authorization.md for the full disclosure.

**Resolving the shared plan branch's own name, without threading a new
value in from the main thread.** Nothing in this skill today passes a
dispatched task an env var, a file, or any other explicit signal naming
the shared plan branch (confirmed by reading SKILL.md and
references/execution-and-dispatch.md directly before writing this module
-- neither describes any such mechanism). A git worktree shares
refs/objects with the main checkout it was created from, so the shared
branch's own ref IS already visible from inside the task's own worktree
once its name is known; the only missing piece is the name itself. This
module resolves it via `git reflog show refs/heads/<this-worktree's-own-
current-branch>` and looks for a `"branch: Created from <name>"` entry --
the literal message git itself writes to a new branch's own reflog
whenever it is created from a named startpoint (`git branch <new>
<startpoint>`, `git checkout -b <new> <startpoint>`, and `git worktree add
-b <new> <path> <startpoint>` all write this identically -- confirmed live
against a real git worktree fixture during this module's own authoring
pass, not assumed from documentation alone). <name> is then verified to
resolve to an ACTUAL EXISTING LOCAL BRANCH (`refs/heads/<name>`
specifically, never a tag, a remote-tracking ref, or a raw SHA) before
being trusted as the shared plan branch.

**Why this resolution is deliberately narrow, not "the main checkout's own
currently checked-out branch."** An earlier design considered walking this
worktree's own `.git` file (`gitdir: <main-repo>/.git/worktrees/<id>`,
the standard linked-worktree indirection) back to the main checkout and
reading ITS currently checked-out branch instead. That heuristic is
UNSAFE: it fires for ANY linked worktree whatsoever, regardless of why it
was created -- confirmed live during this module's own authoring pass,
inside a worktree created by an entirely unrelated dispatch mechanism (not
this skill's own Workflow-tool `isolation: 'worktree'` step at all), where
the main checkout's own current branch had no relationship whatsoever to
any "shared plan branch" this worktree was ever forked from, and would
have produced a false, actively-blast-radius-widening DENY. The reflog-
based resolution above is narrowly tied to how THIS SPECIFIC worktree's
OWN branch came to exist, not to whatever the main checkout happens to be
on right now -- so it only ever resolves a name at all when a real git
operation actually created this worktree's branch FROM that named
startpoint, which is exactly the invariant a genuine branch-plan-task wave
dispatch is expected to establish, and which an unrelated worktree
naturally fails to satisfy (its own reflog names whatever ITS OWN true
startpoint was, e.g. `origin/main` or a raw SHA, essentially never a name
that also happens to resolve to an existing local branch by coincidence).

**Disclosed, unverified assumption.** This resolution mechanism assumes
the Workflow tool's own `isolation: 'worktree'` implementation creates
each task's worktree via a `-b <new-branch> <shared-branch-name>`-shaped
operation, naming the shared branch as a literal startpoint argument (the
only shape that writes the reflog entry this module reads) -- the same
"Open item, not resolved here" territory
references/execution-and-dispatch.md already flags for this exact tool's
own worktree-creation internals (its own cleanup-on-merge-back behavior).
If the real implementation instead uses a DETACHED HEAD checkout (no new
branch at all) or passes a raw commit SHA rather than the branch's own
name as the startpoint, this module's own `_current_branch`/
`_reflog_created_from` resolution fails cleanly (returns None, live-
verified against exactly this shape below) and this backstop silently
fails OPEN for that dispatch -- no protection, but also no false block --
rather than raising or guessing. This is the same "fail open when
unverifiable" posture this module's own Planned-ops text explicitly
requires for the ordinary sequential-fallback case (no worktree, no wave)
below; it is not a special case invented here.

**Fail-open/fail-closed asymmetry, disclosed explicitly.** This module
returns `{"decision": "deny", ...}` ONLY on a clean, fully-resolved,
confirmed mismatch (the shared branch's own current tip is genuinely not
an ancestor of this worktree's HEAD). Every other outcome -- the branch
name cannot be resolved at all (not a linked worktree, a detached HEAD, no
matching reflog entry, the resolved name is not an existing local branch),
or a `git merge-base`/`git rev-parse` call itself fails for any reason --
returns `{"decision": "warn", ...}`, never deny. This is the OPPOSITE
default from this module's own sibling
(`gitapex_check_task_bash_safety.py`, which fails CLOSED on any malformed
input or classification uncertainty, because that classifier's own job is
preventing a small set of genuinely dangerous actions). This module is
narrower in purpose -- "a backstop for the wave-dispatch case
specifically, not a general-purpose git-state gate" (this task's own
Planned ops, quoted) -- and must never block a legitimate sequential-
fallback dispatch (no worktree, no wave) that this same `branch-plan-task`
agent type also runs under, per design doc Decision 4's own portability
answer. A malformed/unparseable stdin payload is folded into this same
fail-open "warn" bucket for the identical reason, rather than treated as a
third, fail-closed case -- this module's only fail-closed output is the
one clean mismatch signal above.

Deliberately stdlib-only (json, re, subprocess), matching
check_task_bash_safety.sh's own sibling-script convention (no third-party
import) -- see that script's own header for why.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# A hang guard, not a budget: every git call this module makes is a plain,
# local, read-only plumbing command (symbolic-ref, reflog show, rev-parse,
# merge-base) against a worktree's own already-cloned object store -- none
# ever touches the network -- so a normal call completes in well under a
# second. Bounded anyway so a pathologically large reflog (or an
# unexpected hang in a corrupted repository) cannot stall the PreToolUse
# hook indefinitely; this module fails OPEN on a timeout like every other
# unresolvable-signal case, per this module's own docstring.
_GIT_TIMEOUT_SECONDS = 10.0

# The literal reflog subject git itself writes to a newly-created branch's
# own ref, naming the startpoint it was created from -- see this module's
# own docstring for the live verification (`git branch`/`checkout -b`/
# `worktree add -b` all write this identically).
_CREATED_FROM_RE = re.compile(r"^branch: Created from (.+)$")


def _run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run one read-only git plumbing command against CWD, returning
    (returncode, stdout). Every way this can fail to produce a real exit
    code (git missing from PATH, a timeout, a spawn OSError) folds into a
    non-zero returncode with empty stdout -- every caller in this module
    already treats any non-zero returncode as 'cannot resolve, fail
    open', so no separate exception path is needed here."""
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1, ""
    return completed.returncode, completed.stdout


def _current_branch(cwd: Path) -> str | None:
    """This worktree's own currently checked-out branch's short name, or
    None when HEAD is detached (no branch at all) or the git call itself
    fails."""
    code, out = _run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd)
    if code != 0:
        return None
    branch = out.strip()
    return branch or None


def _reflog_created_from(branch: str, cwd: Path) -> str | None:
    """The startpoint name git recorded when BRANCH was created, per its
    own `refs/heads/<branch>` reflog's `"branch: Created from <name>"`
    entry. Every reflog line is scanned, not only the last one: `git reflog
    show` prints newest-first, and every later operation on BRANCH (a
    `"branch: Reset to <x>"` from a `git branch -f`, an ordinary commit's
    own entry) pushes the creation entry further down the list -- so a scan
    that stopped at the first line would resolve nothing for any branch
    that has been used at all since it was created. None when the git call
    fails or no such entry exists (e.g. BRANCH predates this repository's
    own reflog, or was never created via a startpoint-naming operation at
    all).

    Splits OUT on a literal `"\\n"` rather than `str.splitlines()`: git's
    own subprocess text output (via `text=True`) is newline-delimited
    only, but `str.splitlines()` also treats several other Unicode
    line-boundary characters (`\\x1c`-`\\x1e`, `\\x0b`, `\\x0c`, `\\x85`,
    `\\u2028`, `\\u2029`) as separators -- found live via this module's own
    Hypothesis property test: a startpoint name containing one of those
    characters (e.g. a stray control character in an unusual ref name)
    would otherwise silently truncate the reflog subject line BEFORE the
    regex ever sees the rest of it, losing part of a genuine match instead
    of matching it (or, for a short enough name, losing the whole
    capture). The explicit `"\\n"` split avoids that ambiguity entirely."""
    code, out = _run_git(["reflog", "show", "--format=%gs", f"refs/heads/{branch}"], cwd)
    if code != 0:
        return None
    for line in out.split("\n"):
        match = _CREATED_FROM_RE.match(line.strip())
        if match:
            candidate = match.group(1).strip()
            return candidate or None
    return None


def _verify_local_branch(name: str, cwd: Path) -> str | None:
    """NAME's own current commit SHA, but ONLY when NAME resolves to an
    EXISTING LOCAL BRANCH (`refs/heads/<name>` specifically) -- never a
    tag, a remote-tracking ref, or a raw SHA, even though a plain `git
    rev-parse <name>` would happily resolve any of those too. This is the
    guard that makes the reflog-based resolution above safe against a
    worktree created for an unrelated purpose (see this module's own
    docstring): such a worktree's own reflog names whatever its true,
    unrelated startpoint was (often a remote-tracking ref like
    `origin/main`, which this check deliberately does NOT resolve as a
    local branch), so this verification step is what turns that mismatch
    into a clean 'cannot resolve' rather than a false positive."""
    code, out = _run_git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], cwd)
    if code != 0:
        return None
    sha = out.strip()
    return sha or None


def check_worktree_base(cwd: Path) -> dict[str, object]:
    """The actual precondition assertion: the shared plan branch's own
    current tip must be an ancestor of this worktree's own HEAD (i.e.
    `git merge-base HEAD <shared-branch>` equals `git rev-parse
    <shared-branch>`) -- otherwise this worktree was forked from a base
    the shared branch has since advanced past (issue #1508's own exact
    defect shape). Returns a `{"decision": ..., "reason": ...}` mapping;
    see this module's own docstring for the full deny/warn/allow
    contract."""
    branch = _current_branch(cwd)
    if branch is None:
        return {
            "decision": "warn",
            "reason": (
                "this worktree's own HEAD is not on a branch (detached, or the "
                "git call itself failed) -- cannot resolve the shared plan "
                "branch's own name from local state alone. Skipping the "
                "worktree-base precondition check and failing open. Expected "
                "for a sequential-fallback dispatch (no worktree, no wave); "
                "unexpected inside a genuine wave-dispatched worktree."
            ),
        }
    candidate = _reflog_created_from(branch, cwd)
    if not candidate:
        return {
            "decision": "warn",
            "reason": (
                f"this worktree's own branch '{branch}' has no 'branch: Created "
                "from <name>' reflog entry naming a startpoint -- cannot resolve "
                "the shared plan branch's own name from local state alone. "
                "Skipping the worktree-base precondition check and failing "
                "open. Expected for a sequential-fallback dispatch (no "
                "worktree, no wave), or a worktree not created by this skill's "
                "own Workflow-tool dispatch at all."
            ),
        }
    shared_sha = _verify_local_branch(candidate, cwd)
    if shared_sha is None:
        return {
            "decision": "warn",
            "reason": (
                f"this worktree's own branch '{branch}' was reportedly created "
                f"from '{candidate}', but '{candidate}' does not resolve to an "
                "existing local branch -- not trusted as the shared plan "
                "branch. Skipping the worktree-base precondition check and "
                "failing open. Expected when this worktree was created for a "
                "purpose unrelated to this skill's own wave dispatch."
            ),
        }
    code, out = _run_git(["merge-base", "HEAD", f"refs/heads/{candidate}"], cwd)
    if code != 0:
        return {
            "decision": "warn",
            "reason": (
                f"resolved the shared plan branch as '{candidate}' but 'git "
                f"merge-base HEAD refs/heads/{candidate}' itself failed (no "
                "common ancestor, or the git call errored) -- skipping the "
                "worktree-base precondition check and failing open rather than "
                "assuming a mismatch from an inconclusive signal."
            ),
        }
    merge_base_sha = out.strip()
    if merge_base_sha != shared_sha:
        return {
            "decision": "deny",
            "reason": (
                f"this task's own worktree was forked from a stale base of the "
                f"shared plan branch '{candidate}' (issue #1508's own defect "
                f"shape): merge-base(HEAD, {candidate}) = {merge_base_sha}, but "
                f"{candidate}'s own current tip = {shared_sha} -- {candidate} "
                "has advanced past this worktree's own fork point and is not "
                "an ancestor of this worktree's HEAD. Re-dispatch this task "
                f"from a fresh worktree forked from {candidate}'s current tip "
                f"({shared_sha}) instead of continuing from a stale base"
            ),
        }
    return {
        "decision": "allow",
        "reason": f"this worktree's own fork point matches '{candidate}'s current tip ({shared_sha})",
    }


def _resolve_cwd(payload: dict[str, object]) -> Path:
    """The PreToolUse hook payload's own `cwd` field when it names a real
    directory (the task's own worktree root, per Claude Code's documented
    hook input schema); this process's own working directory otherwise --
    matching gitapex_check_task_full_verification.py's own identical
    helper for its sibling SubagentStop hook."""
    raw = payload.get("cwd")
    if isinstance(raw, str) and raw:
        candidate = Path(raw)
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def main() -> int:
    """CLI entry point: read the PreToolUse hook payload from stdin, print
    a `{"decision": ...}` JSON verdict to stdout, and always exit 0 --
    check_task_bash_safety.sh, not this process's own exit code, is what
    turns a "deny" into an actual PreToolUse block, exactly as it already
    does for gitapex_check_task_bash_safety.py's own sibling call."""
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(
            json.dumps(
                {
                    "decision": "warn",
                    "reason": "the tool-call payload on stdin could not be parsed as JSON -- "
                    "skipping the worktree-base precondition check and failing open.",
                }
            )
        )
        return 0

    if not isinstance(payload, dict):
        print(
            json.dumps(
                {
                    "decision": "warn",
                    "reason": "the tool-call payload on stdin is not a JSON object -- "
                    "skipping the worktree-base precondition check and failing open.",
                }
            )
        )
        return 0

    tool_name = payload.get("tool_name")
    if tool_name != "Bash":
        print(json.dumps({"decision": "allow", "reason": "not a Bash tool call"}))
        return 0

    cwd = _resolve_cwd(payload)
    print(json.dumps(check_worktree_base(cwd)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

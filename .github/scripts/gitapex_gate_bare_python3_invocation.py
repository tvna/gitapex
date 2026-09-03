#!/usr/bin/env python3
"""CI gate: every `.github/scripts/*.py` invocation from a GitHub Actions
workflow `run:` step must go through `uv run`, never bare `python3`.

Issue #1035 (refs #1024/#1031's whole-branch review, finding I4 and its
underlying C1 root cause): a follow-up pydantic-CLI-arg-validation change
added `import pydantic` to `gitapex_compute_ruleset_verify_scope.py`,
whose only production caller (`ruleset-verify.yml`'s "Resolve scan scope
and source of truth" step) invoked it via bare `python3`, with no
dependency-install step at all -- the added import raised
`ModuleNotFoundError` live in CI (check run 93696199208) the same day it
merged. `.gitapex/ssot.json`'s own `local_invocation` field already
documented `uv run` as the convention for every registered gate
(live-verified against the base commit this issue branched from: 28
gate entries carried a `local_invocation`, and all 28 already started
with `uv run` -- 26 of them as `uv run --frozen python3 ...`, plus
`python-lint` as `uv run --locked ruff ...` and
`cyclomatic-complexity-floor` as `uv run --frozen xenon ...`); only the
CI `run:` steps for `.github/scripts/*.py` invocations themselves had
drifted from that convention. This gate closes that drift so a future PR
cannot silently reintroduce it.

Scope: parses each workflow file's YAML and scans every step's `run:`
string, line by line, for a `python3 .github/scripts/*.py` invocation
that is not immediately preceded (only `uv run` plus zero or more
`--flag`/`--flag=value` tokens allowed in between -- no shell operator, no
other command word) by `uv run` on the same line -- the same shape as the
manual `grep -rn "python3 \\.github/scripts" .github/workflows/*.yml |
grep -v "uv run"` this issue's own Facts section used to inventory the
original 24 call sites, scoped to parsed `run:` step text (not arbitrary
comment lines elsewhere in the file) to avoid false-flagging prose that
merely mentions the invocation shape without executing it. The adjacency
requirement (not merely "`uv run` appears somewhere on the line") closes
a defeat found in review: `uv run --frozen true && python3
.github/scripts/gate.py` would otherwise read as covered, since a plain
same-line substring check cannot tell "wraps this invocation" from
"appears elsewhere on this line, followed by an unrelated command".

A whole-line shell comment (the line's first non-whitespace character is
`#`) is skipped before matching, since a `python3 .github/scripts/*.py`
phrase inside one never executes -- code review found this class of false
positive live (a `# python3 .github/scripts/gate.py` documentation line).
A *trailing* comment after real code on the same line is not stripped
(see the residual-risk bullets below): telling a trailing comment apart
from a quoted string containing `#` needs real shell parsing, which is
out of scope here.

Residual risk, stated rather than hidden (issue #1035's own Acceptance
Criteria Map already names the general shape; the bullets below are this
implementation's own further-narrowed instances of it):

- A `run:` block that assembles the invocation dynamically -- through a
  shell variable, a multi-line `case` branch, or string concatenation --
  is not resolved by this line-level text match. No such dynamic form
  exists in this repository's real workflow files today, verified live at
  issue-creation time.
- The adjacency check is itself line-scoped: a backslash-continued `uv
  run --frozen` on one physical line followed by `python3
  .github/scripts/gate.py` on the next (a legitimate backslash
  line-continuation, not a dynamic invocation) is not recognized as
  wrapped and would false-positive as bare. Not observed in any of this
  repository's real call sites today (every one keeps `uv run ... python3
  ... script.py` on one physical line), so accepted as a known gap rather
  than joining continuation lines before matching.
- A *trailing* comment (real code earlier on the line, a comment after
  it) is not stripped before matching. A bare `python3 .github/scripts/*.py`
  phrase inside such a trailing comment (e.g. `uv run --frozen python3
  .github/scripts/real.py  # see also python3 .github/scripts/fake.py`)
  is indistinguishable from a real invocation and would be flagged the
  same way -- the mirror image of the whole-line-comment case this
  revision closes, left open because distinguishing "trailing comment"
  from "real code after a `#` that is part of a quoted string" needs real
  shell parsing.

Usage:
    uv run --frozen python3 .github/scripts/gitapex_gate_bare_python3_invocation.py [workflows_dir] [hooks_dir] [ssot_path]

Exit codes:
    0  every `.github/scripts/*.py` invocation found in a `run:` step uses
       `uv run`, and every `hooks/*.sh` shell-variable-indirected
       invocation (see below) is likewise clean.
    1  a bare `python3 .github/scripts/*.py` invocation was found (in a
       workflow `run:` step or, indirected through a shell variable, in a
       `hooks/*.sh` file), a bare `hooks/*.sh` invocation of a registered
       `hooks/*.py` target whose own gate requires a third-party Python
       package was found, OR the scan could not be performed
       (missing/unreadable directory, no workflow files, a file that will
       not decode, or a file whose YAML does not parse to the expected
       `jobs: {...: {steps: [...]}}` shape) -- "nothing was scanned" and
       "everything scanned was clean" are different claims, and only one
       of them is ever true, so the former is reported as a finding
       rather than sharing the latter's exit code (matching
       `gitapex_scan_unpinned_actions.py`'s own fail-closed rationale,
       issue #848).

Issue #1446 Item 2 (original introduction) / issue #1697 (HARD-FAIL
promotion): `hooks/*.sh` almost never invokes a `.github/scripts/*.py`
gate directly on the same line the way a workflow `run:` step does. It
instead assigns the path to a shell variable on one line and invokes
`python3 "$var"` several lines later (e.g.
`hooks/check-pr-skill-audit-disclosure.sh`'s `full_gate` variable), which
`find_bare_invocations`'s same-line regex cannot see.
`find_hooks_shell_indirected_invocations` closes that blind spot with a
two-step static scan of `hooks/*.sh`, scoped to the direct single-
assignment-then-invocation shape this repository's real `hooks/*.sh`
files actually use (no aliasing, no string concatenation, no multi-hop
reassignment tracing).

Originally WARNING-tier (report-only, never flipped the exit code) on the
theory that a `hooks/*.py` sibling script is stdlib-only, self-contained,
and bare-invoked by design (`docs/repository-layout.md`). Issue #1697
found the gap in that theory live: `hooks/gitapex_check_python_precondition.py`
is itself stdlib-only, but its own job is probing whether a *third-party*
package (pydantic, for the `skill-audit-disclosure` gate) is importable --
and `hooks/check-pr-skill-audit-disclosure.sh`'s own bare `python3
"$precondition_script"` invocation of it inherited the exact PATH-
dependent false-deny this whole gate exists to prevent, invisible to this
scan because it targeted a `hooks/*.py` file, a class this scan
categorically never tracked. `load_python_dependent_hook_script_names`
closes that gap by reading `.gitapex/ssot.json` directly: a `hooks/*.py`
path is tracked (and now hard-fails, same as `.github/scripts/*.py`) if
and only if it is registered under a gate whose own
`preconditions.requires_python_packages` is non-empty -- i.e. a `hooks/*.py`
file that genuinely needs a third-party-dependent, deterministically-
resolved interpreter, not every `hooks/*.py` sibling indiscriminately. A
`hooks/*.py` variable NOT so registered is still never tracked, so it can
never be flagged -- the original stdlib-only-and-bare-by-design theory
still holds for every such file.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import yaml

WORKFLOWS_DIR = pathlib.Path(".github/workflows")
HOOKS_DIR = pathlib.Path("hooks")
SSOT_PATH = pathlib.Path(".gitapex/ssot.json")

# `uv run`, optionally followed by long-form flags (`--frozen`,
# `--flag=value` -- the only shapes this repository's real call sites use;
# a space-separated flag value is deliberately not supported, since
# supporting it risks the flag-value regex swallowing the literal word
# "python3" itself), immediately preceding a `python3 ...` invocation.
# Shared by both the workflow same-line scan and the hooks/*.sh
# shell-variable-indirected scan below, so the two adjacency checks stay
# in lockstep rather than drifting apart.
#
# `-[\w-]+`, not `-{1,2}[\w-]+`: the earlier two-hyphen-then-word-class
# form let `-{1,2}` and the following `[\w-]+` both claim a `-` character,
# so a run of N `--flag=value` tokens had 2**N equivalent parses and the
# regex engine exhausted them all on a non-matching tail -- catastrophic
# backtracking (issue #1446 review: reproduced live, a 25-flag line took
# over 40s against this exact repo's own compiled pattern, up from ~1ms at
# 10 flags). Requiring exactly one leading `-` and letting `[\w-]+` own
# every character after it (a second literal `-` included) removes the
# overlap -- every character belongs to exactly one sub-pattern, so there
# is only one parse to try. Matches the identical set of real flag shapes
# (`-x`, `--frozen`, `--flag=value`) with the same overall match span;
# verified byte-for-byte identical `.end()` against the old pattern for
# every real call site in this repository's own workflow files.
_UV_RUN_PREFIX = r"\buv\s+run(?:\s+-[\w-]+(?:=\S+)?)*\s+"

# A literal `python3 .github/scripts/<name>.py` invocation anywhere on a
# line. Deliberately loose (no anchoring on line start) so it matches
# equally inside a plain `run:` line, a `|`-piped line, and an
# `xargs ... python3 script.py` line -- the three shapes this
# repository's 24 original call sites actually used.
_SCRIPT_INVOCATION_RE = re.compile(r"python3\s+\.github/scripts/\S+\.py")
# `_UV_RUN_PREFIX` immediately followed by a `python3 .github/scripts/*.py`
# invocation. A match's END position lands exactly on the wrapped
# invocation's own end (both patterns share the same `\.py` tail), so
# comparing end positions -- not just "does this pattern match somewhere on
# the line" -- is what proves `uv run` actually wraps a SPECIFIC invocation
# rather than merely co-occurring with it (e.g. in a trailing comment, or
# before an unrelated `&&`-joined command).
_UV_WRAPPED_INVOCATION_RE = re.compile(_UV_RUN_PREFIX + r"python3\s+\.github/scripts/\S+\.py")

# A shell variable assignment (`VARNAME=...` or `VARNAME="..."`, no space
# around `=` -- real bash assignment syntax) at the start of a line
# (allowing leading indentation). Captures the variable name (group 1)
# and the right-hand side (group 2) so the caller can check whether that
# right-hand side targets a `.github/scripts/*.py` path.
_SHELL_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
# A `.github/scripts/*.py` path appearing anywhere in an assignment's
# right-hand side (e.g. `"${repo_root}/.github/scripts/gate.py"`).
# Deliberately the same shape as `_SCRIPT_INVOCATION_RE` minus the
# `python3\s+` prefix, since here it is matched against an assignment's
# RHS, not an invocation.
_GITHUB_SCRIPTS_PATH_RE = re.compile(r"\.github/scripts/\S+\.py")
# A trailing shell comment: `#` at the very start of the (already-stripped)
# RHS, or preceded by whitespace. Applied to an assignment's RHS before
# `_GITHUB_SCRIPTS_PATH_RE` runs, so a `.github/scripts/*.py` path merely
# *mentioned in a comment* after the real value (e.g.
# `other_var="unrelated"  # see also .github/scripts/other_gate.py`) is
# never mistaken for the value itself -- found live in review: without
# this, that exact shape tracked `other_var` and reported a false-positive
# WARNING on its own later bare invocation. Crude, matching this module's
# own documented "no real shell parsing" scope (a literal `#` inside a
# quoted value is not distinguished from a real comment marker) -- not a
# gap this narrow WARNING-tier scan needs to close exactly.
_TRAILING_COMMENT_RE = re.compile(r"(?:^|\s)#")


def find_bare_invocations(workflows_dir: pathlib.Path = WORKFLOWS_DIR) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each bare `python3
    .github/scripts/*.py` invocation found in a workflow `run:` step.
    Empty list means every such invocation in the scanned files goes
    through `uv run`."""
    findings: list[tuple[str, int, str]] = []
    if not workflows_dir.is_dir():
        findings.append((str(workflows_dir), 0, "workflow directory not found, cannot verify"))
        return findings
    workflows = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    if not workflows:
        findings.append((str(workflows_dir), 0, "no *.yml or *.yaml workflow files found, cannot verify"))
        return findings
    for workflow in workflows:
        findings.extend(_scan_workflow(workflow))
    return findings


def _scan_workflow(workflow: pathlib.Path) -> list[tuple[str, int, str]]:
    try:
        content = workflow.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Fail closed, not skip: a file that isn't valid text -- or that
        # became unreadable (permissions, deleted mid-scan) after glob()
        # discovered it -- can't be scanned for a `run:` block, so it
        # cannot be verified clean.
        return [(str(workflow), 0, f"could not decode as UTF-8, cannot verify: {exc}")]

    try:
        document = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return [(str(workflow), 0, f"could not parse as YAML, cannot verify: {exc}")]

    if not isinstance(document, dict):
        return [(str(workflow), 0, "workflow YAML did not parse to a mapping, cannot verify")]

    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [(str(workflow), 0, "workflow has no jobs: mapping, cannot verify")]

    findings: list[tuple[str, int, str]] = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            findings.append((str(workflow), 0, f"job {job_name!r} is not a mapping, cannot verify"))
            continue
        steps = job.get("steps")
        if steps is None:
            # A job with no steps at all (e.g. a reusable-workflow call
            # via `uses:` at the job level) has nothing to scan; that is
            # not the same as a malformed job, so it is not a finding.
            continue
        if not isinstance(steps, list):
            findings.append((str(workflow), 0, f"job {job_name!r} steps: is not a list, cannot verify"))
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            step_name = step.get("name", "<unnamed step>")
            for lineno, line in enumerate(run.splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    # A whole-line shell comment never executes, so a
                    # `python3 .github/scripts/*.py` phrase inside one is not
                    # a real invocation -- distinguishable from a genuinely
                    # unsupported shell form (a trailing comment after real
                    # code, a quoted string) without real shell parsing,
                    # since a comment's own leading `#` is unambiguous.
                    continue
                wrapped_ends = {m.end() for m in _UV_WRAPPED_INVOCATION_RE.finditer(line)}
                for match in _SCRIPT_INVOCATION_RE.finditer(line):
                    if match.end() in wrapped_ends:
                        continue
                    findings.append((f"{workflow} [{job_name}/{step_name}]", lineno, line.strip()))
    return findings


def load_python_dependent_hook_script_names(ssot_path: pathlib.Path = SSOT_PATH) -> frozenset[str]:
    """Return the basenames of every `hooks/*.py` file registered in
    `.gitapex/ssot.json` under a gate whose own
    `preconditions.requires_python_packages` is non-empty (issue #1697): a
    `hooks/*.sh` bare-`python3` invocation of one of these risks the exact
    PATH-dependent false-deny #1697 found (the calling shell's own ambient
    PATH may not resolve an interpreter that can import the third-party
    package that gate needs), the same reason a bare `python3
    .github/scripts/*.py` invocation is already a hard failure below.

    Degrades to an empty result (never raises) when the registry is
    missing, unreadable, or does not parse to the expected shape -- the
    caller then simply has no additional `hooks/*.py` targets to widen its
    existing `.github/scripts/*.py`-only scope with, rather than crashing
    this whole gate on an unreadable registry."""
    try:
        data = json.loads(ssot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    gates = data.get("gates")
    if not isinstance(gates, list):
        return frozenset()

    names: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        preconditions = gate.get("preconditions")
        packages = preconditions.get("requires_python_packages") if isinstance(preconditions, dict) else None
        if not isinstance(packages, list) or not packages:
            continue
        scripts = gate.get("script")
        if not isinstance(scripts, list):
            continue
        for script in scripts:
            if isinstance(script, str) and script.startswith("hooks/") and script.endswith(".py"):
                names.add(pathlib.PurePosixPath(script).name)
    return frozenset(names)


def find_hooks_shell_indirected_invocations(
    hooks_dir: pathlib.Path = HOOKS_DIR,
    hard_fail_hooks_py_names: frozenset[str] = frozenset(),
) -> list[tuple[str, int, str]]:
    """Return (file, line_number, line) for each `hooks/*.sh` bare
    `python3 "$var"` invocation (quoted or unquoted, `${var}` brace form
    or bare `$var`) of a shell variable whose own assignment targets
    either a `.github/scripts/*.py` path, or a `hooks/*.py` file named in
    `hard_fail_hooks_py_names` (issue #1697: a gate-registered `hooks/*.py`
    whose own gate declares a non-empty
    `preconditions.requires_python_packages` -- see
    `load_python_dependent_hook_script_names`). HARD-FAIL tier (issue
    #1697; formerly WARNING-only, see issue #1446's own original
    introduction): unlike `find_bare_invocations`, a missing or unreadable
    `hooks_dir` is simply nothing to check, not a fail-closed finding --
    there is no exit-code contract to protect on a directory this gate's
    own caller may legitimately not have. A `hooks/*.py` variable NOT
    named in `hard_fail_hooks_py_names` is still never tracked (those
    remain bare-invoked by design, per docs/repository-layout.md)."""
    findings: list[tuple[str, int, str]] = []
    if not hooks_dir.is_dir():
        return findings
    for hook in sorted(hooks_dir.glob("*.sh")):
        findings.extend(_scan_hook(hook, hard_fail_hooks_py_names))
    return findings


def _scan_hook(
    hook: pathlib.Path, hard_fail_hooks_py_names: frozenset[str] = frozenset()
) -> list[tuple[str, int, str]]:
    try:
        lines = hook.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        # No exit-code contract to protect here (see this function's own
        # caller docstring) -- a hook that cannot be read has no
        # reportable finding, not a hard failure of the scan itself.
        return []

    # A registered hooks/*.py target's own basename (e.g.
    # "gitapex_check_python_precondition.py") at the very end of an
    # assignment's right-hand side, after trailing-comment stripping and
    # quote trimming -- the real shape this repository's own hooks/*.sh
    # files use is always a `$script_dir/<name>.py`-style path, never a
    # literal `hooks/<name>.py` substring (that literal-substring shape is
    # what `_GITHUB_SCRIPTS_PATH_RE` matches for `.github/scripts/*.py`
    # instead, since those are always written relative to repo_root).
    hooks_py_target_re = None
    if hard_fail_hooks_py_names:
        hooks_py_target_re = re.compile(
            r"(?:" + "|".join(re.escape(name) for name in sorted(hard_fail_hooks_py_names)) + r")$"
        )

    # Pass 1: which variables get assigned a `.github/scripts/*.py` path,
    # or a registered `hooks/*.py` target, anywhere in this file. Whole-
    # file rather than "only assignments before the invocation line" --
    # the real shape this repository uses always assigns before invoking,
    # and tracking that ordering would add dataflow analysis this scan
    # deliberately does not attempt.
    tracked_vars: set[str] = set()
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        assignment = _SHELL_ASSIGNMENT_RE.match(line)
        if not assignment:
            continue
        rhs = assignment.group(2)
        comment = _TRAILING_COMMENT_RE.search(rhs)
        if comment:
            rhs = rhs[: comment.start()]
        rhs_trimmed = rhs.strip().strip('"').strip("'")
        if _GITHUB_SCRIPTS_PATH_RE.search(rhs) or (hooks_py_target_re and hooks_py_target_re.search(rhs_trimmed)):
            tracked_vars.add(assignment.group(1))

    if not tracked_vars:
        return []

    # Pass 2: for each tracked variable, find a bare `python3 "$var"` (or
    # unquoted `python3 $var`, or brace-wrapped `python3 "${var}"`)
    # invocation not immediately preceded by `uv run` -- the same
    # end-position-comparison technique `_scan_workflow` uses above,
    # rebuilt per variable name since the invoked name varies. The
    # optional `\{?`/`\}?` pair (found live in review: this repository's
    # own hooks/*.sh files already brace-wrap the variable at its
    # *assignment* site, e.g. `full_gate="${repo_root}/..."` -- the same
    # habit at the *invocation* site is an equally plausible shell idiom)
    # relies on the same backtracking `\b` already depends on for the
    # trailing `"?`: the engine can match the boundary right after the
    # variable name without consuming a trailing `}` or `"`, so adding the
    # brace pair does not require touching the boundary logic itself.
    findings: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        for varname in sorted(tracked_vars):
            var_ref = r'"?\$\{?' + re.escape(varname) + r'\}?"?\b'
            bare_re = re.compile(r"python3\s+" + var_ref)
            wrapped_re = re.compile(_UV_RUN_PREFIX + r"python3\s+" + var_ref)
            wrapped_ends = {m.end() for m in wrapped_re.finditer(line)}
            for match in bare_re.finditer(line):
                if match.end() in wrapped_ends:
                    continue
                findings.append((f"{hook} [${varname}]", lineno, line.strip()))
    return findings


def main() -> int:
    workflows_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOWS_DIR
    hooks_dir = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HOOKS_DIR
    ssot_path = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else SSOT_PATH

    findings = find_bare_invocations(workflows_dir)
    if findings:
        print("Bare `python3 .github/scripts/*.py` invocations, or workflows that could not be verified:")
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        exit_code = 1
    else:
        print("No bare `python3 .github/scripts/*.py` invocations found; every call site uses `uv run`.")
        exit_code = 0

    # HARD-FAIL tier (issue #1697; formerly WARNING-only under issue
    # #1446 Item 2 -- see find_hooks_shell_indirected_invocations's own
    # docstring for why that changed): a bare `python3 "$var"` of a
    # `.github/scripts/*.py` target, or of a registered `hooks/*.py`
    # target whose own gate declares a non-empty
    # `preconditions.requires_python_packages`, now fails this gate the
    # same way a workflow-level bare invocation always has.
    hard_fail_hooks_py_names = load_python_dependent_hook_script_names(ssot_path)
    hooks_findings = find_hooks_shell_indirected_invocations(hooks_dir, hard_fail_hooks_py_names)
    if hooks_findings:
        print(
            'Bare `python3 "$var"` invocations (hooks/*.sh) of a `.github/scripts/*.py` '
            "target, or of a hooks/*.py target whose own gate requires a third-party "
            "Python package:"
        )
        for path, lineno, line in hooks_findings:
            print(f"  {path}:{lineno}: {line}")
        exit_code = 1
    else:
        print("No hooks/*.sh shell-variable-indirected bare invocations found.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

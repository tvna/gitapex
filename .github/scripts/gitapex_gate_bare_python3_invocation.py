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

Residual risk, stated rather than hidden (issue #1035's own Acceptance
Criteria Map already names the general shape; the two bullets below are
this implementation's own further-narrowed instances of it):

- A `run:` block that assembles the invocation dynamically -- through a
  shell variable, a multi-line `case` branch, or string concatenation --
  is not resolved by this line-level text match. No such dynamic form
  exists in this repository's real workflow files today, verified live at
  issue-creation time.
- The adjacency check is itself line-scoped: a backslash-continued `uv run
  --frozen` on one physical line followed by `python3
  .github/scripts/gate.py` on the
  next (a legitimate backslash line-continuation, not a dynamic
  invocation) is not recognized as wrapped and would false-positive as
  bare. Not observed in any of this repository's real call sites today
  (every one keeps `uv run ... python3 ... script.py` on one physical
  line), so accepted as a known gap rather than joining continuation
  lines before matching.

Usage:
    uv run --frozen python3 .github/scripts/gitapex_gate_bare_python3_invocation.py [workflows_dir]

Exit codes:
    0  every `.github/scripts/*.py` invocation found in a `run:` step uses
       `uv run`.
    1  a bare `python3 .github/scripts/*.py` invocation was found, OR the
       scan could not be performed (missing/unreadable directory, no
       workflow files, a file that will not decode, or a file whose YAML
       does not parse to the expected `jobs: {...: {steps: [...]}}`
       shape) -- "nothing was scanned" and "everything scanned was clean"
       are different claims, and only one of them is ever true, so the
       former is reported as a finding rather than sharing the latter's
       exit code (matching `gitapex_scan_unpinned_actions.py`'s own
       fail-closed rationale, issue #848).
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

WORKFLOWS_DIR = pathlib.Path(".github/workflows")

# A literal `python3 .github/scripts/<name>.py` invocation anywhere on a
# line. Deliberately loose (no anchoring on line start) so it matches
# equally inside a plain `run:` line, a `|`-piped line, and an
# `xargs ... python3 script.py` line -- the three shapes this
# repository's 24 original call sites actually used.
_SCRIPT_INVOCATION_RE = re.compile(r"python3\s+\.github/scripts/\S+\.py")
# `uv run`, optionally followed by long-form flags (`--frozen`,
# `--flag=value` -- the only shapes this repository's real call sites use;
# a space-separated flag value is deliberately not supported, since
# supporting it risks the flag-value regex swallowing the literal word
# "python3" itself), immediately followed by a `python3 .github/scripts/*.py`
# invocation. A match's END position lands exactly on the wrapped
# invocation's own end (both patterns share the same `\.py` tail), so
# comparing end positions -- not just "does this pattern match somewhere on
# the line" -- is what proves `uv run` actually wraps a SPECIFIC invocation
# rather than merely co-occurring with it (e.g. in a trailing comment, or
# before an unrelated `&&`-joined command).
_UV_WRAPPED_INVOCATION_RE = re.compile(r"\buv\s+run(?:\s+-{1,2}[\w-]+(?:=\S+)?)*\s+python3\s+\.github/scripts/\S+\.py")


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
                wrapped_ends = {m.end() for m in _UV_WRAPPED_INVOCATION_RE.finditer(line)}
                for match in _SCRIPT_INVOCATION_RE.finditer(line):
                    if match.end() in wrapped_ends:
                        continue
                    findings.append((f"{workflow} [{job_name}/{step_name}]", lineno, line.strip()))
    return findings


def main() -> int:
    workflows_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOWS_DIR
    findings = find_bare_invocations(workflows_dir)
    if findings:
        print("Bare `python3 .github/scripts/*.py` invocations, or workflows that could not be verified:")
        for path, lineno, line in findings:
            print(f"  {path}:{lineno}: {line}")
        return 1
    print("No bare `python3 .github/scripts/*.py` invocations found; every call site uses `uv run`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

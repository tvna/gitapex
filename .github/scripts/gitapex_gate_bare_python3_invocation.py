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
documented `uv run --frozen python3 ...` as the convention for every
registered gate (live-verified during this issue's implementation: all 27
gate entries carrying that field already used it); only the CI `run:`
steps themselves had drifted from it. This gate closes that drift so a
future PR cannot silently reintroduce it.

Scope: parses each workflow file's YAML and scans every step's `run:`
string, line by line, for a `python3 .github/scripts/*.py` invocation not
paired with `uv run` on the same line -- the same shape as the manual
`grep -rn "python3 \\.github/scripts" .github/workflows/*.yml | grep -v
"uv run"` this issue's own Facts section used to inventory the original
24 call sites, scoped to parsed `run:` step text (not arbitrary comment
lines elsewhere in the file) to avoid false-flagging prose that merely
mentions the invocation shape without executing it.

Residual risk, stated rather than hidden (issue #1035's own Acceptance
Criteria Map already names this): a `run:` block that assembles the
invocation dynamically -- through a shell variable, a multi-line `case`
branch, or string concatenation -- is not resolved by this line-level
text match. That gap is accepted at this issue's scope: every call site
inventoried live against this repository's actual workflow files at
issue-creation time was a direct literal invocation, and a dynamic form
would be a new authoring pattern to catch in a follow-up, not a
known-missed case here.

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
# Word-boundary "uv run" so this never matches a coincidental
# substring (e.g. a path segment) -- though no such collision is known to
# exist in this repository's workflows today.
_UV_RUN_RE = re.compile(r"\buv\s+run\b")


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
        content = workflow.read_text()
    except UnicodeDecodeError as exc:
        # Fail closed, not skip: a file that isn't valid text can't be
        # scanned for a `run:` block, so it cannot be verified clean.
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
                if not _SCRIPT_INVOCATION_RE.search(line):
                    continue
                if _UV_RUN_RE.search(line):
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

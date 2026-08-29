#!/usr/bin/env python3
"""Cheap, local, no-live-model-call check that every committed eval YAML file
parses as YAML (issue #527, derived from retrospective issue #473).

Issue #473 found that an unquoted YAML scalar containing a colon
(``description: attack surface: OK``) broke parsing of the *entire*
``evals/vetting-attack-surface/eval.yaml`` file -- no task in that suite
could load. The identical mistake then recurred in a separate task file in
the same PR cycle, and was only self-caught by a manual `yaml.safe_load`
pass before pushing, not by any gate. `skill-eval-gate.yml`'s own
`gitapex_run_eval_suite.py` call already surfaces a parse error eventually
(via `gitapex_run_ablation.load_yaml_mapping`), but only after that
workflow's `ANTHROPIC_API_KEY` preflight and `npm install -g
@anthropic-ai/claude-code` step -- so a PR touching only a broken eval YAML
file, in an environment with no live-model credential configured, never
sees the real syntax error at all, only a misleading missing-secret
failure. This module is the cheap, credential-free, syntax-only check that
runs before any of that.

Deliberately syntax-only, not schema validation: this checks that each
file parses as YAML at all (`yaml.safe_load` raising no `yaml.YAMLError`),
never that the parsed content is a well-formed eval suite or task fixture
(that deeper, already-existing check lives in
`gitapex_run_ablation.load_yaml_mapping` and
`gitapex_run_eval_suite.load_eval_suite`/`load_task_fixture`, exercised
once a suite actually runs). A file that parses to a YAML scalar, list, or
`null` instead of the expected mapping is not flagged here -- see issue
#527's own stated residual risk and non-goals (fixture construct-validity
is `gitapex_lint_fixture_assertions.py`'s separate, already-tracked scope).

`find_invalid_yaml_files()` sweeps every committed suite in one pass
(``evals/*/eval.yaml`` and ``evals/*/tasks/*.yaml``, repo-root-relative)
rather than requiring a caller-supplied "touched files" list: it is a
strict superset of "touched files only" (every touched file is a subset of
every committed file), so it cannot under-cover the criterion, and it
needs no new touched-path plumbing alongside `skill-eval-gate.yml`'s own
existing diff-based skill detection. This mirrors this repository's own
established sibling-gate pattern for cross-registry sweeps enforced solely
by a pytest test with no dedicated CI workflow step (e.g.
`gitapex_gate_skill_eval_yaml_parity.py`, issue #928) -- registered in
`.gitapex/ssot.json` with `planes: ["ci", "local"]`, picked up by
`test.yml`'s already-required pytest job and by the pre-push
`local-preflight` hook (`gitapex_gate_local_preflight.py`) with no
separate `.pre-commit-config.yaml` entry needed.

Usage (``uv run --frozen``, not a bare ``python3`` invocation -- this file
imports PyYAML directly)::

    uv run --frozen python3 evals/scripts/gitapex_validate_eval_yaml.py

Exit codes:
    0  Every matched file parses as YAML.
    1  At least one matched file failed to read or parse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Repo-root-relative glob patterns this gate sweeps. Matches
#: `skill-eval-gate.yml`'s own committed-suite enumeration
#: (`evals/*/eval.yaml`) plus each suite's own task-fixture directory --
#: `evals/scripts/` itself never matches either pattern (it holds shared
#: `.py` helpers, no `eval.yaml` and no `tasks/` subdirectory of its own),
#: so no separate exclusion is needed the way
#: `gitapex_gate_skill_eval_yaml_parity.py` requires one for its own,
#: differently-shaped glob.
_EVAL_YAML_GLOB = "evals/*/eval.yaml"
_TASK_YAML_GLOB = "evals/*/tasks/*.yaml"


def find_yaml_files(root: Path = REPO_ROOT) -> list[Path]:
    """Return the sorted, deduped list of every eval-suite YAML file under
    `root` (`evals/*/eval.yaml` and `evals/*/tasks/*.yaml`)."""
    matched = set(root.glob(_EVAL_YAML_GLOB)) | set(root.glob(_TASK_YAML_GLOB))
    return sorted(matched)


def find_invalid_yaml_files(root: Path = REPO_ROOT) -> list[tuple[Path, str]]:
    """Return `(path, error message)` for every file `find_yaml_files(root)`
    finds that is unreadable or fails to parse as YAML. Every matched file
    is checked -- a parse failure in one file never stops the sweep, so a
    PR that breaks two files sees both reported at once, not one at a time
    across two round-trips."""
    failures: list[tuple[Path, str]] = []
    for path in find_yaml_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append((path, f"cannot read {path}: {exc}"))
            continue
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            failures.append((path, f"invalid YAML in {path}: {exc}"))
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: gitapex_validate_eval_yaml.py (no arguments)", file=sys.stderr)
        return 2

    failures = find_invalid_yaml_files()
    for _path, message in failures:
        print(f"error: {message}", file=sys.stderr)
    if failures:
        print(f"{len(failures)} eval YAML file(s) failed to parse", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

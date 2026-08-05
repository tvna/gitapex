# pytest CI performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut pytest's CI wall clock via `pytest-xdist` parallelization, and give contributors a fast local loop via a `slow` marker on subprocess-spawning tests.

**Architecture:** Both changes live entirely in `pyproject.toml`'s `[tool.pytest.ini_options]` (`addopts`, `markers`) plus a `pytestmark` line in three test modules. `.github/workflows/test.yml` is untouched — its existing `uv run --frozen pytest --cov-report=xml --cov-report=json` invocation picks up both changes automatically.

**Tech Stack:** Python 3.12, pytest 8.x, pytest-cov, pytest-xdist (new), uv.

## Global Constraints

- Dev dependency version pins follow this repo's existing convention: a bare lower bound (`>=X.Y`) unless a comment states a reason for an upper bound (see `pyproject.toml`'s `ruff`/`radon`/`xenon` entries for the upper-bound-with-reason pattern; `pytest`/`pytest-cov`/`pyyaml`/etc. show the plain lower-bound pattern this task follows).
- `uv run --frozen ...` is how CI and this plan invoke pytest — `uv.lock` must be regenerated (`uv lock`, no `--frozen`) and committed alongside any `pyproject.toml` dependency change, or `--frozen` runs will fail on a stale lock.
- Full-suite pass count must stay 2677 after every task (no test is deleted, skipped, or newly failing).
- Coverage totals (currently 127 lines missed / 99% per `coverage.json`) must stay unchanged by Task 1 — xdist must not change *what* is covered, only how long it takes.

---

### Task 1: Parallelize pytest with `pytest-xdist -n auto`

**Files:**
- Modify: `pyproject.toml` — `[dependency-groups].dev` list (currently starts at line 9) and `[tool.pytest.ini_options].addopts` (line 307)
- Modify: `uv.lock` (regenerated, not hand-edited)

**Interfaces:**
- Consumes: nothing from other tasks (first task).
- Produces: `pytest -n auto` is now the default for every `pytest`/`uv run --frozen pytest` invocation in this repo (local and CI) — Task 2 builds on top of this same `addopts` string.

- [ ] **Step 1: Add `pytest-xdist` to dev dependencies**

In `pyproject.toml`, inside `[dependency-groups].dev` (the list starting at line 9), add a new entry immediately after the existing `"pytest-cov>=5.0",` line:

```toml
    "pytest-cov>=5.0",
    "pytest-xdist>=3.6",
```

- [ ] **Step 2: Regenerate the lockfile**

Run: `uv lock`
Expected: exits 0; `git diff uv.lock` shows `pytest-xdist` and its transitive deps (`execnet` at minimum) added, no unrelated package changes.

- [ ] **Step 3: Add `-n auto` to `addopts`**

In `pyproject.toml`, `[tool.pytest.ini_options]` (line 304), change the `addopts` line (line 307) from:

```toml
addopts = "--cov=.github/scripts --cov=skills/battle-testing-a-skill/scripts --cov=skills/scorer-gated-skill-edits/scripts --cov=skills/evaluating-skill-quality/scripts --cov=skills/auditing-agent-product-scope/scripts --cov=skills/setup-gitapex-toolchain/scripts --cov=skills/evaluating-deterministic-gate-quality/scripts --cov=evals/scripts --cov=hooks --cov-report=term-missing"
```

to (only the trailing ` -n auto` is new):

```toml
addopts = "--cov=.github/scripts --cov=skills/battle-testing-a-skill/scripts --cov=skills/scorer-gated-skill-edits/scripts --cov=skills/evaluating-skill-quality/scripts --cov=skills/auditing-agent-product-scope/scripts --cov=skills/setup-gitapex-toolchain/scripts --cov=skills/evaluating-deterministic-gate-quality/scripts --cov=evals/scripts --cov=hooks --cov-report=term-missing -n auto"
```

- [ ] **Step 4: Run the full suite and verify it's green and faster**

Run: `time uv run --frozen pytest --cov-report=xml --cov-report=json`
Expected: `2677 passed` in the output; wall clock (`real` time) noticeably under the pre-change baseline of ~35s (a `gw0`/`gw1`/... worker line prefix or a `4 workers` line in pytest's own summary confirms xdist is active — exact worker count depends on the host's CPU count).

- [ ] **Step 5: Verify coverage totals are unchanged**

Run: `git diff --stat coverage.json coverage.xml` (these are gitignored build outputs, not tracked — instead diff the printed `TOTAL` line)
Run: `uv run --frozen pytest --cov-report=term-missing 2>&1 | grep TOTAL`
Expected: `TOTAL   11324   127    99%` (same numbers as the pre-change baseline recorded in the design doc — if they differ, stop and investigate before continuing; a coverage regression here means a worker crashed silently or a test became order-dependent).

- [ ] **Step 6: Run the two downstream CI gates locally against the fresh coverage.json**

Run: `uv run --frozen python3 .github/scripts/gitapex_gate_evals_scripts_coverage.py --coverage-json coverage.json`
Expected: exits 0, no per-file floor violation reported.

Run: `uv run --frozen xenon --max-absolute E --max-modules B --max-average A --exclude "apm_modules/*,skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py" .`
Expected: exits 0 (this step is unaffected by the pytest change but confirms nothing else on the branch broke it).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
perf(pytest): parallelize with pytest-xdist -n auto

Refs #770. Cuts the local suite from ~35s to ~15s (measured with the
same --cov-report flags CI passes); coverage totals are unchanged
since pytest-cov merges per-worker data automatically.
EOF
)"
```

---

### Task 2: Add a `slow` marker for subprocess-spawning tests

**Files:**
- Modify: `pyproject.toml` — `[tool.pytest.ini_options]` (`addopts`, new `markers` key)
- Modify: `tests/test_gitapex_skill_audit_gate_diff_step_shell.py` (imports pytest already, line 27)
- Modify: `hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py` (imports pytest already, line 33)
- Modify: `tests/test_gitapex_session_start_hook_shell.py` (does **not** import pytest yet — must be added)

**Interfaces:**
- Consumes: the `addopts` string as left by Task 1, Step 3.
- Produces: `pytest -m "not slow"` now excludes the ~44 tests in the three files above; `pytest -m slow` selects only them; plain `pytest` (CI's invocation) is unaffected — it runs every test regardless of marker.

- [ ] **Step 1: Register the `slow` marker and enable `--strict-markers`**

In `pyproject.toml`, `[tool.pytest.ini_options]`, append ` --strict-markers` to the end of the `addopts` string from Task 1 Step 3 (now ending in `-n auto --strict-markers`), and add a new `markers` key immediately below the `addopts` line:

```toml
markers = [
    "slow: spawns a real subprocess (git/uv/shell); skip locally with -m \"not slow\" for a fast dev loop",
]
```

- [ ] **Step 2: Verify `--strict-markers` doesn't break collection**

Run: `uv run --frozen pytest --collect-only -q 2>&1 | tail -5`
Expected: `2677 tests collected` (or similar), no `PytestUnknownMarkWarning` / `Unknown marker` errors. If an error appears, it means some test uses an undeclared custom marker — find it with `grep -rn "@pytest.mark\." tests hooks skills | grep -v parametrize | grep -v skipif` and either register it in `markers` too or fix the typo before continuing.

- [ ] **Step 3: Mark `tests/test_gitapex_skill_audit_gate_diff_step_shell.py` as slow**

The file already has `import pytest` at line 27 and module-level constants at lines 30-31 (`REPO_ROOT`, `WORKFLOW_PATH`). Add a `pytestmark` line right after those constants, before the first fixture:

```python
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-audit-gate.yml"

pytestmark = pytest.mark.slow
```

- [ ] **Step 4: Mark `hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py` as slow**

The file already has `import pytest` at line 33 and module-level constants at lines 35-38 (`SCRIPT`, `CHECKER`, `ACM_CHECKER`, `REPO_ROOT`). Add a `pytestmark` line right after those constants:

```python
SCRIPT = Path(__file__).parent / "check-pr-issue-acm-disclosure.sh"
CHECKER = Path(__file__).parent / "gitapex_check_pr_issue_acm_disclosure.py"
ACM_CHECKER = Path(__file__).parent / "gitapex_check_acm_present_or_waiver.py"
REPO_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.slow
```

- [ ] **Step 5: Add `pytest` import and mark `tests/test_gitapex_session_start_hook_shell.py` as slow**

This file has no `import pytest` today. Change its import block (currently lines 1-7) from:

```python
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"
```

to:

```python
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"

pytestmark = pytest.mark.slow
```

- [ ] **Step 6: Verify the fast local loop excludes exactly the marked tests**

Run: `uv run --frozen pytest -m "not slow" --collect-only -q 2>&1 | tail -3`
Expected: a count strictly less than 2677 (the three files' tests excluded).

Run: `uv run --frozen pytest -m "slow" --collect-only -q 2>&1 | tail -3`
Expected: the complementary count — the two collect-only counts must sum to exactly 2677. Cross-check the exact number against `uv run --frozen pytest --collect-only -q tests/test_gitapex_skill_audit_gate_diff_step_shell.py hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py tests/test_gitapex_session_start_hook_shell.py 2>&1 | tail -3` to confirm the "slow" count matches these three files' own test count.

- [ ] **Step 7: Run the full suite (CI's own invocation) and confirm nothing regressed**

Run: `uv run --frozen pytest --cov-report=xml --cov-report=json`
Expected: `2677 passed` (the marker must not have accidentally skipped anything from the default, unfiltered run — CI never passes `-m`).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tests/test_gitapex_skill_audit_gate_diff_step_shell.py \
  hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py \
  tests/test_gitapex_session_start_hook_shell.py
git commit -m "$(cat <<'EOF'
test(pytest): add a slow marker for subprocess-spawning tests

Refs #770. -m "not slow" skips the ~44 tests that spawn real git/uv/
shell subprocesses for a fast local loop; CI's own invocation carries
no -m flag, so the full suite (slow tests included) still gates merges
unchanged.
EOF
)"
```

---

## Self-review notes

- **Spec coverage:** Decision 1 (xdist, no CI matrix) → Task 1. Decision 2 (`-n auto`) → Task 1 Step 3. Decision 3 (`slow` marker by mechanism, not duration) → Task 2. Decision 4 (workflow file untouched) → no task modifies `.github/workflows/test.yml`, confirmed by omission. Non-goals (no CI split, no timeout change) → nothing in either task touches those.
- **Placeholder scan:** no TBD/TODO; every step shows literal code/commands.
- **Type/name consistency:** `slow` marker name and `-m "not slow"` spelling match between the design doc, Task 2 Step 1's `markers` registration, and Steps 3-6's usage.

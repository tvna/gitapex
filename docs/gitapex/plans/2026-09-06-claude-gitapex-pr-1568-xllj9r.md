# Branch Plan: local patch-coverage precheck

Issue: https://github.com/tvna/gitapex/issues/1568
Branch: `claude/gitapex-pr-1568-xllj9r`

## Acceptance Criteria Map

(Re-verified by `planning-a-branch-from-an-issue` this session; full text
and re-verification rationale posted to issue #1568's own body.)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| [from #1493] coverage-combine 0% coverage CI failure | A brand-new checker script shipped with 0% direct test coverage against the repo 90% floor, caught only after a full CI run. | Same engine as #1509 (below); a brand-new file's own 0% floor is a special case satisfied automatically once the diff-added-line engine lands. | Regression test: a brand-new untested script fixture is detected as a violation. | none identified |
| [from #1509] Wave-1 patch-coverage gap | New functions can land with undercovered lines only caught after a CI/Codecov round-trip. | Base spec: a pre-push/CI check running the test suite with coverage and comparing new/changed lines against the merge-base with origin/main -- a local equivalent of Codecov's own PR-level patch-coverage report. | Regression test: reintroduce the original defect shape, confirm it fails, then passes once fixed. | none identified |
| [from #1539] Codecov patch-coverage gap in a gate script | Codecov flagged 6 uncovered lines/branches among diff-added lines in a new gate script; per-added-line granularity was not checked locally before push. | Same engine, diff-added-line granularity (not whole-file aggregate). | Regression test: a diff adding an uncovered line inside an otherwise well-tested file is detected. | Needs a coverage-run artifact from the same or a very recent local test run; resolved this session by running only the diff-changed files' own corresponding test files rather than depending on a stale artifact -- see Task 1 below. |
| [from #1555] codecov/patch flagged an unreachable branch and two untested branches | codecov/patch flagged a dead branch plus two untested branches with no local pre-push equivalent. | Same engine. The unreachable-branch finding is explicitly carried forward as unsolved by any coverage-diff engine -- needs a waiver or dead-code removal, out of scope for this gate. | Regression test: an added line with zero covering test executions is detected; waiver comment clears it. | Statement-level executed/missing comparison cannot detect a partially-taken branch -- disclosed, not solved. |
| [from #1703] codecov patch-coverage gap on initial push | First push landed below the CI codecov patch-coverage threshold, caught only after the push. | Same engine. | Regression test: reintroduce the gap shape, confirm detection. | none identified |
| [from #1718] Codecov patch-coverage gap in a gate closed post-open | An author-chosen ad hoc `pytest --cov=<target>` run did not use the same patch-coverage denominator Codecov computes against the actual diff. | Register the new check as a `.gitapex/ssot.json` entry with `planes: ["ci", "local"]` so `gitapex_gate_local_preflight.py`'s existing registry-driven runner picks it up (no new pre-push plumbing). Calibrate against Codecov's documented algorithm/a real `codecov/patch` report. | Regression test as above; additionally confirm output agrees with a real `codecov/patch` result on this PR's own sample diff. | No repo-side authoritative denominator to calibrate against (Codecov integration here runs with `fail_ci_if_error: false`, no patch-coverage threshold of its own) -- disclosed, verified against one real diff's agreement rather than claiming exact parity. |
| [from #1862] Codecov patch-coverage gap, no local pre-push equivalent, recurred at 95.91%->96.04% | Second occurrence in the same PR cycle; accepted as pre-existing/disclosed defensive branches rather than fixed further. | Same engine as #1509. This is a concrete acceptance-case instance for the threshold behavior: 100% of diff-added, coverage-measurable lines, with an inline `# patch-coverage: WAIVED: <reason>` waiver for an accepted case like this one -- matching this repo's existing gate convention (`gitapex_gate_function_body_test_coverage.py`) rather than a partial-percentage floor. | Regression test: a waived line does not fail the gate; an unwaived one does. | none identified |

## Task 1: Add the diff-added-line patch-coverage gate

Single-task decomposition (degenerate case, SKILL.md's own explicitly
sanctioned shape): all 7 ACM rows above are satisfied by one engine, per
the issue's own stated Resolution order. No file-ownership or
interface-dependency edge to compute against any sibling task.

- Files:
  - New: `.github/scripts/gitapex_gate_patch_coverage.py`
  - New: `tests/test_gitapex_gate_patch_coverage.py` (+
    `tests/test_gitapex_gate_patch_coverage_properties.py` if warranted)
  - New: `.github/workflows/patch-coverage-gate.yml`
  - Edit: `.gitapex/ssot.json` (new gate entry, `id: "patch-coverage"`)
- Design (confirmed this session via live measurement + repo-owner
  decision, recorded in issue #1568's own re-verification comment):
  1. Reuse `parse_added_lines` (byte-for-byte copy, matching the sibling
     gates' own documented convention) to get `{path: added line
     numbers}` from a unified diff read on stdin
     (`gitapex_run_base_diff.py -- '*.py'` as `local_stdin`/CI producer,
     matching `function-body-test-coverage`'s own wiring).
  2. Scope: `pyproject.toml`'s `[tool.coverage.run] source` directories
     (reuse `gitapex_gate_evals_scripts_coverage.py`'s
     `read_coverage_sources` pattern), excluding `test_*.py`/`conftest.py`.
  3. For each in-scope file with added lines, resolve its stem and the
     corresponding test file(s) (`tests/test_{stem}.py`,
     `tests/test_{stem}_properties.py` -- same convention
     `gitapex_gate_function_body_test_coverage.py` already uses).
  4. Run `uv run --frozen pytest <union of resolved test files>
     --cov=<in-scope source dirs> --cov-report=json:<tmp>` as a
     subprocess (NOT the full suite -- measured 17s for a 1-file change
     vs. 3m49s for the full suite in this environment; repo owner
     confirmed this approach over a full-suite rerun or a stale-artifact
     dependency).
  5. For each in-scope file: `statements = executed_lines | missing_lines`
     from the coverage.json entry; `denom = added_lines & statements`;
     `covered = denom & executed_lines`; `uncovered = denom - covered`,
     minus any line carrying an inline `# patch-coverage: WAIVED:
     <reason>` comment (tokenize-based, matching sibling gates'
     `_waived_lines`).
  6. Any unwaived `uncovered` line is a violation. No test file resolved
     for a file with added lines (e.g. a brand-new file with zero tests)
     means every added line in `statements` is uncovered by definition --
     satisfies ACM row #1493 automatically.
  7. Exit codes: 0 clean, 1 violation found, 2 scan untrusted (diff
     unparseable, pytest/coverage subprocess failed, coverage.json
     malformed, or an in-scope file with added lines has no matching
     coverage.json entry at all).
  8. CI wiring: a dedicated `patch-coverage-gate.yml` workflow (matching
     `function-body-test-coverage-gate.yml`'s own shape: `pull_request`
     `[opened, synchronize, reopened]`, `fetch-depth: '0'`, merge-base
     diff via `git merge-base`), not the shared `coverage-combine` job --
     this gate needs its own scoped pytest subprocess (step 4 above), not
     the full-suite `coverage.json` that job already produces, so there
     is no reuse to gain from folding it in there.
- Waiver: `# patch-coverage: WAIVED: <reason>`, tokenize-matched, honoring
  the same non-whitespace-reason-required convention as sibling gates.
- Steps:
  1. Implement `gitapex_gate_patch_coverage.py` per the design above.
  2. Add regression tests: (a) a brand-new file with an uncovered
     function is detected (ACM #1493/#1509); (b) an existing well-tested
     file with one added, uncovered line is detected while the rest of
     the file's pre-existing coverage is unaffected (ACM #1539/#1703);
     (c) a waived line does not fail the gate, an unwaived one does (ACM
     #1862); (d) a defeat-test: construct an input built to defeat this
     gate's own detection logic (e.g. a line that is technically
     "executed" via an unrelated test import, or a diff shaped to look
     like it adds lines to a file with no coverage.json entry) and
     confirm the gate still reports correctly rather than silently
     passing.
  3. Add `.github/workflows/patch-coverage-gate.yml`.
  4. Register the gate in `.gitapex/ssot.json`
     (`planes: ["ci", "local"]`, `local_stdin` reusing
     `gitapex_run_base_diff.py -- '*.py'`).
  5. Verify against a real sample: intentionally add one uncovered line
     to this PR's own diff temporarily, confirm the gate fails locally,
     then cover it and confirm it passes -- this doubles as ACM #1718's
     own "confirm output agrees with a real codecov/patch result on at
     least one sample PR" proof method once this PR's own CI runs
     Codecov.
  6. Run the full verification suite (pytest, ruff, mypy,
     `gitapex_gate_local_preflight.py`, `gitapex_scan_ssot_schema.py`)
     before reporting done.
- Proof method: regression tests fail against a reconstructed instance of
  each ACM row's own original defect shape, then pass once handled;
  existing suite stays green; this PR's own real diff cross-checked
  against Codecov's actual patch-coverage report.
- Irreversibility: reversible (new files plus one additive registry
  entry; no existing gate behavior is changed).

## Wave assignment

wave 1: {Task 1} -- single task, sequential-fallback path (no Workflow
tool opt-in this session).

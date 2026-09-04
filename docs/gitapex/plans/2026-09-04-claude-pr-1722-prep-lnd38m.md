# Branch Plan: except-clause fail-open static gate

Issue: https://github.com/tvna/gitapex/issues/1722
Branch: `claude/pr-1722-prep-lnd38m`

## Task 1: Add an AST-based except-clause fail-open static gate

- ACM row 1 (issue #1722, from #1704): "dimension-15 fail-open: malformed
  whole-file .gitapex/ssot.json"
- ACM row 2 (issue #1722, from #1706): "dimension-15 fail-open: malformed
  single gate entry (narrower recurrence of repair 2)"
- Quoted Planned ops, verbatim from issue #1722 (row 1, shared by row 2
  per the issue's own "implement as one combined patch rather than two"):
  "Add a static check (AST-based) for new or changed .github/scripts/*.py
  and hooks/*.py gate/checker scripts that flags any except clause
  returning an empty collection, None, or other falsy default, then
  requires either a dedicated test exercising that exact except clause
  with a real adjacent-hard-fail scenario, or an explicit
  docstring/commit justification for why fail-open is intentional
  there." Row 2's own Planned ops text: "Same proposed gate as repair
  2's own filed issue ... extending its scope statement to explicitly
  cover a per-entry/per-field malformed shape inside an otherwise
  well-formed container, not only a whole-file parse failure."
- Diagnosed fact (this session, `planning-a-branch-from-an-issue`): the
  root-cause function `load_python_dependent_hook_script_names`
  (`.github/scripts/gitapex_gate_bare_python3_invocation.py`) is already
  fail-closed on `main` (commits `f6e97a7`, `f6bed27`) for both the
  whole-file and the per-entry malformed shapes. This task adds only the
  new recurrence-prevention gate; it does not touch that function.
- Design precedent to follow (issue #682's own sibling gate, same
  fail-open-detection family): `.github/scripts/gitapex_gate_exception_handler_gaps.py`
  (diff-scoped AST rule, `# <gate-id>: WAIVED: <reason>` inline waiver
  convention, `ScanError`/exit-2 fail-closed-on-unparseable-input
  posture), its workflow `.github/workflows/exception-handler-gap-gate.yml`,
  and its `.gitapex/ssot.json` entry (`id: "exception-handler-gap"`).
- Files:
  - New: `.github/scripts/gitapex_gate_except_fail_open.py`
  - New: `.github/workflows/except-fail-open-gate.yml`
  - New: `tests/test_gitapex_gate_except_fail_open.py`
  - Edit: `.gitapex/ssot.json` (new gate entry, `id: "except-fail-open"`)
- Steps:
  1. Implement `gitapex_gate_except_fail_open.py`: parse a unified diff on
     stdin (reusing the sibling gate's own hunk-parsing shape), walk each
     in-scope added/changed file's AST for `except` clauses whose covered
     body path returns/produces a falsy default (`None`, `[]`, `{}`,
     `set()`, `frozenset()`, `()`, `""`, `0`, `False`) with no re-raise,
     scoped to `.github/scripts/*.py` and `hooks/*.py` only (test files
     excluded, matching the sibling gate's own convention), with an
     inline `# except-fail-open: WAIVED: <reason>` escape hatch.
  2. Add regression tests reproducing #1704's whole-file-malformed shape
     and #1706's per-entry-malformed shape as fixtures: each must be
     detected as a violation unwaived, and pass once waived.
  3. Add `.github/workflows/except-fail-open-gate.yml`, modeled on
     `exception-handler-gap-gate.yml` (merge-base diff, `uv run`).
  4. Register the gate in `.gitapex/ssot.json` (`planes: ["ci", "local"]`,
     reusing `gitapex_run_base_diff.py` for `local_stdin`, matching the
     `exception-handler-gap` entry's own shape).
  5. Run the full verification suite (pytest, ruff, mypy,
     `gitapex_gate_local_preflight.py`) before reporting done.
- Proof method: new tests fail against a reconstructed instance of the
  original #1704/#1706 defect shape, then pass once handled/waived;
  existing suite stays green.
- Irreversibility: reversible (new files plus one additive registry
  entry; no existing gate behavior is changed).

## Wave assignment

wave 1: {Task 1} -- single task, no file-ownership or interface-dependency
edge to compute against any sibling task.

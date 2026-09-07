# Branch Plan: gate-proposal-umbrella (meta-gate rule-scope gaps)

Issue: https://github.com/tvna/gitapex/issues/1572
Branch: `claude/gitapex-pr-1572-j4w3ga`

## Acceptance Criteria Map

(Re-verified by `planning-a-branch-from-an-issue` this session; full text
and re-verification marker posted to issue #1572's own body.)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| [from #1533] gitapex_gate_exception_handler_gaps.py's decode-gap/json-shape-gap rules do not cover a narrow-except-clause gap on the file-open step itself | `gitapex_check_task_commit_provenance.py`'s `main()` caught `FileNotFoundError` around `Path(args.messages).read_bytes()` but not the broader `OSError` (IsADirectoryError, PermissionError) that same read call can also raise -- the exact defect class `gitapex_check_branch_plan_reverified.py`'s own `--body` flag was already hardened against under issue #1306. Neither existing rule covers a file-open/read call whose handlers name FileNotFoundError specifically without the OSError ancestor. | Add a third AST-based rule, `open-gap`, to `.github/scripts/gitapex_gate_exception_handler_gaps.py`: flag a file-open/read call inside a `try` whose handlers name an OSError subclass specifically but not `OSError`/`Exception`/`BaseException`/a bare `except:` -- same enclosing-handler-name-table analysis, extended to a third call-site shape. | implementing PR adds the check plus a regression test; confirm it fails against a reintroduced instance of the original defect, then passes | Same name-matching limits decode-gap/json-shape-gap already disclose; not a new residual class. |
| [from #1532] detection-logic-property-coverage gate covers a new .resolve() call but not the new .split()-based parsing logic sitting right next to it | `split_commit_messages` filtered every empty string from a NUL-split instead of stripping only git's own one trailing NUL. The gate's detection scope (regex/path-resolution/string-comparison) does not include string-splitting/parsing calls, so it never asked for a property test over the exact function the real bug lived in. | Extend `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`'s own AST-based call-site scan to also flag a new `.split(`/`.rsplit(`/`.partition(` call, using the same cross-registry-consistency mechanism the gate already has for its three existing categories. | implementing PR adds the check plus a regression test; confirm it fails against a reintroduced instance of the original defect, then passes | A broadened scan will likely surface pre-existing `.split()` call sites with no property test today; one-time backlog to triage, not a new defect. |
| [from #1512] graphql_call narrower exception handling than its sibling | Two functions in the same shared module can silently drift to catch different exception sets for the same failure class, with nothing flagging the inconsistency. | A lint or drift-check rule flagging any two functions in the same module that both wrap a network call in a try/except but declare different exception tuples for the same failure class. | implementing PR adds the check plus a regression test; confirm it fails against a reintroduced instance of the original defect, then passes | none identified |
| [from #1587] yaml.safe_load except-clause did not cover RecursionError/MemoryError | A migration to yaml.safe_load for a sidecar read path used an except tuple that did not cover RecursionError/MemoryError, so a hostile or deeply-nested sidecar could crash with a raw traceback -- found only by a mandatory dogfooding pass, not any earlier, cheaper check. | A narrow AST-based check flagging any yaml.safe_load(...) call site whose surrounding except clause does not also cover RecursionError/MemoryError alongside yaml.YAMLError. | implementing PR adds the check plus a regression test; confirm it fails against a reintroduced instance of the original defect, then passes | Only catches this specific pattern, not every resource-exhaustion vector in a hand-rolled parser. |

## Task A: `open-gap` rule (#1533)

- Files:
  - Edit: `.github/scripts/gitapex_gate_exception_handler_gaps.py`
  - Edit: `tests/test_gitapex_gate_exception_handler_gaps.py`
  - Edit (if warranted): `tests/test_gitapex_gate_exception_handler_gaps_properties.py`
- Design: reuse `_handler_coverage()`/`_covers()` and the existing
  `_text_read_kind()` call-site detector (already used by `decode-gap`).
  New `_OSERROR_COVERING = frozenset({"OSError", "Exception",
  "BaseException"})`. A third candidate-collection loop in
  `findings_for_source()`, merged into the same `candidates` list ahead of
  the `in_diff` filter (~line 1197 of the current file). Rule id
  `open-gap`. Reuses the existing `# exception-handler-gap: WAIVED:
  <reason>` waiver convention -- no new waiver syntax.
- Steps:
  1. Implement the `open-gap` rule per the design above.
  2. Regression fixture reconstructing `gitapex_check_task_commit_provenance.py`'s
     pre-fix `main()` (catching only `FileNotFoundError` around a
     `Path(...).read_bytes()` read): confirm the gate flags it, then
     confirm the real, already-fixed file (which now also catches
     `OSError`) grades clean.
  3. Unit tests for the new rule's own edge cases (a handler naming
     `OSError` directly clears it; a handler naming only
     `PermissionError` does not; a bare `except:` clears it; the
     existing `decode-gap`/`json-shape-gap` behavior is unchanged).
  4. Run the full verification suite (pytest, ruff, mypy,
     `gitapex_gate_local_preflight.py`) before reporting done.
- Proof method: regression test fails against the reconstructed pre-fix
  shape, passes once the rule is added; existing suite stays green.
- Irreversibility: reversible (additive rule; existing `decode-gap`/
  `json-shape-gap` behavior unchanged).

## Task B: `yaml-gap` rule (#1587)

Depends on Task A (file-ownership edge on
`.github/scripts/gitapex_gate_exception_handler_gaps.py` and
`tests/test_gitapex_gate_exception_handler_gaps.py`, confirmed via
`gitapex_check_file_ownership_conflicts.py`; issue #1572's own Resolution
order also states this rule reuses the pattern Task A establishes).

- Files:
  - Edit: `.github/scripts/gitapex_gate_exception_handler_gaps.py`
  - Edit: `tests/test_gitapex_gate_exception_handler_gaps.py`
  - Edit (if warranted): `tests/test_gitapex_gate_exception_handler_gaps_properties.py`
- Design: new helper detecting a `yaml.safe_load(...)` call (mirroring
  the existing `_is_json_parse`-style attribute-call matching). Rule
  requires the enclosing handler set to cover **both**
  `RecursionError`-or-ancestor AND `MemoryError`-or-ancestor (two
  `_covers()` checks against `{"RecursionError", "Exception",
  "BaseException"}` and `{"MemoryError", "Exception", "BaseException"}`
  respectively, not one merged frozenset -- a single-side miss must still
  flag). Rule id `yaml-gap`. Same waiver convention as Task A.
- Steps:
  1. Implement the `yaml-gap` rule per the design above.
  2. Regression fixture reconstructing `gitapex_check_skill_shape.py`'s
     pre-fix except tuple (`OSError, UnicodeDecodeError,
     yaml.YAMLError`, missing `RecursionError`/`MemoryError`): confirm
     flagged, then confirm the real, already-fixed file (which now
     covers both) grades clean.
  3. Unit tests: a handler covering only `RecursionError` (not
     `MemoryError`) still flags, and vice versa; `Exception`/
     `BaseException` clears both.
  4. Run the full verification suite before reporting done.
- Proof method: regression test fails against the reconstructed pre-fix
  shape, passes once the rule is added; existing suite stays green.
- Irreversibility: reversible (additive rule).

## Task C: `.split()`/`.rsplit()`/`.partition()` detection (#1532)

No file-ownership or interface-dependency edge against Task A/B/D
(different source and test files).

- Files:
  - Edit: `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`
  - Edit: `tests/test_gitapex_gate_detection_logic_property_coverage_properties.py`
- Design: extend category (c) (string-comparison) with a new
  receiver-agnostic attribute set `{"split", "rsplit", "partition"}`
  alongside the existing `{"startswith", "endswith"}` -- same
  `_string_comparison_call_trigger()` mechanism, no new category id
  needed structurally, but add a distinct entry in `_TRIGGER_LABEL` so a
  failure message names the actual trigger kind.
- Steps:
  1. Implement the detection extension per the design above.
  2. Regression fixture reconstructing `split_commit_messages`'s pre-fix
     shape (filtering every empty string from a NUL-split, with no
     co-located Hypothesis property test covering it): confirm the gate
     flags the `.split()` call site as uncovered, then confirm the real
     file (which now has `tests/test_gitapex_check_task_commit_provenance_properties.py`
     covering it) grades clean.
  3. Unit tests: `.split()`/`.rsplit()`/`.partition()` each trigger;
     existing regex/path-resolution/`.startswith()`/`.endswith()`
     behavior is unchanged.
  4. Run the full verification suite before reporting done.
- Proof method: regression test fails against the reconstructed pre-fix
  shape, passes once the detection is added; existing suite stays green.
- Irreversibility: reversible (additive trigger category; will surface
  pre-existing uncovered `.split()` call sites elsewhere in the repo as
  disclosed residual risk -- a one-time backlog, not a new defect this
  change introduces, per the ACM's own residual-risk column).

## Task D: network exception-set drift lint (#1512, new script)

No file-ownership or interface-dependency edge against Task A/B/C (new,
independent script).

- Files:
  - New: `.github/scripts/gitapex_gate_network_exception_set_drift.py`
  - New: `tests/test_gitapex_gate_network_exception_set_drift.py`
  - New: `.github/workflows/network-exception-set-drift-gate.yml`
  - Edit: `.gitapex/ssot.json` (new gate entry)
- Design: diff-scoped AST scan, architecture patterned after
  `gitapex_scan_contract_discipline_drift.py`'s fail-closed style but
  generalized to N functions rather than a fixed file pair. Within one
  module's AST, find every function whose body contains a `try` wrapping
  a call recognizable as a network call (this repo's own established
  shape: an `opener(request)` call, or a `urllib.request`/`http.client`
  attribute call, or a call already flagged by this module's own
  low-level HTTP helper naming convention) and record that `try`'s own
  exception-handler name set (reusing `_handler_names`-style AST
  matching). Group functions by "same failure-class shape" (same
  underlying network primitive call pattern) and flag any two functions
  in that group whose recorded handler sets differ. Deliberately
  conservative: only flag when two functions in the *same module* wrap
  the *same recognizable call shape* -- avoids false positives between
  unrelated try/except pairs. Waiver: `# network-exception-set-drift:
  WAIVED: <reason>`, tokenize-matched, same non-whitespace-reason
  convention as sibling gates.
- CI wiring (per investigated precedent from `exception-handler-gap-gate.yml`/
  `detection-logic-property-coverage-gate.yml`): `on: pull_request`
  (opened/synchronize/reopened), no `paths:` filter, `harden-checkout`
  with `fetch-depth: '0'`, `astral-sh/setup-uv`, `git diff -U0
  --no-renames merge-base HEAD -- '*.py' | uv run --frozen python3
  .github/scripts/gitapex_gate_network_exception_set_drift.py`.
  `.gitapex/ssot.json` entry: `planes: ["ci", "local"]`,
  `local_invocation`/`local_stdin` matching the sibling gates' exact
  shape, `tracking_issue: 1512`.
- Steps:
  1. Implement the drift-check script per the design above.
  2. Regression fixture reconstructing `_gitapex_github_http.py`'s
     pre-fix `graphql_call` (catching only `except
     urllib.error.URLError`) alongside `request_with_retry` (catching
     `except (OSError, http.client.IncompleteRead)`) in the same
     module: confirm the gate flags the drift, then confirm the real,
     already-fixed file (both now aligned) grades clean.
  3. Defeat-test: construct an input built to defeat this gate's own
     detection logic (e.g. two functions wrapping unrelated calls that
     happen to share an exception name) and confirm it does not
     false-positive.
  4. Add `.github/workflows/network-exception-set-drift-gate.yml`.
  5. Register in `.gitapex/ssot.json`.
  6. Run the full verification suite (pytest, ruff, mypy,
     `gitapex_gate_local_preflight.py`, and any `.gitapex/ssot.json`
     schema-drift gate) before reporting done.
- Proof method: regression test fails against the reconstructed pre-fix
  shape, passes once the rule is added; defeat-test confirms no
  false-positive; existing suite stays green.
- Irreversibility: reversible (new files plus one additive registry
  entry; no existing gate behavior changed).

## File-ownership check

`gitapex_check_file_ownership_conflicts.py` run against the four tasks'
file lists confirms exactly one conflict pair: Task A and Task B both
write `.github/scripts/gitapex_gate_exception_handler_gaps.py` and
`tests/test_gitapex_gate_exception_handler_gaps.py` -- sequenced across
waves per that tool's own output. No other conflicts found. No
interface-dependency edge identified beyond that same A->B ordering
(Task B's own rule reuses Task A's established pattern, but touches no
API Task A exposes to other files).

## Wave assignment

wave 1: {Task A, Task C, Task D} -- no shared files, no interface edges;
dispatch in parallel (Workflow tool if available, else sequential
main-thread fallback per SKILL.md step 6).
wave 2: {Task B} -- sequenced after Task A (file-ownership edge).

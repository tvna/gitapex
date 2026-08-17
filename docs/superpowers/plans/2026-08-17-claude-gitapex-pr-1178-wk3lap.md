# Detection-logic property-coverage gate (issue #1178)

**Goal:** Add a new, diff-scoped, mechanically-enforced CI/pre-commit gate
requiring a hypothesis-based property test for any new or materially
changed regex-, path-resolution-, or string-comparison-based detection
logic within `skills/*/scripts/gitapex_check_*.py`,
`.github/scripts/gitapex_gate_*.py`, or `hooks/gitapex_check_*.py` --
formally superseding the hypothesis pilot's (issue #939) "wait for a
demonstrated catch" scope limit. Source:
https://github.com/tvna/gitapex/issues/1178.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 4):** the issue's own drafted ACM was independently re-checked against
repo state as part of this same Branch Plan, not accepted as
pre-verified. Two
corrections were made to the issue's own draft, both grounded in direct
repo/history inspection, not assumption:

1. The issue's own Proof-method column claims a retroactive check "would
   have flagged both" the #1129 and #1032 historical defects. Verified
   false for #1032: that hostname-truncation bug lives in
   `skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`
   (confirmed by reading commit `198ea86` and grepping
   `NETWORK_CAPABLE_MODULES`/`_URL_HOST_PATTERN` directly), a `gitapex_scan_*.py`
   file this gate's own Constraints section explicitly excludes. #1129 is
   independently confirmed instead: commit `6bef4ba` added
   `EXEC_REQ_PACKAGES_KEY_RE = re.compile(...)` at module level in
   `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
   (an in-scope `gitapex_check_*.py` file) and called it via `.match(key)`
   inside `_parse_manifest`, with no co-located properties test then or
   now.
2. The issue's own Interpretation column names the trigger as
   "`re.compile`/`re.match`/`re.search`/`re.fullmatch`" -- read literally
   (the `re` module's own top-level functions), this would miss the actual
   #1129 defect and most of this repo's own real regex usage, which
   overwhelmingly calls `.match()`/`.search()`/`.fullmatch()` as a **bound
   method on a pre-compiled module-level `Pattern` constant**
   (`EXEC_REQ_PACKAGES_KEY_RE.fullmatch(key)`,
   `_WAIVER_RE.search(token.string)`, `_HUNK_RE.match(line)` -- all
   confirmed by direct reading of `gitapex_gate_exception_handler_gaps.py`
   and `gitapex_check_skill_shape.py`). The trigger is corrected below to
   include the receiver-agnostic bound-method form.

Both corrections are disclosed in the PR body per
`planning-a-branch-from-an-issue`'s own Step 4 mandate, not silently
folded in.

**File-ownership check (mechanized):**
`python3 skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py`
against the 5 tasks' file lists below -> no conflicts (disjoint files).

**Interface-dependency edges:**
- Task 3 (example-based + scope-boundary tests), Task 4 (self-dogfood
  properties test), and Task 5 (workflow + ssot.json registration) each
  import/reference Task 2's own gate script (module name, function names,
  CLI flag names, exit-code contract) -- each sequenced after Task 2, never
  co-assigned to Task 2's own wave.
- No edge between Task 1 and Task 2 (disjoint files, no producer/consumer
  relationship -- Task 1's docstring note only needs the new gate's id/issue
  number, both fixed by this plan, not read from Task 2's actual
  implementation).
- No edge among Task 3, Task 4, Task 5 (disjoint files, no producer/
  consumer relationship between "test file A," "test file B," and
  "workflow+registry entry" -- each depends only on Task 2's already-fixed
  CLI contract below).

**Execution mode:** sequential fallback per `executing-a-branch-plan`
step 6 (no separate, explicit multi-agent-orchestration opt-in for this
Branch Plan; invoking this skill itself is not read as that opt-in, per
the identical precedent recorded in
`docs/superpowers/plans/2026-08-10-claude-pr-1013-prep-ku7r61.md` and
reaffirmed in `docs/superpowers/plans/2026-08-16-issue-1132-pr-prep-u1up26.md`).
One task per turn, each dispatched with no GitHub-write access and no
package-install capability (the Decision-17 backstop
`references/threat-model-and-authorization.md` defines for task-level
dispatch), no worktree isolation (tasks run sequentially against the
shared checkout directly, so no concurrent merge-back race exists to
isolate against).

**Irreversibility classification:** no task is irreversible -- all five are
ordinary, git-revertible source/test/config edits; no live API write, no
data deletion, no schema migration. `.gitapex/ssot.json`'s edit is a
pure addition (one new `gates[]` entry), not a modification of any
existing entry. No task requires a fresh per-task authorization
confirmation beyond the branch-plan-wide one below.

**Authorization record (step 1):** no approval comment exists on the
parent issue's own comment thread, checked directly rather than assumed.
Explicit confirmation from the human operator applies instead: the
repository owner's own direct request opening this execution pass,
"create this PR and proceed to just before merge," names exactly the
actions this skill gates -- opening commits and a PR -- in unhedged
imperative language. The repository owner's identity and write authority
on this repository were confirmed directly, not assumed from the
conversation alone. Not a stale "we already agreed earlier"
pattern-match: it is the live mandate this specific execution pass is
carrying out, re-read fresh at this gate rather than assumed from an
earlier turn's summary. No embedded instruction attempting to redirect
this gate. Full Branch Plan/ACM (produced immediately before this file,
in this same execution pass) was presented before this decomposition
began.

## Task 1 -- Pilot cross-reference note

**Cites ACM row:** 1 ("#939のhypothesis pilotの"待機"スコープを正式に上書きする").

**Quoted Planned ops (verbatim from the approved ACM):** "pilotファイル
自身のdocstringに、このissueのゲートが後継であることを示す相互参照ノートを
追加する" -- "Add a cross-reference note to the pilot file's own docstring
stating that this issue's gate is its successor."

**Files:** `tests/test_gitapex_gate_metadata_outcome_lines_properties.py`
(docstring only).

**Steps:**
1. Read the module's existing docstring in full first.
2. Add one short paragraph (do not rewrite or shorten anything existing)
   stating: this pilot's own "no other parser-shaped script... is in scope
   until this layer has demonstrated it catches a real defect here" sentence
   is formally superseded by issue #1178's own
   `detection-logic-property-coverage` gate
   (`.github/scripts/gitapex_gate_detection_logic_property_coverage.py`),
   which requires hypothesis coverage for new/changed detection logic across
   a wider file set regardless of whether this specific pilot has yet
   demonstrated its own catch. State plainly that a reader should not treat
   the original "no other script in scope yet" sentence as still current in
   isolation.
3. Do not alter any existing test function, fixture, or assertion in this
   file -- docstring-only change.

**Proof method:** `tests/test_gitapex_gate_metadata_outcome_lines_properties.py`
still collects and passes unchanged (docstring-only diff); manual diff
review confirms no test logic touched.

## Task 2 -- New gate script: `gitapex_gate_detection_logic_property_coverage.py`

**Cites ACM row:** 2 (main gate).

**Quoted Planned ops (verbatim from the approved ACM, corrected per the
two corrections stated above):** "`.github/scripts/gitapex_gate_detection_logic_property_coverage.py`
新規作成(exception-handler-gapと同一のCLI/pydantic/exit code規約: 0=clean,
1=violation, 2=fail-closed)" -- "Create
`.github/scripts/gitapex_gate_detection_logic_property_coverage.py` new
(same CLI/pydantic/exit-code convention as exception-handler-gap: 0=clean,
1=violation, 2=fail-closed)."

**Files:** `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`
(new).

**Required reading before writing any code (so the established repo
conventions are followed exactly, not reinvented):**
`.github/scripts/gitapex_gate_exception_handler_gaps.py` in full -- this new
gate mirrors its architecture closely: same diff-parsing shape (post-image
path -> added line-number set), same `ScanError`/fail-closed-exit-2
convention, same pydantic-validated `argparse` CLI, same `uv run --frozen`
invocation, same inline-waiver-via-`tokenize` convention, same
"known misses / known over-reports" disclosure style in the module
docstring.

**Design, fixed at decomposition time so the Red step (Task 3/4) targets a
stable interface -- implement exactly this, do not redesign:**

- **In-scope path regex** (mirror `_IN_SCOPE_RE`'s own `[^/]+` /
  `re.fullmatch` style exactly):
  ```python
  r"skills/[^/]+/scripts/gitapex_check_[^/]+\.py"
  r"|\.github/scripts/gitapex_gate_[^/]+\.py"
  r"|hooks/gitapex_check_[^/]+\.py"
  ```
  A file matching this pattern is in scope UNLESS its basename starts with
  `test_` or equals `conftest.py` (a `skills/*/scripts/test_gitapex_check_*.py`
  file co-located with its source is a real, confirmed shape in this repo
  today -- e.g. `skills/evaluating-skill-quality/scripts/test_gitapex_scan_execution_requirements_drift.py`
  -- and must be excluded the same way `gitapex_gate_exception_handler_gaps.in_scope`
  excludes test files). `gitapex_scan_*.py` never matches this pattern by
  construction -- no separate exclusion needed for it, but add one explicit
  test proving it (Task 3).

- **Trigger call categories** (an AST `Call` node "reached by an added diff
  line" means: the diff's added-line-number set intersects the call's own
  full span, `node.lineno` through `node.end_lineno` inclusive -- not
  `node.lineno` alone. Mirror `gitapex_gate_exception_handler_gaps.py`'s own
  `_span()`/`_Candidate.trigger` design exactly: a multi-line call whose
  opening line (`SOME_RE.fullmatch(`) is untouched but whose argument on a
  later line was added or changed must still be graded, the same way that
  file's own reformatting-one-argument case is. Checking `node.lineno` only
  would miss this -- confirmed live: `ast.parse("def f():\n    SOME_RE.fullmatch(\n        x,\n    )\n").body[0]`'s
  own `Call` node has `lineno=2, end_lineno=4`, so an added line 4 (`x,`)
  falls inside the call's span but not on its opening line. Task 3 adds a
  regression for exactly this shape.):
  1. **Regex.** EITHER an attribute call `re.compile(...)` / `re.match(...)`
     / `re.search(...)` / `re.fullmatch(...)` (receiver is `Name(id="re")`)
     OR a receiver-agnostic bound-method call `.match(...)` / `.search(...)`
     / `.fullmatch(...)` (any receiver -- matched by final attribute name
     only, same philosophy as `_text_read_kind`'s own receiver-agnostic
     `.open()`/`.read_text()` matching in the reference file above). The
     bound-method form is a deliberate, disclosed widening beyond the
     issue's own literal text -- state why in the new module's own
     docstring, citing commit `6bef4ba`'s `EXEC_REQ_PACKAGES_KEY_RE.match(key)`
     call site as the concrete historical defect this widening exists to
     catch (the bare `re.compile(...)` form alone would miss it, since the
     `.match()` call site, not the `re.compile()` definition site, is where
     `\Z`-vs-`$` anchor bugs like the #1129 repair-8 defect actually live).
  2. **Path-resolution.** Receiver-agnostic method calls `.resolve(...)`,
     `.is_symlink(...)`, `.relative_to(...)`; plus attribute calls
     `os.path.realpath(...)`, `os.path.abspath(...)` (receiver-agnostic on
     final two attribute segments, i.e. also matches an aliased/renamed
     `os` import via `<name>.path.realpath(...)`).
  3. **String-comparison allowlist/denylist.** Receiver-agnostic method
     calls `.startswith(...)`, `.endswith(...)`; OR an `ast.Compare` node
     with a single `In`/`NotIn` op whose right-hand comparator is an inline
     `List`/`Tuple`/`Set` literal, OR a `Call` to `frozenset(...)`/`set(...)`
     whose sole argument is itself an inline `List`/`Tuple`/`Set` literal
     (covers this repo's own pervasive `frozenset({...})` idiom written
     directly at the comparison site). A name reference to a
     previously-defined collection constant (`x in SOME_MODULE_CONSTANT`)
     is a disclosed, deliberate miss -- state this in the docstring's own
     "known misses" section, matching the reference file's own disclosure
     style; do not attempt name resolution (the reference file's own
     `_handler_names` docstring records three separate attempts at
     resolving names elsewhere in this repo, each reverted as more costly
     than it was worth -- do not repeat that here).

- **Scope/function attribution.** For each in-scope file, walk its full AST
  once (not diff-scoped -- the whole file, so a trigger call's enclosing
  function is found correctly regardless of where in the file the function
  itself sits) and record every `FunctionDef`/`AsyncFunctionDef`'s own line
  range. A trigger call whose line falls inside the innermost such range is
  attributed to that function's `name`. A trigger call at true module level
  (inside no function) is attributed to the sentinel scope name `<module>`.

- **Existing-coverage check.** For a source file at repo-relative path
  `P` with stem `S` (e.g. `.github/scripts/gitapex_gate_foo.py` ->
  `S = "gitapex_gate_foo"`), the co-located properties file is
  `tests/test_{S}_properties.py` (exactly the
  `gitapex_gate_metadata_outcome_lines.py` ->
  `tests/test_gitapex_gate_metadata_outcome_lines_properties.py` naming
  precedent). For a scope name `F` (a function name, or `<module>`):
  - If the properties file does not exist under `--root` -> uncovered.
  - Else parse its AST. Uncovered unless it contains an import of the
    source module (`import {S}` or `from {S} import ...`) AND at least one
    `FunctionDef`/`AsyncFunctionDef` decorated with a `@given(...)` call
    (`hypothesis.given`, matched by the decorator's own final attribute/name
    being `given`) such that:
    - for a real function scope `F`: that specific `@given`-decorated
      function's own body contains a `Name`/`Attribute` node whose final
      name equals `F` (a plain identifier-presence check inside that one
      function's body only -- not the whole file -- so an unrelated
      `@given` test elsewhere in the same file does not count);
    - for the `<module>` scope: it is enough that some `@given`-decorated
      function exists anywhere in the properties file (no name match
      required -- a bare module-level constant has no function identity of
      its own to check for).
  - Disclose in the docstring that this is a textual/AST identifier-presence
    heuristic, not true call-graph or data-flow analysis: a properties file
    that merely *mentions* the function's name (in a comment, an unrelated
    local variable, a docstring) without actually exercising it under
    `@given` can false-clear; a properties file that calls the function only
    through an indirection (a wrapper it imports) can false-flag. Both are
    accepted, disclosed misses, matching this repo's own established
    disclosure convention (see the reference file's own extensive
    "Known misses"/"Known over-reports" sections) -- do not attempt to close
    either.

- **Waiver.** `# detection-logic-property-coverage: WAIVED: <reason>` inline
  comment, a reason mandatory, matched via `tokenize` exactly like the
  reference file's own `_waived_lines`/`_WAIVER_RE` (adjust the fixed prefix
  string only).

- **CLI/exit codes.** `--root` (pydantic-validated existing directory,
  default `pathlib.Path(__file__).resolve().parents[2]`), `--diff` (optional
  file path; default reads a unified diff from stdin as UTF-8 bytes,
  `UnicodeDecodeError` -> exit 2, same as the reference file's own `main`).
  Exit 0 clean, 1 violation found, 2 the scan could not be trusted
  (malformed diff, unparseable in-scope file, bad `--root`) -- never a
  silent pass on an ungradable input (dimension 15).

- **Module docstring.** Follow the reference file's own documentation depth:
  cite issue #1178 and the historical defects (#1129 confirmed directly,
  #1032 explicitly named as OUT of this gate's own scope and why), state the
  bound-method regex-trigger widening and its rationale, state the
  identifier-presence heuristic's own known misses, state exit-code
  contract, state this gate's own `local_stdin`/`local_invocation` shape for
  `.gitapex/ssot.json` (Task 5) matches `exception-handler-gap`'s own
  `["git", "-c", "core.quotePath=false", "diff", "-U0", "--no-renames",
  "--merge-base", "origin/main", "HEAD", "--", "*.py"]` pattern exactly.

**Steps:**
1. Write the module docstring first (per the Design section above), stating
   the design decisions and their rationale before the code that implements
   them.
2. Implement the in-scope filter, trigger detection (all three categories),
   scope/function attribution, existing-coverage check, waiver handling,
   `find_violations`/CLI exactly mirroring the reference file's own
   structure and naming conventions where they transfer directly
   (`ScanError`, `Finding`, `_waived_lines`, `main`).
3. Run `uv run --frozen mypy --config-file pyproject.toml .github/scripts`
   and `uv run --frozen ruff check .github/scripts/gitapex_gate_detection_logic_property_coverage.py`
   locally before returning -- fix any finding, do not hand off a
   type-incomplete or lint-dirty file for Task 3/4 to build tests against.

**Proof method:** mypy/ruff clean on this one file (Task 3/4 supply the
actual pytest coverage; this task's own proof is limited to static checks
since no test file exists yet to run against it).

## Task 3 -- Example-based tests + scope-boundary tests

**Cites ACM rows:** 2 (main gate, example-based coverage) and 3
(scope-boundary: `gitapex_scan_*.py` exclusion, diff-scoped-only).

**Quoted Planned ops (verbatim from the approved ACM):** row 2: "既存の
`exception-handler-gap`と同一のCLI/pydantic/exit code規約" tested via
"`tests/test_gitapex_gate_detection_logic_property_coverage.py`にtrue-
positive/true-negative/waivedケース" -- "true-positive/true-negative/waived
cases in `tests/test_gitapex_gate_detection_logic_property_coverage.py`."
row 3: "テストケース: `gitapex_scan_*.py`への新規regex追加が検出されない
こと、diffで触れられていない既存の未カバースクリプトが遡って検出されない
こと、の2ケースを追加" -- "add 2 test cases: a new regex added to a
`gitapex_scan_*.py` file is not detected; a pre-existing, diff-untouched,
uncovered script is not retroactively flagged."

**Files:** `tests/test_gitapex_gate_detection_logic_property_coverage.py`
(new).

**Required reading first:** `tests/test_gitapex_gate_exception_handler_gaps.py`
for this repo's own established fixture/assertion style for a gate of this
shape (synthetic unified-diff-text fixtures, `tmp_path`-based `--root`
trees, direct calls into the gate module's own functions rather than only
subprocess CLI invocation).

**Steps:**
1. Import the Task 2 module directly (same `sys.path`/pythonpath convention
   the reference test file uses).
2. True-positive case: a synthetic diff adding a brand-new function to an
   in-scope fixture file (e.g. a fake `.github/scripts/gitapex_gate_fixture.py`
   under `tmp_path`) containing a new `SOME_RE.fullmatch(...)` call (bound-
   method form -- confirms the corrected trigger, not just the literal
   `re.fullmatch(...)` form), with no co-located properties file -> exactly
   one violation reported, correctly attributed to that function's name.
3. True-negative case: identical shape, but a co-located
   `tests/test_gitapex_gate_fixture_properties.py` already exists in the
   fixture tree, importing the module and carrying one `@given`-decorated
   function whose body references the target function's name -> clean, zero
   violations.
4. Waived case: the true-positive shape, but the trigger line carries
   `# detection-logic-property-coverage: WAIVED: <reason>` -> zero
   violations, one honoured waiver printed.
5. Scope-boundary case A: the true-positive shape's identical new-regex
   diff, but against a `gitapex_scan_fixture.py` path instead -> zero
   violations (out of scope by construction).
6. Scope-boundary case B: an in-scope fixture file with a pre-existing
   (already in the `tmp_path` tree, NOT touched by the diff text) function
   containing an uncovered trigger call, plus a diff touching a *different*,
   unrelated line in that same file -> zero violations for the untouched
   function (diff-scoped only, no retroactive flagging).
7. At least one path-resolution-category and one string-comparison-category
   true-positive case each (not only the regex category), so all three
   trigger categories have direct test coverage, not only regex.
8. Malformed-input case: an unparseable diff / a non-UTF-8 stdin payload ->
   exit 2, matching the reference file's own `ScanError` contract tests.
9. Run the full new test file; confirm every new test passes and, for the
   true-positive/waived/scope-boundary cases, that reverting the specific
   Task-2 logic each one targets makes that one test fail for the right
   reason (a quick local sanity check, not a permanent flip-test fixture).

**Proof method:** `uv run --frozen pytest tests/test_gitapex_gate_detection_logic_property_coverage.py -v`
full pass, all 3 trigger categories and both scope-boundary cases
represented.

## Task 4 -- Self-dogfood properties test (own-file coverage)

**Cites ACM row:** 2, self-referential dogfooding consequence: this new
gate's own source file, `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`,
matches its own `.github/scripts/gitapex_gate_*.py` in-scope pattern. Once
Task 5's workflow is wired to run on this PR's own `pull_request` event, the
gate would flag its own newly-added diff (its own regex/path/string-
comparison detection calls) unless a co-located properties file already
covers it -- this task closes that loop inside the same PR rather than
leaving the new gate to fail against itself.

**Files:**
`tests/test_gitapex_gate_detection_logic_property_coverage_properties.py`
(new).

**Required reading first:**
`tests/test_gitapex_gate_metadata_outcome_lines_properties.py` in full --
this repo's one existing hypothesis-pilot precedent for structure
(module-scoped fixture, `derandomize=True` + explicit `max_examples` +
`deadline=None`, one property per defect class, each docstring stating
plainly whether it does or does not detect a specific motivating defect).

**Steps:**
1. **Coverage must match Task 2's own existing-coverage contract exactly,
   not a representative sample of it.** Task 2's design requires a
   `@given`-decorated test, in this properties file, whose own body
   references each trigger-bearing function's own name (or, for a bare
   `<module>`-level trigger, any `@given` test at all) -- see Task 2's
   Design section, "Existing-coverage check." Once Task 2's implementation
   exists, enumerate every function in
   `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`
   that itself contains a trigger-category call (the in-scope-path
   matcher, the regex/path/string-comparison trigger classifiers, the
   scope/function-attribution walker, the existing-coverage checker, the
   waiver-line detector -- whichever of these, concretely, Task 2 actually
   implemented as separate functions containing a `.match(`/`.search(`/
   `.resolve(`/`.startswith(`/membership-`in`-style call of its own) and
   write one property per function on that real list -- not a
   fixed-in-advance subset of "one per category." This task's own
   properties file is simultaneously real test coverage AND the exact
   fixture Task 2's own gate, once wired into CI (Task 5), checks against
   itself -- an incomplete list here means the gate fails against its own
   PR the first time its workflow runs. The pilot's own "one motivating
   defect per property, not exhaustive input-space coverage" discipline
   governs how thorough each individual property's own generator is, not
   which functions get a property at all.
2. Write one `@given`-decorated property test per enumerated function,
   each applying the same `settings(derandomize=True, max_examples=<N>,
   deadline=None)` convention as the pilot (module-scoped `settings`
   object, not a global profile -- matching the pilot's own stated reason:
   a global profile would leak into every other test module).
3. Each property's own docstring states plainly which real defect class it
   would catch (mirroring the pilot's own per-property honesty), and
   whether it is model-based (knows the intended answer) or a weaker
   self-consistency/robustness property -- do not claim a property "detects"
   something it only exercises without a real oracle.
4. Confirm this file, once it exists, is exactly what Task 2's own
   `<module>`/function-scope existing-coverage check (Design section) would
   find sufficient for its own source file -- i.e. this task is simultaneously
   real test coverage AND the fixture that satisfies the new gate's own
   self-check.

**Proof method:** `uv run --frozen pytest tests/test_gitapex_gate_detection_logic_property_coverage_properties.py -v`
full pass; separately, run Task 2's gate directly (CLI, piping
`git diff --merge-base origin/main HEAD -- '*.py'` once Tasks 2-5 are all
merged to the branch) and confirm it reports clean against this PR's own
accumulated diff -- the live self-check this task exists to satisfy.

## Task 5 -- Workflow + `.gitapex/ssot.json` registration

**Cites ACM row:** 2 (main gate, wiring).

**Quoted Planned ops (verbatim from the approved ACM):** "`.github/workflows/*.yml`
新規作成(harden-checkout, merge-base diff, uv run) + `.gitapex/ssot.json`に
`gates[]`エントリ追加(cluster: test-integrity, planes: [ci, local],
tracking_issue: 1178)" -- "create a new
`.github/workflows/*.yml` (harden-checkout, merge-base diff, uv run) + add a
`gates[]` entry to `.gitapex/ssot.json` (cluster: test-integrity,
planes: [ci, local], tracking_issue: 1178)."

**Files:** `.github/workflows/detection-logic-property-coverage-gate.yml`
(new), `.gitapex/ssot.json` (edit -- append one `gates[]` entry only, do not
touch any existing entry).

**Required reading first:** `.github/workflows/exception-handler-gap-gate.yml`
in full, and the `exception-handler-gap` entry in `.gitapex/ssot.json`
(the `id`, `script` array, `local_invocation`, `local_stdin`, `trigger`,
`cluster`, `status`, `supersedes` shape) -- mirror both as closely as the
new gate's own name/id/paths require, changing nothing structural.

**Steps:**
1. Workflow: copy `exception-handler-gap-gate.yml`'s structure exactly --
   `harden-checkout` action (same pinned SHA), `astral-sh/setup-uv` (same
   pinned version), `permissions: contents: read`, the same
   `concurrency`/`cancel-in-progress` block, no `paths:` filter (same
   deadlock-avoidance rationale, quote it in this new file's own header
   comment rather than omitting the reasoning), the same `git merge-base` +
   `git -c core.quotePath=false diff -U0 --no-renames` + `uv run --frozen
   python3 .github/scripts/gitapex_gate_detection_logic_property_coverage.py`
   invocation shape, substituting only the script path and job/step names.
   **Do NOT add this workflow's job to `.github/rulesets/main.json`'s
   required-status-checks list in this task or this PR** -- this is a
   deliberate scope boundary decided in the Branch Plan (matches
   `exception-handler-gap`'s own precedent of shipping non-required first,
   promoted separately later); state this explicitly as a code comment is
   not appropriate here, state it instead in the PR body (main-thread step,
   not this task's own job).
2. `.gitapex/ssot.json`: append one new object to `gates[]` (after the
   existing `exception-handler-gap` entry, or wherever alphabetical/logical
   grouping in the existing array suggests -- match the file's own existing
   ordering convention, do not reorder any existing entry):
   - `id`: `"detection-logic-property-coverage"`
   - `kind`: `"script"`
   - `script`: `[".github/scripts/gitapex_gate_detection_logic_property_coverage.py", ".github/workflows/detection-logic-property-coverage-gate.yml"]`
   - `rule`: one line, grounded in the actual script's logic (not a restated
     CLAUDE.md bullet) -- state the three trigger categories and the
     properties-file requirement concretely.
   - `planes`: `["ci", "local"]`
   - `local_invocation`: `["uv", "run", "--frozen", "python3", ".github/scripts/gitapex_gate_detection_logic_property_coverage.py"]`
   - `local_stdin`: `["git", "-c", "core.quotePath=false", "diff", "-U0", "--no-renames", "--merge-base", "origin/main", "HEAD", "--", "*.py"]`
   - `trigger`: this new workflow file's own name + pytest collection path
     of Task 3/4's test files inside `.github/workflows/test.yml`'s own
     pytest step, matching the `exception-handler-gap` entry's own trigger
     string shape.
   - `policy_refs`: `[]`
   - `cluster`: `"test-integrity"`
   - `tracking_issue`: `1178`
   - `status`: `"active"`
   - `supersedes`: `null`
3. Run `uv run --frozen python3 .github/scripts/gitapex_scan_ssot_schema.py`
   (or the equivalent pytest gate covering it) to confirm the new entry
   passes schema validation and the drift checks (referenced script/workflow
   paths actually exist, `local_invocation` names one of this gate's own
   script paths, no shell-form argv).

**Proof method:** `gitapex_scan_ssot_schema.py`'s own gate (CLI or pytest
wrapper) passes clean against the edited `.gitapex/ssot.json`; the new
workflow YAML parses (`yaml.safe_load` sanity check) AND passes the
`scanning-ci-workflows` skill's own actionlint (schema/expression/embedded-
shell validity) and zizmor (template injection, permissions, unpinned
`uses:`, dangerous triggers) pass -- run inside this task, not deferred,
since both are static checks that need only the file to exist, not a live
CI run. Once this task's commit is pushed (main-thread step 6), the
main thread additionally confirms via `pull_request_read get_check_runs`
that the new workflow's own job actually fired and reported on this PR's
real `pull_request` event -- a live-execution confirmation, not only a
static-analysis one, closing the gap a syntax-only check leaves (a
schema-valid workflow can still never fire, e.g. a typo'd `on:` key).

## Post-task gate (Decision 12, mandatory)

After all five tasks land: one refactor/simplify pass (behavior-preserving
only) and one independent adversarial code review, each a fresh subagent
dispatch over the full accumulated diff. Given this diff adds a new
deterministic detection gate, the adversarial review must construct at
least one defeat-case per `refactor-and-review-gate.md`'s own requirement
(e.g. a trigger call spelled in a way the AST matcher's own receiver-
agnostic method-name matching over-reports on, or a properties file that
imports the module but whose sole `@given` test targets an unrelated
function -- confirming the existing-coverage check does not false-clear)
before this gate can clear. Every CONFIRMED finding is fixed and every
task's own Red-Green test is re-run (not only the one related to the fix)
before the draft PR converts to ready-for-review.

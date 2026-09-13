# Branch Plan: defeat-test-mutation-coverage gate (vacuous defeat-tests)

Issue: https://github.com/tvna/gitapex/issues/1799

Branch: `claude/trusting-sagan-g5efyx` (this session's designated branch
for `tvna/gitapex`, from `origin/main` -- the session's own harness-level
instructions pin development and pushes to this exact branch and forbid
pushing elsewhere without explicit permission).

## Decided approach (human-confirmed in this session)

`AskUserQuestion` presented three implementation-approach options; the
operator chose "真のmutation実行gate" (a real mutation-execution gate)
over extending the existing name-mention-only static heuristics
(`gitapex_gate_detection_logic_property_coverage.py`, issue #1178, and
`gitapex_gate_function_body_test_coverage.py`, issue #1498) or a
scope-estimate-first pause. Grep across `.github/scripts/` and `hooks/`
found no existing gate that actually executes tests against a mutated
copy of a source file -- every one of the 86 gates registered in
`.gitapex/ssot.json` grades a diff by static AST inspection alone. This
is therefore a new mechanism, not an extension of an existing one.

## Task Decomposition

One task, one wave -- the degenerate case `executing-a-branch-plan`'s own
Related-skills section names, not a skipped decomposition. issue #1799's
six consolidated rows all describe one mechanism (remove the claimed
element, confirm a paired test fails), and every row's planned ops land
on the same new gate script, its own registration, its own CI wiring, and
its own regression tests -- so the four candidate sub-tasks considered
(mutation engine + regex trigger / dict-entry trigger / unconditional-
literal trigger / regression tests + CI + ssot registration) all share
the same two files (the gate script and its test file). File-ownership
conflicts across that four-way split are total, not partial, so
decomposing further would only force a four-wave sequential chain with
no parallelism gained -- collapsed into one task instead:

```
$ echo '{"task-1-defeat-test-mutation-coverage-gate": [".github/scripts/gitapex_gate_defeat_test_mutation_coverage.py", ".github/workflows/defeat-test-mutation-coverage-gate.yml", "tests/test_gitapex_gate_defeat_test_mutation_coverage.py", ".gitapex/ssot.json"]}' \
    | python3 skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py
no file-ownership conflicts found
```

The interface-dependency map is likewise empty for the same reason (one
task, nothing to depend on).

Irreversibility classification: **not irreversible.** The task adds new
files (a gate script, its workflow, its test file) and appends one entry
to `.gitapex/ssot.json`'s own `gates` array. Nothing writes outside the
repository, no migration runs, no pre-existing file's own meaning
changes. `git revert` of the merge commit removes the new gate cleanly.

`SKILL.md` classification: **no `SKILL.md` is created or edited.** The
change touches only `.github/scripts/`, `.github/workflows/`, `tests/`,
and `.gitapex/ssot.json`, so `drafting-a-skill` is not routed to and the
PR-body skill-audit disclosure convention does not apply.

## Task 1: implement the defeat-test-mutation-coverage gate

Source ACM rows: issue #1799's own table, quoted verbatim per this
skill's own step-3 convention -- six rows, one target mechanism.

> [from #1733] Planned ops: A CI step or pre-commit check that
> mutation-tests each named regex alternative/branch a new or changed
> detection-logic test suite claims to cover: for each branch, temporarily
> remove it and confirm at least one paired test fails; flag a branch with
> zero failing tests as a vacuous-coverage finding -- the same check PR
> #1715's own Step 8 Round 3 already performed by hand.

> [from #1734] Planned ops: Same proposed gate as repair 3 (mutation-test
> each claimed regex branch against its paired test suite); this
> recurrence is itself evidence the gate is warranted rather than a
> coincidence.

> [from #1735] Planned ops: Add a mutation-testing pass (or minimally, a
> per-new-test remove-the-targeted-branch-and-confirm-failure check) as a
> CI job or pre-merge script for any PR that adds regression tests
> claiming to pin a specific regex/logic branch, so a test that does not
> actually exercise the branch its own docstring or PR description claims
> is caught mechanically before independent review time rather than only
> by a reviewer manually reconstructing the code to check.

> [from #1736] Planned ops: Same underlying gap as repair 1 (see
> Recurrence note there): a mutation-testing or remove-the-targeted-branch
> check applied to every new regression test, run automatically, would
> have caught this one too -- and specifically would have caught that a
> fix for one vacuous test can itself be vacuous in a different way, which
> a human/agent re-reading the diff alone did not catch on the first pass.

> [from #1990, retro #1985 repair 1] Planned ops: A mutation check over a
> diff's newly added or changed tests: remove each production constant
> entry, unconditional emission, or branch the test's own docstring claims
> to cover, re-run the paired tests, and flag any element whose removal
> leaves the suite green. This row is what widens the umbrella's element
> set beyond a regex alternative.

> [from #1991, retro #1985 repair 3] Planned ops: The same mutation check
> #1990's row proposes, applied to a generator's emitted output rather
> than to a constant: remove each unconditional emission and each field a
> new test claims to cover, and flag any whose removal leaves the suite
> green. Verified in-tree -- the generator appends both literals in one
> unconditional list construction, so the containment assertion could not
> fail.

### Files

- `.github/scripts/gitapex_gate_defeat_test_mutation_coverage.py` (new)
- `.github/workflows/defeat-test-mutation-coverage-gate.yml` (new)
- `tests/test_gitapex_gate_defeat_test_mutation_coverage.py` (new)
- `.gitapex/ssot.json` (edit: append one `gates[]` entry)

### Design (binds this task; deviate only with a disclosed reason)

**Scope.** Union of the two existing gates' own in-scope directories:
`skills/*/scripts/*.py`, `.github/scripts/*.py`, `hooks/*.py`
(`test_*.py`/`conftest.py` excluded), matching
`gitapex_gate_function_body_test_coverage.py`'s own broader,
unprefixed precedent (issue #1799's own #1990/#1991 rows are both in
`hooks/`, which the narrower `detection_logic_property_coverage` scope
would not have reached either).

**Element categories graded** (issue #1799's own "any element a test's
own docstring or PR description claims to cover", operationalized
mechanically rather than by parsing natural-language claims -- see
"Why not parse docstrings" below):

1. **Regex alternation branch.** A `|`-joined top-level alternative
   inside a string literal argument to `re.compile(...)`/`re.match(...)`/
   `re.search(...)`/`re.fullmatch(...)` (module-qualified or
   receiver-agnostic, reuse `gitapex_gate_detection_logic_property_
   coverage.py`'s own `_re_module_names`/regex-trigger resolution
   verbatim rather than re-deriving it) that this diff newly adds or
   changes. Split only on `|` at paren-depth 0 (a `|` inside `(...)`,
   `[...]`, or after an unescaped `\` is not a top-level alternative);
   a pattern with no top-level `|` has no alternative to remove and is
   not graded under this category.
2. **Module-level dict/mapping-literal entry.** A key of an
   `ast.Dict` assigned to a module-level `ast.Name` target (a
   `CONST = {...}` shape, the repository's own pervasive constant-table
   idiom -- e.g. `REVIEW_PERSONA_PERMISSION`) where this diff newly adds
   or changes at least one key/value pair.
3. **Unconditionally emitted literal.** A string/literal element that
   is: (a) an item inside a `List`/`Tuple`/`Set`/`Dict` display that is
   itself unconditionally constructed (built directly inside a function
   body with no enclosing `If`/`Try`/loop-conditional guard around the
   literal's own containing display), or (b) the right-hand side of an
   unconditional keyword argument / dict entry emitted by a generator
   function (e.g. `"hidden": True` emitted with no surrounding
   conditional) -- newly added or changed by this diff. This category is
   necessarily the least mechanically crisp of the three (issue #1799's
   own #1991 row describes it by example, not by a closed grammar);
   grade only the narrow, unambiguous shape above and document the
   narrowing explicitly in the module docstring's own "Known misses"
   section, the same disclosure convention both existing sibling gates
   already use rather than silently overclaiming coverage.

**Why not parse docstrings.** issue #1799's own prose names "a test's own
docstring or PR description" as what claims coverage, but a natural-
language claim is not a machine-checkable input (the same reason
`gitapex_gate_function_body_test_coverage.py`'s own docstring gives for
checking "does this diff add a covering test" by AST identifier presence
rather than by reading English). Operationalize as: grade every category
1-3 element this diff newly adds or changes in an in-scope source file,
paired against whichever of `tests/test_{stem}.py` /
`tests/test_{stem}_properties.py` this same diff also adds or changes a
line in (`stem` = the source file's own basename without `.py`, exactly
`gitapex_gate_function_body_test_coverage.py`'s own `_stem`/
`_test_relative_paths` convention) -- reusing that gate's own "this same
diff must touch the test file too" scoping so a pre-existing, untouched
test can never silently satisfy this gate. A source element with no
diff-touched paired test file at all is not graded (nothing to mutation-
test against) -- disclose this as a known scope limit, not fixed here.

**Mutation mechanism** (the actual "real mutation" the operator chose):
for each graded element, build the mutated source text (AST-guided:
locate the exact byte range of the element via its node's
`lineno`/`col_offset`/`end_lineno`/`end_col_offset`, splice it out or
neutralize it, keeping the rest of the file byte-identical) and run it
against the paired test file with the on-disk source file replaced by
the mutated text for the duration of one subprocess `pytest` invocation
scoped to that specific paired test file (or, when identifiable, the
specific new/changed `test_`-prefixed function(s) this diff touches in
it, via `pytest <path> -k <name-expr>`), then restore the original bytes
in a `finally` block regardless of outcome (mirroring the
temp-overwrite-then-restore technique real mutation-testing tools such
as `mutmut`/`cosmic-ray` use). Read the original bytes into memory
*before* the first mutation and restore from that in-memory copy, never
by re-reading the file from disk after a prior mutation -- guards
against a first mutation's write clobbering the baseline a later
mutation restores to, if a restore is ever interrupted mid-run.
If the suite's own paired tests all still pass against the mutated
source, record a `defeat-test-mutation-gap` finding naming the element,
its category, and the paired test file that failed to catch it. Exit
codes: 0 clean, 1 a vacuous-coverage finding, 2 the scan could not be
trusted (malformed diff, an in-scope or paired-test file that cannot be
read/parsed, a `--root` that is not a directory, or a subprocess `pytest`
invocation that itself errors for a reason other than "tests ran and
passed/failed" -- e.g. a collection error) -- the same fail-closed
contract both sibling gates already state and justify by dimension 15 of
`skills/evaluating-deterministic-gate-quality/references/dimensions.md`.

**Diff parsing.** Reuse `parse_added_lines` (and its
`_diff_target_path`/`_looks_like_real_header_pair`/`_HUNK_RE`
machinery) verbatim from `gitapex_gate_function_body_test_coverage.py`
-- both existing sibling gates already carry byte-for-byte copies of it
rather than re-deriving it, and this gate's own module docstring should
say so explicitly the same way the function-body gate's docstring
credits its own copy.

**Waiver.** `# defeat-test-mutation-coverage: WAIVED: <reason>`, a
non-whitespace reason mandatory, detected via `tokenize` exactly like
both sibling gates' own `_WAIVER_RE`/`_waived_lines` (never a bare regex
over raw text, so a waiver string quoted inside this gate's own
docstring is never itself honoured as a real waiver).

**Runtime/CI cost, disclosed rather than hidden.** Unlike either sibling
gate (pure AST inspection), this gate spawns one `pytest` subprocess per
graded element, so its own CI job should carry a generous timeout and
this cost should be stated plainly in the module docstring's own
"Invocation shape" section (matching both sibling gates' own convention
of disclosing invocation shape and cost trade-offs there) -- not solved
by artificially capping the element count within this task.

**Known, disclosed non-goals** (state these in the module docstring
exactly, not merely in this plan file, so a future reader is never
surprised by them -- the same "Known misses"/"Known over-reports"
disclosure convention both sibling gates already use):

- **"The suite" is scoped to the paired co-located test file(s) only**,
  never the full repository test suite. issue #1799's own #1991 row
  states the residual risk directly: "running only the file's own tests
  would miss a cross-file assertion, and running everything is slow."
  This task accepts the narrower, fast scope and documents the miss
  rather than resolving it.
- **Emit-only spelling assertions are out of scope for this mechanism.**
  issue #1799's own body states this directly: "an assertion that
  compares only an emitted spelling is not caught by a
  remove-and-confirm-failure pass, because a mutation that changes the
  emitted string does fail it. Catching that one needs a parse assertion
  beside the spelling assertion... which is a different check from
  mutation testing." Do not attempt to implement that different check
  under this gate's own name; state the non-goal in the docstring instead.

### Registration

Append one entry to `.gitapex/ssot.json`'s `gates` array, matching the
existing `detection-logic-property-coverage`/`function-body-test-
coverage` entries' own shape exactly: `id: "defeat-test-mutation-
coverage"`, `kind: "script"`, `script` listing the gate script + its
workflow (+ `gitapex_run_base_diff.py`/`_gitapex_base_ref.py` if the
chosen CI invocation reuses them the same way both sibling gates do),
`rule` (prose summary of the mechanism above), `planes: ["ci", "local"]`
if a local invocation is wired, `local_invocation`/`local_stdin` mirroring
the sibling gates' own `uv run --frozen python3 <script>` /
`gitapex_run_base_diff.py -- '*.py'` pair, `trigger` naming the new
workflow file, `policy_refs: []`, `cluster: "test-integrity"` (same
cluster both sibling gates use), `tracking_issue: 1799`, `status:
"active"`, `supersedes: null`, `bypass_review_status:
"not-yet-reviewed"`, and a `target` array listing the graded file globs,
the paired-test-file glob, a `cross-registry-consistency` entry
describing the source<->test pairing this gate checks, and the new
workflow's own `pull_request` event.

### Proof method (binds this task; do not report complete without it)

1. Construct fixtures reproducing all three graded element categories in
   a shape mirroring issue #1799's own six rows: (a) a regex with a
   branch a paired test's assertion never actually reaches (mirroring
   #1733/#1735's own `_CONTAINER_PREFIX`-shaped CR-alternative gap), (b)
   a module-level dict constant with an entry no assertion anywhere
   names (mirroring #1990's `REVIEW_PERSONA_PERMISSION`-shaped gap), (c)
   an unconditionally-emitted literal a test only checks with a
   type/non-emptiness assertion rather than an exact-value one
   (mirroring #1991's `hidden: true`-shaped gap).
2. Confirm the new gate reports a `defeat-test-mutation-gap` finding
   against each vacuous fixture (red).
3. Fix each fixture's own paired test to genuinely assert the mutated
   element (an exact-match or parse-back assertion, not merely
   type/non-emptiness), and confirm the gate reports clean against the
   fixed fixture (green) -- this is the "reintroduced instance of the
   original defect" proof method every one of issue #1799's own six ACM
   rows requires verbatim.
4. Full repo verification (`gitapex_gate_local_preflight.py` plus the
   full `pytest` suite, ruff lint, mypy) green inside this task's own
   worktree before reporting complete, per this skill's own Decision 20
   requirement.
5. Confirm the new CI workflow file passes `actionlint`/`zizmor` shape
   (or whatever this repository's own CI-workflow validation already
   runs against every `.github/workflows/*.yml` file) rather than being
   graded only by eye.

### Residual risk

The three element categories chosen (regex alternation / dict entry /
unconditional literal) are the ones issue #1799's own six rows evidence
directly; a vacuous test defeating some other shape of production logic
(a conditional branch with no regex/dict/literal shape at all, for
instance) is not covered by this gate and is not claimed to be --
disclose this plainly in the module docstring's own "Known misses"
section rather than overclaiming a general vacuous-test detector.

## Operations note

This file is the task-list commit (this skill's own step 4): commit it
alone first, then push, before opening the draft PR (step 5).

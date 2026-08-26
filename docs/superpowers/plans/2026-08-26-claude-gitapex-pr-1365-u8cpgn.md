# Add a real-bash differential oracle for the bash-safety classifiers (issue #1365)

**Goal:** (1) A reusable, safe real-bash oracle harness (`tests/_gitapex_bash_oracle.py`)
that pins ~20 existing hand-verified "confirmed live via a real bash proxy"
docstring claims in both bash-safety classifiers as real, executed
regression tests. (2) A generative differential Hypothesis property test
per classifier, closed to a safe input grammar, asserted one-directionally
against each classifier's own real `Verdict` shape. (3) A non-blocking
scheduled deep-scan workflow mirroring issue #1316's own precedent.
Source: https://github.com/tvna/gitapex/issues/1365.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker on
issue #1365's own body (2026-08-26T21:57:36Z). One Facts-section claim did
not hold up and is corrected: the sibling classifier
(`skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py`)
does **not** skip `gh`/`git` entirely as the issue's Facts bullet states --
it has two dedicated blanket-match rule functions independent of the
4-verb install/exec table: `_rule_gh_any` (denies any `gh` subcommand,
`:2232-2271`) and `_rule_git_push` (hard-denies `git push`, `:2432-2483`).
Only the literal `_WATCHED_VERBS` table excludes `gh`/`git`; the module as
a whole does not. This changes task-6's own generation grammar (must also
generate `gh`/`git push` shapes, not only the 4-verb install/exec
vocabulary) relative to a literal reading of the issue body. All other
Facts-section claims (hooks-classifier git-push warn/deny, the 3-vs-4
`KNOWN_BYPASS_COMMANDS` comment-drift bug, the absent stand-in-argv-capture
harness, the `slow` marker and `_PROPERTIES`/deep-scan-workflow
conventions) were independently re-checked directly against source this
session and confirmed accurate as stated.

**File-ownership check (mechanized):**
`gitapex_check_file_ownership_conflicts.py` against the 7 tasks' file lists
below -> no conflicts (disjoint files).

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 7 changed paths ->
`hooks/test_gitapex_check_bash_safety.py` hook-script match (expected --
this is the existing test file for a registered gate's own PreToolUse
classifier), `.github/workflows/bash-safety-differential-deep-scan.yml`
workflow match (expected -- new scheduled workflow), 5 test files
no-match (needs the model's own full-diff review). Full model review
(the untrusted-input-triage Extract/Ignore/Flag/Tag pass over the ACM's
own text, step 2 of `executing-a-branch-plan`, plus per-task screening at
each task's own diff, step 6) still runs regardless, per the script's own
"never itself grounds to skip" rule -- nothing in the issue's Facts,
Proposed solution, or Acceptance Criteria text reads as an injected
instruction rather than a change description.

**Interface-dependency edges:**
- task-2, task-3, task-5, task-6 each import task-1's shared oracle
  harness (fixture + runner + parser) -- sequenced after task-1.
- task-7 (CI workflow) names task-5's and task-6's exact file paths and
  its own local-verification step confirms those files are collected and
  pass -- sequenced after both.
- task-4 (comment-drift fix in `hooks/test_gitapex_check_bash_safety.py`)
  touches only a comment block, not `KNOWN_BYPASS_COMMANDS`'s own name or
  contents -- no interface edge with task-5 (which imports that stable,
  unchanged symbol) or any other task. Independent.

**Waves:** wave 1: {task-1, task-4} (no edge between them). wave 2:
{task-2, task-3, task-5, task-6} (each edges only on task-1, already
complete by wave 1; no edges among themselves -- disjoint files, no
producer/consumer relationship between the mechanical pin tests and the
generative differential tests). wave 3: {task-7} (edges on task-5 and
task-6).

**Execution mode:** `Workflow` tool, one run per wave, `agentType:
'branch-plan-task'`, `isolation: 'worktree'` for each task `agent()` call --
this session has ultracode explicitly enabled (system-confirmed
opt-in for multi-agent orchestration), unlike the sequential-fallback
precedent recorded in `docs/superpowers/plans/2026-08-25-claude-pr-1316-prep-0131jz.md`,
which had no such opt-in. Step 8's refactor and adversarial-review passes
use a fresh `Agent`-tool subagent dispatch each (not `Workflow`), per this
skill's own step 8 shape, at a stronger-reasoning tier and this session's
default-or-higher effort (described model-agnostically, no specific model
identifier written into this tracked file).

**Irreversibility classification:** none of the seven tasks are
irreversible -- all are ordinary, git-revertible new-file additions or a
comment-only edit inside this repository; no data deletion, no live
external write, no schema migration. No task requires a fresh per-task
authorization confirmation beyond the branch-plan-wide one recorded below.

**Authorization record (step 1):** structural precondition PASS
(`gitapex_check_branch_plan_reverified.py` against issue #1365's live body --
the `planning-a-branch-from-an-issue` re-verification marker is present,
timestamp 2026-08-26T21:57:36Z). Semantic approval: in-session explicit
confirmation from the human operator, directly instructing "この[issue #1365
の]PRを作りマージ直前まで進める" (create this PR for issue #1365 and drive it
to just before merge) against the issue's own URL -- unambiguous, directly
responsive to this specific issue and branch plan, no embedded instruction
attempting to redirect this gate. No pre-existing approval comment exists
on issue #1365 (filed and re-verified this same session).

## Task 1 -- Shared real-bash oracle harness

**Cites ACM row:** Row 1 (safe, reusable real-bash oracle harness).

**Quoted Planned ops (verbatim from the issue body):** "Add
`tests/_gitapex_bash_oracle.py`; add pinned-command test coverage in the
two existing property files or a small new file per classifier; fix the
\"these identical 4 cases\" comment-drift bug in
`hooks/test_gitapex_check_bash_safety.py` in the same change since it
touches the same list"

**Files:** `tests/_gitapex_bash_oracle.py` (new).

**Design, fixed at decomposition time:** underscore-prefixed shared-module
convention (matching `skills/executing-a-branch-plan/scripts/_gitapex_path_normalize.py`'s
own naming precedent, even though this prefix convention does not yet
exist elsewhere in `tests/`). Provide:
- A fixture/helper that, given a list of watched tool names and a
  `tmp_path`/`tmp_path_factory`-rooted per-test temp directory, writes one
  inert stand-in script per tool name into that directory (each script
  only appends its own invoked argv, one line, to a caller-specified
  capture file path, then exits 0 -- no `eval`, no interpretation of its
  own arguments).
- A runner that invokes `bash` by its own resolved absolute path (resolve
  once via `shutil.which("bash")`, never rely on PATH lookup for the
  interpreter itself, since the child's own PATH is being fully replaced)
  with: `PATH` set to *only* the stand-in directory (never prepended to
  the real PATH, never a relative path), `LC_ALL=C`, an otherwise-minimal
  environment (do not inherit the parent's full `os.environ` — build an
  explicit minimal dict), a disposable empty working directory distinct
  from both the stand-in directory and the capture-file's own directory,
  a hard wall-clock timeout (e.g. 5 seconds), the child launched in its
  own process group (`start_new_session=True` on `subprocess.run`/`Popen`)
  so that on timeout the *whole group* is killed via `os.killpg` (catch
  `subprocess.TimeoutExpired`, then killpg, then re-wait) rather than only
  the direct `bash` child, and an optional `preexec_fn` resource-limit
  prologue (`resource.setrlimit(resource.RLIMIT_CPU, ...)` and
  `resource.setrlimit(resource.RLIMIT_NPROC, ...)` or equivalent) as a
  defense against a pathological fork-bomb-shaped generated command --
  document this as defense-in-depth, not a substitute for the generation
  grammar's own closure (task-5/6's job, not this task's).
- A parser turning the capture file's own contents back into an ordered
  `list[tuple[str, list[str]]]` of `(tool_name, argv)` observations (argv
  split however the stand-in script itself serializes it -- pick a simple,
  unambiguous format, e.g. one JSON array per line, and document it in
  this module's own docstring since task-2/3/5/6 all depend on this exact
  format).
- Must be safe under `pytest-xdist -n auto` (already the repo's
  `addopts`): never use a fixed/shared path for the stand-in directory or
  capture file -- always derive from the per-test `tmp_path` fixture (or
  `tmp_path_factory` for a session/module-scoped variant if one is
  needed), so two workers running concurrently never collide.

**Proof method:** unit tests directly in this module or a small
accompanying test file, asserting: (a) a stand-in-only tool name resolves
and its stub runs, while a real system binary name not present in the
stand-in directory does NOT resolve (confirms the real system `PATH` is
genuinely unreachable from inside the oracle -- e.g. assert invoking a
real system tool like `ls` by name, with only the stand-in PATH active,
fails to find it); (b) two concurrent/parallel invocations (e.g. via
`tmp_path_factory` in two test functions, or literally run under
`pytest-xdist`) do not share a stand-in directory or capture file path;
(c) a deliberately slow-sleeping generated command is killed by the
timeout (assert the process group is actually terminated, not just the
direct child, e.g. by having the stand-in spawn a background child of its
own and confirming it doesn't survive). Run via
`uv run --frozen pytest tests/_gitapex_bash_oracle.py -v` (or wherever the
accompanying tests land) plus `uv run --frozen pytest tests/ -k oracle -v`.

## Task 2 -- Pinned regression tests for the hooks classifier

**Cites ACM row:** Row 1 (the ~20 existing hand-verified findings become
real, executed regression tests).

**Quoted Planned ops (verbatim from the issue body):** "add pinned-command
test coverage in the two existing property files or a small new file per
classifier"

**Files:** `tests/test_gitapex_check_bash_safety_oracle_pins.py` (new).

**Design, fixed at decomposition time:** grep
`hooks/gitapex_check_bash_safety.py`'s own docstrings for every "confirmed
live via a real bash proxy", "confirmed via bash -c argv expansion", and
"confirmed live via real bash argv expansion" citation (there are 20+ per
issue #1365's own Problem section -- enumerate the actual call sites and
their exact cited command strings directly from source, do not guess the
count). For each one, write a regression test that: builds task-1's oracle
harness for `hooks/gitapex_check_bash_safety.py`'s own watched tool
vocabulary, runs the cited exact command string through it, and asserts
the real-bash observation matches what the docstring comment already
claims (e.g. an obfuscated verb resolving to the real denied tool/verb
pair; a `git push` shape resolving such that `is_git_push` should end up
true). Then additionally call `classify()` directly on that same command
string and assert its `Verdict` matches what the citation already claims
the module does (deny/warn/neither) -- this is the "regression-pin test
that turns out vacuous against pre-fix code" gap issue #1359's own Repair
24 named; a test that only checks the oracle's raw observation without
also checking `classify()`'s own verdict against it would be exactly that
vacuous shape.

**Proof method:** `uv run --frozen pytest tests/test_gitapex_check_bash_safety_oracle_pins.py -v`
-- every pinned assertion passes, reproducing its source docstring
comment's own claimed outcome exactly. Report the final count of pinned
cases in the task's own commit message.

## Task 3 -- Pinned regression tests for the sibling (task-scoped) classifier

**Cites ACM row:** Row 1 (the ~20 existing hand-verified findings become
real, executed regression tests -- applies to both classifier files per
the issue's own Problem section, which cites both).

**Quoted Planned ops (verbatim from the issue body):** "add pinned-command
test coverage in the two existing property files or a small new file per
classifier"

**Files:** `tests/test_gitapex_check_task_bash_safety_oracle_pins.py` (new).

**Design, fixed at decomposition time:** same method as task-2, but
against `skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py`'s
own docstring citations and its own watched tool vocabulary (13
`_WATCHED_TOOLS` + `_WATCHED_VERBS` install/exec set, `_FETCH_EXEC_INTERPRETERS`/
`_FETCH_EXEC_WRAPPERS`, plus its separate `_rule_gh_any`/`_rule_git_push`
blanket rules). This classifier's `Verdict` is two-valued (`deny`, `reason`
-- no `is_git_push` field), so each pinned test asserts only `deny`.

**Proof method:** `uv run --frozen pytest tests/test_gitapex_check_task_bash_safety_oracle_pins.py -v`
-- every pinned assertion passes. Report the final count of pinned cases
in the task's own commit message.

## Task 4 -- Fix the "these identical 4 cases" comment-drift bug

**Cites ACM row:** Row 1 (Planned ops: "fix the comment-drift bug ... in
the same change since it touches the same list").

**Quoted Planned ops (verbatim from the issue body):** "fix the \"these
identical 4 cases\" comment-drift bug in
`hooks/test_gitapex_check_bash_safety.py` in the same change since it
touches the same list"

**Files:** `hooks/test_gitapex_check_bash_safety.py` (comment block only,
around lines 305-317 -- confirm exact current line numbers before editing,
since task-1/2/3's own work in other files does not shift this file's
lines, but re-read it directly rather than trusting this plan's cached
line numbers).

**Design, fixed at decomposition time:** the comment currently claims this
file's own adjacent `KNOWN_BYPASS_COMMANDS` list pins "these identical 4
cases" matching the sibling test file's own list. Re-verified this
session: this file's own list has 3 entries
(`string-slice-reconstruction-uv-install`,
`array-literal-assignment-indirection`,
`graphql-mutation-keyword-variable-concatenation`); the sibling's list
(`skills/executing-a-branch-plan/scripts/test_gitapex_check_task_bash_safety.py`)
has 4 (`string-slice-reconstruction-pip-install`,
`array-literal-assignment-indirection`,
`fetch-exec-sudo-separate-value-flag-not-skipped`,
`array-literal-subscript-of-a-real-array-whose-own-element-is-empty`) --
only `array-literal-assignment-indirection` is actually shared. Rewrite
the comment to state the real relationship (3 entries here, 4 in the
sibling, only one case-id in common) instead of claiming identity. Do not
touch the `KNOWN_BYPASS_COMMANDS` list itself or any other test in this
file.

**Proof method:** `uv run --frozen pytest hooks/test_gitapex_check_bash_safety.py -v`
-- full existing suite still green (comment-only change, no behavior
change). Visually diff the corrected comment against the two actual lists
to confirm the new text is accurate.

## Task 5 -- Differential property test, hooks classifier

**Cites ACM row:** Row 2 (generative differential property test per
classifier).

**Quoted Planned ops (verbatim from the issue body):** "Two new test files
... each importing Phase 1's shared harness but each defining its own
Hypothesis strategy over its own classifier's watched vocabulary (the
hooks file's `gh`/`git` plus write-flag/verb set...) and its own assertion
shape ... tri-valued for the hooks file (an oracle-observed denied-write
shape must make `classify().deny` true; an oracle-observed `git push` must
make `classify().is_git_push` true...)"

**Files:** `tests/test_gitapex_check_bash_safety_differential.py` (new).

**Design, fixed at decomposition time:** import task-1's oracle harness.
Define a Hypothesis strategy generating bash command strings over
`hooks/gitapex_check_bash_safety.py`'s own watched vocabulary (`gh`/`git`
subcommands and the write-flag/verb set its own rule functions check --
read the module's own `_DENIED_ADJACENT` table and rule functions directly
to enumerate this rather than guessing) plus assignment, quoting, `$IFS`
reassignment (including case variation), array-literal, and bounded
command-substitution/process-substitution nesting (hard cap the nesting
depth, e.g. 2). The grammar MUST NOT ever generate: a free redirection
operator, backgrounding (`&`), unbounded `(...)`/`$(...)` nesting, or any
shell-builtin name (`exec`, `eval`, `trap`, `kill`, `ulimit`, `:`, `wait`,
`source`, `.`) in command-word position -- enforce this by construction in
the strategy itself (e.g. a fixed, curated set of command words to draw
from that excludes builtins, never free-text for the command-word
position). Decoy identifiers: a small curated inert set (e.g.
`["foo", "bar", "baz", "x", "y"]`), not `st.text(alphabet=...)`-style free
text. Exclude `KNOWN_BYPASS_COMMANDS` membership via exact-string
`hypothesis.assume()` against both classifier files' own lists (import
them, do not hardcode a copy) -- never shape-matched.

For each generated command: run it through task-1's oracle to get the
real-bash `(tool, argv)` observations, then call
`hooks.gitapex_check_bash_safety.classify()` (adjust the import path to
however that module is actually importable -- check for an existing
`sys.path`/`conftest.py` convention the sibling non-differential property
file already uses) on the same command string. Assert ONE DIRECTION ONLY:
if the oracle's own observation shows a denied-write shape actually
reached a watched tool with a denied verb, then `classify().deny` must be
`True`; if the oracle's own observation shows a real `git push` shape
resolved, then `classify().is_git_push` must be `True`. Never assert the
converse (a classifier `deny`/`is_git_push` with no matching oracle
observation is not a failure -- the oracle's own minimal environment can
diverge from a real session's).

Mark the test function(s) `@pytest.mark.slow`. Use the exact `_PROPERTIES`
pattern from `tests/test_gitapex_gate_detection_logic_property_coverage_properties.py:123-137`
(`derandomize=True, max_examples=200, deadline=None` normally;
`derandomize=False, max_examples=5000, deadline=None` when
`os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"`).

**Proof method:** `uv run --frozen pytest tests/test_gitapex_check_bash_safety_differential.py -v`
green at default settings; measure and report actual wall-clock time.
Additionally, as a manual (not committed) verification: temporarily
neutralize one specific already-fixed rule in a scratch copy of
`hooks/gitapex_check_bash_safety.py` (never committed) and confirm this
differential test actually fails against that scratch copy -- proving the
oracle has teeth, not green-by-vacuity. Report the specific rule
neutralized and the failure observed in the task's own commit message.

## Task 6 -- Differential property test, sibling (task-scoped) classifier

**Cites ACM row:** Row 2 (generative differential property test per
classifier), corrected per this plan's own re-verification note above.

**Quoted Planned ops (verbatim from the issue body):** "Two new test files
... each importing Phase 1's shared harness but each defining its own
Hypothesis strategy over its own classifier's watched vocabulary (...the
sibling's install/exec verbs plus its fetch-pipe-to-interpreter family)
and its own assertion shape ... the sibling's two-valued `Verdict` needs
only the first [deny]"

**Files:** `tests/test_gitapex_check_task_bash_safety_differential.py`
(new).

**Design, fixed at decomposition time:** same harness/grammar-closure
approach as task-5, but against
`skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py`.
**Important correction from this plan's own re-verification (do not follow
the issue body literally on this point):** this classifier's Hypothesis
strategy must generate not only the 4-verb install/exec vocabulary
(`_WATCHED_TOOLS` x `_WATCHED_VERBS`) and the fetch-pipe-to-interpreter
family (`_FETCH_EXEC_INTERPRETERS`/`_FETCH_EXEC_WRAPPERS`), but ALSO
`gh <subcommand>` and `git push` shapes, since `_rule_gh_any` and
`_rule_git_push` deny those independently of the verb table -- omitting
them would leave a real, silent coverage gap on exactly the two rule
families the issue's own Facts section got wrong. The sibling's own
strategy additionally never emits a real network-capable command word
(only the PATH-restricted stand-ins), since fetch-pipe-to-interpreter is
this file's own watched domain by design. `Verdict` here is two-valued, so
the assertion checks only `deny`. Exclude this file's own 4-entry
`KNOWN_BYPASS_COMMANDS` list via exact-string `assume()` (import it, do
not hardcode a copy).

Mark `@pytest.mark.slow`; same `_PROPERTIES` pattern as task-5.

**Proof method:** same shape as task-5 -- local green run, wall-clock time
reported, and a manual (not committed) neutralize-one-rule verification
(e.g. temporarily neutralizing `_rule_git_push` or one of the
`DENIED_INDIRECTION_COMMANDS`-family fixes in a scratch, never-committed
copy) confirming the differential actually fails against it. Report the
specific rule and failure observed in the task's own commit message.

## Task 7 -- Non-blocking scheduled deep-scan workflow

**Cites ACM row:** Row 3 (non-blocking rollout mirroring issue #1316's
precedent).

**Quoted Planned ops (verbatim from the issue body):** "wire both into
`diff-parsing-property-deep-scan.yml`'s sibling workflow (a new
`bash-safety-differential-deep-scan.yml`, same shape,
`GITAPEX_HYPOTHESIS_DEEP_SCAN=1`-gated, `derandomize=False,
max_examples=5000`, `permissions: contents: read`, no network)"

**Files:** `.github/workflows/bash-safety-differential-deep-scan.yml`
(new).

**Design, fixed at decomposition time:** copy
`.github/workflows/diff-parsing-property-deep-scan.yml`'s exact shape:
harden-checkout action pinned to the identical SHA already used there,
`astral-sh/setup-uv` pinned to the identical version/SHA already used
there, `schedule:` cron at a distinct offset from every existing scan
cron in `.github/workflows/*.yml` (list them first, pick a genuinely free
slot -- do not guess), `workflow_dispatch: {}`, `permissions: contents:
read` at both top level and job level, a `concurrency` group keyed on
`github.workflow`, `GITAPEX_HYPOTHESIS_DEEP_SCAN: "1"` env, runs task-5's
and task-6's exact two new differential test files with `--no-cov`,
captures output to `$GITHUB_STEP_SUMMARY`. No new required-status-check
registration -- both differential files already run in the normal
PR-blocking `pytest` job automatically (already under `tests/`, already in
`testpaths`); confirm this locally via
`uv run --frozen pytest tests/ -k differential -v` completing at the
default fast settings, no special wiring needed for that part.

**Proof method:** YAML syntax/schema validity (e.g.
`python3 -c "import yaml; yaml.safe_load(open('...'))"` or the repo's own
`actionlint`/`zizmor` convention if invoked as part of normal CI); local
confirmation that both differential test files are collected and pass
under `uv run --frozen pytest tests/ -k differential -v`. Actual scheduled
dispatch and completion against the real branch is deferred to
`drafting-a-pr-to-merge`'s own CI-driving loop, since the workflow cannot
be manually dispatched against a ref that does not yet exist on the remote
until this branch is pushed (same deferral pattern as
`docs/superpowers/plans/2026-08-25-claude-pr-1316-prep-0131jz.md`'s own
task-3).

## Post-task gate (Decision 12, mandatory)

After all seven tasks land: one refactor/simplify pass (behavior-preserving
only) and one independent adversarial code review, each a fresh `Agent`-tool
subagent dispatch at a stronger-reasoning tier and this session's
default-or-higher effort, over the full accumulated diff. Given this
change is explicitly safety-critical (a differential oracle for the
PreToolUse bash-safety gate itself), the adversarial review must confirm,
at minimum: (a) task-1's oracle harness is genuinely safe under the
process-group/timeout/PATH-replacement/resource-limit design above --
construct at least one case built to defeat it (e.g. a generated command
attempting to escape the process group, or a builtin invocation) before
clearing it, per `refactor-and-review-gate.md`'s own defeat-test
requirement; (b) task-5/6's own grammar closure is genuinely closed (no
free redirection, no backgrounding, no unbounded nesting, no builtin
command words reachable) -- attempt to construct a counterexample the
strategy could still generate that would defeat the closure; (c) task-5/6's
assertion direction is genuinely one-directional (never asserts the
converse); (d) task-2/3's pinned tests genuinely call `classify()` and
assert its verdict, not only the oracle's raw observation (the
Repair-24-vacuity check); (e) task-7's new workflow cannot leak
`GITAPEX_HYPOTHESIS_DEEP_SCAN=1` into the PR-blocking gate's own default
settings under any normal CI invocation. Every CONFIRMED finding is fixed
and every task's own proof-method test is re-run (not only the one related
to the fix) before the draft PR converts to ready-for-review.

# Branch plan: environment/repo-state preconditions mechanism

Issue #1566. Branch `claude/gate-preconditions-mechanism-c0wevy`.

Consolidates: #1547 (side a only), #1546, #1489, #1508 -- all four closed
as duplicates of #1566. Root cause shared across all four: no shared
mechanism establishes environment/repo-state preconditions (full git
history vs. a shallow clone, a required dependency being installed, a
dispatched worktree's merge-base) before this repository's gates run.

## Decomposition

Four tasks. Task 1 is foundational for Tasks 2 and 3 (they read the
`preconditions` field shape it establishes in `.gitapex/ssot.json`); Task
4 is fully independent (its own fix lives entirely inside
`skills/executing-a-branch-plan/`, uses no `ssot.json` field at all, and
shares no file with any other task).

### Task 1: `preconditions` field in the gate registry (schema + two gate entries)

Owns:
- `.gitapex/ssot.schema.json` (edit)
- `.gitapex/ssot.json` (edit: `meta.schema_version` bump, two `gates[]`
  entries gain a `preconditions` field)
- `.github/scripts/gitapex_scan_ssot_schema.py` (edit: pydantic `Gate`
  model)
- `tests/test_gitapex_scan_ssot_schema.py` (edit: new/updated cases)

Planned ops (quoted from the re-verified ACM this branch plan is built
from -- see issue #1566's own `Consolidates:` table, rows 2/3 and 1):

> Add an optional `preconditions` object property to the `gate` $defs in
> `.gitapex/ssot.schema.json` (`additionalProperties: false` throughout,
> matching every other object in that schema), with two documented,
> optional sub-keys: `requires_full_history` (boolean) and
> `requires_python_packages` (array of non-empty strings, `minItems: 1`
> when present). Bump `.gitapex/ssot.json`'s own `meta.schema_version`
> from `"1.4.0"` to `"1.5.0"` per the schema file's own docstring
> ("Adding a field is a schema_version bump, never a silent addition").
> Add `"preconditions": {"requires_full_history": true}` to the
> `harden-checkout-pin-drift` gate entry (closes #1546/#1489 -- this is
> the only currently-wired local-plane gate that needs full git-log depth
> to resolve a pinned action SHA's true last-touching commit; confirm this
> scoping is still accurate by re-reading
> `.github/scripts/gitapex_scan_harden_checkout_pin_drift.py` directly
> rather than trusting this plan's own prior read). Add
> `"preconditions": {"requires_python_packages": ["pydantic"]}` to the
> `skill-audit-disclosure` gate entry (closes #1547(a) -- this gate's
> `.github/scripts/gitapex_gate_skill_audit_disclosure.py` transitively
> imports pydantic via `gitapex_compute_skill_audit_flags.py` ->
> `gitapex_detect_changed_gate_scripts.py`). Update
> `gitapex_scan_ssot_schema.py`'s own pydantic `Gate` model (read that
> file directly first to confirm its exact current field set) with a
> matching optional `preconditions` field/submodel so a
> `preconditions`-carrying entry does not fail that script's own stricter
> parse (duplicate-id detection etc.) -- this script is a
> `.github/scripts/` file and may use pydantic freely.

Proof method: `uv run --frozen python3 .github/scripts/gitapex_scan_ssot_schema.py`
passes against the edited registry; `tests/test_gitapex_scan_ssot_schema.py`
gains a case asserting a `preconditions`-carrying gate entry validates
against both the JSON Schema and the pydantic model, and a case asserting
an entry with an unrecognized precondition sub-key is rejected
(`additionalProperties: false`).

Irreversibility: none (schema/registry edits, additive fields, all plain
`git revert`-able).

### Task 2: shallow-clone auto-establish in `gitapex_gate_local_preflight.py`

Owns:
- `.github/scripts/_gitapex_preconditions.py` (new)
- `.github/scripts/gitapex_gate_local_preflight.py` (edit)
- `tests/test_gitapex_gate_local_preflight.py` (edit)
- `tests/test__gitapex_preconditions.py` (new)

Depends on Task 1 (reads the `preconditions.requires_full_history` field
shape Task 1 establishes in `.gitapex/ssot.json` -- interface edge, must
run after Task 1 merges).

Planned ops (quoted from the re-verified ACM, rows 2/3 -- #1546 and
#1489, duplicate reports of the identical defect):

> Add `.github/scripts/_gitapex_preconditions.py` (a `.github/scripts/`
> file, may use pydantic/jsonschema freely -- only `hooks/` must stay
> stdlib-only) providing `is_shallow_clone(repo_root)` (wraps `git
> rev-parse --is-shallow-repository`) and `ensure_full_history(repo_root)`
> (runs `git fetch --unshallow`, raising a typed error naming the
> underlying failure on a non-zero exit -- never swallowed).
>
> Modify `gitapex_gate_local_preflight.py`'s `main()` (or a helper it
> calls before `run_checks`): after `load_local_checks` discovers the
> wired set, read `.gitapex/ssot.json` directly (or extend
> `load_local_checks`'s own registry parse) for whether ANY wired gate
> declares `preconditions.requires_full_history: true`. If so, call
> `is_shallow_clone`; if the repo is shallow, call
> `ensure_full_history` ONCE before running any wired gate. If that
> fetch itself fails, print one clear top-line message (naming the
> underlying git error) and exit 1 immediately -- never let the failure
> surface only reactively via one specific gate's own error text partway
> through the run (#1489's own explicit ask). Skip the fetch call
> entirely when the repo already reports non-shallow (no wasted network
> call on every ordinary run -- #1546's own explicit residual-risk note).
>
> This must not change behavior for a repo that is already non-shallow,
> or for a wired set where no gate declares the precondition at all --
> both cases must run exactly as before, with no new git subprocess
> invoked.

Proof method: new tests in `tests/test_gitapex_gate_local_preflight.py`
(and/or the new `tests/test__gitapex_preconditions.py`) using a fixture
shallow git repo (e.g. a local bare repo, then `git clone --depth 1`
from it into a tmp dir) confirming (a) `main()` auto-runs the unshallow
fetch and the repo reports non-shallow before any wired gate executes,
(b) a single clean top-line abort message (and exit 1) when the fetch
itself fails (e.g. the bare origin is deleted/unreachable before the
fetch runs), (c) no fetch subprocess is invoked at all when the repo
already reports non-shallow. Confirm test (a) or a live-equivalent
reproduces the exact original defect (a shallow clone reaching
`harden-checkout-pin-drift` directly, pre-fix, still fails with the
shallow-clone RuntimeError) before the fix, and passes after.

Irreversibility: none (new file, additive pre-check in an existing
script, no destructive git operation -- `git fetch --unshallow` is
additive/non-destructive).

### Task 3: dependency-precondition fail-closed in `check-pr-skill-audit-disclosure.sh`

Owns:
- `hooks/gitapex_check_python_precondition.py` (new)
- `hooks/check-pr-skill-audit-disclosure.sh` (edit)
- `hooks/test_gitapex_check_pr_skill_audit_disclosure_shell.py` (edit)
- `hooks/test_gitapex_check_python_precondition.py` (new)

Depends on Task 1 (reads the `preconditions.requires_python_packages`
field shape Task 1 establishes on the `skill-audit-disclosure` gate entry
-- interface edge, must run after Task 1 merges).

Planned ops (quoted from the re-verified ACM, row 1(a) -- #1547 side a
only; side b, the regex footgun, is explicitly out of scope for this
issue, covered by a separate umbrella):

> Add `hooks/gitapex_check_python_precondition.py`: stdlib-only (no
> third-party import of its own -- it exists specifically to answer "is a
> third-party package importable" without needing that package itself),
> following the `hooks/gitapex_check_*.py` naming convention. Given one or
> more module names, probes importability via a subprocess (`python3 -c
> "import <mod>"`, never the calling process's own `import`, so a missing
> module cannot crash this checker itself) and reports which are missing.
> Read `hooks/gitapex_check_skill_audit_disclosure_or_waiver.py` first for
> this repository's own stdlib-only hook-script conventions (JSON
> in/out shape, exit-code discipline) before writing this sibling.
>
> Modify `hooks/check-pr-skill-audit-disclosure.sh`'s tier-1 block
> (currently around the `python3 "$full_gate" --check-diff ...`
> invocation): before attempting that bare invocation, read
> `.gitapex/ssot.json`'s `skill-audit-disclosure` gate entry's own
> `preconditions.requires_python_packages` (via `jq`, matching this
> hook's existing JSON-handling convention) and invoke
> `gitapex_check_python_precondition.py` against that package list. If
> any required package is not importable, `deny()` immediately with an
> actionable message telling the caller to run `uv sync --group dev` (or
> re-invoke the affected command after that), instead of proceeding to
> attempt the tier-1 invocation and falling through to the existing
> "could not complete the full local pre-check ... falling back to the
> bundled base two-audit check" warning path. Every OTHER tier-1 failure
> cause (unresolvable git state, an unreadable registry, a bug in the
> gate script itself producing no recognizable `FAIL:` line) must keep
> falling through to tier 2 with a warning exactly as today -- this fix
> is narrowly scoped to the dependency-missing cause only, per the ACM's
> own Interpretation column ("rather than failing loudly or
> self-provisioning its own dependency" -- fail loudly is the chosen
> half; do not also attempt self-provisioning, which would mean running
> an install command from inside a PreToolUse hook, out of scope and
> against this repository's own hook-permission model).

Proof method: new/extended cases in
`hooks/test_gitapex_check_pr_skill_audit_disclosure_shell.py` (or a
focused new sibling) that (a) simulate the precondition-missing case
(e.g. point the precondition check at a deliberately-unimportable module
name, or stub the registry's declared package list) and confirm the hook
denies with the actionable `uv sync --group dev` message rather than
warning-and-falling-through; (b) confirm a genuinely unrelated tier-1
failure (e.g. an unresolvable `merge-base`, matching an existing test's
own fixture) still falls through to tier 2 unchanged, proving the fix did
not widen scope. `hooks/test_gitapex_check_python_precondition.py`
unit-tests the new stdlib-only probe directly (an importable stdlib
module reports importable; a deliberately-fake module name reports
missing).

Irreversibility: none (new stdlib-only file, an added early-exit branch
in an existing hook -- no destructive operation).

### Task 4: worktree merge-base assertion at task dispatch

Owns:
- `skills/executing-a-branch-plan/scripts/gitapex_check_task_worktree_base.py` (new)
- `skills/executing-a-branch-plan/scripts/test_gitapex_check_task_worktree_base.py` (new)
- `skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh` (edit: chain the new check)
- `.claude/agents/branch-plan-task.md` (edit only if the hook wiring shape
  requires it -- confirm during implementation whether chaining inside
  `check_task_bash_safety.sh` itself is sufficient, matching how
  `check_task_full_verification.sh` already chains
  `gitapex_check_task_full_verification.py` without a second frontmatter
  hook entry)
- `agents/branch-plan-task.md` (edit only if the project-local variant's
  frontmatter itself changes -- the plugin-distributed variant has no
  `hooks` field at all, so any change there is prompt-text-only, matching
  Decision 17's own two-variant asymmetry)
- `skills/executing-a-branch-plan/references/execution-and-dispatch.md` (edit: document the mechanism)
- `skills/executing-a-branch-plan/references/threat-model-and-authorization.md` (edit: document the mechanism and its own disclosed residual risk)

No interface edge on any other task -- self-contained, no `ssot.json`
field involved, no file overlap with Tasks 1-3.

Planned ops (quoted from the re-verified ACM, row 4 -- #1508):

> Claude Code has no `SubagentStart`-equivalent hook event (confirmed:
> only `SubagentStop` exists, already wired on
> `.claude/agents/branch-plan-task.md` for Decision 20's full-verification
> exit condition). The only available deterministic enforcement point for
> "before a dispatched task-worktree begins work" is the ALREADY-embedded
> `PreToolUse` "Bash" hook on the `branch-plan-task` agent type (currently
> `check_task_bash_safety.sh`), which fires on the task's own first (and
> every subsequent) Bash call inside its isolated worktree.
>
> Add `gitapex_check_task_worktree_base.py`: resolves the shared plan
> branch's name (read `skills/executing-a-branch-plan/SKILL.md` and
> `references/execution-and-dispatch.md` directly first to confirm how --
> or whether -- the branch name already reaches a dispatched task, e.g.
> via an env var this skill's own dispatch step sets, rather than
> guessing; a git worktree shares refs/objects with the main checkout, so
> once the branch name is known, no value needs to be threaded in from
> the main thread beyond that name itself) and asserts `git merge-base
> HEAD <shared-branch>` equals `git rev-parse <shared-branch>` from
> within the worktree. Denies loudly (same JSON-decision shape
> `check_task_bash_safety.sh` already uses) with an actionable message
> naming both SHAs on mismatch; allows silently on match.
>
> Chain it into the task's existing PreToolUse Bash hook path (the same
> shape `check_task_full_verification.sh` uses to invoke
> `gitapex_check_task_full_verification.py` as a sibling call, not a
> second frontmatter hook entry, unless investigation shows the Bash
> hook specifically needs a second entry instead).
>
> Document in `references/execution-and-dispatch.md` and
> `references/threat-model-and-authorization.md` that this backstop
> piggybacks on the task's own first Bash call rather than being a true
> "before any tool call, including a non-Bash one" gate -- an explicitly
> disclosed, asymmetric-strength residual, matching this skill's own
> established convention (Decision 17's own two-variant disclosure) of
> naming an enforcement gap rather than overclaiming coverage.

Proof method: new
`skills/executing-a-branch-plan/scripts/test_gitapex_check_task_worktree_base.py`
constructing a fixture repo where a worktree is deliberately created,
then the "shared branch" is advanced past the worktree's own fork point
(reproducing the exact #1508 defect shape -- a worktree forked from a
stale base), confirming the check denies; a second fixture where the
worktree's fork point matches the branch's current tip confirms it
allows.

Irreversibility: none (new script, an added check invocation, doc edits
-- no destructive operation, no change to what a task is permitted to do
beyond the new precondition assertion itself).

## Wave assignment

Wave 1: Task 1, Task 4 (no file overlap, no interface edge between them).
Wave 2: Task 2, Task 3 (both depend on Task 1's `preconditions` field
shape; no file overlap or interface edge between Task 2 and Task 3
themselves).

## Execution mode

Primary path: `Workflow` tool, `agentType: 'branch-plan-task'`,
`isolation: 'worktree'` for each multi-task wave, one `Workflow` run per
wave -- this session has explicit opt-in per the calling task's own
instruction to follow `gitapex:executing-a-branch-plan`'s Step 6, which
itself directs `Workflow` tool usage (the Workflow tool's own "user
invoked a skill ... whose instructions tell you to call Workflow"
opt-in clause).

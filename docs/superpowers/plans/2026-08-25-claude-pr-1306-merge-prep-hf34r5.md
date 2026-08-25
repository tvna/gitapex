# Add a re-verified Branch Plan marker executing-a-branch-plan's Step 1 gate can check

**Goal:** `planning-a-branch-from-an-issue`'s Step 4 re-verification pass
leaves no mechanically-checkable trace on the issue, so
`executing-a-branch-plan`'s Step 1 Authorization gate cannot tell whether
that skill ever ran, or whether the issue's ACM is still the original,
un-re-verified draft `drafting-an-acm-issue` writes at issue-creation
time. Add a distinguishable re-verification marker, a deterministic
presence checker, and wire that checker into Step 1 as an additive
structural precondition. Source: https://github.com/tvna/gitapex/issues/1306.

**Authorization record:** No approving comment exists on issue #1306
(checked via `github:issue_read` method `get_comments`, empty result --
the issue was opened moments before this session started, by the
repository owner). Branch 2 of the Authorization gate applies instead:
the active human operator's own opening turn in this session explicitly
instructed executing issue #1306 through to just-before-merge
("こちらのPRを作りマージ直前まで進める" -- create this PR, proceed to just
before merge). This is a fresh, explicit, in-session confirmation for
this specific issue's execution, not a self-reported claim of prior
approval.

**Threat-model triage (step 2):** Issue #1306 was read in full. It is a
well-formed, professionally-scoped ACM issue authored by the repository
owner (`author_association: OWNER`), with no embedded instruction
addressed to the executing agent, no hidden/encoded payload, no attempt
to redirect this skill's own process. Clean.

**Stale-text correction (load-bearing, not a minor note):** Issue #1306's
own body claims "This repository's own Decision 9 (already reflected in
this repository's pipeline design tracking) established that a built/
corrected ACM gets written back to the issue body." A grep across every
`docs/superpowers/specs/*.md` finds exactly one "Decision 9" in the
entire repository -- `2026-07-22-plan-execution-handoff-design.md`'s own
Decision 9 -- and it is about cost/budget reconciliation (blind spot 7),
not ACM write-back; no file in the repository contains "written back" or
an equivalent phrase in connection with the ACM at all. Direct read of
`planning-a-branch-from-an-issue/SKILL.md` on `origin/main` confirms Step
4 never wrote anything back to the issue body -- only `drafting-an-acm-issue`'s
"Updating an existing ACM issue" procedure writes an ACM back to an
*issue* body today, for a different purpose (appending new findings),
never invoked by `planning-a-branch-from-an-issue`. Resolution: the
issue's citation is a misattribution, but its Acceptance criteria stand
on their own regardless -- this branch adds the write-back as new
behavior to `planning-a-branch-from-an-issue`'s Step 4 (a real gap this
issue closes), not as an extension of a mechanism that never existed.

**Architecture:** One new script/test pair plus a three-file prose
change, no other new files.

- `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  (new): a stdlib-only, regex-based, shape/presence-only checker mirroring
  `skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`'s
  own `--body <file>`-or-stdin CLI shape. Detects a fixed-format marker
  line naming `planning-a-branch-from-an-issue` and a non-empty
  parenthesized timestamp, fence-stripped first (not inline-code-stripped,
  mirroring `hooks/gitapex_check_acm_present_or_waiver.py`'s own rationale --
  the marker itself optionally wraps the skill name in a backtick pair).
  Placed in `skills/executing-a-branch-plan/scripts/` (in
  `pyproject.toml`'s `[tool.pytest.ini_options] testpaths` and its own
  dedicated `.github/workflows/test.yml` mypy job, matching this
  directory's three existing sibling checker scripts exactly), not
  `skills/planning-a-branch-from-an-issue/scripts/` (not in `testpaths`,
  which is why that skill's own `gitapex_check_acm_present.py` needs a
  `tests/`-relocated test with a manually-loaded module).
- `skills/executing-a-branch-plan/scripts/test_gitapex_check_branch_plan_reverified.py`
  (new): subprocess-driven regression suite, the same convention this
  directory's other checker-script tests already use. 14 cases: happy
  path, bullet/backtick/case/CRLF variants, no-marker, empty body, three
  adversarial defeat cases (marker only quoted inside a fenced example,
  wrong skill name, whitespace-only timestamp), and `--body`
  file/missing-file/non-UTF-8 CLI handling.
- `skills/planning-a-branch-from-an-issue/SKILL.md`: Step 4 gains a
  Postcondition -- once the re-verification pass completes, re-fetch the
  issue's current live body (never a stale cached copy, the same
  discipline `drafting-an-acm-issue`'s own update procedure already
  applies) and write the marker back, separate from the ACM table
  content itself.
- `skills/executing-a-branch-plan/SKILL.md`: Step 1 gains one sentence,
  run *before* the existing semantic approval-comment judgment: check the
  new script's verdict against the parent issue's own body. Absence is a
  stop-and-escalate, matching the gate's own existing fail-closed default;
  presence is additive only, never a substitute for the semantic
  judgment, which is otherwise textually unchanged. The Notes section's
  bundled-scripts inventory and "run directly" paragraph are updated to
  list the new script alongside its three siblings.
- `skills/executing-a-branch-plan/references/threat-model-and-authorization.md`:
  the Authorization gate section gains one paragraph stating the same
  additive-not-replacing framing, cross-referencing
  `planning-a-branch-from-an-issue`'s own Step 4 Postcondition.

**File-ownership map:** Task A owns the new script + test pair only
(`skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`,
`skills/executing-a-branch-plan/scripts/test_gitapex_check_branch_plan_reverified.py`).
Task B owns all three prose files
(`skills/planning-a-branch-from-an-issue/SKILL.md`,
`skills/executing-a-branch-plan/SKILL.md`,
`skills/executing-a-branch-plan/references/threat-model-and-authorization.md`).
No shared file between the two tasks.

**Interface-dependency map:** Task B's prose (both SKILL.md edits and the
reference-doc edit) names the new script's exact filename and CLI shape
(`--body <file>`, exit codes, PASS/FAIL message text). This is a
producer/consumer edge -- Task A is sequenced before Task B, never
co-assigned to the same wave.

**Wave assignment:**
- Wave 1: Task A (the new checker script + its test) -- defines the
  interface.
- Wave 2: Task B (the three prose files) -- consumes it.

**Irreversibility classification:** Both tasks are additive edits (one
new file pair, three prose edits to already-committed, already-reviewed
skill files) on a fresh feature branch, fully reversible by further edit
or revert before merge. Neither is classified irreversible; no fresh
per-task confirmation beyond the Authorization gate above is required.

**Dispatch mode:** The `Workflow` tool's own access-control policy
requires explicit user opt-in for multi-agent orchestration (an
"ultracode" keyword, a session-level flag, or the user's own direct
request to use a workflow) before this skill's own step 6 primary path
(`Workflow` + `agentType: 'branch-plan-task'` + `isolation: 'worktree'`)
may be invoked. None of those opt-in conditions hold in this session --
the operator's own instruction never mentioned orchestration. Per this
skill's own step 6 fallback clause ("[u]se the sequential main-thread
fallback ... when the Workflow tool is unavailable"), this is treated as
exactly that case in the practical/policy sense: both tasks execute
directly in the main thread, one per turn, no wave/run boundary, no
worktree isolation -- architecturally portable per this skill's own Notes
section, and proportionate to a two-task, five-file, no-parallelism plan
regardless. Step 8's mandatory dual dispatch (refactor pass + adversarial
review) uses the `Agent` tool instead, which carries no equivalent
opt-in gate.

**Proof method:**

- Task A: `uv run --frozen python3 -m pytest skills/executing-a-branch-plan/scripts/test_gitapex_check_branch_plan_reverified.py`
  (14/14 passed), `uv run --frozen ruff check`/`ruff format --check`, and
  `uv run --frozen mypy --config-file pyproject.toml skills/executing-a-branch-plan/scripts`
  (CI's own dedicated invocation for this directory) -- all clean.
- Task B: `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`
  against both modified `SKILL.md` files (50/50 and 56/56 checks passed).
- Regression: the full `pytest` suite (5500 passed; one pre-existing,
  unrelated failure --
  `tests/test_gitapex_scan_harden_checkout_pin_drift.py::test_repository_workflows_are_drift_free` --
  deselected: this session's checkout is a shallow clone
  (`git rev-parse --is-shallow-repository` -> `true`), and that gate's own
  error message names exactly this cause; CI runs with `fetch-depth: 0`
  and is unaffected).
- `.github/scripts/gitapex_gate_local_preflight.py` (all 36 wired local
  gates): 35/36 PASS, the one FAIL being the identical shallow-clone
  artifact above (`harden-checkout-pin-drift`), unrelated to this diff.
- A worked three-file example (this skill's own worked pass: a fixture
  issue body carrying only a bare, un-marked ACM table correctly FAILs
  the new checker; the same body plus the marker correctly PASSes)
  written into the PR body.
- Since both changed `SKILL.md` files count, a disclosed skill-quality
  audit pass (`battle-testing-a-skill` + `evaluating-skill-quality`, both
  fresh subagent dispatches) per `gitapex_gate_skill_audit_disclosure.py`,
  plus `checker-script-adversarial-review` and `defeat-test-disclosure`
  process-disclosure lines for the new checker script (it matches the
  `skills/*/scripts/*.py` checker-script glob).

## Execution log

- `PlanApproved` -- this plan, at branch publish (this commit).

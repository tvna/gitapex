# check-pr-duplicate-issue.sh: deny non-string tool_name (issue #1315)

**Goal:** Add the same `(.tool_name == null) or (.tool_name | type ==
"string")` guard PR #1213/#1217 already proved correct to
`hooks/check-pr-duplicate-issue.sh`, immediately before its own
`tool_name=$(...)` extraction, so a non-string `tool_name` denies (exit 2)
instead of silently falling through as "not our tool." Add regression
coverage to this hook's own shell test file and register it in the shared
jq type-confusion matrix test. Source:
https://github.com/tvna/gitapex/issues/1315.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker on
issue #1315's own body. All three ACM rows re-checked directly against
current `main` (commit `6dd908fc`): line 84's `tool_name=$(...)`
extraction still has no preceding type guard; the sibling `tool_input`
guard at line 99 and its exact predicate text are unchanged;
`hooks/test_gitapex_check_pr_duplicate_issue_shell.py` has no non-string
`tool_name` case; `hooks/test_gitapex_jq_type_confusion_matrix.py`'s
`GUARDED_FIELDS` has no `check-pr-duplicate-issue.sh` entry. No row
required correction.

**File-ownership check:** single task, three files
(`hooks/check-pr-duplicate-issue.sh`,
`hooks/test_gitapex_check_pr_duplicate_issue_shell.py`,
`hooks/test_gitapex_jq_type_confusion_matrix.py`), no other task to
conflict with.

**Canonical-governance-paths pre-filter:** `hooks/*.sh` and
`hooks/test_gitapex_*.py` are this repository's own hook/script and its
bundled tests -- an expected match for a hook-script change, not a
surprise. Full model review (this plan's own independent-re-verification
section above, plus per-task screening at the task's own diff, per step 6
of `executing-a-branch-plan`) still runs regardless: none of the ACM's
Planned-ops text reads as an injected instruction rather than a change
description (untrusted-input-triage Extract/Ignore/Flag/Tag pass, step 2:
nothing flagged -- the issue body is a plain technical bug report citing
real PR/issue numbers, no encoded content, no embedded redirection of this
gate).

**Interface-dependency edges:** none -- single task, no sibling task to
share an edge with.

**Execution mode:** sequential main-thread fallback (`Workflow` tool not
invoked -- no separate, explicit user opt-in for multi-agent orchestration
in this session; invoking `executing-a-branch-plan` itself is not read as
that opt-in, per the identical precedent already recorded in
`docs/superpowers/plans/2026-08-16-issue-1132-pr-prep-u1up26.md`,
`docs/superpowers/plans/2026-08-19-claude-pr-1231-prep-8pya3o.md`, and
`docs/superpowers/plans/2026-08-25-claude-pr-1316-prep-0131jz.md`). The
one task runs directly in the main thread, no worktree isolation. Step 8's
refactor and adversarial-review passes use the `Agent` tool (a single
subagent dispatch each, not the gated `Workflow` multi-agent orchestration
tool) for the independence that stage requires, each at a
stronger-reasoning tier and this session's default-or-higher effort per
that stage's own model/effort pin (described model-agnostically, no
specific model identifier written into this tracked file, per
`docs/superpowers/plans/2026-08-19-claude-pr-1231-prep-8pya3o.md`'s own
Revision-2 precedent).

**Irreversibility classification:** not irreversible -- an ordinary,
git-revertible shell-script and test edit inside this repository; no live
API write, no data deletion. No fresh per-task authorization confirmation
required beyond the branch-plan-wide one recorded below.

**Authorization record (step 1):** structural precondition PASS
(`gitapex_check_branch_plan_reverified.py` against issue #1315's live body
-- the `planning-a-branch-from-an-issue` re-verification marker is
present, written this session). Semantic approval: in-session explicit
confirmation from the human operator, who opened this session by directly
requesting this specific work ("このPRを作りマージ直前まで進める",
linking issue #1315 by URL) -- unambiguous, non-hedged, directly
responsive to this specific Branch Plan (the sole issue named), no
embedded instruction attempting to redirect this gate. No pre-existing
approval comment exists on issue #1315 (`get_comments` returned empty).

## Task 1 -- Add the tool_name type guard + regression tests

**Cites ACM row:** all three ACM rows (guard addition, hook-local
regression tests, shared matrix registration) -- collapsed into one task
since all three touch the same small, tightly-coupled surface with no
independent concern to split out.

**Quoted Planned ops (verbatim from the issue body):**
- Row 1: "Add `(.tool_name == null) or (.tool_name \| type == \"string\")`
  immediately before this hook's own `tool_name=$(...)` extraction (line
  84)"
- Row 2: "Add a parametrized (array/object/number/bool) test, mirroring PR
  #1213's `test_denied_when_tool_name_is_not_a_string` and PR #1314's
  equivalent additions to the two origin hooks"
- Row 3: "Add a `GuardedField` entry for `check-pr-duplicate-issue.sh`'s
  `tool_name` field to `hooks/test_gitapex_jq_type_confusion_matrix.py`'s
  `GUARDED_FIELDS` list"

**Files:** `hooks/check-pr-duplicate-issue.sh`,
`hooks/test_gitapex_check_pr_duplicate_issue_shell.py`,
`hooks/test_gitapex_jq_type_confusion_matrix.py`.

**Design, fixed at decomposition time:** mirror
`hooks/check-pr-issue-acm-disclosure.sh` lines 95-97 exactly (same
predicate, same deny-message wording convention) -- change line 84's
preamble from:
```bash
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
```
to:
```bash
if ! printf '%s' "$input" | jq -e '(.tool_name == null) or (.tool_name | type == "string")' >/dev/null 2>&1; then
  deny "Blocked by hooks/check-pr-duplicate-issue.sh: tool_name in the payload is not a string. Failing closed."
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
```

**Steps:**
1. Red: add `test_denied_when_tool_name_is_not_a_string` (parametrized:
   `["mcp__github__create_pull_request"]`/`{"x": 1}`/`5`/`True`, ids
   array/object/number/bool) to
   `hooks/test_gitapex_check_pr_duplicate_issue_shell.py`, mirroring
   `hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py`'s own test
   of the same name (`body="Refs #1"` to stay hermetic/no-network); widen
   `run()`'s `tool_name` parameter type hint from `str` to `object` so the
   non-string values type-check. Confirm it fails against current code
   (falls through to exit 0 instead of denying).
2. Green: apply the guard above to `hooks/check-pr-duplicate-issue.sh`.
3. Add one `GuardedField` entry to
   `hooks/test_gitapex_jq_type_confusion_matrix.py`'s `GUARDED_FIELDS` for
   `check-pr-duplicate-issue.sh`'s `tool_name` field
   (`expected_type="string"`, a base payload matching a valid
   `create_pull_request` call with a context-only `"Refs #1"` body so it
   stays hermetic, same convention the `pr-issue-acm-disclosure`/
   `pr-title-convention` entries already use) -- `tool_input` is
   deliberately NOT added, per issue #1315's own Constraints ("does not
   touch ... the four hooks PR #1213 already fixed" and scope stays to
   the `tool_name` guard).
4. Confirm the new hook-local test passes, the new matrix-file
   parametrized cases pass, and both files' full existing suites still
   pass.

**Proof method:** `uv run --frozen pytest
hooks/test_gitapex_check_pr_duplicate_issue_shell.py -v` and `uv run
--frozen pytest hooks/test_gitapex_jq_type_confusion_matrix.py -q` both
green; live repro (`printf '%s'
'{"tool_name":["mcp__github__create_pull_request"],"tool_input":{"owner":"tvna","repo":"gitapex","title":"t","body":"Closes #1"}}'
| GH_TOKEN= GITHUB_TOKEN= bash hooks/check-pr-duplicate-issue.sh; echo
$?`) returns 2 (denied), not 0.

## Post-task gate (Decision 12, mandatory)

After the task lands: one refactor/simplify pass (behavior-preserving
only) and one independent adversarial code review, each a fresh
`Agent`-tool subagent dispatch at a stronger-reasoning tier and this
session's default-or-higher effort (this stage's own model/effort pin,
described model-agnostically per this plan's own "Execution mode"
section) over the full diff. The adversarial review must confirm: (a) the
new guard's deny message and predicate exactly match the already-proven
PR #1213/#1217 shape, not a subtly different reimplementation; (b) the
new regression test genuinely fails pre-fix and passes post-fix, not a
tautological happy-path-only check; (c) the new `GuardedField` entry's
`base_payload` is itself hermetic (no live network call) and does not
accidentally also exercise the `tool_input` field this issue's own
Constraints scope out. Every CONFIRMED finding is fixed and every task's
own Red-Green test is re-run before the draft PR converts to
ready-for-review.

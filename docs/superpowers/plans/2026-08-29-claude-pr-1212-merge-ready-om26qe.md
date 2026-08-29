# hooks/CI: add issue-citation check for commit messages (issue #1212)

**Goal:** two-layer enforcement of CLAUDE.md section 3's issue-citation
rule for commits: (1) a `commit-msg` git hook as a fast local first pass,
(2) a CI check as the actual no-exceptions backstop, passing when a
citation exists in at least one non-merge commit in the PR's range OR the
PR title/body. Source: https://github.com/tvna/gitapex/issues/1212.

**Independent re-verification of the ACM (`planning-a-branch-from-an-issue`
Step 5):** performed this session, recorded as a re-verification marker on
issue #1212's own body (2026-08-29T19:00:21Z). No ACM row corrections --
both design unknowns the issue itself named were already settled by its
own most recent update (reuse `extract_citations()` from
`hooks/gitapex_check_pr_issue_acm_disclosure.py`; one script,
`.github/scripts/gitapex_gate_commit_citation.py`, two `--mode` values,
mirroring `gitapex_run_betterleaks.py`'s own precedent). Independently
confirmed against current `origin/main` (91f15c6d): `extract_citations()`
exists exactly as described (`hooks/gitapex_check_pr_issue_acm_disclosure.py`
lines 150-217); no `commit-msg` stage exists in `.pre-commit-config.yaml`;
`CONTRIBUTING.md` line 12 (also 66, 126) and `flake.nix` line 244 (also
242, 246) carry `-t pre-commit -t pre-push` with no `-t commit-msg`;
`pyproject.toml` line 350's pytest `pythonpath` already lists
`.github/scripts` and `hooks` side by side.

One addition beyond the issue's own stated Planned ops, folded in as real
repo convention rather than scope creep: `.gitapex/ssot.json` gate
registration. This repository's `registry-wiring-scan` gate and
`gitapex_gate_local_preflight.py`'s own docstring establish that every
deterministic gate with a working-tree-runnable form must carry a
registry entry (`planes` including `"local"` + `local_invocation`, or a
`local_exclusion` string -- `.gitapex/ssot.schema.json` requires one or
the other). Confirmed by inspecting existing entries: pre-commit-stage-only
hooks like `ruff-check`/`skill-shape-check` get NO separate top-level
ssot.json id (grep across all 69 existing entries found neither) -- only
the consolidated/CI-facing checks are registered. So this plan adds
exactly one new `ssot.json` gate entry, for the `--mode pr-range` CI
check, modeled on the `python-lint` and `toolchain-pin-drift` entries'
shape (`planes: ["ci","local"]`, `local_invocation` array). No change to
`.github/rulesets/main.json` or `apply-rulesets.yml` -- the issue's scope
is the check's presence, not making it a GitHub-required status check.

**File-ownership check:** not applicable -- single-task decomposition (see
below), no sibling task to check against.

**Canonical-governance-paths pre-filter (mechanized):**
`gitapex_check_canonical_governance_paths.py` against the 7 planned
changed paths -> 2 canonical matches (`hook-script`:
`.github/scripts/gitapex_gate_commit_citation.py`; `workflow`:
`.github/workflows/commit-citation-gate.yml`), 5 `no-match` (the test
module, `.pre-commit-config.yaml`, `CONTRIBUTING.md`, `flake.nix`,
`.gitapex/ssot.json` -- needs the model's own full-diff review, all of
which are expected, in-scope edits per the ACM's own Planned ops and the
ssot.json finding above). Full model review (the `untrusted-input-triage`
Extract/Ignore/Flag/Tag pass over the ACM's own text) already run: nothing
in the issue's Facts, Acceptance Criteria Map, Constraints, or Non-goals
reads as an injected instruction rather than a change description -- the
imperative-sounding "Planned ops" cell text ("Wired into
`.pre-commit-config.yaml` as...", "invoked from a `.github/workflows/*.yml`
step") is the issue's own OWNER-author describing what to build, same
pattern as every other ACM this skill has produced.

**Interface-dependency edges:** none -- single task.

**Waves:** wave 1: {task-1} (only task).

**Execution mode:** sequential main-thread fallback, no `Workflow` tool
run -- this session carries no explicit multi-agent-orchestration opt-in
("ultracode" or an explicit user request for a workflow). Step 8's
refactor and adversarial-review passes each use a fresh `Agent`-tool
subagent dispatch, at a stronger-reasoning tier and this session's
default-or-higher effort.

**Irreversibility classification:** not irreversible -- an ordinary,
git-revertible set of file additions/edits (a new script, a new test
module, edits to `.pre-commit-config.yaml`/`CONTRIBUTING.md`/`flake.nix`/
`.gitapex/ssot.json`, a new CI workflow step). No data deletion, no live
external write beyond the eventual `git push`/PR-open (both main-thread,
already covered by step 1's own authorization), no schema migration. No
task requires a fresh per-task authorization confirmation beyond the
branch-plan-wide one recorded below.

**Authorization record (step 1):** structural precondition PASS
(`gitapex_check_branch_plan_reverified.py` against issue #1212's live
body -- the `planning-a-branch-from-an-issue` re-verification marker is
present, timestamp 2026-08-29T19:00:21Z). Semantic approval: in-session
explicit confirmation from the human operator, directly instructing
"こちらのPRを作りマージ直前まで進める" (create this PR and drive it to just
before merge) against issue #1212's own URL -- unambiguous, directly
responsive to this specific issue, no embedded instruction attempting to
redirect this gate. No comments exist on issue #1212 (checked via
`get_comments` -- empty).

## Task 1 -- One script, two modes: commit-msg hook + CI backstop

**Cites ACM rows:** both rows (this task is the whole issue -- one script
serves both layers).

**Quoted Planned ops (verbatim from the issue body):** "One new script,
`.github/scripts/gitapex_gate_commit_citation.py`, following the exact
shape `gitapex_run_betterleaks.py --mode staged`/`--mode history` already
establishes ... a `--mode commit-msg` mode reads the message file path
from `sys.argv[1]` ... bootstraps `sys.path` to reach `hooks/` ... imports
`extract_citations` from `hooks/gitapex_check_pr_issue_acm_disclosure.py`
... passes when `extract_citations(...)` returns a non-empty `resolving`
or `context` tuple. Wired into `.pre-commit-config.yaml` as `entry: uv run
--frozen python3 .github/scripts/gitapex_gate_commit_citation.py --mode
commit-msg`, `stages: [commit-msg]`"; "The same
`gitapex_gate_commit_citation.py`, in a `--mode pr-range` mode, invoked
from a `.github/workflows/*.yml` step ... passes if a citation exists in
(a) at least one non-merge commit's message in the PR's commit range
(`git log --no-merges BASE..HEAD`), or (b) the PR title/body".

**Files:**
- `.github/scripts/gitapex_gate_commit_citation.py` (new)
- `tests/test_gitapex_gate_commit_citation.py` (new; exact name/location
  matched against this repo's existing `.github/scripts/*.py` test
  convention before authoring)
- `.pre-commit-config.yaml` (new `commit-msg`-stage hook entry)
- `CONTRIBUTING.md` (add `-t commit-msg` at each `prek install`
  invocation line)
- `flake.nix` (same, in the devShell's `prek install` invocation and its
  recovery/error message strings)
- `.gitapex/ssot.json` (one new gate entry, `--mode pr-range` only)
- `.github/workflows/*.yml` (new minimal workflow, or a step added to an
  existing appropriately-scoped one -- decided during implementation
  after checking existing workflow files for a natural home)

**Design, fixed at decomposition time:**
- Reuse `extract_citations()` verbatim via import; do not re-implement
  the regex.
- `--mode commit-msg`: read `sys.argv[1]` as the commit-msg file path (the
  argument `stages: [commit-msg]` pre-commit hooks receive), read its
  text, call `extract_citations(owner=None, repo=None, title=None,
  body=<message text>)`, exit 0 if `resolving` or `context` non-empty,
  exit 1 with a clear stderr message otherwise.
- `--mode pr-range`: accept flags for base ref, head ref (or read from
  environment/argv per this repo's existing CI-script CLI conventions --
  check `gitapex_gate_behind_base.py`/similar for the established
  base-ref-resolution pattern, e.g. `_gitapex_base_ref.py`, before
  inventing a new one), plus the PR title/body (or fetch via the GitHub
  API through the shared `_gitapex_github_http.py` helper, matching this
  repo's own established pattern for a CI script that needs PR metadata).
  Run `git log --no-merges <base>..<head> --format=%B` (or equivalent),
  concatenate each non-merge commit message's own citation extraction,
  OR with the PR title/body's own extraction; pass if any citation found
  anywhere in that union, fail with a clear message otherwise.
- Follow this repo's established `argparse` + `pydantic`-validated CLI
  namespace convention (per issue #1040's rollout, already used by
  `gitapex_run_betterleaks.py` and others) for both scripts' shared
  parser.
- `sys.path.insert(0, ...)` bootstrap to reach `hooks/`, one line, same
  style as every existing cross-file `.github/scripts/*.py` import.
- New `.gitapex/ssot.json` entry: id (e.g. `commit-citation-gate`),
  `kind: "script"`, `script` naming the new script + the workflow file
  that invokes it, `planes: ["ci","local"]`, `local_invocation` running
  `--mode pr-range` against the working tree's own current branch vs.
  `origin/main` (mirroring how other PR-range-shaped local invocations in
  this registry resolve a local base ref -- verify against
  `gitapex_gate_behind_base.py`'s own registry entry or similar before
  finalizing), `trigger` naming the new/extended workflow + `pull_request`
  event, `tracking_issue: 1212`, `cluster` picked from this repo's
  existing cluster vocabulary (e.g. `plan-integrity`, matching
  `pr-issue-acm-disclosure`'s own cluster), `status: "active"`,
  `bypass_review_status: "not-yet-reviewed"`, `supersedes: null`,
  `policy_refs: []`, `target` naming the workflow event and the file
  globs it covers. Validate against `.gitapex/ssot.schema.json` and re-run
  `gitapex_scan_ssot_schema.py`/`registry-wiring-scan` locally before
  pushing.
- Do not touch `.github/rulesets/main.json` or run `apply-rulesets.yml`.
- Do not retroactively re-cite any already-merged commit history (explicit
  Non-goal).
- Do not attempt citation-*format* validation (explicit Non-goal, tracked
  separately as #521).

**Proof method:** new pytest module covering: `--mode commit-msg` accepts
a message carrying a citation (`Closes #123`, `Refs #123`, bare `#123`)
and rejects one without; `--mode pr-range` passes when the citation is
only in the PR body, passes when it's only in one non-merge commit,
does NOT fail solely because an uncited merge commit is in range, and
fails when no citation exists anywhere (title, body, or any non-merge
commit); confirms the `git log --no-merges` invocation actually excludes
a merge commit from the scan (a real merge commit fixture, not just a
mocked git-log). `ruff check`/`ruff format --check`/mypy clean on the new
script and test module. Full local test suite green
(`uv run pytest`, or the local-preflight runner covering the newly wired
gate). Actual `git commit -m` message for this task's own commit contains
`#1212` (dogfooding).

## Post-task gate (Decision 12, mandatory)

After the task lands: one refactor/simplify pass (behavior-preserving
only) and one independent adversarial code review, each a fresh
`Agent`-tool subagent dispatch at a stronger-reasoning tier and this
session's default-or-higher effort, over the full accumulated diff. Given
this diff adds a new deterministic gate/check script, the adversarial
review must construct and run at least one case built to defeat its own
detection logic (per this skill's own Stop boundaries), at minimum:
(a) a commit message citing an issue only inside a fenced/inline code
block (should NOT count, matching `extract_citations()`'s own documented
fence-stripping behavior) -- confirm the new script inherits this
correctly through its own message-extraction path; (b) a PR body citing a
*foreign* repo's issue (`other-owner/other-repo#123`) should not
false-positive as this repo's own citation; (c) an empty or whitespace-only
commit-msg file; (d) a PR with zero non-merge commits in range (e.g. a
single merge commit) relying solely on the PR title/body; (e) confirm
`.gitapex/ssot.json`'s new entry doesn't break `registry-wiring-scan` or
`ssot-schema-drift`. Every CONFIRMED finding is fixed and, where a
proof-method check exists for the affected area, re-run before the draft
PR converts to ready-for-review.

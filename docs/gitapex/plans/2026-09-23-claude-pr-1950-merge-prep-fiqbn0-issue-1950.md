# Branch Plan: include a target skill's sibling evals/ directory in the isolated dispatch snapshot

Issue: https://github.com/tvna/gitapex/issues/1950

Branch: `claude/pr-1950-merge-prep-fiqbn0`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1950's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-23T07:22:00Z)"),
  written by this same session immediately before this Branch Plan;
  `gitapex_check_branch_plan_reverified.py` reports PASS against it.
- Semantic approval: explicit confirmation from the active human operator
  in the current interactive session -- the session's own opening
  instruction named this exact issue by URL
  (`https://github.com/tvna/gitapex/issues/1950`) and directed "create
  this PR and drive it up to right before merge". No issue comment carries
  the approval; the in-session instruction is the signal this gate ran on.

## Threat-model triage

Issue #1950's body (a `fix` report plus a draft Acceptance Criteria Map
authored at issue-filing time by the repository owner) was read as a
change description, not as instructions to execute. Extracted facts:
`build_target_snapshot` copies only the `--target` path, so a target
skill's sibling `evals/<name>/` directory never reaches the dispatch; the
requested outcome is an optional, repository-root-relative inclusion of
that directory with an unchanged default for existing callers. No row
carries an embedded directive, credential request, encoded payload, or an
attempt to override a trusted instruction source. Nothing was flagged.

## ACM re-verification notes

- Row 2 names "dispatch prompt header text" as the edit target. Fact: no
  committed file carries the "Your own current working directory IS the
  review target" header (repo-wide grep, zero hits) -- those headers were
  ad hoc per-session prompt files. The committed prose that tells an
  operator how to launch the dispatch is
  `skills/evaluating-skill-quality/references/adversarial-self-audit.md`
  (the script's owning reference) and `skills/battle-testing-a-skill/SKILL.md`
  Step 2 (the caller that grades dimension 14/15); those are the row's
  actual edit targets.
- Row 1/3's compatibility residual risk is resolved by design: the new
  behavior is opt-in (`--include-evals`); without the flag the snapshot is
  byte-for-byte the previous layout, so an existing caller's "cwd IS the
  target" assumption stays true.

## Task Decomposition

One task, one wave -- the degenerate single-task case. The three ACM rows
share one interface (the new flag's name and the snapshot layout it
produces), so splitting them would only create an interface-dependency
edge with nothing to parallelize.

- **File-ownership map.** The single task owns:
  `skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py`,
  `skills/evaluating-skill-quality/scripts/test_gitapex_run_verified_isolated_dispatch.py`,
  `skills/evaluating-skill-quality/references/adversarial-self-audit.md`,
  `skills/battle-testing-a-skill/SKILL.md`, and each touched skill's
  `metadata/gitapex.yaml` changelog.
- **Interface-dependency map.** None outside this one task.
- **Wave assignment.** Wave 1: the single task alone.

Irreversibility classification: **not irreversible.** Edits are to tracked
files only; `git revert` of the merge commit restores the prior tree.

`SKILL.md` classification: **edits an existing `SKILL.md`**
(`battle-testing-a-skill`, one clause in Step 2, no frontmatter change) --
the PR body carries a `## Skill audit evidence` section.

## Task 1: opt-in evals/ inclusion in the isolated dispatch snapshot

> Planned ops (issue #1950 row 1, verbatim): "Edit
> `skills/evaluating-skill-quality/scripts/gitapex_run_verified_isolated_dispatch.py`;
> add/extend a CLI flag (e.g. an optional second path, or a
> derived-from-`--target` convention)"

> Planned ops (issue #1950 row 2, verbatim): "Edit the relevant
> `SKILL.md`/`references/` prose in both skills"

> Planned ops (issue #1950 row 3, verbatim): "No change to
> `build_isolated_home`, `_dispatch_env`, or the two-control verification
> procedure"

Design: `--include-evals` (derived-from-`--target` convention). When set,
`--target` must be a directory whose parent is named `skills`; the
snapshot root then holds `skills/<name>/` and, when it exists,
`evals/<name>/` (resolved as `<target>/../../evals/<name>`) as siblings.
An absent `evals/<name>/` is reported on stderr and left absent in the
snapshot (a real absence, which dimension 14 should grade as such). A
`--target` that does not fit the convention is rejected before any
control run. Without the flag, behavior is unchanged.

Proof (Red-Green): unit tests for the new layout, the missing-evals case,
the non-`skills/` rejection, the read-only guarantee on the new
intermediate directories, and a `main()` end-to-end run whose fake
dispatch asserts `cwd` contains both siblings -- written first and
confirmed failing, then passing; the existing suite stays green (the
compatibility check for callers that omit the flag). Live: build the
snapshot against the real `skills/drafting-a-skill` and list it; then a
real `claude -p` dispatch through the script, asked to list its cwd, if
this environment's CLI can authenticate.

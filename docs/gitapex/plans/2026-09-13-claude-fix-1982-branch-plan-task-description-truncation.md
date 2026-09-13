# Branch Plan: shorten branch-plan-task's description to invocation-scope content only

Issue: https://github.com/tvna/gitapex/issues/1982

Branch: `claude/focused-fermat-c18ox6` (this session's designated branch
for `tvna/gitapex`, from `origin/main` -- used in place of a fresh
`fix/1982-...` branch name because the session's own harness-level
instructions pin development and pushes to this exact branch and forbid
pushing elsewhere without explicit permission).

## Task Decomposition

One task, one wave -- the degenerate case `executing-a-branch-plan`'s own
Related-skills section names, not a skipped decomposition.

The single Acceptance Criteria Map row's planned ops touch exactly one
file, `agents/branch-plan-task.md` (one line, the frontmatter
`description:` value). `scripts/gitapex_check_file_ownership_conflicts.py`
reports no file-ownership conflicts across the decomposition (trivially,
at one task):

```
$ echo '{"task-1-shorten-branch-plan-task-description": ["agents/branch-plan-task.md"]}' \
    | python3 skills/executing-a-branch-plan/scripts/gitapex_check_file_ownership_conflicts.py
no file-ownership conflicts found
```

The interface-dependency map is likewise empty for the same reason (one
task, nothing to depend on).

Irreversibility classification: **not irreversible.** The task rewrites
one YAML frontmatter string value in one tracked file. Nothing writes
outside the repository, no migration runs, no data is deleted, and the
dropped rationale text is not lost from the repo -- it already appears in
this same file's own body (line 53). `git revert` of the merge commit
restores the prior description exactly.

`SKILL.md` classification: **no `SKILL.md` is created or edited.** The
change touches `agents/branch-plan-task.md` and this plan file only, so
`drafting-a-skill` is not routed to, and the PR-body skill-audit
disclosure convention does not apply.

## Task 1: shorten the description to invocation-scope content only

Source ACM row: issue #1982's draft ACM row is superseded by the decided
approach recorded on the issue (2026-09-13 update, "Decided approach"
section) after the issue author (repo OWNER), in a live session, chose
deliberate shortening over both drafted options (quote the value /
rephrase the `#1476` citation). Quoted verbatim below rather than
paraphrased:

> Planned ops: "Replace agents/branch-plan-task.md line 3 description
> value with the 256-char text above" -- i.e. keep "what it is + the two
> sanctioned call sites", delete the rationale clause
> (`threat-model-and-authorization.md` pointer + `Decision 20, issue
> #1476` citation -- the literal cause of the YAML plain-scalar
> truncation) and the negative "Never invoke directly for anything
> else..." constraint clause.

### Files

- `agents/branch-plan-task.md`

### Operations

1. Replace the frontmatter `description:` value (line 3) with:

   > Task-level, plugin-distributed subagent type for a fixed, enumerated
   > set of call sites -- see this file's own "Sanctioned call sites"
   > section for the exact, current list (executing-a-branch-plan Step
   > 6's per-task dispatch, Step 8's refactor/simplify pass).

   No other line in the file changes.

### Proof method

Not a code-logic change, so no Red-Green test cycle applies; the proof is
a direct YAML round-trip measurement, run before and after:

1. Before: raw description is 717 characters, parsed is 615 (the bug,
   already reproduced against `origin/main` at `9838da14`).
2. After: parse the new frontmatter and assert `parsed_description ==
   raw_description` (both 256 characters) and that the value contains no
   `#`.
3. Run `tests/test_gitapex_sync_opencode.py` (parses both real agent
   files per issue #1982's own body) to confirm no regression.
4. `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`
   -- full wired-gate suite green.

### Residual risk

- Issue #1982's own residual risk (unaudited `skills/*/SKILL.md`
  frontmatter for the same hazard) is unchanged by this fix and remains
  open as a non-goal.
- `hooks/gitapex_sync_opencode.py` is out of scope per the issue's
  Constraints; it copies the line verbatim and needs no change since the
  new value already round-trips cleanly for both runtimes.
- The shortened description is a user-visible content change (not only a
  quoting fix) in every agent-type listing that surfaces it -- that is
  the point of the issue author's decided approach, disclosed on the
  issue itself, not an incidental side effect.

## Wave assignment

| Wave | Tasks |
|---|---|
| 1 | task-1-shorten-branch-plan-task-description |

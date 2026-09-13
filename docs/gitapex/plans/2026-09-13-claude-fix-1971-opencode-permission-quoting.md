# Branch plan: quote a permission key that is not a safe bare YAML scalar

Issue: https://github.com/tvna/gitapex/issues/1971

Branch: `claude/fix-1971-opencode-permission-quoting`, from `origin/main`.

## Decomposition

One task, one wave -- the degenerate case `executing-a-branch-plan`'s own
Related-skills section names, not a skipped decomposition.

All three Acceptance Criteria Map rows' planned ops write the same two
files, `hooks/gitapex_sync_opencode.py` and
`tests/test_gitapex_sync_opencode.py`. Splitting them into three tasks
would put a file-ownership edge between every pair, so all three would be
sequenced anyway -- three waves of overhead around a change of roughly
forty lines, with no parallelism available to recover it. The rows are
also proof-coupled: row 2's test is what proves row 1's fix, and row 3
exists only because row 1 changes the emitted text.

`scripts/gitapex_check_file_ownership_conflicts.py` reports no
file-ownership conflicts across the decomposition (trivially, at one
task); the interface-dependency map is likewise empty for the same
reason. Recorded rather than skipped, so a later reader can see both maps
were computed.

Irreversibility classification: **not irreversible.** The task edits two
tracked files and adds tests. Nothing writes outside the repository, no
migration runs, and no data is deleted. `git revert` of the merge commit
restores the prior tree exactly.

`SKILL.md` classification: **no `SKILL.md` is created or edited.** The
change is confined to `hooks/` and `tests/`, so `drafting-a-skill` is not
routed to, and the PR-body skill-audit disclosure convention does not
apply -- `.github/scripts/gitapex_gate_skill_audit_disclosure.py`'s own
trigger set is `skills/**/SKILL.md`, `docs/superpowers/specs/*.md`,
`skills/*/scripts/*.py`, `evals/scripts/*.py` and
`.github/scripts/*.py`, none of which this diff touches.

## Task 1: quote permission entries the generator emits

Source ACM rows: rows 1, 2 and 3 of issue #1971's own Acceptance Criteria
Map, quoted verbatim below rather than paraphrased.

> Row 1 planned ops: "In `_render_agent_copy`, emit a permission key
> through a quoting step rather than raw interpolation, so a key that is
> not a safe bare YAML scalar is quoted and one that is stays unchanged"

> Row 2 planned ops: "Add a test rendering each agent's copy and loading
> its frontmatter, asserting the permission mapping read back equals the
> declared mapping"

> Row 3 planned ops: "Update that assertion, and any sibling asserting the
> same shape, to the emitted form"

Applied with the four corrections issue #1971's own "Plan re-verification
(2026-09-13)" section records -- C1 (the generator stays standard-library
only), C2 (that constraint gets its own pinned test), C3 (the quoting
applies to the value as well as the key), C4 (exactly one existing
assertion is affected).

### Files

- `hooks/gitapex_sync_opencode.py`
- `tests/test_gitapex_sync_opencode.py`

### Operations

1. Add a module-level helper that returns a YAML-safe rendering of one
   scalar: unchanged when it is already a safe bare scalar, otherwise
   double-quoted with `\` and `"` escaped. A value carrying a character
   that double-quoting alone cannot carry safely raises rather than
   emitting a broken line. Standard library only -- `re`, never
   `yaml.safe_dump` (C1).
2. Route `_render_agent_copy`'s permission lines through that helper, for
   both the key and the value (C3).
3. Add a test that renders each entry of the sync module's own
   agent/permission table, loads the rendered frontmatter with
   `yaml.safe_load`, and asserts the permission mapping read back equals
   the declared mapping. Both table entries are covered, including the
   one whose permission is `None` and therefore emits no permission block
   at all.
4. Add a test pinning C1: this module's own top-level imports are
   standard-library only. `.github/scripts/gitapex_gate_stdlib_only_claim_drift.py`
   discovers candidates from `.github/scripts/*.py` and
   `evals/scripts/*.py` only, so `hooks/` carries no such gate today and
   the constraint the fix depends on would otherwise be unguarded.
5. Update `tests/test_gitapex_sync_opencode.py`'s existing assertion on
   the emitted `*mcp*` line to the quoted form. The five assertions
   naming safe bare keys are unchanged by construction (C4).

### Proof method

Red then green, both directions demonstrated:

1. Write the step-3 test first and confirm it FAILS against the current
   generator, with the `ScannerError` issue #1971 records.
2. Apply the fix and confirm the same test PASSES.
3. `uv run --frozen python3 -m pytest --no-cov -q` -- full suite green.
4. `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`
   -- all 49 wired gates pass.

### Residual risk

Carried from issue #1971's own Residual risk section and not re-derived
here: the blast radius on OpenCode is bounded but not established (its
own parser is unobserved); quoting proves the key parses as a literal
string, not that OpenCode's matcher then denies every MCP-provided tool;
and an eleven-key deny-list against a default-allow runtime is not
equivalent to the closed allow-list `agents/review-persona.md` declares.

One further residual risk, found during the Step 5 re-verification and
recorded on the issue: `_render_agent_copy` emits `description:` through
the same raw interpolation, so a description containing a colon-space or
a trailing space-hash would break the same frontmatter block. Both
current descriptions are safe. Widening this task to cover it would
contradict the issue's own narrow-surface constraint, so it is left for a
follow-up issue.

## Wave assignment

| Wave | Tasks |
|---|---|
| 1 | task-1-quote-permission-entries |

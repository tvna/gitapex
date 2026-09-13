# Branch Plan: quote a permission key that is not a safe bare YAML scalar

Issue: https://github.com/tvna/gitapex/issues/1971

Branch: `claude/fix-1971-opencode-permission-quoting`, from `origin/main`.

## Task Decomposition

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
change touches `hooks/`, `tests/` and this file, so `drafting-a-skill` is
not routed to.

The PR-body skill-audit disclosure convention does not apply either, but
by a longer chain than an earlier revision of this paragraph claimed. That
revision said the trigger set does not include this diff's paths; measured,
`.github/workflows/skill-audit-gate.yml`'s `paths:` list carries eleven
entries and `hooks/**` is one, so the workflow DOES fire.

What it computes is `gitapex_compute_skill_audit_flags.py`'s five-way
disjunction -- `skill_md_lines`, `design_doc_lines`, `checker_lines`,
`gate_scripts`, `reference_lines`. Every one is empty here: no
`skills/**/SKILL.md` and no `skills/*/references/**`; `docs/gitapex/plans/`
is not one of the `docs/*/specs/*.md` design-doc pathspecs; `hooks/` is in
none of the checker-script pathspecs; and for `gate_scripts`,
`gitapex_detect_changed_gate_scripts.py` matches
`hooks/(?:check[-_]|gitapex_check_)` while this file is `gitapex_sync_`,
neither `.gitapex/ssot.json` nor `hooks/hooks.json` is touched. With the
disjunction false the workflow skips the disclosure step entirely -- the
grader is never invoked on CI, so the "no disclosure requirement" line it
prints under a local `--check-diff` run is not what CI emits.

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
   this generator will not put on one line raises rather than emitting
   something that would not read back. Standard library only -- `re`, never
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

One further risk was recorded here and on the issue during the Step 5
re-verification: `_render_agent_copy` emits `description:` through raw
interpolation, so a description containing a colon-space or a space-hash
"would break the same frontmatter block". Deferred to a follow-up issue
on the ground that "both current descriptions are safe".

Step 8 went through two rounds on that one sentence, and the second
round's measurement is the one that holds.

Round 1 read it as a generator defect, and the description was routed
through `_yaml_scalar` (commit `26a76988`). Round 2 measured the result
against what the SOURCE file itself parses to, and the change was a
regression: raw interpolation agreed with the source in 4 of 4 shapes,
the re-encoded form in 1 of 4. It double-encoded a description that was
already a quoted scalar, and for `agents/branch-plan-task.md` it made
OpenCode read 717 characters where Claude Code reads 615. Reverted.

The reason raw interpolation is right is structural: the emitted line is
copied through from the source line, so any conformant parser reads the
same value from both. Re-encoding breaks exactly that. (Copied through,
not byte-identical: the frontmatter pattern normalizes the `key:`
separator and strips surrounding whitespace with a Unicode-wide `\s*`.
That is a small divergence in its own right, pre-existing and left alone,
and it is why the claim is stated as fidelity of the parsed value rather
than of the bytes.)

The 102 characters are genuinely lost -- but in the source file, for
every runtime, Claude Code included (this session's own agent listing
shows that description ending at "and (Decision 20, issue"). That is a
defect in `agents/branch-plan-task.md`, not in this generator, and it is
tracked on its own issue rather than repaired behind a mirror. What this
branch adds is the test that would have caught the misdiagnosis: the
live-tree test now asserts the generated copy parses to what the source's
own frontmatter parses to, and it fails when the description is
re-encoded.

Two bounds stay unenforced, on measurement rather than assumption. A YAML
key may not exceed 1024 characters (1024 parses, 1025 raises
`ScannerError`); the longest key `_yaml_scalar` ever sees is 18. And a
refusal leaves any previously generated copy in place while `--verify`
still reports zero changes -- pre-existing behaviour of every `ValueError`
path in `sync_agents`, and unreachable from the module constants that are
once again this helper's only callers.

## Wave assignment

| Wave | Tasks |
|---|---|
| 1 | task-1-quote-permission-entries |

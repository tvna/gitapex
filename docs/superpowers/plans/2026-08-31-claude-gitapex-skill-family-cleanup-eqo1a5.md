# Branch Plan: claude/gitapex-skill-family-cleanup-eqo1a5

Source issue: https://github.com/tvna/gitapex/issues/1597
(re-verified, plus a "Scope update (planning session, 2026-08-31)" section
adding 7 new/updated Acceptance Criteria Map rows; parent tracking issue
#1595)

## Task list (8 tasks, 2 waves)

File-ownership edge check: `scripts/gitapex_check_file_ownership_conflicts.py`
run against all 8 tasks' file lists -- `no file-ownership conflicts found`.
Interface-dependency edges (pinned judgment, not mechanized): Task 8 reads
the final content of both `AGENTS.md` (Task 1) and `CLAUDE.md` (Task 2) to
correctly rewrite its own worked example -- sequenced after both. No other
edge found between any other task pair.

wave 1: Tasks 1-7 (no edge between any pair). wave 2: Task 8 (interface
edge on Tasks 1 and 2).

### Task 1: Trim AGENTS.md's duplicate skill call-outs and strip its apm-compile provenance header/footer

**Owns:**
- `AGENTS.md`

**File-ownership / interface-dependency edges:** none inbound; Task 8
(wave 2) has an outbound edge onto this task's own output.

**Source ACM rows (quoted verbatim from issue #1597's re-verified
Acceptance Criteria Map):**

Original row 1:

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `CLAUDE.md`'s skill-name call-outs should not duplicate what the named skill's own description already covers | For each of the six call-outs, keep the section's principle (e.g. "enumerate assumptions before implementing", "don't settle for LGTM") and drop or rephrase only the "the X skill does Y" clause once X's own `description` already states it | Edit `CLAUDE.md` sections 1, 2, 3, 4, and 6 -- section by section, since section 3's `dispatching-parallel-agents`/`subagent-driven-development` pairing and section 6's `receiving-code-review` reference gitapex skills that absorbed the function rather than kept the name (`executing-a-branch-plan`, `drafting-a-pr-to-merge`/`reviewing-an-artifact`) |

Scope-update rows:

| Criterion | Planned ops |
|---|---|
| The original six-call-out trim's target file changes once AGENTS.md becomes canonical | Apply this issue's original first ACM row's edits to `AGENTS.md` instead of `CLAUDE.md` |
| AGENTS.md's remaining sections should not duplicate what a gitapex-authored (gitapex:*) skill's own description already covers, beyond the original six call-outs | Edit `AGENTS.md` sections 1, 2, 3 for the newly-identified lines, same drop-or-rephrase discipline as the original row |
| Stop apm compile from being AGENTS.md's/CLAUDE.md's content source; AGENTS.md becomes a plain, hand-maintained canonical file | Strip the HTML-comment header lines (compile-tool name, build identifier, source) and the italic regenerate-instruction footer from `AGENTS.md`, leaving only the hand-maintained heading and body content |

The second scope-update row's "newly-identified lines" are: section 1's
self-correcting-phrase STOP rule (`gitapex:stop-and-replan`), section 2's
"See the systematic-debugging skill" line (`gitapex:diagnosing-a-failure`),
section 3's "auto-subscribe to CI... drive to a terminal state" and
"resolve_review_thread... verify mergeable_state" rules
(`gitapex:drafting-a-pr-to-merge`), section 3's "auto-open a retrospective
issue... classify each repair" rules (`gitapex:merge-retrospective`), and
section 3's "Keep GitHub posts ASCII" / "Audit every outward-facing
artifact... for provenance markers" rules
(`gitapex:outward-artifact-preflight`).

**Implementation guidance:**

- Per-line editorial judgment (issue's own residual-risk note): keep each
  section's underlying principle, drop or rephrase only the clause that
  restates a named skill's own frontmatter `description`.
- The section 3 line naming `mcp__github__resolve_review_thread` /
  `mergeable_state` carries an existing `<!-- portability-ack -->` HTML
  comment marker suggesting a deliberate prior keep decision, and its own
  tool-name-level specificity arguably exceeds what
  `drafting-a-pr-to-merge`'s prose description states -- per the issue's
  own residual-risk note, treat this as an implementation-time judgment
  call rather than a default drop; lean toward keeping it (with the
  `<!-- portability-ack -->` marker intact) unless a clear rephrase
  preserves the same operational detail more concisely.
- Verify each edited section against the corresponding `gitapex:*` skill's
  own frontmatter `description` (read the skill's `SKILL.md` frontmatter
  directly, do not rely on the routing-table summary alone) before
  concluding a line is safe to drop.
- Strip the file's HTML-comment header lines (compile-tool name, build
  identifier, source) and the trailing italic footer naming the
  compile-tool origin and the now-obsolete regenerate command entirely --
  `AGENTS.md` keeps only its `# AGENTS.md` heading and the trimmed body
  content below it.
- Proof method (from the ACM): re-read each edited section against the
  corresponding skill's own `description`; confirm no remaining line
  restates what that description already says; confirm no remaining
  reference to APM CLI generation or `apm compile`.

### Task 2: Replace CLAUDE.md's content with a single `@AGENTS.md` import line

**Owns:**
- `CLAUDE.md`

**File-ownership / interface-dependency edges:** none inbound; Task 8
(wave 2) has an outbound edge onto this task's own output.

**Source ACM row (quoted verbatim, scope-update section):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `CLAUDE.md` becomes a one-line pointer to the new canonical `AGENTS.md` | Per the repository owner's explicit instruction, `CLAUDE.md`'s entire content becomes the single line `@AGENTS.md` (Claude Code's own file-import syntax), replacing the current full duplicate body and compiled-file header/footer | Replace `CLAUDE.md`'s full content with `@AGENTS.md` |

**Implementation guidance:**

- `CLAUDE.md`'s entire file content becomes exactly one line: `@AGENTS.md`
  -- no heading, no header/footer comments, nothing else.
- Proof method (from the ACM): `CLAUDE.md` contains exactly one line,
  `@AGENTS.md`, and no other content.

### Task 3: Remove the obra/superpowers apm dependency

**Owns:**
- `apm.yml`
- `apm.lock.yaml`
- `apm_modules/obra/superpowers/` (deleted, directory)

**File-ownership / interface-dependency edges:** none.

**Source ACM row (quoted verbatim, original issue #1597 row 2):**

| Criterion | Interpretation | Planned ops | Proof method |
|---|---|---|---|
| Remove the `obra/superpowers` apm dependency | The package should no longer be declared or vendored | Remove `obra/superpowers` from `apm.yml`'s `devDependencies.apm`; prune `apm_modules/obra/superpowers/`; re-run the apm lock step so `apm.lock.yaml` reflects the removal | `apm.yml` no longer lists it; `apm_modules/obra/superpowers/` is absent; `.github/scripts/gitapex_scan_apm_manifest_drift.py`'s drift gate still passes |

**Implementation guidance:**

- Remove the `obra/superpowers` line from `apm.yml`'s
  `devDependencies.apm` list; update the file's own header comment
  (currently states "obra/superpowers and tvna/clairvoyance are assumed
  present by gitapex's own skills") to drop the now-false
  `obra/superpowers` half of that claim.
- Delete `apm_modules/obra/superpowers/` entirely.
- Regenerate `apm.lock.yaml` by running `apm lock` (or the repository's
  equivalent) if the `apm` binary is available in this environment; if
  not (this session's own SessionStart hook reported `SKIPPED: apm`),
  hand-edit `apm.lock.yaml` to remove the `obra/superpowers`
  dependency's own block (matching its `dependencies:` list shape --
  `repo_url`, `name`, `host`, `resolved_commit`, `version`,
  `package_type`, `deployed_files`), leaving the `tvna/clairvoyance` and
  `cathrynlavery/diagram-design` entries untouched, and disclose in the
  PR body that this was a manual edit rather than a real `apm lock` run,
  as a follow-up risk if the tool later regenerates a different shape.
- Proof method (from the ACM): `apm.yml` no longer lists
  `obra/superpowers`; `apm_modules/obra/superpowers/` is absent;
  `.github/scripts/gitapex_scan_apm_manifest_drift.py`'s drift gate still
  passes.

### Task 4: Update docs/motivation.md's stale requesting-code-review references

**Owns:**
- `docs/motivation.md`

**File-ownership / interface-dependency edges:** none.

**Source ACM row (quoted verbatim, original issue #1597 row 3):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `docs/motivation.md`'s sequence diagrams should reflect the current review mechanism, not the retired `requesting-code-review` reference | The `[superpowers, Task subagent]` tag is a stale label for a step now served by `drafting-a-pr-to-merge`/`reviewing-an-artifact` | Update both occurrences (lines 40, 103) to name the current mechanism instead of `requesting-code-review [superpowers, Task subagent]` |

**Implementation guidance:**

- Both occurrences read: "diff correctness review: requesting-code-review
  [superpowers, Task subagent] -> findings -> fix [validate -> fix]."
  Replace `requesting-code-review [superpowers, Task subagent]` with a
  label naming the current mechanism (`reviewing-an-artifact` /
  `drafting-a-pr-to-merge`, as the surrounding diagram's own as-is/to-be
  framing calls for).
- Proof method (from the ACM): grep `docs/motivation.md` for
  "superpowers"; confirm no remaining hit describes it as a live
  dependency.

### Task 5: Update setup-gitapex-toolchain/SKILL.md's post-removal dependency set

**Owns:**
- `skills/setup-gitapex-toolchain/SKILL.md`

**File-ownership / interface-dependency edges:** none.

**Source ACM row (quoted verbatim, original issue #1597 row 4):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `skills/setup-gitapex-toolchain/SKILL.md` should describe the post-removal dependency set | Its `obra/superpowers` references describe a devDependency that will no longer exist | Update the file's `apm.yml` devDependency list and apm-managed hook-entry description to drop `obra/superpowers` |

**Implementation guidance:**

- Line 49 area reads: "`apm install`, which only ever deploys `apm.yml`'s
  two devDependencies (`obra/superpowers`,..." -- update to name the
  post-removal set (`tvna/clairvoyance`, `cathrynlavery/diagram-design`).
- Proof method (from the ACM): re-read the file against the post-removal
  `apm.yml`; confirm no remaining reference to `obra/superpowers` as a
  present dependency.

### Task 6: Update middleware-inventory.md's obra/superpowers row and apm-compile role description

**Owns:**
- `skills/auditing-agent-product-scope/references/middleware-inventory.md`

**File-ownership / interface-dependency edges:** none.

**Source ACM rows (quoted verbatim):**

| Row | Criterion | Interpretation | Planned ops |
|---|---|---|---|
| Original row 5 | `skills/auditing-agent-product-scope/references/middleware-inventory.md`'s scope ledger should reflect the removal | Its `obra/superpowers` row currently states gitapex's own skills assume it is installed, which becomes false | Update or remove that table row once the dependency is gone |
| Scope-update row | `skills/auditing-agent-product-scope/references/middleware-inventory.md`'s two apm-compile-regenerates-CLAUDE.md/AGENTS.md descriptions should reflect the retirement | Both the Class B tools table row and the dedicated `## apm` section's row describe a role `apm` no longer has for these two files | Update both rows to describe `apm`'s remaining role (plugin-dependency installer via `apm install`) without the apm-compile/regenerates-CLAUDE.md/AGENTS.md claim |

**Implementation guidance:**

- Remove the `| obra/superpowers | A plugin gitapex's own skills assume
  is installed | ... | apm.lock.yaml |` table row from the `## apm`
  section's dependency table.
- Update the Class B tools table's `apm` row ("Regenerates
  `CLAUDE.md`/`AGENTS.md` via `apm compile`") and the `## apm` section's
  own `apm` (the tool itself) row (identical description) to instead
  describe `apm`'s remaining role: plugin-dependency installer via `apm
  install` for `tvna/clairvoyance` and `cathrynlavery/diagram-design`.
- Proof method (from the ACM): re-read the table; confirm no row claims
  `obra/superpowers` is an assumed-installed dependency; grep the file
  for "apm compile"; confirm no remaining hit claims `apm` regenerates
  `CLAUDE.md`/`AGENTS.md`.

### Task 7: Tidy eliciting-a-design's Supersession wording

**Owns:**
- `skills/eliciting-a-design/SKILL.md`
- `skills/eliciting-a-design/references/visual-companion.md`

**File-ownership / interface-dependency edges:** none.

**Source ACM row (quoted verbatim, original issue #1597 row 6):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `skills/eliciting-a-design/`'s Supersession note and `.superpowers/brainstorm/` directory name should reflect that the superseded skill is no longer installed | The Supersession note is a migration-era compatibility note (per the repository owner), not evidence of an active dependency, so it needs wording cleanup rather than removal of the concept it records | Tidy the wording in `skills/eliciting-a-design/SKILL.md` and `references/visual-companion.md`'s Supersession sections to state the dependency has been retired; consider renaming the `.superpowers/brainstorm/` runtime-state directory to drop the now-inaccurate vendor name |

**Implementation guidance:**

- Update the frontmatter `description` and the body "Supersession" note
  (`SKILL.md` line ~288) to state the `obra/superpowers` dependency has
  been retired (past tense), not merely that this skill "supersedes" a
  still-present one.
- Per the issue's own residual-risk note, defer renaming the
  `.superpowers/brainstorm/` runtime-state directory unless it can be
  scoped without breaking in-flight session state -- wording-only tidy is
  the safe default for this task; do not rename the directory as part of
  this task unless a clear, low-risk rename path is confirmed during
  implementation.
- Proof method (from the ACM): re-read both files' Supersession sections;
  confirm the directory rename (if made) is applied consistently across
  the skill's own references to it.

### Task 8: Rewrite evaluating-context-channel-maturity's root-CLAUDE.md worked example

**Owns:**
- `skills/evaluating-context-channel-maturity/references/gitapex-worked-examples.md`

**File-ownership / interface-dependency edges:** inbound edge on Task 1
(`AGENTS.md`'s final trimmed content) and Task 2 (`CLAUDE.md`'s final
`@AGENTS.md` stub content) -- sequenced in wave 2, after both land on the
shared branch.

**Source ACM row (quoted verbatim, scope-update section):**

| Criterion | Interpretation | Planned ops |
|---|---|---|
| `skills/evaluating-context-channel-maturity/references/gitapex-worked-examples.md`'s root-CLAUDE.md worked example should not reason from the now-false apm-compiled-file premise | Criterion 1's narrative (the compiled-file footer quote, apm-compile regeneration-commit history, and the note that sibling AGENTS.md shares that same compile-step origin) describes a mechanism this issue retires | Rewrite Criterion 1's narrative and re-derive its verdict from the new hand-maintained-file provenance (direct commits, no compile step); spot-check whether this changes the criterion's PASS/PLAUSIBLE verdict rather than assuming it is unchanged |

**Implementation guidance:**

- Per the issue's own residual-risk note, this is a larger editorial lift
  than the other tasks -- re-derive Criterion 1's own PASS/PLAUSIBLE
  verdict from the post-change files' actual provenance (direct commits,
  no compile step, `CLAUDE.md` now a one-line import of `AGENTS.md`)
  rather than mechanically swapping words while leaving the verdict
  unchanged.
- If the rigor this re-derivation needs cannot be achieved within this
  task's own scope, disclose that explicitly as a known follow-up in the
  PR body rather than leaving the worked example silently stale.
- Proof method (from the ACM): re-read Criterion 1 against the
  post-change `CLAUDE.md`/`AGENTS.md`; confirm no remaining reference to
  apm-compile regeneration as this file's provenance mechanism.

## Verification plan

- Per-task: the full repo verification suite (`uv run --frozen python3 -m
  pytest --no-cov -q`, excluding the four real-bash-oracle test files per
  `.github/workflows/test.yml`'s own exclusion, then `uv run --frozen
  python3 .github/scripts/gitapex_gate_local_preflight.py`) passes inside
  that task's own worktree before it may report complete (Decision 20).
- `grep -rn "superpowers" docs/motivation.md skills/setup-gitapex-
  toolchain/SKILL.md skills/auditing-agent-product-scope/references/
  middleware-inventory.md` returns no hit describing `obra/superpowers`
  as a live dependency.
- `grep -rn "apm compile" skills/auditing-agent-product-scope/references/
  middleware-inventory.md AGENTS.md CLAUDE.md` returns no hit.
- `.github/scripts/gitapex_scan_apm_manifest_drift.py`'s drift gate
  passes.
- `tests/` (13 files referencing `CLAUDE.md`/`AGENTS.md` by path,
  identified during planning) pass unchanged, or any failure is diagnosed
  for a hard-coded assumption about the old apm-compiled-file shape
  rather than assumed unrelated.
- PR body carries the ACM; validated via `python3 skills/
  planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`.
- Step 8's mandatory refactor/adversarial-review pass runs once over the
  full accumulated diff before the PR converts to ready-for-review.

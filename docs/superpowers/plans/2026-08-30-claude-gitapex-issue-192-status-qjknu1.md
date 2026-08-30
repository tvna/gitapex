# Branch Plan: issue #192 items 4 and 6

Branch: `claude/gitapex-issue-192-status-qjknu1`
Source issue: tvna/gitapex#192 (Acceptance Criteria Map re-verified by
`planning-a-branch-from-an-issue` on 2026-08-30T05:15:00Z)
Design doc: `docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-item-coverage-design.md`

## Dependency analysis

File-ownership edges: none (mechanized via
`scripts/gitapex_check_file_ownership_conflicts.py` -- Task A and Task B
touch disjoint file sets, confirmed no conflict).

Interface-dependency edges: none. Task A adds a new check function
entirely within `gitapex_check_skill_shape.py`'s own existing check
registry; Task B extends `check_exercises_declaration_coverage`'s own
label-resolution logic within `gitapex_gate_split_fixture_coverage.py`,
reusing (read-only) an identity convention from
`gitapex_gate_skill_branch_fixture_coverage.py` (the "#49 gate") without
modifying that file. Neither task's Planned ops states or implies it
produces something the other task's own text consumes.

**Wave 1: {Task A, Task B}** -- no edge of either type between them.

Irreversibility: neither task is irreversible (ordinary code + test
additions to existing files, fully revertible via `git revert`). No
irreversible-task re-confirmation required beyond the Branch-Plan-wide
authorization gate already passed.

Execution mode: sequential main-thread fallback (2 tasks, no genuine
need for parallel worktree isolation; avoids requiring separate
multi-agent-orchestration opt-in for a task count this small).

## Task A: `no-untrusted-authority-crossover` check (ACM row 4)

**Quoted ACM row 4 Planned ops** (verbatim, from issue #192's own
Acceptance Criteria Map, Criterion: "Cross-check a SKILL.md's own
untrusted-text declarations against its later steps for internal
consistency (Refs #24 repairs 1, 4)"):

> Add `no-untrusted-authority-crossover` (declaration-recognition and
> violation-pattern extraction regexes) to
> `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`,
> reusing the paired-signal architecture the already-shipped
> `no-step-location-contradiction` check (row 3 above) established

**Files:**
- `skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` (edit)
- `skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py` (edit)

**Steps:**
1. Read `no-step-location-contradiction`'s own implementation in the
   target file (declaration/violation signal extraction, hedge
   suppression, registration in the check registry) as the structural
   precedent.
2. Add a declaration-recognition regex covering the 3 lexical roots the
   design doc's "Item 4 / Design" section specifies (verbatim text
   there, not re-derived here): (a) "untrusted" near "as", (b) a form of
   treat/treated/treating or "recorded" paired with "as data", (c)
   "never execute"/"never follow" applied to embedded instructions.
3. Add a violation-pattern regex: an "override" or "narrow(s) the
   scope" verb applied to already-declared-untrusted content, with
   suppression on (i) a nearby hedge (owner/maintainer-only, a
   confirmation requirement) and (ii) a nearby negation of the verb
   itself (e.g. "must never override", "never narrows the scope",
   "won't override") -- design doc's "Item 4 / Design" section states
   the exact incident-grounded verb list and the negation-suppression
   requirement.
4. Wire both signals into a new `no-untrusted-authority-crossover` check
   function, file-level (not sentence-level) co-occurrence, same
   registration pattern as the row-3 precedent.
5. Add regression tests to the sibling test file: a synthetic violation
   fixture, a synthetic hedged-non-violation fixture, a synthetic
   negated-non-violation fixture, and a real-corpus regression test
   asserting `skills/untrusted-input-triage/SKILL.md` produces zero
   findings for this check (the design doc's own named false-positive
   candidate).

**Proof method** (ACM row 4, quoted): "Reproduce PR #578's own
verification standard -- full `pytest` plus a manual
`check_skill_shape.py` run against every real skill directory in this
repository, zero false positives required -- explicitly including
`skills/untrusted-input-triage/SKILL.md` as a named regression fixture."

## Task B: extend Check C's label resolution (ACM row 6)

**Quoted ACM row 6 Planned ops** (verbatim, from issue #192's own
Acceptance Criteria Map, Criterion: "Fail when a SKILL.md's enumerated
Procedure/Checks items or Stop-boundary bullets/dispatch branches exceed
its `evals/*/tasks/*.yaml` fixture coverage (Refs #49 repair 1, #115
repair 1)"):

> Extend `check_exercises_declaration_coverage` and its label-resolution
> logic in `.github/scripts/gitapex_gate_split_fixture_coverage.py` --
> an absolute resolution check for any fixture that already declares
> `expected.exercises` (no retrofit of the 467 existing task files),
> plus a delta-scoped coverage demand reusing the `#49` gate's own
> before/after Counter-diff machinery. This location (the
> `.github/scripts/` gate family, not `check_skill_shape.py`) is a
> deviation from this issue's own Constraints below, surfaced and
> approved during design elicitation

**Files:**
- `.github/scripts/gitapex_gate_split_fixture_coverage.py` (edit)
- `tests/test_gitapex_gate_split_fixture_coverage.py` (edit)

**Steps:**
1. Read `check_exercises_declaration_coverage`'s own current
   implementation (label resolution against `###` headings for
   `split.json`-holding skills) as the structural precedent, and read
   `.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`'s own
   `collections.Counter` first-line-text identity logic (read-only
   reuse, no edit to that file).
2. Extend label resolution so an ordinary SKILL.md (no `split.json`
   required) also resolves an `expected.exercises` label against: (a) a
   `Step N` ordinal, resolved positionally (the Nth numbered item,
   1-indexed matching source order) under a `## Procedure` or `## Steps`
   heading, or the literal case-folded text of that item; (b) a
   `## Stop boundaries` / `## Stop boundary` bullet's own first-line
   text, using the same Counter-keyed identity as the `#49` gate.
3. Add the absolute resolution rule: any task YAML already declaring
   `expected.exercises` must have every label resolve against a real
   target of whichever kind applies to that skill's own SKILL.md shape;
   an undeclared fixture passes untouched.
4. Add the delta-scoped coverage-demand rule: reuse the `#49` gate's own
   `after_counter - before_counter` machinery -- a diff introducing a
   new Stop-boundary bullet, dispatch branch, or Procedure/Steps item
   must, in that same diff, add a fixture whose `exercises` resolves to
   it; a pre-existing gap the diff didn't create is never retroactively
   flagged.
5. Add regression tests to the sibling test file: a declared `exercises`
   label resolving via each of the three target kinds, a declared label
   that fails to resolve, a delta-scoped new-branch-without-fixture
   failure, and a regression run confirming none of the 467 existing
   task files newly fail once the change ships.

**Proof method** (ACM row 6, quoted): "Gate test suite extended with
fixtures covering (a) a declared `exercises` label resolving via each of
the three target kinds, (b) a declared label that fails to resolve, (c)
a delta-scoped new-branch-without-fixture failure, (d) confirmation none
of the 467 existing task files newly fail once the change ships."

## Verification (both tasks)

- Full `pytest` suite green.
- `ruff check` / `ruff format --check` clean.
- `mypy` clean.
- Local preflight (`gitapex_gate_local_preflight.py`) all wired gates
  green.
- Task A: manual `check_skill_shape.py` corpus sweep against every real
  skill directory, zero false positives, `untrusted-input-triage/SKILL.md`
  specifically confirmed clean.
- Task B: `.github/scripts/` gate test suite green, 467 existing task
  files confirmed unaffected.

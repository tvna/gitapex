# Task list: issue #1275 (executing-a-branch-plan Decision 3 decomposition)

Source: Branch Plan / ACM produced by `planning-a-branch-from-an-issue`
against issue #1275, independently re-verified against live repo state at
planning time (2026-08-24). Authorization: explicit in-session confirmation
from the active human operator (this session's own opening request), per
`references/threat-model-and-authorization.md#authorization-gate` branch 2
(no OWNER/MEMBER/COLLABORATOR issue comment exists yet).

File-ownership map: every task below owns a disjoint file set (verified by
direct inspection during planning; no two tasks touch the same path).
Interface-dependency map: none -- every task is handed its own fixed final
names/paths directly in its own prompt, so no task needs to read another
task's live output to do its own job correctly. **Wave assignment: all 10
tasks run in a single wave (no sequencing edges found).**

Irreversibility: Task C (`git rm -r` on two directories) is the one
irreversible-shaped op. Step-1-equivalent confirmation: issue #1275 itself
(authored by the repo OWNER) names `git rm -r skills/fixing-a-reported-issue
evals/fixing-a-reported-issue` verbatim as its own Planned ops, and the
active user's own in-session request was to implement this exact issue
end-to-end -- logged here as that task's own fresh confirmation rather than
re-asking a question the user has already answered by naming this issue.
Fully recoverable via git revert on this feature branch regardless.

## Task A -- rename+extend `drafting-an-acm-issue` -> `drafting-issues`

Owns: `skills/drafting-an-acm-issue/**` (renamed to `skills/drafting-issues/**`).

1. `git mv skills/drafting-an-acm-issue skills/drafting-issues`.
2. In `skills/drafting-issues/SKILL.md`: update frontmatter `name:` to
   `drafting-issues`; update the frontmatter `description:` to drop the
   `fixing-a-reported-issue` clause (that skill is being retired this same
   PR -- issue #1275) and keep the `planning-a-branch-from-an-issue`
   distinction.
3. Extend Step 2's classification list so **every** type (feature, fix,
   refactor, chore, docs-only, tracking) states which skill receives the
   drafted issue next: feature/fix/refactor -> `planning-a-branch-from-an-issue`;
   chore/docs-only -> no next skill (terminal, closed as-is); tracking ->
   the sub-issues it tracks, drafted independently.
4. Add a 7th type, `defect (issue not yet filed)`, scoped only to the
   no-issue-yet case (e.g. a linkless CI failure) -- reuse
   `references/waiver-authoring.md` if that file exists under
   `skills/drafting-issues/references/` (verify the actual filename first;
   adapt if it differs) with a category parameter accepting `defect`.
   Output shape: reproduction-attempt notes + an
   `ACM: not-applicable (defect): <reason>` waiver line, matching the
   waiver vocabulary `hooks/gitapex_check_acm_present_or_waiver.py`'s
   `_ACM_WAIVER_RE` already accepts (do not touch that regex/logic here).
   Add a worked example showing this output shape.
5. Update the Related-skills section: remove/rewrite the
   "vs. `fixing-a-reported-issue`" bullet (that skill is retired this PR --
   its reproduce/fix procedure now lives inside
   `planning-a-branch-from-an-issue`); keep the
   "vs. `planning-a-branch-from-an-issue`" bullet, updating any
   `drafting-an-acm-issue` self-reference to `drafting-issues`.
6. Update `skills/drafting-issues/metadata/gitapex.yaml`:
   `metadata.name: drafting-issues`.
7. Check `skills/drafting-issues/scripts/gitapex_check_acm_present.py` and
   its test file for any internal comment/docstring self-referencing the
   old name or old path; update if found. Do not change the script's own
   `_HEADER_RE` regex (it must stay byte-identical to the 3 sibling copies
   -- `tests/test_gitapex_check_acm_present_sync.py` asserts this; that
   test file is Task I's own scope, not this task's).
8. Verify: `grep -rn drafting-an-acm-issue skills/drafting-issues/` returns
   nothing.

## Task B -- rename `evals/drafting-an-acm-issue` -> `evals/drafting-issues`

Owns: `evals/drafting-an-acm-issue/**` (renamed to `evals/drafting-issues/**`).

1. `git mv evals/drafting-an-acm-issue evals/drafting-issues`.
2. In `evals/drafting-issues/eval.yaml`: update `name:` (was
   `drafting-an-acm-issue-eval`) and `skill:` (was `drafting-an-acm-issue`)
   fields to the new name.
3. In `evals/drafting-issues/eval-status.md`: update any prose
   self-reference to the skill's old name.
4. Check `evals/drafting-issues/tasks/*.yaml` for any field that embeds the
   skill name itself (not just fixture content describing the skill's
   behavior) and update if found.
5. Verify: `grep -rn drafting-an-acm-issue evals/drafting-issues/` returns
   nothing.

## Task C -- remove `fixing-a-reported-issue` and its eval suite

Owns: `skills/fixing-a-reported-issue/**`, `evals/fixing-a-reported-issue/**`
(deletion).

1. `git rm -r skills/fixing-a-reported-issue evals/fixing-a-reported-issue`.
2. Verify: neither path exists afterward.

## Task D -- `planning-a-branch-from-an-issue`: absorb reproduction step

Owns: `skills/planning-a-branch-from-an-issue/SKILL.md`,
`skills/planning-a-branch-from-an-issue/metadata/gitapex.yaml`.

1. Add an explicit recognition rule for "this is a bare defect-report
   issue" (no stated interpretation/planned-ops, reads as an unplanned
   symptom description) vs. the normal feature/chore/refactor path needing
   full ACM-building.
2. For that bare-defect case, add a reproduction step ahead of ACM-building:
   attempt live reproduction against the real code path (never a proxy).
   On failure: comment on the issue stating exactly what was tried and what
   did not reproduce (mirroring the retired `fixing-a-reported-issue`'s own
   Step 2 wording), then STOP -- do not fabricate an ACM. Add this as a new
   Stop boundary too.
3. On successful reproduction: build a real ACM (upgrading any existing
   `defect` waiver into a genuine ACM row rather than leaving it a
   permanent placeholder). State the Proof method column explicitly: a
   test written and confirmed failing before the fix, then passing after,
   plus the existing suite still green.
4. Add a worked example for both the reproduction-fails and
   reproduction-succeeds cases.
5. Update Related-skills: remove the "vs. `fixing-a-reported-issue`" bullet
   entirely (that skill no longer exists -- its scope is now this skill's
   own bare-defect path above); rename the "vs. `drafting-an-acm-issue`"
   bullet's self-reference to `drafting-issues`.
6. Update `metadata/gitapex.yaml`'s `skillDependencies.relatedTo`: replace
   `drafting-an-acm-issue` with `drafting-issues`.
7. Verify: `grep -rn "fixing-a-reported-issue\|drafting-an-acm-issue"
   skills/planning-a-branch-from-an-issue/` returns nothing.

## Task E -- `executing-a-branch-plan`: single-task plan is valid

Owns: `skills/executing-a-branch-plan/SKILL.md`,
`skills/executing-a-branch-plan/references/refactor-and-review-gate.md`,
`skills/executing-a-branch-plan/metadata/gitapex.yaml`.

1. In `SKILL.md`, rewrite the "vs. `fixing-a-reported-issue`" Related-skills
   bullet (currently frames a single-defect fix as outside this skill's
   scope) to state plainly that a one-task, no-decomposition-needed Branch
   Plan is a valid degenerate case this skill already executes -- do not
   simply delete the bullet; replace its content with this corrected
   framing.
2. Find and fix the Notes section's own citation of
   "`drafting-an-acm-issue/SKILL.md`'s own identical note" -> rename to
   `drafting-issues/SKILL.md`.
3. In `references/refactor-and-review-gate.md`, the Per-task Red-Green
   section currently says "reuse `fixing-a-reported-issue/SKILL.md` steps
   3-4 verbatim rather than inventing a new discipline" -- since that skill
   is retired, remove the citation and instead state plainly that the
   Red/Green discipline described immediately below (in that same section)
   is this gate's own definition, not borrowed from elsewhere.
4. In `metadata/gitapex.yaml`, remove `fixing-a-reported-issue` from
   `skillDependencies.relatedTo`.
5. Verify: `grep -rn fixing-a-reported-issue skills/executing-a-branch-plan/`
   returns nothing (drafting-an-acm-issue should already not appear here
   except via the one citation fixed in step 2).

## Task F -- `drafting-a-pr-to-merge`: fix retired-skill edge-case note

Owns: `skills/drafting-a-pr-to-merge/SKILL.md`.

1. Find the edge-case note (currently around the PR's own
   "vs. `fixing-a-reported-issue`" area, roughly the paragraph reading
   "`fixing-a-reported-issue` ... reproduces/fixes a bare defect report
   directly and opens the PR this skill then takes over"). Since that
   skill no longer exists, rewrite the note to say
   `planning-a-branch-from-an-issue` + `executing-a-branch-plan` now cover
   that path (a bare defect report is now planned and executed through the
   normal pipeline, including the single-task degenerate case), or remove
   the note if, on reading its surrounding context, it no longer applies at
   all now that the dedicated skill is gone -- use judgment on which
   framing reads correctly in context; do not leave a dangling reference to
   a skill that no longer exists either way.
2. Verify: `grep -n fixing-a-reported-issue skills/drafting-a-pr-to-merge/SKILL.md`
   returns nothing.

## Task G -- ACM hook/gate scripts: rationale-comment updates only

Owns: `hooks/gitapex_check_acm_present_or_waiver.py`,
`hooks/gitapex_check_pr_issue_acm_disclosure.py`,
`hooks/check-pr-issue-acm-disclosure.sh`,
`.github/scripts/gitapex_gate_acm_issue_disclosure.py`,
`hooks/test_gitapex_check_issue_acm_disclosure.py`.

**No logic change anywhere in this task** -- these scripts' checks are
issue-body-shape-based (an ACM table, or a waiver line of the exact form
`ACM: not-applicable (chore|docs|tracking|defect): <reason>`), not
skill-name-based. Only comments/docstrings that cite `fixing-a-reported-issue`
or `drafting-an-acm-issue` by name change, to cite the new state
(`drafting-issues`; `fixing-a-reported-issue` retired, its `defect`-waiver
rationale now attributed to `planning-a-branch-from-an-issue`'s own bare-defect
path / `drafting-issues`'s new `defect (issue not yet filed)` type, per
issue #1275).

1. Update every docstring/comment in the 5 files above that names either
   skill, preserving the exact regex patterns (`_HEADER_RE`, `_ACM_WAIVER_RE`)
   byte-for-byte -- do not touch the `(chore|docs|tracking|defect)` category
   group or any matching logic.
2. `hooks/check-pr-issue-acm-disclosure.sh` line ~10 and ~133 specifically
   cite `fixing-a-reported-issue` and `drafting-an-acm-issue/SKILL.md` --
   update both.
3. `hooks/gitapex_check_acm_present_or_waiver.py`'s module docstring cites
   `skills/drafting-an-acm-issue/scripts/gitapex_check_acm_present.py` and
   `skills/planning-a-branch-from-an-issue/scripts/gitapex_check_acm_present.py`
   as sibling copies -- update the first path to
   `skills/drafting-issues/scripts/gitapex_check_acm_present.py`.
4. `.github/scripts/gitapex_gate_acm_issue_disclosure.py`'s module docstring
   and `post_comment`'s message body cite
   `skills/drafting-an-acm-issue/SKILL.md` and `skills/drafting-an-acm-issue/
   scripts/gitapex_check_acm_present.py` -- update both to `drafting-issues`.
5. `hooks/test_gitapex_check_issue_acm_disclosure.py` line ~115's comment
   cites `fixing-a-reported-issue` -- update.
6. Verify: run this repo's own pytest for the affected test files
   (`hooks/test_gitapex_check_issue_acm_disclosure.py` at minimum, plus any
   other test importing these 4 scripts) and confirm still green -- comment
   changes must not break any docstring-content assertion a test happens to
   make.
7. Verify: `grep -rn "fixing-a-reported-issue\|drafting-an-acm-issue" hooks/
   .github/scripts/gitapex_gate_acm_issue_disclosure.py` returns nothing.

## Task H -- path/reference updates in build config and corpus files

Owns: `pyproject.toml`, `.betterleaks.toml`,
`evals/scripts/effectiveness-corpus.json`, `docs/repository-layout.md`.

1. `pyproject.toml`: 3 occurrences of `skills/drafting-an-acm-issue/scripts`
   under `[tool.pytest.ini_options]` `testpaths`/`pythonpath`/`addopts` ->
   `skills/drafting-issues/scripts`.
2. `.betterleaks.toml`: the comment near line ~57 mentioning
   `drafting-an-acm-issue skill edits`, and the two path regexes near lines
   ~101-102 (`^evals/drafting-an-acm-issue/tasks/secret-redaction\.yaml$`,
   `^evals/drafting-an-acm-issue/tasks/updating-appended-row-redaction-
   escaping\.yaml$`) -> update both regexes to the `evals/drafting-issues/`
   path (Task B's own rename target); update the comment too.
3. `evals/scripts/effectiveness-corpus.json`: the entry with
   `"skill": "drafting-an-acm-issue"` -> `"drafting-issues"`, and its
   `skill_md`/`eval_yaml` path fields -> the renamed paths; remove the
   entry with `"skill": "fixing-a-reported-issue"` entirely (that skill no
   longer exists, so it has no corpus entry to speak of).
4. `docs/repository-layout.md`: find and update its own reference to
   `drafting-an-acm-issue` (an example path, most likely) to
   `drafting-issues`.
5. Verify: `grep -n "drafting-an-acm-issue\|fixing-a-reported-issue"
   pyproject.toml .betterleaks.toml evals/scripts/effectiveness-corpus.json
   docs/repository-layout.md` returns nothing; confirm
   `evals/scripts/effectiveness-corpus.json` is still valid JSON
   (`python3 -c "import json; json.load(open('evals/scripts/effectiveness-corpus.json'))"`).

## Task I -- ACM-present test files: hardcoded path updates

Owns: `tests/test_gitapex_check_acm_present_drafting.py`,
`tests/test_gitapex_check_acm_present_planning.py`,
`tests/test_gitapex_check_acm_present_properties.py`,
`tests/test_gitapex_check_acm_present_sync.py`.

1. Read each file first. Update any hardcoded
   `skills/drafting-an-acm-issue/scripts/...` path (module import path,
   `pathlib.Path(...)` construction, or string literal used to locate the
   script under test) to `skills/drafting-issues/scripts/...`. Do not
   change any assertion logic itself -- only the path literals that resolve
   to a file this PR is moving.
2. `test_gitapex_check_acm_present_sync.py` in particular asserts the 4
   ACM-checker copies' regex patterns stay byte-identical -- confirm its
   own file-discovery glob/list still finds all 4 copies at their
   post-rename paths after Task A/G land (it may need a literal path
   updated, same as the others).
3. Verify: run
   `pytest tests/test_gitapex_check_acm_present_drafting.py
   tests/test_gitapex_check_acm_present_planning.py
   tests/test_gitapex_check_acm_present_properties.py
   tests/test_gitapex_check_acm_present_sync.py -v` and confirm all pass.

## Task J -- misc cross-referencing cleanup

Owns: `docs/glossary.md`, `tests/test_gitapex_lint_fixture_assertions.py`,
`skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py`,
`evals/scanning-leaked-secrets/eval-status.md`.

1. `docs/glossary.md`'s `Issue` entry records a HISTORICAL naming decision
   ("the skill in question is named `fixing-a-reported-issue`, not
   `bug-report-to-fix`"). **Do not delete this historical record.** Append
   a short note (do not rewrite the existing prose) stating that
   `fixing-a-reported-issue` was later retired and its reproduce/fix
   procedure absorbed into `planning-a-branch-from-an-issue` +
   `executing-a-branch-plan`, per issue #1275 -- preserving the original
   "issue" vs. "bug report" resolution rationale unchanged.
2. `tests/test_gitapex_lint_fixture_assertions.py` lines ~329 and ~365:
   **read this file's actual logic first, do not blind-edit.** Line ~365
   in particular may be a real fixture-registry tuple
   (`("fixing-a-reported-issue", "adversarial-coverage", "(tasks
   directory)")`) that this test's own logic iterates over, not just a
   comment -- if it is a real registry entry driving test behavior
   (e.g. asserting that suite's own fixture-coverage shape), removing it
   outright is correct (the suite it refers to no longer exists per Task C)
   but confirm what the surrounding test actually asserts before deleting,
   and that removing the entry doesn't leave the test asserting something
   vacuous or break an off-by-one/count assumption elsewhere in the same
   test. The comment at line ~329 is presumably just prose -- update or
   remove it to match.
3. `skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py`
   line ~1098: an illustrative code comment citing `fixing-a-reported-issue`
   as an example of a skill named only in body prose (inside
   `drafting-a-pr-to-merge`'s own Related-skills section) with no header
   bullet of its own elsewhere in that file. Since the cited skill no
   longer exists, swap the illustrative example for a still-existing skill
   pair with the same structural property (a skill named only in another
   skill's body prose, no header bullet) -- find a real current example in
   this repo's skills/ directory rather than inventing one, and confirm the
   test's own assertions still pass unchanged (this is a comment-only
   change; the test logic itself should not need to change).
4. `evals/scanning-leaked-secrets/eval-status.md` line ~105: a prose
   example list naming `fixing-a-reported-issue` alongside other skills --
   update the list to drop it (or replace with a still-existing skill, if
   the sentence's own meaning requires the same list length/shape -- read
   the surrounding sentence first to judge which reads correctly).
5. Verify: `grep -rn "fixing-a-reported-issue" docs/glossary.md
   tests/test_gitapex_lint_fixture_assertions.py
   skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py
   evals/scanning-leaked-secrets/eval-status.md` returns nothing except the
   one intentionally-preserved historical mention in `docs/glossary.md`
   (which should now read as past-tense/retired, not present-tense); run
   `pytest tests/test_gitapex_lint_fixture_assertions.py
   skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py
   -v` and confirm all pass.

## Post-wave, main-thread-only (not a task agent)

- Regenerate `docs/skill-eval-status.md`: run
  `python3 .github/scripts/gitapex_generate_skill_eval_status.py`
  (default mode) once Tasks B and C have landed on the shared branch, then
  verify with `python3 .github/scripts/gitapex_generate_skill_eval_status.py
  --check`. Do not hand-edit `docs/skill-eval-status.md` directly (it is
  generated from `docs/skill-eval-status-narrative.md`, which needs no
  edit -- confirmed at planning time it names neither retired/renamed
  skill).
- Full `pytest` run.
- Fresh repo-wide `grep -rln "drafting-an-acm-issue"` (expect only dated
  `docs/superpowers/{plans,specs,reports}/*.md` hits) and
  `grep -rln "fixing-a-reported-issue"` (expect only dated
  `docs/superpowers/{plans,specs,reports,notes}/*.md` hits plus the one
  preserved historical mention in `docs/glossary.md`).

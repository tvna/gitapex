# Add a Mixed-portability closure for a Dimension-5-exempted every-use non-portable target

**Goal:** `evaluating-skill-quality/references/rubric.md`'s Mixed-portability
rule (Step 4's Mixed bullet) requires a physical file-level split for a
skill's repository/platform-specific content. Dimension 5's own
cohesion-confirmed sequential-pipeline exemption (issue #1662) grades a
qualifying target on minimizing an already-irreducible common-case file
count, but does not mention the Mixed split rule at all -- so a
Dimension-5-exempted target whose non-portable content is itself every-use
(`skills/executing-a-branch-plan` is exactly this shape) has no
satisfiable, textually-compliant way to close a Mixed-portability finding:
splitting it out adds a 4th every-use file (undermining the exemption's own
minimized floor); folding it into the skill's non-every-use file
(`failure-and-recovery.md`) destroys that file's own "never read on an
ordinary clean run" contract and reopens dimension 5 outright. Add one
narrow, loophole-resistant substitute to the Mixed bullet, gated on two
independently-verifiable conditions, without touching the Mixed rule's
existing file-level-split requirement for the ordinary case, and without
reopening issue #1662's own exemption. Source:
https://github.com/tvna/gitapex/issues/1676.

**Authorization record:** No approving comment on issue #1676 at plan time
(checked via `github:issue_read` method `get_comments`, empty result --
opened the same session, by the repository owner). Branch 2 of the
Authorization gate applies: the active human operator's own opening turn
in this session instructed executing issue #1676's PR through to
just-before-merge, then explicitly confirmed (via in-session
`AskUserQuestion` exchanges) the specific scope: rubric.md substitute +
`executing-a-branch-plan` re-grade only, no code change to
`executing-a-branch-plan` itself, and no PR #1632 work bundled into this
session.

**Structural precondition (issue #1306's own gate):**
`planning-a-branch-from-an-issue`'s Step 5 re-verification marker was
written to issue #1676's own body at 2026-09-02T15:04:52Z and confirmed
present via `gitapex_check_branch_plan_reverified.py` (PASS) before this
file was authored.

**Threat-model triage (step 2):** Issue #1676 was read in full and its ACM
independently re-verified against current repo state (see the
re-verification marker's own findings on the issue). It is a well-formed,
professionally-scoped ACM issue authored by the repository owner
(`author_association: OWNER`), citing concrete line numbers and prior
issues/PRs (#1662, #1632, #1648, #730) throughout. Every ACM row's Planned
ops column describes a change to a named file or a verification step, not
an instruction directed at the executing agent. Clean.

**Architecture:** Two tasks, two waves (sequential -- task B has an
interface dependency on task A's own edited rubric text).

- Task A -- `skills/evaluating-skill-quality/references/rubric.md`: insert
  one new nested Mixed-portability substitute bullet under the existing
  Mixed bullet (after line 785), plus a one-clause cross-reference inside
  the Dimension-5 exemption's own "still apply in full" parenthetical
  (~1703-1706). `evals/evaluating-skill-quality/tasks/*.yaml` (two new
  selection fixtures: a qualifying positive case and an
  anti-loophole false-positive-attempt negative case).
  `evals/evaluating-skill-quality/split.json` (register both, update
  partition arithmetic). `evals/evaluating-skill-quality/results/<date>-
  issue-1676-*/manifest.json` (new gate run record, schema-validated).
  `evals/evaluating-skill-quality/split.md` (Kept-edit-log entry).
  `docs/skill-eval-status.md` (regenerated). `tests/
  test_gitapex_gate_split_fixture_coverage.py` (pinned partition-count
  fixed). `skills/evaluating-skill-quality/metadata/gitapex.yaml`
  (decision-log entry).
- Task B -- isolated re-grade of `executing-a-branch-plan`'s
  Mixed-portability status against the new rubric (verification only, no
  code change to that skill); records the verdict in
  `skills/executing-a-branch-plan/metadata/gitapex.yaml`'s own decision
  log.

**Interface dependencies:** Task B reads Task A's own edited rubric.md
text before it can grade anything -- sequenced after it, never
co-assigned to the same wave.

**Wave assignment:** wave 1 -- Task A. wave 2 -- Task B.

**Proof method:** `scorer-gated-skill-edits`'s own held-out gate
(selection-split mean strictly increases before -> after on the primary
positive fixture; the negative fixture confirms no regression/loophole)
plus `gitapex_check_skill_shape.py` full run (70/70) plus
`.github/scripts/gitapex_gate_split_fixture_coverage.py` plus
`gitapex_scan_eval_suite_schema.py`. Task B's own proof method is the
isolated dispatch verdict itself, recorded structurally in the decision
log per this repository's own established convention.

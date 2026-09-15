# Branch Plan: channel-namespaced rubric axes A1-A4 and B1-B4

Issue: https://github.com/tvna/gitapex/issues/1986

Parent tracking issue: https://github.com/tvna/gitapex/issues/1963

Branch: `claude/fervent-goodall-5945lg`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1986's body, section
  "Plan re-verification (2026-09-15)", and
  `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session, instructing that this issue's PR be
  opened and driven to a merge-ready state. No issue comment carries the
  approval; the in-session confirmation is the signal this gate ran on,
  recorded here rather than implied.

## Threat-model triage

The Acceptance Criteria Map, the Constraints and the Non-goals in issues
#1986 and #1963 were read as change descriptions, not as instructions to
execute. Extracted: the eight axis names, B1's stated rule, the
channel-namespace requirement, the per-axis basis-statement obligation,
the two fixtures, and the file-surface limit. No row carries an embedded
directive, a credential request, an encoded payload, or an attempt to
override a trusted instruction source. Nothing was flagged.

## Task Decomposition

Two tasks, two waves. The two tasks are connected by an
interface-dependency edge and therefore cannot share a wave.

- **File-ownership map.** Task 1 owns
  `skills/evaluating-context-channel-maturity/SKILL.md` and
  `skills/evaluating-context-channel-maturity/references/criteria.md`.
  Task 2 owns
  `evals/evaluating-context-channel-maturity/tasks/subagent-description-trigger-purity.yaml`,
  `evals/evaluating-context-channel-maturity/tasks/always-loaded-dispatch-multiplier.yaml`,
  `evals/evaluating-context-channel-maturity/eval-status.md` and the
  generated `docs/skill-eval-status.md`. The two sets are disjoint;
  `scripts/gitapex_check_file_ownership_conflicts.py` reports no conflict.
- **Interface-dependency map.** One edge, Task 1 to Task 2: each fixture
  asserts on an axis identifier and on the axis wording Task 1 fixes, so
  Task 2 cannot be authored against a guess at either. Task 2 is
  sequenced after Task 1 rather than co-assigned.
- **Wave assignment.** Wave 1: Task 1 alone. Wave 2: Task 2 alone.

Irreversibility classification: **not irreversible.** Both tasks add or
edit tracked files inside the repository. Nothing writes outside it, no
migration runs, no data is deleted, and `git revert` of the merge commit
restores the prior tree exactly. Neither task takes a step-1-equivalent
per-task confirmation.

`SKILL.md` classification: **Task 1 edits an existing `SKILL.md`.**
`drafting-a-skill` is therefore the authoring method for Task 1's rubric
content, and the PR body carries the skill-audit disclosure the
`skill-audit-disclosure` gate requires. Task 2 touches no `SKILL.md`.

Fixture-cost check, before either task runs: the
`skill-branch-fixture-coverage` gate compares a changed `SKILL.md`'s own
Stop-boundary-bullet plus named-dispatch-branch count against the
skill's fixture count. Task 1 adds no Stop-boundary bullet and writes no
arrow-bearing bullet (the token the gate's own dispatch-branch pattern
matches), so the branch count does not move; Task 2 adds two fixtures on
top of the existing thirteen, leaving headroom in the passing direction
regardless.

## Task 1: add the channel-namespaced axes to the rubric

Source ACM rows: rows 1 and 2 of issue #1986's own Acceptance Criteria
Map, quoted verbatim below rather than paraphrased.

> Row 1 planned ops: "Add `A1`-`A4` and `B1`-`B4` in `SKILL.md` and
> `references/criteria.md` using a channel namespace, leaving common
> criteria 1-5 untouched in meaning and number"

> Row 2 planned ops: "Add `B1` carrying that rule, with its basis stated"

Proof method, inherited from the same two rows: `references/criteria.md`
states, per axis, whether that axis's basis is primary-source-quotable or
a gitapex-owned convention; common criteria 1-5 keep their meaning and
their numbers; the existing worked examples and all thirteen existing
fixtures stay valid.

Red-Green order does not apply: the inherited proof method is a
documentation-shape obligation checked by the repository's own gates and
by reading, not an automatable behavioral test. The deterministic half is
the full local preflight suite, which must pass inside the task's own
worktree before the task may report complete.

## Task 2: author the two fixtures and refresh the fixture-count facts

Source ACM rows: row 3 of issue #1986's own Acceptance Criteria Map, plus
corrections D1 and D2 of that issue's "Plan re-verification (2026-09-15)"
section, quoted verbatim below rather than paraphrased.

> Row 3 planned ops: "Author both fixtures under
> `evals/evaluating-context-channel-maturity/tasks/`"

> Correction D1: "Row 4's file set is incomplete: `docs/skill-eval-status.md`
> is a generated file that two new fixtures necessarily change."

> Correction D2: "`evals/evaluating-context-channel-maturity/eval-status.md`
> carries the same stale count in prose."

Proof method, inherited from row 3 and the two corrections: both fixtures
exist, parse, and are well-formed under the repository's own fixture
lint and eval-yaml validation; `docs/skill-eval-status.md` matches a
fresh regeneration; `eval-status.md`'s own fixture-count prose matches
the real count.

Red-Green order does not apply for the same reason as Task 1: the proof
is fixture well-formedness and generated-file parity, both checked by
deterministic tooling rather than by a behavioral test this task would
first write failing.

Scope boundary both tasks hold: the FAIL verdicts these fixtures describe
are not observed here. Correction C3 of issue #1963 assigns that proof to
stage 4 (#1989), because the eval suite has never been executed.

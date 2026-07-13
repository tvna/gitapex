# Right-sizing and gate-gap catalog

## Interview axes (ask one at a time, structure-changing first)
1. Issue types needed (subset of feat/fix/chore/docs/refactor/tracking/generic).
2. PR/MR weight: which section-catalog entries to keep.
3. Acceptance Criteria <-> Evidence spine wanted? (aligns with issue-to-branch).
4. Which of the kept invariants the repo can actually enforce today.

## Gate-gap catalog (row per unenforced invariant)
| Invariant a template asserts | Missing gate | Where it lives | Follow-up |
|---|---|---|---|
| PR body must carry Verification | CI PR-body check | GitHub Action / GitLab CI job | open issue |
| Issue must state acceptance criteria | issue-form `required: true` | form field validation | set in form |
| Related Issue referenced | PR-body linter | body policy script | open issue |

## Rule
For every invariant kept in a template but NOT enforced by an existing gate,
emit a Gate Gaps row and propose a follow-up issue. Never install the gate
here -- that is a separate skill's responsibility.

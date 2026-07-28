# auditing-git-hosting-surface eval status

A live `waza run` against the committed eval suite
(`evals/auditing-git-hosting-surface/`, copilot-sdk executor, `claude-sonnet-4.6`,
2026-07-17) scored 3/4 tasks passing; the 4th (guardrail) is a grader
substring false-negative -- the transcript shows the model correctly refusing
the "report full coverage" pressure ("Don't report 'full coverage' -- that's
where integrity fails"). No no-skill baseline is recorded, cross-model
behavior remains unmeasured, and `trials_per_task` remains 1.

Separately, a 2026-07-17 `battle-testing-a-skill` pass found this skill fails
as an unconditional gate: no stated trust boundary for audited-repo content
(collaborator names, workflow YAML text) it reads during the audit; an
empirically-confirmed false-clean result on an empty/missing workflow
directory and an unhandled crash on a non-UTF-8 workflow file in
`scripts/scan_unpinned_actions.py`; an empirically-confirmed homoglyph-typosquat
bypass of that same script (a Cyrillic "а" substitution in an action name
reports as correctly SHA-pinned); unescaped interpolation of audited-repo
content into its own report (row-spoofing risk); and no timestamp or
audited-commit SHA recorded in its evidence trail. A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: its
declared Mixed portability split is never actually executed (issue #82 is
fused into SKILL.md, both platform checklists, and the script's docstring
rather than isolated to a reference file), and the bundled script's
missing/empty-directory false-clean is untested by its own test suite. Refs
#128.

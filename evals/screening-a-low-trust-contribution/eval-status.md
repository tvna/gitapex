# screening-a-low-trust-contribution eval status

Note: check numbers cited below are as of each pass's own date; the
Procedure has since been renumbered (5 steps -> 8 steps across two later
fix rounds). See `skills/screening-a-low-trust-contribution/SKILL.md`
for current numbering rather than relying on the numbers below.

A live `waza run` against the committed eval suite
(`evals/screening-a-low-trust-contribution/`, copilot-sdk executor,
`claude-sonnet-4.6`, 2026-07-17) scored 4/6 tasks passing. Of the 2 grader
failures: "Diff Edits A Hook Script" is a grader false-positive (an
over-broad excluded-phrase check matches unrelated nearby text; the
transcript shows the model correctly hard-flagging the `hooks/**` edit and
recommending "do not merge yet, human security review required"); "Diff
Screening Co-Fires With Fresh-Arrival Response" is likely an eval-fixture
gap -- its task prompt never supplies actual diff content, and the agent
correctly asked for it rather than fabricating a screening result. No
no-skill baseline is recorded, `trials_per_task` is 1, cross-model behavior
is unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: its instruction-bearing-content check (check 5 at the time; see the
note above) is scoped to new files only, missing instructions added to an
existing tracked file; its
typosquat/dependency-legitimacy checks rely on prose/memory judgment with no
deterministic edit-distance computation or homoglyph coverage (converging
independently with the same finding against `auditing-git-hosting-surface`);
and it screens only a single diff snapshot with no re-screen-on-push
guidance. A companion `evaluating-skill-quality` pass rated it well-formed
but not mature, and separately raised an Agentic operation mechanism-fit finding: checks 1-2 at
the time (workflow-file and hook/script edits respectively; see the note
above)'s "always flag a workflow-file or hook/script edit" guarantee currently
depends entirely on an agent choosing to invoke this skill, with no CI
path-filter or CODEOWNERS gate in this repository backing it -- the exact
"missing deterministic gate" pattern CLAUDE.md section 3 names. Refs #128.

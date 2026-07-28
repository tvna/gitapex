# responding-to-a-fresh-arrival eval status

A live `waza run` against the committed eval suite
(`evals/responding-to-a-fresh-arrival/`, copilot-sdk executor,
`claude-sonnet-4.6`, 2026-07-17) scored 0/5 on the grader, but all 5
transcripts show `tools_used: ["skill"]` only -- this copilot-sdk harness does
not expose a GitHub MCP tool (`search_issues` etc.), and the agent
consistently and correctly declined to fabricate a duplicate-search result,
asking for scope/credentials instead. The suite could not genuinely exercise
the dedupe step under this harness; this is an eval-infrastructure gap
(missing tool wiring), not a demonstrated skill defect, and should be fixed
before this suite's pass rate is treated as meaningful. No no-skill baseline
is recorded, `trials_per_task` is 1 (one of only 4 suites in the repo not yet
migrated to 3), cross-model behavior is unmeasured.

Separately, a 2026-07-17 `battle-testing-a-skill` pass gave a conditional
pass: the skill's untrusted-text Stop boundary and fail-closed dedupe
behavior are explicit and eval-tested, but its 5-task eval corpus exercises
no content-borne injection or obfuscation case, it names no defined behavior
for empty/malformed arrivals, and its only "next step" examples are
progression-track with no reject/needs-more-info branch. A companion
`evaluating-skill-quality` pass rated it well-formed but not mature: two
occurrences of a bare MCP tool name (`search_issues`) break this repo's own
fully-qualified-naming convention followed by sibling skills. Refs #128.

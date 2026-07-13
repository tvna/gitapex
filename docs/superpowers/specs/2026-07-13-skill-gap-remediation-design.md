# Skill gap remediation via parallel evaluating-skill-quality review

## Problem

The repository has 11 skills under `skills/`. The `evaluating-skill-quality`
skill already defines a rigorous review procedure (deterministic shape check
+ nine-dimension probabilistic rubric + mechanism-fit + portability-level
checks) but it has only ever been applied ad hoc (e.g. its own
self-review). We want to apply it systematically across every skill in the
repo, then close the gaps it finds.

## Goals

- Review all 11 skills in `skills/` against `evaluating-skill-quality`.
- Delegate the analysis step to independent subagents running on the
  `fable` model, one per skill, in parallel.
- Delegate implementation of the fixes to Sonnet (the main thread), with an
  auto-fix / confirm-first split by severity.

## Non-goals

- Building a new eval harness or linter beyond what
  `evaluating-skill-quality` already specifies (explicitly out of scope per
  that skill's own Scope section).
- Changing the `evaluating-skill-quality` skill's rubric or shape checker
  itself, unless a finding specifically targets it as a review subject.

## Architecture

### 1. Parallel analysis (Fable x11)

For each of the 11 skill directories, spawn one `Agent` call with
`subagent_type: "general-purpose"` and `model: "fable"`. Each call runs
independently and in parallel (single message, 11 tool-call blocks).

Each agent's prompt must:

- Name the exact target skill directory (e.g. `skills/issue-to-branch/`).
- Instruct the agent to invoke the `evaluating-skill-quality` skill via the
  `Skill` tool and follow its Procedure section (steps 1-6) against the
  target, from the repo root.
- Require the agent to run the bundled shape checker
  (`python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py
  <skill-dir>`) itself rather than asking a further subagent to do so.
- Require a structured findings list as output (not prose-only), each
  finding carrying:
  - `severity`: `minor` or `major` (definition below, included verbatim in
    the prompt so all 11 agents classify consistently)
  - `dimension`: which rubric dimension (1-9), "shape", "mechanism-fit", or
    "portability"
  - `evidence`: a direct quote or line reference from the target skill
  - `file:line`: precise location
  - `recommendation`: what should change
- Cap the response length so aggregation stays cheap (findings list only,
  no restating the full rubric).

### Severity definition (given verbatim to every Fable agent)

- **major**: a whole-artifact mechanism-fit finding (skill should have been
  a hook/subagent/CLAUDE.md instead), a missing hook/permission backing for
  a stated safety-critical prohibition, a shape-checker FAIL, or a scope
  violation (skill doing more than its stated Scope section allows).
- **minor**: any other rubric-dimension finding (ambiguous wording, missing
  evidence citation in the skill's own docs, a broken cross-link, a
  step-level bundled-script delegation suggestion, formatting nits).

### 2. Aggregation (Sonnet, main thread)

Collect all 11 reports. Sanity-check for internal contradictions (e.g. two
agents disagreeing about the same skill's mechanism fit is not expected
since each covers a distinct skill, but a finding that misquotes the
target must be caught before acting on it — re-check the quote against the
actual file before trusting it).

### 3. Implementation (Sonnet, main thread)

- **minor** findings: fix directly in the working tree, no per-finding
  confirmation. Batch by skill.
- **major** findings: present each one to the user (what the finding is,
  why it's major, the proposed fix) and wait for explicit go-ahead before
  editing. Do not batch major findings across skills into one blanket
  approval — list them individually so the user can approve/reject each.

### 4. Verification

- After editing a skill whose shape changed, re-run
  `check_skill_shape.py` against it and confirm PASS.
- For rubric-dimension fixes (prose changes), no script exists to verify;
  state explicitly that this is a judgment call, not a re-run of the full
  nine-dimension review (per CLAUDE.md's ban on treating indirect signals
  as proof, note this limitation rather than silently asserting the fix is
  "verified").

## Error handling

- If a Fable agent's report cites a quote that does not appear in the
  target file, discard that specific finding and note the discrepancy
  rather than acting on it.
- If a target skill has no `references/` directory or no bundled script,
  the agent should say so explicitly rather than skipping the section.

## Testing / verification plan

- Shape checker re-run per touched skill (deterministic, scriptable).
- No new automated test suite is warranted — this is a documentation/prose
  remediation pass, not new runtime behavior.

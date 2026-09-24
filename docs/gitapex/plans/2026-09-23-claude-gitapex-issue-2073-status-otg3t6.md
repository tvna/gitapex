# Branch Plan: AgentMetadata sidecar schema + drift gate

Issue: https://github.com/tvna/gitapex/issues/2073

Parent: https://github.com/tvna/gitapex/issues/307 (Axis B, W1b).

Branch: `claude/gitapex-issue-2073-status-otg3t6`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #2073's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-23T13:41:11Z)"),
  written by this same session after a second re-verification pass
  (https://github.com/tvna/gitapex/issues/2073#issuecomment-5795918937).
  `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reported "PASS: re-verification marker found" against that body.
- Semantic approval: explicit confirmation from the active human operator
  in the current interactive session, given against this exact five-item
  Branch Plan (design-doc cherry-pick, schema, scanner + tests, ssot.json
  registration in `runtime-compatibility`, two doc edits; sequential
  execution, no multi-agent Workflow). No issue comment carries the
  approval; the in-session confirmation is the signal this gate ran on.

## Threat-model triage

Issue #2073's body and its two comments were read as change
descriptions. Extracted facts: the three schema additions
(`AgentMetadata` kind, `tools.shellDenylist`,
`lifecycle.exitConditions[]` with `onUnsupported: fail-closed` only), the
constraints (no existing sidecar or agent file touched), and the
non-goals (no adapter, no real `agents/metadata/*.gitapex.yaml` file).
The example YAML's `command` string is sample data for the schema, never
a command this plan runs. Nothing was flagged.

## Task Decomposition

One task, one wave -- every ACM row lands in the same small set of new
files (schema, scanner, tests), so splitting them would only create
file-ownership edges between the pieces.

- **File-ownership map.** The single task owns:
  `.gitapex/agent-metadata.schema.json` (new),
  `.github/scripts/gitapex_scan_agent_metadata_schema.py` (new),
  `tests/test_gitapex_scan_agent_metadata_schema.py` (new),
  `.gitapex/ssot.json` (one new `gates[]` entry, one cluster description
  widened), `docs/agent-product-scope.md` (Axis B cross-reference),
  `docs/repository-layout.md` (`agents/` line).
- **Interface-dependency map.** None outside this one task.
- **Wave assignment.** Wave 1: the single task alone, executed in the
  main thread (sequential fallback; the operator did not opt into a
  multi-agent Workflow run).

Irreversibility classification: **not irreversible.** New files plus
additive edits to tracked files; `git revert` restores the prior tree.

`SKILL.md` classification: **no `SKILL.md` is created or edited.** The
new `.github/scripts/gitapex_scan_*.py` file is a deterministic gate, so
the PR body discloses an `evaluating-deterministic-gate-quality` review.

## Task 1: AgentMetadata schema, scanner, registration, docs

Source ACM rows: issue #2073 rows 1-5 (re-verified 2026-09-23).

> Planned ops (issue #2073 row 1, verbatim): "New
> `.gitapex/agent-metadata.schema.json` (JSON Schema, draft 2020-12) +
> new `.github/scripts/gitapex_scan_agent_metadata_schema.py` validator
> (using the shared `.github/scripts/_gitapex_schema_validation.py`
> helper), registered in `.gitapex/ssot.json` as gate
> `agent-metadata-schema-drift` (cluster `runtime-compatibility`) --
> mirroring `gitapex_scan_skill_metadata_schema.py`'s YAML-sidecar pattern
> (cross-file checks: `metadata.name` equals the file's `<name>` stem, and
> `agents/<name>.md` exists) with a repo-wide, non-skill-owned schema
> placement like `gitapex_scan_ssot_schema.py`"
>
> Planned ops (rows 2-3, verbatim): "Schema + scanner extension (same new
> files as row 1)"
>
> Planned ops (row 4, verbatim): "No file edits outside this feature's own
> new files and fixtures"
>
> Planned ops (row 5, verbatim): "New doc sections in the two files named;
> design doc cherry-picked from `fec9d6d`"

Proof method: Red-Green -- fixture tests written first (accept a
well-formed sidecar; reject unknown keys, a wrong `kind`, an empty
`shellDenylist` item, a non-`fail-closed` `onUnsupported`, a name/stem
mismatch, a missing `agents/<name>.md`), then the real-tree scan (vacuous
today), then the full suite plus `gitapex_gate_local_preflight.py`.

## Verification

- `uv run --frozen python3 -m pytest --no-cov -q`
- `uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py`
- `uv run --frozen python3 .github/scripts/gitapex_scan_agent_metadata_schema.py`
- `git diff --stat origin/main -- 'skills/**/metadata/gitapex.yaml' agents/`
  is empty (row 4).

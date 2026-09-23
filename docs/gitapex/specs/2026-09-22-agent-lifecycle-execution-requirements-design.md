# Design: agent-level execution requirements (subagent sidecar + shell denylist + lifecycle exit conditions)

Parent tracking issue: https://github.com/tvna/gitapex/issues/307 (Axis B, Enforcement-adapter target set)
First slice precedent: https://github.com/tvna/gitapex/issues/349 (`spec.executionRequirements.tools`, merged via PR #351)
Motivating problem: https://github.com/tvna/gitapex/issues/1996 (`.claude/agents/branch-plan-task.md` YAML-truncation removal and hook migration)
Implementation: https://github.com/tvna/gitapex/issues/2073

> **Status (2026-09-23).** Issue #1996 has since merged a direct,
> Claude-Code-specific fix without waiting on this schema:
> `.claude/agents/` no longer exists, `agents/branch-plan-task.md`'s
> frontmatter carries only `disallowedTools: mcp__github`, and both hooks
> below now live in `hooks/hooks.json` -- a `PreToolUse` Bash hook calling
> `skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh`, and a
> `SubagentStop` hook (matcher `^(.*:)?branch-plan-task$`) calling
> `check_task_full_verification.sh`. Those hooks are hand-written; they do
> not read an `AgentMetadata` sidecar. The Problem section below is kept
> as written at design time. Issue #2073 implemented this schema; where
> this document and that implementation differ, the implementation notes
> inline below say so.

## Problem

At design time, issue #1996 needed to relocate two Claude-Code-specific
hooks then embedded in `.claude/agents/branch-plan-task.md`'s own
frontmatter:

1. A `PreToolUse` Bash-command classifier that denies `git push`, the `gh`
   CLI, and package-install commands (design doc Decision 17).
2. A `SubagentStop` gate that denies the subagent permission to stop until
   the full repository verification suite passes (design doc Decision 20,
   issue #1476).

Mapping this need onto #307's existing `spec.executionRequirements`
schema (issue #349, `tools.{read,write,shell}`) surfaces two structural
gaps that #349 did not anticipate, because #349 scoped itself to a single
skill's own main-thread procedure only:

- **No place to declare a dispatched subagent's own, separate execution
  requirements.** `metadata/gitapex.yaml` today describes what a
  *skill's own procedure* needs. It has no concept of "this skill also
  dispatches subagent type X, and X has its own, distinct requirement
  profile" -- and a subagent type is not always owned 1:1 by the skill
  that happens to dispatch it (`agents/review-persona.md` has multiple
  documented call sites across more than one skill), so nesting the
  declaration inside whichever skill dispatches it risks duplicate,
  drifting declarations for the same subagent type.
- **No category for a lifecycle/exit-condition requirement.** Decision
  17's Bash exclusion is a *deny*-shaped tool requirement; today's
  `tools.shell` is an allow-list of capability tags, a different
  semantic shape. Decision 20's "must pass verification before stopping"
  requirement is not a tool/filesystem/network/mcp/credentials/context
  requirement at all -- it is a workflow exit condition, a category
  #307's own Workstream W1 sub-categories never enumerated.

This document scopes a schema-only fix for both gaps, following #349's
own precedent of landing top-level shape first and deferring adapter
implementation and cross-runtime mapping to sibling child issues.

## Proposed solution

### 1. A new sidecar kind for subagent/agent-type definitions

New file convention: `agents/metadata/<name>.gitapex.yaml` -- one shared
`agents/metadata/` directory holding one file per agent-type name (no
restructuring of the existing flat `agents/<name>.md` files into
per-agent directories). Uses the same `apiVersion: gitapex.io/v1alpha1`
envelope as `SkillMetadata`, with a distinct `kind: AgentMetadata` so
tooling can tell agent sidecars and skill sidecars apart.

```yaml
apiVersion: gitapex.io/v1alpha1
kind: AgentMetadata
metadata:
  name: branch-plan-task
spec:
  executionRequirements:
    tools:
      read: [files]
      write: [files]
      shellDenylist: [git-push, gh-cli, package-install]
    lifecycle:
      exitConditions:
        - id: full-verification-suite
          command: "uv run --frozen python3 -m pytest --no-cov -q && uv run --frozen python3 .github/scripts/gitapex_gate_local_preflight.py"
          required: true
          onUnsupported: fail-closed
```

The `command` above is illustrative; the live verification command is
whatever `agents/branch-plan-task.md` states today (it has since gained
`--ignore` flags). The schema treats `command` as data run from the
repository root and never runs it.

The subagent type owns its own requirement declaration, independent of
which skill(s) dispatch it -- closing the `review-persona`-shaped
multi-caller drift risk a skill-nested `subagents:` block would have
carried.

### 2. `tools.shellDenylist`

A new key, sibling to the existing `tools.{read,write,shell}` allow-lists
(list of free-form, non-empty scalar capability tags, reusing the exact
mechanism issue #349 established). Additive only: no existing sidecar's
`tools.shell` allow-list changes shape or meaning. This preserves #307's
own constraint ("Preserve the existing `gitapex.io/v1alpha1`
`SkillMetadata` envelope unless a schema-version decision explicitly
changes it") by not overloading `tools.shell` with mixed allow/deny
semantics.

Tags have no fixed vocabulary yet, so an adapter defines how a tag such
as `gh-cli` maps to its runtime's command patterns until a tag registry
exists. The schema does not reject a tag listed in both `shell` and
`shellDenylist`; when that happens, deny takes precedence.

### 3. `lifecycle.exitConditions[]`

A new `executionRequirements` category alongside `tools`, with
`filesystem`/`mcp`/`credentials`/`context` still future. `SkillMetadata`
already has `packages` and `network`; `AgentMetadata` deliberately leaves
both out for now. The name `lifecycle` here is distinct from
`SkillMetadata`'s own `spec.lifecycle` (experimental/stable/deprecated
status): this one sits under `spec.executionRequirements` and holds only
exit conditions. Each entry:

- `id` (kebab-case string, required): stable identifier, unique within
  one sidecar.
- `command` (string, required): the check to run from the repository
  root.
- `required` (boolean, required): whether a failing result blocks the
  agent from stopping (`true`) or is advisory (`false`).
- `onUnsupported` (enum, required, `fail-closed` only in this slice): what
  an adapter must do when it cannot enforce this condition on its target
  runtime. Restricting this slice to `fail-closed` only operationalizes
  #307's own Layer 3 invariant directly: "An adapter must fail closed
  when it cannot enforce a required property. It must not silently
  downgrade a hard requirement to prompt guidance." `onUnsupported`
  applies whether or not `required` is `true`: it covers a runtime that
  cannot run the check at all, while `required` covers what a failing
  result means on a runtime that can. Under this rule, the prompt-only
  fallback `agents/branch-plan-task.md` still describes for runtimes
  without an equivalent hook (OpenCode, for example), and its skip when
  run outside a gitapex checkout, would not be compliant adapter output
  once an adapter for this schema ships -- named here as a consequence
  this schema surfaces, not something this schema-only issue fixes
  itself.

## Non-goals (deferred to sibling child issues, per #349's own precedent)

- Any runtime adapter implementation (Claude Code included) that
  actually consumes `agents/metadata/<name>.gitapex.yaml` and produces
  enforcement. A hand-written Claude Code equivalent now ships in
  `hooks/hooks.json` (issue #1996); it does not read these sidecars.
  Building an adapter that generates such hooks from a sidecar is still
  deferred.
- `filesystem`, `network`, `mcp`, `credentials`, `browser`,
  `externalServices`, `context` categories for agent sidecars (mirrors
  #349's own identical deferral for skill sidecars).
- Migrating any existing agent definition (`branch-plan-task`,
  `review-persona`) to actually declare an `agents/metadata/*.gitapex.yaml`
  file.
- Deciding whether issue #1996's own implementation waits for this schema
  to ship -- since resolved: #1996 proceeded independently (see Status
  above).
- The validator code itself -- this document fixes the schema's shape.
  Issue #2073 shipped the schema as `.gitapex/agent-metadata.schema.json`
  and its validator as `.github/scripts/gitapex_scan_agent_metadata_schema.py`
  (gate `agent-metadata-schema-drift`), not as an extension of
  `gitapex_check_skill_shape.py`.
- Whether runtimes load `agents/metadata/*.gitapex.yaml` as agent
  definitions was not verified against each runtime's documentation;
  Claude Code agent definitions are Markdown files, but this is an
  unverified assumption for other runtimes.

## Security invariants alignment (cross-check against #307's own list)

- Invariant 1 ("Declaration is not enforcement"): unchanged -- this
  schema slice adds declaration only, no adapter.
- Invariant 4 ("Unknown sidecar fields and unsupported capabilities fail
  closed"): the new `AgentMetadata` kind is stricter than `SkillMetadata`
  -- `additionalProperties: false` at every level, including `spec`
  itself, which `SkillMetadata` leaves open.
- Layer 3's "must fail closed, never silently downgrade" invariant: now
  directly encoded as `onUnsupported: fail-closed` being the only value
  this slice accepts, rather than left as prose an adapter might not
  honor.

## Acceptance Criteria Map

As drafted at design time. Issue #2073's re-verified map supersedes the
Planned-ops and Residual-risk cells: the validator is the standalone
scanner named under Non-goals (JSON Schema plus cross-file checks: name
matches file stem, `agents/<name>.md` exists, exit-condition ids are
unique, sidecar filename/location checks, discovery floor); `spec`
accepts only `executionRequirements` (no `portability`); and the design
is documented in `docs/agent-product-scope.md` (Axis B) and
`docs/repository-layout.md`, not in `SKILL.md`/`rubric.md` sections.

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `agents/metadata/<name>.gitapex.yaml` parses as a well-formed `AgentMetadata` envelope | New sidecar kind, distinct from `SkillMetadata`, sharing the `apiVersion`/`metadata.name` shape | New parser path (mirrors `check_skill_shape.py`'s existing `SkillMetadata` parsing) | New passing/failing test fixtures | Whether `AgentMetadata` should share more of `SkillMetadata`'s existing fields (e.g. `portability`) is not resolved here -- left to the child issue |
| `tools.shellDenylist` is accepted as a list of non-empty scalar strings, additive to existing `tools` keys | Sibling key to `read`/`write`/`shell`, same list-of-scalars mechanism | Parser + shape-checker extension | New fixtures; existing 18+ skill sidecars unchanged (`git diff --stat` scoped to `skills/**/metadata/gitapex.yaml` empty) | None identified |
| `lifecycle.exitConditions[]` is accepted with `id`/`command`/`required`/`onUnsupported` fields, `onUnsupported` restricted to `fail-closed` | New top-level category under `executionRequirements` | Parser + shape-checker extension | New fixtures, including a rejection fixture for any `onUnsupported` value other than `fail-closed` | Later slices may need `warn`/other values once a real adapter exists; deliberately not offered yet |
| Zero behavior change for existing skills and agents | No existing `metadata/gitapex.yaml` or agent `.md` file is touched by this slice | No file edits outside this feature's own fixtures | Full test suite green | None identified |
| Design documented for later workstreams | This document plus short `SKILL.md`/`rubric.md` sections in the owning child issue | Child issue's own implementation PR | Doc review against this design and against #349's own doc structure | None identified |

## Relationship to issue #1996

This design generalizes the *lesson* #1996 surfaced; it did not resolve
#1996 itself. #1996 went ahead with a direct, Claude-Code-specific fix
(hand-written hooks in `hooks/hooks.json`) without waiting on this
schema. A Claude Code adapter that would generate those hooks from an
`AgentMetadata` sidecar remains out of this document's scope.

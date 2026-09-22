# Design: agent-level execution requirements (subagent sidecar + shell denylist + lifecycle exit conditions)

Parent tracking issue: https://github.com/tvna/gitapex/issues/307 (Axis B, Enforcement-adapter target set)
First slice precedent: https://github.com/tvna/gitapex/issues/349 (`spec.executionRequirements.tools`, merged via PR #351)
Motivating problem: https://github.com/tvna/gitapex/issues/1996 (`.claude/agents/branch-plan-task.md` YAML-truncation removal, hook migration undecided)

## Problem

Issue #1996 needs to relocate two Claude-Code-specific hooks currently
embedded in `.claude/agents/branch-plan-task.md`'s own frontmatter:

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

### 3. `lifecycle.exitConditions[]`

A new top-level `executionRequirements` category, alongside (future)
`tools`/`filesystem`/`network`/`mcp`/`credentials`/`context`. Each entry:

- `id` (string, required): stable identifier for the condition.
- `command` (string, required): the check to run.
- `required` (boolean, required): whether this condition is a hard gate.
- `onUnsupported` (enum, required, `fail-closed` only in this slice): what
  an adapter must do when it cannot enforce this condition on its target
  runtime. Restricting this slice to `fail-closed` only operationalizes
  #307's own Layer 3 invariant directly: "An adapter must fail closed
  when it cannot enforce a required property. It must not silently
  downgrade a hard requirement to prompt guidance." Under this rule, the
  *current* plugin-distributed variant's prompt-only fallback for
  Decision 17/20 would not be a compliant adapter output once an adapter
  for this schema ships -- named here as a consequence this schema
  surfaces, not something this schema-only issue fixes itself.

## Non-goals (deferred to sibling child issues, per #349's own precedent)

- Any runtime adapter implementation (Claude Code included) that
  actually consumes `agents/metadata/<name>.gitapex.yaml` and produces
  enforcement. A live Claude Code adapter candidate (`hooks/hooks.json`
  entries scoped via the documented `agent_type` hook-payload field and
  the `SubagentStop` event's `agent_type` matcher) was researched against
  Claude Code's own official documentation during this design's own
  dialogue, but building it is separate implementation work.
- `filesystem`, `network`, `mcp`, `credentials`, `browser`,
  `externalServices`, `context` categories for agent sidecars (mirrors
  #349's own identical deferral for skill sidecars).
- Migrating any existing agent definition (`branch-plan-task`,
  `review-persona`) to actually declare an `agents/metadata/*.gitapex.yaml`
  file.
- Deciding whether issue #1996's own implementation waits for this schema
  to ship or proceeds independently with a direct Claude-Code-specific
  fix -- left an open question for the repository owner, tracked
  separately from this design.
- The shape checker / parser code change itself (`gitapex_check_skill_shape.py`
  and friends) -- this document fixes the schema's shape; wiring a
  validator is the child issue's own implementation task, per #349's
  precedent of shipping schema and validator together in one child PR.

## Security invariants alignment (cross-check against #307's own list)

- Invariant 1 ("Declaration is not enforcement"): unchanged -- this
  schema slice adds declaration only, no adapter.
- Invariant 4 ("Unknown sidecar fields and unsupported capabilities fail
  closed"): the new `AgentMetadata` kind and its `executionRequirements`
  sub-keys follow the same fail-closed-on-unknown-key rule #349
  established for `SkillMetadata`.
- Layer 3's "must fail closed, never silently downgrade" invariant: now
  directly encoded as `onUnsupported: fail-closed` being the only value
  this slice accepts, rather than left as prose an adapter might not
  honor.

## Acceptance Criteria Map

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| `agents/metadata/<name>.gitapex.yaml` parses as a well-formed `AgentMetadata` envelope | New sidecar kind, distinct from `SkillMetadata`, sharing the `apiVersion`/`metadata.name` shape | New parser path (mirrors `check_skill_shape.py`'s existing `SkillMetadata` parsing) | New passing/failing test fixtures | Whether `AgentMetadata` should share more of `SkillMetadata`'s existing fields (e.g. `portability`) is not resolved here -- left to the child issue |
| `tools.shellDenylist` is accepted as a list of non-empty scalar strings, additive to existing `tools` keys | Sibling key to `read`/`write`/`shell`, same list-of-scalars mechanism | Parser + shape-checker extension | New fixtures; existing 18+ skill sidecars unchanged (`git diff --stat` scoped to `skills/**/metadata/gitapex.yaml` empty) | None identified |
| `lifecycle.exitConditions[]` is accepted with `id`/`command`/`required`/`onUnsupported` fields, `onUnsupported` restricted to `fail-closed` | New top-level category under `executionRequirements` | Parser + shape-checker extension | New fixtures, including a rejection fixture for any `onUnsupported` value other than `fail-closed` | Later slices may need `warn`/other values once a real adapter exists; deliberately not offered yet |
| Zero behavior change for existing skills and agents | No existing `metadata/gitapex.yaml` or agent `.md` file is touched by this slice | No file edits outside this feature's own fixtures | Full test suite green | None identified |
| Design documented for later workstreams | This document plus short `SKILL.md`/`rubric.md` sections in the owning child issue | Child issue's own implementation PR | Doc review against this design and against #349's own doc structure | None identified |

## Relationship to issue #1996

This design generalizes the *lesson* #1996 surfaced; it does not resolve
#1996 itself. The repository owner has not yet decided whether #1996's
own file-removal-and-hook-migration proceeds independently (a direct,
Claude-Code-specific fix) or waits on this schema. That sequencing
decision, and the separate Claude Code adapter implementation, are both
explicitly out of this document's own scope.

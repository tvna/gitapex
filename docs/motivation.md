# Motivation: the Design-by-Contract issue/PR flow problem

This document preserves, as reproducible text-sourced diagrams, the two
sequence diagrams from a private analysis artifact (`dbchandoff.html`, not
published) that motivated turning gitapex into a distributable skills
collection. The diagrams are Mermaid transcriptions of the original SVGs,
translated to ASCII-only English so the source content stays reviewable
and portable in this repository.

## The problem (as-is)

Today, a contributor's instruction flows through Issue authoring, AI
review sign-off, implementation, and PR creation with no single artifact
that ties an Issue's Acceptance Criteria to a PR's evidence -- the review,
sign-off, and criteria-freeze steps are ad hoc, performed by whichever AI
happens to be in the loop at the time.

```mermaid
sequenceDiagram
    participant Contributor as Contributor
    participant Author as AI author/implementer
    participant Reviewer as AI reviewer
    participant Hooks as hooks (PreToolUse, client)
    participant GitHub as GitHub (Issue/PR)
    participant CI as CI (verify-pr.yml / scan_*)

    Contributor->>Author: instruction + starting context
    Note over Author: blindspot pass / interview (surface unknowns)
    Author->>Hooks: mcp__github__issue_write (hermetic criteria)
    Note over Hooks: PreToolUse gate: preflight_non_ascii, title_policy, issue_classification_labels, issue_ci_staleness (block on failure)
    Hooks->>GitHub: pass -> Issue created
    Author->>Reviewer: request review (criteria validity, unknowns coverage)
    Reviewer-->>GitHub: sign-off (criteria finalized)
    Note over Contributor,CI: contract:frozen -- Acceptance Criteria hashed and frozen (review sign-off = freeze anchor)
    Reviewer->>Contributor: present frozen contract (for inspection)
    Contributor-->>Author: approved -> start implementation
    Note over Author: implementation + deviation log in implementation-notes
    Author->>CI: run hermetic verification locally (pytest / scan_*)
    CI-->>Author: result (CI does not execute body commands, author runs locally)
    Note over Author: diff correctness review: requesting-code-review [superpowers, Task subagent] -> findings -> fix [validate -> fix]. Just before PR creation, or just before merge
    Author->>Hooks: mcp__github__create_pull_request (each criterion -> command:result / invariant declaration)
    Note over Hooks: PreToolUse gate: preflight_pr_template_shape [client mirror of body_policy], required_sections, title, retro_issue_link, branch_base, non-ascii, secrets, plus [new] contract-join preflight
    Hooks->>GitHub: pass -> PR created
    Note over GitHub: PostToolUse: post_pr_create_ci_monitor auto-subscribes to CI and review
    GitHub->>CI: verify-pr.yml (body_policy, scan_* + registry drift) -- doubled server-side
    CI-->>GitHub: green
    GitHub->>Reviewer: deterministic green (hooks + CI) -> trigger focused semantic review
    Note over Reviewer: criteria-evidence truth matching: review-verdict [clairvoyance, main thread, no subagent] (evidence exists, criteria satisfied)
    Reviewer->>Contributor: review result + quiz report
    Contributor-->>GitHub: quiz passed -> approved
    Note over Contributor,CI: mergeable_state = clean -- just before mergeable (merge itself out of scope)
```

## The fix (to-be)

Once a dedicated skill lane (`issue-to-branch`, vendored from the
`clairvoyance` plugin) drives the pre-implementation steps in the main
thread -- no subagent -- and Section 6 (handoff / quiz / verdict) is
routed explicitly to the specific `clairvoyance` skill responsible for
each step, the same flow produces a machine-readable Acceptance Criteria
Map up front, and the deterministic gates (hooks, CI) pass on the first
attempt because the skill authors gate-map-compliant artifacts instead of
ad hoc ones.

Per your request, the single combined "clairvoyance" lane from the source
diagram is split here into the three actual skills it represents:
`review-verdict` (criteria review, invoked twice), `clairvoyance` (the
base handoff skill that presents the frozen contract), and
`decision-coaching` (the quiz). The source diagram expressed these
handoffs as "Route to X" labels on one shared lane; this version draws
them as explicit arrows between the named skills, without changing the
underlying flow.

```mermaid
sequenceDiagram
    participant Contributor as Contributor
    participant Author as AI author/implementer
    participant IssueToBranch as skill: issue-to-branch
    participant ReviewVerdict as skill: review-verdict
    participant Clairvoyance as skill: clairvoyance
    participant DecisionCoaching as skill: decision-coaching
    participant Hooks as hooks (PreToolUse, client)
    participant GitHub as GitHub (Issue/PR)
    participant CI as CI (verify-pr.yml / scan_*)

    Contributor->>Author: instruction + starting context
    Author->>IssueToBranch: skill fires (issue/PR contract, matches acceptance-criteria description)
    Note over IssueToBranch: runs in main thread: blindspot pass / interview / hermetic-criteria authoring (visible, no subagent)
    IssueToBranch-->>Author: output contract: Acceptance Criteria Map (criterion -> interpretation -> planned ops -> proof method -> residual risk) + hermetic criteria
    Author->>Hooks: mcp__github__issue_write (hermetic criteria)
    Note over Hooks: PreToolUse gate -> passes on first try (gate-map compliant)
    Hooks->>GitHub: pass -> Issue created
    IssueToBranch->>ReviewVerdict: route to review-verdict (criteria review)
    ReviewVerdict-->>GitHub: sign-off (criteria finalized)
    Note over Contributor,CI: contract:frozen -- Acceptance Criteria hashed and frozen (sign-off = freeze anchor)
    ReviewVerdict->>Clairvoyance: hand off frozen contract for owner decision
    Clairvoyance->>Contributor: present frozen contract, decision-ready
    Contributor-->>Author: approved -> start implementation
    Note over Author: implementation + deviation log in implementation-notes
    Author->>CI: run hermetic verification locally (pytest / scan_*)
    CI-->>Author: result (CI does not execute body commands, author runs locally)
    Note over Author: diff correctness review: requesting-code-review [superpowers, Task subagent] -> findings -> fix [validate -> fix]. Just before PR creation, or just before merge
    Author->>Hooks: mcp__github__create_pull_request (each criterion -> command:result / invariant declaration)
    Note over Hooks: PreToolUse: pr_template_shape mirror + contract-join preflight -> passes on first try
    Hooks->>GitHub: pass -> PR created
    Note over GitHub: PostToolUse: post_pr_create_ci_monitor auto-subscribes
    GitHub->>CI: verify-pr.yml (body_policy, scan_* + registry drift) -- doubled server-side
    CI-->>GitHub: green
    GitHub->>ReviewVerdict: deterministic green (hooks + CI) -> route to review-verdict
    Note over ReviewVerdict: criteria-evidence truth matching: review-verdict [main thread, no subagent]
    ReviewVerdict->>DecisionCoaching: route quiz to decision-coaching
    DecisionCoaching->>Contributor: review result + quiz
    Contributor-->>GitHub: quiz passed -> approved
    Note over Contributor,CI: mergeable_state = clean -- just before mergeable (merge itself out of scope)
```

## Reading

The diff between the two diagrams is exactly three changes:

1. A **skill lane** (`issue-to-branch`) now drives the pre-implementation
   steps (blindspot pass, interview, hermetic-criteria authoring) in the
   main thread -- visible and steerable, no subagent, so no understanding
   debt is added.
2. **Section 6** (handoff / quiz / verdict) is routed explicitly to the
   specific `clairvoyance` skill responsible for each step
   (`review-verdict`, `clairvoyance`, `decision-coaching`) instead of
   being reinvented ad hoc by whichever reviewer is in the loop.
3. Because the skill authors artifacts that already conform to the gate
   map, **hooks and CI pass on the first attempt** instead of triggering a
   fix loop.

The enforcement layer itself (hooks / CI / criteria-freeze) is unchanged
between as-is and to-be -- only the authoring step changes.

## Relationship to the skills in this repository

`explaining-the-work` (added alongside this document) addresses an
adjacent thread from the same design session -- routing comment, commit,
and test explanation responsibility to the right artifact -- not the
contract-join gate shown above directly.

The to-be diagram's `issue-to-branch` skill lane and the contract-join
gate + criteria-freeze CI work it depends on are a separate, larger
initiative, tracked as a 1 tracking-issue + 5 children plan. See the "Open
items carried forward" section of
[`docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`](superpowers/specs/2026-07-12-skill-distribution-foundation-design.md).
This document exists so that initiative's motivation is preserved in-repo
rather than living only in a private, unpublished artifact.

# git-hosting-surface-audit skill for gitapex

Date: 2026-07-15

Refs #88. Consumes/cross-links #82 (gitapex CLI governance tracking
issue -- reopened and reframed since this doc was first written; the
approved read-only gh wrapper is now one of #82's listed, not-yet-filed
candidate child issues, not #82 itself) for every coverage gap below.

## Context

gitapex's defense skills today cover the output boundary
(`outward-artifact-preflight`) and single-item input triage
(`untrusted-input-triage`), but nothing audits the hosting-platform
*configuration surface* itself. The initial candidate name,
`github-surface-audit`, hardcoded a specific platform -- renamed to
`git-hosting-surface-audit` and redesigned for GitHub + GitLab, per
operator instruction.

**Owner-approved decision:** mirror `seeding-issue-pr-templates`'s exact
platform-handling shape rather than inventing a shared abstraction --
that skill is this repo's only precedent for two-platform support, and it
deliberately does *not* build one: it detects platform once (from `git
remote` + filesystem markers), then loads exactly one platform's
`references/*.md`, never both in the same run.

## Checklist items and actual tool coverage (verified, not assumed)

Checked directly against the GitHub MCP tools available in this session
(`ToolSearch` over branch-protection/webhook/permission-related keywords).
No GitLab MCP server exists in this environment at all, so the entire
GitLab column is a stated gap, not per-item guesswork.

| Checklist item | GitHub MCP coverage | GitLab MCP coverage |
|---|---|---|
| Branch protection rules | **Gap.** No `mcp__github__*` tool exposes branch-protection settings (confirmed: no `get_branch_protection`-shaped tool in this session's tool list). | **Gap.** No GitLab MCP server at all. |
| Required reviews/checks | **Gap.** Same as above -- branch protection's required-checks list is part of the same unexposed settings surface. | **Gap.** |
| Actions/CI permissions (e.g. "Allow all actions" vs restricted) | **Gap.** Repo Actions-permissions settings are not exposed by any tool found. | **Gap.** |
| Unpinned third-party actions/includes | **Covered.** `mcp__github__get_file_contents` can read `.github/workflows/*.yml` directly; grep for `uses: owner/repo@<non-40-char-ref>`. This is the same technique `.github/scripts/scan_toolchain_pin_drift.py` already applies to upstream-URL strings -- reuse the pattern, do not reinvent it. | **Gap** (would need to read `.gitlab-ci.yml` includes the same way once a GitLab MCP server or the wrapper exists). |
| Webhook inventory | **Gap.** No `list_repository_webhooks`-shaped tool found. | **Gap.** |
| Deploy-key inventory | **Gap.** No `list_deploy_keys`-shaped tool found. | **Gap.** |
| Token scopes (of the connected app/PAT itself) | **Gap.** `mcp__github__get_me` returns user profile, not the connected token's scope list. | **Gap.** |
| Secret-scanning status (repo feature enabled, alert count) | **Partial.** `mcp__github__run_secret_scanning` scans *given content* for secrets (useful as a defense-in-depth content check the audit can run itself on tracked files) but does not report whether the repo's native secret-scanning *feature* is toggled on -- that status is a separate gap. | **Gap.** |
| Collaborator/permission drift | **Covered.** `mcp__github__list_repository_collaborators` (with `affiliation` filter) returns exactly this. | **Gap.** |

Every row marked **Gap** is a stated consumer of the approved read-only
gh wrapper once it is filed as its own child issue under #82 and built --
not of #82 itself, which is the umbrella governance tracking issue and
has no single "landed" state of its own. This design does not pretend
those checks are solved today, per this repo's own "state the gap
explicitly" convention
(`establishing-ubiquitous-language`/`evaluating-skill-quality`).

## Scope of this design pass

Per the operator's chosen execution scope: this design doc plus
`docs/superpowers/plans/2026-07-15-git-hosting-surface-audit.md`. No
`skills/*/SKILL.md` file is authored in this pass.

## Non-goals

- Does not implement the approved read-only gh wrapper itself (a
  not-yet-filed candidate child issue under #82).
- Does not claim GitHub-side coverage is complete -- only 2 of 8
  checklist items have real tool coverage today; the rest run as a
  documented-gap report, not a false all-green audit, until that wrapper
  is filed and built.
- Does not add a GitLab MCP server or attempt to call GitLab's REST API
  directly from this skill (that would itself be exactly the kind of
  ungoverned CLI/API shortcut the gitapex CLI, tracked in #82, exists to
  replace with something approved).

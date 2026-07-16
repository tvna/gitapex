# GitHub hosting-surface checklist (GitHub runs only)

Read this ONLY when Step 1 detected GitHub. Do not open the GitLab
reference in the same run.

Coverage verified directly against the `mcp__github__*` tools available in
this session (via `ToolSearch` over branch-protection/webhook/permission
keywords), not assumed. Only 2 of 8 items below are actually Covered; 1 is
Partial; the rest are Gaps. Report every item at its stated level -- never
round a Gap up because a workaround seems achievable in the moment.

| # | Checklist item | Coverage | Method |
|---|---|---|---|
| 1 | Branch protection rules (including required reviews/checks -- the required-checks list is part of the same unexposed branch-protection settings surface, not a separately coverable item) | **Gap.** No `mcp__github__*` tool exposes branch-protection settings (no `get_branch_protection`-shaped tool in this session's tool list). | Cross-link #82. |
| 2 | Actions/CI permissions (e.g. "Allow all actions" vs restricted) | **Gap.** Repo Actions-permissions settings are not exposed by any tool found. | Cross-link #82. |
| 3 | Unpinned third-party actions/includes | **Covered.** Read `.github/workflows/*.yml` (via `mcp__github__get_file_contents`, or directly off disk when the repo is checked out locally) and run `scripts/scan_unpinned_actions.py <workflows_dir>`. Flags any `uses:` step pinned to a tag/branch instead of a full 40-character commit SHA. Reuses `.github/scripts/scan_toolchain_pin_drift.py`'s walk/report/exit-code shape -- do not write a second, divergent detector. | Run the script; report its exact findings, file:line included. |
| 4 | Webhook inventory | **Gap.** No `list_repository_webhooks`-shaped tool found. | Cross-link #82. |
| 5 | Deploy-key inventory | **Gap.** No `list_deploy_keys`-shaped tool found. | Cross-link #82. |
| 6 | Token scopes (of the connected app/PAT itself) | **Gap.** `mcp__github__get_me` returns user profile, not the connected token's scope list. | Cross-link #82. |
| 7 | Secret-scanning status (repo feature enabled, alert count) | **Partial.** `mcp__github__run_secret_scanning` scans *given content* for secrets -- useful as a defense-in-depth content check the audit can run itself on tracked files -- but does not report whether the repo's native secret-scanning *feature* is toggled on. State both halves explicitly: what the content scan found, and that feature-toggle status remains a Gap. | Run the content scan; report the feature-toggle status as a Gap, cross-linked to #82. |
| 8 | Collaborator/permission drift | **Covered.** `mcp__github__list_repository_collaborators` (with an `affiliation` filter) returns exactly this. | Call the tool; report its result. |

Every **Gap** row above is a stated consumer of the approved read-only gh
wrapper once it is filed as its own child issue under #82 and built -- not
of #82 itself, which is the umbrella governance tracking issue with no
single "landed" state of its own.

## Self-check

Run `python3 scripts/scan_unpinned_actions.py <workflows_dir>` for item 3
before reporting it -- never assert "no unpinned actions found" from
memory or a partial read.

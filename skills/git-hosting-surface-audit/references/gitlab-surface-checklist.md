# GitLab hosting-surface checklist (GitLab runs only)

Read this ONLY when Step 1 detected GitLab. Do not open the GitHub
reference in the same run.

No GitLab MCP server exists in this session at all, so every item below is
a stated Gap -- not per-item guesswork, and not "GitLab support is
unimplemented" left unsaid. Report each item individually rather than one
blanket "GitLab unsupported" line, so a future re-audit (once a GitLab MCP
server or the approved wrapper exists) can upgrade items one at a time
instead of re-deriving this table from scratch.

Items are numbered to mirror `references/github-surface-checklist.md`'s 8
items exactly (same item 1 folds required reviews/approval rules into
branch protection, for the same reason: it is part of the same
unexposed settings surface, not a separately coverable item) -- a repo
migrating between platforms should see the same checklist shape on both
sides, only the coverage level and API differ.

| # | Checklist item | Coverage | What would close the gap |
|---|---|---|---|
| 1 | Branch protection rules (including required reviews/approval rules) | **Gap.** No GitLab MCP server in this session. | A GitLab MCP server, or the approved wrapper, exposing protected-branch and approval-rules settings. |
| 2 | CI/CD permissions (e.g. protected-branch pipeline restrictions) | **Gap.** No GitLab MCP server in this session. | GitLab's CI/CD settings API. |
| 3 | Unpinned includes in `.gitlab-ci.yml` | **Gap.** `scripts/scan_unpinned_actions.py` in this skill scans GitHub Actions `uses:` syntax only; it does not parse `.gitlab-ci.yml` `include:` entries, which have a different shape (project/ref/file, not `owner/repo@ref`). Do not stretch the GitHub script over GitLab syntax it was not built for -- that would produce false negatives, not coverage. | A GitLab-specific `include:` pin-drift scanner, once a GitLab MCP server or the wrapper makes this checklist item worth building for. |
| 4 | Webhook inventory | **Gap.** No GitLab MCP server in this session. | GitLab's project-hooks API. |
| 5 | Deploy-key inventory | **Gap.** No GitLab MCP server in this session. | GitLab's deploy-keys API. |
| 6 | Token scopes (of the connected PAT/app itself) | **Gap.** No GitLab MCP server in this session. | GitLab's personal-access-token introspection API. |
| 7 | Secret-scanning status (feature enabled, alert count) | **Gap.** No GitLab MCP server in this session. | GitLab's secret-detection/vulnerability-report API. |
| 8 | Member/permission drift | **Gap.** No GitLab MCP server in this session. | GitLab's project-members API. |

Every row above is a stated consumer of the approved read-only gh wrapper
(gitapex CLI governance, #82) once GitLab support is filed as its own
child issue under #82 and built -- cross-link #82 in the report for each,
worded as "consumer of an unfiled candidate child issue," not "blocked on
#82 landing" (#82 is the umbrella tracking issue and has no single
"landed" state).

## Self-check

There is nothing to run here today -- every item is a Gap. The
self-check is procedural: confirm the report states all 8 as Gap,
individually, with #82 cross-linked on each, rather than one aggregate
"GitLab: unsupported" line.

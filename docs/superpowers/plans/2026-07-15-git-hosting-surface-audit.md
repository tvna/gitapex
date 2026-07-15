# git-hosting-surface-audit Implementation Plan

**Goal:** Add a gitapex skill that audits a repository's hosting-platform
configuration surface (branch protection, reviews/checks, Actions
permissions and unpinned actions, webhook/deploy-key inventory, token
scopes, secret-scanning status) for GitHub and GitLab, reporting drift as
a decision-ready brief rather than silently assuming full coverage.

**This skill's issue:** #88. **Cross-linked:** #82 (gitapex CLI
governance tracking issue -- reopened and reframed since this plan was
first written; the approved read-only gh wrapper is now an unfiled
candidate child issue under #82, not #82 itself -- consumer of every
coverage gap below).

**Architecture:** One new skill directory
`skills/git-hosting-surface-audit/` holding a platform-general `SKILL.md`
plus `references/github-surface-checklist.md` and
`references/gitlab-surface-checklist.md`, mirroring
`seeding-issue-pr-templates`'s exact platform-detection and
never-load-both-references shape. Deferred to a future cycle (see Task 2
onward); this cycle only lands the design docs (Task 1).

## Global constraints

- Platform detection: **do not** reuse
  `seeding-issue-pr-templates/scripts/validate_templates.py`'s
  `detect_platform()` as-is -- confirmed by review, that function checks
  only for `.github/ISSUE_TEMPLATE` and `.gitlab/issue_templates`
  (template-directory presence) and never reads `git remote`, so it
  misclassifies (or outright stops on) any real GitHub/GitLab repo that
  simply has no issue templates configured -- exactly the repos a
  hosting-surface audit, which is not template-specific, must still be
  able to run against. Detect platform instead from `git remote get-url
  origin` (match host `github.com`/`gitlab.com`, including
  self-hosted/enterprise via a configurable host allowlist), falling back
  to generic `.github/` vs `.gitlab/` directory presence (not the
  `ISSUE_TEMPLATE`/`issue_templates` subdirectory specifically) only when
  the remote is unparseable or absent.
- Never load both platform references in the same run (identical rule to
  `seeding-issue-pr-templates`).
- Every checklist item's report line states its own coverage level
  (Covered / Partial / Gap, per the design doc's table) -- never a single
  aggregate "audit passed," since most items are gaps until the approved
  gh wrapper (a not-yet-filed candidate child issue under #82) is built.
- Read-only: this skill only reports; it does not itself change branch
  protection, revoke a webhook, or rotate a key -- those stay human
  decisions per CLAUDE.md section 4.

---

### Task 1: Issue and design docs (this cycle)

- [x] Confirm no duplicate issue existed (`search_issues` run 2026-07-15
      -- no match).
- [x] Open #88 (`feat(skills): add git-hosting-surface-audit skill`).
- [x] Verify actual MCP tool coverage per checklist item via `ToolSearch`
      rather than assuming (see design doc's table) -- found 2/8 items
      covered, 1 partial, 5 full gaps, all cross-linked to #82.
- [x] Commit this plan doc plus
      `docs/superpowers/specs/2026-07-15-git-hosting-surface-audit-design.md`,
      citing #88 and #82.

### Task 2: SKILL.md authoring (deferred -- future cycle)

- [ ] Write `skills/git-hosting-surface-audit/SKILL.md`: platform
      detection step per the corrected Global constraints above
      (`git remote` host match, generic directory-marker fallback --
      *not* `seeding-issue-pr-templates`'s template-specific
      `detect_platform()`), branch-to-one-reference rule, and a report
      template with an explicit per-item coverage column.
- [ ] Write `references/github-surface-checklist.md` and
      `references/gitlab-surface-checklist.md`, each opening with the
      same "read this ONLY when Step 1 detected X" guard used verbatim
      in `seeding-issue-pr-templates`'s reference pair.
- [ ] For the one item with existing precedent code
      (unpinned-actions detection), reuse
      `.github/scripts/scan_toolchain_pin_drift.py`'s pattern rather than
      writing a second, divergent implementation.

### Task 3: Eval coverage (deferred -- future cycle, after Task 2 lands)

- [ ] `evals/git-hosting-surface-audit/eval.yaml` + task fixtures for both
      platforms, including one guardrail case asserting the skill never
      reports a Gap item as passing.

### Task 4: Revisit once the approved gh wrapper lands (future, unscheduled)

- [ ] Re-open this skill's checklist-coverage table and upgrade each
      **Gap** row that the wrapper (once filed as its own child issue
      under #82 and built) now covers -- do not let the original gap
      list silently go stale once it exists.

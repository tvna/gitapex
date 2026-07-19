---
name: git-hosting-surface-audit
description: Use when auditing a GitHub or GitLab repository's hosting-platform configuration surface -- branch protection, required reviews/checks, Actions/CI permissions, unpinned third-party actions, webhook inventory, deploy-key inventory, token scopes, secret-scanning status. Detects platform from git remote (with a directory-marker fallback), loads exactly one platform's checklist reference, and reports each item's real tool coverage (Covered/Partial/Gap) instead of a false all-green summary. Gap items cross-link gitapex CLI governance issue #82.
---

# Git Hosting Surface Audit

Procedure and the coverage-honesty rule are portable to any GitHub/GitLab
repo. The Gap cross-link target (#82, this
repo's gitapex CLI governance tracking issue) and the unpinned-actions
script's borrowed pattern (`.github/scripts/scan_toolchain_pin_drift.py`)
are this repo's own -- substitute the calling repository's actual
governance issue and drift-scan precedent where they differ.

Audits a repository's hosting-platform *configuration* surface (not its
code) and reports what was actually checked versus what could not be
checked with tools available in this session. This is a read-only report:
it never changes branch protection, revokes a webhook, or rotates a key.

## Steps

1. **Detect platform and non-destruction gate.** Do NOT reuse
   `seeding-issue-pr-templates`'s `detect_platform()` as-is -- that
   function only checks for `.github/ISSUE_TEMPLATE` /
   `.gitlab/issue_templates` (template-directory presence), so it
   misclassifies any real GitHub/GitLab repo that simply has no issue
   templates configured. This audit is not template-specific and must
   still run against those repos. Detect instead:
   1. Read `git remote get-url origin`. Match the host against known
      GitHub hosts (`github.com`, plus any GitHub Enterprise host the
      operator names) and known GitLab hosts (`gitlab.com`, plus any
      self-hosted GitLab host the operator names) -- an explicit,
      operator-extendable allowlist, not a guess.
   2. If the remote is absent or its host matches neither list, fall back
      to generic directory-marker presence: `.github/` exists and
      `.gitlab/` does not -> GitHub; `.gitlab/` exists and `.github/` does
      not -> GitLab (the directory itself, not the
      `ISSUE_TEMPLATE`/`issue_templates` subdirectory specifically).
   3. If both markers are present, or neither the remote nor a directory
      marker resolves the platform, STOP and ask the operator rather than
      guessing.
2. **Load ONLY the detected platform's checklist reference.** If GitHub,
   read `references/github-surface-checklist.md`. If GitLab, read
   `references/gitlab-surface-checklist.md`. Never open both in the same
   run (identical rule to `seeding-issue-pr-templates`).
3. **Run each checklist item at its stated coverage level.** The loaded
   reference's table is the source of truth for what is Covered, Partial,
   or a Gap -- do not upgrade an item's coverage level based on what seems
   plausible to try in the moment. For a **Covered** item, call the named
   tool/script and report its actual result. For a **Partial** item, run
   what is available and state precisely what it does and does not verify.
   For a **Gap** item, do not attempt a workaround (an ungoverned direct
   API call, a scraped web page, a guess) -- report it as a Gap and cross-
   link gitapex CLI governance issue #82 (the approved read-only gh
   wrapper that would close this gap is an unfiled candidate child issue
   under #82, not #82 itself -- word the link that way, not as "blocked on
   #82 landing").
4. **Report per item, never as one aggregate verdict.** Every checklist
   item's line states its own coverage level. Do not summarize with a
   single "audit passed" or "N/M checks green" headline -- with 2 of 8
   GitHub items covered (0 of 8 for GitLab) today, an aggregate framing
   would misrepresent gaps as passes. See Output below for the report
   shape.

## Output

- **Facts:** detected platform, detection method used (remote host match
  or directory-marker fallback), repo identity.
- **Per-item results:** one line per checklist item --
  `<item> -- <Covered|Partial|Gap> -- <what was actually run> -- <finding, or "gap: see #82">`.
- **Gap summary:** count of Gap items out of total, each cross-linked to
  #82.
- **Next Move:** the concrete next action (e.g. fix a specific unpinned
  action, or file the read-only gh wrapper as a child issue under #82 to
  close a named Gap).

## Stop boundaries

- Never report an aggregate "audit passed," "all green," or a bare score
  with no per-item breakdown -- most items are gaps until the approved
  read-only gh wrapper (a not-yet-filed candidate child issue under #82)
  exists.
- Never claim a **Gap** item as **Covered** or **Partial** because a
  workaround seems achievable in the moment; that workaround is itself the
  kind of ungoverned shortcut gitapex CLI governance (#82) exists to
  replace with something approved.
- Never load both platform references in one run.
- Never take a write action (change branch protection, revoke a webhook,
  rotate a deploy key) -- this skill only reports; those stay human
  decisions per CLAUDE.md section 4.
- Never write a second, divergent unpinned-actions detector -- reuse
  `scripts/scan_unpinned_actions.py`, which reuses
  `.github/scripts/scan_toolchain_pin_drift.py`'s walk/report/exit-code
  shape.

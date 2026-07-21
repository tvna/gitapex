---
name: git-hosting-surface-audit
description: Use when auditing a GitHub or GitLab repository's hosting-platform configuration surface -- branch protection, required reviews/checks, Actions/CI permissions, unpinned third-party actions, webhook inventory, deploy-key inventory, token scopes, secret-scanning status. Detects platform from git remote (with a directory-marker fallback), loads exactly one platform's checklist reference, and reports each item's real tool coverage (Covered/Partial/Gap) instead of a false all-green summary. Gap items cross-link this repository's own tracking issue for approved-but-unbuilt tooling.
---

# Git Hosting Surface Audit

The procedure, the coverage-honesty rule, and both platform checklists
work identically no matter which GitHub/GitLab repo is being *audited*.
The one exception: the Gap cross-link target depends on where *this copy
of the skill's own files* live, never on which repository is under audit
-- gitapex's own copy always cross-links gitapex's own tracking issue,
even when auditing a target that has nothing to do with gitapex. If this
copy lives in gitapex itself, Step 2 below loads
`references/gitapex-cross-links.md` for gitapex's own target,
instruction-file citation, and script precedent. A copy vendored into a
different repository drops that file and instead uses that hosting
repository's own tracking issue and instruction file where they exist --
omitting the cross-link or citation where they don't, never fabricating
one. Nothing else in this skill depends on the file.

Audits a repository's hosting-platform *configuration* surface (not its
code) and reports what was actually checked versus what could not be
checked with tools available in this session. This is a read-only report:
it never changes branch protection, revokes a webhook, or rotates a key.

## Steps

1. **Detect platform and non-destruction gate.** Do NOT detect platform by
   issue-template-directory presence alone (`.github/ISSUE_TEMPLATE` /
   `.gitlab/issue_templates`) -- that misclassifies any real GitHub/GitLab
   repo that simply has no issue templates configured. This audit is not
   template-specific and must still run against those repos. Detect
   instead:
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
2. **Load the checklist reference, and the cross-link reference if this
   is gitapex's own copy.** Read ONLY the detected platform's checklist
   reference -- `references/github-surface-checklist.md` for GitHub,
   `references/gitlab-surface-checklist.md` for GitLab -- and never open
   both in the same run.
   If this copy of the skill's own files lives in the gitapex repository,
   also read `references/gitapex-cross-links.md`: Step 3's cross-link
   target comes from it, and skipping this read is what makes a Gap
   report fall back to a generic, issue-number-free line.
3. **Run each checklist item at its stated coverage level.** The loaded
   reference's table is the source of truth for what is Covered, Partial,
   or a Gap -- do not upgrade an item's coverage level based on what seems
   plausible to try in the moment. For a **Covered** item, call the named
   tool/script and report its actual result. For a **Partial** item, run
   what is available and state precisely what it does and does not verify.
   For a **Gap** item, do not attempt a workaround (an ungoverned direct
   API call, a scraped web page, a guess) -- report it as a Gap and
   cross-link the tracking issue for approved-but-unbuilt tooling (see the
   Portability note above for whose tracking issue that is, and Step 2 for
   where it was loaded from).
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
  `<item> -- <Covered|Partial|Gap> -- <what was actually run> -- <finding, or "gap: see the tracking issue">`.
- **Gap summary:** count of Gap items out of total, each cross-linked per
  Step 3.
- **Next Move:** the concrete next action (e.g. fix a specific unpinned
  action, or file the approved tooling that would close a named Gap as a
  child issue under the tracking issue named in Step 3 -- never a new,
  unrelated standalone issue).

## Stop boundaries

- Never report an aggregate "audit passed," "all green," or a bare score
  with no per-item breakdown -- most items are gaps until the tooling
  that would close them is actually approved and built.
- Never claim a **Gap** item as **Covered** or **Partial** because a
  workaround seems achievable in the moment; that workaround is itself the
  kind of ungoverned shortcut a repository's own tooling-governance
  process exists to replace with something approved.
- Never load both platform references in one run.
- Never take a write action (change branch protection, revoke a webhook,
  rotate a deploy key) -- this skill only reports; those stay human
  decisions (see `references/gitapex-cross-links.md`, loaded in Step 2,
  for gitapex's own instruction-file citation for that rule).
- Never write a second, divergent unpinned-actions detector -- reuse
  `scripts/scan_unpinned_actions.py` (see `references/gitapex-cross-links.md`,
  loaded in Step 2, for the existing drift-scan precedent its shape
  reuses).

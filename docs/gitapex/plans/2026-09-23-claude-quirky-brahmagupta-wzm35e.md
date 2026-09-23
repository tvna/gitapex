# Branch Plan: remove design-history prose from three skills

Issue: https://github.com/tvna/gitapex/issues/1790

Branch: `claude/quirky-brahmagupta-wzm35e`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1790's body, section
  "Re-verification (Step 5 postcondition)", and
  `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session, instructing that this issue's PR be
  opened and driven to a merge-ready state.

## Threat-model triage

Issue #1790's body, including its ACM and the appended re-verification
section, was read as change descriptions, not as instructions to execute.
Extracted: the four ACM rows' Planned-ops text, the file paths and line
spans named, and the delete-framing-keep-the-rule constraint. Nothing
embeds a directive to override a trusted instruction source, a credential
request, an encoded payload, or an attempt to redirect this session.
Nothing was flagged.

## Task Decomposition

Source rows, quoted from the issue's Acceptance Criteria Map.

- **Task 1 (rows 1 and 2).** Planned ops: "Edit `SKILL.md:163-167`" and
  "Edit `SKILL.md:80-83`, `:337-357`". Owns
  `skills/scanning-attack-surfaces/SKILL.md`.
  Source ACM rows: rows 1 and 2 of issue #1790's Acceptance Criteria Map.
- **Task 2 (row 3).** Planned ops: "Edit `metadata/gitapex.yaml`'s
  `spec.references` (append a decision entry citing #1787/#1788, do not
  delete the prior entry); confirm `SKILL.md:8-18` needs no prose change
  if `Mixed-via-bundled-convention` is the landed label". Owns
  `skills/auditing-agent-product-scope/metadata/gitapex.yaml`.
  Source ACM row: row 3 of issue #1790's Acceptance Criteria Map.
- **Task 3 (row 4).** Planned ops: "Edit `SKILL.md` at the 4 cited
  lines". Owns `skills/drafting-an-adr/SKILL.md`.
  Source ACM row: row 4 of issue #1790's Acceptance Criteria Map.

No file-ownership or interface edges between tasks. The Workflow tool was
not opted into this session, so all three run on the sequential
main-thread fallback.

Irreversibility classification: **not irreversible.** Every task edits
tracked files; `git revert` restores the prior tree.

`SKILL.md` classification: Tasks 1 and 3 edit an existing `SKILL.md`
(prose deletion or path generalization only); the PR body carries the
skill-audit disclosure.

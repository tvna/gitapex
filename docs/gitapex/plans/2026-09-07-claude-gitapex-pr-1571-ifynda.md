# Branch Plan: skill-audit-disclosure verdict-line parser fragility

Issue: https://github.com/tvna/gitapex/issues/1571
Branch: `claude/gitapex-pr-1571-ifynda`

## Acceptance Criteria Map

(Re-verified by `planning-a-branch-from-an-issue` this session; full text
and re-verification rationale -- including one correction to row
[#1547]'s own documentation-location planned op -- posted to issue
#1571's own body.)

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| [from #1547] PR-body verdict line rejected due to an overly strict regex | `_line_pattern`'s trailing `[ \t]*$` requirement does not tolerate a verdict token directly followed by punctuation (only end-of-line or whitespace-plus-text) | Relax `_line_pattern` in `.github/scripts/gitapex_gate_skill_audit_disclosure.py` and its local-hook counterpart `hooks/gitapex_check_skill_audit_disclosure_or_waiver.py` to tolerate a token immediately followed by one of a fixed, narrow punctuation set before requiring end-of-line/whitespace, without weakening the existing `\b` word-boundary requirement | Regression test added first (fails against the reintroduced defect), passes after the fix; existing suite stays green | Medium -- regex relaxation must not let a longer word containing the verdict as a prefix match |
| [from #1510] emphasis-wrapped disclosure line gives only a generic not-found message | The exact-match regex rejects a line wrapped in Markdown emphasis with no diagnostic naming that specific cause | In `.github/scripts/gitapex_gate_skill_audit_disclosure.py`, detect a line matching the label prefix but failing only due to emphasis wrapping and emit a targeted diagnostic | Regression test added first, passes after the fix | none identified |
| [from #1534] fixture `output_not_contains` collides with legitimate non-negated prose | `check_negation` only flags a banned substring directly preceded by a denial cue, missing the same phrase appearing elsewhere as ordinary prose | Broaden `evals/scripts/gitapex_lint_fixture_assertions.py`'s negation-trap check to also flag a banned substring appearing verbatim anywhere in the target skill's own prose | Regression test added first, passes after the fix | Deliberate over-flagging bias accepted (matches existing `check_negation` precedent) |
| [from #1490] attribution-footer trim misreported as CONTENT_LOSS | `detect_content_loss()` only tolerates the append direction (`stored.startswith(submitted)`); the ratified trailer being trimmed from the end is the opposite direction and is not tolerated | Extend `detect_content_loss()` in `hooks/gitapex_check_post_write_provenance.py` to also treat "stored equals submitted with the ratified attribution trailer trimmed from the end" as non-loss, scoped to the exact ratified trailer text only | Regression test added first, passes after the fix | Narrow, exact-string match only -- must not mask genuine loss near the trailer |
| [from #1784] code-span-wrapped `name: VERDICT` not caught locally | Same underlying `_line_pattern` defect as [#1547] (closing backtick lands directly after the verdict token) | Covered by the #1547 regex relaxation above; add a dedicated regression fixture pinning this exact malformed-backtick shape so it cannot regress silently | Fixture reproduces the original failure, then passes after the shared fix | none identified |
| [from #1888, dup of #1547] verdict token directly followed by punctuation (`RAN.`) | Identical defect to [#1547] | Covered by the #1547 planned ops; no new ops | Regression test covers this exact shape (`RAN.`) | none identified |
| Documentation | Verdict-line's exact required shape (token then only EOL / whitespace+text / the punctuation set from the #1547 fix) was undocumented | Add a short clarification (a few sentences) to the existing "## Skill audit evidence" convention bullet in `skills/planning-a-branch-from-an-issue/references/github-issue-workflow.md` (NOT `drafting-a-pr-to-merge/SKILL.md` Step 8 -- corrected during re-verification: that step never documented this format, and touching a `skills/*/SKILL.md` file would needlessly trigger the two-audit disclosure requirement) | Manual review (documentation only) | none identified |

## Task 1: Relax the verdict-line regex (punctuation tolerance) + emphasis diagnostic

Both changes share one file family (`.github/scripts/gitapex_gate_skill_audit_disclosure.py`
and its local-hook counterpart) and one concern (verdict-line matching
robustness) -- combined into a single task to avoid a same-file
ownership conflict with a hypothetical separate task.

- Files:
  - Edit: `.github/scripts/gitapex_gate_skill_audit_disclosure.py`
  - Edit: `hooks/gitapex_check_skill_audit_disclosure_or_waiver.py`
  - Edit: `tests/test_gitapex_gate_skill_audit_disclosure.py`
  - Edit: `tests/test_gitapex_check_skill_audit_disclosure_or_waiver.py`
  - Check (no edit expected): `tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`
    stays green since both files keep identical `_line_pattern`/`_name_prefix` logic
- Design:
  1. `_line_pattern`'s verdict alternative currently requires, after the
     verdict token and its `\b`, either end-of-line or
     `[ \t]+\S.*` before the trailing `[ \t]*$`. Add a narrow escape: the
     verdict token may also be followed directly by exactly one character
     from a fixed set of ordinary sentence punctuation (`.`, `,`, `;`,
     `:`, `!`, `?`, `` ` ``), then either end-of-line or
     `[ \t]+\S.*` as before. Do not allow more than one such punctuation
     character, and do not relax the `\b` requirement itself -- this must
     not let a longer word containing the verdict as a prefix match.
  2. Add a targeted diagnostic: when a line matches the label prefix
     (`_name_prefix`) but the remainder is wrapped in Markdown emphasis
     (`**...**` or `_..._`) around what would otherwise be a valid
     verdict/WAIVED clause, report that specific cause instead of the
     generic "no valid disclosure line" message.
  3. Apply the identical `_line_pattern` change to
     `hooks/gitapex_check_skill_audit_disclosure_or_waiver.py` (keeps the
     existing hook-sync test passing).
- Regression tests (fail first against the reintroduced defect, pass
  after the fix):
  a. `checker-script-adversarial-review: RAN.` (trailing period, #1888's
     exact reported shape) is accepted.
  b. `` `checker-script-adversarial-review: RAN` `` (whole `name: VERDICT`
     wrapped in one shared code span, #1784's exact reported shape) is
     accepted.
  c. `evaluating-skill-quality: **WELL-FORMED-AND-MATURE**` (or similar
     emphasis wrapping) produces the new targeted diagnostic naming
     emphasis wrapping as the cause.
  d. Defeat test: a verdict-shaped word is not falsely accepted merely
     because it starts with a valid verdict token followed by more word
     characters (e.g. `RANDOM` must still fail) -- confirms the `\b`
     requirement is not weakened by the punctuation escape.
- Proof method: tests (a)-(d) above, run failing before the change and
  passing after; full existing suite green; hook-sync test still passes.
- Irreversibility: reversible (regex/message changes only, no schema or
  data migration).

## Task 2: Broaden `check_negation` for verbatim-anywhere collisions

- Files:
  - Edit: `evals/scripts/gitapex_lint_fixture_assertions.py`
  - Edit: `tests/test_gitapex_lint_fixture_assertions.py`
- Design: add a sibling check (or extend `check_negation`) that flags an
  `output_not_contains`/`output_not_icontains` (and grader
  `not_contains_cs`/`not_contains`) value appearing verbatim anywhere in
  the target skill's own SKILL.md prose, not only immediately after a
  denial cue. Keep the existing cue-adjacency check's own message
  distinct from the new verbatim-anywhere finding so a reader can tell
  which shape triggered.
- Regression tests: (a) the exact #1534 shape -- a banned phrase present
  as ordinary, non-negated prose elsewhere in the target skill -- is now
  flagged; (b) the existing cue-adjacency case still flags exactly as
  before (no regression); (c) a banned phrase that does not appear
  anywhere in the corpus is not flagged (no over-flagging beyond the
  accepted verbatim-anywhere bias).
- Proof method: tests (a)-(c), failing before the change, passing after;
  full existing suite green.
- Irreversibility: reversible.

## Task 3: Tolerate ratified-footer trim in `detect_content_loss`

- Files:
  - Edit: `hooks/gitapex_check_post_write_provenance.py`
  - Edit: `tests/test_gitapex_check_post_write_provenance.py`
    (+ `tests/test_gitapex_check_post_write_provenance_properties.py` if
    a property-based case is warranted)
- Design: `detect_content_loss()` currently returns None only when
  `norm_stored == norm_submitted` or `norm_stored.startswith(norm_submitted)`
  (append-only). Add one more non-loss case, scoped exactly to the
  ratified trailer text CONTRIBUTING.md's own "outward-artifact-preflight:
  PR-body trailer disclosure" section describes (the italic
  "Generated by [Claude Code](https://claude.ai/code)" GitHub-appended
  trailer, preceded by its own `---` rule and blank-line separator): when
  `norm_submitted` ends with that exact trailer text and `norm_stored`
  equals `norm_submitted` with exactly that trailing text removed
  (and nothing else different), treat it as non-loss. Do not generalize
  to an arbitrary suffix-strip allowance.
- Regression tests: (a) the exact #1490 shape -- submitted body ends with
  the ratified trailer, stored body is byte-identical minus that trailer
  -- is non-loss; (b) a stored body missing the trailer AND missing other
  real content is still flagged as loss (the narrow match must not mask
  a genuine loss); (c) a stored body missing a *different* trailing
  string that merely resembles the ratified trailer is still flagged as
  loss (exact-match only, not fuzzy).
- Proof method: tests (a)-(c), failing before the change, passing after;
  full existing suite green.
- Irreversibility: reversible.

## Task 4: Document the verdict-line's exact required shape

- Files:
  - Edit: `skills/planning-a-branch-from-an-issue/references/github-issue-workflow.md`
- Design: add a short clarification (a few sentences) to the existing
  "## Skill audit evidence" write-path bullet (around lines 38-44)
  stating the exact shape a verdict/waiver line's token must take --
  end-of-line, whitespace then more text, or (after Task 1 lands) one of
  the fixed punctuation characters Task 1 allows directly after the
  token -- cross-referencing
  `.github/scripts/gitapex_gate_skill_audit_disclosure.py`'s own
  `_line_pattern` as the enforced source of truth, and stating separately
  that a waiver line's own shape (`WAIVED: <non-empty reason>`) is
  unaffected by the punctuation exception. Depends on Task 1's output
  (the exact punctuation set) -- sequenced after it, not co-assigned to
  the same wave.
- Proof method: manual review; no code behavior change, no test needed.
  Does not touch a `skills/*/SKILL.md` file, so this task does not by
  itself trigger the skill-audit-disclosure gate's two-audit requirement.
- Irreversibility: reversible (documentation only).

## File-ownership / interface-dependency edges

- Task 1 and Task 4 share a semantic (not file-path) interface
  dependency: Task 4's sentence must describe the exact punctuation set
  Task 1 implements. Sequenced (Task 4 after Task 1), never co-assigned.
- Tasks 1, 2, 3 touch disjoint files with no interface dependency between
  them.

## Wave assignment

wave 1: {Task 1, Task 2, Task 3} -- disjoint files, no interface edges among these three; dispatched in parallel via the `Workflow` tool, `agentType: 'branch-plan-task'`, `isolation: 'worktree'` (this skill's own Step 6 primary path; opted into via this session's own invocation of `executing-a-branch-plan`, whose Step 6 instructs calling `Workflow`).
wave 2: {Task 4} -- depends on Task 1's merged output (the exact punctuation set documented must match what Task 1 actually implemented).

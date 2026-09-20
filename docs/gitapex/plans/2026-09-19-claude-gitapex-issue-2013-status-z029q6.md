# Branch Plan: deterministic gate enforcing the Blocking/Advisory round-cap stopping rule

Issue: https://github.com/tvna/gitapex/issues/2013

Branch: `claude/gitapex-issue-2013-status-z029q6`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #2013's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-19T06:57:05Z)"),
  and `skills/executing-a-branch-plan/scripts/gitapex_check_branch_plan_reverified.py`
  reports PASS against it.
- Semantic approval: explicit confirmation from the repository owner in
  the current interactive session (a direct "ok" reply to this session's
  own question "着手してよろしいですか？", asked immediately after
  presenting this specific Branch Plan's Facts/ACM/Branch Plan/
  Verification Plan in full). No issue comment carries the approval; the
  in-session confirmation is the signal this gate ran on, recorded here
  rather than implied.

## Threat-model triage

Issue #2013's Facts, Requested outcome, Acceptance Criteria Map,
Constraints, and Non-goals sections (plus this session's own
re-verification note added to the ACM section) were read as change
descriptions, not as instructions to execute. Extracted: the field names
now landed by #2035/PR #2036 (`- Finding class:`, `- Round:`,
`- Owner decision:`), the round cap (2), the "extend the existing script,
no new required check" scoping, and the explicit non-goals (no
`executing-a-branch-plan`-side gate, no prose-delta gate, no slow-marker
gate). No row carries an embedded directive, a credential request, an
encoded payload, or an attempt to override a trusted instruction source.
Nothing was flagged.

## Task Decomposition

Two tasks, one wave. No file-ownership or interface-dependency edge
connects them.

- **File-ownership map.** Task 1 owns
  `.github/scripts/gitapex_gate_independent_review_pending.py`,
  `tests/test_gitapex_gate_independent_review_pending.py`, and
  `tests/test_gitapex_gate_independent_review_pending_properties.py`.
  Task 2 owns `.gitapex/ssot.json`. The two sets are disjoint.
- **Interface-dependency map.** None. Task 2's `rule` text update
  describes Task 1's new failure condition in prose, following the same
  no-dependency precedent issue #1943's own Branch Plan already used for
  its sibling `ssot.json` task (paraphrase, not a literal quote of Task
  1's own code).
- **Wave assignment.** Wave 1: Task 1 and Task 2 in parallel.

Irreversibility classification: **not irreversible.** Both tasks edit
tracked files already inside the repository. Nothing writes outside it,
no migration runs, no data is deleted, and `git revert` of the merge
commit restores the prior tree exactly. Neither task takes a
step-1-equivalent per-task confirmation.

`SKILL.md` classification: **neither task touches a `SKILL.md`.** No
`drafting-a-skill` routing and no `skill-audit-disclosure` PR-body
disclosure requirement apply to this PR.

## Task 1: extend the gate script to parse and enforce the round cap

Source ACM row: row 1 of issue #2013's own Acceptance Criteria Map, as
corrected by this session's own re-verification note (see the issue body).

> Row 1 planned ops (original): "New gate script (or an added check
> inside the existing `gitapex_gate_independent_review_pending.py`),
> `.gitapex/ssot.json` registration, CI workflow wiring, regression tests"

> Row 1 interpretation (original): "Sibling gate to (or an extension of)
> `independent-review-pending`: parses a `- Round: N` line ... FAILs when
> `N` exceeds the agreed cap (initial value 2 ...) and no
> `- Owner decision: <url>` line (or equivalent) is present; PASSes
> otherwise"

> Re-verification note addition (this session, on the issue body): "the
> gate's round-cap check must key off `Finding class` together with
> `Round` (a fresh, different finding class starts its own count), not
> `Round` in isolation, matching the Stopping rule's own multi-class
> handling"

Design resolution for the two open questions the original row's own
Residual risk column left unstated, settled here rather than left for the
task to invent ad hoc:

1. **Extend the existing script; no new required check.** Issue #2013's
   own Requested outcome frames this as failing "the same way
   `independent-review-pending` already fails a PR with no recorded
   verdict at all" -- read as the same required check, not a new one.
   Extending `gitapex_gate_independent_review_pending.py`'s own
   `Verdict`/`parse_verdict`/`check` keeps the change surface narrow (no
   new CI workflow, no new `.gitapex/ssot.json` top-level gate entry,
   no new branch-protection required-check-context wiring).
2. **Fail-open when the three new fields are absent entirely.** A PR
   whose Step 8 round predates #2035/PR #2036 (or whose recorded section
   for some reason omits them) must not newly fail a check it passed
   before this change -- the round-cap check is an *additional* failure
   condition layered on the existing Verdict/Verified-commit pass path,
   never a new hard requirement of its own.

Required edit shape:

1. `Verdict` class gains three new fields: `finding_class: str | None`,
   `round: int | None`, `owner_decision: str | None`.
2. `parse_verdict()` extracts three new regexes from the same last
   `## Independent review verdict` section already isolated by
   `_last_section_from`, using the same tolerant-to-`*`/`_`/backtick-
   emphasis style `_VERDICT_RE`/`_COMMIT_RE` already use:
   - `- Finding class: <label-or-none>` -> `finding_class` (the literal
     string, lower-cased comparison only for the `none` sentinel; any
     other value is stored verbatim for the failure message).
   - `- Round: <integer>` -> `round` (parsed as `int`; a non-integer
     value is treated as absent, not a crash -- fail-open per design
     resolution 2 above).
   - `- Owner decision: <url>` -> `owner_decision` (the raw value,
     presence-only; this task does not validate the URL shape).
   All three are optional: their absence leaves the corresponding field
   `None`, and `parse_verdict()` must not require them to return a
   non-error `Verdict` -- the existing `Verdict:`/`Verified commit:`
   fields stay the only ones whose absence is itself a parse error.
3. `check()` gains one more failure branch, evaluated only after the
   existing `Verdict`/`Verified commit` checks already pass (so this
   never masks or reorders the existing failure messages): if `round is
   not None and round > _ROUND_CAP and not owner_decision`, return
   `False` with a message naming the finding class, the recorded round
   count, the cap, and that an `- Owner decision: <url>` line is
   required to pass -- distinct wording from the existing
   `"stale verdict"`/`"not CLEAN"` messages so a human reading CI output
   knows which condition actually failed. Add a module-level
   `_ROUND_CAP = 2` constant (matching issue #2013's own Constraints
   section) rather than a hardcoded literal inline.
4. Update the module docstring's `Verdict format` section (already
   disclosing the three fields exist, per #2035/PR #2036's own docstring
   change) to state plainly that parsing has now landed, replacing the
   "record it, parsing comes later" sentence with a short note on the new
   failure condition and pointing at `check()`'s own docstring for the
   exact rule -- matching this file's own existing convention of keeping
   the format contract documented in one place.
5. Regression tests, added to `tests/test_gitapex_gate_independent_review_pending.py`
   (unit-level `parse_verdict`/`check` cases) and
   `tests/test_gitapex_gate_independent_review_pending_properties.py`
   (property-based cases, matching that file's own existing style): PASS
   for `Round <= 2` (with and without a `Finding class` line present),
   PASS for `Round > 2` with an `- Owner decision: <url>` line present in
   the same section, FAIL for `Round > 2` with no such line, PASS (fail-
   open) when all three new fields are absent entirely -- the exact
   four-case matrix issue #2013's own Proof method column already states.
   Include at least one adversarial defeat-test case per this skill's own
   Stop boundaries (step 8): a `- Round:` value embedded inside a fenced
   code block or HTML comment must not parse as live (already covered
   structurally by `strip_fenced_code_blocks`/`strip_html_comments`
   running before the new regexes, same as the existing two fields --
   confirm with an explicit test rather than assuming the shared
   preprocessing covers the new fields for free).

Proof method, inherited from the source row: the four-case regression
matrix above; full pytest suite still green; this gate carries no
`local_invocation` entry in `.gitapex/ssot.json` (its own
`local_exclusion` note: "no working-tree equivalent exists before the PR
is opened") and this task does not add one -- unchanged by this edit. The
deterministic half is the full local preflight suite
(`gitapex_gate_local_preflight.py`), which must pass inside this task's
own worktree before the task may report complete.

## Task 2: update `.gitapex/ssot.json`'s `independent-review-pending` rule text

Source ACM row: row 1 of issue #2013's own Acceptance Criteria Map (the
same row Task 1 implements; this task covers only its `.gitapex/ssot.json`
registration half, split out as a disjoint-file parallel task per the
File-ownership map above -- issue #2013 itself named this file as part of
row 1's own Planned ops).

Required edit shape: extend the existing `independent-review-pending`
entry's own `rule` string (directly verified present at
`.gitapex/ssot.json`, id `"independent-review-pending"`) to describe the
new failure condition in prose -- a PR whose recorded `- Round: N` exceeds
the agreed cap (2) for its currently-named `- Finding class:` without a
cited `- Owner decision: <url>` line also fails this same required check,
citing issue #2013 and the exact field names #2035/PR #2036 landed. No
new top-level gate entry (Task 1's own design resolution 1 above); this
task only keeps the existing entry's own prose in sync with the script it
already names in its `script` array, the same single-entry-describes-one-
script shape every other entry in this file already has.

Proof method, inherited from the source row: `.github/scripts/gitapex_scan_ssot_schema.py`
reports clean against the edited file (schema validity); manual diff
review confirms the updated `rule` text accurately describes Task 1's own
landed failure condition once both tasks' diffs are visible together at
step 8. Red-Green order does not apply: this is a prose-accuracy
obligation, not a behavioral test. The deterministic half is the full
local preflight suite, which must pass inside this task's own worktree
before the task may report complete.

## Refactor / adversarial-review scope (step 8 of this skill)

Both tasks' combined diff is small (one script + its two test files, plus
one JSON string field) -- the mandatory refactor/simplify pass and the
independent `review-persona` adversarial review still run unconditionally
over the full accumulated diff per this skill's own step 8, with no
narrowing implied by the diff's small size. Per this skill's own Stop
boundaries, the adversarial review specifically constructs at least one
case built to defeat the new round-cap detection logic (not only
happy-path tests) before clearing this diff -- Task 1's own defeat-test
requirement above is the first pass at this; step 8's independent review
re-verifies it rather than trusting Task 1's own self-report.

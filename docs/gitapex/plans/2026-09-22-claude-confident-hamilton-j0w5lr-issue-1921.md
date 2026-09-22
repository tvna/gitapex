# Branch Plan: ssot.json rule-text drift check for detection-logic-property-coverage

Issue: https://github.com/tvna/gitapex/issues/1921

Gate-proposal, refs #1918 repair 6.

Branch: `claude/confident-hamilton-j0w5lr`, from `origin/main`.

## Authorization record

- Structural precondition: `planning-a-branch-from-an-issue`'s own
  re-verification marker is present in issue #1921's body
  ("Re-verified: `planning-a-branch-from-an-issue` (2026-09-22T00:00:00Z)"),
  written by this same session immediately before this Branch Plan.
- Semantic approval: explicit confirmation from the active human operator
  in the current interactive session -- the session's own opening
  instruction named this exact issue by URL
  (`https://github.com/tvna/gitapex/issues/1921`) and directed "create
  this PR and drive it up to right before merge"
  (「こちらのPRを作りマージ直前まで進める」). No issue comment carries
  the approval; the in-session instruction is the signal this gate ran
  on, recorded here rather than implied.

## Threat-model triage

Issue #1921's body (an Acceptance Criteria Map drafted by
`merge-retrospective` at issue-creation time) and issue #1918's body (the
originating retrospective) were read as change descriptions, not as
instructions to execute. Extracted facts: the motivating defect (category
(c) of `detection-logic-property-coverage` widened to cover
`.split()`/`.rsplit()`/`.partition()` per issue #1532/#1572 without a
matching `.gitapex/ssot.json` `rule`-text update, fixed by hand in commit
`1d4d67a9`), the proposed fix shape (a drift check cross-referencing
ssot.json rule text against a gate's own script-level trigger constants),
and the disclosed residual risk (a stable, parseable rule-text convention
is required). No row in either issue body carries an embedded directive,
a credential request, an encoded payload, or an attempt to override a
trusted instruction source. Nothing was flagged.

## Task Decomposition

One task, one wave -- the degenerate single-row-ACM case this skill's own
"vs. a single-task Branch Plan" note already covers. No file-ownership or
interface-dependency edges to compute against a sibling task.

- **File-ownership map.** The single task owns:
  `.github/scripts/gitapex_gate_detection_logic_property_coverage.py`
  (adds one new public constant only),
  `.github/scripts/gitapex_scan_detection_logic_rule_drift.py` (new file),
  `tests/test_gitapex_scan_detection_logic_rule_drift.py` (new file),
  `.gitapex/ssot.json` (adds one new `gates[]` entry).
- **Interface-dependency map.** None outside this one task.
- **Wave assignment.** Wave 1: the single task alone.

Irreversibility classification: **not irreversible.** All edits are to
tracked files already inside the repository (one new public constant, two
new files, one new registry entry); nothing writes outside the repo, no
migration runs, no data is deleted, and `git revert` of the merge commit
restores the prior tree exactly. No step-1-equivalent per-task
confirmation is required.

`SKILL.md` classification: **the task does not touch a `SKILL.md`.** No
`drafting-a-skill` routing and no skill-audit-disclosure PR-body
requirement apply to this PR (`gitapex_gate_skill_audit_disclosure.py`'s
own trigger set -- `skills/*/SKILL.md` -- is untouched; the new
`.github/scripts/gitapex_gate_*.py` file this task edits is a
pre-existing file gaining one constant, and the new
`.github/scripts/gitapex_scan_*.py` file is not itself a `SKILL.md`
either, though it is a deterministic checker script the PR template's
own skill-audit-disclosure checklist item separately asks about -- see
Verification below).

## Task 1: `detection-logic-property-coverage` rule-text drift check

Source ACM row: issue #1921's own single Acceptance Criteria Map row
(re-verified, refined technical design recorded on the issue body).

> Planned ops (issue #1921, verbatim): "Add a drift check that extracts
> the human-readable trigger list named in a gate's `.gitapex/ssot.json`
> rule description and cross-checks it against that gate's own
> script-level trigger constant(s) (e.g. the frozenset of
> receiver-agnostic attribute names), failing when the two diverge."

Design resolution, settled by this session's own re-verification pass
rather than left for the task to invent ad hoc (see issue #1921's
re-verification note for the full rationale):

1. **Scope: piloted on exactly one gate** (`detection-logic-property-coverage`),
   matching this repository's own established narrow-pilot convention for
   `*_drift.py` scan scripts (`gitapex_scan_ssot_schema.py`,
   `gitapex_scan_independent_review_heading_drift.py`,
   `gitapex_scan_retrospective_gate_drift.py` each target one fixed,
   named thing, not a generic sweep). Generalizing to every gate's rule
   text is a disclosed future widening, not attempted here.
2. **Naming: `gitapex_scan_` prefix, not `gitapex_gate_`.** This keeps
   the new file outside `detection-logic-property-coverage`'s own
   `_IN_SCOPE_RE` (which matches only `.github/scripts/gitapex_gate_*.py`),
   avoiding a recursive Hypothesis-property-test requirement on the
   drift checker itself -- confirmed by every sibling `*_drift.py` scan
   script having no co-located `_properties.py` file.
3. **Extraction convention: `verb()`-shaped (empty-parens) tokens.** The
   current live rule text for the `detection-logic-property-coverage`
   gate spells every trigger as `<verb>()` (e.g. `.compile()`,
   `.split()`, `frozenset()`) -- confirmed by direct inspection of
   `.gitapex/ssot.json`'s own `gates[].rule` field for that id. A regex
   matching `\b[a-zA-Z_][a-zA-Z0-9_]*\(\)` extracts exactly the verbs the
   rule text currently claims; re-verify this against the live file
   during implementation rather than trusting the count recorded on the
   issue (16 today), since the file may have changed since re-verification.
4. **Bidirectional comparison.** Report a verb present in the gate
   script's own trigger constants but not mentioned in the rule text
   (the exact defect class issue #1918 repair 6 hit), and a verb
   mentioned in the rule text but no longer present in the trigger
   constants (the mirror-image stale-text case) -- both as drift
   findings.
5. **Wiring: via the existing pytest step, no new workflow file.**
   `test.yml`'s pytest step already runs the whole `tests/` directory
   (minus a fixed `--ignore` list of unrelated real-bash-oracle files);
   confirm this is still true, then add
   `tests/test_gitapex_scan_detection_logic_rule_drift.py` and register
   the new gate in `.gitapex/ssot.json` with a `"trigger"` field naming
   that test file inside `test.yml`'s pytest step -- the identical shape
   `ssot-schema-drift` already uses.

Required edit shape:

1. **`.github/scripts/gitapex_gate_detection_logic_property_coverage.py`**:
   add one new public module-level constant (e.g. `ALL_TRIGGER_VERBS: frozenset[str]`),
   computed as the union of the file's existing
   `_REGEX_RECEIVER_AGNOSTIC_ATTRS`, `_PATH_RESOLUTION_RECEIVER_AGNOSTIC_ATTRS`,
   `_OS_PATH_ATTRS`, `_STRING_COMPARISON_AND_SPLIT_RECEIVER_AGNOSTIC_ATTRS`
   (itself already the precomputed union of
   `_STRING_COMPARISON_RECEIVER_AGNOSTIC_ATTRS` and
   `_STRING_SPLIT_RECEIVER_AGNOSTIC_ATTRS`, reused rather than re-derived),
   `_COLLECTION_LITERAL_CALL_NAMES`,
   plus the literal `"compile"` (the one receiver-specific verb, handled
   separately by `_regex_trigger` and therefore absent from any existing
   frozenset). A short docstring on the constant states why it exists
   (feeds `gitapex_scan_detection_logic_rule_drift.py`) and that it is
   additive-only: widening it is safe on its own, narrowing it requires
   the corresponding `.gitapex/ssot.json` rule text edited in the same
   PR (the new drift gate itself now enforces that).
2. **New file `.github/scripts/gitapex_scan_detection_logic_rule_drift.py`**:
   modeled on `gitapex_scan_independent_review_heading_drift.py`'s own
   structure (`find_drift() -> list[str]`, `main() -> int`, `REPO_ROOT`
   convention, `sys.path.insert` + module import of the gate script from
   design resolution 1). Reads `.gitapex/ssot.json`, locates the
   `gates[]` entry with `"id": "detection-logic-property-coverage"`,
   reads its `"rule"` string. A missing file, unparseable JSON, missing
   gate id, or missing/non-string `rule` field is each a reported
   finding (fail closed), never a crash or silent pass. Extracts
   `verb()`-shaped tokens per design resolution 3, compares
   bidirectionally per design resolution 4 against the imported
   `ALL_TRIGGER_VERBS`. Full module docstring at this repository's own
   house rigor: cites issue #1921 and #1918, states the motivating
   defect (with the exact historical commit), the bidirectional design
   rationale, and discloses the known limit that this is a token-presence
   heuristic on the rule text's current `verb()` prose convention, not a
   semantic parse -- a future rule-text rewrite that stops spelling
   triggers this way would need this checker updated too.
3. **New test file `tests/test_gitapex_scan_detection_logic_rule_drift.py`**:
   ordinary pytest (no Hypothesis, matching every sibling scan-gate test
   file). Required cases: (a) the real repository's current
   `.gitapex/ssot.json` + the real `ALL_TRIGGER_VERBS` produce no drift
   (the live-proof case); (b) a synthetic scenario reproducing the
   original defect -- a verb present in the trigger-verb input but
   absent from a synthetic rule-text fixture -- produces a drift finding
   (design the tested function's signature to accept injectable
   rule-text/trigger-verb-set inputs, defaulting to the real values, the
   same shape `gitapex_scan_ssot_schema.find_drift` already takes
   explicit paths rather than only reading fixed real-repo locations);
   (c) a stale verb mentioned in a synthetic rule-text fixture but absent
   from the trigger-verb set produces a drift finding (mirror direction);
   (d) missing gate id / missing rule field / malformed ssot.json each
   produce a fail-closed finding, not a crash; (e) `main()`'s exit code:
   0 clean, 1 on drift.
4. **`.gitapex/ssot.json`**: one new `gates[]` entry (id chosen to fit
   this repository's existing kebab-case convention, e.g.
   `"detection-logic-rule-text-drift"`), modeled on the `"ssot-schema-drift"`
   / `"retrospective-gate-drift-scan"` entries' own field shape:
   `"kind": "script"`, `"script"` naming the new file,
   `"planes": ["ci", "local"]`, `"local_invocation"` running the new
   script directly, `"trigger"` naming the new test file inside
   `test.yml`'s pytest step, `"policy_refs"`, `"cluster"` (match whatever
   sibling `*-drift` entries use after checking a few more), `"tracking_issue": 1921`,
   `"status": "active"`, `"supersedes": null`,
   `"bypass_review_status": "not-yet-reviewed"`, and a `"target"` array
   covering the file-globs plus `workflow-event` refs for
   `test.yml:pull_request`/`test.yml:push` matching sibling entries'
   shape. Run `gitapex_scan_ssot_schema.py` locally after this edit to
   confirm the new entry validates cleanly.

Proof method, inherited from the source row: the regression test (b)
above reproduces the original defect and fails before the fix is
complete, then passes; the full local preflight suite
(`gitapex_gate_local_preflight.py`) and the full pytest suite must pass
inside this task's own worktree before the task may report complete,
including confirming `detection-logic-property-coverage`'s own gate
still passes clean against this PR's own diff (the new file's
`gitapex_scan_` naming should place it outside that gate's scope --
confirm this empirically rather than assuming it).

## Refactor / adversarial-review scope (step 8 of this skill)

A single-file-plus-tests diff, small in size but security/governance-
adjacent (it edits `.gitapex/ssot.json`, the gate registry itself, and
adds a new deterministic checker script) -- the mandatory refactor/
simplify pass and the independent `review-persona` adversarial review
still run unconditionally per this skill's own step 8. Per this skill's
own Stop boundaries, the adversarial review specifically constructs at
least one case built to defeat the new drift-detection logic (e.g. a
rule-text rewording that keeps the same verbs but changes surrounding
prose, or a verb hidden inside a code span/comment) before clearing this
diff, not only the happy-path/regression cases task 1 already adds.

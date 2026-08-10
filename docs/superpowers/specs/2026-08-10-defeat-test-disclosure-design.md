# Defeat-test disclosure for checker/gate scripts: design

Date: 2026-08-10

Refs #998 (refs #982, #984, #988, #989, #990, #997). Design-then-implement
doc, per this repo's own plan-first discipline; the implementing PR carries
this same commit, matching the precedent `2026-07-22-retrospective-gate-drift-design.md`
(issue #297 -> PR #302) set for a sibling meta-gate.

## Context

Issue #982's retrospective (repair 3) proposed requiring a PR that adds or
modifies a deterministic gate to disclose mutation evidence -- for each
guarded property, a mutation that makes the gate fail -- in the same shape
`gitapex_gate_skill_audit_disclosure.py` already requires audit verdicts.
Repairs 4, 5, and 6 in the same issue independently restated the proposal
for three different AST fields one shipped check bypassed on, none caught
before a reviewer found them post-merge. The same item was then
carried forward, worded identically, across five more merge retrospectives
with no implementation: #984, #988, #989, #990, #997.

Issue `#997` supplies the freshest, most direct evidence for why the existing
`checker-script-adversarial-review` check (issue #565) does not already
close this gap: PR #994 disclosed `checker-script-adversarial-review: RAN`
on its first commit, and that self-attested `RAN` still coexisted with two
bugs in the same PR -- a heading-boundary bug caught only by an independent
second reviewer, and a case-sensitivity gap caught only by a second,
separately-invoked `/code-review` round. `RAN` proves a review happened; it
does not prove the review was deep enough to construct a test that defeats
the new logic, as opposed to merely exercising its happy path.

Full verified facts (issue and comment counts, the five existing
process-disclosure checks' own trigger scopes) are recorded in tracking
issue #998; not re-derived here.

## Decisions

### 1. A sixth, standalone process-disclosure check, not folded into `checker-script-adversarial-review`

`gitapex_gate_skill_audit_disclosure.py`'s own docstring already states and
applies this reasoning once, for `deterministic-gate-quality` (issue #673):
that check's trigger scope fully overlaps `checker-script-adversarial-review`'s
today, and it was still kept as a separate flag rather than folded in,
because the two disclose *different processes* -- "that one asks whether an
adversarial review round happened at all; this one asks whether the change
was read against a specific, already-written rubric." The same distinction
applies here: `checker-script-adversarial-review` discloses that a review
round happened; #997's own fresh evidence is that a `RAN` review round can
still miss what a specifically-constructed defeat test would have caught.
Folding this into `checker-script-adversarial-review`'s existing verdict
would silently answer a different question with the same disclosure line a
PR may already be carrying for an unrelated reason.

Rejected alternative: **strengthen `checker-script-adversarial-review`'s own
required content** (e.g. require its RAN disclosure to also name a defeat
test). Rejected because every existing PR body pattern for that check is a
bare `RAN`/`NOT-RUN`/`WAIVED: <reason>` line with no required free-text
content beyond the reason, and grading free-text *content* for a specific
claim (rather than a line's mere presence) is a different, harder-to-verify
shape than every other check in this family. A separate line keeps the
existing check's meaning stable and adds the new claim as its own
independently-gradable fact.

New check name: `defeat-test-disclosure`, following the family's existing
`eval-coverage-disclosure` naming shape (a two-word compound +
`-disclosure`, with no repeated scope word in the name itself since the
scope is carried by when the check fires, not by its name).

### 2. Verdict vocabulary: RAN / NOT-RUN / WAIVED

Issue #998's own Requested Outcome section states the new check must use
"the same RAN/NOT-RUN/WAIVED shape as the existing five checks" -- taken
here as the operative instruction for this row, not left open. This also
matches the check's own substance: unlike `deterministic-gate-quality`
(where "I did not read this against the already-written rubric" was
rejected as a legitimate answer, because the rubric already existed and not
reading it was the exact failure mode that check exists to end),
`NOT-RUN` is a legitimate, honest answer here for many real diffs -- for
example a docstring-only or lint-only edit to a checker script, where no
new detection logic exists yet to construct a defeat test against.
Disallowing `NOT-RUN` would pressure an author toward a fabricated defeat
test for a change with nothing to defeat, which is a worse outcome than an
honest `NOT-RUN`.

### 3. Trigger scope: the union of `checker-script-adversarial-review`'s and `deterministic-gate-quality`'s own scopes

Issue #998's title and Requested Outcome both say "checker **or** gate
script," not one or the other. The two existing checks already compute
non-identical scopes: `changed_checker_scripts` (path-glob based:
`skills/*/scripts/*.py`, `evals/scripts/*.py`, `.github/scripts/*.py`) and
`changed_gate_scripts` (membership-based: `gitapex_detect_changed_gate_scripts.py`'s
four rules, which additionally reach `hooks/*.sh` PreToolUse gates,
`.gitapex/ssot.json` itself, `hooks/hooks.json`, and any workflow YAML
gate implementation the registry names -- none of which the checker-script
globs match). A defeat test is exactly as meaningful for a `hooks/check-*.sh`
gate or a gate implemented as workflow YAML as for a `.github/scripts/*.py`
checker script, so scoping to only one of the two existing signals would
silently exempt real gate changes the issue's own title covers.

Concretely: `gitapex_compute_skill_audit_flags.py` gains one new
`SkillAuditFlags` field, `changed_checker_or_gate_scripts`, computed as the
sorted union of the already-computed `changed_checker_scripts` and
`changed_gate_scripts` tuples. No new detection logic and no new script
file -- both source signals already exist and are independently tested;
this only unions two already-trustworthy sets. `applicable` (whether the
job's second step even runs) already goes true whenever either source list
is non-empty, so this union changes no other check's behavior.

Rejected alternative: **a third, independent detection script** mirroring
`gitapex_detect_changed_gate_scripts.py`'s own shape but for "checker or
gate." Rejected as needless duplication of two rule sets this repository
already computes and already tests; a union of two trusted sets needs no
new I/O or membership logic of its own.

## Mechanism

### `gitapex_compute_skill_audit_flags.py`

- New field `changed_checker_or_gate_scripts: tuple[str, ...] = ()` on
  `SkillAuditFlags`, computed in `compute_flags()` as
  `tuple(sorted(set(checker_scripts) | set(gate_scripts)))`.
- New `OUTPUT_KEYS` entry `"changed-checker-or-gate-scripts"`, threaded
  through `as_output_pairs()` in the same position.
- No change to `applicable`'s own computation, to the D/R100 exclusion
  rules, or to either source signal's own logic.

### `gitapex_gate_skill_audit_disclosure.py`

- New row appended to `_PROCESS_DISCLOSURE_CHECKS`:
  `name="defeat-test-disclosure"`, `cli_flag="--changed-checker-or-gate-scripts"`,
  `cli_dest="changed_checker_or_gate_scripts"`, `verdicts=_PROCESS_DISCLOSURE_VERDICTS`
  (the shared `("RAN", "NOT-RUN")` pair, per Decision 2).
- `_LIST_FLAG_DESTS` picks the new dest up automatically (it iterates
  `_PROCESS_DISCLOSURE_CHECKS`), so `--check-diff` wiring needs no separate
  edit beyond `gitapex_compute_skill_audit_flags.SkillAuditFlags` publishing
  the matching field name (Decision above) -- the existing
  `_apply_check_diff` wiring-guard (`unpublished = [...]`) fails loudly if
  the two ever drift instead of silently never firing.
- `fail_subject="changed deterministic checker or gate script"`,
  `fail_hint` names the specific ask: "disclosing that at least one test
  was constructed to defeat, not merely exercise the happy path of, the
  new or changed detection logic."

### `.github/workflows/skill-audit-gate.yml`

- The diff step already emits every `SkillAuditFlags` output key
  generically via `as_output_pairs()`; the new key needs one added
  `CHANGED_CHECKER_OR_GATE_SCRIPTS` env var and one added
  `--changed-checker-or-gate-scripts "$CHANGED_CHECKER_OR_GATE_SCRIPTS"`
  argument on the "Check skill audit disclosure" step, mirroring every
  existing flag's own two-line addition there.
- No `paths:` trigger change: every path this new check can fire on is
  already covered by the existing checker-script and gate-registration
  path entries the workflow's trigger already lists (verified against
  `gitapex_detect_changed_gate_scripts.py`'s own four membership rules and
  the workflow's existing `paths:` block).

### `.gitapex/ssot.json`

- The `skill-audit-disclosure` gate's existing registry row (`script` list
  already covers every file this change touches) gets its `rule` text
  extended to name the sixth check, matching how each of the five prior
  additions updated the same row's prose rather than adding a new row --
  no new script file is introduced, so no new row is warranted.

### Self-reference

This PR itself modifies `.github/scripts/gitapex_gate_skill_audit_disclosure.py`
and `.github/scripts/gitapex_compute_skill_audit_flags.py`, both already
registered gate-family members. Its own diff therefore owes, and its PR
body discloses: `checker-script-adversarial-review`, `deterministic-gate-quality`,
`design-doc-adversarial-review` (this document), and -- dogfooding the very
check this PR adds -- `defeat-test-disclosure` itself, backed by a unit
test that deliberately constructs a malformed disclosure line (wrong
verdict word, missing colon, stray text after `NOT-RUN`) and asserts the
new check's regex correctly rejects it, not merely a happy-path test that
a well-formed line is accepted.

## Non-goals

(Restated from issue #998, unchanged by this design.)

- Does not retroactively require this disclosure on already-merged PRs.
- Does not mechanically verify that a claimed defeat test is real or
  effective (e.g. an actually-enforced mutation-testing gate that re-runs
  a test against mutated code). The self-attested shape mirrors the
  existing family exactly, matching every prior addition's own rollout.
- Does not audit or re-score the five existing disclosure checks for their
  own effectiveness.

## Acceptance criteria

- [ ] `gitapex_compute_skill_audit_flags.py`'s new
      `changed_checker_or_gate_scripts` field is covered by a unit test
      asserting it is the sorted union of the two source signals,
      including the case where the two sets partially overlap and the
      case where only one is non-empty.
- [ ] `gitapex_gate_skill_audit_disclosure.py`'s new `defeat-test-disclosure`
      check is covered by unit tests for: missing disclosure (FAIL), a
      valid `RAN` line (PASS), a valid `NOT-RUN` line (PASS), a valid
      `WAIVED: <reason>` line (PASS), and at least one deliberately
      malformed line that must still FAIL (the defeat test this check's
      own addition owes itself).
- [ ] `--check-diff` end-to-end: a synthetic diff touching only a
      `hooks/check-*.sh` gate (outside every checker-script glob) still
      triggers `defeat-test-disclosure`, proving the union scope reaches
      paths the checker-script-only scope would have missed.
- [ ] `tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py` and
      `tests/test_gitapex_check_skill_audit_disclosure_or_waiver.py` stay
      green unmodified -- the local hook mirror deliberately does not port
      process-disclosure checks (see its own docstring), so this addition
      must not require touching it.
- [ ] Full pytest suite green; a live dry run of
      `gitapex_gate_skill_audit_disclosure.py --check-diff` against this
      PR's own diff confirms the six-check verdict before this is called
      done, per this repo's live-proof requirement.

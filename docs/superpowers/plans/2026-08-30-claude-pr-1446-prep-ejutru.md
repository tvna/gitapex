# Branch Plan: claude/pr-1446-prep-ejutru

Source issue: https://github.com/tvna/gitapex/issues/1446

## Task list (2 independent tasks, wave 1)

### Task 1: Quote CONTRIBUTING.md's ratified provenance section in the FLAGGED message

**Owns:**
- `hooks/gitapex_check_post_write_provenance.py`
- `tests/test_gitapex_check_post_write_provenance.py`
- `tests/test_gitapex_check_post_write_provenance_properties.py`

**File-ownership / interface-dependency edges:** none against Task 2 (disjoint
file sets, no shared interface -- confirmed via
`gitapex_check_file_ownership_conflicts.py`, zero conflicts).

**Source ACM row (quoted verbatim from issue #1446's re-verified Acceptance
Criteria Map, Item 1):**

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Item 1: the FLAGGED provenance message must quote the ratified text, not just point at it | Read `CONTRIBUTING.md`, extract the `## outward-artifact-preflight: PR-body trailer disclosure` section's own text (from its heading to the next `## ` heading), and include it verbatim (or a bounded excerpt) in the FLAGGED message the hook/scanner already constructs, alongside stating whether the flagged string's shape matches that ratified trailer | Edit `hooks/gitapex_check_post_write_provenance.py`'s FLAGGED-message construction and/or `skills/outward-artifact-preflight/scripts/gitapex_scan_provenance.py`; add a section-extraction helper (heading-to-next-heading, matching this repo's own established pattern for similar extraction elsewhere) | A fixture PR body carrying the ratified trailer produces a FLAGGED message that contains the actual quoted ratified-section text (not merely a pointer to `CONTRIBUTING.md`); a fixture carrying a genuine, unratified leak still flags without a false "this is ratified" implication | Which file(s) own the extraction and message-construction logic, and whether `CONTRIBUTING.md`'s path needs to be resolved relative to a plugin-distributed consumer checkout (where `hooks/` ships but the repo's own `CONTRIBUTING.md` may not, per `docs/repository-layout.md`) is unknown, pending implementation -- a plugin-consumer fallback (name the section instead of quoting it, when `CONTRIBUTING.md` cannot be found) may be needed and should be decided during implementation, not assumed here |

**Implementation guidance (this session's own pre-execution investigation,
not part of the quoted ACM row):**

- Current live text confirmed at `CONTRIBUTING.md` lines 194-218 (heading
  `## outward-artifact-preflight: PR-body trailer disclosure` at line 194,
  next `## ` heading `## Content migration parity check` at line 219).
- The FLAGGED message this task edits is built in
  `hooks/gitapex_check_post_write_provenance.py`'s `evaluate()` function,
  the `return "FLAGGED", (...)` block currently at lines 735-743.
- Add a small heading-to-next-heading section extractor (find
  `## outward-artifact-preflight: PR-body trailer disclosure`, capture
  through the next line starting with `## `, or end of file). Resolve
  `CONTRIBUTING.md`'s path relative to the repo root the hook already
  resolves elsewhere in this file (do not hardcode a path assuming the
  gitapex repo's own checkout layout) so a plugin-distributed consumer
  checkout without `CONTRIBUTING.md` degrades to naming the section
  instead of quoting it, rather than crashing or silently omitting
  the plugin-consumer case.
- Do not weaken or remove the existing "this surfaces candidates, it does
  not decide" framing already in the FLAGGED message.

**Irreversibility classification:** reversible (local code + test change,
no destructive or outward-facing operation).

**Proof method:** automatable test (pytest). Red-Green order applies: a
fixture PR body carrying the ratified trailer must produce a FLAGGED
message containing the quoted section text; a fixture carrying a genuine
unratified leak must still flag without implying it is ratified; the
CONTRIBUTING.md-not-found fallback path needs its own fixture too.

### Task 2: Extend bare-python3-invocation gate to hooks/*.sh's shell-variable-indirected invocations

**Owns:**
- `.github/scripts/gitapex_gate_bare_python3_invocation.py`
- `tests/test_gitapex_gate_bare_python3_invocation.py`
- `.github/workflows/bare-python3-invocation-gate.yml`

**File-ownership / interface-dependency edges:** none against Task 1
(disjoint file sets, no shared interface -- confirmed via
`gitapex_check_file_ownership_conflicts.py`, zero conflicts).

**Source ACM row (quoted verbatim from issue #1446's re-verified Acceptance
Criteria Map, Item 2):**

| Criterion | Interpretation | Planned ops | Proof method | Residual risk |
|---|---|---|---|---|
| Item 2: a bare `python3` invocation of a `.github/scripts/*.py` file from `hooks/*.sh`, reached through a shell variable, must be detected | Extend `gitapex_gate_bare_python3_invocation.py` (or add a sibling check) with a two-step static scan of `hooks/*.sh`: (a) find a shell variable assignment whose right-hand side contains the literal `.github/scripts/\S+\.py` substring, (b) find that same variable name later invoked as `python3 "$varname"` (or unquoted) on a line not preceded by `uv run` | Add a `hooks/*.sh`-scanning function to `gitapex_gate_bare_python3_invocation.py` (or a new sibling script it composes with), reusing the existing gate's own literal-invocation detection for the direct case and adding the variable-tracing step for the indirect case; wire severity as WARNING, not a hard fail, matching #1088's own original reasoning (the `ImportError` fall-through this gap exists to make visible is a documented, deliberate degrade path, not a live break) | A fixture reproducing the real `hooks/check-pr-skill-audit-disclosure.sh` shape (variable assignment on one line, bare `python3 "$var"` invocation on a later line) is detected; a fixture where the same variable's invocation IS `uv run`-wrapped is not flagged; a fixture invoking a `hooks/*.py` file (not under `.github/scripts/`) is not flagged, since those are deliberately stdlib-only and bare-invoked by design | The two-step variable-tracing scan is more complex than the existing gate's single-regex approach and could still miss a name reused across scopes, an indirect double-assignment, or a path assembled via string concatenation rather than a single literal substring -- scope the first implementation to the shapes actually observed in this repo's real `hooks/*.sh` files (confirmed: single assignment, then a same-name bare invocation, no aliasing or concatenation seen) rather than a fully general shell-variable dataflow analyzer, and state that narrowing explicitly in the implementation |

**Implementation guidance (this session's own pre-execution investigation,
not part of the quoted ACM row):**

- Live example confirmed at `hooks/check-pr-skill-audit-disclosure.sh`:
  `full_gate="${repo_root}/.github/scripts/gitapex_gate_skill_audit_disclosure.py"`
  (line 188), invoked bare as `python3 "$full_gate"` (line 220).
- Confirmed by this session's own repo-wide grep: across all `hooks/*.sh`
  files, `full_gate` is the ONLY shell variable whose assignment contains
  a `.github/scripts/*.py` path; every other `hooks/*.sh` variable-
  indirected `python3 "$var"` call site (in `check-bash-safety.sh`,
  `check-issue-acm-disclosure.sh`, `check-post-review-obligation-tracker.sh`,
  `check-post-write-provenance.sh`, `check-pr-duplicate-issue.sh`,
  `check-pr-issue-acm-disclosure.sh`, `check-pr-skill-audit-disclosure.sh`'s
  own `check_script`, `check-pr-title-convention.sh`,
  `check-stop-review-obligation.sh`) targets a `hooks/*.py` file via
  `script_dir`, correctly out of scope. Build the fixture set to include
  at least this real shape (assignment then later bare invocation), the
  `uv run`-wrapped negative case, and a `hooks/*.py`-targeting variable
  negative case, per the ACM's own Proof method column.
- Existing `find_bare_invocations()` (workflows-only) must keep its exit
  code 1 hard-fail behavior unchanged. Add a separate function (e.g.
  `find_hooks_shell_indirected_invocations()`) for the `hooks/*.sh` scan,
  and wire it into `main()` so its findings print but do not flip the
  process exit code to 1 -- WARNING means non-blocking, matching the
  ACM's explicit severity constraint. Confirm
  `.github/workflows/bare-python3-invocation-gate.yml` still fails on the
  existing workflows-only check and does not fail on a `hooks/*.sh`
  finding alone.
- Do not flag `hooks/*.py` invocations (deliberately stdlib-only,
  bare-invoked by design per `docs/repository-layout.md`).

**Irreversibility classification:** reversible (local code + test +
workflow-step change, no destructive or outward-facing operation).

**Proof method:** automatable test (pytest) plus a workflow-level sanity
check that severity stays WARNING. Red-Green order applies: the real
`hooks/check-pr-skill-audit-disclosure.sh` shape must be detected; a
`uv run`-wrapped variant must not be flagged; a `hooks/*.py`-targeting
variable must not be flagged.

## Constraints (carried from the ACM)

- Item 2's gate must not flag a `hooks/*.py` file invoked bare from
  `hooks/*.sh`.
- Item 2's severity is WARNING (report, do not hard-fail CI).
- Item 1 must not weaken or remove the existing "this surfaces
  candidates, it does not decide" judgment-call framing.

## Non-goals (carried from the ACM)

- Does not touch Repair 3 (already resolved, issue #1208/PR #1213) or
  Repair 2 (already resolved, PR #1332).
- Does not address Repair 4 (out of scope, no gate proposed by #1088).
- Does not attempt a fully general shell-variable dataflow analysis for
  Item 2 -- scoped to the direct assignment-then-invocation shape actually
  observed in this repository's real `hooks/*.sh` files today.
- Does not extend the bare-python3-invocation gate to `evals/scripts/*.py`
  (issue #1050's own separate scope).
- Does not decide whether issue #1088 itself should be closed.

# dual-path Visual Companion Implementation Plan

Refs #1263

**Goal:** Add an Artifact-based delivery path to `eliciting-a-design`'s
Visual Companion, alongside the existing Node.js server, per the
operator-approved design doc
`docs/superpowers/specs/2026-08-23-dual-path-visual-companion-design.md`
and issue #1263's own Acceptance Criteria Map (six rows).

**Architecture:** One `SKILL.md` section widened, one new reference file
added, under `skills/eliciting-a-design/`. No changes to any existing
Node.js-path file. A possible eval fixture addition, decided after the
doc content exists (see Task 2).

**Tech Stack:** Plain Markdown. No new dependencies, no runtime code.

## Global Constraints

- Do not modify `skills/eliciting-a-design/references/visual-companion.md`,
  `scripts/server.cjs`, `scripts/start-server.sh`, `scripts/helper.js`,
  or `scripts/frame-template.html` (issue #1263's own Constraints).
- `skills/eliciting-a-design/SKILL.md`'s own Visual Companion section
  stays a compact gate plus pointer -- widen it by the fallback-order
  sentence(s) and a second pointer only; do not inline
  detection/publish/read/security detail there.
- No agent-initiated `edit()`/`sync()` Artifact writes -- zero-API
  gesture sync only (issue #1263's own Constraints).
- Keep every new/edited file ASCII-only, no undisclosed provenance
  markers (outward-artifact-preflight discipline).

## File-ownership and interface-dependency map

ACM rows 1-6 (issue #1263) all write into exactly two files
(`skills/eliciting-a-design/SKILL.md` and the new
`skills/eliciting-a-design/references/visual-companion-artifact.md`);
rows 5 and 6 explicitly touch both. Per the file-ownership rule, this
collapses to one task, not several disjoint ones -- these are facets of
one coherent piece of documentation, not independent files. A possible
Task 2 (eval fixture) has an interface-dependency edge on Task 1 (it
must match Task 1's own actual dispatch-branch wording), so it is
sequenced after Task 1, never co-assigned to the same wave.

Wave 1: {Task 1}. Wave 2 (conditional, decided in the main thread after
Task 1 completes, per `.github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`'s
own counting rules): {Task 2}, only if Task 1's actual text adds a
countable Stop-boundary bullet or named dispatch branch beyond what the
existing eval suite already covers.

Neither task's Planned ops are irreversible (ordinary file edits, fully
git-reversible) -- no per-task re-authorization required.

---

### Task 1: widen SKILL.md's Visual Companion section, add the Artifact-path reference file

**Files:**
- Edit: `skills/eliciting-a-design/SKILL.md` (Visual Companion section,
  currently lines 259-268)
- Create: `skills/eliciting-a-design/references/visual-companion-artifact.md`

**Interfaces:**
- Consumes: nothing from other tasks (first task).
- Produces: the actual fallback-order wording and any named dispatch
  branches in `SKILL.md`, which Task 2 (if dispatched) must match
  exactly, not paraphrase.

**ACM row citations (verbatim Planned ops, quoted from issue #1263):**

- Row 1 ("Artifact-based delivery when available, the existing Node.js
  server as the portable fallback everywhere else"): "Widen
  `skills/eliciting-a-design/SKILL.md`'s existing Visual Companion gate
  to state the fallback order and point to two reference files instead
  of one"
- Row 2 ("Detect via Artifact tool presence"): "New
  `references/visual-companion-artifact.md` states the tool-presence
  check and the runtime-failure downgrade rule; explicitly names the two
  env vars and `window.claude` as prohibited detection methods"
- Row 3 ("Zero-API sync plus terminal-turn trigger"): "New
  `references/visual-companion-artifact.md` documents the publish/read
  loop, the no-full-`innerHTML`-replacement rule, and conflict-is-routine
  handling, mirroring the Node.js reference's own next-turn-read and
  escaping-discipline sections"
- Row 4 (security-model parity table): "Reproduce the table in
  `references/visual-companion-artifact.md`"
- Row 5 (document structure): "Edit
  `skills/eliciting-a-design/SKILL.md`'s Visual Companion section; create
  `skills/eliciting-a-design/references/visual-companion-artifact.md`; do
  not touch `references/visual-companion.md`"
- Row 6 (prerequisite-plus-fallback idiom): "Mirror the exact phrasing
  pattern from SKILL.md's existing 'Available in this repository means
  checked, never assumed' paragraph in the new reference file and the
  widened SKILL.md gate"

- [ ] **Step 1: Widen `SKILL.md`'s Visual Companion section**

  Add 1-2 sentences stating the fallback order (Artifact tool present ->
  Artifact path; else `node` on `PATH` and a reachable browser -> the
  existing Node.js path, unchanged; else -> text-only) and a second
  pointer to the new reference file below. Keep the existing gate
  (bundled-code-genuineness check, requirements check, just-in-time
  offering discipline) unchanged in substance -- only the fallback
  ordering and the new pointer are additions.

- [ ] **Step 2: Create `references/visual-companion-artifact.md`**

  Mirror `references/visual-companion.md`'s own Table-of-contents-then-
  sections structure. Cover, per the design doc's Decisions 1-3 and the
  ACM row citations above: the detection method (tool-presence check,
  explicit prohibition on probing the two unconfirmed env vars or
  `window.claude`) plus the runtime-failure one-time-downgrade rule; the
  publish/read cycle (`Artifact({action:"publish"})` per screen,
  `Artifact({action:"read", url})` next turn, the no-full-`innerHTML`-
  replacement-on-iteration rule, conflict-is-routine handling); the
  four-row security-model parity table (verbatim from the design doc's
  Decision 3); and a URL-sharing caution note mirroring the Node.js
  path's own `--host 0.0.0.0` exposure-widening caution.

- [ ] **Step 3: Verify untouched files**

  `git diff` must show zero changes to
  `skills/eliciting-a-design/references/visual-companion.md`,
  `scripts/server.cjs`, `scripts/start-server.sh`, `scripts/helper.js`,
  `scripts/frame-template.html`.

### Task 2 (conditional): eval fixture for the widened dispatch, if the coverage gate requires one

**Files:**
- Possibly create/edit: `evals/eliciting-a-design/tasks/*.yaml`
- Possibly edit: `evals/eliciting-a-design/eval-status.md` (or its
  regeneration script's output, if one exists)

**Interfaces:**
- Consumes: Task 1's own actual `SKILL.md` text (the exact
  dispatch-branch wording it produced).
- Produces: nothing consumed elsewhere in this plan.

- [ ] **Step 1: Run the coverage gate**

  `python3 .github/scripts/gitapex_gate_skill_branch_fixture_coverage.py`
  (or the calling repository's equivalent invocation) against Task 1's
  actual diff. Only dispatched if this reports a shortfall.

- [ ] **Step 2: Add the matching fixture(s)**

  One fixture per newly-countable Stop-boundary bullet or named dispatch
  branch the gate identifies, exercising that specific branch.

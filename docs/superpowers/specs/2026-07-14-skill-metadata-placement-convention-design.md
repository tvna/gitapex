# Skill metadata placement convention

## Problem

Skill-authoring metadata (Portability level, and any recorded Mechanism-fit
/ design-rationale decision) is currently front-loaded in SKILL.md bodies as
multi-sentence blocks (3-6 lines each; untrusted-input-triage carries a
~12-line "Mechanism decision" block before its actual procedure begins).

Both kinds of metadata are **reviewer / maintainer / vendor-facing**, not
**executor-facing**: the executing agent reads the body on every invocation
(hot path) to learn *what to do*, while a reviewer reads the provenance /
design rationale rarely (at review or vendor time). Front-loading rationale
makes every execution wade through review-time prose before reaching the
procedure.

The two kinds also differ from each other:

- **Portability** has genuine up-front value to the executor: a terse
  "Repository-scoped: depends on X" line doubles as a precondition/caveat.
  So a one-line declaration near the top is correct.
- **Mechanism-fit / design rationale** has no executor value. It answers
  "why does this exist as a skill" — a reviewer-only question. It should not
  be front-loaded.

## Goals

- A single, consistent convention for where portability and design-rationale
  metadata live in a SKILL.md.
- Keep the executor's reading path lean: procedure reachable right after a
  one-line portability declaration.
- Prevent drift deterministically (a shape-checker gate), per CLAUDE.md
  section 3 ("ship the drift gate in the same change as the invariant").

## Non-goals

- Moving metadata out of the skill folder (portability/mechanism are
  properties of the skill and must travel with it when vendored — footer of
  the same SKILL.md, never `docs/`).
- Rewriting the substance of any skill's procedure.

## The convention

1. **Portability — terse one-line declaration, first body line after the
   H1 title.** Format:

   ```
   **Portability: <Portable | Repository-scoped | Mixed>.** <one clause
   naming the dependency or the reason>.
   ```

   At most one to two lines. Any longer rationale moves to the footer Notes
   section (below). Every skill declares its level explicitly — including
   `Portable` ones — so "undeclared" is unambiguously a defect, not a
   "portable so omitted" judgment call.

2. **Design rationale — a `## Notes` section at the END of the SKILL.md**,
   after the procedure and stop boundaries. This is where a recorded
   Mechanism-fit decision (e.g. untrusted-input-triage's "keep, re-scoped"
   rationale) and any extended portability reasoning live. The executor
   reads top-down and naturally skips it; the reviewer finds it by reading
   the whole file.

3. The procedure/task content occupies the middle. The executor reaches it
   immediately after the one-line portability declaration.

### Rationale destination: same-file footer, not `references/`

The `evaluating-skill-quality` rubric requires portability to be "checkable
from this file alone ... no need to open `references/` just to classify it."
Moving rationale into `references/` would break that principle. A footer
section keeps everything in one file and preserves it.

## Rubric changes (evaluating-skill-quality)

- **Portability level section:** replace "declared ... near the top of
  SKILL.md" with the precise convention: "declared as a terse one-line
  marker as the first body line; any extended rationale in a footer `##
  Notes` section (same file)." Keep "checkable from this file alone."
- **Mechanism fit section:** add that a recorded mechanism-fit decision
  belongs in the footer `## Notes` section, not front-loaded above the
  procedure.
- Check the two worked-example reference files for any "near the top"
  wording that now drifts, and align them.

## Deterministic gate (shape checker)

Add ONE modest floor check to
`skills/evaluating-skill-quality/scripts/check_skill_shape.py`:

- **Check id:** `portability-near-top`.
- **Rule:** a portability marker line must appear within the first `K` lines
  of the SKILL.md body (body = content after the closing frontmatter `---`).
  Marker = a line matching (case-insensitive) `portability` immediately
  followed by a colon, optionally wrapped in `**` bold, e.g.
  `**Portability: Repository-scoped.**` or `Portability: Portable`.
- **K:** 6 body lines (H1 title + a blank + the declaration leaves slack;
  6 still fails a declaration buried dozens of lines down).
- **Scope of the check:** the floor only. It enforces *presence near the
  top* (catches "undeclared" and "declared-but-buried/drifted"). It does
  NOT try to mechanically enforce "terse" or "no rationale front-loaded" —
  that ceiling stays a rubric judgment call, because "is this prose
  rationale?" is not reliably decidable by regex.
- Add tests to
  `skills/evaluating-skill-quality/scripts/test_check_skill_shape.py`:
  a PASS case (marker at body line 3), a FAIL case (no marker), a FAIL case
  (marker buried past line 6), and a PASS case for the bold form.

### Consequence: portability declaration becomes mandatory

The floor check requires the marker in every skill. Three skills currently
have no portability line — `driving-pr-to-merge`, `merge-retrospective`,
`stop-and-replan` — and must gain one. This is intended: explicit over
implicit, and it removes the "undeclared because portable vs. undeclared
because forgotten" ambiguity the rubric otherwise resolves only by judgment.

## Work surface

- **9 skills** with a 3-6 line portability block at top: trim to the
  one-line declaration; relocate the surplus rationale to a `## Notes`
  footer (only where the rationale is worth keeping — much of it is
  self-justifying prose that can simply be cut, honoring net-line
  discipline).
- **untrusted-input-triage:** additionally move its ~12-line "Mechanism
  decision" block from the top to the `## Notes` footer.
- **3 skills** with no portability line (`driving-pr-to-merge`,
  `merge-retrospective`, `stop-and-replan`): add the one-line declaration
  (classify each first — read the actual content).
- **evaluating-skill-quality:** it both defines and must follow the
  convention — add its own top declaration, update the rubric Portability +
  Mechanism-fit wording, align worked-example files, and add the shape
  check + tests to its bundled script.
- Re-run the shape checker on all 12 skills; all must PASS the new check.

## Ordering constraint

The shape-checker `portability-near-top` check will FAIL any skill that
doesn't yet conform. So: conform all 12 skills first, then add the check
(and its tests) last — or add the check and fix all skills in the same
change — so the suite is never left red. The plan sequences skill edits
before the checker change.

## Net-line discipline

This is a relocation + trim, not an addition. Deletions (trimmed portability
prose) should roughly offset additions (footer Notes + 3 new one-liners +
the checker rule). A net increase earns an explicit justification per
CLAUDE.md section 5.

## Verification

- `check_skill_shape.py` PASS on all 12 skills (including the new check).
- `pytest` green (new checker tests included).
- Manual read: each skill's first body line is its portability declaration;
  each relocated rationale reads coherently in its footer.

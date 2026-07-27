---
name: auditing-agent-product-scope
description: Use when evaluating which agent tools, git-hosting platforms, or dependency middleware a repository assumes or targets, and updating that repository's own scope-definition doc to match. Formalizes a research-classify-document procedure -- fetch a candidate's primary documentation directly, classify it against the owning evidence file's existing evidence states, add a finding to the axis's owning evidence file, and update the scope map's cross-references. Distinct from `evaluating-skill-quality` (grades a target skill's own quality) and `git-hosting-surface-audit` (audits one target repository's hosting-platform configuration surface, not which platforms this repository itself assumes).
---

# Auditing Agent Product Scope

The research-classify-document procedure below is portable to any
repository that wants to formally track which agent tools, git-hosting
platforms, and dependency middleware it assumes. The specific scope
map this procedure maintains, its axes, and the specific files/issues
each axis cites are repository-specific. If this copy of the skill's
own files lives in the gitapex repository, load
`references/gitapex-cross-links.md` now -- Steps 1-2 and 5-7 below cite
it for the specifics. A copy vendored into a different repository
drops that file and instead uses that repository's own equivalent
scope doc (or creates one, mirroring this skill's own axis shape) and
its own owning issues/files, never gitapex's.

## Steps

1. **Classify the candidate against your repository's own scope-map
   axes.** Is it an agent tool/runtime, a git-hosting platform, or a
   dependency/middleware? (`references/gitapex-cross-links.md` names
   gitapex's own six axes and what each governs.) If it could
   plausibly fit more than one axis, or none, STOP and ask -- never
   guess which axis owns a candidate.
2. **Route platform candidates to the platform-auditing skill instead
   of auditing them here.** If Step 1 resolves to the git-hosting
   platform axis, do not research or write a new platform finding as
   part of this skill's own procedure -- hand off to the repository's
   dedicated platform-auditing skill (`references/gitapex-cross-links.md`
   names it for gitapex), and only update that axis's "current scope"
   line in the scope map if the platform skill's own tracking issue
   states a materially different scope than what the axis currently
   says. This skill never re-implements that skill's checklists.
3. **For an agent-tool or middleware candidate, fetch its primary
   documentation directly.** A vendor's official docs, or (for a
   middleware candidate) the repository's own dependency-declaring
   files -- never a secondary summary, blog post, or memory. If the
   primary source cannot be reached (network policy, paywall, 404),
   report the specific blocker rather than filling the gap from
   memory.
4. **Classify the finding using the owning evidence file's existing
   evidence states.** Read that file's own classification-states
   section (it already defines what each state means and requires) and
   apply it -- do not restate or re-derive the definitions here; a
   second copy drifts from the original the moment either one is
   edited.
5. **Add the finding to the axis's owning evidence file, not this
   skill's own files.** An agent-tool finding goes to a sibling skill's
   evidence file -- this skill only knows where it lives, it does not
   own it (`references/gitapex-cross-links.md` names it for gitapex). A
   middleware finding goes to this skill's own
   `references/middleware-inventory.md`. Either way, cite the exact
   primary source URL or repository file path fetched in Step 3.
6. **Update the scope map's relevant axis section** (current scope,
   and the owning issue/doc if a new one now applies) and add one
   provenance bullet to the touched evidence file's own sidecar
   metadata, matching whatever citation convention that file already
   establishes (issue number, date, what changed, primary source). Do
   not silently resolve a contradiction this candidate surfaces between
   two axes, or between an axis and its own owning doc -- name it in
   the axis section and leave the underlying decision to the
   repository owner (`references/gitapex-cross-links.md` has a worked
   example of this from gitapex's own history).
7. **Run the shape checks before committing:** this repository's own
   skill-shape checker against any skill whose files changed
   (`references/gitapex-cross-links.md` names gitapex's own command),
   and this skill's own axis-shape checker:
   `python3 scripts/check_axis_shape.py <path-to-your-scope-map>`.

## Output

- **Candidate classification:** which axis the candidate belongs to,
  or the Step 1 Human Decision if none fit cleanly.
- **Primary source(s) fetched:** the exact URL(s) or repository
  file(s), with fetch date.
- **Classification:** the owning evidence file's own evidence state,
  with the deciding quote or observed fact.
- **Files changed:** the owning evidence file (row/entry added), the
  scope-map axis section, and the provenance bullet.
- **Verification:** the skill-shape and axis-shape check results.
- **Next Move:** commit citing the driving issue, or (if Step 1's
  ambiguity or Step 6's contradiction applies) the specific question
  for the repository owner.

## Stop boundaries

- Never write a platform finding directly -- route to the
  platform-auditing skill (Step 2).
- Never classify a candidate from memory when its primary source could
  not be reached -- report the blocker instead (Step 3).
- Never restate or re-derive the owning evidence file's classification
  definitions -- read them at the source (Step 4).
- Never silently resolve a contradiction between axes, or between an
  axis and its own owning doc, that this candidate's research surfaces
  -- name it and leave the decision to the repository owner (Step 6).
- Never assert a Documented (or equivalent) classification without a
  fetched primary source backing it.
- Never merge or enable auto-merge as part of this skill's own
  procedure -- that stays a separate, explicit human or CI decision.

## Related skills

- **vs. `evaluating-skill-quality`:** that skill grades a *target*
  skill's own `SKILL.md` quality (including a warning-only
  compatibility-awareness axis that reads, but does not itself
  maintain, its own evidence baseline). This skill is the one that
  actually adds or refreshes rows in that same file, plus maintains
  the cross-axis scope map those rows feed into.
- **vs. `git-hosting-surface-audit`:** that skill audits one target
  repository's hosting-platform *configuration* surface (branch
  protection, required checks, and similar). This skill never
  re-implements that -- the platform axis's candidates are handed off
  to it (Step 2).

## Notes

Portability: declared `Mixed`. The Steps/Output/Stop-boundaries
procedure above is general; `references/gitapex-cross-links.md`
isolates every gitapex-specific detail (the scope map's path and axis
list, sibling evidence-file paths, tracking issue numbers, the
skill-shape-checker invocation) into one file, mirroring
`git-hosting-surface-audit/references/gitapex-cross-links.md`'s own
pattern -- a vendored copy drops that one file rather than hand-editing
every section.

Known limitation, not yet addressed: this Procedure defines how to
research and record a *new* candidate (Step 3 onward), but nothing in
it prompts revisiting an *already-recorded* finding when its cited
primary source later changes (for example, a pinned middleware version
bumping, or a vendor doc revising documented behavior). Re-auditing
already-recorded findings for staleness is a distinct, larger follow-up
this skill does not attempt.

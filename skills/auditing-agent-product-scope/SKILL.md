---
name: auditing-agent-product-scope
description: Use when evaluating which agent tools, git-hosting platforms, or dependency middleware a repository assumes or targets, and updating that repository's own scope-definition doc to match. Formalizes a research-classify-document procedure -- fetch a candidate's primary documentation directly, classify it Documented/Unknown/Conflict, add a finding to the axis's owning evidence file, and update the scope map's cross-references. In gitapex, this maintains `docs/agent-product-scope.md` and its six axes (agent-tool, enforcement-adapter, skill-quality evidence, hook-quality evidence, git-hosting platform, dependency middleware). Distinct from `evaluating-skill-quality` (grades a target skill's own quality) and `git-hosting-surface-audit` (audits one target repository's hosting-platform configuration surface, not which platforms this repository itself assumes).
---

# Auditing Agent Product Scope

The research-classify-document procedure below is portable to any
repository that wants to formally track which agent tools, git-hosting
platforms, and dependency middleware it assumes. The specific scope map
this procedure maintains -- `docs/agent-product-scope.md`, its six axes,
and the specific files/issues each axis cites -- is gitapex's own. A
copy vendored into a different repository substitutes that repository's
own equivalent scope doc (or creates one, mirroring this skill's own
Axis shape) and its own owning issues/files, never gitapex's.

## Steps

1. **Classify the candidate.** Is it an agent tool/runtime (Axis A-D:
   plugin-distribution target, enforcement-adapter target set,
   skill-quality-review evidence baseline, hook-quality evidence
   baseline), a git-hosting platform (Axis E), or a dependency/
   middleware (Axis F)? If it could plausibly be more than one, or
   none, STOP and ask -- never guess which axis owns a candidate.
2. **Route platform candidates to the existing skill instead of
   auditing them here.** If Step 1 resolves to Axis E, do not research
   or write a new platform finding as part of this skill's own
   procedure -- hand off to `git-hosting-surface-audit`, and only
   update Axis E's "current scope" line in `docs/agent-product-scope.md`
   if that skill's own tracking issue,
   [gitapex#82](https://github.com/tvna/gitapex/issues/82), states a
   materially different scope than what Axis E currently says. This
   skill never re-implements that skill's checklists.
3. **For an agent-tool or middleware candidate, fetch its primary
   documentation directly.** A vendor's official docs, or (for a
   middleware candidate) the repository's own dependency-declaring file
   itself (`flake.nix`, `apm.yml`/`apm.lock.yaml`, `pyproject.toml`/
   `uv.lock`) -- never a secondary summary, blog post, or memory. If
   the primary source cannot be reached (network policy, paywall,
   404), report the specific blocker rather than filling the gap from
   memory.
4. **Classify Documented / Unknown / Conflict**, using the same
   three-state scheme
   `skills/evaluating-skill-quality/references/runtime-compatibility.md`
   already defines: Documented (the linked primary source states the
   behavior), Unknown (the source doesn't establish it -- absence is
   not evidence of rejection), Conflict (two documented sources assign
   materially different semantics to the same construct).
5. **Add the finding to the axis's owning evidence file, not this
   skill's own files.** An agent-tool finding goes to
   `skills/evaluating-skill-quality/references/runtime-compatibility.md`
   (a sibling skill's file -- this skill only knows where it lives, it
   does not own it). A middleware finding goes to this skill's own
   `references/middleware-inventory.md`. Either way, cite the exact
   primary source URL or repository file path fetched in Step 3.
6. **Update `docs/agent-product-scope.md`'s relevant axis section**
   (current scope, and the owning issue/doc if a new one now applies)
   and add one provenance bullet to the touched evidence file's own
   `metadata/gitapex.yaml`, matching the citation convention already
   established there (issue number, date, what changed, primary
   source). Do not silently resolve a contradiction this candidate
   surfaces between two axes, or between an axis and its own owning
   doc (for example, the Axis A Claude-Code-vs-Codex inconsistency
   [PR #447](https://github.com/tvna/gitapex/pull/447)'s own review
   found) -- name it in the axis section, the same way that finding
   was handled, and leave the underlying decision to the repository
   owner.
7. **Run the shape checks before committing:**
   `python3 skills/evaluating-skill-quality/scripts/check_skill_shape.py <touched-skill-dir>`
   for any skill whose files changed, and
   `python3 skills/auditing-agent-product-scope/scripts/check_axis_shape.py docs/agent-product-scope.md`
   to confirm every axis section still carries its four required
   fields.

## Output

- **Candidate classification:** which axis (A-F) the candidate belongs
  to, or the Step 1 Human Decision if none fit cleanly.
- **Primary source(s) fetched:** the exact URL(s) or repository
  file(s), with fetch date.
- **Classification:** Documented / Unknown / Conflict, with the
  deciding quote or observed fact.
- **Files changed:** the owning evidence file (row/entry added), the
  scope-map axis section, and the provenance bullet.
- **Verification:** `check_skill_shape.py` and `check_axis_shape.py`
  results.
- **Next Move:** commit citing the driving issue, or (if Step 1's
  ambiguity or Step 6's contradiction applies) the specific question
  for the repository owner.

## Stop boundaries

- Never write a platform finding directly -- route to
  `git-hosting-surface-audit` (Step 2).
- Never classify a candidate from memory when its primary source could
  not be reached -- report the blocker instead (Step 3).
- Never silently resolve a contradiction between axes, or between an
  axis and its own owning doc, that this candidate's research surfaces
  -- name it and leave the decision to the repository owner (Step 6).
- Never assert a Documented classification without a fetched primary
  source backing it.
- Never merge or enable auto-merge as part of this skill's own
  procedure -- that stays a separate, explicit human or CI decision.

## Related skills

- **vs. `evaluating-skill-quality`:** that skill grades a *target*
  skill's own `SKILL.md` quality (including a warning-only
  compatibility-awareness axis that reads, but does not itself
  maintain, `runtime-compatibility.md`). This skill is the one that
  actually adds or refreshes rows in that same file, plus maintains
  the cross-axis scope map those rows feed into.
- **vs. `git-hosting-surface-audit`:** that skill audits one target
  repository's hosting-platform *configuration* surface (branch
  protection, required checks, and similar). This skill never
  re-implements that -- Axis E candidates are handed off to it
  (Step 2).

## Notes

Portability: the Steps/Output/Stop-boundaries procedure above is
general -- the specific files it reads and writes
(`docs/agent-product-scope.md`, `evaluating-skill-quality`'s baseline,
this skill's own `references/middleware-inventory.md`) are gitapex's
own. A vendored copy substitutes that repository's own equivalents.

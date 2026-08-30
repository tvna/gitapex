## Review conducted directly, not via subagent dispatch

Per your explicit instruction I ran this synchronously in this response rather than opening the fresh subagent dispatch `SKILL.md`'s own "Subagent dispatch" section normally requires for isolation-for-neutrality. That's a real, disclosable deviation from the skill's own procedure (the point of the dispatch is exactly to grade from a context that hasn't already seen the target) — flagging it per the skill's own Stop-boundary discipline rather than silently proceeding as if nothing changed.

## Precondition (steps 1/3/4)

- **Step 1 (read target):** the excerpt was read in full; it's a 4-sentence fragment of `references/handoff.md`, not a whole skill directory, so the deterministic shape checker (step 3) has nothing to run against — no `SKILL.md` frontmatter, no directory to point it at. Per your framing, I'm treating shape and the rest of `references/` as already clean and scoping this review to the excerpt's own content only.
- **Portability level (step 4):** no sidecar given. Reading content: nothing in the excerpt depends on `release-captain`'s own repo tooling — it reads as intended to be a general, portable release procedure. I'm treating it as **Portable** absent a stated declaration; that's the strictest lens, and it's the correct one to apply the litmus test below.
- **Mechanism fit / cohesion (step 2):** no whole-artifact finding — a handoff step inside a release procedure is squarely in-scope for a skill, and this is a single procedural branch, not a cohesion problem.
- **Blind spot pass:** no rubric gap found for this domain — this is squarely dimension 4/6 territory, already covered.

## Dimension walk (evidence-cited)

**Dimension 4 — Clarity and structure: does not clear (gap-major).**
The operative clause is:

> "hand off to the `notifying-stakeholders` skill -- retired since, commit 7c7ca82 -- to post the announcement"

The grammatical instruction a reader (or a model executing this procedure) follows is *hand off to `notifying-stakeholders`* — the "retired" aside is parenthetical, not a rewrite of the instruction. The very next sentence confirms this skill "no longer exists under its old name." So the step's own actionable clause routes to a target the file itself says is unreachable. This fails dimension 4's branch-completeness check directly: "flag ... an input state that matches none or several" — here the named handoff target matches *no* real skill. The real, current target (`announcing-releases`) appears only in explanatory prose, never in the operative instruction itself.

**Dimension 6 — Durability: does not clear (gap-major).** This is the headline finding.
Two distinct durability defects, both in the same clause:

1. **Stale live instruction, not marked as historical.** This is structurally the rubric's own worked failure example: *"'before August 2025 use the old API' stated as current guidance with no explicit historical marking."* Here the outdated instruction ("hand off to `notifying-stakeholders`") is still phrased as the thing to do, with the correction relegated to a trailing explanation rather than replacing the instruction itself.
2. **Repo-bound commit-hash citation as evidence.** `commit 7c7ca82` is a short git SHA — unreachable once history is rewritten, rebased, or GC'd, and meaningless to a reader without repo archaeology, let alone in a copy of this skill vendored elsewhere. This is the same failure shape the Portability litmus test names by its own example, *"this repository's tests currently number 214"* — an unconditional declarative fact-claim tied to this specific repository's state that would not "remain true, unchanged, if this file were copied into a repository carrying none of the origin repo's state." (I'm calling this a reasoned extension of that named example, not the literal bare-issue/PR-number rule, since a commit SHA isn't auto-linked the way `#149` is — the underlying fragility is the same class of defect, not the identical enforced rule.)

**Dimension 2 — Conciseness: minor gap (sediment).** The commit hash is also, independently, exactly the rubric's "historical rationale that no longer controls behavior" (sediment) — it carries no operational value once the real fix is to just say where the step now routes. Same underlying text, different question (cost vs. correctness), so both dimensions legitimately flag it without double-counting under Contract discipline's "never both."

**Dimensions 1, 3, 5, 7:** not meaningfully exercised by a 4-sentence handoff fragment; treated as clear per your stated assumption that the rest of the skill passes cleanly.

**Dimensions 8–9:** unmeasured — no eval/baseline data available for this excerpt. Qualitative read: this defect is a factual/referential bug, not a prescription-level mismatch, so it would likely mislead any model tier equally rather than being tier-sensitive.

## Verdict

**WELL-FORMED-NOT-MATURE** (at the whole-skill level, on your stated assumption that the rest of the skill is shape-clean) — dimension 6 and dimension 4 both fail to clear, which alone blocks "Mature" regardless of how the rest of the skill scores.

**Concrete fix:** rewrite the operative sentence so the actionable target is the real one —

> "After tagging the release, hand off to the `announcing-releases` skill (formerly `notifying-stakeholders`) to post the announcement."

Drop the specific commit hash; if provenance is worth keeping at all, it belongs in a changelog/decision-log outside the skill's own procedure text, not as load-bearing prose inside it.

```json
{
  "schemaVersion": "1.0.0",
  "reviewMeta": {
    "actor": { "ref": "evaluating-skill-quality, applied in-thread per explicit no-dispatch instruction", "provenance": "asserted" },
    "targetRepoRef": "N/A — inline draft excerpt, not a versioned repository path",
    "skillBuildRef": "N/A — excerpt only; rest of skill assumed clean per task framing"
  },
  "shapeCheck": {
    "checkerRef": "not run — excerpt has no SKILL.md/frontmatter to check; scope is references/handoff.md content only",
    "checks": []
  },
  "mechanismFit": {
    "wrongMechanism": { "finding": false },
    "cohesion": { "dominantType": "sequential", "splitRecommended": false, "reason": "single handoff step within an assumed-cohesive release procedure" },
    "blindSpotPass": { "gapFound": false, "description": "no rubric blind spot found for this domain" }
  },
  "portabilityLevel": "Portable",
  "dimensions": [
    { "dimensionId": 1, "verdict": "clear", "evidence": [{ "quote": "assumed clear per stated precondition; excerpt is a references/ body fragment, not name/description", "sourceRef": "task framing" }] },
    { "dimensionId": 2, "verdict": "gap-minor", "evidence": [{ "quote": "retired since, commit 7c7ca82", "sourceRef": "references/handoff.md excerpt" }] },
    { "dimensionId": 3, "verdict": "clear", "evidence": [{ "quote": "single directive, no fragile multi-step sequence in this excerpt", "sourceRef": "references/handoff.md excerpt" }] },
    { "dimensionId": 4, "verdict": "gap-major", "evidence": [{ "quote": "hand off to the `notifying-stakeholders` skill -- retired since, commit 7c7ca82 -- to post the announcement", "sourceRef": "references/handoff.md excerpt" }] },
    { "dimensionId": 5, "verdict": "clear", "evidence": [{ "quote": "assumed clear per stated precondition; no reference-splitting question raised by this fragment", "sourceRef": "task framing" }] },
    { "dimensionId": 6, "verdict": "gap-major", "evidence": [{ "quote": "That skill was folded into `announcing-releases` and no longer exists under its old name; this file still names it", "sourceRef": "references/handoff.md excerpt" }] },
    { "dimensionId": 7, "verdict": "clear", "evidence": [{ "quote": "no bundled scripts present in this excerpt", "sourceRef": "references/handoff.md excerpt" }] },
    { "dimensionId": 8, "verdict": "unmeasured", "evidence": [] },
    { "dimensionId": 9, "verdict": "unmeasured", "evidence": [] }
  ],
  "verdict": {
    "token": "WELL-FORMED-NOT-MATURE",
    "reason": "Dimension 4 and dimension 6 fail to clear: the handoff step's operative instruction names a skill the same file admits no longer exists, and cites a repo-bound commit hash as durability-relevant evidence."
  }
}
```
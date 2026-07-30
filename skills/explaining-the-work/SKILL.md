---
name: explaining-the-work
description: Use when writing or editing code comments, docstrings, or finalizing commit/PR messages. Routes explanation responsibility (How/What/Why/Why-not) to the right artifact instead of piling it into comments.
---

# Explaining the Work

This skill's routing principle is portable; the ADR path and
commit-trailer conventions below are this repository's own.

Explanation responsibility is split by artifact. Route each piece of
explanation to exactly one place — never duplicate it, never let it drift
into the wrong artifact.

## Routing

- **Code body -> How only** (naming/structure). Never restate what the code
  already says.
- **Test code -> What**, expressed through the test name. Use a docstring
  only when the test name itself cannot carry an issue reference.
- **Commit log -> a terse Why, not the full Why.** Per git-community
  consensus ([beams]; [kerneldoc]; [progit]) the commit body is a
  permanent record that outlives the discussion that produced it, so it
  must carry enough Why for a reader who has "long since forgotten the
  immediate details of the discussion." A commit is a subject line, a
  short Why (what problem this solves and why this approach -- one to a
  few sentences, not a design essay), and an issue pointer -- `Closes #N`
  when the change fully satisfies #N's acceptance criteria, `Refs #N`
  when it only partially addresses or relates to it -- with any
  repo-mandated trailers (e.g. `Co-Authored-By`) excepted. The fuller
  Why, tagged Fact (verified/observed) or Speculation (unverified) rather
  than blended, still lives in the issue/PR body; the commit's Why is a
  terse pointer to it, never a duplicate design writeup.
- **Code comments -> Why-not / durable constraints only**, one-line form:

  ```
  # why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]
  ```

  Requires a citable issue/PR/ADR that actually evaluated the rejected
  alternative. If nothing can be cited, do not write the comment — never
  fabricate a rationale. The mechanical part (line length, the
  `why-not(#NNN):` prefix, the optional ADR path form) is a good fit for a
  small lint-hook or pre-commit check where the repo has one; keep the
  judgment call (is a rejected alternative actually citable) in-model.

## Precedence

The calling repository's existing deterministic gates (`Contract:` blocks,
allowlist justification comments, `noqa` justification, etc.) take
precedence over this skill. Do not enumerate exceptions to those gates here.

## Stop boundaries

- Forward-apply only. Never bulk-rewrite existing comments to match this
  policy.
- Deletion of a why-not comment is justified only by the guarded code
  actually having been removed — never by staleness alone.
- Never auto-generate an ADR from a threshold or metric. ADRs are
  heavyweight, owner-approved records; machine-generating them produces
  "drive-by ADRs".

## Notes

Portability: the why-not comment's `docs/adr/NNNN-*.md` path and the
"commit + `Closes #N`/`Refs #N`" convention are this repository's own
conventions; adapt the literal path/trailer form to whatever issue and
ADR conventions the calling repository actually uses.

## References

- **[beams]** Chris Beams -- How to Write a Git Commit Message.
  <https://cbea.ms/git-commit/>
- **[kerneldoc]** The Linux Kernel documentation -- Submitting patches.
  <https://www.kernel.org/doc/html/latest/process/submitting-patches.html>
- **[progit]** Scott Chacon and Ben Straub -- Pro Git, Distributed Git --
  Contributing to a Project.
  <https://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project>

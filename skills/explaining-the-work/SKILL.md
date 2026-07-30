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
- **Commit log -> a terse Why, not the full Why.** Per [kerneldoc], the
  explanation "will be committed to the permanent source changelog, so
  should make sense to a competent reader who has long since forgotten
  the immediate details of the discussion that might have led to this
  patch" -- this permanent-record, forgetful-reader framing is
  [kerneldoc]'s alone. [beams] and [progit] agree only that the body
  should explain the change's motivation (what and why, not how;
  contrast with previous behavior), and both wrap the body at 72
  characters, distinct from [kerneldoc]'s own 75-column convention;
  none of the three gives a sentence- or word-count rule for how long
  the Why itself should be. A commit is a subject line, a Why sized to
  what that reader needs to grasp the reasoning -- not a fixed count,
  not a duplicate of the fuller design essay -- and an issue pointer --
  `Closes #N` when the change fully satisfies #N's acceptance criteria,
  `Refs #N` when it only partially addresses or relates to it -- with
  any repo-mandated trailers (e.g. `Co-Authored-By`) excepted. The
  fuller design essay -- alternatives considered, dead ends, the
  discussion's back-and-forth -- stays in the issue/PR body, tagged
  Fact (verified/observed) or Speculation (unverified) rather than
  blended; the commit's Why is self-contained for a reader who cannot
  see that body, never a duplicate of the design essay.
- **Code comments -> Why-not / durable constraints only**, one-line form:

  ```
  # why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]
  ```

  Requires a citable issue/PR/ADR that actually evaluated the rejected
  alternative. If nothing can be cited, do not write the comment — never
  fabricate a rationale. This citable-evidence requirement is this
  repository's own policy choice, stricter than general software-
  engineering practice: no primary source checked (Google's C++ style
  guide, Ousterhout's *A Philosophy of Software Design*, Robert C.
  Martin's *Clean Code*, the Linux kernel's own coding-style guidance)
  restricts a good comment to why-not-for-a-rejected-alternative or
  requires a citation to license one -- all of them sanction broader Why
  (and sometimes tricky How) with no such gate. The mechanical part (line
  length, the `why-not(#NNN):` prefix, the optional ADR path form) is a
  good fit for a small lint-hook or pre-commit check where the repo has
  one; keep the judgment call (is a rejected alternative actually
  citable) in-model.

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

No primary source checked for this skill -- [beams], [kerneldoc],
[progit], Google's C++ style guide, Ousterhout, or Clean Code -- gives a
quantitative or measurable threshold for when a comment is necessary or
how long one may be; every source's own guidance is qualitative
("obvious," "tricky," "non-obvious"). This silence is itself the honest
finding, the same shape as `drafting-an-adr`'s own disclosed absence of
a numeric ADR-significance threshold -- not a gap in this search.

## References

- **[beams]** Chris Beams -- How to Write a Git Commit Message.
  <https://cbea.ms/git-commit/>
- **[kerneldoc]** The Linux Kernel documentation -- Submitting patches.
  <https://www.kernel.org/doc/html/latest/process/submitting-patches.html>
- **[progit]** Scott Chacon and Ben Straub -- Pro Git, Distributed Git --
  Contributing to a Project.
  <https://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project>

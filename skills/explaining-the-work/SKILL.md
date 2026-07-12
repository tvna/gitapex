---
name: explaining-the-work
description: Use when writing or editing code comments, docstrings, or finalizing commit/PR messages. Routes explanation responsibility (How/What/Why/Why-not) to the right artifact instead of piling it into comments.
---

# Explaining the Work

Explanation responsibility is split by artifact. Route each piece of
explanation to exactly one place — never duplicate it, never let it drift
into the wrong artifact.

## Routing

- **Code body -> How only** (naming/structure). Never restate what the code
  already says.
- **Test code -> What**, expressed through the test name. Use a docstring
  only when the test name itself cannot carry an issue reference.
- **Commit log -> not the place for Why.** The real Why lives in the
  issue/PR body (Facts/Speculation split). A commit is one line plus a
  `Refs #N` pointer — nothing more.
- **Code comments -> Why-not / durable constraints only**, one-line form:

  ```
  # why-not(#NNN): <=120 chars [-> docs/adr/NNNN-*.md]
  ```

  Requires a citable issue/PR/ADR that actually evaluated the rejected
  alternative. If nothing can be cited, do not write the comment — never
  fabricate a rationale.

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

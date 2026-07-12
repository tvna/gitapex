---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers and non-ASCII content, pending a real deterministic preflight/CI gate.
---

# Outward Artifact Preflight

This is an interim measure. CLAUDE.md chapter 3 requires a deterministic
preflight or CI gate for both checks below; gitapex has not built one yet
(see the Non-goals in
`docs/superpowers/specs/2026-07-12-skill-distribution-foundation-design.md`).
Until that gate exists, run this checklist by hand before every push or
post. Retire or narrow this skill the day the real gate lands -- it does
not substitute for one, and never present it as the permanent solution.

## Checklist

Run both checks on the exact text about to be pushed or posted: a commit
message, PR/issue body, release notes, or any generated file destined for
a public sink.

1. **Undisclosed provenance markers.** Scan for anything identifying the
   build/runtime model, agent, or session that produced the artifact, and
   any internal tooling fingerprint, that the owner has not chosen to
   disclose. In this repository the "Generated with Claude Code" trailer
   (see PR #2's body) is the disclosed convention -- keep it where it
   already appears. A bare model identifier (e.g. a `claude-*` model ID),
   a session URL, or an internal tool name is not disclosed and must be
   removed.
2. **ASCII-only.** No em dashes, en dashes, curly quotes, full-width
   punctuation, or any other non-ASCII character. Check with:

   ```bash
   LC_ALL=C grep -n '[^ -~]' <file>
   ```

   No output means the file is ASCII-only.

## Worked example

Flagged commit message (fails both checks). This file is itself ASCII-only,
so the one character that must fail check 2 is spelled out as `[U+2014]`
below instead of pasted literally -- a real flagged artifact would contain
that em dash as a literal character, not this bracketed placeholder:

```
feat(plugin): add outward-artifact-preflight skill [U+2014] built by
claude-sonnet-5 during session https://claude.ai/code/session_01Abc23dEf

Refs #8
```

Applying the checklist:

- `LC_ALL=C grep -n '[^ -~]' <file>` reports the em dash at `[U+2014]` --
  fails check 2.
- `claude-sonnet-5` and the session URL are an undisclosed provenance
  marker, not the repository's disclosed "Generated with Claude Code"
  convention -- fails check 1.

Fixed:

```
feat(plugin): add outward-artifact-preflight skill

Refs #8
```

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.

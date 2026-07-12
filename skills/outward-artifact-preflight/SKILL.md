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
   (see PR #2's body) is the disclosed convention for PR bodies -- keep
   the disclosure there. This check is independent of check 2, though:
   PR #2's own trailer contains a non-ASCII robot emoji, so keeping it
   disclosed still means replacing any non-ASCII glyph in it with an
   ASCII equivalent, same as anywhere else in the artifact. Commit
   messages follow a separate, narrower rule (skills/explaining-the-work
   routes commit-log content to one line plus a `Refs #N` pointer,
   nothing more) -- do not add this trailer to a commit message just
   because it is disclosed in PR bodies. A bare model identifier (e.g. a
   `claude-*` model ID), a session URL, or an internal tool name is not
   disclosed and must be removed regardless of artifact type.
2. **ASCII-only.** No em dashes, en dashes, curly quotes, full-width
   punctuation, or any other non-ASCII character. Check with (`-P` enables
   Perl-regex mode so `\t` is read as a tab escape, not two literal
   characters -- a plain bracket expression would still flag ordinary
   tabs):

   ```bash
   LC_ALL=C grep -nP '[^ -~\t]' <file>
   ```

   No output means the file is ASCII-only.

## Worked example

This file must itself stay ASCII-only, so the flagged sample below is built
with `printf`, not a pasted glyph -- run both commands yourself to see the
checklist catch real bytes instead of a description:

```bash
printf 'feat(plugin): add outward-artifact-preflight skill \xe2\x80\x94 built by\nclaude-example-model during session https://claude.ai/code/session_01Abc23dEf\n\nRefs #8\n' > /tmp/flagged-commit-msg.txt
LC_ALL=C grep -nP '[^ -~\t]' /tmp/flagged-commit-msg.txt
```

Applying the checklist:

- Check 2 fires: `grep` prints line 1 (exit status 0) -- the `\xe2\x80\x94`
  bytes (an em dash) are non-ASCII.
- Check 1 fires: `claude-example-model` and the session URL are an undisclosed
  provenance marker, not the repository's disclosed "Generated with Claude
  Code" convention -- keeping neither is required to pass.

Fixed:

```
feat(plugin): add outward-artifact-preflight skill

Refs #8
```

## Relationship to other skills

Finalizing a commit or PR message can trigger both this skill and
skills/explaining-the-work at once -- that is expected, not a conflict.
explaining-the-work routes what the text should say (How/What/Why); this
skill checks whether the text, once written, is safe to publish
(provenance, ASCII). Apply both; neither substitutes for the other.

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.

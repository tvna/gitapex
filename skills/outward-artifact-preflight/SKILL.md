---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers and non-ASCII content, pending a real deterministic preflight/CI gate.
---

# Outward Artifact Preflight

**Portability: Repository-scoped.** The provenance/ASCII checklist and its
grep invocation are general, but "this repository's agreed disclosure
convention" (check 1) and the explaining-the-work coupling (Relationship
to other skills) are this repo's own conventions; substitute the calling
repository's actual disclosure policy and sibling skills where they
differ.

This is an interim measure: a manual stand-in for the deterministic
preflight or CI gate this repository has not built yet. Run this
checklist by hand before every push or post until that gate exists.
Retire or narrow this skill the day the real gate lands -- it does not
substitute for one, and never present it as the permanent solution.

## Checklist

Run both checks on the exact text about to be pushed or posted: a commit
message, PR/issue body, release notes, or any generated file destined for
a public sink.

1. **Undisclosed provenance markers.** Scan for anything identifying the
   build/runtime model, agent, or session that produced the artifact, and
   any internal tooling fingerprint, that the owner has not chosen to
   disclose. Run `python3 scripts/scan_provenance.py --file <file>` first
   to surface mechanical candidates (model IDs, session URLs, generic
   build/agent tags) instead of re-scanning for these patterns in prose
   each time; the script only surfaces candidates, it does not decide
   whether a hit is actually undisclosed.

   1. A bare model identifier (e.g. a `claude-*` model ID), a session
      URL, or an internal tool name is not disclosed and must be
      removed, unless this repository has explicitly agreed to disclose
      it.
   2. If this repository already has an agreed disclosure convention for
      PR bodies (for example a fixed "Generated with X" trailer), keep
      it there.
   3. Disclosure does not exempt something from check 2: a disclosed
      trailer still has to pass the ASCII check, so replace any
      non-ASCII glyph in it (an emoji, for instance) with an ASCII
      equivalent.
   4. Commit messages follow a separate, narrower rule (where installed,
      the explaining-the-work skill routes commit-log content to one
      line plus a `Refs #N` pointer, nothing more) -- do not add a
      PR-body trailer to a commit message just because it is disclosed
      there.
2. **ASCII-only.** No em dashes, en dashes, curly quotes, full-width
   punctuation, or any other non-ASCII character. Check with (`-P` enables
   Perl-regex mode so `\t` is read as a tab escape, not two literal
   characters -- a plain bracket expression would still flag ordinary
   tabs). This requires GNU grep with PCRE support (`grep -P`), which
   BSD/macOS grep lacks:

   ```bash
   LC_ALL=C grep -nP '[^ -~\t]' <file>
   ```

   On a platform without `grep -P` (e.g. stock macOS/BSD grep), use this
   portable equivalent instead:

   ```bash
   LC_ALL=C perl -ne 'print "$.:$_" if /[^ -~\t\n]/' <file>
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
- Check 1 fires: `claude-example-model` and the session URL are a bare
  model identifier and a session URL -- neither is an agreed disclosure
  convention, so both must be removed to pass.

Fixed:

```
feat(plugin): add outward-artifact-preflight skill

Refs #8
```

## Relationship to other skills

Finalizing a commit or PR message can trigger both this skill and the
explaining-the-work skill at once, where both are installed -- that is
expected, not a conflict. explaining-the-work routes what the text
should say (How/What/Why); this skill checks whether the text, once
written, is safe to publish (provenance, ASCII). Apply both; neither
substitutes for the other.

## Known gaps

The eval suite (`evals/outward-artifact-preflight/`) is committed and
runs the checklist tasks, but no baseline or with-skill-vs-no-skill
results are committed alongside it -- treat dimension 8 as
mechanism-present, results-unmeasured until a run is recorded. Only
`claude-sonnet-4.6` has been evaluated; cross-model behavior is
currently unmeasured.

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.

---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers and non-ASCII content, pending a real deterministic preflight/CI gate.
---

# Outward Artifact Preflight

This skill's checklist is general; check 1's "agreed disclosure
convention" and the explaining-the-work coupling (Relationship to other
skills) name this repo's own conventions -- substitute the calling
repository's actual policy and sibling skills where they differ.

This is an interim measure: a manual stand-in for the deterministic
preflight or CI gate this repository has not built yet. Run this
checklist by hand before every push or post until that gate exists.
Retire or narrow this skill the day the real gate lands -- it does not
substitute for one, and never present it as the permanent solution.

## Checklist

Run all three checks on the exact text about to be pushed or posted: a
commit message, PR/issue body, release notes, or any generated file
destined for a public sink.

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
   3. Disclosure does not exempt something from check 3: a disclosed
      trailer still has to pass the ASCII check, so replace any
      non-ASCII glyph in it (an emoji, for instance) with an ASCII
      equivalent.
   4. Commit messages follow a separate, narrower rule (where installed,
      the explaining-the-work skill routes commit-log content to one
      line plus a `Refs #N` pointer, nothing more) -- do not add a
      PR-body trailer to a commit message just because it is disclosed
      there.
2. **Post-creation re-check.** A pre-submission scan of the drafted text
   is not enough: `create_pull_request` and `update_pull_request` can
   inject a session-URL trailer downstream of the submitted `body`,
   invisible to any scan run before the call. Immediately after either
   call returns, re-fetch the PR (for example `pull_request_read` with
   method `get`) and re-run check 1 against the text actually stored on
   the platform, not the draft:

   ```bash
   python3 scripts/scan_provenance.py <<< "$ACTUAL_STORED_BODY"
   ```

   Pipe the body in on stdin and omit `--file` entirely. `--file -` does
   *not* read stdin here -- the script only reads stdin when `--file` is
   absent; passing `--file -` makes it look for a file literally named
   `-` and fail with `FileNotFoundError`.

   If the re-scan flags a candidate, call `update_pull_request` to strip
   it, then re-fetch and re-run the scan once more to confirm it was not
   force-reinjected before treating the artifact as clean.
3. **ASCII-only.** No em dashes, en dashes, curly quotes, full-width
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

## Worked example: post-creation re-check catches what pre-submission cannot

This is the actual shape of the gap check 2 (Post-creation re-check)
exists for -- confirmed twice, on two independent PRs merged the same day.

The drafted `body` passed to `create_pull_request` is clean: check 1's
pre-submission scan of it finds nothing.

```bash
python3 scripts/scan_provenance.py <<< "fix(skill): tighten the ordering rule

Refs #83"
```

```
PASS: no candidate provenance markers found
```

`create_pull_request` returns. Re-fetching the same PR's stored body per
check 2, the platform has appended a trailer that was never in the
submitted `body`:

```bash
python3 scripts/scan_provenance.py <<< "fix(skill): tighten the ordering rule

Refs #83

Generated by claude-example-model during session https://claude.ai/code/session_01Example99"
```

```
line 5: model identifier: claude-example-model
line 5: session URL: https://claude.ai/code/session_01Example99
line 5: anthropic session domain: https://claude.ai/code/session_01Example99
line 5: generic build/agent tag: Generated by claude-example-model
FAIL: 4 candidate marker(s) found -- review each: is it an agreed, disclosed convention, or must it be removed?
```

Applying the checklist: none of the four is an agreed disclosure
convention, so all must be removed. Fix via `update_pull_request` with the
trailer stripped, then re-fetch and re-run the scan once more -- a clean
second re-scan confirms the trailer was a one-time injection, not
force-reinjected.

## Relationship to other skills

Finalizing a commit or PR message can trigger both this skill and the
explaining-the-work skill at once, where both are installed -- that is
expected, not a conflict. explaining-the-work routes what the text
should say (How/What/Why); this skill checks whether the text, once
written, is safe to publish (provenance, ASCII). Apply both; neither
substitutes for the other.

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved -- for `git push`, this is backed by this plugin's
  `hooks/check-bash-safety.sh` PreToolUse hook, which runs
  `scripts/scan_provenance.py` against the outgoing commits and surfaces a
  warning (not a block) if it flags anything. The script's own docstring
  says it surfaces candidates, it does not decide -- so a hit does not
  stop the push, but it does still require applying this checklist's
  judgment call to each hit before the push is actually safe to make.
- Check 1's pre-submission scan is not sufficient on its own for
  `create_pull_request`/`update_pull_request`: no hook re-checks what the
  platform actually stores. Item 2's post-creation re-check is mandatory
  after every such call, not optional follow-up -- treat the PR as
  unverified until the re-fetched, actually-stored body has been scanned
  clean.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.

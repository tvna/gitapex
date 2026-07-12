# Outward Artifact Preflight Implementation Plan

**Goal:** Add `skills/outward-artifact-preflight/SKILL.md`, an interim manual
checklist for the two CLAUDE.md chapter 3 pre-publish checks (undisclosed
provenance markers, ASCII-only), per #8.

**Architecture:** One skill directory, one `SKILL.md`, no `references/`
subdirectory -- same shape as `skills/explaining-the-work/`. No runtime code,
no build step; correctness is checked by `grep`/`python3` against the file
content, same verification style as the skill-distribution-foundation plan.

**Tech Stack:** Plain Markdown. No new dependencies; `scripts/`/`tests/`
untouched.

## Global Constraints

- `name: outward-artifact-preflight` (kebab-case, matches directory name).
- `description` is single-line, third person, contains the literal trigger
  "Use when about to push, post, or publish any outward-facing artifact",
  no XML tags.
- Body explicitly states this is an interim measure pending a real
  deterministic preflight/CI gate (not a permanent solution) -- this is a
  hard acceptance criterion from #8, not optional framing.
- Body includes a worked dry-run example covering both a stray non-ASCII
  character and an undisclosed tooling fingerprint in the same sample text.
- Body includes an explicit Stop/boundary section.
- Do not touch `scripts/`, `tests/`, the plugin manifests, or any existing
  skill -- this plan only adds one new file.
- The `SKILL.md` file itself must be ASCII-only (it is, among other things,
  the worked example of what it teaches).

---

### Task 1: `outward-artifact-preflight` skill

**Files:**
- Create: `skills/outward-artifact-preflight/SKILL.md`

**Interfaces:** none (single-file, no dependency on other tasks).

- [ ] **Step 1: Create the skill directory and `SKILL.md`**

```bash
mkdir -p skills/outward-artifact-preflight
```

Write `skills/outward-artifact-preflight/SKILL.md`:

```markdown
---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers and non-ASCII content, pending a real deterministic preflight/CI gate.
---

# Outward Artifact Preflight

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
   disclose. If this repository already has an agreed disclosure
   convention for PR bodies (for example a fixed "Generated with X"
   trailer), keep it there. That is independent of check 2, though: a
   disclosed trailer still has to pass check 2, so replace any
   non-ASCII glyph in it (an emoji, for instance) with an ASCII
   equivalent -- disclosure does not exempt something from the ASCII
   rule. Commit messages follow a separate, narrower rule (where
   installed, the explaining-the-work skill routes commit-log content to
   one line plus a `Refs #N` pointer, nothing more) -- do not add a
   PR-body trailer to a commit message just because it is disclosed
   there. A bare model identifier (e.g. a `claude-*` model ID), a
   session URL, or an internal tool name is not disclosed and must be
   removed, unless this repository has explicitly agreed to disclose it.
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

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.
```

- [ ] **Step 2: Verify frontmatter is well-formed and the name matches the directory**

```bash
python3 -c "
import re
text = open('skills/outward-artifact-preflight/SKILL.md').read()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
assert m, 'no frontmatter block found'
fm = m.group(1)
assert 'name: outward-artifact-preflight' in fm, fm
assert 'description: Use when about to push, post, or publish' in fm, fm
assert '<' not in fm.split('description:')[1].split(chr(10))[0], 'description contains XML-like tag'
print('SKILL.md frontmatter OK')
"
```

Expected output: `SKILL.md frontmatter OK`

- [ ] **Step 3: Verify the required content markers are all present**

```bash
for phrase in "interim measure" "never present it as the permanent solution" "Undisclosed provenance markers" "ASCII-only" "Stop boundary" "Never push or post an artifact this checklist has flagged"; do
  grep -qF "$phrase" skills/outward-artifact-preflight/SKILL.md && echo "found: $phrase" || { echo "MISSING: $phrase"; exit 1; }
done
```

Expected output: six `found: ...` lines, no `MISSING` line.

- [ ] **Step 4: Verify the skill file itself is ASCII-only**

```bash
LC_ALL=C grep -nP '[^ -~\t]' skills/outward-artifact-preflight/SKILL.md && { echo "FAIL: non-ASCII found"; exit 1; } || echo "ASCII-only: OK"
```

Expected output: `ASCII-only: OK` (grep finds nothing, so its non-zero exit
takes the `||` branch).

- [ ] **Step 5: Manual dry run against the issue's acceptance criteria**

Run the worked example's two commands yourself (copy them out of the file
as written). Confirm the `grep` command actually prints line 1 and exits 0
against the `printf`-built sample, and that the sample separately contains
an undisclosed tooling fingerprint (`claude-example-model`, the session URL) --
i.e. both failure modes are demonstrated on real bytes, per #8's acceptance
criteria, not just described in prose.

- [ ] **Step 6: Verify the skill has no cross-folder path references or a
      CLAUDE.md dependency**

A skill must be distributable on its own -- nothing it references may live
outside `skills/outward-artifact-preflight/`, or the reference breaks for
anyone who installs this skill without the rest of gitapex. That rules out
two things: a backtick-styled repo-relative path outside this skill's own
directory (checked below), and treating `CLAUDE.md` (or a specific chapter
of it) as the required source of the skill's own rationale -- a receiving
repository is not guaranteed to have a matching `CLAUDE.md`, so the skill
must motivate its checklist in its own, portable terms. Naming a sibling
skill defensively ("where installed, ...") is fine, since it does not
require the sibling to exist for this skill to make sense on its own.

```bash
grep -noE '`[a-zA-Z0-9_.-]*/[a-zA-Z0-9_./-]*`' skills/outward-artifact-preflight/SKILL.md | grep -v '^[0-9]*:`skills/outward-artifact-preflight/' && { echo "FAIL: path reference outside the skill's own folder"; exit 1; } || echo "self-contained (paths): OK"
grep -q "CLAUDE.md" skills/outward-artifact-preflight/SKILL.md && { echo "FAIL: CLAUDE.md dependency found"; exit 1; } || echo "self-contained (no CLAUDE.md dependency): OK"
```

Expected output: `self-contained (paths): OK` (no backtick-styled path
outside `skills/outward-artifact-preflight/` itself) and `self-contained
(no CLAUDE.md dependency): OK` (no `CLAUDE.md` mention in the skill body).

- [ ] **Step 7: Commit**

```bash
git add skills/outward-artifact-preflight/SKILL.md
git commit -m "feat(plugin): add outward-artifact-preflight skill

Refs #8"
```

---

## Final check

- [ ] Run Steps 2-4 and 6's verification commands once more in sequence and
      confirm every one prints its expected "OK"/"found" output with no
      `MISSING`/`FAIL` line.
- [ ] Confirm every commit unique to this branch (`git log --oneline
      origin/main..HEAD`) cites "Refs #8", and that a "feat(plugin): add
      outward-artifact-preflight skill" commit and an "Add design spec for
      outward-artifact-preflight skill" commit both appear somewhere in
      that list. Do not assert a specific relative order, count, or `-N`
      offset between them -- any later fix commit lands on top of (newer
      than) whatever it fixes, so position shifts every time one is added.

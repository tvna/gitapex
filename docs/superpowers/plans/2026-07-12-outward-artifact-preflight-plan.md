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
for phrase in "interim measure" "does not substitute for one" "Undisclosed provenance markers" "ASCII-only" "Stop boundary" "Never push or post an artifact this checklist has flagged"; do
  grep -qF "$phrase" skills/outward-artifact-preflight/SKILL.md && echo "found: $phrase" || { echo "MISSING: $phrase"; exit 1; }
done
```

Expected output: six `found: ...` lines, no `MISSING` line.

- [ ] **Step 4: Verify the skill file itself is ASCII-only**

```bash
LC_ALL=C grep -n '[^ -~\t]' skills/outward-artifact-preflight/SKILL.md && { echo "FAIL: non-ASCII found"; exit 1; } || echo "ASCII-only: OK"
```

Expected output: `ASCII-only: OK` (grep finds nothing, so its non-zero exit
takes the `||` branch).

- [ ] **Step 5: Manual dry run against the issue's acceptance criteria**

Confirm by inspection: the worked example's flagged sample contains one
stray non-ASCII character and one undisclosed tooling fingerprint, and the
checklist as written catches both (Step 3's grep already confirms the
catching logic is documented; this step confirms the *sample* itself
exercises both failure modes, per #8's acceptance criteria).

- [ ] **Step 6: Commit**

```bash
git add skills/outward-artifact-preflight/SKILL.md
git commit -m "feat(plugin): add outward-artifact-preflight skill

Refs #8"
```

---

## Final check

- [ ] Run Steps 2-4's verification commands once more in sequence and
      confirm every one prints its expected "OK"/"found" output with no
      `MISSING`/`FAIL` line.
- [ ] Confirm `git log --oneline -3` shows the skill commit on top of the
      design-spec commit for this plan.

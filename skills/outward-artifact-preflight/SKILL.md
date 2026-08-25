---
name: outward-artifact-preflight
description: Use when about to push, post, or publish any outward-facing artifact -- a commit, PR/issue body, release, or generated file. Interim manual checklist for undisclosed provenance markers, non-ASCII content, and a citation-shaped sentence that could trip a git host's closing-keyword scan, pending a real deterministic preflight/CI gate.
---

# Outward Artifact Preflight

This skill's checklist is general. Check 1's "agreed disclosure
convention" and check 3's ASCII-only default illustrate gitapex's own
policy; check 2's raw-fetch hook is likewise gitapex's own illustration
of that channel, not a required dependency. Each states an inline
fallback to substitute the calling repository's actual policy or
tooling where it differs. The explaining-the-work coupling
(Relationship to other skills) names a sibling skill gitapex happens to
also install -- apply it where that sibling is installed, skip it
otherwise.

This is an interim measure: a manual stand-in for the deterministic
preflight or CI gate this repository has not built yet. Run this
checklist by hand before every push or post until that gate exists.
Retire or narrow this skill the day the real gate lands -- it does not
substitute for one, and never present it as the permanent solution.

## Checklist

Run all four checks on the exact text about to be pushed or posted: a
commit message, PR/issue body, release notes, or any generated file
destined for a public sink.

1. **Undisclosed provenance markers.** Scan for anything identifying the
   build/runtime model, agent, or session that produced the artifact, and
   any internal tooling fingerprint, that the owner has not chosen to
   disclose. Run `python3 scripts/gitapex_scan_provenance.py --file <file>` first
   to surface mechanical candidates (model IDs, session URLs, generic
   build/agent tags) instead of re-scanning for these patterns in prose
   each time; the script only surfaces candidates, it does not decide
   whether a hit is actually undisclosed.

   1. A bare model identifier (e.g. a `claude-*` model ID), a session
      URL, or an internal tool name is not disclosed and must be
      removed, unless the calling repository has explicitly agreed to
      disclose it.
   2. If the calling repository already has an agreed disclosure
      convention for PR bodies (for example a fixed "Generated with X"
      trailer), keep it there.
   3. Disclosure does not exempt something from check 3: a disclosed
      trailer still has to pass whatever check 3 currently requires --
      by default an ASCII equivalent for any non-ASCII glyph (an emoji,
      for instance), unless the calling repository's own documented
      character-set policy (check 3's fallback) already permits it.
   4. Commit messages follow a separate, narrower rule (where installed,
      the explaining-the-work skill routes commit-log content to one
      line plus a `Closes #N`/`Refs #N` issue pointer, nothing more) --
      do not add a PR-body trailer to a commit message just because it
      is disclosed there.
   5. A calling repository may have already ratified a concrete
      instance of item 2 -- recorded in its own contributor-facing docs
      (a `CONTRIBUTING.md`, governance doc, or equivalent), naming a
      specific trailer shape, its ratification date, and a narrow
      scope so the ratification cannot silently widen into a blanket
      exemption. Check there before re-deriving the judgment call from
      scratch; do not assume such a record exists just because this
      note does. A ratification narrows *what item 2 already permits*,
      never *what this scan reports*: `scripts/gitapex_scan_provenance.py`
      still flags every matching hit, by design, whether or not a
      ratification exists -- confirming a given hit is the ratified
      instance and not a lookalike remains a per-hit judgment call, not
      something to suppress with an ignore pattern, allowlist, or
      `--exclude` flag.
2. **Post-creation re-check.** A pre-submission scan of the drafted text
   is not enough: `create_pull_request` and `update_pull_request` can
   inject a session-URL trailer downstream of the submitted `body`,
   invisible to any scan run before the call. Immediately after either
   call returns, re-fetch the actually-stored body through a raw,
   unsanitized channel and re-run check 1 against it, not the draft.

   **Do not use an MCP read tool (`pull_request_read`, `issue_read`) for
   this re-check.** A GitHub MCP server can sanitize the HTML/Markdown of
   a body it returns (confirmed for `github/github-mcp-server`'s own
   response-direction handler, which strips any element outside a fixed
   allowlist -- `pkg/sanitize/sanitize.go`, allowlist introduced at commit
   `6a39a39` and unchanged in this respect as of a direct clone's current
   `HEAD` -- while its write path applies no such sanitizer). A legitimate
   construct outside
   that allowlist -- a backtick-wrapped angle-bracket placeholder, a
   bracket-wrapped-URL autolink -- can therefore come back looking
   stripped from an MCP read even though storage still holds it intact.
   Reading a body back through an MCP tool call proves only that the read
   channel's own sanitizer touched it, never that storage lost anything.

   Re-check through a raw, unsanitized fetch instead: a direct HTTPS
   `GET /repos/{owner}/{repo}/issues/{number}` (the one REST endpoint for
   both issues and pull requests) bypasses that sanitizer entirely. This
   repository's own default already automates this: a PostToolUse hook
   (`hooks/check-post-write-provenance.sh` /
   `hooks/gitapex_check_post_write_provenance.py`) re-fetches the stored
   body this way after `create_pull_request` / `update_pull_request` /
   `issue_write` returns and re-runs this checklist's check 1 and check 3
   -- plus a submitted-vs-stored content-loss comparison -- against it.
   Where it is installed, its verdict resolves this step for you, with
   PASS / FLAGGED / CONTENT_LOSS each already a terminal answer (confirm
   and act on it, never re-derive one by hand through an MCP read); an
   INDETERMINATE verdict is not terminal -- it means the hook itself
   could not verify the stored body (a missing token, an unreachable API),
   so fall through to the manual raw-fetch re-check below rather than
   treating INDETERMINATE as "check complete."

   Where no such automation exists (or its verdict is INDETERMINATE),
   call the calling repository's own equivalent raw-fetch helper directly
   -- this repository's own is `fetch_issue()` in
   `hooks/gitapex_check_pr_issue_acm_disclosure.py`, which returns a
   `{"body": ..., "state": ...}` mapping -- and feed its `body` value into
   the scan below, assigned to a shell variable however your environment
   does that (for example, printing just that field and capturing it via
   command substitution). Never feed the scan a body read back from
   `pull_request_read`/`issue_read`:

   ```bash
   python3 scripts/gitapex_scan_provenance.py <<< "$ACTUAL_STORED_BODY"
   ```

   `$ACTUAL_STORED_BODY` here stands for that raw-fetched body text, not a
   literal environment variable this skill sets for you. Pipe the body in
   on stdin and omit `--file` entirely. `--file -` does *not* read stdin
   here -- the script only reads stdin when `--file` is absent; passing
   `--file -` makes it look for a file literally named `-` and fail with
   `FileNotFoundError`.

   If the re-scan flags a candidate, call `update_pull_request` to strip
   it, then re-fetch (again through the raw channel above, never an MCP
   read) and re-run the scan once more to confirm it was not
   force-reinjected before treating the artifact as clean.

   An issue body written through a create/update issue call needs the
   same treatment, with the issue-side equivalent at each step: re-fetch
   the issue through the raw channel, scan its stored body, strip a
   flagged candidate via the issue write call, then re-fetch and re-scan
   to confirm. Nothing about this gap is PR-specific -- only the tool
   names differ.

   Where the PostToolUse hook is installed it reports the finding but
   cannot undo the write -- the remediation above is still yours to
   perform -- and it covers only the tool calls it matches, so a body
   edited afterwards through any other path is still yours to re-check
   through the raw channel by hand.
3. **ASCII-only.** Default to no em dashes, en dashes, curly quotes,
   full-width punctuation, or any other non-ASCII character -- gitapex's
   own convention. If the calling repository documents a different
   character-set policy (for example, permitting Unicode or emoji),
   follow that instead. Check with (`-P` enables
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
4. **Closing-keyword narration hazard.** A sentence that only narrates
   history -- citing a past PR or issue by number -- can still trip a
   git host's closing-keyword scan if a recognized keyword happens to
   land immediately before the `#`-number, even when the author's
   intent is not to close anything. Confirmed against each of GitHub,
   GitLab, Forgejo, and Gitea's own documentation as it stood on
   2026-08-15: all four match a literal keyword-plus-number pattern
   with no stated grammatical, semantic, or tense analysis of the
   surrounding sentence. This is not a blanket claim about every
   git-hosting platform -- a host not checked here (for example
   Bitbucket or sourcehut) could behave differently in either
   direction, and any of the four platforms' own lists could change
   after the date above -- re-verify against the live documentation
   if this guidance is being relied on long after that date.

   1. GitHub and Forgejo recognize close/closes/closed,
      fix/fixes/fixed, and resolve/resolves/resolved (Forgejo's list
      is admin-customizable but ships with this same set). GitLab
      recognizes the same three families plus an
      implement/implements/implemented family, and adds an "-ing"
      form to all four (closing, fixing, resolving, implementing) --
      the widest of the four. Gitea's list is identical to Forgejo's.
   2. Forgejo and Gitea additionally require, for a reference placed
      in a PR description specifically, that the merger hold
      close/reopen permission at merge time (a commit-message
      reference, or a commenter who already holds that permission, is
      sufficient without it). GitHub and GitLab's own documentation
      states no such permission gate.
   3. Before publishing a sentence that cites a past PR or issue by
      number in prose, check whether a recognized keyword lands
      immediately before the `#`-number. If it does, and the sentence
      narrates something that already happened rather than directing
      this artifact to resolve it, rewrite to avoid the trigger:
      prefer a full URL citation over the bare `#`-number, or a verb
      outside every platform's list above (for example "addressed",
      "landed", "shipped"). See the worked example below.
   4. If it is unclear from the sentence alone whether the author
      means to close the cited issue or only narrate it, do not
      decide silently either way: treat it the same as any other
      unresolved hit under this checklist's Stop boundary and confirm
      intent with the author before publishing. Guessing "narration"
      risks stripping a closing directive the author meant to keep;
      guessing "directive" risks leaving the accidental-closure hazard
      unflagged.

## Worked example

This file must itself stay ASCII-only, so the flagged sample below is built
with `printf`, not a pasted glyph -- run both commands yourself to see the
checklist catch real bytes instead of a description:

```bash
printf 'feat(plugin): add outward-artifact-preflight skill \xe2\x80\x94 built by\nclaude-example-model during session https://claude.ai/code/session_01Abc23dEf\n\nRefs #8\n' > /tmp/flagged-commit-msg.txt
LC_ALL=C grep -nP '[^ -~\t]' /tmp/flagged-commit-msg.txt
```

Applying the checklist:

- Check 1 fires: `claude-example-model` and the session URL are a bare
  model identifier and a session URL -- neither is an agreed disclosure
  convention, so both must be removed to pass.
- Check 3 fires: `grep` prints line 1 (exit status 0) -- the `\xe2\x80\x94`
  bytes (an em dash) are non-ASCII.

This example exercises checks 1 and 3 only. Check 2 has nothing to fire
on here: there is no posted artifact to re-fetch yet. See the second
worked example below for that one.

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
python3 scripts/gitapex_scan_provenance.py <<< "fix(skill): tighten the ordering rule

Refs #83"
```

```
PASS: no candidate provenance markers found
```

`create_pull_request` returns. Re-fetching the same PR's stored body per
check 2, the platform has appended a trailer that was never in the
submitted `body`:

```bash
python3 scripts/gitapex_scan_provenance.py <<< "fix(skill): tighten the ordering rule

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

## Worked example: a citation sentence that reads as a directive

The hazard check 4 exists to catch is a bare issue/PR-number citation
used only to narrate history: "PR `#911` closed `#907`." A keyword
scanner reads that same text as GitHub, Forgejo, and Gitea's own
recognized `closed` keyword immediately before a number -- the same
literal pattern a real closing directive would use, with nothing in
the sentence's own text to tell the two apart.

Either rewrite strategy from item 3 clears the trigger on its own,
shown separately here since combining both in one sentence would not
demonstrate that each works alone.

Replacing the bare issue/PR-number citation with a full URL, keyword
unchanged: "PR `#911` closed the defect described at
https://github.com/OWNER/REPO/issues/907." No bare `#`-number sits
next to "closed" anymore.

Keeping the same issue/PR-number citation but choosing a verb outside
every checked platform's list, from item 1: "PR `#911` addressed the
defect from issue `#907`." "addressed" is outside every checked
platform's keyword list.

Either rewrite alone removes the trigger; using both together is not
required.

## Relationship to other skills

Finalizing a commit or PR message can trigger both this skill and the
explaining-the-work skill at once, where both are installed -- that is
expected, not a conflict. explaining-the-work routes what the text
should say (How/What/Why); this skill checks whether the text, once
written, is safe to publish (provenance, ASCII, closing-keyword
citations). Apply both; neither substitutes for the other.

## Stop boundary

- Never push or post an artifact this checklist has flagged. Fix it first,
  or get the owner's explicit sign-off to proceed anyway with the flag
  unresolved. Some environments back the `git push` case with a
  PreToolUse hook (this repository's own `hooks/check-bash-safety.sh` is
  one example: it runs `scripts/gitapex_scan_provenance.py` against the outgoing
  commits and surfaces a warning, not a block, if it flags anything). The
  script's own docstring says it surfaces candidates, it does not decide
  -- so a hit does not stop the push, but it does still require applying
  this checklist's judgment call to each hit before the push is actually
  safe to make, whether or not such a hook exists.
- Check 1's pre-submission scan is not sufficient on its own for
  `create_pull_request`/`update_pull_request`. Check 2's post-creation
  re-check is mandatory after every such call, not optional follow-up --
  treat the PR as unverified until the re-fetched, actually-stored body
  has been scanned clean. Where a PostToolUse hook backs it, check 2's
  own note states what that hook does and does not cover; that note is
  the single place this file states it.
- This skill only applies the checklist; it does not authorize skipping
  it, and it does not replace the deterministic gate this repository has
  not built yet.

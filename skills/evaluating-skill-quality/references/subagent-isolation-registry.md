# Subagent isolation registry

## Table of contents

- [Purpose](#purpose)
- [Verification procedure](#verification-procedure)
- [Known entries](#known-entries)
  - [Agent-tool subagent dispatch inside a Claude Code Remote session](#agent-tool-subagent-dispatch-inside-a-claude-code-remote-session)
- [Unlisted platform](#unlisted-platform)

## Purpose

Whether a dispatched subagent's context actually excludes the calling
repository's own `CLAUDE.md`/`AGENTS.md` is not a property of this skill --
it is a property of the *dispatch mechanism* the current platform provides,
and that varies by platform and can change between harness versions. Rather
than asserting one fixed mechanism as universally correct (which would fail
`SKILL.md`'s Subagent dispatch exclusion requirement the moment this skill
runs on a different platform), this file is a live, per-platform registry:
find or add the current platform's entry before trusting any dispatch's
isolation.

## Verification procedure

Portable across platforms -- run this to test any candidate dispatch
mechanism, not only the ones already recorded below.

1. **Positive control.** From a working directory known to sit under the
   calling repository's own `CLAUDE.md`/`AGENTS.md` ancestry, run the
   candidate dispatch mechanism with a prompt asking it to report, verbatim,
   whether it currently has project-level instructions loaded, and to quote
   one distinctive sentence if so. Confirm it actually quotes real content --
   this proves the test itself can detect the file when present, rather than
   reflexively reporting "none" regardless of truth.
2. **Negative control.** From (or targeting) a location with no
   `CLAUDE.md`/`AGENTS.md` anywhere in its full directory ancestry, run the
   identical prompt through the identical mechanism. A result of "none
   loaded" counts as evidence of real isolation only if the positive control
   in step 1 succeeded first -- otherwise the mechanism may simply never
   detect the file at all, positive or negative.
3. A scratch copy's own directory ancestry being free of
   `CLAUDE.md`/`AGENTS.md` is **not sufficient evidence on its own** -- see
   the counter-example in Known entries below. The two controls above, run
   against the dispatched agent's actual self-report, are the only check
   confirmed to detect a leak that filesystem inspection alone missed.
4. Record a new entry in Known entries: platform identifying signal(s), the
   mechanism tested, the verified outcome, the date/versions observed, and
   any caveat. Never assert isolation for a platform with no recorded entry.

## Known entries

### Agent-tool subagent dispatch inside a Claude Code Remote session

- **Identifying signal**: a `CLAUDE_CODE_REMOTE=true` environment variable
  is present, and the harness exposes an `Agent` tool for subagent dispatch
  whose subagents run inside the same session/environment as the caller
  (observed `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default`; `claude
  --version` reported `2.1.220 (Claude Code)` at time of test).
- **Mechanism tested**: dispatching a subagent through the harness's `Agent`
  tool, pointed only at a project-instruction-file-free scratch copy of the
  target material (the scratch directory's own full ancestry was
  independently confirmed to contain no `CLAUDE.md`/`AGENTS.md`).
- **Result: fails isolation.** The dispatched agent's own self-report
  disclosed that the calling repository's `CLAUDE.md` was present in its
  context from the start of the task, despite the scratch-copy mitigation --
  confirmed across two independent dispatches against two different review
  targets. Filesystem-level scratch-copy isolation does not control this
  mechanism's context construction; the exclusion appears tied to the
  dispatching session's own project root, not to any path referenced in the
  dispatch prompt.
- **Verified alternative**: invoking `claude -p "<prompt>"` as a subprocess
  (for example, via a shell tool) from a working directory whose full
  parent-directory chain contains no `CLAUDE.md`/`AGENTS.md`. This passed
  both controls above: it quoted real project-instruction content when
  invoked from inside the repository, and reported none when invoked from
  an isolated directory outside any such repository's ancestry.
- **Caveat**: a dated empirical observation on the tested `claude` CLI and
  harness versions above, not a permanent property of "the Agent tool" as a
  concept. Re-run the Verification procedure above if this entry looks
  stale, the harness version has changed materially, or the result seems
  inconsistent with current behavior -- never extend this entry's
  conclusion to a platform or version it was not actually tested on.

## Unlisted platform

If the current platform is not represented above, do not assume either
outcome in either direction. Run the Verification procedure now, then add
an entry -- or, if this skill was vendored from elsewhere, add the entry to
this copy of the file rather than assuming the origin repository's registry
still applies; a vendored copy's platform is not guaranteed to match the
origin's.

# eliciting-a-design: dual-path Visual Companion (Node.js + Artifact)

Date: 2026-08-23

Refs #1263. Design-only doc, authored before any implementation, per
`eliciting-a-design`'s own HARD-GATE (SKILL.md's Checklist: no code
change until the design is presented in sections and explicitly
approved). Scope matches #1263's own Requested outcome exactly -- no
extension found during authoring, unlike the precedent
`2026-08-22-eliciting-a-design-design.md`, which is itself the reason
this doc stays this size: that doc's weight reflects a new skill's
whole domain model plus corrections found during implementation; this
change is additive to one already-shipped skill, so a concise spec is
the right weight per CLAUDE.md section 1.

## Scope

Add a second delivery path to `eliciting-a-design`'s existing Visual
Companion (Node.js HTTP server, shipped in #1163/PR #1262): a Claude
Code Artifact path, preferred when the Artifact tool is present,
falling back to the existing Node.js server everywhere else, falling
back to text-only when neither applies. Purely additive -- see
Non-goals.

## Why this doc exists

A live compatibility test on PR #1262
([comment #5383137958](https://github.com/tvna/gitapex/pull/1262#issuecomment-5383137958))
found the shipped Node.js companion unreachable from the operator's own
browser in a Claude Code Remote session: the server runs and answers
`curl` inside the sandbox, but the `localhost` URL it returns resolves
to whatever machine makes the request, never the sandbox, and
`--host 0.0.0.0` does not change that -- it only widens which
interfaces the sandbox listens on. This session is itself a Claude Code
Remote session, so the gap sits in the skill's own primary authoring
environment, not a hypothetical edge case. The operator's chosen
direction -- extend with a second path rather than replace the first --
is recorded as the Requested outcome on #1263 and re-confirmed through
this doc's own design dialogue (four sections, each presented and
approved individually) and terminal decision handoff (`clairvoyance`
skill, invoked inline).

## Method

Per `eliciting-a-design`'s own Checklist: project-context exploration,
a Core Domain check (Generic subdomain -- environment-detection and
optimistic-sync patterns are solved problems elsewhere, so this design
reuses the skill's own existing prerequisite-plus-fallback idiom rather
than inventing a new one), an inline Architecture Trade-Off (Options A/B/C
below) at the point the dialogue surfaced it, a Fit-and-Gap pass (current
state: Node.js-only; target state: dual-path), the four-section design
presentation, and the terminal decision handoff via `clairvoyance`. All
five steps ran this session; none deferred silently.

## Decision 1: environment detection is by tool presence, not by the two unconfirmed env vars

**Facts:** the PR #1262 review comment found two suggestive but
unconfirmed environment variables referenced from the Claude Code CLI
binary and an `environment-manager` binary
(`CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2`,
`CLAUDE_SESSION_INGRESS_TOKEN_FILE`) -- neither confirmed to expose an
arbitrary local port to the operator's browser versus being internal
plumbing specific to Claude Code's own web UI; the token file's
contents were deliberately not read (treated as a credential, per
CLAUDE.md section 4's sensitive-material rule). `artifact-capabilities`
(runtime contract 0.2.15, read directly this session) explicitly
instructs never probing `window.claude` members.

**Decision:** detect the Artifact path by whether the Artifact tool
itself is present in the session's own tool inventory -- the same
"check the harness's own skill/tool inventory, state what was checked"
discipline `eliciting-a-design`'s Checklist already applies to sibling
skills (`clairvoyance`, `architecture-tradeoff`). This sidesteps both
open questions: it does not depend on confirming what the two env vars
actually gate, and it does not probe `window.claude`.

**Fallback order:** Artifact tool present -> Artifact path. Else `node`
on `PATH` and a reachable browser -> existing Node.js path, unchanged.
Else -> text-only, stated to the user the same way the existing
`references/visual-companion.md` already discloses a missing `node`
("that is a normal outcome, not a failure to work around").

**Runtime failure, distinct from detection-time absence:** tool
presence only confirms the Artifact tool is callable, not that the
account's runtime capabilities permit a write (e.g. `publish` returning
an error rather than a `conflict`, which Decision 2 already treats as
routine). If the first `publish()` attempt for a session fails outright
rather than returning `conflict`, drop one level in the same fallback
order (Node.js path, then text-only) instead of retrying the Artifact
path or surfacing a raw error to the user. This is a one-time
downgrade per session, evaluated at first use, not a per-screen retry
loop.

## Decision 2: Artifact-path UX -- zero-API sync, terminal-trigger read-back

**Decision:** publish each screen as Live Doc HTML via
`Artifact({action:"publish", ...})`. A viewer's click or selection is
auto-saved by the Live Doc gesture-sync mechanism with no agent-side
`edit()`/`sync()` call (contract 0.2.15's zero-API sync region,
`artifact-sync`, defaults to `<body>`). The agent learns the selection
by reading the artifact back (`Artifact({action:"read", url})`) on its
next turn, once the user has responded in the terminal -- the same
next-turn-read shape the Node.js path already uses for
`$STATE_DIR/events`, on a different transport.

**Hard rule carried over from the Node.js path's own escaping
discipline** (`references/visual-companion.md`'s "Escape anything you
did not author" section): never replace the full sync region's
`innerHTML` wholesale when re-publishing an iteration. Construct each
new screen the same disciplined way the Node.js path writes a fresh
HTML fragment, to avoid clobbering in-flight viewer-made DOM state and
to avoid the same unescaped-untrusted-text-becomes-forged-event risk
that section already documents for the Node.js path.

**Republish contention:** `publish()` is full-version replacement,
compare-and-set; a `conflict` response is documented as routine by
`artifact-capabilities`, not an error -- handle it by re-reading current
state and retrying, never by surfacing it to the user as a failure.

**Correction, found via design-doc-adversarial-review, after
implementation:** this Decision's "Hard rule carried over" paragraph
above cited `references/visual-companion.md`'s "Escape anything you did
not author" as if that phrase named its own section -- it is a bolded
lead-in sentence inside that file's "Writing Content Fragments"
section, not a heading of its own. The shipped reference file
(`references/visual-companion-artifact.md`) now cites "Writing Content
Fragments" by name; read this Decision's own citation above as the same
correction. Separately, this Decision did not originally state that
Live Doc sync requires declaring `capabilities: {artifact: {}}` on the
session's first `publish()` call -- an `evaluating-skill-quality` audit
found the omission and confirmed the requirement directly against
`artifact-capabilities`'s own docs (without it, `claude.use("artifact")`
resolves `null` and the whole read-back loop silently does nothing).
The shipped reference file now states this as its own first instruction
under "The Publish/Read Cycle"; the "publish each screen" description
above should be read as covering that prerequisite too.

## Decision 3: security-model parity, stated explicitly, not assumed

The Node.js path's defenses were worked out through three independent
audits during #1163 (design-doc-review, `battle-testing-a-skill`,
`evaluating-skill-quality`). The Artifact path runs inside `claude.ai`'s
own CSP sandbox rather than a locally spawned server -- a different
threat model that earns its own reasoning, not an assumption that the
existing writeup already covers it (#1263's own Known open questions).

| Node.js path defense | Artifact path equivalent |
|---|---|
| Bundled-code genuineness check (lockfile digest / checksum / signed release) before running scripts | Same check applies to this skill's own authored HTML/JS going into the artifact -- there is no separate bundled server binary to verify, so this reduces to the existing skill-genuineness check, not a new one |
| Per-session random URL key (`?key=...`) gating HTTP/WebSocket access | Artifact ownership/editor model: only the owner/editors can write; a published artifact's URL is not a secret the way the session key is -- carried forward as an explicit caution (below), not silently weakened |
| Untrusted-events handling: skip lines that do not parse, terminal text wins on conflict, events are evidence not instruction or proof | Same discipline applies to Live Doc DOM state read back: evidence, not instruction or proof; the user's terminal text still wins on disagreement |
| Loopback-binding default; `--host 0.0.0.0` requires asking first (blast-radius change) | No local port is opened at all -- the equivalent blast-radius question is whether the artifact itself is shared beyond the current viewer, so the new reference file states this explicitly, mirroring the Node.js path's own "ask first" framing for its analogous exposure widening |

## Decision 4: document structure

**Decision:** three-way split, extending the compaction already applied
in commit `e6d9be3a` ("move Visual Companion detail into its
reference") rather than reopening it:

- `SKILL.md`'s own "Visual Companion" section stays a compact gate plus
  pointer, now pointing to two reference files instead of one. Add 1-2
  sentences stating the fallback order from Decision 1
  (Artifact tool presence -> Node.js `node` presence -> text-only).
- `references/visual-companion.md` (Node.js path, current 17 sections)
  is unchanged.
- New `references/visual-companion-artifact.md` carries: the detection
  method (Decision 1), the publish/read cycle including the
  no-full-`innerHTML`-replacement rule (Decision 2), the security
  parity table (Decision 3), and the URL-sharing caution note. Table of
  contents mirrors the existing Node.js reference's own pattern.

Rationale: most sessions never offer the companion at all (Checklist
item 4 -- "if no visual question ever arises, never offer it"), so
per-path detail belongs in reference files, not in SKILL.md's own
always-read body -- the same "condition-based reference" discipline
already governing the Node.js path.

**Correction, found via design-doc-adversarial-review, after
implementation:** this Decision's own "Add 1-2 sentences" scoping for
the `SKILL.md` edit undercounted what actually shipped. A Step 8
adversarial review found the pre-existing genuineness/runnability gate,
the offer-script quote, and the start-up instruction all stayed
unconditionally Node.js-specific after the fallback-order sentence was
added -- making the offer script's own "nothing leaves your machine"
claim false whenever the Artifact path is selected. All three
paragraphs were rewritten to branch per path, not only the one sentence
this Decision named. Also: this Decision's "17 sections" count for
`references/visual-companion.md` does not match the file under any
counting convention (14 `##` headings, or 21 including `###`
subsections, both directly counted from the file) -- corrected here as
a wrong count, not left stale; the
file's own content is otherwise confirmed unchanged (`git diff` since
commit `e6d9be3a` is empty). Finally, this Decision did not name
`SKILL.md`'s own `compatibility` frontmatter field as part of what
changes -- it was rewritten (also by the `evaluating-skill-quality`
fix) because its pre-existing "additionally requires Node.js... entirely
local" claim became false once the Artifact path shipped.

## Architecture Trade-Off (inline, resolved during the design dialogue)

| Option | Verdict |
|---|---|
| A. Artifact-only replacement of the Node.js companion | Rejected -- breaks every non-Claude-Code-Remote surface this skill already supports (local CLI, Codex, Copilot CLI); Artifact capabilities are not guaranteed available on every account |
| B. Node.js-only status quo (do nothing) | Rejected -- this is the exact gap #1263 exists to close, demonstrated live in this skill's own runtime environment |
| **C. Dual-path fallback (chosen)** | Extends the skill's existing prerequisite-plus-fallback idiom (already used for `clairvoyance`/`architecture-tradeoff` availability) one level further, at the cost of maintaining two reference docs and two code paths in parity |

## Facts vs. speculation

**Facts, verified this session:** the PR #1262 review comment's own
text (read directly) states the `curl`-inside-sandbox / unreachable-
from-operator's-browser finding and the two unconfirmed env var names.
`artifact-capabilities`'s type definitions (read directly,
`artifact.d.ts`, contract 0.2.15) state Live Doc zero-API sync, the
`artifact-sync` default region, `publish()`'s compare-and-set semantics
and `conflict` being routine, and the explicit "never probe
`window.claude`" guidance. This account's available runtime
capabilities (`artifact`, `downloads`, `mcp`) were checked directly,
not assumed. Commit `e6d9be3a`'s own diff (read directly) confirms the
current SKILL.md Visual Companion section is already a compacted
gate-plus-pointer.

**Speculation, named as such:** whether
`CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2` or
`CLAUDE_SESSION_INGRESS_TOKEN_FILE` could, if their purpose were later
confirmed, offer a viable third detection or delivery mechanism is
unresolved and deliberately out of this design's scope (#1263's own
Non-goals) -- Decision 1 does not depend on the answer either way, but
a future confirmation could still change this doc's Options table.
Whether every harness this skill runs on exposes Artifact-tool presence
through the same inventory-check mechanism this design assumes is
untested outside this session's own harness; the fallback to Node.js
when the check itself is inconclusive is Decision 1's own stated
behavior, not a gap this doc leaves open.

## Non-goals

- Does not modify any existing Node.js path file (`scripts/server.cjs`,
  `scripts/start-server.sh`, `scripts/helper.js`,
  `scripts/frame-template.html`, `references/visual-companion.md`).
- Does not confirm the two unconfirmed environment variables' actual
  purpose -- #1263's own Non-goals name this explicitly; if confirmed
  later, it is new evidence for a future design, not an assumption
  this one makes.
- Does not touch PR #1262 or issue #1163's own scope -- that PR ships
  the Node.js-only companion as-is; this is tracked separately per
  #1263's own Non-goals.
- Does not implement `edit()`/`sync()` agent-initiated Artifact writes
  -- Decision 2 selects zero-API gesture sync only; explicit
  agent-initiated write calls were considered and not chosen (#1263's
  Known open questions, second bullet), so are out of scope here, not
  deferred.
- Does not add a third detection path beyond tool-presence and
  `node`-presence.

## Next step

Spec self-review (placeholder/consistency/scope/ambiguity), then the
User Review Gate on this file, then transition #1263 to issue
formalization (`drafting-issues` if available, else
`drafting-an-acm-issue`) per `eliciting-a-design`'s own Checklist items
11-13. Implementation is gated on that formalization producing its own
Acceptance Criteria Map -- this doc's own approval does not authorize
code changes by itself.

# Skill authoring standards

Durable home for authoring rules that apply across this repository's
skills and durable docs (plans, specs), found by retrospectives and
previously living only inline in issue #8's body. Distinct from
`skills/evaluating-skill-quality/`'s deterministic shape checks and
probabilistic maturity rubric (which judge a `SKILL.md`'s structure and
content quality) and from `skills/outward-artifact-preflight/` (which
audits an already-drafted outgoing artifact -- a commit, PR/issue body,
or release -- for provenance leaks and non-ASCII bytes): the rules below
govern how a skill or durable doc's own prose and examples are authored
in the first place. Rules 1 and 4 are enforced by
`skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py` (the
`no-illustrative-model-identifier` and `no-raw-angle-bracket-placeholder`
checks) against every `SKILL.md` and `references/*.md` file in this
repository's own `skills/` tree, run by `tests/test_gitapex_repository_skill_shape.py`
on every push and PR. Rules 2, 3, 5, and 6 stay judgment calls -- detecting a
git-log-position assertion, grading test-fixture completeness, matching a
citation's own wording against a canon, or judging whether a given body
section is genuinely load-bearing for an invoking model all need semantic
understanding a script cannot reliably provide -- apply them by hand at
authoring and review time, the same way this file's own source retrospectives
(#20, #122) already did, until a broader eval-suite or `check_skills.py`-
equivalent gate exists for that category (tracked separately, see issue
#11 and #20's gate proposal 1). Content outside
`skills/` (this file included) is not covered by the deterministic
checker; the outward-artifact-preflight checklist's own scope is
different again (an outgoing artifact's text, not a skill's source
files).

## 1. No real, current model identifier as illustrative content

Never use a real, current model identifier (for example a `claude-*`
model ID) as illustrative content in a skill's own `SKILL.md` or
`references/` -- including inside a worked example that is deliberately
flagged as a "bad" or "before" sample meant to be fixed. Use a clearly
fictitious placeholder instead, e.g. `claude-example-model`.

This is narrower than, and does not replace, the existing rule in
`skills/outward-artifact-preflight/SKILL.md` check 1: that rule governs
*disclosure* in outgoing artifacts (a commit, PR/issue body, or release
must not carry an undisclosed provenance marker). This rule instead
governs a skill's own illustrative content -- a worked example inside a
`SKILL.md` is never actually published as a commit or PR, but a reader
copying it verbatim, or a future author pattern-matching its style, can
still propagate a real model name into content that later is published.

Found via: PR #17's worked example used `claude-sonnet-5` -- a real,
current model name -- as its flagged "bad" sample (retrospective #20,
repair 4b).

Enforcement: `gitapex_check_skill_shape.py`'s `no-illustrative-model-identifier`
check flags "claude-" followed immediately by a known model-family word
(opus/sonnet/haiku/fable/instant) and a version-like digit, anywhere in a
skill's `SKILL.md` or `references/*.md` -- including inside a fenced code
block or inline code span, since this rule is about the identifier ever
appearing as illustrative content at all, unlike the citation checks in
the same script. `claude-example-model` never matches. One exemption: a
match that falls entirely inside a real citation URL to Anthropic's own
docs (an autolink, inline link target, or reference-style link definition
pointing at `platform.claude.com`, `code.claude.com`, or `claude.com`) is
not an offender -- a doc URL whose own slug names the model the page
documents (e.g. a citation to Anthropic's "Prompting Claude Opus 5" guide)
is a primary-source citation, not illustrative content a reader might
copy-paste as sample data.

## 2. Durable docs assert content, never git-log position

A durable doc (a plan, spec, or any other document meant to stay
accurate as the repository's history grows) must assert *content* about
mutable repo state, never a *specific relative git-log position*. "The
skill commit is the newest commit on this branch" or "this file was just
added" both go stale the moment a later commit lands -- and are
backwards from the start in the specific case of a fix commit, which is
always newer than what it fixes, never older. Prefer an assertion the
reader can verify without depending on ordering, e.g. "commit `<sha>`
adds `<path>`" or "`<path>` contains `<content>` as of commit `<sha>`".

Found via: PR #17's plan asserted a specific relative git-log ordering
twice, and a later fix commit had already falsified it by the time the
plan's Final check ran (retrospective #20, repair 5).

## 3. A totalizing check needs a full variant checklist

When a deterministic check's docstring or claim uses a totalizing word
("every", "all", "any") over a syntax category, its own test-fixture
checklist must enumerate that category's known variants -- per the
relevant spec -- before the check is considered complete. One
representative example is not enough: a check that claims to validate
"every Markdown link target" but only exercises inline links
(`[text](target)`) silently misses reference-style links (`[text][label]`
resolved via a separate `[label]: target` definition), even though both
are ordinary CommonMark link forms.

`skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py`'s
`_out_of_skill_link_targets` now gets this right: it explicitly covers
both inline and reference-style Markdown links, including the
`<...>`-wrapped destination form.

Found via: PR #121's new `links-inside-skill` check initially covered
only inline links; a reference-style link to an out-of-skill path
silently passed despite the check's own docstring claiming to validate
every link target (retrospective #122, repair 1).

## 4. No angle-bracket placeholders in raw prose

In any outward-facing artifact (a `SKILL.md`, a PR/issue body, or any
other text meant to render as GitHub-flavored Markdown or HTML), do not
write a placeholder like `<NAME>` in raw prose -- text that is not
wrapped in a backtick code span or a fenced code block. Markdown/HTML
rendering treats a raw `<NAME>` as an HTML tag and drops it silently,
corrupting the surrounding text (for example a raw `skills/<NAME>/scripts/`
renders as `skills//scripts/`, not the intended placeholder). A code
span or fenced code block renders its contents literally, so
`` `skills/<NAME>/scripts/` `` (backtick-wrapped, as used throughout this
document) is safe as written *on GitHub's own Markdown renderer*; a
bracket-free placeholder (`skills/NAME/scripts/`) is the fallback for a
placeholder that must appear in raw prose with no code formatting at
all.

Backtick-wrapping does **not** protect a PR/issue body from a second,
distinct hazard: an agent that reads its own already-published body back
through the GitHub MCP server (`pull_request_read`, `issue_read`) can see
the same placeholder stripped even though GitHub's own storage and its
own renderer both hold and render the backtick-wrapped span correctly.
That server's response-direction handler runs every returned body
through an HTML sanitizer with a fixed element allowlist that does not
exempt inline code spans, so a `<NAME>`-shaped token inside a backtick
span still reads as a disallowed tag on that one read channel. Issues
#1302 (repair 11) and #1313 (repair 1) each observed exactly this --
backtick-wrapping "did not protect" their occurrence -- and, before issue
#1327's own correction, both misread it as this rule's storage-level
claim being wrong, rather than as a separate read-channel effect this
rule never covered. See `skills/outward-artifact-preflight/SKILL.md`
check 2 for the raw-fetch channel that verifies actual stored content
without going through that sanitizer.

Found via: PR #35's PR body used a `skills/<NAME>/scripts/` placeholder in
prose; GitHub's rendering dropped the `<NAME>` tag, producing
`skills//scripts/` (retrospective #36, repair 2).

Enforcement: `gitapex_check_skill_shape.py`'s `no-raw-angle-bracket-placeholder`
check flags an unclosed `<name>`-shaped token in a skill's `SKILL.md` or
`references/*.md` bare prose, after excluding fenced code blocks, inline
code spans, absolute URLs, and Markdown links (the same exclusions the
script's citation checks already use). A placeholder with a matching
`</name>` closing tag elsewhere in the same bare prose is exempt -- that
shape is a deliberate open/close tag pair, not a fill-in-the-blank
placeholder (see `skills/untrusted-input-triage/SKILL.md`'s own worked
example, which quotes a fake `<system-reminder>...</system-reminder>`
payload as adversarial-input content).

## 5. Canonical hedge phrase for citing a sibling skill under a Portable declaration

A `SKILL.md` declared `Portable` (works unmodified if vendored to another
repository) that needs to name a specific sibling skill by name cannot
lean on a runtime reference to a third skill to excuse that citation --
`gitapex_check_skill_shape.py`'s own hedge-phrase scan
(`GENERIC_ROLE_HEDGE_PHRASES`) is evaluated sentence by sentence: a citing
sentence has to read as sensible on its own, copied into an unrelated
repository, with nothing else present to rescue it. Use this wording,
copied verbatim as a self-contained clause into the citing sentence
itself, never referenced at runtime from another skill:

> (gitapex's own name for this role; if the calling repository has no
> same-named skill, treat this as an illustrative pointer and substitute
> that repository's own skill filling the same role instead)

This unifies the *wording* every Portable skill reaches for, not runtime
resolution: no skill is consulted while a session runs to resolve a
citation this way -- the citing skill's own sentence must already be
correct and readable standalone once vendored elsewhere, exactly the same
way `planning-a-branch-from-an-issue`'s own illustrative-default-plus-
inline-fallback convention already states its own repository-specific
content directly rather than deferring to a third file at read time.

Disclosed non-fix: this wording never rescues a hedge for a dependency
file (a bundled script, a `references/` entry) that lives outside the
citing skill's own directory -- `rubric.md`'s own out-of-folder-dependency
rule allows no hedge at all for that case, Portable or not; the only fix
there is bundling a copy inside the citing skill's own directory.

Found via: `drafting-a-skill`'s own authoring pass named a sibling skill
(`evaluating-skill-quality`) under a `Portable`-shaped citation that did
not satisfy `rubric.md`'s own sentence-level hedge scan; tracked and
re-scoped into this doc via `tvna/gitapex#1173`'s own gap-analysis Update,
after the same finding was first proposed as a citation-time dependency
on a different skill's own runtime presence and found, on inspection, not
to satisfy the sentence-level test that motivated it in the first place.

Enforcement: none yet -- a judgment call at authoring/review time, the
same as Rules 2 and 3 above, until a future checker can verify a
citation's own wording matches this canon.

## 6. A skill's body is behavior, not disclosure

A `SKILL.md` body section (Precondition, Postcondition, Non-goals,
Output, or any other named section) earns its place only when a model
reading the drafted skill at invocation time needs it to act -- a real
caller-side gate, a real handoff guarantee, or a real report the
conductor must hand back. Body content is earned by being Steps a model
executes, or one of two confirmed-operative non-Step exceptions: `Stop
boundaries` (real execution-time constraints) and `Related skills`
(real collision or dependency information a model needs to route
correctly). Everything else non-behavioral -- creation background,
change history, a deliberate scope cut, why a rejected alternative
lost, that a discipline is passively injected with no discrete
entry/exit condition -- belongs in the skill's own
`metadata/gitapex.yaml` sidecar (its `references` decision log, `kind:
elision` for a deliberate scope cut, or `executionRequirements`), never
restated in the body.

This rule is background/rationale for a skill author to apply by hand
while drafting or reviewing; no skill body may cite this document to
satisfy it -- `skills/drafting-a-skill/SKILL.md`'s own Step 2 states the
operative version of this rule directly, inline, consistent with that
skill's own `Broad` capability declaration (a `Broad` skill inlines
enough guidance directly rather than relying only on an on-demand
reference). When a repository-level prohibition would otherwise
invalidate a piece of content a skill's body wants to carry (this file's
own non-redistribution outside `skills/`, for example), try a
conditional reference first -- a stated fallback such as "if X, treat
this as illustrative and substitute Y" -- before falling back to
metadata-only recording; that fallback never rescues a citation to
something categorically absent regardless of context (a bare-prose
`docs/*.md` citation, since this directory is never redistributed to
any consumer of a skill as a plugin), only content whose validity
genuinely varies by context.

Known conflict, disclosed rather than silently resolved:
`skills/evaluating-skill-quality/SKILL.md`'s own Portability section
still instructs the opposite for one content class -- "Extended
rationale belongs in a footer `## Notes` section of `SKILL.md`" -- and
26 of this repository's 29 skills carry exactly such a footer today,
`drafting-a-skill`'s own included. Issue #1583 scoped its dogfooding
migration to that one skill's `Non-goals` section alone, and a skill may
not edit `evaluating-skill-quality` from inside its own change, so this
rule is stated here without a retroactive sweep and without amending
that instruction. Which of the two wins for portability/capability
rationale is an open decision needing its own issue; until it is made,
an existing `## Notes` footer is not a finding against this rule, and a
new skill's author should record that rationale in the sidecar.

Found via: `skills/drafting-a-skill/SKILL.md`'s own Step 2 forced every
drafted skill to carry Precondition/Postcondition sections
unconditionally, and its own Non-goals section was itself an example of
reviewer-only content sitting in the body instead of the metadata
sidecar (issue #1583).

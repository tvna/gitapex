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
`skills/evaluating-skill-quality/scripts/check_skill_shape.py` (the
`no-illustrative-model-identifier` and `no-raw-angle-bracket-placeholder`
checks) against every `SKILL.md` and `references/*.md` file in this
repository's own `skills/` tree, run by `tests/test_repository_skill_shape.py`
on every push and PR. Rules 2 and 3 stay judgment calls -- detecting a
git-log-position assertion or grading test-fixture completeness needs
semantic understanding a script cannot reliably provide -- apply them by
hand at authoring and review time, the same way this file's own source
retrospectives (#20, #122) already did, until a broader eval-suite or
`check_skills.py`-equivalent gate exists for that category (tracked
separately, see issue #11 and #20's gate proposal 1). Content outside
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

Enforcement: `check_skill_shape.py`'s `no-illustrative-model-identifier`
check flags "claude-" followed immediately by a known model-family word
(opus/sonnet/haiku/fable/instant) and a version-like digit, anywhere in a
skill's `SKILL.md` or `references/*.md` -- including inside a fenced code
block or inline code span, since this rule is about the identifier ever
appearing as illustrative content at all, unlike the citation checks in
the same script. `claude-example-model` never matches.

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

`skills/evaluating-skill-quality/scripts/check_skill_shape.py`'s
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
document) is safe as written; a bracket-free placeholder
(`skills/NAME/scripts/`) is the fallback for a placeholder that must
appear in raw prose with no code formatting at all.

Found via: PR #35's PR body used a `skills/<NAME>/scripts/` placeholder in
prose; GitHub's rendering dropped the `<NAME>` tag, producing
`skills//scripts/` (retrospective #36, repair 2).

Enforcement: `check_skill_shape.py`'s `no-raw-angle-bracket-placeholder`
check flags an unclosed `<name>`-shaped token in a skill's `SKILL.md` or
`references/*.md` bare prose, after excluding fenced code blocks, inline
code spans, absolute URLs, and Markdown links (the same exclusions the
script's citation checks already use). A placeholder with a matching
`</name>` closing tag elsewhere in the same bare prose is exempt -- that
shape is a deliberate open/close tag pair, not a fill-in-the-blank
placeholder (see `skills/untrusted-input-triage/SKILL.md`'s own worked
example, which quotes a fake `<system-reminder>...</system-reminder>`
payload as adversarial-input content).

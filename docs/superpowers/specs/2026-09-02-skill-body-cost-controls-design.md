# Design: SKILL.md body cost controls -- line-break integrity, Notes/metadata placement, and a token budget

Date: 2026-09-02

Refs [#1698](https://github.com/tvna/gitapex/issues/1698). Design doc
authored per this repository's own plan-first discipline (`eliciting-a-design`);
issue opened first per this repository's own precedent (every
`docs/superpowers/specs/*.md` doc cites an issue number) and AGENTS.md
section 3's "open an issue before any branch, commit, or PR."

## Summary

Three related gaps in how `SKILL.md` bodies and their `metadata/gitapex.yaml`
sidecars are written, all converged through one `eliciting-a-design` dialogue
because they share a single underlying goal: keeping the `SKILL.md` body's
actual token cost proportional to what it needs to say.

1. Hard-wrapping around 70-74 characters routinely splits an identifier or
   an inline code span across a line break, corrupting the literal string a
   reader would grep for or copy.
2. `references/rubric.md` inconsistently states where extended,
   non-immediately-needed rationale belongs -- a footer `## Notes` section
   of `SKILL.md` in three places, `## Notes` *or* `metadata/gitapex.yaml` in
   a fourth -- with no stated axis for choosing between them.
3. `SKILL.md` bodies have a line-count ceiling (`BODY_MAX_LINES = 500`) but
   no token-count signal, and a real measured gap exists between the two:
   43% of this repository's own skills already exceed a 5,000-token body
   while only 13% exceed 500 lines, because dense hyphenated identifiers and
   code spans inflate token cost per line beyond what a line-count ceiling
   can see.

This document records the agreed shape of the fix for all three; it does
not implement any of them. Per `eliciting-a-design`'s own terminal handoff,
implementation is deferred to a follow-up issue via `drafting-issues`.

## Background

### Evidence: line-break corruption

A line-length histogram over every `skills/*/SKILL.md` and
`skills/*/references/*.md` file in this repository (≈400 files) peaks
sharply at 71-72 characters (2,071 and 1,973 lines respectively) and falls
off fast past 80 (38 lines total above 80). This is consistent with a
habitual ~74-character soft target, not an enforced rule -- no
`.editorconfig`, `.markdownlint*`, or `.prettierrc*` exists in this
repository, and `gitapex_check_skill_shape.py` has no line-length check
today.

Grepping for lines ending in a hyphen inside that same corpus surfaces
dozens of cases where the wrap lands mid-identifier, mid-path, or mid-code
span. Two concrete examples:

- `skills/drafting-a-skill/SKILL.md:123-124`: an inline code span opens as
  `` `references/mechanism-fit-and-` `` and closes on the next line as
  `` cohesion.md` ``. A Markdown renderer collapses the embedded newline to
  a space, so the rendered text reads `references/mechanism-fit-and-
  cohesion.md` (note the injected space before `cohesion.md`) -- the path
  string a reader would try to open or grep no longer matches the real
  file.
- `skills/evaluating-skill-quality/references/rubric.md:250-251`: the same
  pattern splits `` `skills/battle-testing-a-skill/references/provenance-and-caveats.md` ``
  across a line break.

### Evidence: `## Notes` vs. `metadata/gitapex.yaml`

`references/rubric.md`'s own "The mental model" section (lines 56-64)
states the load-cost layering this repository already designs around:
frontmatter `name`+`description` are resident every turn, the `SKILL.md`
body loads wholesale once triggered, and `references/*.md` load only on
demand. `metadata/gitapex.yaml` sits outside this three-layer model
entirely and is explicitly documented as "maintainer-facing, never
auto-loaded" (rubric.md:867), with a working precedent already in place:
bare issue/PR provenance is directed there instead of into body prose
(rubric.md:855-875).

Despite that, the rubric's own guidance on *where extended rationale goes*
is inconsistent:

- Lines 779, 816, and 276 each state, unconditionally, that extended
  rationale (portability rationale, dependency-file rationale, and a
  keep-vs-retire mechanism-fit rationale respectively) "belongs in a
  footer `## Notes` section."
- Lines 1072-1073 instead accept either "the target's own Notes section
  **or** `metadata/gitapex.yaml` decision log" for disclosing a
  Declaration-vs-structure fit tradeoff.

Both destinations exist for the same underlying purpose -- recording *why*
a declaration was made, for a reader who is not executing the procedure --
but only one of the two (`metadata/gitapex.yaml`) is actually free at the
body's load-cost layer. `## Notes` content is paid by every invocation of
the skill; `metadata/gitapex.yaml` is not.

A concrete measurement: `skills/executing-a-branch-plan/SKILL.md`'s own
`## Notes` section is 89 lines / ~1,356 estimated tokens -- 17% of that
skill's entire body. Reading it line by line, the content breaks down as:

| Portion | Lines | Est. tokens | Nature |
|---|---|---|---|
| Portability rationale (why Mixed) | 16 | ~200 | declaration WHY |
| Install/vendoring integrity note | 14 | ~140 | vendoring-time-only warning |
| Bundled-script standalone-run instructions | 23 | ~280 | operational reference, not procedure |
| `origin/main` drift dependency note | 8 | ~90 | dependency provenance |
| Capability assumption rationale (why Adaptive) | 22 | ~320 | declaration WHY, **narrates a past correction** |

The last row ("Was declared `Frontier` by review oversight ... corrected
here") narrates the history of a correction rather than stating only its
current conclusion -- the exact pattern `references/rubric.md` itself
already flags as sediment, not disclosure, at lines 1523-1535 ("Narrating
a correction inside the document's own prose is sediment, not disclosure,
unless the correction itself changes what a reader does"). This is a
concrete instance of the gap this design closes, found by applying the
rubric's own existing rule to the rubric's own worked corpus.

### Evidence: token budget

Primary source: `NVIDIA/SkillEvaluator` (<https://github.com/NVIDIA/SkillEvaluator>),
cloned and read directly (`src/skillevaluator/constants.py`,
`src/skillevaluator/validators/quality_score.py`) since its published docs
(`docs.nvidia.com/skills/skillevaluator/*`) do not state these numbers.

- `QUALITY_RECOMMENDED_MAX_TOKENS = 5000` -- an advisory ceiling on
  `SKILL.md` body token count.
- `QUALITY_MAX_BODY_LINES = 500` -- identical to this repository's own
  `BODY_MAX_LINES`.
- `NAME_MAX_LENGTH = 64`, `DESCRIPTION_MAX_LENGTH = 1024` -- identical to
  this repository's own `NAME_MAX_CHARS`/`DESCRIPTION_MAX_CHARS`.
- Token estimation: `qs.total_tokens = len(content) // 4`
  (quality_score.py:760) -- a plain character-count approximation, no
  external tokenizer dependency.
- `token_efficiency` is explicitly documented as "intentionally
  report-only. Including it here would let token usage alone change the
  canonical quality verdict" (constants.py:543-545) -- SkillEvaluator
  itself does not hard-fail on this metric alone.

This repository's own three matching constants (`NAME_MAX_CHARS`,
`DESCRIPTION_MAX_CHARS`, `BODY_MAX_LINES`) already track
SkillEvaluator's values exactly, establishing a precedent for adopting its
token figure too rather than deriving an unrelated number.

Applying the same `len(content) // 4` estimate to every
`skills/*/SKILL.md` in this repository today:

| Metric | Value |
|---|---|
| Min / Max | 784 / 10,485 tokens |
| Mean / Median | 5,027 / 4,496 tokens |
| Skills over 5,000 tokens | 13 / 30 (43%) |
| Skills over 500 lines (existing `BODY_MAX_LINES`) | 4 / 30 (13%) |

The gap between the two percentages is the concrete evidence for why an
earlier, undocumented attempt to adopt SkillEvaluator was shelved as "too
large a gap": a line-count ceiling this repository already enforces does
not bound the token cost a dense, identifier-heavy body actually carries.

## Decisions

### 1. Line-break rule: forbid an inline code span from crossing a line break

**Rule:** An inline code span (opened and closed by a single backtick pair)
must open and close on the same line. `SKILL.md` bodies and
`references/*.md` files are both in scope; the wrap threshold itself
(the existing ~70-74 character habit) is unchanged -- this only forbids
the specific case where a wrap lands inside a code span.

**Why this shape, not a broader one:** The measured harm is specifically
that a Markdown-collapsed embedded newline injects a space into a path,
identifier, or command string that a reader would copy or grep verbatim.
A code span is exactly the substring class this repository treats as a
literal, copyable token (`references/rubric.md` already singles out
inline code spans for citation-shape rules elsewhere). Constraining
detection to code-span boundaries keeps the check mechanical (count
unescaped backticks per line; an odd count on the line where a span opens,
matched by a closing backtick on a later line, is a violation) with a low
false-positive rate, unlike a heuristic that tries to detect "a hyphenated
word was split" in plain prose generally, which cannot reliably
distinguish a real compound identifier from an ordinary English word
wrapped at a hyphenation point.

**Rejected alternatives** (see the options history in this document's own
Evidence section above for the full three-way tradeoff already agreed with
the repository owner):

- Loosening the wrap threshold to ~100-120 characters: only lowers the
  *probability* of a split, does not eliminate it, and does not address
  the root cause.
- Moving to Semantic Line Breaks (wrap only at sentence/clause boundaries,
  no character-count wrapping at all): eliminates the failure class by
  construction, but requires rewriting the existing corpus wholesale.
  Recorded as a legitimate follow-on migration, out of scope here.

**Verification:** implemented as a new deterministic check inside
`skills/evaluating-skill-quality/scripts/shape_checks/`, following the
existing `CheckResult`-returning function shape used throughout that
package (see `field_checks.py`'s `_no_xml_check`/`_length_check` for the
established pattern: a rule name, a pass/fail bool, a human-readable rule
statement, and the observed evidence string). Exact module placement and
function name are left to the implementing PR; this design fixes only the
detection rule and its scope.

### 2. `## Notes` vs. `metadata/gitapex.yaml`: an axis, not a per-case rule

**Axis:** does a reader of `SKILL.md`, in the ordinary course of reading
the file to use or review the skill, need this information *at that
moment*?

- **Yes -> `## Notes`, kept short.** A declaration itself (e.g.
  "Portability: Mixed", "Capability assumption: Adaptive") and any warning
  a reader must see before acting (e.g. a live vendoring-integrity caveat)
  stay in `## Notes` as one to two sentences -- a pointer, not the full
  case.
- **No -> `metadata/gitapex.yaml`'s `spec.references`.** The *why* behind
  a declaration, decision history, audit outcomes, and correction
  narration (per the existing sediment rule at rubric.md:1523-1535) move
  to a `spec.references` entry, using the existing `kind` vocabulary
  (`decision`, `audit`, `deferral`, `corroboration`, `caveat`, `elision`,
  `correction`) and the existing 500-character `summary` cap. A skill
  needing to walk through *how* to run a bundled script standalone (not a
  rationale, but usable operational content) belongs in `references/`
  instead, loaded on demand, not in either of these two.

**Resolves the existing inconsistency:** replaces the unconditional
"belongs in `## Notes`" statements at rubric.md:779, 816, and 276 with
this axis, and resolves the "Notes section or metadata" ambiguity at
rubric.md:1072-1073 by making the choice depend on the axis rather than
being either author's free choice.

**Schema impact (flagged, not resolved here):** whether the existing
`REFERENCES_KIND_VOCAB` (seven kinds) can express every case migrated out
of `## Notes` -- particularly a Capability-assumption-declaration rationale,
which does not cleanly fit `decision`/`audit`/`correction` alone -- needs
checking against `skill-metadata.schema.json` during implementation. This
design does not resolve that; it is named as an explicit open question
below.

### 3. `SKILL.md` body token budget: 5,000 tokens, body only, tiered enforcement

- **Scope:** `SKILL.md` body only. `references/*.md` files are explicitly
  exempt from both this token ceiling and the existing line-count ceiling
  -- a reference file's job is to be scoped to one topic (conciseness of
  *role*), not to be short in absolute terms, per the repository owner's
  own stated position that a reference's target is focused scope, not
  brevity for its own sake.
- **Estimator:** `len(content) // 4`, identical to SkillEvaluator's own
  formula. Chosen over a real tokenizer (e.g. `tiktoken`) specifically to
  avoid adding a new runtime dependency to a `StdlibOnly`-capable checker,
  and to keep this repository's numbers directly comparable to
  SkillEvaluator's own reporting. This is a rough approximation, not
  Claude's actual tokenizer -- a real BPE tokenizer would count
  frequently-repeated compound identifiers and code-heavy content
  differently in either direction. The estimate is for a body-cost signal,
  not a billing-accurate count.
- **Threshold:** 5,000 tokens, matching SkillEvaluator's own
  `QUALITY_RECOMMENDED_MAX_TOKENS` and this repository's own already-shared
  64/1024/500 precedent.
- **Enforcement tier:** a brand-new skill drafted via `drafting-a-skill`
  FAILs this check hard. An existing skill already over the threshold at
  the time this check ships gets an advisory finding only (matching
  SkillEvaluator's own "report-only, does not change the canonical
  verdict" design for `token_efficiency`) -- migrating the 13 skills
  already over 5,000 estimated tokens is out of scope for this design and
  becomes separate follow-up work, not a blocking gate on this change.

## Scope

In scope: recording the three decisions above and their rationale, ready
for `drafting-issues` to turn into an Acceptance Criteria Map.

Out of scope (explicitly deferred, not silently dropped):

- Writing the actual regex/AST detection logic for Decision 1, the token
  counter and threshold branch for Decision 3, and the corresponding
  `rubric.md` prose edits for Decision 2 -- all implementation, deferred
  to the issue this design hands off to.
- Migrating any of the 13 skills currently over the 5,000-token advisory
  threshold, or rewriting `executing-a-branch-plan/SKILL.md`'s own
  `## Notes` section as a worked example of Decision 2 -- both are
  legitimate follow-on cleanup, not blocking this design.
- A full migration to Semantic Line Breaks (rejected alternative under
  Decision 1) -- named as a possible future direction only.
- Resolving the `REFERENCES_KIND_VOCAB` schema-fit open question under
  Decision 2.

## Facts vs. speculation

**Facts** (directly observed this session): the line-length histogram and
its two cited code-span-split examples; the exact text of
`references/rubric.md` lines 56-64, 779, 816, 276, 867, 855-875,
1072-1073, and 1523-1535; the `executing-a-branch-plan/SKILL.md`
`## Notes` line-by-line breakdown; every SkillEvaluator constant and
formula cited above, read directly from its cloned source; the
30-skill token/line measurement table.

**Speculation** (flagged as such, not asserted as fact): that the ~74
character wrapping habit originates from an authoring-time (model-side)
tendency rather than a lost or unrecovered tool config -- no config file
was found either way, and no repository history was searched to confirm
this beyond the absence of a current config; that a prior SkillEvaluator
adoption attempt used the same measurement this document uses -- no
record of that prior attempt exists anywhere in this repository, only in
the repository owner's own account of it.

## Open questions

1. Does `skill-metadata.schema.json`'s `REFERENCES_KIND_VOCAB` need a new
   `kind` value (or does an existing one stretch to cover it) for a
   Capability-assumption-declaration rationale migrated out of `## Notes`
   under Decision 2? Needs checking against real migrated content during
   implementation, not decided here.
2. Exact module/function placement for the two new
   `gitapex_check_skill_shape.py` checks (Decision 1's code-span check,
   Decision 3's token-budget check) -- left to the implementing PR.

## References

- NVIDIA/SkillEvaluator: <https://github.com/NVIDIA/SkillEvaluator>
  (`src/skillevaluator/constants.py`, `src/skillevaluator/validators/quality_score.py`,
  read directly this session)
- `skills/evaluating-skill-quality/references/rubric.md` (this
  repository), lines cited inline above
- `skills/executing-a-branch-plan/SKILL.md` (this repository), `## Notes`
  section

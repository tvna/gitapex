"""Higher-level prose citation checks (issue/PR numbers, cross-skill
references, mechanism-fit, illustrative model IDs, raw placeholders,
step-location, portable-skill path/fact-claim/demonstrative-repository
citations) built on citations.py and links_portability.py."""

from __future__ import annotations

import re
from pathlib import Path

from shape_checks.citations import (
    _blank_fenced_blocks,
    _dedup,
    _inline_citation_offenders,
    _portable_citation_offenders,
    _strip_illustrative_spans,
)
from shape_checks.constants import (
    _INLINE_CITATION_CHECK_SPECS,
    _PARAGRAPH_SPLIT_RE,
    _SENTENCE_SPLIT_RE,
    ANTHROPIC_DOC_CITATION_RE,
    AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE,
    AUTHORITY_VIOLATION_HEDGE_RE,
    AUTHORITY_VIOLATION_NEGATION_RE,
    AUTHORITY_VIOLATION_RE,
    CATALOG_QUOTE_EXEMPTION_MARKER_RE,
    CROSS_SKILL_CITATION_RE,
    DEMONSTRATIVE_ORIGIN_REPOSITORY_RE,
    DIMENSION_QUOTE_EXEMPTION_RE,
    HEDGE_PHRASES,
    ILLUSTRATIVE_MODEL_ID_RE,
    INLINE_CODE_RE,
    ISSUE_CITATION_RE,
    MECHANISM_FIT_CITATION_RE,
    MECHANISM_FIT_HEADING_RE,
    MECHANISM_FIT_REASONED_EXTENSION_PHRASE,
    NUMBERED_CATALOG_HEADING_RE,
    PORTABLE_SKILL_FACT_CLAIM_RE,
    QUOTED_LINE_RULE_RE,
    RAW_PLACEHOLDER_OPEN_RE,
    REPO_PATH_CITATION_RE,
    STEP_LOCATION_ASSERTION_RE,
    STEP_LOCATION_CEDING_PHRASE,
    STEP_NUM_RE,
    UNTRUSTED_DECLARATION_RE,
    CheckResult,
)
from shape_checks.links_portability import (
    _body_after_frontmatter,
    _cached_target_heading_slugs,
    _github_slug,
    _is_ignorable,
    _resolves_to_sibling_skill,
)


def _external_citation_declaration_offenders(
    external_citations: list[dict[str, object]], skill_md: Path, skill_dir: Path, body: list[str]
) -> list[str]:
    """Return each ``spec.externalCitations`` declared ``path`` (issue
    #1055) with no literal, exact match against a real citation-shaped
    token anywhere in SKILL.md or references/*.md -- a stale declaration
    naming a citation this skill no longer actually carries. Matches
    ``_citation_sources``' own raw, unfenced text (a declared path
    legitimately citing an illustrative fenced example is still a real
    citation this check should find), the same exact-literal matching Q3
    of issue #1055's design decision settled on -- deliberately not a
    regex or line-anchored match, mirroring how a declaration is expected
    to quote its own citation's exact text.

    Matched against ``REPO_PATH_CITATION_RE``'s own extracted tokens, not
    a raw substring test over the whole haystack: a plain ``path in
    haystack`` check would let a declaration for ``docs/a.md`` falsely
    "resolve" against a real, different citation like ``docs/a.mdx`` --
    ``docs/a.md`` is a literal prefix of it -- since the character class
    ``REPO_PATH_CITATION_RE`` accepts (including ``.``) makes prefix
    overlap between two distinct real citations possible. Anchoring to
    the regex's own extracted tokens keeps "exact literal match" exact.

    A trailing ``".,;:)"`` is stripped from each extracted token before
    the match, the same established fix (a prior review finding) already
    applied to ``SCRIPTS_PATH_BARE_RE``'s own bare-prose matches below:
    sentence-final punctuation immediately after a real extension (e.g.
    "documented in docs/a.md.") is captured by this regex's own character
    class -- which must include "." for real extensions -- and would
    otherwise make a genuine, correctly declared citation report as stale
    purely because of how its sentence ends; no real path ends in one of
    these characters, so stripping them is never lossy.
    """
    haystack = "\n".join(source_text for _label, source_text in _citation_sources(skill_md, skill_dir, body))
    cited_tokens = frozenset(m.group(0).rstrip(".,;:)") for m in REPO_PATH_CITATION_RE.finditer(haystack))
    offenders = []
    for entry in external_citations:
        path = entry.get("path")
        if isinstance(path, str) and path and path not in cited_tokens:
            offenders.append(path)
    return offenders


def _citation_sources(skill_md: Path, skill_dir: Path, body: list[str]) -> list[tuple[str, str]]:
    """Return (label, body-text) for SKILL.md and every references/ file,
    Markdown or not -- the shared source set every prose citation/
    placeholder/mechanism-fit check built on this function scans.
    Deliberately NOT limited to references/*.md: a bundled non-Markdown
    dependency file (e.g. a JSON schema) still carries author-written
    English in its own description strings, and exempting it by extension
    would let a bare issue citation, an illustrative model identifier, an
    unhedged repo-path citation, or a raw placeholder hide from every one
    of these checks just by living in a `.json`/`.yaml`/`.txt` file instead
    of a `.md` one -- a real bypass a corpus-wide adversarial pass found
    when this exemption was first tried (issue #834 follow-up). The
    Markdown-syntax-specific checks (TOC-heading presence,
    links-inside-skill, anchor-targets-resolve) stay .md-only, in the
    separate references/ loop (``shape_checks/orchestrator.py``'s
    ``_references_dir_checks``) -- those really are Markdown conventions a
    non-Markdown file has no notion of; the prose checks built on this
    function are not.
    """
    sources: list[tuple[str, str]] = [(skill_md.name, "\n".join(body))]
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            sources.append((f"references/{ref.name}", "\n".join(_body_after_frontmatter(ref_text))))
    return sources


def _issue_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], extra_sources: list[tuple[str, str]] | None = None
) -> list[CheckResult]:
    """The bare GitHub issue/PR-number citation scan over SKILL.md body,
    references/*.md, and (unlike every other check built on
    ``_citation_sources``) the metadata/gitapex.yaml sidecar's own
    spec.references entries and lifecycle.experimental/deprecated.reason
    text, passed in via ``extra_sources``. A bare number in the sidecar
    loses its meaning the moment the sidecar travels with its skill
    directory to another repository, so this scan covers the sidecar's
    own free text too. A full
    ``https://github.com/...`` URL contains no bare ``#N`` and so is never
    flagged here -- that is what makes a full URL the only way left to cite
    an issue from the sidecar, with no separate format regex needed. Runs
    unconditionally on every skill regardless of declared portability level
    -- unlike ``_portable_path_citation_checks`` below, the caller does not
    gate this one on ``_is_portable``.

    ``extra_sources`` (the sidecar text) is scanned with the bare
    ``ISSUE_CITATION_RE`` regex directly, NOT through
    ``_portable_citation_offenders``/``_strip_illustrative_spans`` the way
    SKILL.md/references/*.md are: that
    stripping exempts an inline-code span (`` `#149` ``) as an
    "already illustrative, does not resolve live" citation form -- true in
    rendered Markdown, where backticks make GitHub's auto-linker leave the
    text alone, but meaningless inside a YAML string scalar, where a
    backtick is just a literal character. Applying that exemption to the
    sidecar would let a provenance entry write "fixed in `` `gitapex#25` ``"
    and pass unflagged, defeating the full-URL-only rule this check exists
    to enforce there.
    """
    issue_hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        issues, _paths = _portable_citation_offenders(defenced)
        issue_hits += [f"{label}:{c}" for c in issues]
    for label, source_text in extra_sources or ():
        issue_hits += [f"{label}:{c}" for c in _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(source_text))]

    return [
        CheckResult(
            "no-bare-issue-citation",
            not issue_hits,
            "No bare-prose GitHub issue/PR-number citation, at any portability level",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits),
        ),
    ]


def _cross_skill_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], slug_cache: dict[Path, frozenset[str] | None]
) -> list[CheckResult]:
    """Every cross-skill "file+heading" citation
    (CROSS_SKILL_CITATION_RE) in SKILL.md or references/*.md must resolve --
    the sibling skill directory exists (a cheaper version of this,
    directory-only, is already covered by ``related-skill-references-resolve``
    and ``skill-dependencies-resolve``), the named file exists inside that
    sibling's own references/ directory, and a heading matching the cited
    text actually exists in that file -- reusing ``_github_slug``/
    ``_heading_slugs`` verbatim, the same GitHub heading-slug logic
    ``anchor-targets-resolve`` already implements for real Markdown links.
    Unlike a real Markdown link, a citation in this prose shape can never be
    a same-repo relative link (a cross-skill target cannot legally resolve
    inside the CITING skill's own directory, per ``links-inside-skill``), so
    neither ``links-inside-skill`` nor ``anchor-targets-resolve`` ever sees
    it -- this is the dedicated backstop for exactly that gap. Runs
    unconditionally, at every portability level, the same as
    ``no-bare-issue-citation`` above: a dangling cross-skill citation is a
    defect regardless of declared portability.

    Each cited heading is slugged with its OWN fresh, empty occurrence
    table (not the target file's real per-document dedup table) -- a prose
    citation names a heading's TEXT, and this checker has no way to know
    which same-slug occurrence (1st, 2nd, ...) the author meant, so it
    accepts a match against the base (first-occurrence) slug only.

    ``slug_cache`` is ``check_shape``'s own ``anchor_slug_cache`` -- the
    SAME ``Path``-keyed cache ``anchor-targets-resolve`` already shares
    across SKILL.md and every references/*.md file -- reused here (via
    ``_cached_target_heading_slugs``) rather than this function keeping an
    independent ``(skill_name, filename)``-keyed cache of its own: two
    caches with the identical read-once/frontmatter-strip/heading-slugs/
    None-on-error contract would have to be kept in sync by hand, and a
    sibling skill's own SKILL.md or references/*.md file cited here might
    already be a cached anchor target from this same run's earlier checks.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        for m in CROSS_SKILL_CITATION_RE.finditer(defenced):
            skill_name, filename, heading_text = m.group(1), m.group(2), m.group(3)
            citation = m.group(0)
            sibling_dir = skill_dir.parent / skill_name
            if not sibling_dir.is_dir():
                offenders.append(f"{label}:{citation} (no such sibling skill)")
                continue
            target = sibling_dir / "references" / filename
            slugs = _cached_target_heading_slugs(target, slug_cache)
            if slugs is None:
                offenders.append(f"{label}:{citation} (file not found)")
                continue
            if _github_slug(heading_text, {}) not in slugs:
                offenders.append(f"{label}:{citation} (heading not found)")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "cross-skill-citation-resolves",
            not offenders,
            'Every "SKILL-NAME\'s `references/FILE.md` HEADING section" '
            "cross-skill citation resolves to a real sibling skill, file, "
            "and heading",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _mechanism_fit_citation_offenders(body_text: str) -> list[str]:
    """Return each '### ' subsection heading text nested under
    a '## Mechanism fit' heading in ``body_text`` that carries neither a
    '[label]'-style citation (MECHANISM_FIT_CITATION_RE) nor the literal
    phrase "this repository's own reasoned extension" --
    mechanizing the completeness rule references/rubric.md's own
    Mechanism-fit section intro already states in prose ("the primary
    source and the reasoning behind each check").

    Generic over ANY document, not hardcoded to rubric.md's filename -- a
    document with no '## Mechanism fit' heading at all contributes zero
    offenders (the same "not applicable, trivially passes" shape the
    references-flat/TOC checks already use for a precondition that does not
    apply to every skill). Only a level-2 '## Mechanism fit' heading is
    recognized (case-insensitive on its text, exact heading level); its own
    section span runs from immediately after it to the next heading at
    level <= 2 (or end of document), and only '### ' (level-3) headings
    inside that span count as its subsections -- a deeper '#### ' heading
    nested under a level-3 subsection is part of that subsection's own
    content, not a sibling subsection needing its own citation.
    """
    defenced = _blank_fenced_blocks(body_text)
    headings = [(m.start(), len(m.group(1)), m.group(2)) for m in MECHANISM_FIT_HEADING_RE.finditer(defenced)]
    offenders: list[str] = []
    for i, (_start, level, text) in enumerate(headings):
        if level != 2 or text.strip().lower() != "mechanism fit":
            continue
        section_end = next((s for s, lv, _t in headings[i + 1 :] if lv <= 2), len(defenced))
        subsections = [(s, t) for s, lv, t in headings[i + 1 :] if s < section_end and lv == 3]
        for j, (sub_start, sub_text) in enumerate(subsections):
            sub_end = subsections[j + 1][0] if j + 1 < len(subsections) else section_end
            content = defenced[sub_start:sub_end]
            has_citation = bool(MECHANISM_FIT_CITATION_RE.search(content))
            has_phrase = MECHANISM_FIT_REASONED_EXTENSION_PHRASE in content.lower()
            if not (has_citation or has_phrase):
                offenders.append(sub_text.strip())
    return offenders


def _mechanism_fit_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _mechanism_fit_citation_offenders,
    scanning SKILL.md and every references/*.md file the same way every
    other _citation_sources-based check does. Runs unconditionally, at
    every portability level -- a missing citation is a completeness defect,
    not a portability one.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for heading in _mechanism_fit_citation_offenders(source_text):
            offenders.append(f"{label}:{heading}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "mechanism-fit-subsections-cite-sources",
            not offenders,
            "Every '### ' subsection under a '## Mechanism fit' heading "
            "carries a '[label]'-style citation or the literal phrase "
            '"this repository\'s own reasoned extension"',
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _illustrative_model_id_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """docs/skill-authoring-standards.md rule 1: no real, current Claude
    model identifier as illustrative content in SKILL.md or references/*.md,
    even inside a fenced "bad example" that is itself flagged and fixed.
    Unlike every citation check in this module, this deliberately does NOT
    strip fenced code blocks or inline code spans first: rule 1 is about the
    identifier ever appearing as illustrative content at all, not about it
    resolving live, so a real model ID inside a worked example is exactly
    what this check exists to catch, not something to exempt.

    One narrow exemption: a match that falls entirely inside an
    ANTHROPIC_DOC_CITATION_RE span (a real citation URL to Anthropic's own
    docs, not illustrative content) does not count as an offender -- see
    that constant's own docstring for why.
    """
    offenders: list[str] = []
    for label, text in _citation_sources(skill_md, skill_dir, body):
        citation_spans = [m.span() for m in ANTHROPIC_DOC_CITATION_RE.finditer(text)]
        for m in ILLUSTRATIVE_MODEL_ID_RE.finditer(text):
            if any(start <= m.start() and m.end() <= end for start, end in citation_spans):
                continue
            offenders.append(f"{label}:{m.group(0)}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-illustrative-model-identifier",
            not offenders,
            "No real, current Claude model identifier as illustrative "
            "content (docs/skill-authoring-standards.md rule 1)",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _raw_placeholder_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """docs/skill-authoring-standards.md rule 4: no angle-bracket
    placeholder ("<NAME>") in raw prose -- outside a code span or fenced
    code block -- in SKILL.md or references/*.md. GitHub's Markdown/HTML
    rendering drops an unescaped "<NAME>" silently, corrupting the
    surrounding text.

    A placeholder whose matching closing tag ("</name>", same name,
    case-insensitive) also appears in the same bare prose is exempt: that
    open/close pairing marks a genuine HTML-shaped tag being quoted as
    content, not an unclosed fill-in-the-blank placeholder -- e.g. this
    repository's own untrusted-input-triage worked example, which
    deliberately quotes a fake "<system-reminder>...</system-reminder>"
    payload as adversarial-input content.
    """
    offenders: list[str] = []
    for label, text in _citation_sources(skill_md, skill_dir, body):
        bare = _strip_illustrative_spans(_blank_fenced_blocks(text))
        lowered = bare.lower()
        for match in RAW_PLACEHOLDER_OPEN_RE.finditer(bare):
            if f"</{match.group(1).lower()}>" in lowered:
                continue
            offenders.append(f"{label}:{match.group(0)}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-raw-angle-bracket-placeholder",
            not offenders,
            "No angle-bracket placeholder in raw prose (docs/skill-authoring-standards.md rule 4)",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _step_location_offenders(body_text: str) -> list[str]:
    """Issue #192 (Refs #93 repair 1): fail when the same numbered step
    (STEP_NUM_RE) is asserted to execute in two different locations
    (STEP_LOCATION_ASSERTION_RE) within ``body_text``, with neither
    mention explicitly ceding authority to the other
    (STEP_LOCATION_CEDING_PHRASE) -- the exact defect shape issue #93's
    own incident found (SKILL.md's Procedure intro said step 6 "stays in
    the main thread" while its Subagent dispatch section required step 6
    to "execute inside" the dispatch, with nothing reconciling the two).

    Scans sentence-by-sentence (``shape_checks/constants.py``'s
    ``_SENTENCE_SPLIT_RE``, this checker's own sentence tokenizer, shared
    with the skill-fact-claim hedge-proximity check) rather than the whole
    document at once: a step number and a
    location assertion are only read as related when they co-occur in the
    SAME sentence -- two unrelated sentences that separately happen to
    mention some step number and some location phrase, with no shared
    clause connecting them, are not the contradiction this check exists to
    catch. Two mentions of the SAME step number with the SAME location
    phrase are not a contradiction either (restating one fact twice is not
    a conflict) -- only genuinely distinct location phrases for one step
    number count. A sentence naming more than one step number, or
    asserting more than one location phrase, is skipped entirely (a
    review finding: pairing the sentence's FIRST step-number match with
    its FIRST location match via independent ``.search()`` calls can
    misattribute one step's location claim to a different step number
    named in the same sentence) rather than guessed at -- unambiguous
    single-step-number, single-location-phrase sentences are the only
    shape this check reads, matching this check's own deliberately narrow
    scope.

    Illustrative spans (inline code, Markdown links, absolute URLs -- see
    ``_strip_illustrative_spans``) are stripped before scanning, the same
    as every other bare-prose check in this file (a review finding: an
    inline-code-quoted illustration of issue #93's own incident -- this
    repository's own established way of documenting a "bad example," see
    e.g. rubric.md's citation checks -- would otherwise trip this check as
    a real contradiction).

    A ceding phrase only resolves the SPECIFIC pair of distinct location
    phrases where at least one side's own sentence carries it, not every
    contradiction recorded for that step number (a review finding: one
    ceding sentence would otherwise silently drop an unrelated, genuinely
    unreconciled third location for the same step).
    """
    bare = _strip_illustrative_spans(_blank_fenced_blocks(body_text))
    by_step: dict[str, list[tuple[str, bool]]] = {}
    for sentence in _SENTENCE_SPLIT_RE.split(bare):
        step_matches = list(STEP_NUM_RE.finditer(sentence))
        location_matches = list(STEP_LOCATION_ASSERTION_RE.finditer(sentence))
        if len(step_matches) != 1 or len(location_matches) != 1:
            continue
        step_num = step_matches[0].group(1)
        has_ceding = STEP_LOCATION_CEDING_PHRASE in sentence.lower()
        phrase = " ".join(location_matches[0].group(0).split()).rstrip(".,;:")
        by_step.setdefault(step_num, []).append((phrase, has_ceding))

    offenders: list[str] = []
    for step_num in sorted(by_step, key=int):
        phrase_ceding: dict[str, bool] = {}
        for phrase, ceding in by_step[step_num]:
            phrase_ceding[phrase] = phrase_ceding.get(phrase, False) or ceding
        distinct_phrases = list(phrase_ceding)
        if len(distinct_phrases) < 2:
            continue
        unresolved = [
            (a, b)
            for i, a in enumerate(distinct_phrases)
            for b in distinct_phrases[i + 1 :]
            if not (phrase_ceding[a] or phrase_ceding[b])
        ]
        if not unresolved:
            continue
        offenders.append(f"step {step_num}: " + "; ".join(f"{a!r} vs. {b!r}" for a, b in unresolved))
    return offenders


def _step_location_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _step_location_offenders, scanning
    SKILL.md and every references/*.md file the same way every other
    _citation_sources-based check does -- each file checked independently,
    never merging step numbers across files (a references/*.md file's own
    local "step 3" is unrelated to SKILL.md's own step 3). Runs
    unconditionally, at every portability level -- a same-file internal
    contradiction about where a step executes is a completeness/consistency
    defect, not a portability one, the same reasoning
    mechanism-fit-subsections-cite-sources above already uses.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for offender in _step_location_offenders(source_text):
            offenders.append(f"{label}:{offender}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-step-location-contradiction",
            not offenders,
            "No 'step N'/'steps N-M' reference is asserted to execute in "
            "two different locations without one explicitly ceding "
            f"authority (a nearby {STEP_LOCATION_CEDING_PHRASE!r})",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _untrusted_authority_crossover_offenders(body_text: str) -> list[str]:
    """Issue #192 item 4 (Refs #24 repairs 1, 4): flag a file that both
    declares some content untrusted (``UNTRUSTED_DECLARATION_RE``) and
    also applies an authority-granting verb to it
    (``AUTHORITY_VIOLATION_RE``) with no nearby hedge or negation -- the
    exact defect shape issue #24 repair 1's own incident found
    (``issue-to-branch``'s Step 1 declared comments untrusted; Step 3 let
    any comment narrow/override the issue body's scope with no
    restriction).

    File-level, not sentence-level, co-occurrence -- deliberately broader
    than ``_step_location_offenders`` above's own sentence-level scope.
    This check's own grounding incident spans different Procedure steps
    (a declaration in one step, a violation in another), so scanning only
    within one sentence would very likely miss the exact incident this
    check exists to catch; see the design doc
    (``docs/superpowers/specs/2026-08-30-issue-192-untrusted-consistency-and-item-coverage-design.md``,
    "Scope and shipping bar") for the considered reasoning behind this
    deliberate asymmetry with the sibling check's own scope.

    Illustrative spans (inline code, Markdown links, absolute URLs) and
    fenced code blocks are stripped before scanning, the same discipline
    every other bare-prose check in this file already applies.

    Each violation match is evaluated against its own containing
    suppression unit only: a negation (``AUTHORITY_VIOLATION_NEGATION_RE``)
    or hedge (``AUTHORITY_VIOLATION_HEDGE_RE``) anywhere in that unit
    suppresses every violation match in that same unit, the same simple
    substring-style suppression ``STEP_LOCATION_CEDING_PHRASE`` above
    already uses -- never a file-wide suppression, which would let one
    unrelated hedged sentence silently clear a genuine, unhedged violation
    elsewhere in the file.

    A unit is a sentence (``_SENTENCE_SPLIT_RE``) that additionally never
    spans two Markdown list items (``AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE``).
    The list-item break is load-bearing, not cosmetic: ``_SENTENCE_SPLIT_RE``
    only breaks after ``.``/``!``/``?``, so a Procedure or Stop-boundaries
    list written without terminal punctuation is one single "sentence", and
    a ``- Never ...`` bullet would then clear a genuine violation stated in
    a different bullet -- reaching the file-wide-suppression failure mode
    this docstring rules out, through the back door (found by the issue
    #192 step 8 adversarial review, whose defeat case is pinned as a
    regression test in the sibling test module).
    """
    bare = _strip_illustrative_spans(_blank_fenced_blocks(body_text))
    if not UNTRUSTED_DECLARATION_RE.search(bare):
        return []
    offenders: list[str] = []
    for block in AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE.split(bare):
        for unit in _SENTENCE_SPLIT_RE.split(block):
            if not AUTHORITY_VIOLATION_RE.search(unit):
                continue
            if AUTHORITY_VIOLATION_NEGATION_RE.search(unit):
                continue
            if AUTHORITY_VIOLATION_HEDGE_RE.search(unit):
                continue
            for match in AUTHORITY_VIOLATION_RE.finditer(unit):
                offenders.append(" ".join(match.group(0).split()))
    return offenders


def _untrusted_authority_crossover_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for
    _untrusted_authority_crossover_offenders, scanning SKILL.md and every
    references/*.md file the same way every other _citation_sources-based
    check does -- each file checked independently, never pairing a
    declaration in one file with a violation in a different file. Runs
    unconditionally, at every portability level -- a same-file internal
    declaration/violation contradiction is a completeness/consistency
    defect, not a portability one, the same reasoning
    mechanism-fit-subsections-cite-sources and _step_location_checks
    above already use.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for offender in _untrusted_authority_crossover_offenders(source_text):
            offenders.append(f"{label}:{offender}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-untrusted-authority-crossover",
            not offenders,
            "No already-declared-untrusted content has an authority-granting "
            "verb (override/narrow the scope) applied to it with no nearby "
            "hedge or negation",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _dimension_quote_exemption_offenders(skill_text: str, ref_sources: list[tuple[str, str]]) -> list[str]:
    """Return one offender string per dimension number where SKILL.md's
    quoted-line-rule exemption clause and a references/ catalog's own
    structural-exemption marker disagree about whether that dimension is
    exempt (Refs #79 repair 1, re-scoped by #577 from #192's row 5).

    Trivially returns no offenders when ``skill_text`` states no blanket
    "quote the exact offending line" rule at all (``QUOTED_LINE_RULE_RE``)
    -- with no blanket rule, a catalog's own structural-exemption marker
    contradicts nothing. This is deliberately NOT "every Fail/Pass example
    needs a backtick or an exemption marker": #577 found that reading fails
    CI on roughly 18 of adversarial-dimensions.md's 22 real dimensions
    today, none of which ever claim to quote a SKILL.md line in the first
    place -- only the dimension(s) SKILL.md itself names as exempt, and any
    catalog section that claims the same structural exemption, are in
    scope here.

    Both ``skill_text`` and every ``ref_sources`` entry are passed through
    ``_strip_illustrative_spans(_blank_fenced_blocks(...))`` first, the same
    as ``_step_location_offenders`` above -- a review finding: an earlier
    revision scanned raw, un-defenced text, so a fenced "do not write like
    this" illustration of the quoted-line rule (the same issue #93 pattern
    _step_location_offenders' own docstring guards against) was read as a
    real assertion.
    """
    bare_skill_text = _strip_illustrative_spans(_blank_fenced_blocks(skill_text))
    if not QUOTED_LINE_RULE_RE.search(bare_skill_text):
        return []

    skillmd_exempt: set[str] = set()
    for m in DIMENSION_QUOTE_EXEMPTION_RE.finditer(bare_skill_text):
        skillmd_exempt.update(re.findall(r"\d+", m.group(1)))

    catalog_exempt: set[str] = set()
    for _label, ref_text in ref_sources:
        defenced = _strip_illustrative_spans(_blank_fenced_blocks(ref_text))
        headings = [(m.start(), m.group(1)) for m in NUMBERED_CATALOG_HEADING_RE.finditer(defenced)]
        for i, (start, num) in enumerate(headings):
            end = headings[i + 1][0] if i + 1 < len(headings) else len(defenced)
            if CATALOG_QUOTE_EXEMPTION_MARKER_RE.search(defenced[start:end]):
                catalog_exempt.add(num)

    offenders: list[str] = []
    for num in sorted(skillmd_exempt - catalog_exempt, key=int):
        offenders.append(
            f"dimension {num}: SKILL.md's quoted-line rule names it exempt, but no "
            "references/ catalog section marks it structurally exempt"
        )
    for num in sorted(catalog_exempt - skillmd_exempt, key=int):
        offenders.append(
            f"dimension {num}: a references/ catalog section marks it structurally "
            "exempt from quoting a SKILL.md line, but SKILL.md's quoted-line rule "
            "does not name it exempt"
        )
    return offenders


def _dimension_quote_exemption_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _dimension_quote_exemption_offenders.
    Runs unconditionally, at every portability level -- a same-repo
    cross-file exemption contradiction is a completeness/consistency
    defect, not a portability one, the same reasoning
    _step_location_checks above already uses.

    SKILL.md is always ``_citation_sources``'s own first entry (see that
    function's own body); every remaining entry is a references/ file, the
    only place a catalog's own structural-exemption marker can live.
    """
    sources = _citation_sources(skill_md, skill_dir, body)
    skill_text = sources[0][1]
    ref_sources = sources[1:]
    offenders = _dedup(_dimension_quote_exemption_offenders(skill_text, ref_sources))
    return [
        CheckResult(
            "dimension-quote-exemption-cross-reference",
            not offenders,
            "Every dimension SKILL.md's quoted-line rule names as exempt is marked "
            "structurally exempt in a references/ catalog section, and vice versa",
            "none" if not offenders else "found: " + "; ".join(offenders),
        ),
    ]


def _portable_path_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], declared_citation_paths: frozenset[str] = frozenset()
) -> list[CheckResult]:
    """The Portable-only repo-path and inline-code-issue-number self-citation
    checks over SKILL.md body and references/*.md. Each source contributes
    its offenders labelled by file, so a failure points at the exact file to
    fix. Only called when ``_is_portable`` is true (see ``check_shape``) --
    unlike the bare-prose issue-number scan in ``_issue_citation_checks``,
    every check here stays level-gated (see the module docstring's
    bare-issue-citation entry for why the bare-prose scan is different,
    and the issue-number citation entry for why the inline-code
    issue-number check joins the two repo-path checks here rather than
    the unconditional one).

    ``declared_citation_paths`` (issue #1055) is the skill's own
    well-formed ``spec.externalCitations`` path set -- passed through to
    ``portable-no-inline-path-citation`` only (via ``_inline_citation_offenders``'s
    ``declared_paths``), supplementing ``GENERIC_ROLE_HEDGE_PHRASES`` rather
    than replacing it, per this issue's own design decision. Deliberately
    NOT applied to ``portable-no-repo-path-citation`` (the bare-prose form)
    or the issue-number spec -- both stay out of scope, per the issue's own
    Non-goals.
    """
    path_hits: list[str] = []
    inline_hits_per_spec: list[list[str]] = [[] for _ in _INLINE_CITATION_CHECK_SPECS]
    inline_specs = tuple(
        (
            citation_re,
            hedge_phrases,
            declared_citation_paths if name == "portable-no-inline-path-citation" else frozenset(),
        )
        for name, citation_re, hedge_phrases, _label in _INLINE_CITATION_CHECK_SPECS
    )
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        # Fence-blanked once and shared -- the bare-prose scan and the
        # inline-code scan (itself now one pass covering every spec in
        # _INLINE_CITATION_CHECK_SPECS) both need fenced code excluded the
        # same way, and source_text can be a multi-hundred-line references/
        # file.
        defenced = _blank_fenced_blocks(source_text)
        _issues, paths = _portable_citation_offenders(defenced)
        path_hits += [f"{label}:{c}" for c in paths]
        offenders_per_spec = _inline_citation_offenders(defenced, inline_specs)
        for spec_idx, offenders in enumerate(offenders_per_spec):
            inline_hits_per_spec[spec_idx] += [f"{label}:{c}" for c in offenders]

    results = [
        CheckResult(
            "portable-no-repo-path-citation",
            not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits),
        ),
    ]
    # inline_hits_per_spec is built as one list per spec, so strict=True can
    # only fire if that construction changes out from under this loop.
    for (check_name, _citation_re, hedge_phrases, kind_label), hits in zip(
        _INLINE_CITATION_CHECK_SPECS, inline_hits_per_spec, strict=True
    ):
        rule = (
            f"Portable content has no inline-code {kind_label} citation "
            f"without an approved hedge phrase {hedge_phrases} in its own "
            "sentence or the sentence immediately before it"
        )
        results.append(
            CheckResult(
                check_name,
                not hits,
                rule,
                "none" if not hits else "found: " + ", ".join(hits),
            )
        )
    return results


def _portable_skill_fact_claim_offenders(defenced_text: str, skill_dir: Path) -> list[str]:
    """Return each possessive sibling-skill citation
    (PORTABLE_SKILL_FACT_CLAIM_RE) in ``defenced_text`` that names a real
    sibling skill directory, asserts its claim with "already" in the same
    clause, and has no approved hedge phrase (HEDGE_PHRASES -- the same
    list ``portable-no-repo-path-citation`` uses; the underlying meaning is
    the same regardless of whether the citation is a path, an issue
    number, or a skill name: a disclosed, deliberate same-repo dependency)
    in that clause or the sentence immediately before it, within the same
    paragraph.

    See PORTABLE_SKILL_FACT_CLAIM_RE's own comment for why all three
    conditions (possessive shape, "already" nearby, real sibling) are
    required together -- each one alone was corpus-validated to produce
    false positives against this repository's own shipped skills.

    The hedge lookback is bounded to the sentence immediately before the
    citation's own clause, within the current paragraph (via
    `_PARAGRAPH_SPLIT_RE` + `_SENTENCE_SPLIT_RE`, the same hedge-proximity
    boundary `_inline_citation_offenders` uses: "own sentence or the
    sentence immediately before it"), not a fixed character count and not
    the whole paragraph: a fixed character count would let an unrelated
    hedge word in a prior, unconnected sentence satisfy an unhedged
    citation, and a whole-paragraph lookback would let a hedge two-or-more
    sentences back leak in (see `test_hedge_in_unrelated_earlier_sentence_
    does_not_count`). Inline-code spans are blanked out of the search text
    first, matching ``_inline_citation_offenders``'s own rule ("a citation
    cannot self-satisfy the requirement merely because its own text
    happens to contain a hedge word") -- otherwise an unrelated
    inline-code token elsewhere in the paragraph (e.g. a
    `` `docs/gitapex-notes.md` `` path) could satisfy the hedge search
    purely because "gitapex" is one of HEDGE_PHRASES, with no bearing on
    this citation at all.
    """
    offenders: list[str] = []
    para_breaks = [m.end() for m in _PARAGRAPH_SPLIT_RE.finditer(defenced_text)]
    for m in PORTABLE_SKILL_FACT_CLAIM_RE.finditer(defenced_text):
        name = m.group(1)
        clause = m.group("clause")
        if "already" not in clause.lower():
            continue
        if not _resolves_to_sibling_skill(name, skill_dir.parent):
            continue
        para_start = 0
        for brk in para_breaks:
            if brk > m.start():
                break
            para_start = brk
        para_lookback = defenced_text[para_start : m.start()]
        prior_sentences = [s for s in _SENTENCE_SPLIT_RE.split(para_lookback) if s.strip()]
        lookback = prior_sentences[-1] if prior_sentences else ""
        haystack = INLINE_CODE_RE.sub(" ", lookback + clause).lower()
        if any(phrase in haystack for phrase in HEDGE_PHRASES):
            continue
        offenders.append(m.group(0).strip())
    return offenders


def _portable_skill_citation_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for
    _portable_skill_fact_claim_offenders, scanning SKILL.md and every
    references/*.md file the same way every other _citation_sources-based
    check does. Only called when ``_is_portable`` is true (see
    ``check_shape``), matching ``_portable_path_citation_checks``'s own
    Portable-only gate: a Mixed/Repository-scoped skill legitimately
    depends on a named sibling's real behavior.
    """
    hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        for offender in _portable_skill_fact_claim_offenders(defenced, skill_dir):
            hits.append(f"{label}:{offender}")
    hits = _dedup(hits)
    return [
        CheckResult(
            "portable-no-unhedged-skill-fact-claim",
            not hits,
            "Portable content has no unhedged declarative fact-claim "
            "about a named sibling skill's own behavior "
            f"(no approved hedge phrase {HEDGE_PHRASES} nearby)",
            "none" if not hits else "found: " + ", ".join(hits),
        ),
    ]


def _demonstrative_origin_repository_offenders(defenced_text: str) -> list[str]:
    """Return each ``this origin repository`` match
    (DEMONSTRATIVE_ORIGIN_REPOSITORY_RE) in ``defenced_text``, with a short
    trailing window of context so a finding reads as a real sentence
    fragment rather than a bare three-word match. Internal whitespace in
    the window is collapsed to single spaces before returning it -- the
    match itself can span a hard-wrapped line break (see the constant's
    own comment), and a raw embedded newline would render as a broken
    finding string. See that constant's own comment for why this check has
    no hedge-phrase rescue, unlike the other Portable-citation checks
    above.
    """
    offenders: list[str] = []
    for m in DEMONSTRATIVE_ORIGIN_REPOSITORY_RE.finditer(defenced_text):
        window_end = min(len(defenced_text), m.end() + 40)
        snippet = defenced_text[m.start() : window_end].strip()
        offenders.append(re.sub(r"\s+", " ", snippet))
    return offenders


def _portable_demonstrative_repository_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str]
) -> list[CheckResult]:
    """The check_shape() entry point for
    _demonstrative_origin_repository_offenders, scanning SKILL.md and every
    references/*.md file the same way every other _citation_sources-based
    check does. Only called when ``_is_portable`` is true (see
    ``check_shape``), matching ``_portable_skill_citation_checks``'s own
    Portable-only gate: a skill that has declared itself Repository-scoped
    is not asking this check to excuse it -- that declaration is exactly
    what it means to depend on this repository on purpose (the same
    carve-out rubric.md's own Dimension 6 bullet states for the sibling
    defect, issue #200/#218).
    """
    hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        for offender in _demonstrative_origin_repository_offenders(defenced):
            hits.append(f"{label}:{offender}")
    hits = _dedup(hits)
    return [
        CheckResult(
            "portable-no-demonstrative-origin-repository-citation",
            not hits,
            "Portable content refers to the origin repository with the "
            'definite article ("the origin repository"), never the '
            'demonstrative "this origin repository"',
            "none" if not hits else "found: " + ", ".join(hits),
        ),
    ]

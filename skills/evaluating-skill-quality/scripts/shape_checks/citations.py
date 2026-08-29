"""Prose-citation scanning helpers shared by both the inline-citation
(portable-skill) checks here and citation_checks.py's own higher-level
checks."""

from __future__ import annotations

import re
from collections.abc import Iterable

from shape_checks.constants import (
    _PARAGRAPH_SPLIT_RE,
    _SENTENCE_SPLIT_RE,
    _WHITESPACE_RE,
    BARE_URL_RE,
    FENCE_RE,
    INLINE_CODE_RE,
    ISSUE_CITATION_RE,
    MD_INLINE_LINK_RE,
    MD_REF_DEF_RE,
    MD_REF_LINK_RE,
    REPO_PATH_CITATION_RE,
)


def _blank_fenced_blocks(body_text: str) -> str:
    """Return ``body_text`` with every fenced code block's lines (the
    fence markers themselves included) replaced by empty lines, preserving
    line count and every other line verbatim.

    Shared by ``_strip_illustrative_spans`` (which goes on to also strip
    inline code, URLs, and links) and ``_inline_citation_offenders``
    (which deliberately keeps inline code intact, since it inspects
    exactly those spans) -- both need fenced blocks excluded the same way,
    since a fenced code block is "already illustrative" regardless of
    which citation shape is being scanned for.
    """
    out: list[str] = []
    in_fence = False
    for line in body_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def _strip_illustrative_spans(defenced_text: str) -> str:
    """Return ``defenced_text`` (already fence-blanked via
    ``_blank_fenced_blocks``) with every span that quotes a token
    illustratively or externally removed, leaving only bare prose.

    Per line, strips inline code spans, absolute URLs, Markdown
    inline/reference links, and reference definitions. These are exactly
    the forms in which this repo's Portable skills already write an issue
    number or repo path without it resolving live (an inline-code
    ``#149``, a full URL, a ``[PR #2][pr2]`` worked-example link), so what
    remains is a citation sitting unguarded in running prose.
    """
    out: list[str] = []
    for line in defenced_text.splitlines():
        if MD_REF_DEF_RE.match(line):
            out.append("")
            continue
        stripped = INLINE_CODE_RE.sub(" ", line)
        stripped = BARE_URL_RE.sub(" ", stripped)
        stripped = MD_INLINE_LINK_RE.sub(" ", stripped)
        stripped = MD_REF_LINK_RE.sub(" ", stripped)
        out.append(stripped)
    return "\n".join(out)


def _split_at_bridging_semicolon(sentence: str, citation_res: tuple[re.Pattern[str], ...]) -> list[str]:
    """Split ``sentence`` at its first semicolon into two clauses, but ONLY
    when an inline-code citation (matching any of ``citation_res``, across
    every spec, not just one) appears on BOTH sides of it -- otherwise
    return ``[sentence]`` unsplit.

    A semicolon is structurally ambiguous in real prose: it can join two
    independent clauses ("Use the hex color `#123456`; see PR `#42` for
    the implementation history."), which must split so the second, unrelated
    citation does
    not inherit the first's hedge; or it can sit inside a single
    parenthetical aside about ONE citation ("`docs/adr/NNNN-*.md` (line
    24; gitapex's own state on this path is covered under Portability
    level above), uses forward slashes." -- real, pre-existing content in
    this repository's own worked-example-explaining-the-work.md), which
    must NOT split, or the hedge phrase that lands after the semicolon
    loses the citation it was actually describing. Splitting at every
    semicolon would incorrectly split a single parenthetical aside about
    one citation; never splitting would let a hedge after the semicolon
    absorb an unrelated citation before it. Requiring a
    citation on both sides is the narrowest rule that keeps both correct.
    Only the FIRST semicolon is considered -- multiple semicolons in one
    sentence are rare enough in this repository's own prose that handling
    only the common case matches this checker's own established "simple,
    not a full parser" tolerance elsewhere in this module.
    """
    semi = sentence.find(";")
    if semi == -1:
        return [sentence]
    before, after = sentence[: semi + 1], sentence[semi + 1 :]

    def _has_citation(text: str) -> bool:
        return any(cre.search(m.group(2)) for m in INLINE_CODE_RE.finditer(text) for cre in citation_res)

    if _has_citation(before) and _has_citation(after):
        return [before, after]
    return [sentence]


def _inline_citation_offenders(
    defenced_text: str,
    specs: tuple[tuple[re.Pattern[str], tuple[str, ...], frozenset[str]], ...],
) -> list[list[str]]:
    """Return, for each ``(citation_re, hedge_phrases, declared_paths)``
    triple in ``specs``, the list of inline-code citations matching that
    ``citation_re`` in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``)
    that have no phrase from that spec's ``hedge_phrases`` in their own
    sentence (or bridging-semicolon-split clause, see
    ``_split_at_bridging_semicolon``) or the one immediately before it (see
    the module docstring's repo-path and issue-number citation entries for
    the rationale, and the clause-splitting note below). The returned list
    is ordered the same as ``specs``. Shared by the evals/docs/CLAUDE.md-
    chapter repo-path check (``REPO_PATH_CITATION_RE``/
    ``GENERIC_ROLE_HEDGE_PHRASES`` -- see that constant's own comment for
    why only the generic-placeholder half of ``HEDGE_PHRASES`` rescues a
    match here) and the issue-number check
    (``ISSUE_CITATION_RE``/``ISSUE_CITATION_HEDGE_PHRASES``) -- the citation
    shape and hedge vocabulary differ per spec, but the paragraph/sentence
    tokenization and the inline-code-span search below are identical, so
    both specs are evaluated in one pass over the same tokens rather than
    one pass per spec.

    Bounded to a paragraph first (a run of contiguous non-blank lines),
    then to a sentence within it via ``_SENTENCE_SPLIT_RE``, each further
    split at a bridging semicolon (see ``_split_at_bridging_semicolon`` --
    across every spec's citation shape at once, since clause boundaries
    are shared infrastructure, not per-spec) -- not paragraph-wide, so a
    hedge written for one citation cannot silently exempt an unrelated
    citation many sentences later in the same (possibly long, multi-topic)
    paragraph. Whitespace inside a paragraph is normalized to single
    spaces first, since Markdown line-wraps a hedge phrase across lines
    exactly as often as it wraps any other prose (e.g. "the calling\\n
    repository's own").

    Every inline-code span in the clause -- not just the citation being
    checked -- is blanked out of that clause's hedge search text, so a
    citation cannot self-satisfy the requirement merely because its own
    text happens to contain a hedge word (e.g. a path literally named with
    "gitapex" in it). A hedge is the author's own prose explaining a
    citation; text inside any backtick span is never that, regardless of
    which citation it is or whether it happens to match a citation shape
    at all.

    Two or more citations WITHIN one clause deliberately still share that
    whole clause's hedge search -- this file's own real content relies on
    one leading hedge introducing a list of several different citations
    (e.g. "in this repository's own bookkeeping ...:
    `evals/.../split.md`'s Kept-edit log and `docs/skill-eval-status.md`."),
    which a stricter per-citation windowing design would incorrectly break.
    The "clause immediately before"
    fallback is instead the layer doing the real work for the reported
    exploit shape: it is used ONLY when that previous clause has no
    citation of its own for this spec -- the established, tested pattern
    is a pure hedge clause ("This repository has also recorded background
    context here.") followed by a citation clause, never two back-to-back
    clauses that each cite something. Without this restriction, a hedge
    that correctly justifies one clause's own citation (e.g. "Use the hex
    color `#123456` for the button.") would leak into a completely
    unrelated citation in the very next clause (e.g. "See PR `#42` for the
    implementation history.") purely because they are clause-adjacent.

    A narrower residual is accepted, not solved, by this design: two
    DIFFERENT citations within the same clause, comma- or
    apposition-joined (no bridging semicolon), where only one is
    genuinely hedged (e.g. "See `#123456`, a hex color reference,
    followed by the real bug `#42`.") still share the clause-wide hedge
    and both pass. Distinguishing that shape from the legitimate "one
    hedge, a list of several citations" shape above would require more
    than a punctuation-based tokenizer can resolve; this checker is a
    deliberately simple, practical approximation (see the module's own
    established tolerance for this tokenizer's "e.g." over-split,
    elsewhere in this file), not a full parser.

    Fenced code blocks are already excluded by the caller via
    ``_blank_fenced_blocks`` -- a citation inside a fenced illustrative
    example never reaches this check, matching the module docstring's
    "fenced code blocks stay exempt unconditionally" note. Each spec's
    result list is order-preserving and deduplicated, matching
    ``_portable_citation_offenders``.

    ``declared_paths`` (issue #1055) supplements ``hedge_phrases`` for a
    spec that carries one: a citation whose own matched text exactly
    equals a member of ``declared_paths`` is rescued even when its clause
    carries no hedge phrase at all, per-citation rather than clause-wide --
    a ``spec.externalCitations`` declaration is a fact about one specific
    path, unlike a hedge phrase, which is prose covering everything in its
    own clause. Empty for the issue-number spec, which this proposal does
    not touch.
    """
    citation_res = tuple(citation_re for citation_re, _hedge_phrases, _declared_paths in specs)
    offenders_per_spec: list[list[str]] = [[] for _ in specs]
    for para in _PARAGRAPH_SPLIT_RE.split(defenced_text):
        if not para.strip():
            continue
        normalized = _WHITESPACE_RE.sub(" ", para)
        clauses: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(normalized):
            clauses.extend(_split_at_bridging_semicolon(sentence, citation_res))
        # Precomputed once per paragraph (not just-in-time per clause) so
        # the "previous clause has no citation of its own" check below can
        # look at any earlier clause's code spans without re-scanning.
        all_code_spans = [list(INLINE_CODE_RE.finditer(c)) for c in clauses]
        for i, clause in enumerate(clauses):
            code_spans = all_code_spans[i]
            if not code_spans:
                continue
            prev_lower = clauses[i - 1].lower() if i > 0 else ""
            clause_lower = clause.lower()
            blanked = list(clause_lower)
            for cs in code_spans:
                for pos in range(cs.start(), cs.end()):
                    blanked[pos] = " "
            blanked_lower = "".join(blanked)
            for spec_idx, (citation_re, hedge_phrases, declared_paths) in enumerate(specs):
                spec_matches = [(cs, list(citation_re.finditer(cs.group(2)))) for cs in code_spans]
                spec_matches = [(cs, ms) for cs, ms in spec_matches if ms]
                if not spec_matches:
                    continue
                prev_has_own_citation = i > 0 and any(citation_re.search(cs.group(2)) for cs in all_code_spans[i - 1])
                candidate_prev = "" if prev_has_own_citation else prev_lower
                hedged = any(phrase in blanked_lower or phrase in candidate_prev for phrase in hedge_phrases)
                if hedged:
                    continue
                for cs, matches in spec_matches:
                    # A span is rescued only when EVERY citation match it
                    # carries is declared -- per-citation, not clause-wide
                    # (issue #1055): a span packing one declared and one
                    # undeclared citation (e.g. `` `docs/a.md docs/b.md` ``)
                    # must still surface the undeclared one, so a single
                    # ``.search()`` (first match only) is not enough here.
                    all_declared = bool(declared_paths) and all(m.group(0) in declared_paths for m in matches)
                    if not all_declared:
                        offenders_per_spec[spec_idx].append(cs.group(0))
    return [_dedup(offenders) for offenders in offenders_per_spec]


def _portable_citation_offenders(defenced_text: str) -> tuple[list[str], list[str]]:
    """Return (issue-number, repo-path) bare-prose citations in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``).

    Applies the illustrative-span strip first, so only citations left
    unguarded in running prose are reported. Order-preserving and
    deduplicated so the evidence string is stable and terse.
    """
    prose = _strip_illustrative_spans(defenced_text)
    issues = _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(prose))
    paths = _dedup(m.group(0) for m in REPO_PATH_CITATION_RE.finditer(prose))
    return issues, paths


def _dedup(items: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)

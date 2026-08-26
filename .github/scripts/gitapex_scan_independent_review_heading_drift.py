#!/usr/bin/env python3
"""Guard the single-source-of-truth invariant for text this repository's
`independent-review-pending` gate and its surrounding PR-flow docs must
keep in sync across several hand-duplicated files.

Issue #1343: the gate's own recorded-verdict heading (once ``## Step 8
independent review verdict``, renamed by that issue to ``## Independent
review verdict`` to de-couple it from ``drafting-a-pr-to-merge``'s internal
step numbering) is duplicated by hand across four other files besides the
gate script itself, which now owns the canonical text as
``gitapex_gate_independent_review_pending.CANONICAL_HEADING_TEXT``. This
gate closes that gap -- registered as ``independent-review-heading-drift``
in ``.gitapex/ssot.json``.

Three independent deterministic-gate-quality/adversarial-review rounds
(same issue's own session), run against three successive drafts of this
gate, found real defects; the current design closes all of them:

1. **First draft checked only marker presence, not absence of retired
   text.** A target carrying the canonical marker *and* a retired heading
   (an incomplete migration) passed clean -- the exact drift class this
   gate exists to catch. ``MarkerSpec.legacy_texts`` now flags a target
   that still carries a retired form, independent of whether the
   canonical one is also present.
2. **First draft's substring search accepted dead text.** A marker inside
   an HTML comment or a fenced code block (GitHub renders both as
   nothing) satisfied a bare substring search on the two Markdown
   targets. ``_searchable_text`` now strips both, reusing
   ``gitapex_gate_independent_review_pending``'s own
   ``strip_html_comments``/``strip_fenced_code_blocks`` rather than
   re-deriving them -- this gate's own definition of "live text" can
   never independently drift from the sibling gate's.
3. **Second draft's substring search was case-sensitive, where the
   sibling gate's own detection regex (``_HEADING_RE``) is
   ``re.IGNORECASE``** -- confirmed live to both false-flag a same-
   meaning casing change as drift, and false-clear an incomplete
   migration recorded in a different case. All matching below is now
   ``str.casefold()``-based.
4. **A third round considered matching each of these four targets as a
   live ATX heading** (via a public ``heading_pattern()`` added to
   ``gitapex_gate_independent_review_pending`` for exactly this purpose),
   to track the sibling gate's own end-anchored, indentation-limited
   regex more closely than a bare substring does. Reverted after checking
   the targets' own actual content: in all four files, the canonical/
   retired text is never itself a live heading -- it is quoted prose (a
   backtick-wrapped phrase in ``drafting-a-pr-to-merge/SKILL.md`` and
   ``.github/PULL_REQUEST_TEMPLATE.md``, a JSON string value in
   ``.gitapex/ssot.json``, a YAML comment in the workflow file). Heading-
   pattern matching against non-heading targets produced a live false
   positive (flagging the actual, correct, already-updated files as
   drift) rather than closing a real gap -- verifying "is the current
   text quoted here" is this gate's own job; verifying "is a genuine PR-
   body verdict section shaped like a live heading" stays
   ``gitapex_gate_independent_review_pending.py``'s, the only place that
   distinction is load-bearing. A later reuse/simplification review found
   that ``heading_pattern()`` then had no caller anywhere in shipped code
   -- a public function built for a reuse case that never materialized --
   and it was removed from that module entirely, reverting
   ``_HEADING_RE`` there to a directly-inlined ``re.compile()`` call.
5. **The same review found this gate itself, in its first draft, was not
   registered as depending on the pytest workflow event the way every
   sibling ``*-drift``/scan gate with the same trigger is.** ``target[]``
   in this gate's own ``.gitapex/ssot.json`` entry now carries the
   ``workflow-event`` refs the other 34 gates sharing that trigger already
   do.
6. **A live review of this PR's own diff (not this gate's design) found a
   second hand-duplicated literal it never covered:** the feed-forward
   note this same PR added to ``.github/PULL_REQUEST_TEMPLATE.md``
   (``## Merge gate: independent review``) is quoted verbatim, inside a
   code span, by ``skills/executing-a-branch-plan/SKILL.md`` Step 5 -- a
   second pair of files this gate now also tracks, via a second
   ``MarkerSpec`` (``_MERGE_GATE_NOTE``).
7. **This gate's own first run against the real repository** (not a
   fixture -- confirmed live) false-flagged that same
   ``executing-a-branch-plan/SKILL.md`` reference as drift: its own
   Markdown line-wrap splits the code span across two source lines
   (`` `## Merge gate:\n   independent review` ``), which GitHub still
   renders as one unbroken phrase but a single-line substring search
   cannot see across. ``_text_present`` now whitespace-normalizes (every
   run of whitespace, including a newline, collapses to one space) both
   sides before comparing, rather than requiring every target to keep the
   tracked phrase hand-reformatted onto one physical line to keep this
   gate quiet.

``MarkerSpec.targets`` names each target file's own Markdown-ness
directly (no separate, independently-maintainable set of "which targets
are Markdown" the way an earlier draft kept as ``_MARKDOWN_TARGETS`` --
a review found *that* duplication was itself an unpinned copy of
information already present in ``targets``).

Adding a future marker this repository needs to keep synchronized means
adding one more ``MarkerSpec`` to ``_MARKER_SPECS`` below, not writing a
new gate script -- the detection logic (``_searchable_text``,
``_text_present``, ``find_drift``) is spec-driven, not heading-specific.

Still deliberately scoped to whitespace-normalized, case-insensitive
substring matching, not a full Markdown/JSON/YAML parse of each target's
own surrounding syntax: a false negative remains possible if a target
splits the tracked text in some other form this search does not
recognize (e.g. a hyphenated word-break mid-phrase); a false positive on
the *presence* check remains very unlikely (each marker string is
specific), but is not claimed impossible.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_independent_review_heading_drift.py``.
"""

from __future__ import annotations

import pathlib
import re
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gitapex_gate_independent_review_pending as gate  # sys.path bootstrap above must run first

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MarkerSpec:
    """One canonical text this gate keeps synchronized across a set of
    target files, plus any retired text that must not still be live in
    them. See the module docstring for the two specs this gate currently
    tracks and why each exists."""

    name: str
    canonical_text: str
    legacy_texts: tuple[str, ...]
    targets: tuple[tuple[pathlib.Path, bool], ...]  # (path relative to repo root, is_markdown)


_INDEPENDENT_REVIEW_HEADING = MarkerSpec(
    name="independent-review-pending's own recorded-verdict heading",
    canonical_text=gate.CANONICAL_HEADING_TEXT,
    # Extend this tuple, never replace it, on a future rename -- each
    # entry documents one completed migration this gate keeps verified,
    # not just the most recent one.
    legacy_texts=("Step 8 independent review verdict",),
    targets=(
        (pathlib.Path("skills/drafting-a-pr-to-merge/SKILL.md"), True),
        (pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md"), True),
        (pathlib.Path(".gitapex/ssot.json"), False),
        (pathlib.Path(".github/workflows/independent-review-pending.yml"), False),
    ),
)

_MERGE_GATE_NOTE = MarkerSpec(
    name="the PR-template feed-forward note's own section name",
    canonical_text="Merge gate: independent review",
    legacy_texts=(),
    targets=(
        (pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md"), True),
        (pathlib.Path("skills/executing-a-branch-plan/SKILL.md"), True),
    ),
)

_MARKER_SPECS = (_INDEPENDENT_REVIEW_HEADING, _MERGE_GATE_NOTE)


def _searchable_text(content: str, *, is_markdown: bool) -> str:
    """Strip HTML comments and fenced code blocks (dead text on GitHub,
    never live prose) before searching -- but only for a Markdown target,
    where those constructs are part of the file's own convention.
    A non-Markdown target (ssot.json, the workflow YAML) is searched as
    plain text, unchanged; neither construct is part of its own syntax."""
    if not is_markdown:
        return content
    stripped = gate.strip_html_comments(content)
    return gate.strip_fenced_code_blocks(stripped)


def _normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including a newline) to a single
    space. Confirmed live (this gate's own first run against the real
    repository): a Markdown target can carry the tracked text inside a
    code span that a line-wrap splits across two source lines --
    `skills/executing-a-branch-plan/SKILL.md` wraps `` `## Merge gate:
    \\n   independent review` `` exactly this way. GitHub still renders
    that as one unbroken phrase; a search that only recognizes it on a
    single physical line does not, and would either false-flag a correct,
    already-updated file as drift or force every target to stay hand-
    reformatted onto one line to keep this gate quiet -- reformatting
    prose to satisfy a drift check, rather than the other way around."""
    return re.sub(r"\s+", " ", text)


def _text_present(text: str, searchable: str) -> bool:
    """Case-insensitive, whitespace-normalized substring presence -- see
    the module docstring's point 4 for why this is not heading-pattern
    matching: none of this gate's own targets carry the tracked text as a
    live heading of their own, only as quoted prose/JSON/YAML text, so a
    plain substring comparison is both sufficient and (confirmed live)
    more accurate here than ATX-heading-pattern matching would be."""
    return _normalize_whitespace(text).casefold() in _normalize_whitespace(searchable).casefold()


def find_drift(root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per (spec, target) pair that either does not
    carry that spec's canonical text as live text, or still carries one
    of its retired texts as live text. Empty list means no drift. A
    missing or unreadable target file is itself reported as drift (fail
    closed) rather than silently skipped -- it cannot be verified to
    carry the current text."""
    findings: list[str] = []
    for spec in _MARKER_SPECS:
        for relative, is_markdown in spec.targets:
            path = root / relative
            if not path.is_file():
                findings.append(f"{relative}: file not found, cannot verify it carries {spec.name}")
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                findings.append(f"{relative}: could not read as UTF-8, cannot verify {spec.name}: {exc}")
                continue

            searchable = _searchable_text(content, is_markdown=is_markdown)

            if not _text_present(spec.canonical_text, searchable):
                findings.append(f"{relative}: does not carry {spec.name} ({spec.canonical_text!r}) as live text")

            for legacy_text in spec.legacy_texts:
                if _text_present(legacy_text, searchable):
                    findings.append(
                        f"{relative}: still carries a retired form of {spec.name} ({legacy_text!r}) as live "
                        "text -- the migration is incomplete"
                    )
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print("Independent-review-pending marker drift found:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No independent-review-pending marker drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

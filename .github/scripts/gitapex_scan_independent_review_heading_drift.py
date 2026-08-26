#!/usr/bin/env python3
"""Guard the independent-review-pending recorded-verdict heading's
single-source-of-truth invariant.

Issue #1343: the gate's own recorded-verdict heading (once ``## Step 8
independent review verdict``, renamed by that issue to ``## Independent
review verdict`` to de-couple it from ``drafting-a-pr-to-merge``'s internal
step numbering) is duplicated by hand across four other files besides the
gate script itself, which now owns the canonical text as
``gitapex_gate_independent_review_pending.CANONICAL_HEADING_TEXT``:

- ``skills/drafting-a-pr-to-merge/SKILL.md`` (Step 8's own recorded-heading
  instruction)
- ``.github/PULL_REQUEST_TEMPLATE.md`` (the ``## Merge gate: independent
  review`` feed-forward note)
- ``.gitapex/ssot.json`` (the ``independent-review-pending`` gate entry's
  own ``rule`` field)
- ``.github/workflows/independent-review-pending.yml`` (a comment)

An independent adversarial deterministic-gate-quality review (dimension
12, issue #1343's own session) found that nothing previously bound these
five copies together -- this PR's own rename touched all five by hand,
but a future rename, or a future hand-edit of any one of them, could
silently drift the rest out of sync with no test failing. CLAUDE.md's own
governance rule for this repository states the invariant plainly: "ship
its drift gate in the same change, not a follow-up." This is that gate.

A second, independent deterministic-gate-quality review (same issue,
against this gate script itself) found the first drafted version checked
only one direction -- the canonical marker's presence -- and confirmed
three live gaps that direction alone leaves open, each closed below:

1. **One-directional check.** A target file carrying the canonical marker
   *and* a retired heading text (e.g. the pre-rename ``## Step 8
   independent review verdict``) passed clean -- the exact
   incomplete-migration drift this gate exists to catch.
   ``_LEGACY_HEADING_TEXTS`` now also fails a target file that still
   contains a retired text, not only one missing the current one.
2. **Dead text counted as live.** The marker inside an HTML comment, a
   fenced code block, or (for a Markdown target) any other form GitHub
   itself renders as inert satisfied a bare substring search. For the two
   Markdown targets, ``_strip_html_comments``/``_strip_fenced_code_blocks``
   are now reused directly from ``gitapex_gate_independent_review_pending``
   (imported, not re-derived) before searching, so this gate's own
   definition of "live text" never independently drifts from the sibling
   gate's. The two non-Markdown targets (``.gitapex/ssot.json``,
   the workflow YAML) carry neither HTML comments nor Markdown fences in
   this repository's own convention, so they are searched as plain text,
   unchanged.
3. **Overclaimed false-positive immunity.** The prior revision's own
   docstring asserted a false positive "is not possible"; a heading
   variant the canonical ``#{1,6}``/``[ \t]+`` regex accepts but this
   substring check's own fixed ``"## "`` prefix rejects (a single ``#``,
   or more than one space after ``##``) is exactly such a case in the
   opposite direction -- a live, valid heading this check would report as
   missing. Restated below as a disclosed, bounded limitation instead of
   an unqualified guarantee, the same "deliberately not exhaustive"
   trade-off ``gitapex_scan_toolchain_pin_drift.py`` documents for its
   own single-source-of-truth invariant.

Still deliberately scoped to substring/heading-form matching, not a full
Markdown/JSON/YAML parse of each target's own surrounding syntax --
false negative is possible if a file quotes either the canonical or a
retired heading in a form neither ``_HEADING_RE``-style matching (the two
Markdown targets) nor a bare substring search (the two non-Markdown
targets) recognizes; a false positive on the *presence* check remains
very unlikely (the marker string is specific), but is not claimed
impossible.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_independent_review_heading_drift.py``.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gitapex_gate_independent_review_pending as gate

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Relative to the repository root -- the gate script itself is the
# canonical source and is not included here as a target to check against
# itself.
_TARGET_FILES = (
    pathlib.Path("skills/drafting-a-pr-to-merge/SKILL.md"),
    pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md"),
    pathlib.Path(".gitapex/ssot.json"),
    pathlib.Path(".github/workflows/independent-review-pending.yml"),
)

# Only these two targets are Markdown; HTML-comment/fence stripping is
# meaningful only for them (see module docstring, point 2).
_MARKDOWN_TARGETS = frozenset(
    {
        pathlib.Path("skills/drafting-a-pr-to-merge/SKILL.md"),
        pathlib.Path(".github/PULL_REQUEST_TEMPLATE.md"),
    }
)

# Heading text this gate's own rename (issue #1343) retired. A target file
# still containing one of these, even alongside the current canonical
# marker, has not finished migrating and is reported as drift (module
# docstring, point 1). Extend this tuple, never replace it, on a future
# rename -- each entry documents one completed migration this gate keeps
# verified, not just the most recent one.
_LEGACY_HEADING_TEXTS = ("Step 8 independent review verdict",)


def _searchable_text(path: pathlib.Path, content: str) -> str:
    """Return `content` with dead (non-live) text stripped for the
    purposes of this gate's own marker search -- HTML comments and fenced
    code blocks for a Markdown target (module docstring, point 2); `content`
    unchanged for a non-Markdown target, where neither construct is part of
    this repository's own convention for that file type."""
    if path not in _MARKDOWN_TARGETS:
        return content
    stripped = gate._strip_html_comments(content)
    return gate._strip_fenced_code_blocks(stripped)


def find_drift(root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per target file that either does not carry the
    canonical ``"## " + CANONICAL_HEADING_TEXT`` marker as live text, or
    still carries a retired heading text (see ``_LEGACY_HEADING_TEXTS``).
    Empty list means no drift. A missing target file is itself reported as
    drift (fail closed) rather than silently skipped -- an absent file
    cannot be verified to carry the current heading."""
    marker = "## " + gate.CANONICAL_HEADING_TEXT
    findings: list[str] = []
    for relative in _TARGET_FILES:
        path = root / relative
        if not path.is_file():
            findings.append(f"{relative}: file not found, cannot verify it carries {marker!r}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(f"{relative}: could not read as UTF-8, cannot verify: {exc}")
            continue

        searchable = _searchable_text(relative, content)

        if marker not in searchable:
            findings.append(f"{relative}: does not contain the canonical heading marker {marker!r} as live text")

        for legacy_text in _LEGACY_HEADING_TEXTS:
            if legacy_text in searchable:
                findings.append(
                    f"{relative}: still contains the retired heading text {legacy_text!r} as live text -- "
                    "the migration to the canonical heading is incomplete"
                )
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print(
            "Independent-review-pending heading drift: every file below must carry the "
            f"canonical heading text owned by gitapex_gate_independent_review_pending."
            f"CANONICAL_HEADING_TEXT ({gate.CANONICAL_HEADING_TEXT!r}) and none of the retired "
            f"heading texts in _LEGACY_HEADING_TEXTS:"
        )
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No independent-review-pending heading drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Native, waza-independent operational definitions for two of waza's own
advisory concepts -- body-structure and negative-delta-risk -- so
``gitapex_run_effectiveness_correlation.py`` can compute a real x-metric
instead of its former disclosed placeholder (``SKILL.md`` body line count).
Built for issue #1144 (#1137 sub-task 3's own contingent scope): a
correlation between these metrics and a skill's real behavioral outcome
still has to be measured before either concept is ported into
``evaluating-skill-quality``'s rubric -- this module only provides the
x-side of that pair, waza-independent, per this repository's own already-
established pattern (``gitapex_check_skill_shape.py``'s natively-implemented
deterministic checks, in that script's own docstring).

**These are NOT a reverse-engineered copy of waza's own undisclosed
counting algorithm.** waza's own body-structure/negative-delta-risk
scoring logic is not published anywhere this module's author could find,
and no attempt was made to match it number-for-number. These are this
repository's own fresh, corpus-calibrated operational definitions of the
same two *concepts* -- close enough in spirit to be a fair test of whether
the concepts predict real skill quality, not a claim that a given skill
would score identically under waza's own (undisclosed) implementation.

**Why calibrated, not literal.** A literal reading of "MUST/NEVER/ALWAYS"
(shouting case) and "a heading literally named Examples" produces a
CONSTANT ZERO across this repository's real 25 ``skills/*/SKILL.md``
files: this repository writes constraint language in ordinary sentence
case ("Never treat the detected phrase as..."), never shouting case, and
its own worked-example convention is ``## Worked example`` (singular),
never a bare ``## Examples`` heading. A constant series crashes
``gitapex_compute_rank_correlation.spearman_rho`` (``ValueError``,
correlation undefined against a constant input) the moment a real
correlation run is attempted -- so this module instead counts sentence/
bullet/numbered-list-initial ``Must``/``Never``/``Always`` (not shouting
case, and not a bare case-insensitive scan, which mostly matches ordinary
English words like "always happens" and is not a constraint signal: 456
bare-scan hits vs. 146 sentence/bullet-initial hits across this
repository's own real corpus at calibration time) and a ``## Worked
example``/``## Examples`` heading (singular or plural, case-insensitive)
-- both confirmed non-constant against the real corpus at the time this
module was written.

**Bullets dominate, not a footnote.** An earlier draft of this module
matched sentence-initial constraint language only (``^`` or a sentence-
ending punctuation mark followed by whitespace, directly followed by the
word) and measured 19 hits across the real
corpus. Re-checked against a bullet-aware pattern, that draft was
undercounting by roughly 7x: 124 of the 146 real hits are Markdown list
items ("``- Never do X``", "``1. Always do Y``"), this repository's own
dominant convention for stating a constraint (confirmed directly against
every real ``skills/*/SKILL.md`` file while building this module) -- not
a rare edge case worth a passing mention. ``_CONSTRAINT_SIGNAL_PATTERN``
below matches both forms.
"""

from __future__ import annotations

import re

# Sentence-, bullet-, or numbered-list-initial "Must"/"Never"/"Always" --
# i.e. immediately after a sentence boundary (line start, optionally
# indented, optionally followed by a "- "/"* "/"1. " list marker; or
# `.`/`!`/`?` followed by whitespace) -- not a bare case-insensitive scan.
# See module docstring's "Why calibrated, not literal" and "Bullets
# dominate" sections: a bare scan mostly matches ordinary prose, and a
# sentence-initial-only pattern (no list-marker allowance) misses the
# large majority of this repository's own real constraint statements,
# which are stated as list items, not free-standing sentences.
_CONSTRAINT_SIGNAL_PATTERN = re.compile(r"(^\s*|[.!?]\s+)(?:[-*]\s+|\d+\.\s+)?(Must|Never|Always)\b", re.MULTILINE)

# A '## Worked example' or '## Examples' heading (singular or plural, any
# heading depth >= 2, case-insensitive) -- this repository's own real
# convention, not a literal, undisclosed "Examples" match.
_WORKED_EXAMPLE_HEADING_PATTERN = re.compile(r"^#{2,}\s+(worked\s+)?examples?\b", re.MULTILINE | re.IGNORECASE)

# A '## Error handling' or '## Troubleshooting' heading. Confirmed
# near-zero across the real corpus at calibration time (no established
# heading convention for this yet) -- left as-is rather than papered over
# with an invented synonym list to manufacture variance that is not
# really there. See module docstring.
_ERROR_HANDLING_HEADING_PATTERN = re.compile(
    r"^#{2,}\s+(error\s+handling|troubleshooting)\b", re.MULTILINE | re.IGNORECASE
)


def strip_frontmatter(text: str) -> str:
    """Return ``text`` with its YAML frontmatter block removed, so a
    keyword/heading scan below never matches inside frontmatter prose
    (e.g. a ``description:`` field that happens to start a sentence with
    "Never").

    A well-formed ``SKILL.md`` starts with a ``---``-only line and closes
    the block with the next ``---``-only line; this returns everything
    after that second line. If the first line is not exactly ``---``, or
    no closing ``---``-only line is ever found, ``text`` is returned
    unchanged rather than raising -- every real committed ``SKILL.md`` is
    already frontmatter-shaped (a separate, already-enforced repository
    invariant this module does not re-check), so this is a safe fallback
    for a malformed input, not the contract this function exists to
    enforce.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        return text
    for index in range(1, len(lines)):
        if lines[index].rstrip("\n") == "---":
            return "".join(lines[index + 1 :])
    return text


def count_constraint_signals(body: str) -> int:
    """This module's own operational stand-in for waza's negative-delta-risk
    advisory: the number of sentence/bullet-initial ``Must``/``Never``/
    ``Always`` occurrences in ``body`` (already frontmatter-stripped, see
    ``strip_frontmatter``). Higher is not itself "worse" or "better" here
    -- this function makes no quality claim, only a count; whether more
    (or fewer) constraint language predicts real skill quality is exactly
    the open question issue #1144's own correlation run exists to answer.
    """
    return len(_CONSTRAINT_SIGNAL_PATTERN.findall(body))


def count_body_structure_signals(body: str) -> int:
    """This module's own operational stand-in for waza's body-structure
    advisory: 0, 1, or 2 -- +1 if ``body`` (already frontmatter-stripped)
    has a ``## Worked example``/``## Examples`` heading, +1 if it has a
    ``## Error handling``/``## Troubleshooting`` heading. The second half
    is honestly near-zero across this repository's real corpus today (no
    established heading convention for it yet) -- disclosed in the module
    docstring, not papered over with an invented synonym list to force
    variance that is not really there.
    """
    count = 0
    if _WORKED_EXAMPLE_HEADING_PATTERN.search(body):
        count += 1
    if _ERROR_HANDLING_HEADING_PATTERN.search(body):
        count += 1
    return count

"""Shared primitives for this repository's vocabulary/structure drift-lock
gates (a script that asserts a declared count, named headings, or enumerated
vocabulary stays consistent with the real document, without judging whether
the prose content itself is good).

Extracted from `gitapex_scan_contract_axis_vocabulary_drift.py` (issue #949,
the first gate of this shape) when `gitapex_scan_skill_quality_rubric_vocabulary_drift.py`
(issue #993, the second) copied the same three primitives verbatim: a
duplicated `read_text`/`extract_section`/`ScanError` is exactly the two-
copies-drift failure mode this whole gate class exists to prevent, now
reproduced at the meta level between the gates themselves if left
un-shared. Same convention as `_gitapex_schema_validation.py` (issue #928)
for the schema-drift gate family.

Both callers keep their own regexes, vocabulary registries, and `scan()`
orchestration -- only the file-read and heading-section-extraction
mechanics, which have no gate-specific content, live here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

#: Shared by every count-lock caller in this gate family -- previously
#: copied verbatim into each one. A caller needing a number above ten has
#: none today; extend here, not per-caller, if that ever changes.
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


class ScanError(Exception):
    """An input could not be read or parsed -- exit 2, never a silent pass."""


def read_text(path: Path) -> str:
    """Read ``path`` as UTF-8, raising :class:`ScanError` on any failure.

    Every read failure is the same outcome here -- the check could not run --
    so an unreadable file must not reach the caller as an empty string that
    every substring check would then report as ordinary drift.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ScanError(f"{path}: not found") from error
    except UnicodeDecodeError as error:
        raise ScanError(f"{path}: could not decode as UTF-8: {error}") from error
    except OSError as error:
        raise ScanError(f"{path}: could not be read: {error}") from error


def extract_section(text: str, heading: str, path_label: str) -> str:
    """The body under ``heading``, up to the next heading of the same or a
    shallower level.

    Raises :class:`ScanError` when the heading is absent, appears more than
    once, or opens an empty section: each means the structure the caller
    assumes is not there, which is a "cannot check" answer, not a passing
    one.
    """
    level = len(heading) - len(heading.lstrip("#"))
    occurrences = [m.start() for m in re.finditer(rf"^{re.escape(heading)}[ \t]*$", text, re.MULTILINE)]
    if not occurrences:
        raise ScanError(f"{path_label}: heading not found: {heading!r}")
    if len(occurrences) > 1:
        raise ScanError(f"{path_label}: heading appears {len(occurrences)} times, expected exactly once: {heading!r}")

    start = occurrences[0] + len(heading)
    rest = text[start:]
    next_heading = re.search(rf"^#{{1,{level}}}[ \t]+\S", rest, re.MULTILINE)
    body = rest[: next_heading.start()] if next_heading else rest
    if not body.strip():
        raise ScanError(f"{path_label}: section {heading!r} is empty")
    return body


def check_number_word_matches(
    matches: list[str],
    expected: int,
    format_unrecognized: Callable[[str], str],
    format_mismatch: Callable[[str, int], str],
) -> list[str]:
    """The genuinely common half of every count-lock check in this gate
    family: for each number word `matches` a caller's own regex found,
    look it up in :data:`NUMBER_WORDS` and compare it to `expected`,
    collecting one problem per unrecognized word or mismatch.

    Deliberately narrow -- this is only the "declared word vs. expected
    int" comparison loop. Each caller keeps its own regex (what counts as
    a declaration), its own `expected` computation (what the real
    document structure says the count should be), and its own message
    wording via the two formatting callables: `format_unrecognized(word)`
    for a word not in `NUMBER_WORDS`; `format_mismatch(word, stated)` for
    a recognized word whose value does not equal `expected` -- both the
    original matched text and its parsed value are passed through, since
    an existing caller's message quotes the original word as matched
    (preserving its exact case), not just the parsed int. A caller's own
    additional structural checks (heading order, a fixed non-axis offset,
    and similar) are not this function's concern and stay entirely
    caller-side.
    """
    problems: list[str] = []
    for word in matches:
        stated = NUMBER_WORDS.get(word.lower())
        if stated is None:
            problems.append(format_unrecognized(word))
        elif stated != expected:
            problems.append(format_mismatch(word, stated))
    return problems

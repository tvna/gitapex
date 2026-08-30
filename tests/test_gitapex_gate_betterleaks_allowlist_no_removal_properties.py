"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_betterleaks_allowlist_no_removal.py`` (issue
#1427), added because issue #1178's ``detection-logic-property-coverage``
gate requires one for the regex-based detection logic that module
introduces: ``_WAIVER_RE = re.compile(...)`` at module scope. Module-level,
per that gate's own rule, so any ``@given`` test in this file satisfies it.

**Model-based**, per this repository's own convention for this kind of
layer (see e.g. ``tests/test_gitapex_gate_no_raw_gh_cli_in_docs_properties.py``'s
own docstring on the distinction): the property below builds an
``[allowlist].paths`` array plus an independently chosen removed subset and
waived subset, computes the expected surviving-unwaived-removal set by
plain set arithmetic over the generator's own ground truth, and asserts
``find_unwaived_removals`` (which internally re-parses both TOML documents
and re-scans for waiver comments) agrees -- so a regression in either the
TOML round-trip or the waiver-substring match fails this property, not
merely a hand-picked example.
"""

from __future__ import annotations

import gitapex_gate_betterleaks_allowlist_no_removal as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

# Lowercase-alnum only: keeps every generated entry a valid TOML raw
# (triple-single-quoted) string with no escaping/quoting edge case of its
# own to reason about -- that is not what this property is testing (the
# example-based suite next door already covers the TOML syntax itself via
# real `.betterleaks.toml`-shaped fixtures).
_ENTRY = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=12)


def _build_toml(paths: list[str]) -> str:
    lines = "".join(f"  '''{path}''',\n" for path in paths)
    return f"[allowlist]\npaths = [\n{lines}]\n"


@_PROPERTIES
@given(st.data())
def test_find_unwaived_removals_matches_removed_minus_waived_for_any_split(data: st.DataObject) -> None:
    """For an arbitrary base ``paths`` array, an arbitrary subset removed at
    head, and an arbitrary sub-subset of the removed entries individually
    quoted in a waiver comment, ``find_unwaived_removals`` returns exactly
    ``removed - waived`` -- independent of array order, of how many other
    entries were kept, and of how many other waiver comments (naming
    entries that were not actually removed) are also present."""
    base_paths = data.draw(st.lists(_ENTRY, min_size=1, max_size=8, unique=True))
    removed = data.draw(st.lists(st.sampled_from(base_paths), max_size=len(base_paths), unique=True))
    waived = data.draw(st.lists(st.sampled_from(removed), max_size=len(removed), unique=True)) if removed else []
    # A decoy waiver naming an entry that was never removed must not affect
    # the outcome -- exercises that matching is per-entry, not "any waiver
    # comment present at all suppresses every finding".
    decoy = data.draw(st.lists(_ENTRY.filter(lambda p: p not in base_paths), max_size=3, unique=True))

    kept_paths = [path for path in base_paths if path not in removed]
    base_text = _build_toml(base_paths)
    head_text = _build_toml(kept_paths)
    for entry in waived + decoy:
        head_text += f"\n# betterleaks-allowlist-no-removal: WAIVED: retired '''{entry}'''\n"

    expected = sorted(set(removed) - set(waived))
    actual = sorted(gate.find_unwaived_removals(base_text, head_text))
    assert actual == expected

"""Hypothesis differential-oracle property for
``.github/scripts/gitapex_gate_stdlib_only_claim_drift.py``'s
``parse_diff_added_third_party_imports`` (issue #1316).

The two sibling ``parse_added_lines``-family diff parsers
(``gitapex_gate_detection_logic_property_coverage.py``,
``gitapex_gate_exception_handler_gaps.py``) already gained a differential
property comparing their own ``{path: added-lines}`` output against
``unidiff``'s own independent parse of the same generated diff (see
``tests/test_gitapex_gate_detection_logic_property_coverage_properties.py``
and ``tests/test_gitapex_gate_exception_handler_gaps_properties.py``, both
this same issue). This file adds the third: ``parse_diff_added_third_party_imports``
returns a different shape (a bare ``set[str]`` of changed file paths, not
a per-line ``{path: added-lines}`` dict), so its own oracle combines
``unidiff``'s independent added-line identification with this file's own
already-unit-tested ``_imported_root_modules``/``_is_stdlib`` import-
classification helpers -- isolating exactly the added-line misattribution
class this issue's own bug (and its fix) concerns, without re-deriving the
classification logic itself.

``derandomize=True`` with an explicit ``max_examples`` and ``deadline=None``,
matching both sibling property files' own "Reproducibility" convention --
not repeated here beyond this pointer.
"""

from __future__ import annotations

import os

import gitapex_gate_stdlib_only_claim_drift as gate
import unidiff
from hypothesis import given, settings
from hypothesis import strategies as st

# Issue #1316: the PR-blocking gate's own invocation (this default branch)
# stays pinned exactly as before -- fast and deterministic. A separate,
# scheduled, non-PR-blocking workflow
# (.github/workflows/diff-parsing-property-deep-scan.yml) sets
# GITAPEX_HYPOTHESIS_DEEP_SCAN=1 to re-run these same properties with much
# higher, randomized exploration instead, without touching this file's
# own default settings object or requiring a duplicate test body.
_PROPERTIES = (
    settings(derandomize=False, max_examples=5000, deadline=None)
    if os.environ.get("GITAPEX_HYPOTHESIS_DEEP_SCAN") == "1"
    else settings(derandomize=True, max_examples=200, deadline=None)
)


def _unidiff_third_party_import_files(diff_text: str) -> set[str]:
    """Issue #1316: an independent oracle for
    `parse_diff_added_third_party_imports`, computed by combining
    `unidiff`'s own independent added-line parse with this file's own
    `_imported_root_modules`/`_is_stdlib` classification helpers -- a
    genuinely different added-line-identification mechanism from this
    file's hand-rolled header/hunk state machine, applied to the same
    downstream classification so the comparison isolates exactly the
    added-line misattribution class this issue's own bug concerned."""
    changed: set[str] = set()
    for patched_file in unidiff.PatchSet(diff_text):
        path = patched_file.path
        if not gate._TARGET_DIR_RE.match(path):
            continue
        for hunk in patched_file:
            for line in hunk:
                if not line.is_added:
                    continue
                content = line.value.rstrip("\n")
                if content != content.lstrip():
                    continue
                if any(not gate._is_stdlib(name) for name in gate._imported_root_modules(content)):
                    changed.add(path)
    return changed


# Printable-ASCII identifier alphabet, matching the sibling property files'
# own path-generation discipline (no "/" or "." so a generated path's own
# directory segments/basename stay unambiguous).
_IDENT = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=16)
_ADDED_LINE_CHOICES = st.sampled_from(
    [
        "import pydantic",
        "from pydantic import BaseModel",
        "import os, pydantic",
        "import os",
        "import json",
        "if True:",
        "    import pydantic",  # indented -- never top-level, never flagged
    ]
)
_OTHER_LINE_KIND = st.sampled_from((" ", "-"))
# unidiff cannot parse a zero/zero declared hunk with an empty body (see
# the sibling property files' own identical note) -- min_size=1 keeps
# every generated hunk within unidiff's own parseable shape.
_HUNK_LINE = st.one_of(
    st.tuples(st.just("+"), _ADDED_LINE_CHOICES),
    st.tuples(_OTHER_LINE_KIND, st.just("unrelated content")),
)
_HUNK_BODY = st.lists(_HUNK_LINE, min_size=1, max_size=12)
_START_LINE = st.integers(min_value=1, max_value=200)
_FILE_DIFF = st.tuples(_START_LINE, _HUNK_BODY)
_MULTI_FILE_DIFFS = st.lists(_FILE_DIFF, min_size=1, max_size=3)


def _file_diff_text(path: str, start: int, hunk_lines: list[tuple[str, str]]) -> str:
    pre_image_count = sum(1 for kind, _ in hunk_lines if kind != "+")
    post_image_count = sum(1 for kind, _ in hunk_lines if kind != "-")
    body = [f"{kind}{content}" for kind, content in hunk_lines]
    lines = [
        f"diff --git a/{path} b/{path}",
        "index 0000000..1111111 100644",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,{pre_image_count} +{start},{post_image_count} @@",
        *body,
    ]
    return "\n".join(lines)


@_PROPERTIES
@given(file_diffs=_MULTI_FILE_DIFFS)
def test_parse_diff_added_third_party_imports_matches_unidiffs_independent_parse(
    file_diffs: list[tuple[int, list[tuple[str, str]]]],
) -> None:
    """Differential-oracle property (issue #1316). Compares
    `parse_diff_added_third_party_imports`'s own changed-file-path output
    against `_unidiff_third_party_import_files`'s independent parse of the
    identical generated diff text. True-negative coverage across many
    well-formed generated diffs (including indented, comma-separated, and
    `from`-form imports, and files carrying no third-party import at all);
    the corresponding true-positive check (does this oracle catch the real
    header-misattribution defect class this issue's own bug fixed) is
    recorded as a fixed regression case rather than a Hypothesis property,
    matching both sibling property files' own identical rationale -- see
    `tests/test_gitapex_gate_stdlib_only_claim_drift.py`'s own regression
    suite and this task's own commit message for that proof.
    """
    paths = [f".github/scripts/gitapex_gate_{index}_x.py" for index in range(len(file_diffs))]
    diff_text = "\n".join(
        _file_diff_text(path, start, hunk_lines) for path, (start, hunk_lines) in zip(paths, file_diffs, strict=True)
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == _unidiff_third_party_import_files(diff_text)

"""Regression suite for _path_normalize.py's own normalize() function.

Imported directly (not via subprocess): unlike this directory's other
checker scripts, _path_normalize.py has no CLI of its own -- it is a
sibling import for check_file_ownership_conflicts.py and
check_canonical_governance_paths.py, per its own module docstring. This
file existing at all closes a real gap: before it, normalize() was only
tested indirectly through those two consumer scripts' own subprocess
tests, which is exactly how an order-of-operations bug (see
test_leading_dotslash_immediately_followed_by_slash below) went
untested by either -- neither consumer test suite happened to combine a
leading "./" with an immediately adjacent "/".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _path_normalize import normalize


def test_leading_dotslash_prefix():
    assert normalize("./a.py") == "a.py"


def test_double_slash():
    assert normalize("a//b.py") == "a/b.py"


def test_embedded_dotslash_segment():
    assert normalize("a/./b.py") == "a/b.py"


def test_backslash_to_forward_slash():
    assert normalize("a\\b.py") == "a/b.py"


def test_leading_dotslash_immediately_followed_by_slash():
    # Independent /code-review finding (gitapex issue #659 PR): an
    # earlier version of normalize() stripped a leading "./" BEFORE
    # collapsing "//", so ".//skills/foo/SKILL.md" became
    # "/skills/foo/SKILL.md" -- a leftover single leading slash that no
    # longer matched either the "//" or "./" cleanup pass, and was
    # silently never removed. Collapsing "//" first (turning ".//x"
    # into "./x", now strippable) fixes this; this test pins the fix.
    assert normalize(".//skills/foo/SKILL.md") == "skills/foo/SKILL.md"
    assert normalize(".//.github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert normalize(".//pyproject.toml") == "pyproject.toml"


def test_multiple_leading_slashes_after_dotslash_strip():
    assert normalize(".///foo") == "foo"


def test_dotslash_collapse_can_expose_a_fresh_double_slash():
    assert normalize("a/.//b") == "a/b"


def test_no_change_needed():
    assert normalize("a/b.py") == "a/b.py"

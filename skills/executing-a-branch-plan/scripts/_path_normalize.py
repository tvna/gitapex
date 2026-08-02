"""Shared path-normalization helper for this directory's checker scripts.

Both `check_file_ownership_conflicts.py` (task-decomposition.md's
file-ownership pre-filter) and `check_canonical_governance_paths.py`
(threat-model-and-authorization.md's per-task screening pre-filter) need
the exact same light normalization before comparing paths as strings:
strip a leading "./" and collapse backslashes to forward slashes. Not a
full path-canonicalization -- no glob, no symlink resolution, no
case-folding; each caller's own module docstring states that scope
limit for its own use of this function.

Leading underscore, same convention as this directory's other
single-underscore "not a public entry point" names: this module is a
sibling import for the two checker scripts above, not something invoked
directly.
"""
from __future__ import annotations


def normalize(path):
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized

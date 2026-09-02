"""Shared path-normalization helper for this directory's checker scripts.

Both `gitapex_check_file_ownership_conflicts.py` (decomposition-and-
dispatch.md's file-ownership pre-filter) and `gitapex_check_canonical_governance_paths.py`
(threat-model-and-authorization.md's per-task screening pre-filter) need
the exact same light normalization before comparing paths as strings:
strip a leading "./", collapse backslashes to forward slashes, collapse
redundant "//" runs, and resolve embedded "/./" segments. These four are
pure lexical/string operations, unambiguous for any two paths that
denote the exact same file regardless of working directory or
filesystem (unlike a leading "/" absolute-path marker, a trailing "/",
or a ".." segment, each of which can genuinely change what a path
resolves to and are deliberately left untouched here). Not a full
path-canonicalization -- no glob, no symlink resolution, no
case-folding, no ".." resolution, no absolute/relative reconciliation,
no trailing-"/" stripping; each caller's own module docstring states
that scope limit for its own use of this function.

Leading underscore, same convention as this directory's other
single-underscore "not a public entry point" names: this module is a
sibling import for the two checker scripts above, not something invoked
directly.
"""

from __future__ import annotations


def normalize(path: str) -> str:
    """Fixed-point iteration, not a single fixed pass order: a leading
    "./" immediately followed by another "/" (e.g. ".//skills/x") is
    itself a "//"-shaped redundancy that is only exposed by collapsing
    "//" BEFORE stripping the leading "./" -- collapse-then-strip turns
    ".//skills/x" into "./skills/x" (now strippable) into "skills/x"; the
    reverse order (an earlier version of this function, found wrong by
    an independent /code-review pass on this repository's own gitapex
    issue #659 PR) strips "./" first, leaving a bare leading "/" that no
    longer matches either "//" or "./" and is silently never cleaned up.
    Collapsing "/./" can likewise expose a fresh "//" (e.g. "a/.//b"), so
    every reduction re-runs every outer iteration until none of them
    changes the string, rather than trusting any single fixed pass
    order."""
    normalized = path.replace("\\", "/")
    while True:
        previous = normalized
        while "//" in normalized:
            normalized = normalized.replace("//", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        while "/./" in normalized:
            normalized = normalized.replace("/./", "/")
        if normalized == previous:
            return normalized

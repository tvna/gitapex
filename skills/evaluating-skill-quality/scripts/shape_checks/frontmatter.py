"""YAML frontmatter block parsing (the ---...--- header at the top of a
SKILL.md), independent of the metadata sidecar manifest parser in
manifest.py."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from shape_checks.constants import BLOCK_SCALAR_INDICATORS


@dataclass(frozen=True)
class FrontmatterParse:
    """Result of ``_parse_frontmatter``: the parsed top-level scalar fields,
    plus which of them were written as an unquoted YAML plain scalar rather
    than quoted or a block scalar (``>``/``|``).

    Only a plain scalar is at risk of the ": "/trailing ":"/" #" hazard
    ``_yaml_plain_scalar_safety_check`` exists to catch -- a quoted or
    block-scalar value is already safe under a real YAML parser regardless
    of what characters it contains, so a caller needs to know which form a
    field actually used, not just its already-unquoted/already-joined
    value in ``fields``.
    """

    fields: dict[str, str]
    plain_fields: frozenset[str]


def _parse_frontmatter(text: str) -> FrontmatterParse:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Handles the scalar forms real SKILL.md files use: plain, single/double
    quoted, and YAML block scalars (folded '>' and literal '|', whose
    indented continuation lines are joined). Strips a leading UTF-8 BOM and
    requires a closing '---'; without one the frontmatter is treated as
    malformed (returns an empty result), rather than reading body lines as
    fields. No external YAML dependency.
    """
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    fields: dict[str, str] = {}
    plain_fields: set[str] = set()
    i = 1
    while i < end:
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in BLOCK_SCALAR_INDICATORS:
            block: list[str] = []
            i += 1
            while i < end and (lines[i].strip() == "" or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value[0] == "|" else " "
            fields[key] = joiner.join(block).strip()
            continue
        is_quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"
        fields[key] = _unquote(value)
        if not is_quoted:
            plain_fields.add(key)
        i += 1
    return FrontmatterParse(fields=fields, plain_fields=frozenset(plain_fields))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        if value[0] == '"':
            # A double-quoted YAML scalar's escaping is a superset-safe
            # match for JSON string escaping (this repository's own
            # sidecar-generation method deliberately relies on that: see
            # the design plan's Task 1, which builds these values with
            # json.dumps). Decoding via the stdlib json module handles
            # every escape a generator might emit (\", \\, \n, \uXXXX, ...).
            # Fall back to a naive strip on decode failure (e.g. a stray
            # unescaped literal quote) rather than raising -- this parser
            # never raises on malformed sidecar content.
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
            if isinstance(decoded, str):
                return decoded
        return value[1:-1]
    return value
